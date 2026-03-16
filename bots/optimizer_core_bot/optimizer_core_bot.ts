// src/clockwork/bots/optimizer_core_bot/optimizer_core_bot.ts
// PURE implementation (no aionmind_core). Port-and-improve based on an original Python optimizer_core.
// Adheres to the canvas Bot standards.
import { InputSchema, OutputSchema, Input, Output, OriginalSpecSchema, CoreSpecSchema } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { selectPath, recordPath } from './internal/shim_golden_paths';
import { computeS, decideAction } from './internal/shim_stability';
import { callModel } from './internal/shim_model_proxy';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const COST_REF_USD = 0.01;
const LATENCY_REF_S = 1.5;
const KAIA_MIX = { kiren: 0.55, veritas: 0.3, vallon: 0.15 }; // plan-heavy, with verification & budget awareness

function preview(o:any, max=512){ try { return JSON.stringify(o).slice(0,max); } catch { return String(o).slice(0,max); } }

function tryParseJSON(s?: string): any | undefined {
  if (!s) return undefined;
  try { return JSON.parse(s); } catch { return undefined; }
}

function normalizeSpec(input: Input): any {
  // Look in params.spec or first text attachment for a JSON spec
  let raw = (input.params as any)?.spec || undefined;
  if (!raw && input.attachments?.length) {
    const textBlob = input.attachments.find(a => a.type === 'text')?.text;
    raw = tryParseJSON(textBlob);
  }
  // Try original spec, else try core spec; else return undefined and let model proxy synthesize
  if (raw) {
    const orig = OriginalSpecSchema.safeParse(raw);
    if (orig.success) {
      // map original -> core
      const variables = orig.data.variables.map(v => (v.choices
        ? { name: v.name, kind: v.type, domain: { choices: v.choices }, init: v.default }
        : { name: v.name, kind: v.type, domain: { min: (v.min??0), max: (v.max??1) }, init: v.default }
      ));
      return {
        objective: orig.data.objective,
        direction: orig.data.direction,
        metric: orig.data.metric,
        variables,
        constraints: (orig.data.constraints||[]).map(c => c.expr || '').filter(Boolean),
        algorithm: (['grid','random','bayes','tpe','cmaes','nevergrad'].includes((orig.data.algorithm||'').toLowerCase()) ? (orig.data.algorithm||'bayes').toLowerCase() : 'bayes'),
        stop: { max_evals: orig.data.budget_evals || 50 }
      };
    }
    const core = CoreSpecSchema.safeParse(raw);
    if (core.success) return core.data;
  }
  return undefined;
}

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // Quota
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot:'optimizer_core_bot', reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  // Budget
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot:'optimizer_core_bot', reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  // GP reuse
  const taskKey = { task_type: input.task.slice(0,128), params_preview: preview(input.params), software_signature_preview: preview(input.software_signature,256) };
  let gpCandidate: any = null;
  try { gpCandidate = await selectPath(ctx.db, taskKey as any, Math.max(1, Math.floor((input.constraints?.budget_hint_usd||0.001)*1000))); } catch(e) { ctx.logger?.warn?.('selectPath failed', e); }

  if (gpCandidate?.spec && gpCandidate.confidence >= 0.8) {
    const out: Output = {
      result: gpCandidate.spec,
      confidence: gpCandidate.confidence,
      notes: ['golden_path_reuse'],
      meta: { budget: { tier, pool:'gp' }, gp: { hit: true, key: taskKey as any, spec_id: gpCandidate.id }, stability: { S: 1.0, action:'continue' }, kaiaMix: KAIA_MIX },
      provenance: [`gp:${gpCandidate.id}`]
    };
    await emit('run.complete', { bot:'optimizer_core_bot', gp_hit: true, userId, tier, success: true }, ctx);
    await recordPath(ctx.db, { task_type: 'optimizer_core_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result });
    return out;
  }

  // Build prompt: if we have a normalized core spec, pass it through; else ask model proxy to synthesize
  const core_spec = normalizeSpec(input);
  const systemMsg = { role:'system', content: [
    'You are OptimizerCore. Your job is to produce a normalized optimization plan: core_spec, initial_points, best_guess.',
    'Emit strict JSON; no prose.'
  ].join('\n') };
  const userMsg = { role:'user', content: JSON.stringify({ input: { ...input, spec: core_spec ? { core_spec } : undefined } }) };
  const profile = (tier==='teams'||tier==='pro'||tier==='enterprise') ? 'turbo' : 'mini';

  const t0 = Date.now();
  const res = await callModel({ profile, messages:[systemMsg as any, userMsg as any], json: true, maxTokens: 900 });
  const usage = res.usage || { tokens_in:0, tokens_out:0, cost_usd:0, model: profile };

  // normalize result
  let plan = res.result?.optimization ?? res.result ?? null;
  if (typeof plan === 'string') { try { plan = JSON.parse(plan); } catch { plan = null; } }
  if (!plan?.core_spec) plan = { core_spec: (core_spec || { objective:'minimize loss', direction:'minimize', metric:'loss', variables:[{name:'x', kind:'float', domain:{min:0,max:1}}], constraints:[], algorithm:'bayes', stop:{max_evals:50} }) };

  const latency_ms = Date.now() - t0;
  const confidence = 0.8;

  // Stability
  const S = computeS(confidence, usage.cost_usd, latency_ms, undefined, { costRefUsd: COST_REF_USD, latencyRefS: LATENCY_REF_S });
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gpCandidate?.spec });
  const notes: string[] = [];
  if (decision.action==='fallback_gp' && gpCandidate?.spec) { plan = (gpCandidate.spec as any).optimization ?? plan; notes.push('fallback_to_gp_due_to_stability'); }
  else if (decision.action==='downgrade') { notes.push('downgrade_due_to_stability'); }

  // Charge
  const pool = (tier==='free_na'||tier==='free'||tier==='starter') ? 'free' : 'paid';
  await chargeCost(ctx.db, { amount_cents: Math.round((usage.cost_usd||0)*100), month: undefined, tier });

  // Optional microtasks
  const tasks = [
    { id:'t1', title:'validate core_spec and constraints', requires:['optimizer_access'], est_time_min:2 },
    { id:'t2', title:'submit optimization job (max_evals)', requires:['optimizer_access'], est_time_min:3 },
  ];

  const out: Output = {
    result: { optimization: plan, tasks, chain_id: `opt_${Date.now()}`, level: 2 },
    confidence,
    notes,
    meta: { budget: { tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, tier, pool }, gp: { hit: !!gpCandidate, key: taskKey as any, spec_id: gpCandidate?.id }, stability: { S, action: decision.action }, kaiaMix: KAIA_MIX },
    provenance: (gpCandidate ? [`gp:${gpCandidate.id}`] : []),
  };

  const v = OutputSchema.safeParse(out);
  if (!v.success) {
    await emit('run.complete', { bot:'optimizer_core_bot', userId, tier, success:false, reason:'validation_failed' }, ctx);
    return { result: { optimization: plan, chain_id: `opt_${Date.now()}` }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any;
  }

  try { await recordPath(ctx.db, { task_type: 'optimizer_core_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result }); } catch {}

  await emit('run.complete', { bot:'optimizer_core_bot', userId, tier, tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, latency_ms, gp_hit: !!gpCandidate, success: true }, ctx);
  return out;
}

export default { run };

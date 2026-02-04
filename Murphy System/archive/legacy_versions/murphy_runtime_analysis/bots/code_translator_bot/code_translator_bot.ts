// src/clockwork/bots/code_translator_bot/code_translator_bot.ts
// Combined "Code Translator + Coding Bot" — PURE implementation. Adheres to the canvas Bot standards.
import { InputSchema, OutputSchema, Input, Output } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { selectPath, recordPath } from './internal/shim_golden_paths';
import { computeS, decideAction } from './internal/shim_stability';
import { callModel } from './internal/shim_model_proxy';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const COST_REF_USD = 0.01;
const LATENCY_REF_S = 1.5;
const KAIA_MIX = { kiren: 0.5, veritas: 0.4, vallon: 0.1 }; // generate/fix + verify + budget awareness

function preview(o:any, max=512){ try { return JSON.stringify(o).slice(0,max); } catch { return String(o).slice(0,max); } }

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // Quota
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot:'code_translator_bot', reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  // Budget
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot:'code_translator_bot', reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

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
    await emit('run.complete', { bot:'code_translator_bot', gp_hit: true, userId, tier, success: true }, ctx);
    await recordPath(ctx.db, { task_type: 'code_translator_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result });
    return out;
  }

  // Model proxy
  const systemMsg = { role:'system', content: [
    'You are CodeTranslatorCodingBot. Emit STRICT JSON only matching {patches[], tests[], explain?}.',
    'Perform translation/refactor/fix/explain/tests based on input intent. No prose.'
  ].join('\n') };
  const userMsg = { role:'user', content: JSON.stringify({ input }) };
  const profile = (tier==='teams'||tier==='pro'||tier==='enterprise') ? 'turbo' : 'mini';

  const t0 = Date.now();
  const res = await callModel({ profile, messages:[systemMsg as any, userMsg as any], json: true, maxTokens: 1200 });
  const usage = res.usage || { tokens_in:0, tokens_out:0, cost_usd:0, model: profile };
  let result = res.result ?? null;
  if (typeof result === 'string') { try { result = JSON.parse(result); } catch { result = null; } }
  if (!result?.patches) result = { patches: [], tests: [], explain: { summary: 'fallback', key_points: [], risks: [] } };

  const latency_ms = Date.now() - t0;
  const confidence = Math.min(1, Math.max(0, (result.patches?.length ? 0.85 : 0.6)));

  // Stability
  const S = computeS(confidence, usage.cost_usd, latency_ms, undefined, { costRefUsd: COST_REF_USD, latencyRefS: LATENCY_REF_S });
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gpCandidate?.spec });
  const notes: string[] = [];
  if (decision.action==='fallback_gp' && gpCandidate?.spec) { result = gpCandidate.spec; notes.push('fallback_to_gp_due_to_stability'); }
  else if (decision.action==='downgrade') { notes.push('downgrade_due_to_stability'); }

  // Cost
  const pool = (tier==='free_na'||tier==='free'||tier==='starter') ? 'free' : 'paid';
  await chargeCost(ctx.db, { amount_cents: Math.round((usage.cost_usd||0)*100), month: undefined, tier });

  const out: Output = {
    result,
    confidence,
    notes,
    meta: { budget: { tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, tier, pool }, gp: { hit: !!gpCandidate, key: taskKey as any, spec_id: gpCandidate?.id }, stability: { S, action: decision.action }, kaiaMix: KAIA_MIX },
    provenance: (gpCandidate ? [`gp:${gpCandidate.id}`] : []),
  };

  const v = OutputSchema.safeParse(out);
  if (!v.success) {
    await emit('run.complete', { bot:'code_translator_bot', userId, tier, success:false, reason:'validation_failed' }, ctx);
    return { result, confidence: 0, notes:['validation_failed'], meta: out.meta } as any;
  }

  try { await recordPath(ctx.db, { task_type: 'code_translator_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result }); } catch {}

  await emit('run.complete', { bot:'code_translator_bot', userId, tier, tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, latency_ms, gp_hit: !!gpCandidate, success: true }, ctx);
  return out;
}

export default { run };

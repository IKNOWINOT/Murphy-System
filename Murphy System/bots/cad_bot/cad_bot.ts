// src/clockwork/bots/cad_bot/cad_bot.ts
// Ported from Python `third_party/original/SYN_CORE/agents/modern_arcana/cad_bot.py` (entities+units schema)
// and upgraded to the Bot standards: quotas, budget guard/charge, GP reuse/record, stability S(t), observability.

import { InputSchema, OutputSchema, Input, Output, CADSpecSchema } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { selectPath, recordPath } from './internal/shim_golden_paths';
import { computeS, decideAction } from './internal/shim_stability';
import { callModel } from './internal/shim_model_proxy';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const COST_REF_USD = 0.01;
const LATENCY_REF_S = 1.5;
const KAIA_MIX = { kiren: 0.55, veritas: 0.35, vallon: 0.10 };  // planning & verification heavy

function preview(o:any, max=512){ try { return JSON.stringify(o).slice(0,max); } catch { return String(o).slice(0,max); } }

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // ===== 1) Quota
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot:'cad_bot', reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  // ===== 2) Budget
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot:'cad_bot', reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  // ===== 3) GP reuse
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
    await emit('run.complete', { bot:'cad_bot', gp_hit: true, userId, tier, success: true }, ctx);
    await recordPath(ctx.db, { task_type: 'cad_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result });
    return out;
  }

  // ===== 4) Model call — prompt mirrors Python cad_bot.py intent (entities + units JSON only)
  const units = (input.params?.units || 'mm');
  const systemMsg = { role:'system', content: [
    'You are CADBot. Emit ONLY JSON matching this schema: {entities:[{type,params}], units}.',
    'No prose; no comments; no code block fences. Entities define parametric CAD primitives/ops.'
  ].join('\n') };
  const userMsg = { role:'user', content: JSON.stringify({ input: { ...input, params: { ...input.params, units } } }) };
  const profile = (tier==='teams'||tier==='pro'||tier==='enterprise') ? 'turbo' : 'mini';

  const t0 = Date.now();
  const res = await callModel({ profile, messages:[systemMsg as any, userMsg as any], json: true, maxTokens: 900 });
  const usage = res.usage || { tokens_in:0, tokens_out:0, cost_usd:0, model: profile };

  // validate CAD spec; apply Python-style fallback on parse/shape issues
  let draft = res.result?.cad_spec ?? res.result ?? null;
  // Accept strings -> try parse
  if (typeof draft === 'string') { try { draft = JSON.parse(draft); } catch { draft = null; } }
  // If model returned a wrapper {cad_spec:{...}}, unwrap
  if (draft && draft.cad_spec) draft = draft.cad_spec;

  // Fallback (like Python): single box 1x1x1 in meters (but use user's units default)
  let cad_spec = (() => {
    const candidate = CADSpecSchema.safeParse(draft);
    if (candidate.success) return candidate.data;
    return { entities: [{ type:'box', params:{ w:1, h:1, d:1 } }], units };
  })();

  const latency_ms = Date.now() - t0;
  const confidence = 0.8; // can be improved with downstream validation

  // ===== 5) Stability
  const S = computeS(confidence, usage.cost_usd, latency_ms, undefined, { costRefUsd: COST_REF_USD, latencyRefS: LATENCY_REF_S });
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gpCandidate?.spec });
  const notes: string[] = [];
  if (decision.action==='fallback_gp' && gpCandidate?.spec) { cad_spec = (gpCandidate.spec as any).cad_spec ?? cad_spec; notes.push('fallback_to_gp_due_to_stability'); }
  else if (decision.action==='downgrade') { notes.push('downgrade_due_to_stability'); }

  // ===== 6) Charge
  const pool = (tier==='free_na'||tier==='free'||tier==='starter') ? 'free' : 'paid';
  await chargeCost(ctx.db, { amount_cents: Math.round((usage.cost_usd||0)*100), month: undefined, tier });

  // Optional microtasks (downstream steps) — create simple export/validate chain
  const tasks = [
    { id:'t1', title:`validate CAD spec (${units})`, requires:['cad_engine'], est_time_min:2 },
    { id:'t2', title:'export STEP and DXF', requires:['cad_engine','file_access'], est_time_min:3 },
  ];

  const out: Output = {
    result: { cad_spec, tasks, chain_id: `cad_${Date.now()}`, level: 2 },
    confidence,
    notes,
    meta: { budget: { tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, tier, pool }, gp: { hit: !!gpCandidate, key: taskKey as any, spec_id: gpCandidate?.id }, stability: { S, action: decision.action }, kaiaMix: KAIA_MIX },
    provenance: (gpCandidate ? [`gp:${gpCandidate.id}`] : []),
  };

  const v = OutputSchema.safeParse(out);
  if (!v.success) {
    await emit('run.complete', { bot:'cad_bot', userId, tier, success:false, reason:'validation_failed' }, ctx);
    return { result: { cad_spec, chain_id: `cad_${Date.now()}` }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any;
  }

  try { await recordPath(ctx.db, { task_type: 'cad_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result }); } catch {}

  await emit('run.complete', { bot:'cad_bot', userId, tier, tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, latency_ms, gp_hit: !!gpCandidate, success: true }, ctx);
  return out;
}

export default { run };

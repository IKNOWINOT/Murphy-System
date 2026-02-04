// src/clockwork/bots/anomaly_watcher_bot/anomaly_watcher_bot.ts
// PURE implementation (no aionmind_core). Adheres to the canvas Bot standards.
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
const kaiaMix = { kiren: 0.2, veritas: 0.6, vallon: 0.2 }; // heavy on verification + gating

function preview(o:any, max=512){ try { return JSON.stringify(o).slice(0,max); } catch { return String(o).slice(0,max); } }

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // Quota
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot:'anomaly_watcher_bot', reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  // Budget
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot:'anomaly_watcher_bot', reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  // GP reuse
  const taskKey = { task_type: input.task.slice(0,128), params_preview: preview(input.params), software_signature_preview: preview(input.software_signature,256) };
  let gpCandidate: any = null;
  try { gpCandidate = await selectPath(ctx.db, taskKey as any, Math.max(1, Math.floor((input.constraints?.budget_hint_usd||0.001)*1000))); } catch(e) { ctx.logger?.warn?.('selectPath failed', e); }

  if (gpCandidate?.spec && gpCandidate.confidence >= 0.8) {
    const out: Output = {
      result: gpCandidate.spec,
      confidence: gpCandidate.confidence,
      notes: ['golden_path_reuse'],
      meta: {
        budget: { tier, pool:'gp' },
        gp: { hit: true, key: taskKey as any, spec_id: gpCandidate.id },
        stability: { S: 1.0, action:'continue' },
        kaiaMix
      },
      provenance: [`gp:${gpCandidate.id}`]
    };
    await emit('run.complete', { bot:'anomaly_watcher_bot', gp_hit: true, userId, tier, success: true }, ctx);
    await recordPath(ctx.db, { task_type: 'anomaly_watcher_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result });
    return out;
  }

  // Model call (compact JSON-mode prompt)
  const systemMsg = { role:'system', content: [
    'You are AnomalyWatcher. Given a monitoring/ops task, produce 1–3 ordered microtasks to:',
    ' - pull timeseries and compute baselines/outliers (e.g., z-score or IQR),',
    ' - compare to SLO/SLA or historical baseline,',
    ' - and triage/notify/open incident if thresholds are breached.',
    'Return strict JSON only.'
  ].join('\n') };
  const userMsg = { role:'user', content: JSON.stringify({ input }) };
  const profile = (tier==='teams'||tier==='pro'||tier==='enterprise') ? 'turbo' : 'mini';

  const t0 = Date.now();
  const res = await callModel({ profile, messages:[systemMsg as any, userMsg as any], json: true, maxTokens: 800 });
  const usage = res.usage || { tokens_in:0, tokens_out:0, cost_usd:0, model: profile };
  let normalized:any = typeof res.result==='object' && res.result ? res.result : (()=>{ try { return JSON.parse(String(res.result)); } catch { return { raw: res.result }; } })();
  const latency_ms = Date.now() - t0;
  const confidence = Math.min(1, Math.max(0, normalized.confidence ?? 0.8));

  // Stability
  const S = computeS(confidence, usage.cost_usd, latency_ms, undefined, { costRefUsd: COST_REF_USD, latencyRefS: LATENCY_REF_S });
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gpCandidate?.spec });
  let finalResult = normalized; const notes: string[] = normalized?.notes ? [...normalized.notes] : [];
  if (decision.action==='fallback_gp' && gpCandidate?.spec) { finalResult = gpCandidate.spec; notes.push('fallback_to_gp_due_to_stability'); }
  else if (decision.action==='downgrade') { notes.push('downgrade_due_to_stability'); }

  // Charge cost
  const pool = (tier==='free_na'||tier==='free'||tier==='starter') ? 'free' : 'paid';
  await chargeCost(ctx.db, { amount_cents: Math.round((usage.cost_usd||0)*100), month: undefined, tier });

  // Output
  const out: Output = {
    result: finalResult,
    confidence,
    notes,
    meta: {
      budget: { tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, tier, pool },
      gp: { hit: !!gpCandidate, key: taskKey as any, spec_id: gpCandidate?.id },
      stability: { S, action: decision.action },
      kaiaMix
    },
    provenance: normalized?.provenance ?? (gpCandidate ? [`gp:${gpCandidate.id}`] : []),
  };

  const v = OutputSchema.safeParse(out);
  if (!v.success) {
    await emit('run.complete', { bot:'anomaly_watcher_bot', userId, tier, success:false, reason:'validation_failed' }, ctx);
    return { result: { error:'validation_failed', details: out.result }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any;
  }

  try { await recordPath(ctx.db, { task_type: 'anomaly_watcher_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result }); } catch {}

  await emit('run.complete', { bot:'anomaly_watcher_bot', userId, tier, tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, latency_ms, gp_hit: !!gpCandidate, success: true }, ctx);
  return out;
}

export default { run };

// src/clockwork/bots/bot_base/bot_base.ts
// TEMPLATE bot (PURE). Adheres to the canvas Bot standards.
// ✅ To use: copy this folder, rename it, then set BOT_NAME and adjust KAIA_MIX + SYSTEM_PROMPT.
import { InputSchema, OutputSchema, Input, Output } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { selectPath, recordPath } from './internal/shim_golden_paths';
import { computeS, decideAction } from './internal/shim_stability';
import { callModel } from './internal/shim_model_proxy';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

// ======= EDIT THESE FOR YOUR NEW BOT =======
const BOT_NAME = 'bot_base';
const KAIA_MIX = { kiren: 0.4, veritas: 0.4, vallon: 0.2 };
const SYSTEM_PROMPT = [
  'You are a production-grade task bot. From the given input, produce 1–3 ordered microtasks that measurably advance the user goal.',
  '- Use short, actionable step titles.',
  '- Include required capabilities per step when obvious (e.g., drive_api_token).',
  '- Return strict JSON only.'
].join('\n');
// ===========================================

const COST_REF_USD = 0.01;
const LATENCY_REF_S = 1.5;

function preview(o:any, max=512){ try { return JSON.stringify(o).slice(0,max); } catch { return String(o).slice(0,max); } }

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // Quota
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot: BOT_NAME, reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  // Budget
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot: BOT_NAME, reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

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
        kaiaMix: KAIA_MIX
      },
      provenance: [`gp:${gpCandidate.id}`]
    };
    await emit('run.complete', { bot: BOT_NAME, gp_hit: true, userId, tier, success: true }, ctx);
    await recordPath(ctx.db, { task_type: BOT_NAME, key: taskKey as any, success: true, confidence: out.confidence, spec: out.result });
    return out;
  }

  // Model call
  const systemMsg = { role:'system', content: SYSTEM_PROMPT };
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
      kaiaMix: KAIA_MIX
    },
    provenance: normalized?.provenance ?? (gpCandidate ? [`gp:${gpCandidate.id}`] : []),
  };

  const v = OutputSchema.safeParse(out);
  if (!v.success) {
    await emit('run.complete', { bot: BOT_NAME, userId, tier, success:false, reason:'validation_failed' }, ctx);
    return { result: { error:'validation_failed', details: out.result }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any;
  }

  try { await recordPath(ctx.db, { task_type: BOT_NAME, key: taskKey as any, success: true, confidence: out.confidence, spec: out.result }); } catch {}

  await emit('run.complete', { bot: BOT_NAME, userId, tier, tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, latency_ms, gp_hit: !!gpCandidate, success: true }, ctx);
  return out;
}

export default { run };

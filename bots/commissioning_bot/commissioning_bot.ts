// src/clockwork/bots/commissioning_bot/commissioning_bot.ts
import { InputSchema, OutputSchema, Input, Output, CommissioningPlanSchema } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { selectPath, recordPath } from './internal/shim_golden_paths';
import { computeS, decideAction } from './internal/shim_stability';
import { callModel } from './internal/shim_model_proxy';
import { makeFPTForms } from './internal/forms/fpt';
import { normalizePlanUnits } from './internal/util/units';
import { mapRows } from './internal/adapters/point_map';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const COST_REF_USD = 0.01;
const LATENCY_REF_S = 1.5;
const KAIA_MIX = { veritas: 0.45, kiren: 0.4, vallon: 0.15 };

function preview(o:any, max=1024){ try { return JSON.stringify(o).slice(0,max); } catch { return String(o).slice(0,max); } }

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot:'commissioning_bot', reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot:'commissioning_bot', reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  const taskKey = { task_type: input.task.slice(0,128), params_preview: preview(input.params), software_signature_preview: preview(input.software_signature,512) };
  let gpCandidate: any = null;
  try { gpCandidate = await selectPath(ctx.db, taskKey as any, Math.max(1, Math.floor((input.constraints?.budget_hint_usd||0.001)*1000))); } catch(e) { ctx.logger?.warn?.('selectPath failed', e); }

  if (gpCandidate?.spec && gpCandidate.confidence >= 0.85) {
    const out: Output = {
      result: gpCandidate.spec,
      confidence: gpCandidate.confidence,
      notes: ['golden_path_reuse'],
      meta: { budget: { tier, pool:'gp' }, gp: { hit: true, key: taskKey as any, spec_id: gpCandidate.id }, stability: { S: 1.0, action:'continue' }, kaiaMix: KAIA_MIX },
      provenance: [`gp:${gpCandidate.id}`]
    };
    await emit('run.complete', { bot:'commissioning_bot', gp_hit: true, userId, tier, success: true }, ctx);
    await recordPath(ctx.db, { task_type: 'commissioning_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result });
    return out;
  }

  const systemMsg = { role:'system', content: [
    'You are CommissioningBot. Emit STRICT JSON matching { plan: {...} } per CommissioningPlanSchema.',
    'Include procedures with preconditions/steps/acceptance, risk register, schedule window, and deliverables.'
  ].join('\n') };
  const userMsg = { role:'user', content: JSON.stringify({ input }) };
  const profile = (tier==='teams'||tier==='pro'||tier==='enterprise') ? 'turbo' : 'mini';

  const t0 = Date.now();
  const res = await callModel({ profile, messages:[systemMsg as any, userMsg as any], json: true, maxTokens: 1400 });
  const usage = res.usage || { tokens_in:0, tokens_out:0, cost_usd:0, model: profile };

  let plan = res.result?.plan ?? res.result ?? null;
  if (typeof plan === 'string') { try { plan = JSON.parse(plan); } catch { plan = null; } }
  let planSafe = (() => { const v = CommissioningPlanSchema.safeParse(plan); return v.success ? v.data : { site: input.params?.site, system: input.params?.system || 'HVAC', assets: [], points: [], procedures: [], risk_register: { items: [] }, deliverables: [], schedule: { window: input.constraints?.window } }; })();

  // Unit normalization if requested
  if (input.params?.desired_units) {
    planSafe = normalizePlanUnits(planSafe, input.params.desired_units);
  }

  // Generate FPT checklist JSON templates
  const forms = makeFPTForms(planSafe);

  // Optional: if attachments include a point list text payload (CSV-like), try to map it into plan.points
  const pointListAttachment = (input.attachments || []).find(a=> (a.filename||'').toLowerCase().includes('.csv') || (a.text||'').includes(','));
  if (pointListAttachment?.text) {
    const rows = pointListAttachment.text.split(/\r?\n/).map(line => line.split(',')).filter(cols=>cols.length>=2);
    if (rows.length>1) {
      const headers = rows[0];
      const objects = rows.slice(1).map(r => {
        const o:any = {};
        headers.forEach((h, i) => { o[h.trim()] = (r[i]||'').trim(); });
        return o;
      });
      const mapped = mapRows(objects);
      for (const m of mapped) {
        if (!m.name) continue;
        planSafe.points.push({ name: m.name, point_type: (m.type||'AI'), unit: m.unit, source:'BAS' as any });
      }
    }
  }

  const latency_ms = Date.now() - t0;
  const confidence = Math.min(1, Math.max(0, (planSafe.procedures.length ? 0.9 : 0.7)));

  const S = computeS(confidence, usage.cost_usd, latency_ms, undefined, { costRefUsd: COST_REF_USD, latencyRefS: LATENCY_REF_S });
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gpCandidate?.spec });
  const notes: string[] = [];
  if (decision.action==='fallback_gp' && gpCandidate?.spec) { const gpPlan = (gpCandidate.spec as any).plan; if (gpPlan) { /* adopt GP */ } notes.push('fallback_to_gp_due_to_stability'); }
  else if (decision.action==='downgrade') { notes.push('downgrade_due_to_stability'); }

  const pool = (tier==='free_na'||tier==='free'||tier==='starter') ? 'free' : 'paid';
  await chargeCost(ctx.db, { amount_cents: Math.round((usage.cost_usd||0)*100), month: undefined, tier });

  const tasks = [
    { id:'t1', title:'Ingest BAS point list and map to plan.points', requires:['file_access'], est_time_min:5 },
    { id:'t2', title:'Generate FPT forms for each procedure', requires:['doc_access'], est_time_min:4 },
    { id:'t3', title:'Schedule commissioning window', requires:['calendar_access'], est_time_min:3 },
  ];

  const out: Output = {
    result: { plan: planSafe, tasks, chain_id: `cx_${Date.now()}`, level: 3 },
    confidence,
    notes,
    meta: { budget: { tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, tier, pool }, gp: { hit: !!gpCandidate, key: taskKey as any, spec_id: gpCandidate?.id }, stability: { S, action: decision.action }, kaiaMix: KAIA_MIX, forms },
    provenance: (gpCandidate ? [`gp:${gpCandidate.id}`] : []),
  };

  const v = OutputSchema.safeParse(out);
  if (!v.success) {
    await emit('run.complete', { bot:'commissioning_bot', userId, tier, success:false, reason:'validation_failed' }, ctx);
    return { result: { plan: planSafe }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any;
  }

  try { await recordPath(ctx.db, { task_type: 'commissioning_bot', key: taskKey as any, success: true, confidence: out.confidence, spec: out.result }); } catch {}

  await emit('run.complete', { bot:'commissioning_bot', userId, tier, tokens_in: usage.tokens_in, tokens_out: usage.tokens_out, cost_usd: usage.cost_usd, latency_ms, gp_hit: !!gpCandidate, success: true }, ctx);
  return out;
}

export default { run };

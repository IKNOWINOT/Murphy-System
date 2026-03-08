
import { InputSchema, OutputSchema, Input, Output } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { toGoldenPathKey } from './internal/adapters/goldenpath';
import { toIngestionPayload } from './internal/adapters/ingestion';
import { toGoldenPathSubmitPayload } from './internal/adapters/goldenpath_submit';
import { postGoldenPath } from './internal/adapters/gp_post';
import { toMicroTasks } from './internal/microtasks/microtasker';
import { validateMicroTasks } from './internal/microtasks/validator';
import { dailyQuestions, suggestionsFromHistory } from './internal/kaia/messenger';
import { buildProbabilityChain } from './internal/kaia/probability';
import { redact } from './internal/privacy/redactor';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas: 0.35, vallon: 0.45, kiren: 0.20 };

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // Allowlist hard-cap
  if (input.params?.allow_apps?.length) {
    const txt = (input.attachments||[]).find(a=>a.type==='events')?.text || '';
    if (txt && !input.params.allow_apps.some(app => txt.includes(app))) {
      await emit('run.blocked', { bot:'ghost_controller_bot', reason:'app_not_allowed', tier, allowlist: input.params.allow_apps }, ctx);
      const e:any = new Error('app_not_allowed'); e.status=403; e.body={ reason:'app_not_allowed' }; throw e;
    }
  }

  // Quota & budget
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked', { bot:'ghost_controller_bot', reason:'quota', tier, userId }, ctx); const e:any = new Error('quota exceeded'); e.status=429; e.body={reason:'quota'}; throw e; }

  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked', { bot:'ghost_controller_bot', reason:'hard_stop', tier, userId }, ctx); const e:any = new Error('budget_hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  // Ingest & redact
  let eventsText = (input.attachments||[]).find(a=>a.type==='events')?.text || '';
  if (input.params?.privacy?.redact) eventsText = redact(eventsText || '');

  // Synthesize minimal spec (focus_app step); your desktop adds richness
  const app = 'Unknown';
  const automation = { title:`Automation for ${app}`, steps:[{ id:'s1', action:'focus_app', args:{ app } }], triggers:['on_hotkey:Ctrl+Shift+G'], replay_notes:['Verify locators'] };
  const microtasks = toMicroTasks(automation);
  const validation = await validateMicroTasks(microtasks, true);
  const live_reports:any[] = [];

  const attention = { idle_events: 0, avg_idle_s: 0, context_switches: 0, top_apps:[{app,seconds:0}], keystroke_rate_hz: 0 };

  const taskKey = input.params?.gp_key || toGoldenPathKey((input as any).profile || {});
  const confidence = 0.86;

  await chargeCost(ctx.db, { amount_cents: 1, tier });

  // Kaia end-of-day clarifier
  const capture_ref = (input as any).profile?.timestamp || new Date().toISOString();
  const message = input.params?.kaia?.end_of_day ? { ts:new Date().toISOString(), questions: dailyQuestions(capture_ref), notes: ['End-of-day review'] } : undefined;
  const suggestions = suggestionsFromHistory(input.params?.kaia?.answers || [], 2);
  const probability_chain = buildProbabilityChain(microtasks, input.params?.kaia?.answers || []);

  // GP submit + optional POST
  const gp_payload = toGoldenPathSubmitPayload((input as any).profile || {}, microtasks, automation);
  let gp_post_status: string | undefined;
  if (input.params?.gp_post_endpoint){
    try { const r = await postGoldenPath(input.params.gp_post_endpoint, gp_payload); gp_post_status = r.ok ? 'posted' : ('error:'+(r.error||r.status)); } catch(e:any){ gp_post_status='error:'+String(e); }
  }

  const result = {
    task_summary: `Synthesized ${automation.steps.length} step(s) with privacy ${input.params?.privacy?.redact ? 'on' : 'off'}.`,
    automation_spec: automation,
    microtasks,
    validation,
    live_reports,
    attention,
    kaia: { message, suggestions, probability_chain },
    confidence,
    integrations: {
      osmosis_pack: eventsText,
      goldenpath_key: taskKey,
      ingestion_payload: toIngestionPayload((input as any).profile || {}, automation),
      goldenpath_submit: gp_payload,
      gp_post_status
    }
  };

  const out = { result, confidence, notes: [], meta: { kaiaMix: KAIA_MIX } } as any;
  return out;
}

export default { run };

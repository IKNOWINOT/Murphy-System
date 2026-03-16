
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { redact } from "./internal/privacy/redactor";
import { ambiguityScore } from "./internal/ambiguity/score";
import { ttcQuestions } from "./internal/ttc/questions";
import { makeTemplate } from "./internal/ttc/template";
import { buildPlan } from "./internal/ttc/build";
import { countNodes } from "./internal/planner/hierarchy";
import { wireDeps } from "./internal/planner/deps";
import { collectAcceptance } from "./internal/planner/acceptance";
import { synthesizePrompt } from "./internal/prompt/synthesize";
import { saveTemplate } from "./internal/storage/templates";
import { ingestToLibrarian } from "./internal/storage/librarian";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.35, vallon:0.2, kiren:0.45 };

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error("invalid input"); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;
  const tier = (ctx.tier||'free_na').toLowerCase();
  const userId = ctx.userId || 'anonymous';
  const goal = (input.params?.goal || '').trim() || (input.attachments?.[0]?.text || '').slice(0,200) || 'Untitled goal';
  const domain = input.params?.domain || 'engineering';

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed){ await emit('run.blocked',{bot:'plan_structurer_bot',reason:'quota',tier},ctx); const e:any=new Error('quota'); e.status=429; e.body={reason:'quota'}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed){ await emit('run.blocked',{bot:'plan_structurer_bot',reason:'hard_stop',tier},ctx); const e:any=new Error('hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  // GP reuse
  const keyPreview = JSON.stringify({ goal, domain }).slice(0,128);
  const gp = await selectPath(ctx.db, { task_type:'plan_structurer_bot', params_preview: keyPreview } as any, 1);
  if (gp?.spec && gp.confidence>=0.9){
    const out: Output = { result: gp.spec, confidence: gp.confidence, notes:['golden_path_reuse'], meta:{ budget:{tier, pool:'gp'}, gp:{hit:true,key:{fp:keyPreview},spec_id:gp.id}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const amb = ambiguityScore(goal);
  let questions:any[]|undefined = undefined;
  let template:any|undefined = undefined;
  let plan:any|undefined = undefined;
  let prompt:any|undefined = undefined;

  // TTC Phase 1: Clarify if ambiguous or user asked clarify/template
  if (input.task==='clarify' || amb>=0.5){
    questions = ttcQuestions(goal, domain).map((q,i)=> ({ ...q, id:`${q.axis}_${i+1}` }));
  }

  // TTC Phase 2: Template (if answers are present or not ambiguous)
  const answers = (input as any).answers || [];
  if (input.task==='template' || input.task==='build' || (questions && answers.length) || amb<0.5){
    template = makeTemplate(goal, answers||[]);
  }

  // TTC Phase 3: Build (hierarchy + prompt)
  if (template && (input.task==='structure' || input.task==='build' || input.task==='prompt' || amb<0.5)){
    plan = buildPlan(template, domain);
    // wire dependencies & acceptance
    plan.dependencies = wireDeps(plan.tree);
    plan.acceptance_tests = collectAcceptance(plan.tree);
    prompt = synthesizePrompt(goal, template, plan, (input.params?.verbosity||'normal') as any);
  }

  // Coverage metric for stability
  const nodes = plan ? countNodes(plan.tree) : 0;
  const coverage = Math.min(1, (template?1:0)*0.4 + (nodes>0?0.6:0));
  const passProb = Math.max(0.5, coverage);

  const latency_ms = 120;
  const cost_usd = 0.0006;
  const S = computeS(passProb, cost_usd, latency_ms);
  const decision = decideAction(S, { S_min:0.45, gpAvailable: !!gp?.spec });

  // Optional storage
  if (input.params?.store && template && prompt){
    const saved = await saveTemplate(ctx.db, (ctx as any)?.tenant||'t', goal, domain, template, prompt);
    try { await ingestToLibrarian(ctx, { id:saved.id, title:goal, text: prompt.long, tags:[`domain:${domain}`] }); } catch {}
  }

  const result:any = { questions, answers, template, plan, prompt };
  await recordPath(ctx.db, { task_type:'plan_structurer_bot', key:{ task_type:'plan_structurer_bot', params_preview: keyPreview } as any, success:true, confidence: passProb, spec: result });

  await chargeCost(ctx.db, { amount_cents: Math.round(cost_usd*100), tier });
  const out: Output = { result, confidence: passProb, notes: [], meta:{ budget:{ cost_usd, tier, pool:'mini' }, gp:{hit:false}, stability:{ S, action: decision.action }, kaiaMix: { veritas:0.35, vallon:0.2, kiren:0.45 } } as any };
  await emit('run.complete',{bot:'plan_structurer_bot',tier,cost_usd,latency_ms,gp_hit:false,success:true},ctx);
  return OutputSchema.parse(out);
}

export default { run };

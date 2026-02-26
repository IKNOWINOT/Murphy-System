
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { redact } from "./internal/privacy/redactor";

import { hydrate, fold as foldFn } from "./internal/hydrate/kaprekar";
import { fidelity as fidelityFn } from "./internal/hydrate/fidelity";
import { update as confUpdate, rank as confRank } from "./internal/confidence/registry";
import { barSpec } from "./internal/viz/bar";

import { summarize, corr } from "./internal/statistics/summary";
import { normalCDF, normalPDF, normalQuantile, expCDF, expPDF, expQuantile, binomPMF, binomCDF, poissonPMF, poissonCDF } from "./internal/probability/distributions";
import { ciMean, ciProp } from "./internal/inference/ci";
import { zTestMean, zTestProp, chiSquareIndependence } from "./internal/inference/hypothesis";
import { betaBinomial, normalNormal } from "./internal/bayes/update";
import { simulate } from "./internal/simulate/montecarlo";
import { ols } from "./internal/forecast/ols";
import { explainStats } from "./internal/report/summary";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.45, vallon:0.3, kiren:0.25 };

function parseJSON(text?:string){ try{ return text? JSON.parse(text): null }catch{ return null } }

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const p = InputSchema.safeParse(raw);
  if (!p.success){ const e:any=new Error('invalid input'); e.status=400; e.details=p.error.format(); throw e; }
  const input = p.data;
  const tier = (ctx.tier||'free_na').toLowerCase();
  const userId = ctx.userId || 'anonymous';
  const params = input.params||{};

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed){ await emit('run.blocked',{bot:'rubixcube_bot',reason:'quota',tier},ctx); const e:any=new Error('quota'); e.status=429; e.body={reason:'quota'}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed){ await emit('run.blocked',{bot:'rubixcube_bot',reason:'hard_stop',tier},ctx); const e:any=new Error('hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  const keyPreview = JSON.stringify({ task: input.task, params }).slice(0,128);
  const gp = await selectPath(ctx.db, { task_type:'rubixcube_bot', params_preview: keyPreview } as any, 1);
  if (gp?.spec && gp.confidence>=0.9){
    const out: Output = { result: gp.spec, confidence: gp.confidence, notes:['golden_path_reuse'], meta:{ budget:{tier, pool:'gp'}, gp:{hit:true,key:{fp:keyPreview},spec_id:gp.id}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const result:any = {};
  let passProb = 0.9;
  const t0 = Date.now();

  // Hydration & fold
  if (input.task==='hydrate'){
    const h = hydrate(params.seed||1337, params.shape||[64]);
    result.hydration = { tensor_name: params.tensor_name||'tensorA', seed: params.seed||1337, shape: h.shape, entropy_hint: params.entropy_hint||0 };
  }
  if (input.task==='fold'){
    const attData = parseJSON(input.attachments?.[0]?.text||'') as {data:number[], shape:number[]}|null;
    const data = attData?.data || new Array((params.shape||[64]).reduce((a,b)=>a*b,1)).fill(0).map((_,i)=>Math.random());
    const f = foldFn(data);
    result.fold = { length: data.length, topk: f.topk as any, stats: f.stats };
    result.viz = barSpec(data);
  }
  if (input.task==='score_path'){
    const att = parseJSON(input.attachments?.[0]?.text||'') as {original:number[], hydrated:number[]}|null;
    if (att && att.original && att.hydrated){
      const fid = fidelityFn(att.original, att.hydrated);
      confUpdate(params.path_key||'tensorA:∅', fid.cos, params.entropy_hint||0, params.hydration_cost||1);
      result.confidence = { path_key: params.path_key||'tensorA:∅', score: confRank()[0]?.[1]||0.5, fidelity: fid as any };
    }
    result.ranked_paths = confRank() as any;
  }
  if (input.task==='visualize'){
    const att = parseJSON(input.attachments?.[0]?.text||'') as {data:number[]}|null;
    const data = att?.data || [];
    result.viz = barSpec(data);
  }
  if (input.task==='report'){
    result.ranked_paths = confRank() as any;
  }
  if (input.task==='store'){
    result.ranked_paths = confRank() as any;
  }

  // Probability & Statistics
  if (input.task==='stats'){
    const data = params.data || parseJSON(input.attachments?.[0]?.text||'') || [];
    const s = summarize(data as number[]);
    result.stats = s as any;
    result.explain = explainStats(s);
  }
  if (input.task==='probability'){
    const d = params.dist||{name:'normal', params:[]};
    const x = params.x ?? 0;
    let val=NaN, kind='cdf';
    if (d.name==='normal'){ val=normalCDF(x, d.params[0]||0, d.params[1]||1); }
    if (d.name==='exp'){ val=expCDF(x, d.params[0]||1); }
    if (d.name==='binom'){ val=binomCDF(x, params.n||10, params.p||0.5); }
    if (d.name==='poisson'){ val=poissonCDF(x, d.params[0]||1); }
    result.prob = { value: val, kind };
  }
  if (input.task==='ci'){
    if (params.data){ result.ci = ciMean(params.data, params.alpha||0.05) as any; }
    else if (params.n!=null && params.p!=null){ result.ci = ciProp(Math.round((params.p||0)*Math.max(1,params.n||1)), params.n||1, params.alpha||0.05) as any; }
  }
  if (input.task==='hypothesis'){
    if (params.data && params.x!=null){ const t=zTestMean(params.data, params.x); result.test={statistic:t.statistic, p:t.p, df:t.df, reject: t.p<(params.alpha||0.05)}; }
    else if (params.n!=null && params.p!=null && params.p2!=null && params.n2!=null){ const t=zTestProp(Math.round((params.p2||0)*Math.max(1,params.n2||1)), params.n2||1, params.p||0.5); result.test={statistic:t.statistic,p:t.p,df:t.df,reject:t.p<(params.alpha||0.05)}; }
    else if (params.table){ const t=chiSquareIndependence(params.table as any); result.test={statistic:t.statistic,p:t.p,df:t.df,reject:false}; }
  }
  if (input.task==='bayes_update'){
    if (params.prior?.a!=null && params.prior?.b!=null && params.evidence?.success!=null && params.evidence?.trials!=null){ result.bayes = betaBinomial({a:params.prior.a,b:params.prior.b}, {success:params.evidence.success,trials:params.evidence.trials}) as any; }
    else if (params.prior?.mu!=null && params.prior?.tau!=null && params.evidence?.mean!=null && params.evidence?.n!=null && params.evidence?.sigma2!=null){ result.bayes = normalNormal({mu:params.prior.mu,tau:params.prior.tau},{mean:params.evidence.mean,n:params.evidence.n,sigma2:params.evidence.sigma2}) as any; }
  }
  if (input.task==='simulate'){
    const d=params.dist||{name:'normal',params:[0,1]};
    const out = simulate(d.name, d.params, params.runs||10000, { op: (params.event?.op||'gt') as any, threshold: params.event?.threshold||0 });
    result.simulate = out as any;
  }
  if (input.task==='forecast'){
    const s = params.series || [];
    const f = ols(s as number[]);
    result.forecast = f as any;
  }
  if (input.task==='explain_prob'){
    result.explain = "This module provides probability distributions (CDF/PDF/quantile for Normal/Exponential/Binomial/Poisson), confidence intervals, z-tests, chi-square tests, Bayesian updates (Beta-Binomial, Normal-Normal), Monte Carlo simulation, and simple OLS forecasting.";
  }

  const latency_ms = Date.now()-t0;
  const cost_usd = 0.0008;
  const S = computeS(passProb, cost_usd, latency_ms);
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gp?.spec });

  await recordPath(ctx.db, { task_type:'rubixcube_bot', key:{ task_type:'rubixcube_bot', params_preview: keyPreview } as any, success:true, confidence: passProb, spec: result });
  await chargeCost(ctx.db, { amount_cents: 1, tier });

  const out: Output = { result, confidence: passProb, notes: [], meta:{ budget:{ cost_usd, tier, pool:'mini' }, gp:{hit:false}, stability:{ S, action: decision.action }, kaiaMix: KAIA_MIX } as any };
  await emit('run.complete',{bot:'rubixcube_bot',tier,cost_usd,latency_ms,gp_hit:false,success:true},ctx);
  return OutputSchema.parse(out);
}

export default { run };

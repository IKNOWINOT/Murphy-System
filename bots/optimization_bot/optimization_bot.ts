
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { redact } from "./internal/privacy/redactor";
import * as exps from "./internal/d1/experiments";
import * as arms from "./internal/d1/arms";
import * as runs from "./internal/d1/runs";
import * as pol from "./internal/d1/policies";
import * as audit from "./internal/d1/audit";
import { getAlloc, setAlloc } from "./internal/kv/alloc";
import { thompsonSample } from "./internal/bandit/thompson";
import { choose as qChoose, update as qUpdate } from "./internal/qlearn/qtable";
import { suggestGrid } from "./internal/bayes/grid";
import { wilson } from "./internal/eval/ci";
import { proposeWithModelProxy } from "./internal/propose/model_proxy";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: D1Database; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.3, vallon:0.5, kiren:0.2 };

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error("invalid input"); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;
  const params = input.params||{};
  const tier = (ctx.tier || "free_na").toLowerCase();
  const userId = ctx.userId || "anonymous";

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit("run.blocked",{bot:"optimization_bot",reason:"quota",tier},ctx); const e:any = new Error("quota"); e.status=429; e.body={reason:"quota"}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit("run.blocked",{bot:"optimization_bot",reason:"hard_stop",tier},ctx); const e:any = new Error("hard_stop"); e.status=429; e.body={reason:"hard_stop"}; throw e; }

  // GP reuse
  const gp = await selectPath(ctx.db, { task_type:"optimization_bot", params_preview: JSON.stringify({task:input.task, target:params.target_bot, area:params.area}).slice(0,64) } as any, 1);

  // PROPOSE: create draft experiment arms (via model proxy stub)
  if (input.task==='propose'){
    if (!params.target_bot || !params.area) throw new Error("missing target_bot/area");
    const cand = params.arms || await proposeWithModelProxy(ctx, params.target_bot, params.area);
    const out: Output = { result: { exp_id: undefined, status: "draft", allocations: undefined, policy: undefined, report: { proposals: cand } }, confidence: 0.9, notes: [], meta:{ budget:{cost_usd:0.0005, tier, pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // START: persist experiment and arms
  if (input.task==='start'){
    if (!params.target_bot || !params.area) throw new Error("missing target_bot/area");
    const exp_id = params.exp_id || ('opt_'+Date.now());
    await exps.create(ctx.db!, { id: exp_id, ts_created:new Date().toISOString(), owner:userId, target_bot:params.target_bot, area:params.area, hypothesis: params.hypothesis||'', method: params.method||'bandit', status:'running', params: params, guardrails: params.guardrails||{}, primary_metric: params.primary_metric||'pass_rate', secondary_metrics: params.secondary_metrics||[] });
    const a = params.arms || [{ arm_id:'A', spec:{} }, { arm_id:'B', spec:{} }];
    await arms.upsertArms(ctx.db!, exp_id, a);
    // default 50/50 alloc (canary inside assign)
    await setAlloc(ctx.kv, exp_id, Object.fromEntries(a.map((x:any)=>[x.arm_id, 1/a.length])));
    await audit.audit(ctx.db!, 'opt.start', userId, { exp_id, target_bot: params.target_bot });
    const out: Output = { result: { exp_id, status:'running', allocations: Object.fromEntries(a.map((x:any)=>[x.arm_id, 1/a.length])) }, confidence: 0.9, notes: [], meta:{ budget:{cost_usd:0.0007, tier, pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // ASSIGN: decide which arm for a request context
  if (input.task==='assign'){
    if (!params.exp_id) throw new Error("missing exp_id");
    const alloc = await getAlloc(ctx.kv, params.exp_id) || {};
    const list = await arms.listArms(ctx.db!, params.exp_id);
    if (!list.length){ const out: Output = { result:{ assignment:{ arm_id: undefined }, status:'stopped' }, confidence:0.7, notes:['no_arms'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:0.7,action:'continue'}, kaiaMix: KAIA_MIX } as any }; return OutputSchema.parse(out); }
    // Thompson sampling
    const tsArms = list.map((r:any)=> ({ arm_id:r.arm_id, alpha:r.prior_alpha||1, beta:r.prior_beta||1 }));
    let arm_id = thompsonSample(tsArms);
    // canary gate
    const canary = (params.guardrails?.canary_pct ?? 0.05);
    if (Math.random()<canary){ arm_id = list[0].arm_id; } // hold first arm as baseline for canary
    const out: Output = { result:{ assignment:{ arm_id }, status:'running' }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // TRACK: log a run outcome and update posteriors / Q
  if (input.task==='track'){
    if (!params.exp_id || !params.arm_id) throw new Error("missing exp_id/arm_id");
    const passed = (params.reward||0) > 0 ? 1 : 0;
    await runs.logRun(ctx.db!, { id:'run_'+Date.now(), exp_id:params.exp_id, arm_id:params.arm_id, ts:new Date().toISOString(), ctx: params.context||{}, reward: params.reward||0, metrics: params.metrics||{}, passed, tokens_in:0, tokens_out:0, cost_cents:0, latency_ms: params.metrics?.latency_ms||0 });
    await arms.updatePosterior(ctx.db!, params.exp_id, params.arm_id, params.reward||0);
    await audit.audit(ctx.db!, 'opt.track', userId, { exp_id: params.exp_id, arm: params.arm_id, reward: params.reward });
    const out: Output = { result:{ exp_id: params.exp_id, status:'running' }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0.0003,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // STOP
  if (input.task==='stop'){
    if (!params.exp_id) throw new Error("missing exp_id");
    await exps.setStatus(ctx.db!, params.exp_id, 'stopped');
    await audit.audit(ctx.db!, 'opt.stop', userId, { exp_id: params.exp_id });
    const out: Output = { result:{ exp_id: params.exp_id, status:'stopped' }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0.0002,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // PROMOTE (write policy + GP record)
  if (input.task==='promote'){
    if (!params.exp_id || !params.policy) throw new Error("missing exp_id/policy");
    await pol.setPolicy(ctx.db!, params.target_bot||'unknown', params.policy);
    await audit.audit(ctx.db!, 'opt.promote', userId, { exp_id: params.exp_id, policy: params.policy });
    await recordPath(ctx.db, { task_type:'optimization_bot', key:{ task_type:'optimization_bot', params_preview: params.exp_id } as any, success:true, confidence:0.95, spec: params.policy });
    const out: Output = { result:{ exp_id: params.exp_id, status:'succeeded', policy: params.policy }, confidence:0.95, notes:[], meta:{ budget:{cost_usd:0.0003,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // REVERT
  if (input.task==='revert'){
    if (!params.exp_id || !params.target_bot) throw new Error("missing exp_id/target_bot");
    await pol.setPolicy(ctx.db!, params.target_bot, { baseline:true });
    await audit.audit(ctx.db!, 'opt.revert', userId, { exp_id: params.exp_id });
    const out: Output = { result:{ exp_id: params.exp_id, status:'reverted' }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0.0002,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // POLICY GET/SET
  if (input.task==='policy_get'){
    if (!params.target_bot) throw new Error("missing target_bot");
    const policy = await pol.getPolicy(ctx.db!, params.target_bot);
    const out: Output = { result:{ policy }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }
  if (input.task==='policy_set'){
    if (!params.target_bot || !params.policy) throw new Error("missing target_bot/policy");
    await pol.setPolicy(ctx.db!, params.target_bot, params.policy);
    const out: Output = { result:{ policy: params.policy }, confidence:0.95, notes:[], meta:{ budget:{cost_usd:0.0002,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // EVAL OFFLINE: query real A/B test data from D1, compute CI from actual results
  if (input.task==='eval_offline'){
    const exp_id = params.exp_id;
    let report: any;
    const notes: string[] = [];

    if (ctx.db && exp_id) {
      try {
        const res = await ctx.db.prepare('SELECT arm_id, passed, reward FROM opt_runs WHERE exp_id = ?').bind(exp_id).all();
        const rows: any[] = (res?.results || res || []);
        const armA = rows.filter((r:any) => r.arm_id === 'A');
        const armB = rows.filter((r:any) => r.arm_id === 'B');

        if (armA.length > 0 || armB.length > 0) {
          const nA = armA.length || 1;
          const nB = armB.length || 1;
          const pA = armA.length > 0 ? armA.filter((r:any) => r.passed).length / nA : 0;
          const pB = armB.length > 0 ? armB.filter((r:any) => r.passed).length / nB : 0;
          const [loA, hiA] = wilson(pA, nA);
          const [loB, hiB] = wilson(pB, nB);
          report = { pass_rate_A: pA, pass_rate_A_ci: [loA, hiA], n_A: nA, pass_rate_B: pB, pass_rate_B_ci: [loB, hiB], n_B: nB, uplift: pB - pA };
        } else {
          // No data in DB: use defaults with warning
          const pA=0.6,nA=100,pB=0.64,nB=100;
          const [lo,hi]=wilson(pB,nB);
          report = { pass_rate_B_ci:[lo,hi], uplift: pB-pA, warning: 'no_data_using_defaults' };
          notes.push('no_data_using_defaults');
        }
      } catch {
        // DB error: fall back to defaults
        const pA=0.6,nA=100,pB=0.64,nB=100;
        const [lo,hi]=wilson(pB,nB);
        report = { pass_rate_B_ci:[lo,hi], uplift: pB-pA, warning: 'no_data_using_defaults' };
        notes.push('no_data_using_defaults');
      }
    } else {
      // No DB or no exp_id: fall back to defaults
      const pA=0.6,nA=100,pB=0.64,nB=100;
      const [lo,hi]=wilson(pB,nB);
      report = { pass_rate_B_ci:[lo,hi], uplift: pB-pA, warning: 'no_data_using_defaults' };
      notes.push('no_data_using_defaults');
    }

    const out: Output = { result:{ report }, confidence:0.85, notes, meta:{ budget:{cost_usd:0.0003,tier,pool:'free'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const out: Output = { result: { status:'noop' }, confidence: 0.6, notes:['noop'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:!!gp}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
  return OutputSchema.parse(out);
}

export default { run };

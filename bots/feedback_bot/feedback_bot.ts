
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { computeS, decideAction } from "./internal/shim_stability";
import * as dbIngest from "./internal/db/ingest";
import * as dbAgg from "./internal/db/aggregates";
import * as act from "./internal/db/actions";
import * as decay from "./internal/analysis/decay";
import * as adaptive from "./internal/analysis/adaptive";
import * as robust from "./internal/analysis/robust";
import * as cluster from "./internal/analysis/cluster";
import * as bandit from "./internal/analysis/bandit";
import * as propose from "./internal/analysis/propose";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.5, vallon:0.3, kiren:0.2 };
const COST_REF = 0.01, LAT_REF_S = 1.5;

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error("invalid input"); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;
  const tier = (ctx.tier || "free_na").toLowerCase();
  const userId = ctx.userId || "anonymous";

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit("run.blocked",{bot:"feedback_bot",reason:"quota",tier},ctx); const e:any = new Error("quota"); e.status=429; e.body={reason:"quota"}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit("run.blocked",{bot:"feedback_bot",reason:"hard_stop",tier},ctx); const e:any = new Error("hard_stop"); e.status=429; e.body={reason:"hard_stop"}; throw e; }

  const taskKey = { task_type:"feedback_bot", task: input.task, window: input.params?.window };
  const gp = await selectPath(ctx.db, taskKey as any, 1);

  if (input.task === "ingest" && input.params?.events?.length) {
    await dbIngest.ingestEvents(ctx.db, input.params.events);
    await chargeCost(ctx.db, { amount_cents: 1, tier });
    const out: Output = { result: { scores: [], recurring_clusters: [], actions: [], ab_assignments: {} }, confidence: 0.9,
      meta: { budget:{cost_usd:0.0005,tier,pool:"mini"}, gp:{hit: false}, stability:{S:1, action:"continue"}, kaiaMix: KAIA_MIX } as any };
    await emit("run.complete",{bot:"feedback_bot",tier,success:true,mode:"ingest"},ctx);
    return OutputSchema.parse(out);
  }

  const rows = await dbAgg.loadWindow(ctx.db, input.params?.window);
  const strategy = input.params?.strategy || "decay";
  const half = input.params?.half_life_days || 3;
  const scores = (strategy === "adaptive")
    ? adaptive.score(rows, half)
    : (strategy === "seasonal" ? robust.seasonal(rows, half) : decay.score(rows, half));

  const rec = cluster.recurring(rows);

  let actions:any[] = [];
  if (input.task === "propose_actions" && input.params?.propose?.enabled) {
    const proposals = await propose.proposeActionsViaModelProxy(rec, ctx);
    actions = proposals.map(p => ({ ...p, gated: true }));
    await act.upsertSuggestedActions(ctx.db, actions);
  }

  let ab_assignments: Record<string,string> = {};
  if (input.task === "ab_test" && input.params?.bandit?.arms?.length) {
    ab_assignments = bandit.assignArms(input.params.bandit.arms);
  }

  const latency_ms = 200; const cost_usd = 0.001; const passProb = robust.estimatePassProb(rows);
  const S = computeS(passProb, cost_usd, latency_ms, undefined, { cr: COST_REF, lr: LAT_REF_S } as any);
  const decision = decideAction(S, { S_min:0.45, gpAvailable: !!gp?.spec });
  await chargeCost(ctx.db, { amount_cents: Math.round(cost_usd*100), tier });

  if (scores.length) {
    await recordPath(ctx.db, { task_type:"feedback_bot", key: taskKey as any, success: true, confidence: 0.9, spec: { scores } });
  }

  const result = { scores, recurring_clusters: rec, actions, ab_assignments };
  const out: Output = { result, confidence: 0.9, notes: [], meta: { budget:{cost_usd, tier, pool:"mini"}, gp:{hit: !!gp}, stability:{S, action: decision.action}, kaiaMix: KAIA_MIX } as any };
  await emit("run.complete",{bot:"feedback_bot",tier,success:true,model:"mini",cost_usd,latency_ms},ctx);
  return OutputSchema.parse(out);
}

export default { run };

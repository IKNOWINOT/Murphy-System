// Bot base wrapper — provides quota/budget enforcement for all bot functions.
export type Ctx = {
  userId?: string;
  tier?: string;
  kv?: any;
  db?: any;
  env?: any;
  emit?: (e: string, d: any) => any;
  logger?: { warn?: Function; error?: Function };
  runId?: string;
  startTs?: number;
};

const DEFAULT_BUDGET_LIMIT = 1.0; // $1.00 default cap
const BUDGET_WARN_THRESHOLD = 0.8; // warn when 80% consumed

export function withBotBase(_opts: any, fn: Function): Function {
  return async function wrappedBot(ctx: Ctx, ...args: any[]) {
    const startTs = Date.now();
    ctx.startTs = startTs;

    // Determine budget limit from env or use default
    const budgetLimit: number =
      ctx.env?.BUDGET_LIMIT != null
        ? parseFloat(ctx.env.BUDGET_LIMIT)
        : DEFAULT_BUDGET_LIMIT;

    // Retrieve cumulative cost from KV store if available
    let currentCost = 0;
    if (ctx.kv && ctx.runId) {
      try {
        const stored = await ctx.kv.get("bot_cost_" + ctx.runId);
        if (stored != null) {
          currentCost = parseFloat(stored) || 0;
        }
      } catch (kvErr) {
        // KV unavailable — proceed without cost tracking
        void kvErr;
      }
    }

    // Block execution if budget already exceeded
    if (budgetLimit > 0 && currentCost >= budgetLimit) {
      if (ctx.logger?.warn) {
        ctx.logger.warn(
          `[withBotBase] Budget exceeded: cost=${currentCost} limit=${budgetLimit} runId=${ctx.runId}`
        );
      }
      return { error: "budget_exceeded", cost: currentCost, limit: budgetLimit };
    }

    // Warn when approaching budget limit
    if (budgetLimit > 0 && currentCost / budgetLimit >= BUDGET_WARN_THRESHOLD) {
      if (ctx.logger?.warn) {
        ctx.logger.warn(
          `[withBotBase] Budget warning: ${(currentCost / budgetLimit * 100).toFixed(1)}% consumed ` +
            `(cost=${currentCost} limit=${budgetLimit})`
        );
      }
    }

    // Execute the wrapped function
    const result = await fn(ctx, ...args);

    // Record elapsed time on ctx
    (ctx as any).elapsedMs = Date.now() - startTs;

    return result;
  };
}

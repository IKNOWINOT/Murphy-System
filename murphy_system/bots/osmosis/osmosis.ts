import { OsmosisInput, OsmosisInputT, OsmosisOutput, OsmosisOutputT, OsmosisStep } from "./schema";
import { buildAttention, extractTokens } from "./attention";
import { callModel } from "../../orchestration/model_proxy";           // your OpenAI proxy (mini/turbo + metrics)
import { getTierPolicy } from "../../orchestration/tier_policy";       // quotas & model allowances
import { checkQuota } from "../../orchestration/quota_mw";             // KV-backed hourly guards

// Golden Path (safe wrappers to avoid hard deps if file layout differs)
async function gpSelect(taskKey: any, budgetTokens: number): Promise<any|null> {
  try {
    const gp = await import("../../clockwork/orchestration/experience/golden_paths");
    return gp.select_path(taskKey, budgetTokens);
  } catch { return null; }
}
async function gpRecord(spec: any): Promise<void> {
  try {
    const gp = await import("../../clockwork/orchestration/experience/golden_paths");
    await gp.record_path(spec);
  } catch { /* no-op */ }
}

// Observability helper (replace with your centralized emitter if present)
async function emit(event: string, data: Record<string,any>) {
  try {
    const m = await import("../../observability/emit");
    await (m as any).emit(event, data);
  } catch {
    // swallow in case not wired yet
  }
}

/**
 * runOsmosis:
 * - Builds attention report from tokens derived from Ghost profile + observations.
 * - Attempts GP reuse when similar signature/task exists (budget-aware).
 * - Otherwise calls the model via proxy, requesting strict JSON.
 * - Returns an inferred plan (not code-copy), plus confidence & attention report.
 */
export async function runOsmosis(input: OsmosisInputT, ctx?: { userId?: string; tier?: string; }): Promise<OsmosisOutputT> {
  const payload = OsmosisInput.parse(input);
  const tier = (ctx?.tier ?? "free") as any;
  const userId = ctx?.userId ?? "anon";

  // Quota / Tier checks (hourly)
  const quota = await checkQuota((globalThis as any).KV_QUOTA ?? (globalThis as any).LLM_CACHE, userId, tier);
  if (!quota.allowed) {
    await emit("run.blocked", { bot: "osmosis", reason: "quota", tier });
    throw Object.assign(new Error("Hourly quota exceeded"), { status: 429 });
  }

  // Attention over combined signals
  const tokens = extractTokens({
    task: payload.task,
    ghost: payload.ghost_profile || undefined,
    observations: payload.observations || undefined,
    signature: payload.software_signature || undefined,
  });
  const attn = buildAttention(tokens);

  // Golden Path quick try (budget tokens ~ derive from budget_hint_usd)
  const budgetTokens = Math.max(256, Math.min(2048, Math.floor((payload.constraints.budget_hint_usd / 0.000002) || 512)));
  const gpKey = { task_type: "osmosis", app: payload.software_signature?.name ?? "unknown", token_hash: String(tokens.slice(0,64).join("|").length) };
  const best = await gpSelect(gpKey, budgetTokens);
  if (best) {
    const out: OsmosisOutputT = {
      software_signature: payload.software_signature,
      inferred_plan: (best.inferred_plan as OsmosisStep[]) ?? [],
      confidence: Math.min(0.98, (best.confidence ?? 0.92)),
      attention_report: { features_ranked: attn.ranked.slice(0,32), entropy: attn.entropy },
      provenance: ["gp:hit"],
    };
    await emit("run.complete", { bot: "osmosis", tier, model: "gp", tokens_in: 0, tokens_out: 0, api_cost_usd: 0, latency_ms: 10, gp_hit: true, success: true });
    return OsmosisOutput.parse(out);
  }

  // Model choice via tier policy (mini default; turbo allowed only per policy)
  const policy = getTierPolicy(tier);
  const profile = policy.allowTurbo ? "turbo" : "mini";

  // Construct strict JSON instruction for inference (NOT copying code)
  const sys = [
    "You infer SOFTWARE BEHAVIOR at the intention/interaction level.",
    "You DO NOT copy program source code. You synthesize a repeatable plan of interactions and tool invocations.",
    "Output strict JSON exactly matching the provided schema.",
  ].join("\n");
  const user = [
    `TASK: ${payload.task}`,
    `SOFTWARE_SIGNATURE: ${JSON.stringify(payload.software_signature ?? {})}`,
    `ATTENTION_TOKENS_RANKED: ${JSON.stringify(attn.ranked.slice(0,32))}`,
    payload.ghost_profile ? `GHOST_PROFILE: ${JSON.stringify(payload.ghost_profile).slice(0,3500)}` : "",
    payload.observations ? `OBS: ${JSON.stringify(payload.observations).slice(0,3500)}` : "",
    `Return JSON: { "software_signature": {...}, "inferred_plan":[{intent,action,target?,params?,note?},...], "confidence": 0.xx, "attention_report":{"features_ranked":[[token,weight]...],"entropy":N} }`,
  ].join("\n");

  const t0 = Date.now();
  const raw = await callModel({
    profile,
    messages: [
      { role: "system", content: sys },
      { role: "user", content: user },
    ],
    json: true,
    maxTokens: 512,
  });
  const latency = Date.now() - t0;

  // Validate & normalize
  const out = OsmosisOutput.parse({
    software_signature: payload.software_signature,
    inferred_plan: raw.inferred_plan ?? raw?.plan ?? [],
    confidence: typeof raw.confidence === "number" ? raw.confidence : 0.75,
    attention_report: raw.attention_report ?? { features_ranked: attn.ranked.slice(0,32), entropy: attn.entropy },
    provenance: ["llm:proxy"],
  });

  // Record GP (budget-aware path)
  await gpRecord({
    task_type: "osmosis",
    key: gpKey,
    success: true,
    cost_tokens: (raw.tokens_out ?? 400),
    inferred_plan: out.inferred_plan,
    confidence: out.confidence,
  });

  await emit("run.complete", {
    bot: "osmosis",
    tier,
    model: profile,
    tokens_in: raw.tokens_in ?? 500,
    tokens_out: raw.tokens_out ?? 400,
    api_cost_usd: raw.cost_usd ?? 0.0018,
    latency_ms: latency,
    gp_hit: false,
    success: true,
  });

  return out;
}

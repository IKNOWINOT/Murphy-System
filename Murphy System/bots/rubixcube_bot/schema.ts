
import { z } from "zod";

export const AttachmentSchema = z.object({
  type: z.enum(["json","text"]),
  text: z.string().optional(),
  filename: z.string().optional(),
  url: z.string().url().optional()
});

export const ConstraintsSchema = z.object({
  safety: z.enum(["strict","normal","off"]).default("strict"),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional()
});

export const VoiceSchema = z.object({ stt: z.boolean().optional(), tts: z.boolean().optional() });

export const InputSchema = z.object({
  task: z.enum([
    "hydrate","fold","score_path","visualize","optimize_from_feedback","report","store",
    "stats","probability","ci","hypothesis","bayes_update","simulate","forecast","explain_prob"
  ]).default("report"),
  params: z.object({
    // hydration
    tensor_name: z.string().default("tensorA").optional(),
    seed: z.number().int().default(1337).optional(),
    shape: z.array(z.number().int()).default([64]).optional(),
    entropy_hint: z.number().default(0.0).optional(),
    depths: z.array(z.number().int()).optional(),
    hydration_cost: z.number().default(1.0).optional(),
    path_key: z.string().optional(),

    // stats/prob tasks
    data: z.array(z.number()).optional(),
    data2: z.array(z.number()).optional(),
    dist: z.object({
      name: z.enum(["normal","t","chisq","f","binom","poisson","exp","beta"]).default("normal"),
      params: z.array(z.number()).default([])
    }).optional(),
    x: z.number().optional(),
    tail: z.enum(["two","left","right"]).default("two").optional(),
    alpha: z.number().min(0).max(1).default(0.05).optional(),
    n: z.number().int().optional(),
    p: z.number().optional(),
    n2: z.number().int().optional(),
    p2: z.number().optional(),
    known_sigma: z.number().optional(),
    hypothesis: z.enum(["mean_eq","prop_eq","diff_means","diff_props","independence"]).default("mean_eq").optional(),
    table: z.array(z.array(z.number())).optional(),

    // bayes
    prior: z.object({ a: z.number().optional(), b: z.number().optional(), mu: z.number().optional(), tau: z.number().optional(), sigma2: z.number().optional() }).optional(),
    evidence: z.object({ success: z.number().int().optional(), trials: z.number().int().optional(), mean: z.number().optional(), n: z.number().int().optional() }).optional(),

    // simulate
    runs: z.number().int().default(10000).optional(),
    event: z.object({ op: z.enum(["gt","lt","ge","le"]).default("gt"), threshold: z.number().default(0) }).optional(),

    // forecast
    series: z.array(z.number()).optional(),

    // viz/store
    store: z.boolean().default(false).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.record(z.any()).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const ResultSchema = z.object({
  hydration: z.object({ tensor_name: z.string().optional(), seed: z.number().optional(), shape: z.array(z.number()).optional(), entropy_hint: z.number().optional() }).optional(),
  fold: z.object({ length: z.number().optional(), topk: z.array(z.tuple([z.number(), z.number()])).optional(), stats: z.record(z.number()).optional() }).optional(),
  confidence: z.object({ path_key: z.string().optional(), score: z.number().optional(), fidelity: z.record(z.number()).optional() }).optional(),
  viz: z.object({ type: z.enum(["bar","heatmap"]).optional(), data: z.array(z.record(z.any())).optional(), thumb_uri: z.string().optional() }).optional(),
  optimizations: z.array(z.object({ target_bot: z.string(), area: z.string(), proposal: z.string(), confidence: z.number().optional() })).optional(),
  ranked_paths: z.array(z.tuple([z.string(), z.number()])).optional(),
  stats: z.record(z.number()).optional(),
  corr: z.array(z.array(z.number())).optional(),
  prob: z.object({ value: z.number().optional(), kind: z.string().optional() }).optional(),
  ci: z.object({ low: z.number(), high: z.number() }).optional(),
  test: z.object({ statistic: z.number(), p: z.number(), df: z.number().optional(), reject: z.boolean() }).optional(),
  bayes: z.object({ posterior: z.record(z.number()), summary: z.record(z.number()).optional() }).optional(),
  simulate: z.object({ estimate: z.number(), stderr: z.number(), runs: z.number() }).optional(),
  forecast: z.object({ slope: z.number(), intercept: z.number(), r2: z.number(), next: z.number() }).optional(),
  explain: z.string().optional()
});

export const BudgetMetaSchema = z.object({
  tokens_in: z.number().int().nonnegative().optional(),
  tokens_out: z.number().int().nonnegative().optional(),
  cost_usd: z.number().nonnegative().optional(),
  tier: z.string().optional(),
  pool: z.enum(["free","paid","turbo","gp"]).optional()
});
export const GPMetaSchema = z.object({ hit: z.boolean().default(false), key: z.record(z.any()).optional(), spec_id: z.string().optional() });
export const StabilityMetaSchema = z.object({ S: z.number(), action: z.enum(["continue","fallback_gp","downgrade","halt"]), drift: z.object({ avg:z.number().optional(), cur:z.number().optional() }).optional() });
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.45), vallon: z.number().min(0).max(1).default(0.3), kiren: z.number().min(0).max(1).default(0.25) });

export const OutputSchema = z.object({
  result: ResultSchema.or(z.string()).or(z.array(z.any())),
  confidence: z.number().min(0).max(1),
  notes: z.array(z.string()).optional(),
  meta: z.object({
    budget: BudgetMetaSchema.optional(),
    gp: GPMetaSchema.optional(),
    stability: StabilityMetaSchema.optional(),
    kaiaMix: KaiaMixMetaSchema.optional()
  }),
  provenance: z.array(z.string()).optional()
}).strict();

export type Input = z.infer<typeof InputSchema>;
export type Output = z.infer<typeof OutputSchema>;

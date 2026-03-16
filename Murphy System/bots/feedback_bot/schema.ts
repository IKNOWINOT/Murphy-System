
import { z } from "zod";

export const AttachmentSchema = z.object({
  type: z.string(),
  url: z.string().url().optional(),
  text: z.string().optional(),
  filename: z.string().optional(),
});

export const ConstraintsSchema = z.object({
  safety: z.enum(["strict","normal","off"]).default("strict"),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional(),
});

export const VoiceSchema = z.object({ stt: z.boolean().optional(), tts: z.boolean().optional() });

export const FeedbackEventSchema = z.object({
  ts: z.string(),
  bot: z.string(),
  task_type: z.string().optional(),
  user_id_hash: z.string().optional(),
  value: z.number(),
  reinforcement: z.number().int().nonnegative().default(0),
  weight: z.number().positive().default(1),
  source: z.string().default("implicit"),
  meta: z.record(z.any()).optional()
});

export const InputSchema = z.object({
  task: z.enum(["ingest","analyze","score","propose_actions","ab_test"]),
  params: z.object({
    events: z.array(FeedbackEventSchema).optional(),
    window: z.object({ from: z.string().optional(), to: z.string().optional() }).optional(),
    half_life_days: z.number().positive().default(3),
    strategy: z.enum(["decay","adaptive","seasonal"]).default("decay"),
    bandit: z.object({
      arms: z.array(z.string()).optional(),
      metric: z.enum(["pass_rate","stability","cost"]).default("pass_rate")
    }).optional(),
    propose: z.object({ enabled: z.boolean().default(false) }).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const ScoreRowSchema = z.object({
  bot: z.string(),
  task_type: z.string().optional(),
  gp_id: z.string().optional(),
  score: z.number(),
  ci: z.tuple([z.number(), z.number()]).optional(),
  n: z.number().int().nonnegative()
});

export const ClusterSchema = z.object({
  key: z.object({ bot: z.string(), category: z.string() }),
  count: z.number().int().nonnegative(),
  gp_candidate: z.object({ task_type: z.string(), spec: z.record(z.any()) }).optional()
});

export const ActionSchema = z.object({
  type: z.enum(["prompt_patch","spec_patch","retry_policy","validator_rule"]),
  target_bot: z.string(),
  category: z.string().optional(),
  action_json: z.record(z.any()),
  confidence: z.number().min(0).max(1).default(0.5),
  gated: z.boolean().default(true)
});

export const ResultSchema = z.object({
  scores: z.array(ScoreRowSchema).default([]),
  recurring_clusters: z.array(ClusterSchema).default([]),
  actions: z.array(ActionSchema).default([]),
  ab_assignments: z.record(z.string()).default({})
});

export const BudgetMetaSchema = z.object({
  tokens_in: z.number().int().nonnegative().optional(),
  tokens_out: z.number().int().nonnegative().optional(),
  cost_usd: z.number().nonnegative().optional(),
  tier: z.string().optional(),
  pool: z.enum(["free","paid","turbo","gp"]).optional()
});
export const GPMetaSchema = z.object({ hit: z.boolean().default(false), key: z.record(z.any()).optional(), spec_id: z.string().optional() });
export const StabilityMetaSchema = z.object({ S: z.number(), action: z.enum(["continue","fallback_gp","downgrade","halt"]) });
export const KaiaMixMetaSchema = z.object({
  veritas: z.number().min(0).max(1).default(0.5),
  vallon: z.number().min(0).max(1).default(0.3),
  kiren: z.number().min(0).max(1).default(0.2)
});

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

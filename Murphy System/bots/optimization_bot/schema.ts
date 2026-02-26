
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

export const InputSchema = z.object({
  task: z.enum(["propose","start","assign","track","stop","promote","revert","policy_get","policy_set","eval_offline"]),
  params: z.object({
    target_bot: z.string().optional(),
    area: z.string().optional(),
    hypothesis: z.string().optional(),
    method: z.enum(["bandit","q_learning","bayes"]).default("bandit").optional(),
    // Arms for bandit-style experiments
    arms: z.array(z.object({
      arm_id: z.string(),
      spec: z.record(z.any())
    })).optional(),
    guardrails: z.object({
      canary_pct: z.number().min(0).max(1).default(0.05),
      max_error_delta: z.number().min(0).max(1).default(0.02),
      max_cost_usd: z.number().min(0).default(0.005)
    }).optional(),
    primary_metric: z.string().default("pass_rate").optional(),
    secondary_metrics: z.array(z.string()).optional(),
    context: z.record(z.any()).optional(),
    exp_id: z.string().optional(),
    arm_id: z.string().optional(),
    reward: z.number().optional(),
    metrics: z.record(z.any()).optional(),
    policy: z.record(z.any()).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const ResultSchema = z.object({
  exp_id: z.string().optional(),
  status: z.string().optional(),
  allocations: z.record(z.number()).optional(),
  assignment: z.object({ arm_id: z.string().optional() }).optional(),
  policy: z.record(z.any()).optional(),
  report: z.record(z.any()).optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.3), vallon: z.number().min(0).max(1).default(0.5), kiren: z.number().min(0).max(1).default(0.2) });

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

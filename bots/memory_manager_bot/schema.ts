
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
  task: z.enum([
    "add","update","merge","get","delete","search",
    "stm_store","stm_flush","prune","compress","stats",
    "export","import"
  ]),
  params: z.object({
    id: z.string().optional(),
    text: z.string().optional(),
    tenant: z.string().default("default").optional(),
    trust: z.number().min(0).max(1).default(1.0).optional(),
    top_k: z.number().int().positive().default(10).optional(),
    query: z.string().optional(),
    filters: z.record(z.any()).optional(),
    embedding: z.object({ enabled: z.boolean().default(true), profile: z.enum(["mini","turbo"]).default("mini") }).optional(),
    decay: z.object({ threshold: z.number().min(0).max(1).default(0.3) }).optional(),
    stm: z.object({ task_id: z.string(), ttl_s: z.number().int().positive().default(1800) }).optional(),
    export_path: z.string().optional(),
    import_path: z.string().optional(),
    allow_plaintext: z.boolean().default(false).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const MemHitSchema = z.object({
  id: z.string(),
  text: z.string(),
  score: z.number().optional(),
  trust: z.number().optional(),
  last_accessed: z.string().optional()
});

export const ResultSchema = z.object({
  memories: z.array(MemHitSchema).default([]),
  stats: z.record(z.any()).optional(),
  stm: z.object({ flushed: z.number().int().optional() }).optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.45), vallon: z.number().min(0).max(1).default(0.2), kiren: z.number().min(0).max(1).default(0.35) });

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

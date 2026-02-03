
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
  task: z.enum(["parse","convert","validate","normalize","diff","patch","stream"]),
  params: z.object({
    strict: z.boolean().default(false),
    input_format: z.enum(["auto","json","yaml","csv","xml","ini","text"]).default("auto"),
    output_format: z.enum(["json","yaml","csv","xml","ini","canonical_json","jcs","none"]).default("none"),
    schema_json: z.record(z.any()).optional(),
    key_policy: z.enum(["none","lowercase","uppercase","snake","kebab"]).default("none"),
    number_policy: z.enum(["as_is","stringify_nonfinite"]).default("as_is"),
    patch: z.object({
      type: z.enum(["json_patch","merge_patch"]),
      ops: z.array(z.record(z.any()))
    }).optional(),
    stream: z.object({ max_objects: z.number().int().positive().default(100000) }).optional(),
    privacy: z.object({ redact: z.boolean().default(true) }).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const IssueSchema = z.object({
  level: z.enum(["error","warn","info"]),
  path: z.string().optional(),
  message: z.string(),
  line: z.number().int().optional(),
  col: z.number().int().optional()
});

export const ResultSchema = z.object({
  data: z.any().optional(),
  issues: z.array(IssueSchema).default([]),
  diff: z.array(z.record(z.any())).optional(),
  size_bytes: z.number().int().optional(),
  objects_count: z.number().int().optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.6), vallon: z.number().min(0).max(1).default(0.25), kiren: z.number().min(0).max(1).default(0.15) });

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


import { z } from "zod";

export const AttachmentSchema = z.object({
  type: z.enum(["image","audio","video","text"]),
  url: z.string().url().optional(),
  text: z.string().optional(),          // for JSON payloads (e.g., arrays) or text content
  bytes_b64: z.string().optional(),     // raw bytes (base64) if provided
  metadata: z.record(z.any()).optional()
});

export const ConstraintsSchema = z.object({
  safety: z.enum(["strict","normal","off"]).default("strict"),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional(),
});

export const VoiceSchema = z.object({ stt: z.boolean().optional(), tts: z.boolean().optional() });

export const InputSchema = z.object({
  task: z.enum(["describe","features","caption","ocr","asr","keyframes","summarize","embed"]),
  params: z.object({
    verbosity: z.enum(["short","normal","verbose"]).default("normal").optional(),
    ocr: z.boolean().default(false).optional(),
    asr: z.boolean().default(false).optional(),
    keyframes: z.object({ max: z.number().int().positive().default(3) }).optional(),
    limits: z.object({ max_bytes: z.number().int().positive().default(8000000), max_ms: z.number().int().positive().default(60000) }).optional(),
    privacy: z.object({ redact: z.boolean().default(true) }).optional(),
    cache_ttl_s: z.number().int().positive().default(900).optional(),
    store: z.boolean().default(false).optional(),
    blend: z.object({ lexical: z.number().min(0).max(1).default(0.4), semantic: z.number().min(0).max(1).default(0.5), freshness: z.number().min(0).max(1).default(0.1) }).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).min(1).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const ResultSchema = z.object({
  descriptions: z.array(z.string()).default([]),
  features: z.object({
    image: z.record(z.any()).optional(),
    audio: z.record(z.any()).optional(),
    video: z.record(z.any()).optional(),
    text: z.record(z.any()).optional()
  }).default({}),
  ocr_text: z.string().optional(),
  asr_text: z.string().optional(),
  keyframes: z.array(z.object({ t: z.number(), thumb_uri: z.string().optional() })).optional(),
  artifacts: z.object({ r2_uris: z.array(z.string()).default([]) }).optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.35), vallon: z.number().min(0).max(1).default(0.2), kiren: z.number().min(0).max(1).default(0.45) });

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


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
  task: z.enum(["ingest","search","retrieve","sync","fetch_remote","rebuild_embeddings"]),
  params: z.object({
    // ingest
    doc: z.object({
      id: z.string(),
      title: z.string().default(""),
      text: z.string(),
      tags: z.array(z.string()).default([]),
      content_uri: z.string().optional(),
      meta: z.record(z.any()).optional()
    }).optional(),

    // search
    query: z.string().optional(),
    tags: z.array(z.string()).optional(),
    limit: z.number().int().positive().default(20).optional(),
    rerank: z.boolean().default(false).optional(),
    blend: z.object({ lexical: z.number().min(0).max(1).default(0.4), semantic: z.number().min(0).max(1).default(0.5), freshness: z.number().min(0).max(1).default(0.1) }).optional(),
    facets: z.boolean().default(false).optional(),

    // remote fetch (safe)
    safe_remote: z.boolean().default(false).optional(),
    remote: z.object({ url: z.string().url(), max_bytes: z.number().int().positive().default(200000), timeout_ms: z.number().int().positive().default(3000) }).optional(),

    // ANN options
    ann: z.object({ enable: z.boolean().default(false), projections: z.number().int().positive().default(64) }).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const DocHitSchema = z.object({
  id: z.string(),
  title: z.string().optional(),
  snippet: z.string().optional(),
  tags: z.array(z.string()).default([]),
  score: z.number().optional(),
  content_uri: z.string().optional()
});

export const FacetSchema = z.object({
  field: z.enum(["tags"]),
  buckets: z.array(z.object({ value: z.string(), count: z.number().int() }))
});

export const ResultSchema = z.object({
  docs: z.array(DocHitSchema).default([]),
  usage: z.object({ from_cache: z.boolean().default(false), objects: z.number().int().default(0) }).default({ from_cache:false, objects:0 }),
  facets: z.array(FacetSchema).optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.45), vallon: z.number().min(0).max(1).default(0.20), kiren: z.number().min(0).max(1).default(0.35) });

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


import { z } from "zod";

export const AttachmentSchema = z.object({
  type: z.enum(["text","code"]),
  url: z.string().url().optional(),
  text: z.string().optional(),
  filename: z.string().optional(),
  language: z.string().optional()    // for code
});

export const ConstraintsSchema = z.object({
  safety: z.enum(["strict","normal","off"]).default("strict"),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional()
});

export const VoiceSchema = z.object({ stt: z.boolean().optional(), tts: z.boolean().optional() });

export const InputSchema = z.object({
  task: z.enum(["clarify","translate","translate_batch","transpile","detect","explain","normalize","romanize","route","store_template"]).default("translate"),
  params: z.object({
    goal: z.string().default(""),
    source_lang: z.string().default("auto").optional(),
    target_lang: z.string().default("en").optional(),
    style: z.object({
      tone: z.enum(["neutral","formal","casual"]).default("neutral").optional(),
      domain: z.string().default("general").optional(),
      locale: z.string().default("en-US").optional()
    }).optional(),
    glossary: z.record(z.string()).default({}).optional(),
    no_translate: z.array(z.string()).default([]).optional(),
    preserve_formatting: z.boolean().default(true).optional(),
    batch: z.array(z.string()).optional(),
    transpile: z.object({ to: z.enum(["python","javascript"]).default("javascript") }).optional(),
    return_quality: z.boolean().default(true).optional(),
    return_explain: z.boolean().default(false).optional(),
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
  translations: z.array(z.object({
    original: z.string(),
    translated: z.string(),
    source_lang: z.string(),
    target_lang: z.string(),
    quality: z.number().min(0).max(1).optional(),
    notes: z.array(z.string()).optional()
  })).optional(),
  transpiled: z.object({ from: z.string().optional(), to: z.string().optional(), code: z.string().optional() }).optional(),
  detection: z.object({ language: z.string(), confidence: z.number().min(0).max(1) }).optional(),
  explanation: z.string().optional(),
  template: z.object({ style: z.any(), glossary: z.any(), no_translate: z.any() }).optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.5), vallon: z.number().min(0).max(1).default(0.15), kiren: z.number().min(0).max(1).default(0.35) });

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

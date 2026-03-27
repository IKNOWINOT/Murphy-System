// src/clockwork/bots/code_translator_bot/schema.ts
// Combined "Code Translator + Coding Bot" — PURE TypeScript, Bot-standards compliant.
// Supports translation, refactor, fix, explain, tests, and patch diffs.

import { z } from 'zod';

export const AttachmentSchema = z.object({
  type: z.string(),
  url: z.string().url().optional(),
  text: z.string().optional(),
  filename: z.string().optional(),
});

export const ConstraintsSchema = z.object({
  safety: z.enum(['strict','normal','off']).optional().default('normal'),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional(),
  style: z.string().optional(),            // e.g., "pep8", "google", "airbnb"
  testing: z.boolean().optional().default(true),
});

export const VoiceSchema = z.object({
  stt: z.boolean().optional().default(false),
  tts: z.boolean().optional().default(false),
});

export const InputSchema = z.object({
  task: z.string().min(1),                 // e.g., "translate to Go", "fix bug", "refactor", "explain & add tests"
  params: z.object({
    source_code: z.string().optional(),
    src_lang: z.string().optional(),
    target_lang: z.string().optional(),
    intent: z.enum(['translate','refactor','fix','explain','tests','format','document']).optional(),
    filename: z.string().optional(),
    entrypoint: z.string().optional(),
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional(),
}).strict();

// Output payload
export const PatchSchema = z.object({
  before: z.string().optional(),
  after: z.string(),
  diff: z.string().optional(),
  filename: z.string().optional(),
  language: z.string().optional(),
});

export const TestFileSchema = z.object({
  filename: z.string(),
  content: z.string(),
  framework: z.string().optional(),
});

export const ExplainSchema = z.object({
  summary: z.string(),
  key_points: z.array(z.string()).default([]),
  risks: z.array(z.string()).default([]),
});

export const ResultSchema = z.object({
  patches: z.array(PatchSchema).default([]),
  tests: z.array(TestFileSchema).default([]),
  explain: ExplainSchema.optional(),
});

export const BudgetMetaSchema = z.object({
  tokens_in: z.number().int().nonnegative().optional(),
  tokens_out: z.number().int().nonnegative().optional(),
  cost_usd: z.number().nonnegative().optional(),
  tier: z.string().optional(),
  pool: z.enum(['free','paid','turbo','gp']).optional(),
});

export const GPMetaSchema = z.object({
  hit: z.boolean().default(false),
  key: z.record(z.any()).optional(),
  spec_id: z.string().optional(),
});

export const StabilityMetaSchema = z.object({
  S: z.number(),
  action: z.enum(['continue','fallback_gp','downgrade','halt']),
  drift: z.object({ avg: z.number().optional(), cur: z.number().optional() }).optional(),
});

export const KaiaMixMetaSchema = z.object({
  veritas: z.number().min(0).max(1).default(0),
  vallon: z.number().min(0).max(1).default(0),
  kiren: z.number().min(0).max(1).default(0),
  veritas_vallon: z.number().optional(),
  kiren_veritas: z.number().optional(),
  vallon_kiren: z.number().optional(),
});

export const MetaSchema = z.object({
  budget: BudgetMetaSchema.optional(),
  gp: GPMetaSchema.optional(),
  stability: StabilityMetaSchema.optional(),
  kaiaMix: KaiaMixMetaSchema.optional(),
});

export const OutputSchema = z.object({
  result: ResultSchema.or(z.string()).or(z.array(z.any())),
  confidence: z.number().min(0).max(1),
  notes: z.array(z.string()).optional(),
  meta: MetaSchema,
  provenance: z.array(z.string()).optional(),
}).strict();

export type Input = z.infer<typeof InputSchema>;
export type Output = z.infer<typeof OutputSchema>;
export type Patch = z.infer<typeof PatchSchema>;

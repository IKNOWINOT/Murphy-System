// src/clockwork/bots/clarifier_bot/schema.ts
// Clarifier Bot — PURE TypeScript, Bot-standards compliant.
// Normalized output captures questions, assumptions, missing fields, and next steps.

import { z } from 'zod';

export const AttachmentSchema = z.object({
  type: z.string(),
  url: z.string().url().optional(),
  text: z.string().optional(),
});

export const ConstraintsSchema = z.object({
  safety: z.enum(['strict','normal','off']).optional().default('normal'),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional(),
});

export const VoiceSchema = z.object({
  stt: z.boolean().optional().default(false),
  tts: z.boolean().optional().default(false),
});

export const InputSchema = z.object({
  task: z.string().min(1),                   // brief or intent to clarify
  params: z.record(z.any()).optional(),      // optional context/spec
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),  // telemetry/context
  software_signature: z.record(z.any()).optional(),
}).strict();

// Clarifier questions & plan
export const ClarifyQuestionSchema = z.object({
  id: z.string(),
  field: z.string().min(1),                  // which parameter the question informs
  text: z.string().min(1),                   // human-friendly clarifying question
  short: z.string().optional(),              // terse version (UI prompts)
  expected_format: z.string().optional(),    // e.g., "YYYY-MM-DD", "number (mm)"
  example: z.string().optional(),
  options: z.array(z.union([z.string(), z.number()])).optional(),
  default: z.union([z.string(), z.number(), z.boolean()]).optional(),
  blocking: z.boolean().default(false),
  rationale: z.string().optional(),
  when: z.string().optional(),               // condition/expression for when to ask
});

export const ClarifyOutputSchema = z.object({
  questions: z.array(ClarifyQuestionSchema).default([]),
  assumptions: z.array(z.object({
    key: z.string(),
    value: z.union([z.string(), z.number(), z.boolean()]),
    confidence: z.number().min(0).max(1).default(0.5),
    rationale: z.string().optional(),
  })).default([]),
  missing_fields: z.array(z.string()).default([]),
  priority: z.enum(['low','medium','high']).default('medium'),
  next_steps: z.array(z.object({
    id: z.string(),
    title: z.string(),
    requires: z.array(z.string()).optional(),
    est_time_min: z.number().optional(),
  })).default([]),
  field_schema: z.array(z.object({
    field: z.string(),                        // recommended field key
    type: z.string().optional(),
    required: z.boolean().default(false),
    hint: z.string().optional(),
  })).default([])
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

export const TaskItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  requires: z.array(z.string()).optional(),
  est_time_min: z.number().optional(),
  details: z.record(z.any()).optional(),
});

export const OutputSchema = z.object({
  result: z.object({
    clarification: ClarifyOutputSchema,      // primary product
    chain_id: z.string().optional(),
    level: z.number().int().min(1).max(5).optional(),
    tasks: z.array(TaskItemSchema).optional(),
  }).or(z.string()).or(z.array(z.any())),
  confidence: z.number().min(0).max(1),
  notes: z.array(z.string()).optional(),
  meta: MetaSchema,
  provenance: z.array(z.string()).optional(),
}).strict();

export type Input = z.infer<typeof InputSchema>;
export type Output = z.infer<typeof OutputSchema>;
export type ClarifyOutput = z.infer<typeof ClarifyOutputSchema>;

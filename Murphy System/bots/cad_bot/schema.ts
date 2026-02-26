// src/clockwork/bots/cad_bot/schema.ts
// Ported to mirror Python `cad_bot.py` (entities + units) while adhering to the Bot standards.

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
  task: z.string().min(1),                   // human spec or goal
  params: z.record(z.any()).optional(),      // optional: { units?: 'mm'|'m'|'in', entities_hint?: ... }
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional(),
}).strict();

// === CAD spec (mirrors Python SCHEMA in repo: {entities:[], units}) ===
export const CADEntitySchema = z.object({
  type: z.string(),                           // e.g., 'box' | 'cylinder' | 'extrude' | 'union' | 'difference'
  params: z.record(z.any()).default({}),      // free-form param bag, validated by downstream CAD pipeline
});

export const CADSpecSchema = z.object({
  entities: z.array(CADEntitySchema),
  units: z.string().min(1),                   // 'mm' | 'm' | 'in' | etc.
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

// Result: include CAD spec + optional microtasks (for automation)
export const OutputSchema = z.object({
  result: z.object({
    cad_spec: CADSpecSchema,                  // primary product (port of Python output)
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
export type CADSpec = z.infer<typeof CADSpecSchema>;

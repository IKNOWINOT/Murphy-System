// src/clockwork/bots/optimizer_core_bot/schema.ts
// Port-and-improve template for an Optimizer Core bot (based on a typical Python optimizer_core).
// The bot accepts either an "original" Python-style spec or an improved "core" spec and normalizes it.

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
  task: z.string().min(1),                   // human objective or brief
  params: z.record(z.any()).optional(),      // optional: embeds spec or hints
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional(),
}).strict();

// ===== Original Python-style spec (guess-compatible): variables, constraints, objective, algorithm, budget =====
export const OriginalVarSchema = z.object({
  name: z.string(),
  type: z.enum(['int','float','categorical']).default('float'),
  min: z.number().optional(),
  max: z.number().optional(),
  choices: z.array(z.union([z.string(), z.number()])).optional(),
  default: z.union([z.number(), z.string()]).optional(),
});

export const OriginalConstraintSchema = z.object({
  type: z.enum(['linear','nonlinear']).default('linear'),
  expr: z.string().optional(), // e.g., "x + 2*y <= 10"
  lhs: z.array(z.string()).optional(),
  rhs: z.number().optional(),
});

export const OriginalSpecSchema = z.object({
  objective: z.string().min(1),              // e.g., "minimize loss"
  variables: z.array(OriginalVarSchema).min(1),
  constraints: z.array(OriginalConstraintSchema).optional().default([]),
  metric: z.string().optional().default('loss'),
  direction: z.enum(['minimize','maximize']).optional().default('minimize'),
  algorithm: z.string().optional(),          // grid, random, bayes, tpe...
  budget_evals: z.number().int().positive().optional().default(50),
});

// ===== Improved core spec =====
export const CoreVarSchema = z.object({
  name: z.string(),
  kind: z.enum(['int','float','categorical']).default('float'),
  domain: z.union([
    z.object({ min: z.number(), max: z.number() }),             // continuous/interval
    z.object({ choices: z.array(z.union([z.number(), z.string()])).min(1) }) // categorical
  ]),
  init: z.union([z.number(), z.string()]).optional(),
});

export const StopSchema = z.object({
  max_evals: z.number().int().positive().default(50),
  time_s: z.number().positive().optional(),
  target: z.number().optional(), // stop when metric reaches this
});

export const InitSchema = z.object({
  seed: z.number().int().optional(),
  n_sobol: z.number().int().optional(),
  n_random: z.number().int().optional(),
});

export const CoreSpecSchema = z.object({
  objective: z.string().min(1),
  direction: z.enum(['minimize','maximize']).default('minimize'),
  metric: z.string().default('loss'),
  variables: z.array(CoreVarSchema).min(1),
  constraints: z.array(z.string()).optional().default([]), // normalized as expressions
  algorithm: z.enum(['grid','random','bayes','tpe','cmaes','nevergrad']).default('bayes'),
  init: InitSchema.optional(),
  stop: StopSchema.default({ max_evals: 50 } as any),
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

export const OptimizationPlanSchema = z.object({
  core_spec: CoreSpecSchema,                   // normalized spec used by the optimizer
  initial_points: z.array(z.record(z.any())).optional(), // seeds
  best_guess: z.record(z.any()).optional(),    // current recommended params
  notes: z.array(z.string()).optional(),
});

export const OutputSchema = z.object({
  result: z.object({
    optimization: OptimizationPlanSchema,
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
export type CoreSpec = z.infer<typeof CoreSpecSchema>;
export type OriginalSpec = z.infer<typeof OriginalSpecSchema>;

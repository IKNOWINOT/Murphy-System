import { z } from 'zod';

export const AttachmentSchema = z.object({
  type: z.string(),
  url: z.string().url().optional(),
  text: z.string().optional(),
  id: z.union([z.string(), z.number()]).optional(),
});

export const InputSchema = z.object({
  task: z.string().min(1),
  params: z.object({
    ids: z.array(z.union([z.string(), z.number()])).optional(),
    texts: z.record(z.union([z.string(), z.null()])).optional(),
    threshold: z.number().min(0).max(1).optional().default(0.92),
    max_pairs: z.number().int().positive().optional().default(5000),
    strategy: z.enum(['pairwise','block','block+ann']).optional().default('block')
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
}).strict();

export const PairScoreSchema = z.object({
  id1: z.union([z.string(), z.number()]),
  id2: z.union([z.string(), z.number()]),
  score: z.number(),
});

export const MergeActionSchema = z.object({
  keep: z.union([z.string(), z.number()]),
  drop: z.union([z.string(), z.number()]),
  strategy: z.enum(['append','prefer_longer','prefer_recent']).default('append'),
  score: z.number(),
});

export const ClusterSchema = z.object({
  canonical_id: z.union([z.string(), z.number()]),
  members: z.array(z.union([z.string(), z.number()])),
  scores: z.array(PairScoreSchema).default([]),
});

export const ResultSchema = z.object({
  clusters: z.array(ClusterSchema).default([]),
  merges: z.array(MergeActionSchema).default([]),
  mapping: z.record(z.union([z.string(), z.number()])).default({})
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
});

export const KaiaMixMetaSchema = z.object({
  veritas: z.number().min(0).max(1).default(0.55),
  vallon: z.number().min(0).max(1).default(0.10),
  kiren: z.number().min(0).max(1).default(0.35),
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
}).strict();

export type Input = z.infer<typeof InputSchema>;
export type Output = z.infer<typeof OutputSchema>;

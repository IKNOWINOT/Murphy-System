
import { z } from 'zod';

export const AttachmentSchema = z.object({ type: z.string(), url: z.string().url().optional(), text: z.string().optional(), filename: z.string().optional() });

export const ConstraintsSchema = z.object({ safety: z.enum(['strict','normal','off']).optional().default('strict'), budget_hint_usd: z.number().optional(), time_s: z.number().optional() });

export const VoiceSchema = z.object({ stt: z.boolean().optional().default(false), tts: z.boolean().optional().default(false) });

export const InputSchema = z.object({
  task: z.string().min(1),
  params: z.object({
    mode: z.enum(['calc','conversion','sizing','design_check','dfma','tolerance','optimization','simulation','domain']).optional().default('calc'),
    domain: z.string().optional(),        // 'structural','electrical','aero','fluids','thermo','chemical','mechanical','printing','rocket','mfg'
    spec: z.record(z.any()).optional(),
    units: z.record(z.string()).optional(),
    monte_carlo: z.object({ runs: z.number().int().min(1).max(1000).default(5), sigma: z.number().min(0).max(0.5).default(0.02) }).optional(),
    optimize: z.object({ objective: z.string().optional(), vars: z.record(z.object({ min: z.number(), max: z.number() })).optional(), max_iters: z.number().int().default(50) }).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional(),
}).strict();

export const StepSchema = z.object({ name: z.string(), details: z.string().optional(), vars: z.record(z.any()).optional() });

export const ChecksSchema = z.object({
  pass: z.boolean(),
  warnings: z.array(z.string()).default([]),
  errors: z.array(z.string()).default([]),
  codes: z.array(z.object({ ref: z.string(), ok: z.boolean(), severity: z.enum(['info','warn','critical']).default('info'), note: z.string().optional(), edition: z.string().optional(), section: z.string().optional() })).default([])
});

export const ResultSchema = z.object({ summary: z.string(), outputs: z.record(z.any()).default({}), steps: z.array(StepSchema).default([]), checks: ChecksSchema, artifacts: z.array(z.object({ name: z.string(), data: z.any() })).default([]) });

export const BudgetMetaSchema = z.object({ tokens_in: z.number().int().nonnegative().optional(), tokens_out: z.number().int().nonnegative().optional(), cost_usd: z.number().nonnegative().optional(), tier: z.string().optional(), pool: z.enum(['free','paid','turbo','gp']).optional() });

export const GPMetaSchema = z.object({ hit: z.boolean().default(false), key: z.record(z.any()).optional(), spec_id: z.string().optional() });

export const StabilityMetaSchema = z.object({ S: z.number(), action: z.enum(['continue','fallback_gp','downgrade','halt']), drift: z.object({ avg: z.number().optional(), cur: z.number().optional() }).optional() });

export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.4), vallon: z.number().min(0).max(1).default(0.2), kiren: z.number().min(0).max(1).default(0.4) });

export const MetaSchema = z.object({ budget: BudgetMetaSchema.optional(), gp: GPMetaSchema.optional(), stability: StabilityMetaSchema.optional(), kaiaMix: KaiaMixMetaSchema.optional() });

export const OutputSchema = z.object({ result: ResultSchema.or(z.string()).or(z.array(z.any())), confidence: z.number().min(0).max(1), notes: z.array(z.string()).optional(), meta: MetaSchema, provenance: z.array(z.string()).optional() }).strict();

export type Input = z.infer<typeof InputSchema>;
export type Output = z.infer<typeof OutputSchema>;

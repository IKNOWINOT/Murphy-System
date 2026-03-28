// src/clockwork/bots/commissioning_bot/schema.ts
import { z } from 'zod';

export const AttachmentSchema = z.object({
  type: z.string(),
  url: z.string().url().optional(),
  text: z.string().optional(),
  filename: z.string().optional(),
});

export const ConstraintsSchema = z.object({
  safety: z.enum(['strict','normal','off']).optional().default('strict'),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional(),
  window: z.object({ start: z.string().optional(), end: z.string().optional(), tz: z.string().optional() }).optional(),
});

export const VoiceSchema = z.object({
  stt: z.boolean().optional().default(false),
  tts: z.boolean().optional().default(false),
});

export const InputSchema = z.object({
  task: z.string().min(1),
  params: z.object({
    site: z.string().optional(),
    system: z.string().optional(),
    assets_hint: z.array(z.string()).optional(),
    standard: z.string().optional(),
    priority: z.enum(['P1','P2','P3']).optional(),
    desired_units: z.record(z.string()).optional() // e.g., { '°F':'°C', 'gpm':'L/s' }
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional(),
}).strict();

export const AssetSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  tag: z.string().optional(),
  location: z.string().optional(),
  meta: z.record(z.any()).optional(),
});

export const PointSchema = z.object({
  name: z.string(),
  point_type: z.string(),
  unit: z.string().optional(),
  source: z.enum(['BAS','logger','calc','manual']).default('BAS'),
  asset_id: z.string().optional(),
  range: z.object({ min: z.number().optional(), max: z.number().optional() }).optional(),
});

export const AcceptanceSchema = z.object({
  criteria: z.array(z.object({ metric: z.string(), op: z.enum(['<=','>=','=','<>','between']).default('between'), target: z.union([z.number(), z.array(z.number())]) , unit: z.string().optional() })).default([]),
  sampling: z.object({ duration_s: z.number().default(300), interval_s: z.number().default(5) }).default({ duration_s: 300, interval_s: 5 } as any),
  notes: z.string().optional(),
});

export const StepSchema = z.object({
  id: z.string(),
  action: z.string(),
  expected_effect: z.string().optional(),
  watch_points: z.array(z.string()).default([]),
  hold_s: z.number().optional(),
  safety: z.array(z.string()).default([]),
  requires: z.array(z.string()).optional(),
});

export const TestProcedureSchema = z.object({
  id: z.string(),
  title: z.string(),
  preconditions: z.array(z.string()).default([]),
  steps: z.array(StepSchema).default([]),
  acceptance: AcceptanceSchema,
  data_capture: z.object({ points: z.array(z.string()).default([]), duration_s: z.number().default(300), interval_s: z.number().default(5) }).default({ points:[], duration_s:300, interval_s:5 } as any),
  risks: z.array(z.string()).default([]),
  references: z.array(z.string()).default([]),
  automation: z.object({ can_auto: z.boolean().default(false), mode: z.enum(['manual','semi-auto','auto']).default('manual') }).optional(),
});

export const RiskRegisterSchema = z.object({
  items: z.array(z.object({ id: z.string(), description: z.string(), severity: z.enum(['low','medium','high']).default('medium'), mitigation: z.string().optional() })).default([])
});

export const DeliverableSchema = z.object({
  name: z.string(),
  type: z.enum(['FPT','TrendReport','PunchList','IssueLog','Checklist','Calibration']).default('FPT'),
  link: z.string().optional(),
});

export const CommissioningPlanSchema = z.object({
  site: z.string().optional(),
  system: z.string().optional(),
  assets: z.array(AssetSchema).default([]),
  points: z.array(PointSchema).default([]),
  procedures: z.array(TestProcedureSchema).default([]),
  risk_register: RiskRegisterSchema.default({ items: [] } as any),
  deliverables: z.array(DeliverableSchema).default([]),
  schedule: z.object({ window: z.object({ start: z.string().optional(), end: z.string().optional(), tz: z.string().optional() }).optional(), dependencies: z.array(z.string()).default([]) }).default({} as any),
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
  // new: attached form templates (JSON) for convenience (optional)
  forms: z.array(z.object({ filename: z.string(), content: z.record(z.any()) })).optional()
});

export const OutputSchema = z.object({
  result: z.object({
    plan: CommissioningPlanSchema,
    chain_id: z.string().optional(),
    level: z.number().int().min(1).max(5).optional(),
    tasks: z.array(z.object({ id: z.string(), title: z.string(), requires: z.array(z.string()).optional(), est_time_min: z.number().optional() })).optional(),
  }).or(z.string()).or(z.array(z.any())),
  confidence: z.number().min(0).max(1),
  notes: z.array(z.string()).optional(),
  meta: MetaSchema,
  provenance: z.array(z.string()).optional(),
}).strict();

export type CommissioningPlan = z.infer<typeof CommissioningPlanSchema>;
export type Input = z.infer<typeof InputSchema>;
export type Output = z.infer<typeof OutputSchema>;

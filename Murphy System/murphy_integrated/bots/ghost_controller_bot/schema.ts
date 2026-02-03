
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
});

export const VoiceSchema = z.object({
  stt: z.boolean().optional().default(false),
  tts: z.boolean().optional().default(false),
});

export const DesktopEventSchema = z.object({
  ts: z.string(),
  kind: z.enum(['key','mouse','focus','idle','app']),
  data: z.record(z.any()).default({})
});

export const ScriptStepSchema = z.object({
  id: z.string(),
  action: z.string(),
  args: z.record(z.any()).default({}),
  guard: z.string().optional(),
});

export const AutomationSpecSchema = z.object({
  title: z.string(),
  steps: z.array(ScriptStepSchema).default([]),
  triggers: z.array(z.string()).default([]),
  replay_notes: z.array(z.string()).default([]),
});

export const MicroTaskSchema = z.object({
  id: z.string(),
  goal: z.string(),
  preconditions: z.array(z.string()).default([]),
  steps: z.array(ScriptStepSchema).default([]),
  success: z.object({
    type: z.enum(['window','text','pixel','noop']).default('noop'),
    selector: z.string().optional(),
    image: z.string().optional(),
    region: z.array(z.number()).optional(),
    timeout_s: z.number().default(10),
  }).default({ type:'noop', timeout_s:10 }),
});

export const ValidationResultSchema = z.object({
  microtask_id: z.string(),
  passed: z.boolean(),
  details: z.string().optional(),
});

export const AttentionMetricsSchema = z.object({
  idle_events: z.number().default(0),
  avg_idle_s: z.number().default(0),
  context_switches: z.number().default(0),
  top_apps: z.array(z.object({ app: z.string(), seconds: z.number() })).default([]),
  keystroke_rate_hz: z.number().default(0),
});

export const KaiaQSchema = z.object({
  id: z.string(),
  capture_ref: z.string(),
  axis: z.enum(['who','what','when','where','how','why']),
  prompt: z.string(),
  options: z.array(z.string()).default([]),
  allow_multi: z.boolean().default(true),
});

export const KaiaMsgSchema = z.object({
  ts: z.string(),
  questions: z.array(KaiaQSchema),
  notes: z.array(z.string()).default([]),
});

export const ProbabilityChainSchema = z.object({
  nodes: z.array(z.object({ id: z.string(), p: z.number() })).default([]),
  edges: z.array(z.object({ from: z.string(), to: z.string(), weight: z.number() })).default([]),
});

export const InputSchema = z.object({
  task: z.string().min(1), // observe|record|synthesize_automation|playback|export|post_gp
  params: z.object({
    description: z.string().optional(),
    adhd: z.object({ idle_warn_s: z.number().default(30), context_switch_warn: z.number().default(6) }).optional(),
    bridge: z.object({ token: z.string().optional(), endpoint: z.string().optional() }).optional(),
    allow_apps: z.array(z.string()).optional(),
    gp_key: z.record(z.any()).optional(),
    gp_post_endpoint: z.string().optional(),
    google_docs: z.object({ enabled: z.boolean().default(false), doc_id: z.string().optional() }).optional(),
    privacy: z.object({ redact: z.boolean().default(true) }).optional(),
    kaia: z.object({ end_of_day: z.boolean().default(false), answers: z.array(z.object({ id:z.string(), value:z.any(), reasons: z.array(z.string()).default([]) })).optional() }).optional(),
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: ConstraintsSchema.optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional(),
}).strict();

export const ResultSchema = z.object({
  task_summary: z.string(),
  automation_spec: AutomationSpecSchema,
  microtasks: z.array(MicroTaskSchema).default([]),
  validation: z.array(ValidationResultSchema).default([]),
  live_reports: z.array(z.object({ microtask_id:z.string(), passed:z.boolean(), details:z.string().optional(), ts:z.string().optional() })).default([]),
  attention: AttentionMetricsSchema,
  kaia: z.object({
    message: KaiaMsgSchema.optional(),
    suggestions: z.array(z.string()).default([]),
    probability_chain: ProbabilityChainSchema.optional(),
  }).default({} as any),
  confidence: z.number().min(0).max(1).default(0.85),
  integrations: z.object({
    osmosis_pack: z.string().optional(),
    goldenpath_key: z.record(z.any()).optional(),
    ingestion_payload: z.record(z.any()).optional(),
    relay_hint: z.object({ endpoint: z.string(), token: z.string() }).optional(),
    goldenpath_submit: z.record(z.any()).optional(),
    gp_post_status: z.string().optional(),
  }).default({}),
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
  veritas: z.number().min(0).max(1).default(0.35),
  vallon: z.number().min(0).max(1).default(0.45),
  kiren: z.number().min(0).max(1).default(0.20),
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

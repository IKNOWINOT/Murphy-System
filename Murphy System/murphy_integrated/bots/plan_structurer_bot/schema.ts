
import { z } from "zod";

export const AttachmentSchema = z.object({
  type: z.string(),                         // 'text' for notes; others ignored
  url: z.string().url().optional(),
  text: z.string().optional(),
  filename: z.string().optional()
});

export const ConstraintsSchema = z.object({
  safety: z.enum(["strict","normal","off"]).default("strict"),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional()
});

export const VoiceSchema = z.object({ stt: z.boolean().optional(), tts: z.boolean().optional() });

export const InputSchema = z.object({
  task: z.enum(["clarify","template","structure","build","prompt","store"]).default("build"),
  params: z.object({
    goal: z.string().default(""),
    domain: z.enum(["product","engineering","ops","research","marketing","design"]).default("engineering").optional(),
    verbosity: z.enum(["short","normal","verbose"]).default("normal").optional(),
    risk_tolerance: z.enum(["low","normal","high"]).default("normal").optional(),
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

export const QuestionSchema = z.object({ axis: z.enum(["who","what","when","where","how","why"]), prompt: z.string(), options: z.array(z.string()).default([]) });

export const TemplateSchema = z.object({
  purpose: z.string(),
  personas: z.array(z.string()).default([]),
  scenarios: z.array(z.string()).default([]),
  requirements: z.array(z.string()).default([]),
  architecture: z.array(z.string()).default([]),
  acceptance: z.array(z.string()).default([]),
  risks: z.array(z.string()).default([]),
  timeline: z.array(z.string()).default([]),
  milestones: z.array(z.string()).default([]),
  budget: z.array(z.string()).default([]),
  success_metrics: z.array(z.string()).default([])
});

export const PlanNodeSchema = z.object({
  id: z.string(),
  title: z.string(),
  level: z.enum(["epic","capability","story","task","subtask"]),
  rationale: z.string().optional(),
  preconditions: z.array(z.string()).default([]),
  deliverables: z.array(z.string()).default([]),
  dependencies: z.array(z.string()).default([]),
  required_inputs: z.array(z.string()).default([]),
  acceptance_tests: z.array(z.string()).default([]),
  risk: z.object({ level: z.enum(["low","medium","high"]).default("low"), notes: z.string().optional() }).optional(),
  effort: z.object({ tshirt: z.enum(["XS","S","M","L","XL"]).default("M") }).optional(),
  children: z.array(z.any()).default([])
});

export const PlanSchema = z.object({
  tree: z.array(PlanNodeSchema).default([]),
  dependencies: z.array(z.tuple([z.string(), z.string()])).default([]),
  acceptance_tests: z.array(z.object({ id: z.string(), text: z.string() })).default([])
});

export const PromptSchema = z.object({
  short: z.string(),
  long: z.string()
});

export const ResultSchema = z.object({
  questions: z.array(QuestionSchema).optional(),
  answers: z.array(z.object({ id: z.string(), value: z.any() })).optional(),
  template: TemplateSchema.optional(),
  plan: PlanSchema.optional(),
  prompt: PromptSchema.optional(),
  explain: z.string().optional()
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
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.35), vallon: z.number().min(0).max(1).default(0.2), kiren: z.number().min(0).max(1).default(0.45) });

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


import { z } from "zod";

export const AttachmentSchema = z.object({
  type: z.string(),
  url: z.string().url().optional(),
  text: z.string().optional(),
  filename: z.string().optional(),
});

export const ConstraintsSchema = z.object({
  safety: z.enum(["strict","normal","off"]).default("strict"),
  budget_hint_usd: z.number().optional(),
  time_s: z.number().optional(),
});

export const VoiceSchema = z.object({ stt: z.boolean().optional(), tts: z.boolean().optional() });

export const InputSchema = z.object({
  task: z.enum([
    "register_key","allocate_key","get_key","mint_ephemeral","use_key",
    "revoke_key","quarantine_key","rotate_key","sign_request",
    "policy_set","policy_get","audit_report"
  ]),
  params: z.object({
    bot_name: z.string().optional(),
    scope: z.string().optional(),
    key_id: z.string().optional(),
    key_value: z.string().optional(),   // plaintext only on register; never logged
    ttl_s: z.number().int().positive().default(300).optional(),
    policy: z.object({
      max_calls: z.number().int().positive().default(100),
      window_s: z.number().int().positive().default(60),
      burst: z.number().int().positive().default(20),
      tier: z.string().optional()
    }).optional(),
    request: z.object({
      method: z.string().optional(),
      url: z.string().optional(),
      headers: z.record(z.string()).optional(),
      body: z.string().optional()
    }).optional(),
    // security flags
    allow_plaintext_get: z.boolean().default(false).optional()
  }).optional(),
  attachments: z.array(AttachmentSchema).optional(),
  constraints: z.object({
    safety: z.enum(["strict","normal","off"]).default("strict"),
    budget_hint_usd: z.number().optional(),
    time_s: z.number().optional()
  }).optional(),
  voice: VoiceSchema.optional(),
  ghost_profile: z.record(z.any()).optional(),
  observations: z.array(z.record(z.any())).optional(),
  software_signature: z.record(z.any()).optional()
}).strict();

export const ResultSchema = z.object({
  status: z.string().default("ok"),
  artifact: z.record(z.any()).optional(), // e.g., { ephemeral_token, expires_ts } or { sealed_key }
  signature: z.object({ alg: z.string(), headers: z.record(z.string()) }).optional(),
  policy: z.object({ max_calls: z.number(), window_s: z.number(), burst: z.number(), tier: z.string().optional() }).optional(),
  report: z.record(z.any()).optional()
});

export const BudgetMetaSchema = z.object({
  tokens_in: z.number().int().nonnegative().optional(),
  tokens_out: z.number().int().nonnegative().optional(),
  cost_usd: z.number().nonnegative().optional(),
  tier: z.string().optional(),
  pool: z.enum(["free","paid","turbo","gp"]).optional()
});
export const GPMetaSchema = z.object({ hit: z.boolean().default(false), key: z.record(z.any()).optional(), spec_id: z.string().optional() });
export const StabilityMetaSchema = z.object({ S: z.number(), action: z.enum(["continue","fallback_gp","downgrade","halt"]) });
export const KaiaMixMetaSchema = z.object({ veritas: z.number().min(0).max(1).default(0.35), vallon: z.number().min(0).max(1).default(0.5), kiren: z.number().min(0).max(1).default(0.15) });

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

import { z } from "zod";

/**
 * OsmosisInput:
 * - Works standalone OR consumes Ghost's task profile/telemetry.
 * - `software_signature`: sparse fingerprint of the app/workflow (names, menus, UI tokens).
 * - `observations`: normalized interaction stream (from Ghost or logs).
 * - `constraints`: safe modes, SLAs, budget hints.
 */
export const Observation = z.object({
  ts: z.number().optional(),                    // epoch ms (optional)
  kind: z.enum(["key","mouse","window","ui","log","net"]).optional(),
  value: z.any(),                                // normalized token/value
});

export const SoftwareSignature = z.object({
  name: z.string().optional(),                   // e.g., "Figma", "Notion", "SAP"
  version: z.union([z.string(), z.number()]).optional(),
  os: z.enum(["win","mac","linux","web"]).optional(),
  hints: z.array(z.string()).optional(),         // e.g., menu labels, hotkeys, common flows
  features: z.array(z.string()).optional(),      // declarative feature tokens (if known)
});

export const GhostProfile = z.object({
  task_description: z.string().optional(),
  keystrokes: z.array(z.tuple([z.string(), z.string()])).optional(), // [isoTime, key]
  mouse_path: z.array(z.tuple([z.string(), z.number(), z.number()])).optional(), // [isoTime, x, y]
  active_window: z.string().optional(),
}).optional();

export const OsmosisInput = z.object({
  task: z.string().min(1, "task is required"),
  software_signature: SoftwareSignature.optional(),
  observations: z.array(Observation).optional(),
  ghost_profile: GhostProfile,                   // if present, we will ingest it
  constraints: z.object({
    safety: z.enum(["strict","normal","off"]).default("strict"),
    budget_hint_usd: z.number().min(0).default(0.002),
    time_s: z.number().min(1).max(60).default(10),
  }).default({ safety: "strict", budget_hint_usd: 0.002, time_s: 10 }),
});

export type OsmosisInputT = z.infer<typeof OsmosisInput>;

/**
 * OsmosisOutput:
 * - A reproducible plan that INFERS behavior (no code copy).
 * - Each step is tool/gesture/intent level; UI selectors are descriptive, not raw code.
 */
export const OsmosisStep = z.object({
  intent: z.string(),                            // "Open project palette", "Insert shape", etc.
  action: z.enum(["ui.click","ui.type","ui.hotkey","nav.open","wait","assert","tool.invoke"]),
  target: z.string().optional(),                 // human-readable locator ("Menu→File→New")
  params: z.record(z.any()).optional(),          // keys, delays, etc.
  note: z.string().optional(),
});

export const OsmosisOutput = z.object({
  software_signature: SoftwareSignature.optional(),
  inferred_plan: z.array(OsmosisStep).nonempty(),
  confidence: z.number().min(0).max(1),
  attention_report: z.object({
    features_ranked: z.array(z.tuple([z.string(), z.number()])), // token, weight
    entropy: z.number(),
  }),
  provenance: z.array(z.string()).optional(),    // e.g., "ghost:profile:hash", "obs:hash"
});

export type OsmosisOutputT = z.infer<typeof OsmosisOutput>;

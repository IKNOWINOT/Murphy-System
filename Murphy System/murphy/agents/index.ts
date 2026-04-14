// Copyright © 2020 Inoni Limited Liability Company
// Creator: Corey Post
// License: BSL 1.1
/**
 * Murphy agents — barrel export.
 * Design Label: MURPHY-AGENTS-INDEX-001
 *
 * NOTE: TypeScript agents are stubs pointing to the Python implementations.
 * All agent logic runs server-side in Python; this file exists for type
 * registration and import consistency.
 */

export const AGENT_REGISTRY = [
  "ManifestAgent",
  "RosettaAgent",
  "LyapunovAgent",
  "RecommissionAgent",
  "RenderAgent",
  "PackageAgent",
] as const;

export type AgentName = (typeof AGENT_REGISTRY)[number];

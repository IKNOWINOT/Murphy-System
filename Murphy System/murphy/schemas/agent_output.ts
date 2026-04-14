// Copyright © 2020 Inoni Limited Liability Company
// Creator: Corey Post
// License: BSL 1.1
/**
 * Universal AgentOutput schema — TypeScript mirror of agent_output.py
 *
 * Design Label: MURPHY-SCHEMA-TS-001
 * Owner: Platform Engineering
 *
 * Every agent in the Murphy system MUST return an AgentOutput.
 * Freeform text and untyped objects are forbidden.
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Enums  (MURPHY-SCHEMA-ENUM-TS-001)
// ---------------------------------------------------------------------------

export enum ContentType {
  SVG = "svg",
  HTML = "html",
  ZIP = "zip",
  PDF = "pdf",
  CODE = "code",
  CHART = "chart",
  COMPLIANCE_REPORT = "compliance_report",
  MATRIX_MESSAGE = "matrix_message",
  JSON_MANIFEST = "json_manifest",
  TEST_SUITE = "test_suite",
  PASS_FAIL = "pass_fail",
  AUTOMATION_PROPOSAL = "automation_proposal",
  AUDIT_ENTRY = "audit_entry",
}

export enum RenderType {
  DIAGRAM = "diagram",
  WIDGET = "widget",
  DOWNLOAD = "download",
  DOCUMENT = "document",
  SYNTAX_HIGHLIGHT = "syntax_highlight",
  DATA_VIZ = "data_viz",
  MESSAGE = "message",
}

// ---------------------------------------------------------------------------
// Zod schema  (MURPHY-SCHEMA-ZOD-001)
// ---------------------------------------------------------------------------

export const AgentOutputSchema = z
  .object({
    agent_id: z.string().min(1),
    agent_name: z.string().min(1),
    file_path: z.string().min(1),
    content_type: z.nativeEnum(ContentType),
    content: z.string(),
    lang: z.string().nullable().optional(),
    depends_on: z.array(z.string()).default([]),
    org_node_id: z.string().min(1),
    rosetta_state_hash: z.string().min(1),
    render_type: z.nativeEnum(RenderType),
    hitl_required: z.boolean().default(false),
    hitl_authority_node_id: z.string().nullable().optional(),
    bat_seal_required: z.boolean().default(false),
    error: z.string().nullable().optional(),
    timestamp: z.string().datetime(),
    schema_version: z.string().default("1.0.0"),
  })
  .refine(
    (data) => !(data.hitl_required && !data.hitl_authority_node_id),
    {
      message:
        "MURPHY-SCHEMA-ERR-001: hitl_authority_node_id must be set when hitl_required is True",
      path: ["hitl_authority_node_id"],
    }
  )
  .refine(
    (data) =>
      data.content_type !== ContentType.PASS_FAIL ||
      data.content === "PASS" ||
      data.content === "FAIL",
    {
      message:
        "MURPHY-SCHEMA-ERR-002: content must be 'PASS' or 'FAIL' when content_type is pass_fail",
      path: ["content"],
    }
  );

// ---------------------------------------------------------------------------
// TypeScript interface  (MURPHY-SCHEMA-IF-001)
// ---------------------------------------------------------------------------

export interface AgentOutput {
  agent_id: string;
  agent_name: string;
  file_path: string;
  content_type: ContentType;
  content: string;
  lang?: string | null;
  depends_on: string[];
  org_node_id: string;
  rosetta_state_hash: string;
  render_type: RenderType;
  hitl_required: boolean;
  hitl_authority_node_id?: string | null;
  bat_seal_required: boolean;
  error?: string | null;
  timestamp: string;
  schema_version: string;
}

// ---------------------------------------------------------------------------
// Validation  (MURPHY-SCHEMA-VALIDATE-001)
// ---------------------------------------------------------------------------

/**
 * Validate an unknown value against the AgentOutput schema.
 * Throws a typed ZodError on failure — never returns undefined.
 */
export function validateAgentOutput(output: unknown): AgentOutput {
  return AgentOutputSchema.parse(output) as AgentOutput;
}

// ---------------------------------------------------------------------------
// Error factory  (MURPHY-SCHEMA-FACTORY-TS-001)
// ---------------------------------------------------------------------------

/**
 * Create a valid FAIL AgentOutput for error reporting.
 */
export function agentOutputFromError(
  agentId: string,
  agentName: string,
  filePath: string,
  orgNodeId: string,
  errorMessage: string
): AgentOutput {
  return {
    agent_id: agentId,
    agent_name: agentName,
    file_path: filePath,
    content_type: ContentType.PASS_FAIL,
    content: "FAIL",
    lang: null,
    depends_on: [],
    org_node_id: orgNodeId,
    rosetta_state_hash: "error-state",
    render_type: RenderType.SYNTAX_HIGHLIGHT,
    hitl_required: false,
    hitl_authority_node_id: null,
    bat_seal_required: true,
    error: errorMessage,
    timestamp: new Date().toISOString(),
    schema_version: "1.0.0",
  };
}

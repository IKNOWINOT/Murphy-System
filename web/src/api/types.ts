/**
 * types.ts — Shared TypeScript interfaces matching Murphy System backend Pydantic models.
 *
 * These types ensure frontend code and the FastAPI backend speak the same language.
 * Keep in sync with: src/form_intake/schemas.py, src/runtime/app.py execute endpoint.
 *
 * © 2020 Inoni Limited Liability Company · BSL 1.1
 */

// ── Standard API response envelope ───────────────────────────────────────

/** Every Murphy API response follows this envelope. */
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: ApiError;
}

/** Structured API error. */
export interface ApiError {
  code: string;
  message: string;
}

// ── Health ────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  version?: string;
  mfgc_enabled?: boolean;
  uptime_seconds?: number;
  timestamp?: string;
}

// ── Form Intake ───────────────────────────────────────────────────────────

/** Maps to src/form_intake/schemas.py FormType enum. */
export type FormType =
  | "plan_upload"
  | "plan_generation"
  | "task_execution"
  | "validation"
  | "correction";

/** Maps to src/form_intake/schemas.py ExpansionLevel enum. */
export type ExpansionLevel = "minimal" | "moderate" | "comprehensive";

/** Maps to src/form_intake/schemas.py CheckpointType enum. */
export type CheckpointType =
  | "before_execution"
  | "after_each_phase"
  | "on_high_risk"
  | "on_low_confidence"
  | "final_review";

/** Maps to src/form_intake/schemas.py FormSubmission. */
export interface FormSubmissionResult {
  form_id: string;
  form_type: FormType;
  status: "pending" | "processing" | "completed" | "failed";
  submitted_at?: string;
  completed_at?: string;
  result?: unknown;
  errors?: string[];
}

// ── Flow Execution ────────────────────────────────────────────────────────

/** Describes a node in a flow graph. */
export interface FlowNode {
  id: string;
  kind: "start" | "end" | "action" | "decision" | "parallel" | string;
  label: string;
  metadata?: Record<string, unknown>;
}

/** Describes an edge in a flow graph. */
export interface FlowEdge {
  from: string;
  to: string;
  condition?: string;
  label?: string;
}

/** Complete flow graph sent to the execute endpoint. */
export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
  metadata?: Record<string, unknown>;
}

/** Maps to the /api/execute response shape. */
export interface FlowExecutionResult {
  success: boolean;
  output?: unknown;
  trace_id?: string;
  error?: string;
}

// ── Module Compiler ───────────────────────────────────────────────────────

/** Maps to src/module_compiler/models/module_spec.py ModuleSpec. */
export interface ModuleSpec {
  module_id: string;
  source_path: string;
  version_hash?: string;
  capabilities: CapabilitySpec[];
  sandbox_profile?: Record<string, unknown>;
  verification_status: "passed" | "failed" | "pending";
  is_partial: boolean;
  requires_manual_review: boolean;
  uncertainty_flags: string[];
  compiled_at?: string;
}

/** A single capability within a module. */
export interface CapabilitySpec {
  name: string;
  description: string;
  deterministic: boolean;
  requires_network: boolean;
  timeout_seconds: number;
}

// ── Gate Synthesis ────────────────────────────────────────────────────────

export type GateState = "proposed" | "active" | "retired";
export type GateCategory = "safety" | "quality" | "compliance" | "performance" | string;

export interface Gate {
  id: string;
  state: GateState;
  category: GateCategory;
  description?: string;
  created_at?: string;
}

// ── Cost Optimization ─────────────────────────────────────────────────────

export interface CostRecommendation {
  id: string;
  resource_id: string;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "pending" | "applied" | "dismissed";
  description: string;
  estimated_savings?: number;
  currency?: string;
}

// ── Compliance ────────────────────────────────────────────────────────────

export interface ComplianceRule {
  id: string;
  name: string;
  framework: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "active" | "disabled";
  expression: string;
  description?: string;
  remediation?: string;
}

export interface ComplianceScan {
  id: string;
  name: string;
  status: "running" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  passed: number;
  failed: number;
  errored: number;
}

// ── Blockchain Audit Trail ────────────────────────────────────────────────

export type EntryType = "api_call" | "admin_action" | "config_change" | "auth_event" | string;

export interface AuditEntry {
  id: string;
  entry_type: EntryType;
  actor: string;
  action: string;
  resource?: string;
  details?: Record<string, unknown>;
  timestamp: string;
  outcome: "success" | "failure";
}

export interface AuditBlock {
  id: string;
  index: number;
  previous_hash: string;
  hash: string;
  timestamp: string;
  entries: AuditEntry[];
}

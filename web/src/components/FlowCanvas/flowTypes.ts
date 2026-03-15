export type NodeKind =
  | "action"
  | "condition"
  | "human-approval"
  | "parallel-fork"
  | "parallel-join"
  | "start"
  | "end";

export interface FlowNode {
  id: string;
  kind: NodeKind;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  metadata?: Record<string, unknown>;
}

export interface FlowEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
  condition?: string;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
  metadata?: Record<string, unknown>;
}

export interface FlowExecutionResult {
  success: boolean;
  output?: unknown;
  error?: string;
  trace_id?: string;
}

export const NodeColors: Record<NodeKind, string> = {
  action: "#00ff41",
  condition: "#ffaa00",
  "human-approval": "#ff6b6b",
  "parallel-fork": "#00d4ff",
  "parallel-join": "#00d4ff",
  start: "#39ff14",
  end: "#ff073a",
};

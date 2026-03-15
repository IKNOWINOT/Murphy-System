import type { FlowGraph, FlowExecutionResult } from "./flowTypes";
import { post, get } from "../../api/murphyClient";

export function convertFlowToStateGraph(graph: FlowGraph): Record<string, unknown> {
  const states: Record<string, unknown> = {};

  for (const node of graph.nodes) {
    const outEdges = graph.edges.filter((e) => e.from === node.id);

    const stateEntry: Record<string, unknown> = {
      type: node.kind,
      label: node.label,
    };

    if (node.metadata) {
      Object.assign(stateEntry, node.metadata);
    }

    if (outEdges.length === 1) {
      stateEntry.next = outEdges[0].to;
    } else if (outEdges.length > 1) {
      stateEntry.transitions = outEdges.map((e) => ({
        target: e.to,
        condition: e.condition ?? e.label ?? null,
      }));
    }

    states[node.id] = stateEntry;
  }

  const startNode = graph.nodes.find((n) => n.kind === "start");

  return {
    version: "1.0",
    initial: startNode?.id ?? null,
    states,
    metadata: graph.metadata ?? {},
  };
}

export async function executeFlow(
  graph: FlowGraph,
  /** @deprecated apiBase is ignored; murphyClient reads base URL from VITE_API_BASE env var */
  _deprecatedApiBase = ""
): Promise<FlowExecutionResult> {
  const stateGraph = convertFlowToStateGraph(graph);
  const result = await post<{ output?: unknown; trace_id?: string }>("/api/execute", { state_graph: stateGraph });

  if (!result.success) {
    return { success: false, error: result.error?.message ?? "Execute failed" };
  }

  const data = result.data as Record<string, unknown> ?? {};
  return {
    success: true,
    output: data.output ?? data,
    trace_id: data.trace_id as string | undefined,
  };
}

export async function saveFlow(
  graph: FlowGraph,
  name: string,
  /** @deprecated apiBase is ignored; murphyClient reads base URL from VITE_API_BASE env var */
  _deprecatedApiBase = ""
): Promise<{ success: boolean; template_id?: string }> {
  const stateGraph = convertFlowToStateGraph(graph);
  const result = await post<{ template_id?: string; id?: string }>("/api/templates/publish", {
    name,
    state_graph: stateGraph,
    flow_graph: graph,
  });

  if (!result.success) return { success: false };
  const d = result.data as Record<string, unknown> ?? {};
  return { success: true, template_id: (d.template_id ?? d.id) as string | undefined };
}

export async function loadFlow(
  templateId: string,
  /** @deprecated apiBase is ignored; murphyClient reads base URL from VITE_API_BASE env var */
  _deprecatedApiBase = ""
): Promise<FlowGraph> {
  const result = await get<{ flow_graph?: FlowGraph } | FlowGraph>(`/api/templates/${templateId}`);

  if (!result.success) {
    throw new Error(`Failed to load template ${templateId}: ${result.error?.message ?? "Unknown error"}`);
  }

  const data = result.data as Record<string, unknown> | undefined;
  const flowGraph = (data?.flow_graph ?? data) as FlowGraph;
  return flowGraph;
}


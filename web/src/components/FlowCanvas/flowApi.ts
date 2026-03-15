import type { FlowGraph, FlowExecutionResult } from "./flowTypes";

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
  apiBase = ""
): Promise<FlowExecutionResult> {
  const stateGraph = convertFlowToStateGraph(graph);

  const response = await fetch(`${apiBase}/api/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state_graph: stateGraph }),
  });

  if (!response.ok) {
    const text = await response.text();
    return { success: false, error: `HTTP ${response.status}: ${text}` };
  }

  const data = await response.json();
  return {
    success: true,
    output: data.output ?? data,
    trace_id: data.trace_id,
  };
}

export async function saveFlow(
  graph: FlowGraph,
  name: string,
  apiBase = ""
): Promise<{ success: boolean; template_id?: string }> {
  const stateGraph = convertFlowToStateGraph(graph);

  const response = await fetch(`${apiBase}/api/templates/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, state_graph: stateGraph, flow_graph: graph }),
  });

  if (!response.ok) {
    return { success: false };
  }

  const data = await response.json();
  return { success: true, template_id: data.template_id ?? data.id };
}

export async function loadFlow(
  templateId: string,
  apiBase = ""
): Promise<FlowGraph> {
  const response = await fetch(`${apiBase}/api/templates/${templateId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Failed to load template ${templateId}: HTTP ${response.status}`);
  }

  const data = await response.json();
  const flowGraph: FlowGraph = data.flow_graph ?? data;
  return flowGraph;
}

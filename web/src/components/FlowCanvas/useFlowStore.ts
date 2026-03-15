import { useState, useCallback } from "react";
import type { FlowNode, FlowEdge, FlowGraph } from "./flowTypes";

export function useFlowStore() {
  const [nodes, setNodes] = useState<FlowNode[]>([]);
  const [edges, setEdges] = useState<FlowEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const addNode = useCallback((node: FlowNode) => {
    setNodes((prev) => [...prev, node]);
  }, []);

  const updateNode = useCallback((id: string, updates: Partial<FlowNode>) => {
    setNodes((prev) =>
      prev.map((n) => (n.id === id ? { ...n, ...updates } : n))
    );
  }, []);

  const removeNode = useCallback((id: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.from !== id && e.to !== id));
    setSelectedNodeId((prev) => (prev === id ? null : prev));
  }, []);

  const addEdge = useCallback((edge: FlowEdge) => {
    setEdges((prev) => [...prev, edge]);
  }, []);

  const removeEdge = useCallback((id: string) => {
    setEdges((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const selectNode = useCallback((id: string | null) => {
    setSelectedNodeId(id);
  }, []);

  const clearCanvas = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setSelectedNodeId(null);
  }, []);

  const loadGraph = useCallback((graph: FlowGraph) => {
    setNodes(graph.nodes);
    setEdges(graph.edges);
    setSelectedNodeId(null);
  }, []);

  const toGraph = useCallback((): FlowGraph => {
    return { nodes, edges };
  }, [nodes, edges]);

  return {
    nodes,
    edges,
    selectedNodeId,
    addNode,
    updateNode,
    removeNode,
    addEdge,
    removeEdge,
    selectNode,
    clearCanvas,
    loadGraph,
    toGraph,
  };
}

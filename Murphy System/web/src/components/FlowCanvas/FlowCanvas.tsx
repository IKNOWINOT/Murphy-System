import React, { useRef, useCallback, useState } from "react";
import { FlowNode } from "./FlowNode";
import { FlowEdge } from "./FlowEdge";
import { FlowToolbar } from "./FlowToolbar";
import { useFlowStore } from "./useFlowStore";
import { executeFlow, saveFlow, loadFlow } from "./flowApi";
import type { NodeKind, FlowNode as FlowNodeData } from "./flowTypes";
import "./FlowCanvas.css";

const CANVAS_WIDTH = 1200;
const CANVAS_HEIGHT = 700;
const NODE_WIDTH = 140;
const NODE_HEIGHT = 48;

let nodeCounter = 0;
function generateId(kind: NodeKind): string {
  return `${kind}-${++nodeCounter}-${Date.now()}`;
}

export const FlowCanvas: React.FC = () => {
  const {
    nodes,
    edges,
    selectedNodeId,
    addNode,
    updateNode,
    removeNode,
    addEdge,
    selectNode,
    clearCanvas,
    loadGraph,
    toGraph,
  } = useFlowStore();

  const [isRunning, setIsRunning] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string>("Ready.");
  const svgRef = useRef<SVGSVGElement>(null);

  const getSvgPoint = useCallback(
    (clientX: number, clientY: number): { x: number; y: number } => {
      if (!svgRef.current) return { x: 0, y: 0 };
      const rect = svgRef.current.getBoundingClientRect();
      return {
        x: clientX - rect.left,
        y: clientY - rect.top,
      };
    },
    []
  );

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      // Deselect when clicking empty canvas
      if ((e.target as SVGElement).tagName === "svg") {
        selectNode(null);
      }
    },
    [selectNode]
  );

  const handleAddNode = useCallback(
    (kind: NodeKind) => {
      const centerX = CANVAS_WIDTH / 2 - NODE_WIDTH / 2 + (Math.random() - 0.5) * 120;
      const centerY = CANVAS_HEIGHT / 2 - NODE_HEIGHT / 2 + (Math.random() - 0.5) * 80;
      const newNode: FlowNodeData = {
        id: generateId(kind),
        kind,
        label: kind.charAt(0).toUpperCase() + kind.slice(1),
        x: Math.round(centerX),
        y: Math.round(centerY),
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      };
      addNode(newNode);
      setStatusMsg(`Added ${kind} node.`);
    },
    [addNode]
  );

  const handleDragEnd = useCallback(
    (id: string, x: number, y: number) => {
      updateNode(id, { x, y });
    },
    [updateNode]
  );

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    setStatusMsg("Executing flow...");
    try {
      const graph = toGraph();
      const result = await executeFlow(graph);
      if (result.success) {
        setStatusMsg(
          `Execution complete.${result.trace_id ? ` trace_id=${result.trace_id}` : ""}`
        );
      } else {
        setStatusMsg(`Execution failed: ${result.error ?? "unknown error"}`);
      }
    } catch (err) {
      setStatusMsg(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsRunning(false);
    }
  }, [toGraph]);

  const handleSave = useCallback(async () => {
    const name = window.prompt("Flow template name:", "my-flow");
    if (!name) return;
    setStatusMsg("Saving...");
    try {
      const graph = toGraph();
      const result = await saveFlow(graph, name);
      setStatusMsg(
        result.success
          ? `Saved. template_id=${result.template_id ?? "unknown"}`
          : "Save failed."
      );
    } catch (err) {
      setStatusMsg(`Save error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [toGraph]);

  const handleLoad = useCallback(async () => {
    const id = window.prompt("Template ID to load:");
    if (!id) return;
    setStatusMsg("Loading...");
    try {
      const graph = await loadFlow(id);
      loadGraph(graph);
      setStatusMsg(`Loaded template ${id}. ${graph.nodes.length} nodes.`);
    } catch (err) {
      setStatusMsg(`Load error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [loadGraph]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if ((e.key === "Delete" || e.key === "Backspace") && selectedNodeId) {
        removeNode(selectedNodeId);
        setStatusMsg(`Removed node ${selectedNodeId}.`);
      }
    },
    [selectedNodeId, removeNode]
  );

  // Connect two nodes: click first node then shift-click second node
  const pendingConnectionRef = useRef<string | null>(null);

  const handleNodeSelect = useCallback(
    (id: string, e?: React.MouseEvent) => {
      if (e?.shiftKey && pendingConnectionRef.current && pendingConnectionRef.current !== id) {
        addEdge({
          id: `edge-${pendingConnectionRef.current}-${id}-${Date.now()}`,
          from: pendingConnectionRef.current,
          to: id,
        });
        setStatusMsg(`Connected ${pendingConnectionRef.current} → ${id}`);
        pendingConnectionRef.current = null;
        selectNode(null);
      } else {
        selectNode(id);
        pendingConnectionRef.current = id;
      }
    },
    [addEdge, selectNode]
  );

  const resolvedEdges = edges
    .map((edge) => ({
      edge,
      fromNode: nodes.find((n) => n.id === edge.from),
      toNode: nodes.find((n) => n.id === edge.to),
    }))
    .filter(
      (e): e is { edge: typeof e.edge; fromNode: FlowNodeData; toNode: FlowNodeData } =>
        e.fromNode !== undefined && e.toNode !== undefined
    );

  return (
    <div
      className="flow-canvas-container"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <FlowToolbar
        onAddNode={handleAddNode}
        onSave={handleSave}
        onLoad={handleLoad}
        onRun={handleRun}
        onClear={clearCanvas}
        isRunning={isRunning}
      />

      <div className="flow-canvas-viewport">
        <svg
          ref={svgRef}
          className="flow-canvas-svg"
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          onClick={handleCanvasClick}
        >
          {/* Grid background */}
          <defs>
            <pattern id="grid" width={40} height={40} patternUnits="userSpaceOnUse">
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="#0f2a0f"
                strokeWidth={0.5}
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Render edges below nodes */}
          <g className="flow-edges">
            {resolvedEdges.map(({ edge, fromNode, toNode }) => (
              <FlowEdge
                key={edge.id}
                edge={edge}
                fromNode={fromNode}
                toNode={toNode}
              />
            ))}
          </g>

          {/* Render nodes */}
          <g className="flow-nodes">
            {nodes.map((node) => (
              <FlowNode
                key={node.id}
                node={node}
                isSelected={node.id === selectedNodeId}
                onSelect={(id) => handleNodeSelect(id)}
                onDragEnd={handleDragEnd}
              />
            ))}
          </g>
        </svg>
      </div>

      <div className="flow-canvas-statusbar">
        <span>
          NODES: {nodes.length} | EDGES: {edges.length}
          {selectedNodeId ? ` | SELECTED: ${selectedNodeId}` : ""}
        </span>
        <span className="flow-canvas-statusbar__msg">{statusMsg}</span>
        <span className="flow-canvas-statusbar__hint">
          [Shift+Click] to connect nodes &nbsp; [Del] to remove selected
        </span>
      </div>
    </div>
  );
};

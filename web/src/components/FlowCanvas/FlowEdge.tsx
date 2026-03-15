import React from "react";
import type { FlowEdge as FlowEdgeData, FlowNode as FlowNodeData } from "./flowTypes";

interface FlowEdgeProps {
  edge: FlowEdgeData;
  fromNode: FlowNodeData;
  toNode: FlowNodeData;
}

const MARKER_ID = "murphy-arrow";

export const FlowEdge: React.FC<FlowEdgeProps> = ({ edge, fromNode, toNode }) => {
  const x1 = fromNode.x + fromNode.width / 2;
  const y1 = fromNode.y + fromNode.height / 2;
  const x2 = toNode.x + toNode.width / 2;
  const y2 = toNode.y + toNode.height / 2;

  // Shorten line ends so arrow tip lands at node border rather than center
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / len;
  const uy = dy / len;

  const startX = x1 + ux * (fromNode.width / 2);
  const startY = y1 + uy * (fromNode.height / 2);
  const endX = x2 - ux * (toNode.width / 2 + 8); // 8px gap for arrow head
  const endY = y2 - uy * (toNode.height / 2 + 8);

  const midX = (startX + endX) / 2;
  const midY = (startY + endY) / 2;

  const labelText = edge.label ?? edge.condition;

  return (
    <g>
      <defs>
        <marker
          id={MARKER_ID}
          markerWidth={10}
          markerHeight={7}
          refX={10}
          refY={3.5}
          orient="auto"
        >
          <polygon points="0 0, 10 3.5, 0 7" fill="#00ff41" />
        </marker>
      </defs>
      <line
        x1={startX}
        y1={startY}
        x2={endX}
        y2={endY}
        stroke="#00ff41"
        strokeWidth={1.5}
        markerEnd={`url(#${MARKER_ID})`}
        opacity={0.8}
      />
      {labelText && (
        <text
          x={midX}
          y={midY - 6}
          fill="#00ff41"
          fontSize={10}
          fontFamily="'Courier New', monospace"
          textAnchor="middle"
          style={{ userSelect: "none" }}
        >
          {labelText}
        </text>
      )}
    </g>
  );
};

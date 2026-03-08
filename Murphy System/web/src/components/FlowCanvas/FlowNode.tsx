import React, { useRef, useCallback } from "react";
import type { FlowNode as FlowNodeData } from "./flowTypes";
import { NodeColors } from "./flowTypes";

interface FlowNodeProps {
  node: FlowNodeData;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
}

export const FlowNode: React.FC<FlowNodeProps> = ({
  node,
  isSelected,
  onSelect,
  onDragEnd,
}) => {
  const color = NodeColors[node.kind];
  const dragOrigin = useRef<{ mouseX: number; mouseY: number; nodeX: number; nodeY: number } | null>(null);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGGElement>) => {
      e.stopPropagation();
      onSelect(node.id);
      dragOrigin.current = {
        mouseX: e.clientX,
        mouseY: e.clientY,
        nodeX: node.x,
        nodeY: node.y,
      };

      const handleMouseMove = (moveEvent: MouseEvent) => {
        if (!dragOrigin.current) return;
        const dx = moveEvent.clientX - dragOrigin.current.mouseX;
        const dy = moveEvent.clientY - dragOrigin.current.mouseY;
        onDragEnd(node.id, dragOrigin.current.nodeX + dx, dragOrigin.current.nodeY + dy);
      };

      const handleMouseUp = () => {
        dragOrigin.current = null;
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      };

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    },
    [node.id, node.x, node.y, onSelect, onDragEnd]
  );

  const strokeWidth = isSelected ? 3 : 1;
  const textX = node.x + node.width / 2;
  const textY = node.y + node.height / 2;

  return (
    <g onMouseDown={handleMouseDown} style={{ cursor: "grab" }}>
      <rect
        x={node.x}
        y={node.y}
        width={node.width}
        height={node.height}
        fill="#0a0a0a"
        stroke={color}
        strokeWidth={strokeWidth}
        rx={4}
        ry={4}
      />
      <text
        x={textX}
        y={textY - 6}
        fill={color}
        fontSize={10}
        fontFamily="'Courier New', monospace"
        textAnchor="middle"
        dominantBaseline="middle"
        pointerEvents="none"
        style={{ userSelect: "none" }}
      >
        [{node.kind}]
      </text>
      <text
        x={textX}
        y={textY + 8}
        fill="#00ff41"
        fontSize={12}
        fontFamily="'Courier New', monospace"
        textAnchor="middle"
        dominantBaseline="middle"
        pointerEvents="none"
        style={{ userSelect: "none" }}
      >
        {node.label}
      </text>
    </g>
  );
};

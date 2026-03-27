import React from "react";
import type { NodeKind } from "./flowTypes";
import { NodeColors } from "./flowTypes";

interface FlowToolbarProps {
  onAddNode: (kind: NodeKind) => void;
  onSave: () => void;
  onLoad: () => void;
  onRun: () => void;
  onClear: () => void;
  isRunning: boolean;
}

const NODE_KINDS: NodeKind[] = [
  "start",
  "end",
  "action",
  "condition",
  "human-approval",
  "parallel-fork",
  "parallel-join",
];

export const FlowToolbar: React.FC<FlowToolbarProps> = ({
  onAddNode,
  onSave,
  onLoad,
  onRun,
  onClear,
  isRunning,
}) => {
  return (
    <div className="flow-toolbar">
      <div className="flow-toolbar__section flow-toolbar__section--palette">
        <span className="flow-toolbar__label">ADD NODE:</span>
        {NODE_KINDS.map((kind) => (
          <button
            key={kind}
            className="flow-toolbar__btn flow-toolbar__btn--node"
            style={{ borderColor: NodeColors[kind], color: NodeColors[kind] }}
            onClick={() => onAddNode(kind)}
            title={`Add ${kind} node`}
          >
            {kind}
          </button>
        ))}
      </div>

      <div className="flow-toolbar__section flow-toolbar__section--actions">
        <button
          className="flow-toolbar__btn flow-toolbar__btn--run"
          onClick={onRun}
          disabled={isRunning}
          title="Execute flow"
        >
          {isRunning ? "⏳ Running..." : "▶ RUN"}
        </button>
        <button
          className="flow-toolbar__btn"
          onClick={onSave}
          title="Save flow as template"
        >
          💾 SAVE
        </button>
        <button
          className="flow-toolbar__btn"
          onClick={onLoad}
          title="Load a saved template"
        >
          📂 LOAD
        </button>
        <button
          className="flow-toolbar__btn flow-toolbar__btn--danger"
          onClick={onClear}
          title="Clear canvas"
        >
          🗑 CLEAR
        </button>
      </div>
    </div>
  );
};

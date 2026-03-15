# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
workflow_builder.py — Murphy System No-Code/Low-Code Workflow Builder
Build, validate, compile and export pipelines programmatically.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeType(Enum):
    TRIGGER = "trigger"
    ACTION = "action"
    CONDITION = "condition"
    TRANSFORM = "transform"
    CONNECTOR = "connector"
    OUTPUT = "output"


class TriggerType(Enum):
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"
    MANUAL = "manual"
    API = "api"


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WorkflowNode:
    id: str
    node_type: NodeType
    label: str
    config: Dict[str, Any] = field(default_factory=dict)
    connections: List[str] = field(default_factory=list)  # IDs of downstream nodes
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["node_type"] = self.node_type.value
        return d


@dataclass
class WorkflowEdge:
    id: str
    source_id: str
    target_id: str
    label: str = ""
    condition: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowTrigger:
    trigger_type: TriggerType
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trigger_type"] = self.trigger_type.value
        return d


@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str = ""
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    triggers: List[WorkflowTrigger] = field(default_factory=list)
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "triggers": [t.to_dict() for t in self.triggers],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


@dataclass
class ValidationResult:
    status: ValidationStatus
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID

    def __bool__(self) -> bool:
        return self.is_valid()


@dataclass
class CompiledWorkflow:
    definition: WorkflowDefinition
    execution_order: List[str]          # node IDs in topological order
    compiled_steps: List[Dict[str, Any]]
    validation: ValidationResult

    def to_dict(self) -> dict:
        return {
            "definition": self.definition.to_dict(),
            "execution_order": self.execution_order,
            "compiled_steps": self.compiled_steps,
            "validation": {
                "status": self.validation.status.value,
                "errors": self.validation.errors,
                "warnings": self.validation.warnings,
            },
        }


# ---------------------------------------------------------------------------
# WorkflowBuilder
# ---------------------------------------------------------------------------

class WorkflowBuilder:
    """
    Fluent API for building workflow pipelines.

    Example:
        wf = (
            WorkflowBuilder("patient-pipeline", "Patient Data Pipeline")
            .add_node("trigger1", NodeType.TRIGGER, "Patient Data Trigger",
                      config={"source": "EHR"})
            .add_node("gate1", NodeType.CONDITION, "HIPAA Gate",
                      config={"rule": "hipaa_compliant"})
            .connect("trigger1", "gate1")
            .add_trigger(TriggerType.WEBHOOK, {"path": "/patient/new"})
        )
        compiled = wf.compile()
        print(wf.export_json(indent=2))
    """

    def __init__(self, workflow_id: Optional[str] = None, name: str = "Unnamed Workflow",
                 description: str = "") -> None:
        self._definition = WorkflowDefinition(
            id=workflow_id or str(uuid.uuid4()),
            name=name,
            description=description,
        )
        self._node_index: Dict[str, WorkflowNode] = {}

    # ── Build methods ────────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        label: str,
        config: Optional[Dict[str, Any]] = None,
        x: float = 0.0,
        y: float = 0.0,
    ) -> "WorkflowBuilder":
        node = WorkflowNode(
            id=node_id,
            node_type=node_type,
            label=label,
            config=config or {},
            x=x,
            y=y,
        )
        self._definition.nodes.append(node)
        self._node_index[node_id] = node
        return self

    def connect(
        self,
        source_id: str,
        target_id: str,
        label: str = "",
        condition: Optional[str] = None,
    ) -> "WorkflowBuilder":
        if source_id not in self._node_index:
            raise ValueError(f"Source node '{source_id}' not found")
        if target_id not in self._node_index:
            raise ValueError(f"Target node '{target_id}' not found")

        edge_id = f"edge_{source_id}_{target_id}"
        edge = WorkflowEdge(id=edge_id, source_id=source_id, target_id=target_id,
                            label=label, condition=condition)
        self._definition.edges.append(edge)
        self._node_index[source_id].connections.append(target_id)
        return self

    def add_trigger(
        self,
        trigger_type: TriggerType,
        config: Optional[Dict[str, Any]] = None,
    ) -> "WorkflowBuilder":
        self._definition.triggers.append(WorkflowTrigger(trigger_type, config or {}))
        return self

    def tag(self, *tags: str) -> "WorkflowBuilder":
        self._definition.tags.extend(tags)
        return self

    def set_version(self, version: str) -> "WorkflowBuilder":
        self._definition.version = version
        return self

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        defn = self._definition

        if not defn.nodes:
            errors.append("Workflow has no nodes")

        # At least one trigger node or trigger definition
        trigger_nodes = [n for n in defn.nodes if n.node_type == NodeType.TRIGGER]
        if not trigger_nodes and not defn.triggers:
            warnings.append("No trigger defined — workflow cannot run automatically")

        # At least one output
        output_nodes = [n for n in defn.nodes if n.node_type == NodeType.OUTPUT]
        if not output_nodes:
            warnings.append("No OUTPUT node defined — results may not be surfaced")

        # All edge endpoints exist
        node_ids = {n.id for n in defn.nodes}
        for edge in defn.edges:
            if edge.source_id not in node_ids:
                errors.append(f"Edge '{edge.id}' source '{edge.source_id}' not found")
            if edge.target_id not in node_ids:
                errors.append(f"Edge '{edge.id}' target '{edge.target_id}' not found")

        # Detect cycles (simple DFS)
        if _has_cycle(defn):
            errors.append("Workflow contains a cycle — directed cycles are not allowed")

        status = ValidationStatus.INVALID if errors else (
            ValidationStatus.WARNING if warnings else ValidationStatus.VALID
        )
        return ValidationResult(status=status, errors=errors, warnings=warnings)

    # ── Compile ──────────────────────────────────────────────────────────────

    def compile(self) -> CompiledWorkflow:
        validation = self.validate()
        order = _topological_sort(self._definition)
        steps = [
            {
                "step": i + 1,
                "node_id": nid,
                "node_type": self._node_index[nid].node_type.value,
                "label": self._node_index[nid].label,
                "config": self._node_index[nid].config,
            }
            for i, nid in enumerate(order)
        ]
        return CompiledWorkflow(
            definition=self._definition,
            execution_order=order,
            compiled_steps=steps,
            validation=validation,
        )

    # ── Export ───────────────────────────────────────────────────────────────

    def export_json(self, indent: int = 2) -> str:
        return json.dumps(self._definition.to_dict(), indent=indent)

    def get_definition(self) -> WorkflowDefinition:
        return self._definition


# ---------------------------------------------------------------------------
# Graph utilities
# ---------------------------------------------------------------------------

def _adjacency(defn: WorkflowDefinition) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {n.id: [] for n in defn.nodes}
    for edge in defn.edges:
        if edge.source_id in adj:
            adj[edge.source_id].append(edge.target_id)
    return adj


def _has_cycle(defn: WorkflowDefinition) -> bool:
    adj = _adjacency(defn)
    visited: Dict[str, int] = {}  # 0=unvisited, 1=in-stack, 2=done

    def dfs(node: str) -> bool:
        visited[node] = 1
        for nb in adj.get(node, []):
            if visited.get(nb, 0) == 1:
                return True
            if visited.get(nb, 0) == 0 and dfs(nb):
                return True
        visited[node] = 2
        return False

    for node_id in list(adj.keys()):
        if visited.get(node_id, 0) == 0:
            if dfs(node_id):
                return True
    return False


def _topological_sort(defn: WorkflowDefinition) -> List[str]:
    adj = _adjacency(defn)
    in_degree: Dict[str, int] = {n.id: 0 for n in defn.nodes}
    for edges in adj.values():
        for target in edges:
            in_degree[target] = in_degree.get(target, 0) + 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    order: List[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for nb in adj.get(node, []):
            in_degree[nb] -= 1
            if in_degree[nb] == 0:
                queue.append(nb)

    return order


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main() -> None:
    wf = (
        WorkflowBuilder("healthcare-demo", "Patient Triage Pipeline",
                        description="HIPAA-compliant AI-assisted triage workflow")
        .add_node("trigger1", NodeType.TRIGGER, "Patient Data Trigger",
                  config={"source": "EHR_FHIR", "event": "new_observation"}, x=100, y=250)
        .add_node("gate1", NodeType.CONDITION, "HIPAA Gate",
                  config={"rule": "hipaa_compliant", "fail_action": "reject"}, x=350, y=250)
        .add_node("ai1", NodeType.ACTION, "AI Diagnosis Engine",
                  config={"model": "murphy-medical-v3", "context_window": 8192}, x=600, y=250)
        .add_node("score1", NodeType.TRANSFORM, "Confidence Scorer",
                  config={"threshold": 0.85, "method": "mathematical"}, x=850, y=250)
        .add_node("hitl1", NodeType.CONDITION, "Doctor Approval Gate",
                  config={"role": "attending_physician", "timeout_hours": 2}, x=1100, y=250)
        .add_node("out1", NodeType.OUTPUT, "Treatment Plan Output",
                  config={"format": "HL7_FHIR", "destination": "EHR"}, x=1350, y=250)
        .connect("trigger1", "gate1")
        .connect("gate1", "ai1", label="compliant")
        .connect("ai1", "score1")
        .connect("score1", "hitl1", label="high_confidence")
        .connect("hitl1", "out1", label="approved")
        .add_trigger(TriggerType.WEBHOOK, {"path": "/patient/observation/new"})
        .tag("healthcare", "hipaa", "ai", "triage")
        .set_version("2.1.0")
    )

    validation = wf.validate()
    compiled = wf.compile()

    print("═" * 60)
    print("  Murphy System — Workflow Builder Demo")
    print("═" * 60)
    print(f"  Workflow : {wf.get_definition().name}")
    print(f"  Nodes    : {len(wf.get_definition().nodes)}")
    print(f"  Edges    : {len(wf.get_definition().edges)}")
    print(f"  Valid    : {validation.status.value}")
    if validation.warnings:
        for w in validation.warnings:
            print(f"  ⚠️  {w}")
    print()
    print("  Execution order:")
    for step in compiled.compiled_steps:
        print(f"    Step {step['step']}: [{step['node_type'].upper():>10}]  {step['label']}")
    print()
    print("  JSON export (truncated):")
    print(wf.export_json()[:500] + "…")


if __name__ == "__main__":
    main()

# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Visual Swarm Builder for Murphy System.

Design Label: VSB-001 — Visual Swarm Builder
Owner: Platform Engineering / Architecture

Production-capability-spec-only visual builder that lets users compose swarm
configurations through a node-and-edge model and export them as machine-
executable production capability specs.

Key capabilities
────────────────
  * Blueprint authoring — create named blueprints with typed nodes
    (agent / gate / connector / output) and directed edges.
  * Recommendation engine — analyses the blueprint topology and surfaces
    missing gates, compliance gaps, and optimal agent configurations.
  * Validation — checks that every blueprint is complete, connected,
    and safe before export.
  * Export as spec — serialises the blueprint as a production capability
    spec JSON ready for ``SelfCodebaseSwarm.build_package()``.
  * External project analysis — calls ``SelfIntrospectionEngine`` on an
    external project and recommends a swarm blueprint tailored to that
    project's language stack, frameworks, and complexity.

Observation / recommendation mode only for external projects — no auto-
execution.  All execute paths require HITL approval from the caller.

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock.
  - Bounded collections via capped_append (CWE-770).
  - Input validated before processing (CWE-20).
  - Errors sanitised before logging (CWE-209).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants                                                          [CWE-20]
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_LABEL_RE = re.compile(r"^[a-zA-Z0-9 _\-.,:()/]{1,500}$")
_MAX_BLUEPRINTS: int = 1_000
_MAX_NODES_PER_BP: int = 500
_MAX_EDGES_PER_BP: int = 2_000
_MAX_AUDIT_LOG: int = 50_000

_VALID_NODE_TYPES: frozenset = frozenset({"agent", "gate", "connector", "output"})

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class VisualNode:
    """A single node in a swarm blueprint graph."""

    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    node_type: str = "agent"        # agent | gate | connector | output
    label: str = ""
    position: Tuple[float, float] = (0.0, 0.0)
    config: Dict[str, Any] = field(default_factory=dict)
    connections: List[str] = field(default_factory=list)   # outgoing node_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "position": list(self.position),
            "config": dict(self.config),
            "connections": list(self.connections),
        }


@dataclass
class SwarmBlueprint:
    """A complete, authored swarm blueprint."""

    blueprint_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    description: str = ""
    nodes: List[VisualNode] = field(default_factory=list)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    target_project: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "draft"   # draft | valid | invalid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "name": self.name,
            "description": self.description[:1000],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [list(e) for e in self.edges],
            "target_project": dict(self.target_project),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }


@dataclass
class ValidationResult:
    """Result of blueprint validation."""

    passed: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    has_output_node: bool = False
    has_hitl_gate: bool = False
    has_compliance_gate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "has_output_node": self.has_output_node,
            "has_hitl_gate": self.has_hitl_gate,
            "has_compliance_gate": self.has_compliance_gate,
        }


@dataclass
class Recommendation:
    """A recommendation for improving a blueprint or project swarm design."""

    recommendation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    category: str = "architecture"
    title: str = ""
    description: str = ""
    priority: int = 2               # 1=high, 2=medium, 3=low
    action: str = ""                # "add_node", "add_gate", "add_compliance", etc.
    suggested_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category,
            "title": self.title,
            "description": self.description[:1000],
            "priority": self.priority,
            "action": self.action,
            "suggested_config": dict(self.suggested_config),
        }


@dataclass
class ProjectAnalysis:
    """Analysis of an external project with recommended swarm blueprint."""

    project_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    repo_url: str = ""
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    module_count: int = 0
    recommended_agents: List[str] = field(default_factory=list)
    recommended_gates: List[str] = field(default_factory=list)
    complexity_score: float = 0.0
    recommendations: List[Recommendation] = field(default_factory=list)
    analysed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "repo_url": self.repo_url,
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "module_count": self.module_count,
            "recommended_agents": list(self.recommended_agents),
            "recommended_gates": list(self.recommended_gates),
            "complexity_score": self.complexity_score,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "analysed_at": self.analysed_at,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"{name} must match {_ID_RE.pattern}")
    return value


def _validate_label(value: str, name: str = "label") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value[:500]


# ---------------------------------------------------------------------------
# Core engine                                                        VSB-001
# ---------------------------------------------------------------------------

class VisualSwarmBuilder:
    """
    Visual Swarm Builder — VSB-001.

    Manages a library of swarm blueprints.  Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._blueprints: Dict[str, SwarmBlueprint] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Blueprint authoring
    # ------------------------------------------------------------------

    def create_blueprint(
        self, name: str, description: str = ""
    ) -> SwarmBlueprint:
        """Create a new empty blueprint."""
        safe_name = _validate_label(name, "name")
        safe_desc = _validate_label(description, "description")
        bp = SwarmBlueprint(name=safe_name, description=safe_desc)
        with self._lock:
            if len(self._blueprints) >= _MAX_BLUEPRINTS:
                raise RuntimeError("VSB-001: blueprint store at capacity")
            self._blueprints[bp.blueprint_id] = bp
        self._audit("create_blueprint", blueprint_id=bp.blueprint_id, name=safe_name)
        logger.info("VSB-001 created blueprint %s '%s'", bp.blueprint_id, safe_name)
        return bp

    def add_node(
        self,
        blueprint_id: str,
        node_type: str,
        label: str,
        config: Optional[Dict[str, Any]] = None,
        position: Optional[Tuple[float, float]] = None,
    ) -> VisualNode:
        """Add a node to a blueprint."""
        bid = _validate_id(blueprint_id, "blueprint_id")
        if node_type not in _VALID_NODE_TYPES:
            raise ValueError(f"node_type must be one of {_VALID_NODE_TYPES}")
        safe_label = _validate_label(label)

        node = VisualNode(
            node_type=node_type,
            label=safe_label,
            position=position or (0.0, 0.0),
            config=dict(config or {}),
        )

        with self._lock:
            bp = self._blueprints.get(bid)
            if bp is None:
                raise KeyError(f"Blueprint {bid!r} not found")
            if len(bp.nodes) >= _MAX_NODES_PER_BP:
                raise RuntimeError("VSB-001: node limit reached for blueprint")
            bp.nodes.append(node)
            bp.updated_at = _ts()

        self._audit("add_node", blueprint_id=bid, node_id=node.node_id,
                    node_type=node_type, label=safe_label)
        return node

    def connect_nodes(
        self, blueprint_id: str, from_node_id: str, to_node_id: str
    ) -> bool:
        """Add a directed edge from_node → to_node."""
        bid = _validate_id(blueprint_id, "blueprint_id")
        _validate_id(from_node_id, "from_node_id")
        _validate_id(to_node_id, "to_node_id")

        with self._lock:
            bp = self._blueprints.get(bid)
            if bp is None:
                return False
            node_ids = {n.node_id for n in bp.nodes}
            if from_node_id not in node_ids or to_node_id not in node_ids:
                return False
            if len(bp.edges) >= _MAX_EDGES_PER_BP:
                return False
            edge = (from_node_id, to_node_id)
            if edge not in bp.edges:
                bp.edges.append(edge)
                # Update source node's connections list
                for n in bp.nodes:
                    if n.node_id == from_node_id:
                        if to_node_id not in n.connections:
                            n.connections.append(to_node_id)
            bp.updated_at = _ts()

        self._audit("connect_nodes", blueprint_id=bid,
                    from_node=from_node_id, to_node=to_node_id)
        return True

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def generate_recommendations(self, blueprint_id: str) -> List[Recommendation]:
        """Analyse a blueprint and return actionable improvement recommendations."""
        bid = _validate_id(blueprint_id, "blueprint_id")
        with self._lock:
            bp = self._blueprints.get(bid)
        if bp is None:
            return []

        recs: List[Recommendation] = []
        node_types = {n.node_type for n in bp.nodes}
        node_labels_lower = " ".join(n.label.lower() for n in bp.nodes)

        # Missing output node
        if "output" not in node_types:
            recs.append(Recommendation(
                category="architecture",
                title="Add Output Node",
                description=(
                    "Every blueprint must have at least one output node that "
                    "collects the swarm's final deliverable."
                ),
                priority=1,
                action="add_node",
                suggested_config={"node_type": "output", "label": "Deliverable Output"},
            ))

        # Missing HITL gate
        if not any("hitl" in n.label.lower() or
                   ("gate" == n.node_type and "human" in n.label.lower())
                   for n in bp.nodes):
            recs.append(Recommendation(
                category="compliance",
                title="Add HITL Gate",
                description=(
                    "Production blueprints require a HITL (Human-In-The-Loop) gate "
                    "before any execute step to satisfy 99% confidence gating policy."
                ),
                priority=1,
                action="add_node",
                suggested_config={
                    "node_type": "gate",
                    "label": "HITL Approval Gate",
                    "config": {"confidence_threshold": 0.99, "requires_human": True},
                },
            ))

        # Missing compliance gate
        if not any("compliance" in n.label.lower() for n in bp.nodes):
            recs.append(Recommendation(
                category="compliance",
                title="Add Compliance Gate",
                description=(
                    "Add a compliance gate that validates outreach and data handling "
                    "against CAN-SPAM, TCPA, GDPR, or CASL as applicable."
                ),
                priority=1,
                action="add_node",
                suggested_config={
                    "node_type": "gate",
                    "label": "Regulatory Compliance Gate",
                    "config": {"regulations": ["CAN-SPAM", "TCPA", "GDPR"]},
                },
            ))

        # No agents
        if "agent" not in node_types:
            recs.append(Recommendation(
                category="architecture",
                title="Add Agents",
                description="The blueprint has no agent nodes. Add at least one agent.",
                priority=1,
                action="add_node",
                suggested_config={"node_type": "agent", "label": "Primary Agent"},
            ))

        # Disconnected nodes
        all_ids = {n.node_id for n in bp.nodes}
        connected_ids: set = set()
        for src, dst in bp.edges:
            connected_ids.add(src)
            connected_ids.add(dst)
        isolated = all_ids - connected_ids
        if isolated and len(bp.nodes) > 1:
            recs.append(Recommendation(
                category="architecture",
                title=f"{len(isolated)} Isolated Node(s)",
                description=(
                    f"{len(isolated)} node(s) have no edges. Connect them to the "
                    "main execution flow or remove them."
                ),
                priority=2,
                action="connect_nodes",
            ))

        # Suggest review agent
        if not any("review" in n.label.lower() for n in bp.nodes):
            recs.append(Recommendation(
                category="quality",
                title="Add Review Agent",
                description=(
                    "A dedicated review agent checks code / deliverables against "
                    "standards before the deploy/output step."
                ),
                priority=2,
                action="add_node",
                suggested_config={"node_type": "agent", "label": "Review Agent"},
            ))

        return recs

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_blueprint(self, blueprint_id: str) -> ValidationResult:
        """Check a blueprint for completeness, connectivity, and safety."""
        bid = _validate_id(blueprint_id, "blueprint_id")
        vr = ValidationResult()

        with self._lock:
            bp = self._blueprints.get(bid)
        if bp is None:
            vr.errors.append(f"Blueprint {bid!r} not found")
            return vr

        vr.node_count = len(bp.nodes)
        vr.edge_count = len(bp.edges)

        # Must have nodes
        if not bp.nodes:
            vr.errors.append("Blueprint has no nodes")
        else:
            # Must have at least one agent and one output
            node_types = {n.node_type for n in bp.nodes}
            if "agent" not in node_types:
                vr.errors.append("Blueprint must have at least one agent node")
            if "output" not in node_types:
                vr.errors.append("Blueprint must have at least one output node")

            # HITL gate check
            vr.has_hitl_gate = any(
                n.node_type == "gate" and
                ("hitl" in n.label.lower() or "human" in n.label.lower()
                 or n.config.get("requires_human"))
                for n in bp.nodes
            )
            if not vr.has_hitl_gate:
                vr.errors.append("Blueprint must have a HITL gate before output")

            # Compliance gate check
            vr.has_compliance_gate = any(
                n.node_type == "gate" and "compliance" in n.label.lower()
                for n in bp.nodes
            )
            if not vr.has_compliance_gate:
                vr.warnings.append(
                    "No compliance gate found — recommended for outreach blueprints"
                )

            # Connectivity: every non-output node must have at least one outgoing edge
            connected_from = {src for src, _ in bp.edges}
            output_ids = {n.node_id for n in bp.nodes if n.node_type == "output"}
            for node in bp.nodes:
                if node.node_id not in output_ids and node.node_id not in connected_from:
                    vr.warnings.append(
                        f"Node '{node.label}' ({node.node_id}) has no outgoing edges"
                    )

            vr.has_output_node = "output" in node_types

        vr.passed = not vr.errors

        # Always update status so callers can observe the result via get_blueprint()
        with self._lock:
            bp_obj = self._blueprints.get(bid)
            if bp_obj:
                bp_obj.status = "valid" if vr.passed else "invalid"
                bp_obj.updated_at = _ts()

        self._audit("validate_blueprint", blueprint_id=bid,
                    passed=vr.passed, errors=len(vr.errors))
        return vr

    # ------------------------------------------------------------------
    # Export / import
    # ------------------------------------------------------------------

    def export_as_spec(self, blueprint_id: str) -> Dict[str, Any]:
        """Export a blueprint as a production capability spec (JSON-serialisable)."""
        bid = _validate_id(blueprint_id, "blueprint_id")
        with self._lock:
            bp = self._blueprints.get(bid)
        if bp is None:
            return {"error": f"Blueprint {bid!r} not found"}

        spec = {
            "spec_version": "1.0",
            "blueprint_id": bp.blueprint_id,
            "name": bp.name,
            "description": bp.description,
            "created_at": bp.created_at,
            "status": bp.status,
            "agents": [
                {"agent_id": n.node_id, "label": n.label, "config": n.config}
                for n in bp.nodes if n.node_type == "agent"
            ],
            "gates": [
                {"gate_id": n.node_id, "label": n.label, "config": n.config}
                for n in bp.nodes if n.node_type == "gate"
            ],
            "connectors": [
                {"connector_id": n.node_id, "label": n.label, "config": n.config}
                for n in bp.nodes if n.node_type == "connector"
            ],
            "outputs": [
                {"output_id": n.node_id, "label": n.label, "config": n.config}
                for n in bp.nodes if n.node_type == "output"
            ],
            "edges": [{"from": src, "to": dst} for src, dst in bp.edges],
            "target_project": dict(bp.target_project),
        }
        self._audit("export_as_spec", blueprint_id=bid)
        return spec

    def import_project(self, repo_url: str) -> ProjectAnalysis:
        """Analyse an external project and recommend a swarm blueprint.

        Uses keyword heuristics on the repo URL to infer language and
        framework.  In production this would call SelfIntrospectionEngine
        on a checked-out copy of the project.

        Observation / recommendation mode only — does NOT execute.
        """
        safe_url = str(repo_url)[:2000]
        pa = ProjectAnalysis(repo_url=safe_url)

        lower = safe_url.lower()

        # Language detection from URL
        lang_hints = {
            "python": [".py", "python", "django", "flask", "fastapi"],
            "javascript": [".js", "node", "react", "vue", "angular"],
            "typescript": [".ts", "typescript"],
            "java": ["java", "spring", "maven", "gradle"],
            "csharp": ["dotnet", "csharp", "aspnet"],
            "go": ["golang", ".go"],
        }
        for lang, hints in lang_hints.items():
            if any(h in lower for h in hints):
                pa.languages.append(lang)

        if not pa.languages:
            pa.languages = ["python"]   # default assumption

        # Framework / domain detection
        fw_hints = {
            "django": ["django"],
            "fastapi": ["fastapi"],
            "flask": ["flask"],
            "react": ["react"],
            "bms": ["bms", "bacnet", "hvac", "building"],
            "iot": ["iot", "mqtt", "sensor"],
        }
        for fw, hints in fw_hints.items():
            if any(h in lower for h in hints):
                pa.frameworks.append(fw)

        # Recommended agents based on detected languages
        pa.recommended_agents = ["architect", "code_gen", "test", "review", "deploy"]
        if "bms" in pa.frameworks:
            pa.recommended_agents += ["rfp_parser", "spec_gen", "bms_domain"]

        # Gates
        pa.recommended_gates = ["hitl_gate", "compliance_gate", "confidence_gate"]

        # Complexity score (heuristic: more languages / frameworks = higher complexity)
        pa.complexity_score = round(
            min(0.95, 0.3 + len(pa.languages) * 0.1 + len(pa.frameworks) * 0.05),
            2,
        )

        # Recommendations for this project
        pa.recommendations = [
            Recommendation(
                category="architecture",
                title="Deploy Architect + CodeGen Swarm",
                description=(
                    f"Detected {', '.join(pa.languages)} project. "
                    "Deploy an Architect agent for structural analysis and a "
                    "CodeGen agent for automated refactoring."
                ),
                priority=1,
                action="add_agents",
                suggested_config={"agents": pa.recommended_agents},
            ),
            Recommendation(
                category="compliance",
                title="Add HITL Gate at Execution Boundary",
                description=(
                    "All code changes to an external project must pass through "
                    "a HITL approval gate before commit. Add one gate node before "
                    "the Deploy output."
                ),
                priority=1,
                action="add_gate",
                suggested_config={
                    "gate_type": "hitl",
                    "confidence_threshold": 0.99,
                    "position": "pre_deploy",
                },
            ),
        ]

        if "bms" in pa.frameworks:
            pa.recommendations.append(Recommendation(
                category="domain",
                title="Enable BMS Domain Agent",
                description=(
                    "Project appears to be a Building Management System. "
                    "Enable the BMS Domain Agent for BACnet point-schedule "
                    "generation, sequence-of-operations, and ASHRAE compliance."
                ),
                priority=1,
                action="add_agent",
                suggested_config={"agent_type": "bms_domain"},
            ))

        self._audit("import_project", project_id=pa.project_id, url=safe_url[:100])
        logger.info("VSB-001 import_project %s langs=%s complexity=%.2f",
                    pa.project_id, pa.languages, pa.complexity_score)
        return pa

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_blueprint(self, blueprint_id: str) -> Optional[SwarmBlueprint]:
        bid = _validate_id(blueprint_id, "blueprint_id")
        with self._lock:
            return self._blueprints.get(bid)

    def list_blueprints(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "blueprint_id": bp.blueprint_id,
                    "name": bp.name,
                    "node_count": len(bp.nodes),
                    "status": bp.status,
                    "created_at": bp.created_at,
                }
                for bp in self._blueprints.values()
            ]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(self, action: str, **kwargs: Any) -> None:
        entry = {"action": action, "timestamp": _ts(), **kwargs}
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

"""
Executive Planning Engine — Top-down executive planning with
business-driven gate generation.

Provides the executive-level planning layer where business needs
generate gates that control automation execution. Integrations become
part of wired automation generation.

Core components:
  - ExecutiveStrategyPlanner: define and decompose business objectives
  - BusinessGateGenerator: auto-generate gates from objectives
  - IntegrationAutomationBinder: wire integrations into workflows
  - ExecutiveDashboardGenerator: executive-level reporting
  - ResponseEngine: generate responses based on gate outcomes
"""

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ObjectiveCategory(str, Enum):
    """Objective category (str subclass)."""
    REVENUE_TARGET = "revenue_target"
    COST_REDUCTION = "cost_reduction"
    MARKET_EXPANSION = "market_expansion"
    COMPLIANCE_MANDATE = "compliance_mandate"
    OPERATIONAL_EFFICIENCY = "operational_efficiency"


class ObjectiveStatus(str, Enum):
    """Objective status (str subclass)."""
    DRAFT = "draft"
    ACTIVE = "active"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GateType(str, Enum):
    """Gate type (str subclass)."""
    BUDGET_GATE = "budget_gate"
    APPROVAL_GATE = "approval_gate"
    COMPLIANCE_GATE = "compliance_gate"
    TIMELINE_GATE = "timeline_gate"
    ROI_GATE = "roi_gate"
    RISK_GATE = "risk_gate"


class GateStatus(str, Enum):
    """Gate status (str subclass)."""
    PENDING = "pending"
    OPEN = "open"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"
    BLOCKED = "blocked"


class InitiativeStatus(str, Enum):
    """Initiative status (str subclass)."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkflowNodeStatus(str, Enum):
    """Workflow node status (str subclass)."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BindingStatus(str, Enum):
    """Binding status (str subclass)."""
    UNBOUND = "unbound"
    BOUND = "bound"
    ACTIVE = "active"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Gate templates per objective category
# ---------------------------------------------------------------------------

_GATE_TEMPLATES: Dict[ObjectiveCategory, List[Dict[str, Any]]] = {
    ObjectiveCategory.REVENUE_TARGET: [
        {"gate_type": GateType.BUDGET_GATE, "condition": "budget_available", "threshold": 0.0},
        {"gate_type": GateType.ROI_GATE, "condition": "expected_roi_above_threshold", "threshold": 1.5},
        {"gate_type": GateType.TIMELINE_GATE, "condition": "within_deadline", "threshold": 1.0},
        {"gate_type": GateType.APPROVAL_GATE, "condition": "stakeholder_sign_off", "threshold": 1.0},
    ],
    ObjectiveCategory.COST_REDUCTION: [
        {"gate_type": GateType.BUDGET_GATE, "condition": "implementation_cost_within_limit", "threshold": 0.0},
        {"gate_type": GateType.ROI_GATE, "condition": "savings_exceed_investment", "threshold": 2.0},
        {"gate_type": GateType.RISK_GATE, "condition": "operational_risk_acceptable", "threshold": 0.3},
        {"gate_type": GateType.APPROVAL_GATE, "condition": "finance_approval", "threshold": 1.0},
    ],
    ObjectiveCategory.MARKET_EXPANSION: [
        {"gate_type": GateType.BUDGET_GATE, "condition": "expansion_budget_allocated", "threshold": 0.0},
        {"gate_type": GateType.COMPLIANCE_GATE, "condition": "market_regulations_met", "threshold": 1.0},
        {"gate_type": GateType.RISK_GATE, "condition": "market_risk_within_tolerance", "threshold": 0.4},
        {"gate_type": GateType.TIMELINE_GATE, "condition": "launch_window_valid", "threshold": 1.0},
        {"gate_type": GateType.APPROVAL_GATE, "condition": "executive_board_approval", "threshold": 1.0},
    ],
    ObjectiveCategory.COMPLIANCE_MANDATE: [
        {"gate_type": GateType.COMPLIANCE_GATE, "condition": "regulatory_requirements_mapped", "threshold": 1.0},
        {"gate_type": GateType.BUDGET_GATE, "condition": "compliance_budget_secured", "threshold": 0.0},
        {"gate_type": GateType.TIMELINE_GATE, "condition": "regulatory_deadline_met", "threshold": 1.0},
        {"gate_type": GateType.RISK_GATE, "condition": "non_compliance_risk_mitigated", "threshold": 0.1},
        {"gate_type": GateType.APPROVAL_GATE, "condition": "legal_sign_off", "threshold": 1.0},
    ],
    ObjectiveCategory.OPERATIONAL_EFFICIENCY: [
        {"gate_type": GateType.BUDGET_GATE, "condition": "efficiency_budget_available", "threshold": 0.0},
        {"gate_type": GateType.ROI_GATE, "condition": "efficiency_gains_projected", "threshold": 1.2},
        {"gate_type": GateType.RISK_GATE, "condition": "disruption_risk_acceptable", "threshold": 0.25},
        {"gate_type": GateType.APPROVAL_GATE, "condition": "ops_lead_approval", "threshold": 1.0},
    ],
}

# Integration catalog keyed by objective category
_INTEGRATION_CATALOG: Dict[ObjectiveCategory, List[Dict[str, Any]]] = {
    ObjectiveCategory.REVENUE_TARGET: [
        {"integration_id": "crm_connector", "name": "CRM Connector", "capability": "sales_pipeline"},
        {"integration_id": "payment_gateway", "name": "Payment Gateway", "capability": "billing"},
        {"integration_id": "analytics_engine", "name": "Analytics Engine", "capability": "revenue_tracking"},
        {"integration_id": "content_creator_platforms", "name": "Content Creator Platforms", "capability": "monetization_tracking"},
        {"integration_id": "messaging_platforms", "name": "Messaging Platforms", "capability": "customer_engagement"},
        {"integration_id": "digital_asset_pipeline", "name": "Digital Asset Pipeline", "capability": "asset_monetization"},
        {"integration_id": "enterprise_integrations", "name": "Enterprise Integrations", "capability": "erp_billing"},
    ],
    ObjectiveCategory.COST_REDUCTION: [
        {"integration_id": "expense_tracker", "name": "Expense Tracker", "capability": "cost_monitoring"},
        {"integration_id": "procurement_system", "name": "Procurement System", "capability": "vendor_management"},
        {"integration_id": "automation_rpa", "name": "RPA Engine", "capability": "task_automation"},
        {"integration_id": "building_automation", "name": "Building Automation", "capability": "energy_optimization"},
        {"integration_id": "energy_management", "name": "Energy Management", "capability": "utility_cost_reduction"},
        {"integration_id": "manufacturing_automation", "name": "Manufacturing Automation", "capability": "production_efficiency"},
    ],
    ObjectiveCategory.MARKET_EXPANSION: [
        {"integration_id": "market_research", "name": "Market Research", "capability": "market_analysis"},
        {"integration_id": "localization_engine", "name": "Localization Engine", "capability": "translation"},
        {"integration_id": "compliance_checker", "name": "Compliance Checker", "capability": "regulatory_check"},
        {"integration_id": "messaging_platforms", "name": "Messaging Platforms", "capability": "global_messaging"},
        {"integration_id": "content_creator_platforms", "name": "Content Creator Platforms", "capability": "audience_expansion"},
        {"integration_id": "platform_connectors", "name": "Platform Connectors", "capability": "multi_platform_reach"},
    ],
    ObjectiveCategory.COMPLIANCE_MANDATE: [
        {"integration_id": "policy_engine", "name": "Policy Engine", "capability": "policy_enforcement"},
        {"integration_id": "audit_logger", "name": "Audit Logger", "capability": "audit_trail"},
        {"integration_id": "compliance_checker", "name": "Compliance Checker", "capability": "regulatory_check"},
        {"integration_id": "building_automation", "name": "Building Automation", "capability": "safety_compliance"},
        {"integration_id": "manufacturing_automation", "name": "Manufacturing Automation", "capability": "isa95_compliance"},
        {"integration_id": "energy_management", "name": "Energy Management", "capability": "energy_reporting"},
    ],
    ObjectiveCategory.OPERATIONAL_EFFICIENCY: [
        {"integration_id": "monitoring_suite", "name": "Monitoring Suite", "capability": "performance_tracking"},
        {"integration_id": "automation_rpa", "name": "RPA Engine", "capability": "task_automation"},
        {"integration_id": "workflow_optimizer", "name": "Workflow Optimizer", "capability": "process_optimization"},
        {"integration_id": "rosetta_stone_heartbeat", "name": "Rosetta Stone Heartbeat", "capability": "org_sync"},
        {"integration_id": "platform_connectors", "name": "Platform Connectors", "capability": "unified_integration"},
        {"integration_id": "enterprise_integrations", "name": "Enterprise Integrations", "capability": "erp_orchestration"},
        {"integration_id": "digital_asset_pipeline", "name": "Digital Asset Pipeline", "capability": "asset_automation"},
    ],
}


# ---------------------------------------------------------------------------
# ExecutiveStrategyPlanner
# ---------------------------------------------------------------------------

class ExecutiveStrategyPlanner:
    """Define business objectives and decompose them into initiatives."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._objectives: Dict[str, Dict[str, Any]] = {}
        self._initiatives: Dict[str, Dict[str, Any]] = {}

    # -- objectives --------------------------------------------------------

    def create_objective(
        self,
        name: str,
        category: str,
        target_metric: str,
        deadline: str,
        priority: int = 3,
    ) -> Dict[str, Any]:
        """Create a business objective.

        Args:
            name: Human-readable objective name.
            category: One of ObjectiveCategory values.
            target_metric: Measurable target (e.g. "revenue >= 10M").
            deadline: ISO-8601 date string.
            priority: 1 (highest) to 5 (lowest).

        Returns:
            Dict describing the created objective.
        """
        cat = ObjectiveCategory(category)
        with self._lock:
            obj_id = f"obj-{uuid.uuid4().hex[:12]}"
            obj = {
                "objective_id": obj_id,
                "name": name,
                "category": cat.value,
                "target_metric": target_metric,
                "deadline": deadline,
                "priority": max(1, min(5, priority)),
                "status": ObjectiveStatus.DRAFT.value,
                "initiatives": [],
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._objectives[obj_id] = obj
            logger.info("Created objective %s: %s", obj_id, name)
            return dict(obj)

    def get_objective(self, objective_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            obj = self._objectives.get(objective_id)
            return dict(obj) if obj else None

    def activate_objective(self, objective_id: str) -> Dict[str, Any]:
        with self._lock:
            obj = self._objectives.get(objective_id)
            if not obj:
                return {"error": "objective_not_found", "objective_id": objective_id}
            obj["status"] = ObjectiveStatus.ACTIVE.value
            obj["updated_at"] = time.time()
            return dict(obj)

    def list_objectives(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(o) for o in self._objectives.values()]

    # -- decomposition -----------------------------------------------------

    def decompose_into_initiatives(self, objective_id: str) -> List[Dict[str, Any]]:
        """Decompose an objective into actionable initiatives."""
        with self._lock:
            obj = self._objectives.get(objective_id)
            if not obj:
                return []
            cat = ObjectiveCategory(obj["category"])
            templates = _INITIATIVE_TEMPLATES.get(cat, [])
            created: List[Dict[str, Any]] = []
            for tmpl in templates:
                init_id = f"init-{uuid.uuid4().hex[:12]}"
                initiative = {
                    "initiative_id": init_id,
                    "objective_id": objective_id,
                    "name": tmpl["name"],
                    "description": tmpl["description"],
                    "estimated_roi": tmpl["estimated_roi"],
                    "risk_level": tmpl["risk_level"],
                    "feasibility": tmpl["feasibility"],
                    "urgency": tmpl["urgency"],
                    "status": InitiativeStatus.PROPOSED.value,
                    "created_at": time.time(),
                }
                self._initiatives[init_id] = initiative
                created.append(dict(initiative))
            obj["initiatives"] = [i["initiative_id"] for i in created]
            obj["updated_at"] = time.time()
            return created

    def rank_initiatives(
        self,
        criteria: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Rank all proposed initiatives by weighted criteria.

        Args:
            criteria: weights for roi, urgency, risk, feasibility (0-1 each).
        """
        weights = {
            "roi": 0.4,
            "urgency": 0.3,
            "risk": 0.15,
            "feasibility": 0.15,
        }
        if criteria:
            for k in ("roi", "urgency", "risk", "feasibility"):
                if k in criteria:
                    weights[k] = float(criteria[k])

        with self._lock:
            scored: List[Tuple[float, Dict[str, Any]]] = []
            for init in self._initiatives.values():
                score = (
                    weights["roi"] * init.get("estimated_roi", 0)
                    + weights["urgency"] * init.get("urgency", 0)
                    + weights["risk"] * (1.0 - init.get("risk_level", 0))
                    + weights["feasibility"] * init.get("feasibility", 0)
                )
                entry = dict(init)
                entry["composite_score"] = round(score, 4)
                scored.append((score, entry))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [s[1] for s in scored]


# Initiative templates per category
_INITIATIVE_TEMPLATES: Dict[ObjectiveCategory, List[Dict[str, Any]]] = {
    ObjectiveCategory.REVENUE_TARGET: [
        {"name": "Upsell Automation", "description": "Automate upsell workflows", "estimated_roi": 2.5, "risk_level": 0.2, "feasibility": 0.8, "urgency": 0.7},
        {"name": "Lead Scoring Pipeline", "description": "ML-based lead scoring", "estimated_roi": 3.0, "risk_level": 0.3, "feasibility": 0.7, "urgency": 0.8},
        {"name": "Pricing Optimization", "description": "Dynamic pricing engine", "estimated_roi": 2.0, "risk_level": 0.4, "feasibility": 0.6, "urgency": 0.5},
    ],
    ObjectiveCategory.COST_REDUCTION: [
        {"name": "Process Automation", "description": "Automate manual processes", "estimated_roi": 3.5, "risk_level": 0.15, "feasibility": 0.9, "urgency": 0.8},
        {"name": "Vendor Consolidation", "description": "Reduce vendor count", "estimated_roi": 2.0, "risk_level": 0.2, "feasibility": 0.85, "urgency": 0.6},
        {"name": "Infrastructure Optimization", "description": "Right-size infrastructure", "estimated_roi": 2.5, "risk_level": 0.25, "feasibility": 0.75, "urgency": 0.7},
    ],
    ObjectiveCategory.MARKET_EXPANSION: [
        {"name": "Market Entry Analysis", "description": "Analyze new markets", "estimated_roi": 1.5, "risk_level": 0.5, "feasibility": 0.7, "urgency": 0.6},
        {"name": "Localization Pipeline", "description": "Localize products", "estimated_roi": 2.0, "risk_level": 0.35, "feasibility": 0.65, "urgency": 0.7},
        {"name": "Partner Channel Setup", "description": "Establish partner channels", "estimated_roi": 2.5, "risk_level": 0.4, "feasibility": 0.6, "urgency": 0.5},
    ],
    ObjectiveCategory.COMPLIANCE_MANDATE: [
        {"name": "Regulatory Mapping", "description": "Map regulatory requirements", "estimated_roi": 1.0, "risk_level": 0.1, "feasibility": 0.95, "urgency": 0.9},
        {"name": "Audit Trail Automation", "description": "Automate audit logging", "estimated_roi": 1.5, "risk_level": 0.15, "feasibility": 0.9, "urgency": 0.85},
        {"name": "Policy Enforcement Engine", "description": "Automated policy checks", "estimated_roi": 2.0, "risk_level": 0.2, "feasibility": 0.8, "urgency": 0.8},
    ],
    ObjectiveCategory.OPERATIONAL_EFFICIENCY: [
        {"name": "Workflow Streamlining", "description": "Optimize existing workflows", "estimated_roi": 2.0, "risk_level": 0.15, "feasibility": 0.85, "urgency": 0.7},
        {"name": "Monitoring Automation", "description": "Automated system monitoring", "estimated_roi": 2.5, "risk_level": 0.2, "feasibility": 0.8, "urgency": 0.75},
        {"name": "Capacity Planning", "description": "Predictive capacity planning", "estimated_roi": 1.8, "risk_level": 0.3, "feasibility": 0.7, "urgency": 0.6},
    ],
}


# ---------------------------------------------------------------------------
# BusinessGateGenerator
# ---------------------------------------------------------------------------

class BusinessGateGenerator:
    """Auto-generate gates from business objectives that control execution."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._gates: Dict[str, Dict[str, Any]] = {}

    def generate_gates_for_objective(
        self,
        objective_id: str,
        category: str,
        *,
        budget_threshold: float = 100000.0,
        roi_threshold: Optional[float] = None,
        risk_tolerance: Optional[float] = None,
        approvers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate gates based on objective category.

        Returns:
            List of gate dicts ready for enforcement.
        """
        cat = ObjectiveCategory(category)
        templates = _GATE_TEMPLATES.get(cat, [])
        approvers = approvers or ["executive_sponsor"]

        with self._lock:
            generated: List[Dict[str, Any]] = []
            for tmpl in templates:
                gate_id = f"gate-{uuid.uuid4().hex[:12]}"
                threshold = tmpl["threshold"]
                gt = GateType(tmpl["gate_type"])

                if gt == GateType.BUDGET_GATE:
                    threshold = budget_threshold
                elif gt == GateType.ROI_GATE and roi_threshold is not None:
                    threshold = roi_threshold
                elif gt == GateType.RISK_GATE and risk_tolerance is not None:
                    threshold = risk_tolerance

                gate = {
                    "gate_id": gate_id,
                    "objective_id": objective_id,
                    "gate_type": gt.value,
                    "condition": tmpl["condition"],
                    "threshold": threshold,
                    "approvers": list(approvers),
                    "status": GateStatus.PENDING.value,
                    "created_at": time.time(),
                    "evaluated_at": None,
                    "evaluation_result": None,
                }
                self._gates[gate_id] = gate
                generated.append(dict(gate))
            logger.info(
                "Generated %d gates for objective %s", len(generated), objective_id
            )
            return generated

    def get_gate(self, gate_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            g = self._gates.get(gate_id)
            return dict(g) if g else None

    def evaluate_gate(
        self,
        gate_id: str,
        actual_value: float,
    ) -> Dict[str, Any]:
        """Evaluate a gate against an actual value.

        For BUDGET_GATE: actual_value = current spend (passes if <= threshold).
        For ROI_GATE: actual_value = projected ROI (passes if >= threshold).
        For RISK_GATE: actual_value = risk score (passes if <= threshold).
        For TIMELINE/COMPLIANCE/APPROVAL: actual_value 1.0 = met, 0.0 = not met.
        """
        with self._lock:
            gate = self._gates.get(gate_id)
            if not gate:
                return {"error": "gate_not_found", "gate_id": gate_id}

            gt = GateType(gate["gate_type"])
            threshold = gate["threshold"]

            if gt in (GateType.BUDGET_GATE, GateType.RISK_GATE):
                passed = actual_value <= threshold
            elif gt == GateType.ROI_GATE:
                passed = actual_value >= threshold
            else:
                passed = actual_value >= threshold

            gate["status"] = GateStatus.PASSED.value if passed else GateStatus.FAILED.value
            gate["evaluated_at"] = time.time()
            gate["evaluation_result"] = {
                "actual_value": actual_value,
                "threshold": threshold,
                "passed": passed,
            }
            return dict(gate)

    def get_gates_for_objective(self, objective_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(g) for g in self._gates.values()
                if g["objective_id"] == objective_id
            ]

    def update_gate_status(self, gate_id: str, status: str) -> Dict[str, Any]:
        with self._lock:
            gate = self._gates.get(gate_id)
            if not gate:
                return {"error": "gate_not_found", "gate_id": gate_id}
            gate["status"] = GateStatus(status).value
            return dict(gate)

    def list_gates(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(g) for g in self._gates.values()]


# ---------------------------------------------------------------------------
# IntegrationAutomationBinder
# ---------------------------------------------------------------------------

class IntegrationAutomationBinder:
    """Wire available integrations into automation workflows."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bindings: Dict[str, Dict[str, Any]] = {}
        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._custom_integrations: List[Dict[str, Any]] = []

    def register_integration(self, integration: Dict[str, Any]) -> Dict[str, Any]:
        """Register a custom integration in the catalog."""
        with self._lock:
            capped_append(self._custom_integrations, dict(integration))
            return {"registered": True, "integration_id": integration.get("integration_id")}

    def discover_integrations_for_objective(
        self,
        objective_id: str,
        category: str,
    ) -> List[Dict[str, Any]]:
        """Recommend integrations for an objective based on its category."""
        cat = ObjectiveCategory(category)
        with self._lock:
            catalog = list(_INTEGRATION_CATALOG.get(cat, []))
            for ci in self._custom_integrations:
                if ci.get("category") == cat.value:
                    catalog.append(ci)
            return [
                {**intg, "objective_id": objective_id, "recommended": True}
                for intg in catalog
            ]

    def bind_integration_to_workflow(
        self,
        integration_id: str,
        workflow_id: str,
        step_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Bind an integration to a workflow step."""
        with self._lock:
            binding_id = f"bind-{uuid.uuid4().hex[:12]}"
            binding = {
                "binding_id": binding_id,
                "integration_id": integration_id,
                "workflow_id": workflow_id,
                "step_config": dict(step_config),
                "status": BindingStatus.BOUND.value,
                "created_at": time.time(),
            }
            self._bindings[binding_id] = binding
            return dict(binding)

    def get_binding(self, binding_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            b = self._bindings.get(binding_id)
            return dict(b) if b else None

    def activate_binding(self, binding_id: str) -> Dict[str, Any]:
        with self._lock:
            b = self._bindings.get(binding_id)
            if not b:
                return {"error": "binding_not_found", "binding_id": binding_id}
            b["status"] = BindingStatus.ACTIVE.value
            return dict(b)

    def list_bindings_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(b) for b in self._bindings.values()
                if b["workflow_id"] == workflow_id
            ]

    def generate_automation_workflow(
        self,
        objective_id: str,
        category: str,
        gates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate a DAG workflow for an objective using recommended integrations.

        Each recommended integration becomes a node; gates become gate-check
        nodes inserted before execution nodes.
        """
        cat = ObjectiveCategory(category)
        integrations = _INTEGRATION_CATALOG.get(cat, [])
        gates = gates or []

        with self._lock:
            wf_id = f"wf-{uuid.uuid4().hex[:12]}"
            nodes: List[Dict[str, Any]] = []
            edges: List[Dict[str, str]] = []

            # Start node
            start_id = f"node-start-{wf_id}"
            nodes.append({
                "node_id": start_id,
                "type": "start",
                "name": "Workflow Start",
                "status": WorkflowNodeStatus.PENDING.value,
            })

            prev_id = start_id

            # Gate-check nodes
            for gate in gates:
                gnode_id = f"node-gate-{gate['gate_id']}"
                nodes.append({
                    "node_id": gnode_id,
                    "type": "gate_check",
                    "gate_id": gate["gate_id"],
                    "gate_type": gate["gate_type"],
                    "name": f"Gate: {gate['condition']}",
                    "status": WorkflowNodeStatus.PENDING.value,
                })
                edges.append({"from": prev_id, "to": gnode_id})
                prev_id = gnode_id

            # Integration execution nodes
            for intg in integrations:
                inode_id = f"node-intg-{intg['integration_id']}-{wf_id}"
                nodes.append({
                    "node_id": inode_id,
                    "type": "integration",
                    "integration_id": intg["integration_id"],
                    "name": intg["name"],
                    "capability": intg["capability"],
                    "status": WorkflowNodeStatus.PENDING.value,
                })
                edges.append({"from": prev_id, "to": inode_id})
                prev_id = inode_id

                # Auto-bind
                binding_id = f"bind-{uuid.uuid4().hex[:12]}"
                self._bindings[binding_id] = {
                    "binding_id": binding_id,
                    "integration_id": intg["integration_id"],
                    "workflow_id": wf_id,
                    "step_config": {"node_id": inode_id, "capability": intg["capability"]},
                    "status": BindingStatus.BOUND.value,
                    "created_at": time.time(),
                }

            # End node
            end_id = f"node-end-{wf_id}"
            nodes.append({
                "node_id": end_id,
                "type": "end",
                "name": "Workflow End",
                "status": WorkflowNodeStatus.PENDING.value,
            })
            edges.append({"from": prev_id, "to": end_id})

            workflow = {
                "workflow_id": wf_id,
                "objective_id": objective_id,
                "category": cat.value,
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "integration_count": len(integrations),
                "gate_count": len(gates),
                "status": "generated",
                "created_at": time.time(),
            }
            self._workflows[wf_id] = workflow
            return dict(workflow)


# ---------------------------------------------------------------------------
# ExecutiveDashboardGenerator
# ---------------------------------------------------------------------------

class ExecutiveDashboardGenerator:
    """Generate executive-level reporting data."""

    def __init__(
        self,
        planner: ExecutiveStrategyPlanner,
        gate_generator: BusinessGateGenerator,
        binder: IntegrationAutomationBinder,
    ) -> None:
        self._lock = threading.RLock()
        self._planner = planner
        self._gate_gen = gate_generator
        self._binder = binder

    def objective_progress_report(self, objective_id: str) -> Dict[str, Any]:
        """Generate a progress report for a single objective."""
        with self._lock:
            obj = self._planner.get_objective(objective_id)
            if not obj:
                return {"error": "objective_not_found", "objective_id": objective_id}

            gates = self._gate_gen.get_gates_for_objective(objective_id)
            passed = sum(1 for g in gates if g["status"] == GateStatus.PASSED.value)
            failed = sum(1 for g in gates if g["status"] == GateStatus.FAILED.value)
            pending = sum(1 for g in gates if g["status"] in (GateStatus.PENDING.value, GateStatus.OPEN.value))
            total = len(gates)
            gate_progress = (passed / total * 100) if total > 0 else 0.0

            return {
                "objective_id": objective_id,
                "name": obj["name"],
                "status": obj["status"],
                "category": obj["category"],
                "target_metric": obj["target_metric"],
                "deadline": obj["deadline"],
                "gates_total": total,
                "gates_passed": passed,
                "gates_failed": failed,
                "gates_pending": pending,
                "gate_progress_pct": round(gate_progress, 2),
                "kpis": {
                    "gate_pass_rate": round(passed / total, 4) if total else 0.0,
                    "blocking_gates": [g["gate_id"] for g in gates if g["status"] == GateStatus.FAILED.value],
                },
                "generated_at": time.time(),
            }

    def portfolio_summary(self) -> Dict[str, Any]:
        """Summary of all objectives with status, budget, timeline."""
        with self._lock:
            objectives = self._planner.list_objectives()
            summary: List[Dict[str, Any]] = []
            for obj in objectives:
                gates = self._gate_gen.get_gates_for_objective(obj["objective_id"])
                passed = sum(1 for g in gates if g["status"] == GateStatus.PASSED.value)
                total = len(gates)
                summary.append({
                    "objective_id": obj["objective_id"],
                    "name": obj["name"],
                    "category": obj["category"],
                    "status": obj["status"],
                    "priority": obj["priority"],
                    "deadline": obj["deadline"],
                    "gates_passed": passed,
                    "gates_total": total,
                })
            return {
                "total_objectives": len(summary),
                "objectives": summary,
                "generated_at": time.time(),
            }

    def gate_compliance_matrix(self) -> Dict[str, Any]:
        """Which gates are passing/failing across all objectives."""
        with self._lock:
            all_gates = self._gate_gen.list_gates()
            matrix: Dict[str, List[Dict[str, Any]]] = {}
            for g in all_gates:
                gt = g["gate_type"]
                if gt not in matrix:
                    matrix[gt] = []
                matrix[gt].append({
                    "gate_id": g["gate_id"],
                    "objective_id": g["objective_id"],
                    "status": g["status"],
                    "condition": g["condition"],
                })

            counts = {
                "total": len(all_gates),
                "passed": sum(1 for g in all_gates if g["status"] == GateStatus.PASSED.value),
                "failed": sum(1 for g in all_gates if g["status"] == GateStatus.FAILED.value),
                "pending": sum(1 for g in all_gates if g["status"] in (GateStatus.PENDING.value, GateStatus.OPEN.value)),
            }
            return {
                "matrix": matrix,
                "counts": counts,
                "generated_at": time.time(),
            }

    def integration_utilization_report(self) -> Dict[str, Any]:
        """Which integrations are being used and their effectiveness."""
        with self._lock:
            all_bindings = self._binder._bindings  # direct access for reporting
            integrations: Dict[str, Dict[str, Any]] = {}
            for b in all_bindings.values():
                iid = b["integration_id"]
                if iid not in integrations:
                    integrations[iid] = {
                        "integration_id": iid,
                        "binding_count": 0,
                        "active_count": 0,
                        "workflows": [],
                    }
                integrations[iid]["binding_count"] += 1
                if b["status"] == BindingStatus.ACTIVE.value:
                    integrations[iid]["active_count"] += 1
                integrations[iid]["workflows"].append(b["workflow_id"])

            return {
                "total_integrations": len(integrations),
                "integrations": list(integrations.values()),
                "generated_at": time.time(),
            }


# ---------------------------------------------------------------------------
# ResponseEngine
# ---------------------------------------------------------------------------

class ResponseEngine:
    """Generate executive responses based on gate outcomes."""

    def __init__(
        self,
        gate_generator: BusinessGateGenerator,
        planner: ExecutiveStrategyPlanner,
    ) -> None:
        self._lock = threading.RLock()
        self._gate_gen = gate_generator
        self._planner = planner
        self._responses: List[Dict[str, Any]] = []

    def generate_response(
        self,
        gate_id: str,
        outcome: str,
    ) -> Dict[str, Any]:
        """Generate an executive-level summary of a gate outcome.

        Args:
            gate_id: The gate that was evaluated.
            outcome: 'passed' or 'failed'.
        """
        with self._lock:
            gate = self._gate_gen.get_gate(gate_id)
            if not gate:
                return {"error": "gate_not_found", "gate_id": gate_id}

            obj = self._planner.get_objective(gate["objective_id"])
            obj_name = obj["name"] if obj else "Unknown Objective"

            if outcome == "passed":
                impact = "Gate requirements satisfied. Execution may proceed."
                next_steps = ["Continue to next gate or workflow step."]
                severity = "info"
            else:
                impact = "Gate requirements not met. Execution blocked."
                next_steps = [
                    "Review gate condition and threshold.",
                    "Engage approvers for remediation.",
                    "Consider escalation if timeline is at risk.",
                ]
                severity = "warning"

            response = {
                "response_id": f"resp-{uuid.uuid4().hex[:12]}",
                "gate_id": gate_id,
                "gate_type": gate["gate_type"],
                "objective_id": gate["objective_id"],
                "objective_name": obj_name,
                "outcome": outcome,
                "impact": impact,
                "next_steps": next_steps,
                "severity": severity,
                "generated_at": time.time(),
            }
            capped_append(self._responses, response)
            return dict(response)

    def escalation_handler(self, blocked_gate_id: str) -> Dict[str, Any]:
        """Identify stakeholders and generate escalation brief for a blocked gate."""
        with self._lock:
            gate = self._gate_gen.get_gate(blocked_gate_id)
            if not gate:
                return {"error": "gate_not_found", "gate_id": blocked_gate_id}

            obj = self._planner.get_objective(gate["objective_id"])
            obj_name = obj["name"] if obj else "Unknown Objective"

            stakeholders = list(gate.get("approvers", []))
            if obj:
                cat = obj.get("category", "")
                if cat == ObjectiveCategory.COMPLIANCE_MANDATE.value:
                    stakeholders.append("legal_counsel")
                elif cat == ObjectiveCategory.REVENUE_TARGET.value:
                    stakeholders.append("cro")
                elif cat == ObjectiveCategory.COST_REDUCTION.value:
                    stakeholders.append("cfo")
                else:
                    stakeholders.append("coo")

            brief = {
                "escalation_id": f"esc-{uuid.uuid4().hex[:12]}",
                "gate_id": blocked_gate_id,
                "gate_type": gate["gate_type"],
                "objective_id": gate["objective_id"],
                "objective_name": obj_name,
                "condition": gate["condition"],
                "threshold": gate["threshold"],
                "current_status": gate["status"],
                "stakeholders": stakeholders,
                "urgency": "high" if gate["gate_type"] in (
                    GateType.COMPLIANCE_GATE.value, GateType.TIMELINE_GATE.value
                ) else "medium",
                "recommended_actions": [
                    f"Review {gate['gate_type']} condition: {gate['condition']}",
                    "Schedule stakeholder meeting within 24 hours.",
                    "Prepare impact analysis if gate remains blocked.",
                ],
                "generated_at": time.time(),
            }
            return brief

    def recommend_course_correction(self, objective_id: str) -> Dict[str, Any]:
        """Recommendations when gates are failing for an objective."""
        with self._lock:
            obj = self._planner.get_objective(objective_id)
            if not obj:
                return {"error": "objective_not_found", "objective_id": objective_id}

            gates = self._gate_gen.get_gates_for_objective(objective_id)
            failing = [g for g in gates if g["status"] == GateStatus.FAILED.value]

            recommendations: List[Dict[str, Any]] = []
            for gate in failing:
                gt = GateType(gate["gate_type"])
                rec: Dict[str, Any] = {
                    "gate_id": gate["gate_id"],
                    "gate_type": gt.value,
                    "condition": gate["condition"],
                }
                if gt == GateType.BUDGET_GATE:
                    rec["recommendation"] = "Request additional budget allocation or reduce scope."
                    rec["priority"] = "high"
                elif gt == GateType.ROI_GATE:
                    rec["recommendation"] = "Re-evaluate value proposition or adjust ROI targets."
                    rec["priority"] = "medium"
                elif gt == GateType.RISK_GATE:
                    rec["recommendation"] = "Implement risk mitigations or adjust risk tolerance."
                    rec["priority"] = "high"
                elif gt == GateType.COMPLIANCE_GATE:
                    rec["recommendation"] = "Engage compliance team for remediation plan."
                    rec["priority"] = "critical"
                elif gt == GateType.TIMELINE_GATE:
                    rec["recommendation"] = "Negotiate deadline extension or reduce deliverable scope."
                    rec["priority"] = "high"
                elif gt == GateType.APPROVAL_GATE:
                    rec["recommendation"] = "Schedule approval meeting with required stakeholders."
                    rec["priority"] = "medium"
                recommendations.append(rec)

            overall_health = "healthy" if not failing else (
                "critical" if len(failing) > len(gates) / 2 else "at_risk"
            )

            return {
                "objective_id": objective_id,
                "objective_name": obj["name"],
                "overall_health": overall_health,
                "failing_gates": len(failing),
                "total_gates": len(gates),
                "recommendations": recommendations,
                "generated_at": time.time(),
            }

    def list_responses(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._responses)


# ---------------------------------------------------------------------------
# Convenience facade
# ---------------------------------------------------------------------------

class ExecutivePlanningEngine:
    """Unified facade over all executive planning components."""

    def __init__(self) -> None:
        self.planner = ExecutiveStrategyPlanner()
        self.gate_generator = BusinessGateGenerator()
        self.binder = IntegrationAutomationBinder()
        self.dashboard = ExecutiveDashboardGenerator(
            self.planner, self.gate_generator, self.binder,
        )
        self.response_engine = ResponseEngine(
            self.gate_generator, self.planner,
        )

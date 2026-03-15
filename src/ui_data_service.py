"""
UI Data Service - Provides data for both System and Human interfaces
Implements the UI Data Schema from the architecture spec
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemStateSnapshot:
    """Real-time system state"""
    timestamp: str
    phase: str
    confidence: float
    authority_band: str
    murphy_index: float
    active_gate_count: int
    swarm_count: int
    execution_allowed: bool


@dataclass
class GateNode:
    """Single gate in the graph"""
    gate_id: str
    type: str
    target: str
    status: str  # "blocking", "satisfied", "pending"
    trigger: str
    risk_reduction: float
    satisfied: bool = False


@dataclass
class ConfidenceBreakdown:
    """Detailed confidence components"""
    confidence: float
    generative_adequacy: float
    deterministic_grounding: float
    weights: Dict[str, float]
    drivers: List[Dict[str, Any]]


@dataclass
class ExecutionPacket:
    """Execution packet status"""
    packet_id: str
    status: str  # "compiled", "expired", "executing"
    allowed_actions: int
    sealed_at: str
    expired_at: Optional[str]


class UIDataService:
    """
    Central service for UI data
    Both System and Human interfaces consume from here
    """

    # ── Module-level constants for phase FSM ───────────────────────────────
    _DTYPE_MAP: Dict[str, Any] = {
        'int': int,
        'float': (int, float),
        'str': str,
        'bool': bool,
        'list': list,
        'dict': dict,
    }

    _PHASE_TRANSITIONS: Dict[str, List[str]] = {
        "Expand":    ["Type", "Constrain"],
        "Type":      ["Enumerate", "Constrain"],
        "Enumerate": ["Constrain"],
        "Constrain": ["Collapse", "Expand"],
        "Collapse":  ["Bind", "Constrain"],
        "Bind":      ["Execute", "Collapse"],
        "Execute":   ["Complete", "Bind"],
    }

    def __init__(self, mfgc_system):
        self.system = mfgc_system
        self.event_log = []
        self.max_events = 1000

    def get_system_state_snapshot(self) -> Dict[str, Any]:
        """Get current system state for UI"""
        state = self.system.get_system_state()

        snapshot = SystemStateSnapshot(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            phase=state.get('band', 'conversational').upper(),
            confidence=state.get('confidence', 0.5),
            authority_band=self._get_authority_band(state.get('confidence', 0.5)),
            murphy_index=self._calculate_murphy_index(state),
            active_gate_count=state.get('gates_count', 0),
            swarm_count=0,  # Will be populated from actual swarm system
            execution_allowed=state.get('confidence', 0.5) >= 0.88
        )

        return asdict(snapshot)

    def get_phase_fsm(self) -> Dict[str, Any]:
        """Get phase FSM state including Type and Enumerate phase implementations."""
        state = self.system.get_system_state()
        confidence = state.get('confidence', 0.5)
        state_vars = state.get('variables', {})

        # ── Type phase: validate declared types of state variables ─────────
        type_results: Dict[str, Any] = {}
        type_errors: List[str] = []
        for var_name, var_info in state_vars.items():
            if not isinstance(var_info, dict):
                continue
            declared_dtype = var_info.get('dtype')
            actual_value = var_info.get('value')
            if declared_dtype is None:
                continue
            expected_type = self._DTYPE_MAP.get(str(declared_dtype).lower())
            if expected_type is None:
                continue
            if actual_value is not None and not isinstance(actual_value, expected_type):
                error_msg = (
                    f"{var_name}: expected {declared_dtype}, "
                    f"got {type(actual_value).__name__}"
                )
                type_errors.append(error_msg)
            type_results[var_name] = {
                "declared": declared_dtype,
                "actual": type(actual_value).__name__ if actual_value is not None else "None",
                "valid": not any(e.startswith(var_name + ":") for e in type_errors),
            }

        type_phase_status = "pass" if not type_errors else "fail"

        # ── Enumerate phase: list valid next states from current phase ──────
        current_phase = self._get_phase_name(confidence)
        valid_next_states = self._PHASE_TRANSITIONS.get(current_phase, [])
        enumerate_results: Dict[str, Any] = {
            "current_state": current_phase,
            "valid_transitions": valid_next_states,
            "transition_count": len(valid_next_states),
        }

        return {
            "fsm": {
                "Expand": {
                    "allowed": confidence < 0.3,
                    "phase_name": "Expand",
                    "status": "active" if current_phase == "Expand" else "inactive",
                    "next_phases": self._PHASE_TRANSITIONS.get("Expand", []),
                },
                "Type": {
                    "allowed": True,
                    "phase_name": "Type",
                    "status": type_phase_status,
                    "results": type_results,
                    "errors": type_errors,
                    "next_phases": self._PHASE_TRANSITIONS.get("Type", []),
                },
                "Enumerate": {
                    "allowed": True,
                    "phase_name": "Enumerate",
                    "status": "pass",
                    "results": enumerate_results,
                    "next_phases": self._PHASE_TRANSITIONS.get("Enumerate", []),
                },
                "Constrain": {
                    "allowed": 0.3 <= confidence < 0.7,
                    "phase_name": "Constrain",
                    "status": "active" if current_phase == "Constrain" else "inactive",
                    "next_phases": self._PHASE_TRANSITIONS.get("Constrain", []),
                },
                "Collapse": {
                    "allowed": 0.7 <= confidence < 0.82,
                    "phase_name": "Collapse",
                    "status": "active" if current_phase == "Collapse" else "inactive",
                    "next_phases": self._PHASE_TRANSITIONS.get("Collapse", []),
                },
                "Bind": {
                    "allowed": 0.82 <= confidence < 0.88,
                    "phase_name": "Bind",
                    "status": "active" if current_phase == "Bind" else "inactive",
                    "next_phases": self._PHASE_TRANSITIONS.get("Bind", []),
                },
                "Execute": {
                    "allowed": confidence >= 0.88,
                    "phase_name": "Execute",
                    "status": "active" if current_phase == "Execute" else "inactive",
                    "next_phases": self._PHASE_TRANSITIONS.get("Execute", []),
                },
            },
            "thresholds": {
                "Expand": 0.0,
                "Constrain": 0.3,
                "Collapse": 0.7,
                "Bind": 0.82,
                "Execute": 0.88
            },
            "current_phase": current_phase,
            "type_phase": {
                "phase_name": "Type",
                "status": type_phase_status,
                "results": type_results,
                "errors": type_errors,
                "next_phases": self._PHASE_TRANSITIONS.get("Type", []),
            },
            "enumerate_phase": {
                "phase_name": "Enumerate",
                "status": "pass",
                "results": enumerate_results,
                "next_phases": self._PHASE_TRANSITIONS.get("Enumerate", []),
            },
        }

    def get_gate_graph(self) -> Dict[str, Any]:
        """Get gate graph for visualization"""
        gates = self.system.get_active_gates()

        nodes = []
        for i, gate in enumerate(gates):
            nodes.append(asdict(GateNode(
                gate_id=f"GATE-{i:03d}",
                type="verification",
                target="system",
                status="active",
                trigger=gate,
                risk_reduction=0.05,
                satisfied=False
            )))

        # Simple linear graph for now
        edges = []
        for i in range(len(nodes) - 1):
            edges.append({
                "from": nodes[i]['gate_id'],
                "to": nodes[i+1]['gate_id'],
                "blocked_by": []
            })

        return {
            "nodes": nodes,
            "edges": edges
        }

    def get_confidence_breakdown(self) -> Dict[str, Any]:
        """Get detailed confidence breakdown"""
        state = self.system.get_system_state()
        confidence = state.get('confidence', 0.5)

        # Estimate components
        generative = min(confidence + 0.1, 1.0)
        deterministic = max(confidence - 0.1, 0.0)

        breakdown = ConfidenceBreakdown(
            confidence=confidence,
            generative_adequacy=generative,
            deterministic_grounding=deterministic,
            weights={"wg": 0.4, "wd": 0.6},
            drivers=[
                {"source": "gate_satisfaction", "delta": 0.05},
                {"source": "unknown_resolution", "delta": 0.03},
                {"source": "verification_pending", "delta": -0.02}
            ]
        )

        return asdict(breakdown)

    def get_execution_packet_status(self) -> Dict[str, Any]:
        """Get execution packet status"""
        state = self.system.get_system_state()
        confidence = state.get('confidence', 0.5)

        if confidence >= 0.88:
            status = {
                "packet_compiled": True,
                "current_packet": {
                    "packet_id": f"PKT-{int(time.time())}",
                    "status": "ready",
                    "allowed_actions": 5,
                    "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "expired_at": None
                }
            }
        else:
            status = {
                "packet_compiled": False,
                "last_packet": None
            }

        return status

    def get_swarm_activity(self) -> Dict[str, Any]:
        """Get aggregated swarm activity"""
        return {
            "active_domains": ["general"],
            "candidate_rate": 0,
            "rejection_rate": 0.0,
            "gate_proposals_per_min": 0,
            "dominant_risk": "none"
        }

    def add_event(self, event_type: str, data: Dict[str, Any]):
        """Add event to log"""
        event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": event_type,
            "data": data
        }

        self.event_log.append(event)

        # Keep only recent events
        if len(self.event_log) > self.max_events:
            self.event_log = self.event_log[-self.max_events:]

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events"""
        return self.event_log[-limit:]

    def _get_authority_band(self, confidence: float) -> str:
        """Determine authority band from confidence"""
        if confidence < 0.3:
            return "EXPLORE"
        elif confidence < 0.7:
            return "PROPOSE"
        elif confidence < 0.88:
            return "CONSTRAIN"
        else:
            return "EXECUTE"

    def _calculate_murphy_index(self, state: Dict[str, Any]) -> float:
        """Calculate Murphy index (risk indicator)"""
        confidence = state.get('confidence', 0.5)
        gates = state.get('gates_count', 0)

        # Simple formula: lower confidence + more gates = higher Murphy index
        murphy = (1.0 - confidence) * 0.7 + (gates / 20.0) * 0.3
        return min(murphy, 1.0)

    def _get_phase_name(self, confidence: float) -> str:
        """Get phase name from confidence"""
        if confidence < 0.3:
            return "Expand"
        elif confidence < 0.7:
            return "Constrain"
        elif confidence < 0.82:
            return "Collapse"
        elif confidence < 0.88:
            return "Bind"
        else:
            return "Execute"

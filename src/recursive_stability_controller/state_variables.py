"""
State Variables & Normalization

Canonical state variables for recursive stability control:
- Aₜ: Active agents
- Gₜ: Active gates
- Eₜ: Feedback entropy / disagreement
- Cₜ: Confidence (external validation only)
- Mₜ: Murphy index (observed failure pressure)

All quantities normalized to bounded ranges [0, 1].
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger("recursive_stability_controller.state_variables")


@dataclass
class StateVariables:
    """Raw state variables (unnormalized)"""

    # Active agents (autonomous decision-making components)
    active_agents: int

    # Active gates (currently being evaluated)
    active_gates: int

    # Feedback entropy (contradiction count from artifact graph)
    feedback_entropy: float

    # Confidence (from Confidence Engine, already normalized)
    confidence: float

    # Murphy index (from system, already normalized)
    murphy_index: float

    # Metadata
    timestamp: float
    cycle_id: int

    def validate(self) -> bool:
        """Validate raw state variables"""
        if self.active_agents < 0:
            return False
        if self.active_gates < 0:
            return False
        if self.feedback_entropy < 0:
            return False
        if not (0.0 <= self.confidence <= 1.0):
            return False
        if not (0.0 <= self.murphy_index <= 1.0):
            return False
        return True


@dataclass
class NormalizedState:
    """Normalized state variables (all in [0, 1])"""

    # Normalized active agents
    A_t: float

    # Normalized active gates
    G_t: float

    # Normalized feedback entropy
    E_t: float

    # Confidence (already normalized)
    C_t: float

    # Murphy index (already normalized)
    M_t: float

    # Metadata
    timestamp: float
    cycle_id: int

    # Raw values (for reference)
    raw_agents: int
    raw_gates: int
    raw_entropy: float

    def validate(self) -> bool:
        """Validate normalized state variables"""
        if not (0.0 <= self.A_t <= 1.0):
            return False
        if not (0.0 <= self.G_t <= 1.0):
            return False
        if not (0.0 <= self.E_t <= 1.0):
            return False
        if not (0.0 <= self.C_t <= 1.0):
            return False
        if not (0.0 <= self.M_t <= 1.0):
            return False
        return True

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "A_t": self.A_t,
            "G_t": self.G_t,
            "E_t": self.E_t,
            "C_t": self.C_t,
            "M_t": self.M_t,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "raw_agents": self.raw_agents,
            "raw_gates": self.raw_gates,
            "raw_entropy": self.raw_entropy
        }


class StateNormalizer:
    """
    Normalize state variables to bounded ranges.

    Normalization ranges (as approved):
    - Aₜ: [0, 100] → [0, 1]
    - Gₜ: [0, 1000] → [0, 1]
    - Eₜ: [0, 10] → [0, 1]
    - Cₜ: [0, 1] → unchanged
    - Mₜ: [0, 1] → unchanged

    Hard caps: If raw values exceed max, clamp to 1.0 and emit alert.
    """

    # Normalization constants (IMMUTABLE)
    MAX_AGENTS = 100
    MAX_GATES = 1000
    MAX_ENTROPY = 10.0

    def __init__(self):
        self.alert_count = 0
        self.alerts = []

    def normalize(self, state: StateVariables) -> Optional[NormalizedState]:
        """
        Normalize state variables.

        Returns:
            NormalizedState if successful, None if validation fails
        """
        # Validate raw state
        if not state.validate():
            return None

        # Normalize agents
        A_t = self._normalize_agents(state.active_agents)

        # Normalize gates
        G_t = self._normalize_gates(state.active_gates)

        # Normalize entropy
        E_t = self._normalize_entropy(state.feedback_entropy)

        # Confidence and Murphy index already normalized
        C_t = state.confidence
        M_t = state.murphy_index

        # Create normalized state
        normalized = NormalizedState(
            A_t=A_t,
            G_t=G_t,
            E_t=E_t,
            C_t=C_t,
            M_t=M_t,
            timestamp=state.timestamp,
            cycle_id=state.cycle_id,
            raw_agents=state.active_agents,
            raw_gates=state.active_gates,
            raw_entropy=state.feedback_entropy
        )

        # Validate normalized state
        if not normalized.validate():
            return None

        return normalized

    def _normalize_agents(self, agents: int) -> float:
        """Normalize agent count"""
        if agents > self.MAX_AGENTS:
            self._emit_alert(
                f"Agent count {agents} exceeds max {self.MAX_AGENTS}, clamping to 1.0"
            )
            return 1.0
        return agents / self.MAX_AGENTS

    def _normalize_gates(self, gates: int) -> float:
        """Normalize gate count"""
        if gates > self.MAX_GATES:
            self._emit_alert(
                f"Gate count {gates} exceeds max {self.MAX_GATES}, clamping to 1.0"
            )
            return 1.0
        return gates / self.MAX_GATES

    def _normalize_entropy(self, entropy: float) -> float:
        """Normalize entropy"""
        if entropy > self.MAX_ENTROPY:
            self._emit_alert(
                f"Entropy {entropy} exceeds max {self.MAX_ENTROPY}, clamping to 1.0"
            )
            return 1.0
        return entropy / self.MAX_ENTROPY

    def _emit_alert(self, message: str):
        """Emit alert for clamping"""
        self.alert_count += 1
        self.alerts.append({
            "message": message,
            "count": self.alert_count
        })
        logger.info(f"[ALERT] {message}")

    def get_alerts(self) -> list:
        """Get all alerts"""
        return self.alerts

    def clear_alerts(self):
        """Clear alerts"""
        self.alerts = []


class StateCollector:
    """
    Collect state variables from Murphy System components.

    Pulls telemetry from:
    - Confidence Engine (8055)
    - Gate Synthesis Engine (8056)
    - Execution Orchestrator (8058)
    """

    def __init__(
        self,
        confidence_engine_url: str = "http://localhost:8055",
        gate_synthesis_url: str = "http://localhost:8056",
        orchestrator_url: str = "http://localhost:8058"
    ):
        self.confidence_engine_url = confidence_engine_url
        self.gate_synthesis_url = gate_synthesis_url
        self.orchestrator_url = orchestrator_url
        self.cycle_id = 0

    def collect(self) -> Optional[StateVariables]:
        """
        Collect current state variables from all components.

        Returns:
            StateVariables if successful, None if collection fails
        """
        import time

        import requests

        try:
            # Increment cycle ID
            self.cycle_id += 1

            # Collect from Execution Orchestrator
            orchestrator_response = requests.get(
                f"{self.orchestrator_url}/telemetry",
                timeout=2.0
            )
            orchestrator_data = orchestrator_response.json()

            # Extract active agents
            active_agents = orchestrator_data.get("active_agents", 0)

            # Collect from Gate Synthesis Engine
            gate_response = requests.get(
                f"{self.gate_synthesis_url}/telemetry",
                timeout=2.0
            )
            gate_data = gate_response.json()

            # Extract active gates (gates currently being evaluated)
            active_gates = gate_data.get("active_gates", 0)

            # Collect from Confidence Engine
            confidence_response = requests.get(
                f"{self.confidence_engine_url}/telemetry",
                timeout=2.0
            )
            confidence_data = confidence_response.json()

            # Extract feedback entropy (contradiction count)
            feedback_entropy = confidence_data.get("contradiction_count", 0)

            # Extract confidence (mean confidence)
            confidence = confidence_data.get("mean_confidence", 0.5)

            # Extract Murphy index
            murphy_index = confidence_data.get("murphy_index", 0.0)

            # Create state variables
            state = StateVariables(
                active_agents=active_agents,
                active_gates=active_gates,
                feedback_entropy=feedback_entropy,
                confidence=confidence,
                murphy_index=murphy_index,
                timestamp=time.time(),
                cycle_id=self.cycle_id
            )

            return state

        except Exception as exc:
            logger.info(f"[ERROR] Failed to collect state: {exc}")
            return None

    def collect_mock(self) -> StateVariables:
        """
        Collect mock state for testing.

        Returns:
            Mock StateVariables
        """
        import random
        import time

        self.cycle_id += 1

        return StateVariables(
            active_agents=random.randint(0, 50),
            active_gates=random.randint(0, 500),
            feedback_entropy=random.uniform(0, 5),
            confidence=random.uniform(0.5, 0.9),
            murphy_index=random.uniform(0.0, 0.3),
            timestamp=time.time(),
            cycle_id=self.cycle_id
        )

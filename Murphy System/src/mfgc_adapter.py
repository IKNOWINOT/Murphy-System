"""
MFGC Adapter
Bridges MFGC 7-phase control system with SystemIntegrator
Provides optional phase-locked execution with confidence, authority, and Murphy index tracking
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.mfgc_core import (
    AuthorityController,
    ConfidenceEngine,
    GateCompiler,
    MFGCController,
    MFGCSystemState,
    MurphyIndexMonitor,
    Phase,
    SwarmGenerator,
)
from src.system_integrator import SystemIntegrator, SystemResponse, SystemState, UserRequest

logger = logging.getLogger(__name__)


@dataclass
class MFGCConfig:
    """Configuration for MFGC control"""
    enabled: bool = False
    murphy_threshold: float = 0.3
    confidence_mode: str = "phase_locked"
    authority_mode: str = "standard"
    gate_synthesis: bool = True
    emergency_gates: bool = True
    phase_verbosity: int = 1
    audit_trail: bool = True

    def to_dict(self) -> Dict:
        return {
            "enabled": self.enabled,
            "murphy_threshold": self.murphy_threshold,
            "confidence_mode": self.confidence_mode,
            "authority_mode": self.authority_mode,
            "gate_synthesis": self.gate_synthesis,
            "emergency_gates": self.emergency_gates,
            "phase_verbosity": self.phase_verbosity,
            "audit_trail": self.audit_trail
        }


@dataclass
class MFGCExecutionResult:
    """Result of MFGC-controlled execution"""
    success: bool
    phases_completed: List[str]
    final_phase: str
    confidence_trajectory: List[float]
    authority_trajectory: List[float]
    murphy_trajectory: List[float]
    gates_generated: List[str]
    total_gates: int
    murphy_index: float
    final_confidence: float
    final_authority: float
    execution_time: float
    system_state: MFGCSystemState
    integrator_response: Optional[SystemResponse] = None

    def to_dict(self, phase_verbosity: int = 1) -> Dict:
        return {
            "success": self.success,
            "phases_completed": self.phases_completed,
            "final_phase": self.final_phase,
            "confidence_trajectory": self.confidence_trajectory,
            "authority_trajectory": self.authority_trajectory,
            "murphy_trajectory": self.murphy_trajectory,
            "gates_generated": self.gates_generated,
            "total_gates": self.total_gates,
            "murphy_index": self.murphy_index,
            "final_confidence": self.final_confidence,
            "final_authority": self.final_authority,
            "execution_time": self.execution_time,
            "system_state": {
                "phase": self.system_state.p_t.value,
                "confidence": self.system_state.c_t,
                "authority": self.system_state.a_t,
                "murphy_index": self.system_state.M_t,
                "gates": self.system_state.G_t,
                "phase_history": [p.value for p in self.system_state.phase_history],
                "events": self.system_state.events[-10:] if phase_verbosity > 1 else []
            },
            "integrator_response": self.integrator_response.to_dict() if self.integrator_response else None
        }


class MFGCAdapter:
    """Adapter that bridges MFGC control with SystemIntegrator"""

    def __init__(self, integrator: SystemIntegrator, config: Optional[MFGCConfig] = None):
        self.integrator = integrator
        self.config = config or MFGCConfig()
        self.controller = MFGCController()

        if self.config.murphy_threshold != 0.3:
            self.controller.murphy_monitor.threshold = self.config.murphy_threshold

        self.execution_count = 0
        self.total_execution_time = 0.0
        self.success_count = 0

    def execute_with_mfgc(self, user_input: str,
                          request_type: str = "general",
                          parameters: Optional[Dict] = None) -> MFGCExecutionResult:
        import time
        start_time = time.time()

        context = {
            "user_input": user_input,
            "request_type": request_type,
            "parameters": parameters or {},
            "integrator": self.integrator
        }

        mfgc_state = self.controller.execute(user_input, context)

        integrator_response = None
        if mfgc_state.c_t >= mfgc_state.p_t.confidence_threshold:
            try:
                integrator_response = self.integrator.process_user_request(
                    user_input=user_input,
                    parameters=parameters
                )
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                if self.config.audit_trail:
                    mfgc_state.log_event("integrator_error", {
                        "error": str(exc),
                        "user_input": user_input
                    })

        execution_time = time.time() - start_time

        self.execution_count += 1
        self.total_execution_time += execution_time
        if mfgc_state.c_t >= mfgc_state.p_t.confidence_threshold:
            self.success_count += 1

        result = MFGCExecutionResult(
            success=mfgc_state.c_t >= mfgc_state.p_t.confidence_threshold,
            phases_completed=[p.value for p in mfgc_state.phase_history],
            final_phase=mfgc_state.p_t.value,
            confidence_trajectory=mfgc_state.confidence_history,
            authority_trajectory=[],
            murphy_trajectory=mfgc_state.murphy_history,
            gates_generated=mfgc_state.G_t,
            total_gates=len(mfgc_state.G_t),
            murphy_index=mfgc_state.M_t,
            final_confidence=mfgc_state.c_t,
            final_authority=mfgc_state.a_t,
            execution_time=execution_time,
            system_state=mfgc_state,
            integrator_response=integrator_response
        )

        return result

    def execute_without_mfgc(self, user_input: str,
                             request_type: str = "general",
                             parameters: Optional[Dict] = None) -> SystemResponse:
        return self.integrator.process_user_request(
            user_input=user_input,
            parameters=parameters
        )

    def update_config(self, config: MFGCConfig):
        self.config = config
        if config.murphy_threshold != self.controller.murphy_monitor.threshold:
            self.controller.murphy_monitor.threshold = config.murphy_threshold

    def get_statistics(self) -> Dict[str, Any]:
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        avg_time = (self.total_execution_time / self.execution_count) if self.execution_count > 0 else 0

        return {
            "total_executions": self.execution_count,
            "successful_executions": self.success_count,
            "success_rate": f"{success_rate:.2f}%",
            "average_execution_time": f"{avg_time:.3f}s",
            "mfgc_enabled": self.config.enabled,
            "murphy_threshold": self.config.murphy_threshold,
            "confidence_mode": self.config.confidence_mode
        }

    def get_current_state(self) -> Dict[str, Any]:
        integrator_state = self.integrator.get_system_state()

        return {
            "integrator_state": integrator_state.to_dict(),
            "mfgc_config": self.config.to_dict(),
            "mfgc_statistics": self.get_statistics(),
            "phase": "idle",  # No active execution
            "confidence": 0.0,
            "authority": 0.0,
            "murphy_index": 0.0,
            "gates": [],
            "phase_history": [],
            "events": []
        }


class MFGCSystemFactory:
    """Factory for creating MFGC-enabled systems"""

    @staticmethod
    def create_production_system() -> MFGCAdapter:
        config = MFGCConfig(
            enabled=True,
            murphy_threshold=0.5,
            confidence_mode="relaxed",
            authority_mode="standard",
            gate_synthesis=True,
            emergency_gates=False,
            phase_verbosity=1,
            audit_trail=True
        )
        integrator = SystemIntegrator()
        return MFGCAdapter(integrator, config)

    @staticmethod
    def create_certification_system() -> MFGCAdapter:
        config = MFGCConfig(
            enabled=True,
            murphy_threshold=0.2,
            confidence_mode="strict",
            authority_mode="strict",
            gate_synthesis=True,
            emergency_gates=True,
            phase_verbosity=2,
            audit_trail=True
        )
        integrator = SystemIntegrator()
        return MFGCAdapter(integrator, config)

    @staticmethod
    def create_development_system() -> MFGCAdapter:
        config = MFGCConfig(
            enabled=True,
            murphy_threshold=0.4,
            confidence_mode="phase_locked",
            authority_mode="permissive",
            gate_synthesis=True,
            emergency_gates=False,
            phase_verbosity=0,
            audit_trail=False
        )
        integrator = SystemIntegrator()
        return MFGCAdapter(integrator, config)

    @staticmethod
    def create_custom_system(**kwargs) -> MFGCAdapter:
        config = MFGCConfig(**kwargs)
        integrator = SystemIntegrator()
        return MFGCAdapter(integrator, config)

"""Rosetta State Management System for Murphy."""
from .rosetta_manager import RosettaManager
from .rosetta_models import AgentState, Goal, Identity, RosettaAgentState, SystemState, Task
from .subsystem_wiring import (
    WiringPoint,
    WiringResult,
    WiringStatus,
    RosettaSubsystemWiring,
    bootstrap_wiring,
)

__all__ = [
    "RosettaAgentState",
    "Identity",
    "SystemState",
    "AgentState",
    "Goal",
    "Task",
    "RosettaManager",
    "WiringPoint",
    "WiringResult",
    "WiringStatus",
    "RosettaSubsystemWiring",
    "bootstrap_wiring",
]

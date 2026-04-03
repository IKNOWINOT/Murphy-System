"""Rosetta State Management System for Murphy."""
from .rosetta_manager import RosettaManager
from .rosetta_models import AgentState, Goal, Identity, RosettaAgentState, SystemState, Task
from .subsystem_wiring import (
    RosettaSubsystemWiring,
    WiringPoint,
    WiringResult,
    WiringStatus,
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
    "RosettaSubsystemWiring",
    "bootstrap_wiring",
]

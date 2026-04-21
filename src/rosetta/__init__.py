"""Rosetta State Management System for Murphy."""
from .rosetta_manager import RosettaManager
from .rosetta_models import AgentState, Goal, Identity, RosettaAgentState, SystemState, Task
from .subsystem_wiring import (
    RosettaSubsystemWiring,
    WiringStatus,
    bootstrap_wiring,
)
from .platform_org_seed import (
    CEO_BRANCH_LABEL_TO_ROLE_TITLE,
    PLATFORM_OPERATOR_TO_ROLE,
    PLATFORM_ORG_ID,
    get_platform_roster,
    seed_platform_org,
)
from .org_chart import build_org_chart, lookup_role_for_operator

__all__ = [
    "RosettaAgentState",
    "Identity",
    "SystemState",
    "AgentState",
    "Goal",
    "Task",
    "RosettaManager",
    "RosettaSubsystemWiring",
    "WiringStatus",
    "bootstrap_wiring",
    "PLATFORM_ORG_ID",
    "PLATFORM_OPERATOR_TO_ROLE",
    "CEO_BRANCH_LABEL_TO_ROLE_TITLE",
    "get_platform_roster",
    "seed_platform_org",
    "build_org_chart",
    "lookup_role_for_operator",
]

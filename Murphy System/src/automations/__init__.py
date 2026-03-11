"""
Automations – Advanced Automations
=====================================

Phase 7 of Monday.com feature parity for the Murphy System.

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Automations"

from .models import (
    ActionType,
    AutomationAction,
    AutomationRule,
    Condition,
    ConditionOperator,
    TriggerType,
)
from .engine import AutomationEngine

try:
    from .api import create_automations_router
except Exception:  # pragma: no cover
    create_automations_router = None  # type: ignore[assignment]

__all__ = [
    "ActionType",
    "AutomationAction",
    "AutomationRule",
    "Condition",
    "ConditionOperator",
    "TriggerType",
    "AutomationEngine",
    "create_automations_router",
]

"""
Automations – Advanced Automations
=====================================

Phase 7 of management systems feature parity for the Murphy System.

Provides a complete automation engine including:

- **Rule engine** – trigger / condition / action evaluation
- **Recurrence scheduler** – SCHEDULE-triggered rules with configurable frequency
- **Webhook adapter** – WEBHOOK trigger for external HTTP events
- **Template marketplace** – built-in and custom automation blueprints
- **Cross-board actions** – CROSS_BOARD_CREATE / CROSS_BOARD_UPDATE

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.2.0"
__codename__ = "Automations"

from .engine import AutomationEngine, RecurrenceScheduler
from .models import (
    ActionType,
    AutomationAction,
    AutomationRule,
    AutomationTemplate,
    Condition,
    ConditionOperator,
    RecurrenceFrequency,
    RecurrenceRule,
    TriggerType,
)

try:
    from .api import create_automations_router
except Exception:  # pragma: no cover
    create_automations_router = None  # type: ignore[assignment]

__all__ = [
    "ActionType",
    "AutomationAction",
    "AutomationRule",
    "AutomationTemplate",
    "Condition",
    "ConditionOperator",
    "RecurrenceFrequency",
    "RecurrenceRule",
    "TriggerType",
    "AutomationEngine",
    "RecurrenceScheduler",
    "create_automations_router",
]

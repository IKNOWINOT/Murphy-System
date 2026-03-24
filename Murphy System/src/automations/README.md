# `src/automations` — Advanced Automations

Rule-based automation engine with conditional triggers, typed actions, and a REST API for the Murphy System.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The automations package provides a "when this happens, do that" rule engine for Murphy System workspaces. Each `AutomationRule` pairs one or more `Condition` objects with a sequence of `AutomationAction` steps that fire when the conditions evaluate to true. Triggers are typed — covering board events, time-based schedules, and webhook arrivals — and actions span item mutations, notifications, and cross-board operations. The FastAPI router exposes full CRUD over rules and a run-history log.

## Key Components

| Module | Purpose |
|--------|---------|
| `engine.py` | `AutomationEngine` — evaluates rules, executes action chains, records history |
| `models.py` | `AutomationRule`, `Condition`, `AutomationAction`, `TriggerType`, `ActionType`, `ConditionOperator` |
| `api.py` | FastAPI router (`create_automations_router`) for rule management and history |

## Usage

```python
from automations import AutomationEngine, AutomationRule, TriggerType, ActionType

engine = AutomationEngine()
rule = AutomationRule(
    name="Notify on status change",
    trigger_type=TriggerType.ITEM_STATUS_CHANGED,
    conditions=[],
    actions=[{"type": ActionType.SEND_NOTIFICATION, "params": {"channel": "slack"}}],
)
engine.register_rule(rule)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

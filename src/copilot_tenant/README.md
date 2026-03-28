# `src/copilot_tenant` — Copilot Tenant Agent

Persistent internal orchestration agent — Murphy's always-on copilot that learns from decisions, proposes actions, and graduates to autonomy.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `copilot_tenant` package implements the **Copilot Tenant** — an autonomous agent that lives inside Murphy System, observing all activity, learning from every decision made, and progressively taking over routine work as it earns trust. It operates in two modes: `SHADOW` (observe only) and `ACTIVE` (propose + execute with HITL approval). Graduation to higher autonomy tiers is managed by `GraduationManager`.

## Key Components

| Module | Purpose |
|--------|---------|
| `tenant_agent.py` | `CopilotTenant` — main agent lifecycle, mode switching, task dispatch |
| `task_planner.py` | `TaskPlanner` — decomposes goals into `PlannedTask` sequences |
| `decision_learner.py` | `DecisionLearner` — learns from approved/rejected proposals |
| `execution_gateway.py` | `ExecutionGateway` — executes `Proposal` objects with rollback support |
| `graduation_manager.py` | `GraduationManager` — tracks autonomy tier progression |
| `llm_router.py` | `TenantLLMRouter` — routes LLM calls to DeepInfra / Together / local |
| `matrix_room.py` | `CopilotMatrixRoom` — Matrix room integration for HITL approval |

## Public API

```python
from src.copilot_tenant import (
    CopilotTenant, CopilotTenantMode,
    TaskPlanner, PlannedTask,
    DecisionLearner,
    ExecutionGateway, ExecutionResult, Proposal,
    GraduationManager,
    TenantLLMRouter,
    CopilotMatrixRoom, ApprovalResult,
)
```

## Related

- `src/hitl_autonomy_controller.py` — HITL gate wiring
- `docs/CEO_AUTONOMOUS_OPERATIONS.md` — autonomy roadmap

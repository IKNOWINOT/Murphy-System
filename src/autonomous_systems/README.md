# `src/autonomous_systems` — Autonomous Systems Module

Self-scheduling task execution, risk assessment, and human-oversight controls for autonomous Murphy operation.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The autonomous systems module enables Murphy to plan and execute tasks without constant human direction while preserving meaningful oversight. The `AutonomousScheduler` manages dependency graphs and resource pools to sequence tasks efficiently across priorities. The `RiskManager` evaluates each planned action against configurable risk thresholds and emits mitigation recommendations before execution proceeds. The `HumanOversightSystem` gates high-risk operations behind an approval queue and records every intervention in an immutable event log.

## Key Components

| Module | Purpose |
|--------|---------|
| `autonomous_scheduler.py` | `AutonomousScheduler` with `DependencyGraph`, `ResourcePool`, `Task`, and priority queuing |
| `risk_manager.py` | `RiskManager`, `RiskMonitor`, `MitigationPlanner` — categorised risk assessment |
| `human_oversight_system.py` | `HumanOversightSystem`, `ApprovalQueue`, `InterventionManager`, and `EventLogger` |

## Usage

```python
from autonomous_systems import AutonomousScheduler, RiskManager, HumanOversightSystem, OversightLevel

scheduler = AutonomousScheduler()
risk = RiskManager()
oversight = HumanOversightSystem(level=OversightLevel.STANDARD)

task = scheduler.enqueue(task_id="deploy-v2", priority="high", dependencies=["build"])
assessment = risk.assess(task)
if assessment.requires_approval:
    oversight.request_approval(task, assessment)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

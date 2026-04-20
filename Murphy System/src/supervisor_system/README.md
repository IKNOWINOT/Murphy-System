# `src/supervisor_system` — Supervisor Feedback Loops & Assumption Correction

Prevents overconfident automation by requiring explicit assumption declaration, tracking validity, and automatically correcting when assumptions are invalidated.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The supervisor system is Murphy's epistemic safety layer. Every automated action must declare its underlying assumptions as `AssumptionArtifact` objects before proceeding. The `AssumptionRegistry` tracks these declarations; `AssumptionValidator` checks them against live telemetry and supervisor feedback. When an assumption is invalidated, `InvalidationDetector` triggers the correction loop: `ConfidenceDecayer` reduces the confidence of downstream claims, `AuthorityDecayer` reduces execution authority, and `ExecutionFreezer` halts in-progress tasks until re-validation completes. An anti-recursion layer prevents agents from validating their own assumptions.

## Key Components

| Module | Purpose |
|--------|---------|
| `supervisor.py` | Top-level `Supervisor` coordinating all feedback loops |
| `supervisor_loop.py` | `SupervisorInterface`, `FeedbackProcessor`, `FeedbackRouter`, `SupervisorAuditLogger` |
| `assumption_management.py` | `AssumptionRegistry`, `AssumptionValidator`, `AssumptionBindingManager`, `AssumptionLifecycleManager` |
| `correction_loop.py` | `InvalidationDetector`, `ConfidenceDecayer`, `AuthorityDecayer`, `ExecutionFreezer`, `ReExpansionTrigger` |
| `anti_recursion.py` | `AntiRecursionSystem`, `SelfValidationBlocker`, `CircularDependencyDetector` |
| `hitl_monitor.py` | Human-in-the-loop monitoring for high-risk assumption invalidations |
| `integrated_hitl_monitor.py` | Integrated HITL + supervisor feedback in a single pipeline |
| `schemas.py` | `AssumptionArtifact`, `SupervisorFeedbackArtifact`, `InvalidationSignal`, `CorrectionAction` |
| `hitl_models.py` | HITL-specific data models |

## Usage

```python
from supervisor_system import AssumptionRegistry, AssumptionArtifact, Supervisor

registry = AssumptionRegistry()
assumption = AssumptionArtifact(
    claim="production database is writable",
    source="deployment-agent",
    confidence=0.95,
)
registry.declare(assumption)

supervisor = Supervisor(registry=registry)
supervisor.start()
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

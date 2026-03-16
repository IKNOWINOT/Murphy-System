# `src/execution_orchestrator` — Execution Orchestrator

Safe actuation plane that executes sealed packets with stepwise validation, real-time telemetry, risk monitoring, and automatic rollback.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The execution orchestrator is the final layer before actions reach the real world. It accepts only sealed `ExecutionPacket` objects and enforces a strict sequence: pre-execution validation, stepwise execution with telemetry streaming, continuous risk monitoring, and rollback if any threshold is breached. No packet generation occurs here — the orchestrator is purely an actuation plane. Completion is certified cryptographically by `CompletionCertifier`, releasing the execution lock only when all steps have succeeded within risk bounds.

## Key Components

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Top-level `ExecutionOrchestrator` coordinating all sub-systems |
| `executor.py` | `StepwiseExecutor` — executes REST/RPC, math, filesystem, and actuator steps |
| `validator.py` | `PreExecutionValidator` — packet integrity and interface health checks |
| `risk_monitor.py` | `RuntimeRiskMonitor` — continuous risk calculation during execution |
| `rollback.py` | `RollbackEnforcer` — automatic rollback on risk threshold breach |
| `telemetry.py` | `TelemetryStreamer` — real-time event emission per step |
| `completion.py` | `CompletionCertifier` — cryptographic completion certification |
| `models.py` | `ExecutionState`, `StepResult`, `TelemetryEvent`, `RuntimeRisk`, `SafetyState` |
| `rsc_integration.py` | Integration with the Recursive Stability Controller |
| `api.py` | REST API for orchestrator status and execution history |

## Usage

```python
from execution_orchestrator import ExecutionOrchestrator

orchestrator = ExecutionOrchestrator()
certificate = orchestrator.execute(sealed_packet)
print(certificate.status, certificate.execution_id)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

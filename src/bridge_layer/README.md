# `src/bridge_layer` — System A → System B Bridge Layer

Typed, logged, and safety-constrained bridge between the sandbox hypothesis plane and the execution control plane.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The bridge layer enforces a hard boundary between System A (sandbox hypotheses with zero execution rights) and System B (the Control Plane that compiles and dispatches `ExecutionPacket`s). All bridging is explicit — a `HypothesisArtifact` produced in System A must pass through typed intake, verification request generation, and a `CompilationGate` before System B will compile it into an actionable packet. Blocking reasons are surfaced as human-readable feedback via `ExecutabilityExplainer` so engineers can correct hypotheses safely. No hidden execution paths exist.

## Key Components

| Module | Purpose |
|--------|---------|
| `intake.py` | `HypothesisIntakeService`, `ClaimExtractor`, `VerificationRequestGenerator` |
| `compilation.py` | `CompilationGate` and `ExecutionPacketCompiler` boundary enforcement |
| `models.py` | `HypothesisArtifact`, `VerificationArtifact`, `CompilationResult`, `BlockingReason` |
| `schemas.py` | Serialisation schemas for bridge wire format |
| `hypothesis.py` | Hypothesis document structure and validation |
| `hypothesis_intake.py` | Intake pipeline for raw hypothesis inputs |
| `ux.py` | `ExecutabilityExplainer` and `BlockingFeedback` developer-facing messages |

## Usage

```python
from bridge_layer import HypothesisIntakeService, CompilationGate

intake = HypothesisIntakeService()
artifact = intake.ingest(raw_hypothesis={"claim": "deploy to staging"})

gate = CompilationGate()
result = gate.evaluate(artifact)
if result.approved:
    packet = result.compile()
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

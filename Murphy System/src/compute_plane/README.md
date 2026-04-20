# `src/compute_plane` — Deterministic Compute Plane

Read-only mathematical verification oracle that defines arithmetic reality for the Murphy System.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The compute plane is a pure verification service: it accepts `ComputeRequest` objects, executes deterministic mathematical workloads, and returns `ComputeResult` objects that are fed into the Confidence Engine, Gate Synthesis, and Execution Packet Compiler. LLMs may reason about mathematics, but every numerical claim must be verified here before confidence scores increase. The service exposes parsers, analysers, and solvers for diverse mathematical domains through a unified `ComputeService` interface, and no state mutations are ever performed.

## Key Components

| Module | Purpose |
|--------|---------|
| `service.py` | `ComputeService` — main entry point routing requests to appropriate solvers |
| `models/` | `ComputeRequest` and `ComputeResult` Pydantic model definitions |
| `solvers/` | Domain-specific solver implementations (arithmetic, algebra, calculus, etc.) |
| `parsers/` | Input parsers for mathematical expressions and symbolic notation |
| `analyzers/` | Result analysers for confidence scoring and error detection |
| `api/` | REST API layer exposing compute endpoints |

## Usage

```python
from compute_plane import ComputeService, ComputeRequest

svc = ComputeService()
result = svc.compute(ComputeRequest(expression="integral(x**2, 0, 1)", domain="calculus"))
print(result.value, result.confidence)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

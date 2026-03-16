# `src/deterministic_compute_plane` — Deterministic Compute Plane (Bridge)

Compatibility shim that re-exports `DeterministicComputePlane` from the canonical `deterministic_routing_engine` module.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The `deterministic_compute_plane` package is a thin namespace bridge. The substantive implementation lives in `src/deterministic_routing_engine`; this package re-exports `DeterministicRoutingEngine` as `DeterministicComputePlane` to satisfy historical import paths. New code should import directly from `deterministic_routing_engine`. The single `compute_plane.py` module performs the re-export and exposes `__all__` for static analysis tools.

## Key Components

| Module | Purpose |
|--------|---------|
| `compute_plane.py` | Re-exports `DeterministicRoutingEngine` as `DeterministicComputePlane` |

## Usage

```python
# Prefer the canonical import
from deterministic_routing_engine import DeterministicRoutingEngine

# Legacy import path (still works)
from deterministic_compute_plane.compute_plane import DeterministicComputePlane
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

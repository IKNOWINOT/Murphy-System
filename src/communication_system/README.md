# `src/communication_system` — Communication System

Thin compatibility bridge that re-exports the `comms` package under the `communication_system` namespace.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The `communication_system` package is a namespace shim that provides backward compatibility for code that imports from `src.communication_system`. All substantive logic lives in `src/comms`; this package simply re-exports from there. New code should import directly from `comms`. The `pipeline.py` module contains a thin delegation layer that proxies calls to the canonical comms pipeline.

## Key Components

| Module | Purpose |
|--------|---------|
| `pipeline.py` | Delegation layer proxying to `comms.pipeline` |

## Usage

```python
# Prefer importing from comms directly
from comms import MessageArtifact, Channel

# Legacy import path (still works)
from communication_system.pipeline import MessageIngestionPipeline
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

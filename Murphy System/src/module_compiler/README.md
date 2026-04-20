# `src/module_compiler` — Module Compiler System

Converts bot capabilities into safe, auditable, deterministic execution modules via static analysis — never executing code.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The module compiler analyses bot source code without executing it to extract `Capability` objects, classify determinism, generate sandbox profiles, and produce a `ModuleSpec` that the Execution Orchestrator can safely schedule. All analysis is purely static — the compiler never runs the code it inspects. Modules are registered in `ModuleRegistry` for discovery by gate synthesis and packet compilation downstream. This system is the bridge between raw bot implementations and the formal capability contracts the Murphy control plane requires.

## Key Components

| Module | Purpose |
|--------|---------|
| `compiler.py` | `ModuleCompiler` — static analysis pipeline producing `ModuleSpec` |
| `models/module_spec.py` | `ModuleSpec`, `Capability`, `FailureMode`, `SandboxProfile` |
| `registry/module_registry.py` | `ModuleRegistry` — CRUD and discovery for compiled modules |
| `analyzers/` | Static analysers for I/O schemas, side-effects, and determinism |
| `api/` | REST API for compiler invocation and module registry queries |
| `integration/` | Integration adapters for connecting to the broader Murphy pipeline |

## Usage

```python
from module_compiler import ModuleCompiler, ModuleRegistry

compiler = ModuleCompiler()
spec = compiler.compile(source_path="bots/data_fetcher.py")

registry = ModuleRegistry()
registry.register(spec)
print(spec.capabilities, spec.sandbox_profile)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

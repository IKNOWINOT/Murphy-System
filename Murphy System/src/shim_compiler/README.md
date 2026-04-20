# `src/shim_compiler` — Shim Compiler

Generates bot shim files from manifest definitions, keeping all bot shim implementations in sync with a single source of truth.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The shim compiler solves the problem of keeping dozens of independently deployable bot shims consistent with their module manifests. A `BotManifest` file describes a bot's interface, dependencies, and deployment parameters; `ShimCompiler` reads the manifest and renders the corresponding shim implementation from a Jinja2 template. `ShimDrift` detection compares compiled output against the live shim on disk and reports divergence so CI can catch stale shims before deployment.

## Key Components

| Module | Purpose |
|--------|---------|
| `compiler.py` | `ShimCompiler` — reads manifests and renders shim files from templates |
| `schemas.py` | `BotManifest`, `CompileResult`, `ShimDrift` |
| `templates/` | Jinja2 shim templates for supported bot deployment targets |

## Usage

```python
from shim_compiler import ShimCompiler, BotManifest

compiler = ShimCompiler()
manifest = BotManifest.from_file("bots/data_fetcher/manifest.yaml")
result = compiler.compile(manifest)

if result.drift:
    print("Shim is out of sync:", result.diff)
else:
    result.write()
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# Shim Compiler

The `shim_compiler` package generates thin shim wrappers that adapt
external APIs to Murphy's internal capability interface, rendering them
callable from the AUAR routing engine.

## Key Modules

| Module | Purpose |
|--------|---------|
| `compiler.py` | `ShimCompiler` — generates shim code from API specs |
| `schemas.py` | Input/output schema definitions for shims |
| `templates/` | Jinja2 code templates for generated shims |

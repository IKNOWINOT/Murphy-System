# Module Compiler

The `module_compiler` package compiles Murphy module specifications
into deployable module bundles, resolves integration dependencies, and
validates API contracts.

## Key Modules

| Module | Purpose |
|--------|---------|
| `compiler.py` | `ModuleCompiler` — main compilation pipeline |
| `analyzers/` | Pre-compile analysers (dependency, security, performance) |
| `integration/` | Integration validators and contract checkers |
| `models/` | `ModuleSpec`, `CompiledModule`, `CompilationResult` models |
| `api/` | REST API for triggering and monitoring compilations |

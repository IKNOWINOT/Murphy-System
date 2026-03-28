# Org Compiler

The `org_compiler` package compiles organisation build plans into executable
Murphy configurations, merging enterprise policies with org-specific settings.

## Key Modules

| Module | Purpose |
|--------|---------|
| `compiler.py` | `OrgCompiler` — base compilation pipeline |
| `enterprise_compiler.py` | Extended compiler for enterprise orgs (SSO, RBAC, audit) |
| `murphy_integration.py` | Wires compiled org config into Murphy runtime |
| `parsers.py` | Parses org specification files (YAML/JSON) |
| `schemas.py` | JSON schemas for org specification formats |

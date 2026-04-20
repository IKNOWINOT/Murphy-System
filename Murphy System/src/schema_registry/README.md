# `src/schema_registry` — Schema Registry

Central registry of bot I/O schemas auto-derived from org-chart `RoleTemplate` artifacts for handoff validation and code generation.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The schema registry maintains the canonical set of data contracts governing how bots exchange artifacts at handoff points. Schemas are derived automatically from `RoleTemplate` objects produced by the Org Compiler, then registered as `ArtifactSchema` entries keyed by schema ID. `BotContract` objects pair an input schema with an output schema and declare compatibility constraints. The registry validates live handoff data against active schemas and can generate stub code for new bot implementations. A library of built-in `ARTIFACT_SCHEMA_TEMPLATES` covers common artifact types.

## Key Components

| Module | Purpose |
|--------|---------|
| `registry.py` | `SchemaRegistry` — registration, validation, and code-generation; `ARTIFACT_SCHEMA_TEMPLATES` |
| `schemas.py` | `ArtifactSchema`, `BotContract`, `SchemaField`, `HandoffValidation`, `SchemaCompatibility` |

## Usage

```python
from schema_registry import SchemaRegistry, ArtifactSchema, SchemaField

registry = SchemaRegistry()
schema = ArtifactSchema(
    schema_id="report_v1",
    fields=[SchemaField(name="title", type="string", required=True)],
)
registry.register(schema)

result = registry.validate(data={"title": "Q3 Report"}, schema_id="report_v1")
print(result.valid)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# Integration Engine

The `integration_engine` package automatically generates integration modules
and capability adapters by introspecting target API specifications.

## Key Modules

| Module | Purpose |
|--------|---------|
| `agent_generator.py` | Generates agent stubs from OpenAPI / AsyncAPI specs |
| `capability_extractor.py` | Extracts Murphy capabilities from external API schemas |
| `module_generator.py` | Scaffolds full Murphy modules from extracted capabilities |
| `hitl_approval.py` | Routes generated modules through human review before activation |
| `adapters/` | Pre-built adapters generated for common integrations |

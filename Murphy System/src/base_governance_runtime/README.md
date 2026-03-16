# Base Governance Runtime

The `base_governance_runtime` package implements the foundational governance
policies that all Murphy agents must comply with.  It monitors agent behaviour,
enforces presets, and provides a compliance API.

## Key Modules

| Module | Purpose |
|--------|---------|
| `governance_runtime.py` | Core runtime that evaluates governance rules per request |
| `governance_runtime_complete.py` | Extended runtime with full policy DSL support |
| `compliance_monitor.py` | Continuously monitors running agents for policy violations |
| `preset_manager.py` | Manages reusable governance preset configurations |
| `api_server.py` | REST API for governance policy management |

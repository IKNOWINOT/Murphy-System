# Org Build Plan

The `org_build_plan` package orchestrates the end-to-end setup of a new
organisation within the Murphy System: intake, org-chart generation,
connector selection, and compliance profiling.

## Key Modules

| Module | Purpose |
|--------|---------|
| `organization_intake.py` | Gathers org requirements via structured intake form |
| `org_chart_builder.py` | Generates an org-chart from intake data |
| `connector_selector.py` | Recommends integration connectors based on org profile |
| `compliance_profiler.py` | Builds initial compliance posture from org type and jurisdiction |
| `build_orchestrator.py` | Sequences all build steps and tracks progress |

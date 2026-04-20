# `src/org_build_plan` — Organisation Build Plan

Six-phase on-ramp pipeline that takes any external organisation from intake questionnaire to fully operational Murphy tenant.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The org build plan package orchestrates everything needed to onboard a new customer organisation onto Murphy. Starting from a structured questionnaire captured by `OrganizationIntake`, the `OrganizationBuildOrchestrator` executes six sequential phases: tenant provisioning, org-chart construction, industry-appropriate connector selection, regulatory compliance profiling, and workflow template loading. Preset libraries cover common industries (SaaS, manufacturing, healthcare, finance) so most organisations can be onboarded with minimal configuration. The `BuildResult` records the outcome of each phase for audit.

## Key Components

| Module | Purpose |
|--------|---------|
| `organization_intake.py` | `OrganizationIntake`, `OrganizationIntakeProfile`, `DepartmentSpec` |
| `tenant_provisioner.py` | `TenantProvisioner` — creates isolated workspace and resource quotas |
| `org_chart_builder.py` | `OrgChartBuilder` — constructs corporate hierarchy from intake data |
| `connector_selector.py` | `ConnectorSelector` — selects industry-appropriate platform connectors |
| `compliance_profiler.py` | `ComplianceProfiler` — maps regulatory frameworks to Murphy modules |
| `workflow_templates.py` | `WorkflowTemplateLibrary` — loads pre-built DAG templates per industry |
| `build_orchestrator.py` | `OrganizationBuildOrchestrator`, `BuildResult`, `BuildPhase` |
| `presets/` | Preset configuration files for common industry verticals |

## Usage

```python
from org_build_plan import OrganizationIntake, OrganizationBuildOrchestrator

intake = OrganizationIntake()
profile = intake.capture(name="Acme Corp", industry="manufacturing", headcount=500)

orchestrator = OrganizationBuildOrchestrator()
result = orchestrator.build(profile)
print(result.phase_results)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

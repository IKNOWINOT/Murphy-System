# ORG BUILD PLAN

**Package:** `src/org_build_plan`  
**Version:** 0.1.0  
**Owner:** Platform Engineering  
**License:** BSL 1.1

---

## Overview

The `org_build_plan` package is the **generic on-ramp** for any external organization that wants to become a tenant on the Murphy System. It is industry-agnostic and orchestrates six sequential build phases that take an organization from "I want to use Murphy" to "fully operational tenant."

This is **not** a CLEARS-specific package — it applies to any organization in any sector. Industry-specific defaults are handled by the preset system.

---

## Six-Phase Build Process

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Organization Build Pipeline                      │
├──────┬──────────────────────┬──────────────────────────────────────┤
│Phase │ Module               │ Purpose                              │
├──────┼──────────────────────┼──────────────────────────────────────┤
│  1   │ organization_intake  │ Collect org profile via              │
│      │                      │ questionnaire (12+ questions)        │
├──────┼──────────────────────┼──────────────────────────────────────┤
│  2   │ tenant_provisioner   │ Create isolated workspace with       │
│      │                      │ scaled resource limits               │
├──────┼──────────────────────┼──────────────────────────────────────┤
│  3   │ org_chart_builder    │ Build corporate hierarchy and        │
│      │                      │ enforcement layer                    │
├──────┼──────────────────────┼──────────────────────────────────────┤
│  4   │ connector_selector   │ Wire industry-appropriate platform   │
│      │                      │ connectors                           │
├──────┼──────────────────────┼──────────────────────────────────────┤
│  5   │ compliance_profiler  │ Map regulatory frameworks to Murphy  │
│      │                      │ compliance modules                   │
├──────┼──────────────────────┼──────────────────────────────────────┤
│  6   │ workflow_templates   │ Load pre-built DAG templates for the │
│      │                      │ industry vertical                    │
└──────┴──────────────────────┴──────────────────────────────────────┘
```

---

## Architecture Diagram

```
                          ┌─────────────────────┐
                          │  External Org        │
                          │  "I want to use      │
                          │   Murphy"            │
                          └────────┬────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  OrganizationBuildOrchestrator│
                    │  (build_orchestrator.py)      │
                    └──────────────┬───────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│OrganizationIntake│   │TenantProvisioner │   │ OrgChartBuilder  │
│(intake profile)  │   │(WorkspaceManager)│   │(CorporateOrgChart│
│                  │   │                  │   │+OrgChartEnforce) │
└──────────────────┘   └──────────────────┘   └──────────────────┘
          │                        │                        │
          ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ConnectorSelector │   │ComplianceProfiler│   │WorkflowTemplate  │
│(preset +         │   │(FRAMEWORK_MAP    │   │Library           │
│ existing_systems)│   │ → security level)│   │(→WorkflowDAGEngine│
└──────────────────┘   └──────────────────┘   └──────────────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                                   ▼
                            ┌─────────────┐
                            │ BuildResult │
                            │ (all phases)│
                            └─────────────┘

Presets
───────
presets/
  ├── manufacturing.py       → scada_modbus, OSHA, EPA
  ├── financial_services.py  → stripe, SOC2, PCI_DSS, GDPR
  ├── logistics_fleet.py     → DOT, FMCSA, clickup
  ├── nonprofit_advocacy.py  → mailchimp, GDPR, CAN_SPAM
  ├── energy_utilities.py    → scada_opcua, NERC, EPA, OSHA
  ├── retail_ecommerce.py    → stripe, PCI_DSS, GDPR
  └── saas_agency.py         → github, jira, SOC2, GDPR
```

---

## Integration with Existing Murphy Components

| org_build_plan Component | Murphy Component | Integration Point |
|---|---|---|
| `TenantProvisioner` | `multi_tenant_workspace.WorkspaceManager` | `create_workspace(TenantConfig)`, `add_member()` |
| `OrgChartBuilder` | `onboarding_flow.CorporateOrgChart` | `add_position()` |
| `OrgChartBuilder` | `org_chart_enforcement.OrgChartEnforcement` | `add_node()` |
| `WorkflowTemplateLibrary` | `workflow_dag_engine.WorkflowDAGEngine` | `compile_to_dag()` → `WorkflowDefinition` |
| `ComplianceProfiler` | `compliance_engine` | Activates module IDs |
| `OrganizationIntake.apply_preset()` | `setup_wizard.PRESET_PROFILES` | Maps `setup_wizard_preset` field |

---

## API Reference

### `OrganizationIntake`

Step 1: Collect the organization's profile via a structured questionnaire.

```python
from src.org_build_plan import OrganizationIntake

intake = OrganizationIntake()

# Get all questions
questions = intake.get_questions()  # List[Dict] — 12+ ordered questions

# Apply answers
intake.apply_answer("org_name", "Acme Corp")
intake.apply_answer("industry", "manufacturing")
intake.apply_answer("org_type", "corporation")
intake.apply_answer("company_size", "medium")
intake.apply_answer("labor_model", "union")
intake.apply_answer("ip_protection_level", "trade_secret")
intake.apply_answer("regulatory_frameworks", ["OSHA", "EPA"])

# Validate before proceeding
result = intake.validate_profile()
# {"valid": True, "issues": []}

profile = intake.get_profile()  # OrganizationIntakeProfile
```

**Valid values:**

| Field | Valid Values |
|---|---|
| `industry` | manufacturing, technology, finance, healthcare, retail, energy, media, logistics, nonprofit, other |
| `org_type` | corporation, llc, union_trust, nonprofit, cooperative, government, other |
| `labor_model` | union, w2, contractor, mixed |
| `company_size` | small, medium, enterprise |
| `ip_protection_level` | standard, trade_secret, patent_pending |
| `regulatory_frameworks` | OSHA, EPA, HIPAA, SOC2, GDPR, PCI_DSS, ISO27001, DOT, FMCSA, NERC, CAN_SPAM |

---

### `TenantProvisioner`

Step 2: Creates an isolated workspace.

```python
from src.org_build_plan import TenantProvisioner

provisioner = TenantProvisioner()
result = provisioner.provision(profile)
# ProvisionResult(tenant_id="abc123", isolation_level="strict", ...)
```

**Resource limits by company_size:**

| Size | Storage | API Calls | Members |
|---|---|---|---|
| small | 256 MB | 10,000 | 20 |
| medium | 1,024 MB | 100,000 | 50 |
| enterprise | 4,096 MB | 500,000 | 200 |

**Isolation level by IP protection:**

| `ip_protection_level` | `IsolationLevel` |
|---|---|
| standard | standard |
| trade_secret | strict |
| patent_pending | strict |

---

### `OrgChartBuilder`

Step 3: Builds corporate hierarchy and enforcement layer.

```python
from src.org_build_plan import OrgChartBuilder

builder = OrgChartBuilder()
result = builder.build_from_intake(profile)
# OrgChartResult(positions_created=12, enforcement_nodes=6, ...)
```

---

### `ConnectorSelector`

Step 4: Selects platform connectors from three sources.

```python
from src.org_build_plan import ConnectorSelector

selector = ConnectorSelector()
result = selector.select_connectors(profile)
# ConnectorSelectionResult(selected_connectors=[...], categories={...})
```

Sources (in order, de-duplicated):
1. Industry preset `recommended_connectors`
2. `intake.existing_systems`
3. `intake.connector_needs`

---

### `ComplianceProfiler`

Step 5: Maps regulatory frameworks to Murphy compliance configuration.

```python
from src.org_build_plan import ComplianceProfiler

profiler = ComplianceProfiler()
result = profiler.profile(profile)
# ComplianceProfileResult(security_level="hardened", audit_frequency="quarterly", ...)
```

**Framework → Security Level mapping:**

| Framework | Security | Audit | Data Residency |
|---|---|---|---|
| HIPAA | hardened | quarterly | No |
| SOC2 | hardened | annual | No |
| GDPR | standard | annual | **Yes** |
| PCI_DSS | hardened | quarterly | No |
| NERC | hardened | quarterly | No |
| ISO27001 | hardened | annual | No |
| OSHA | standard | annual | No |
| EPA | standard | annual | No |
| DOT | standard | annual | No |
| FMCSA | standard | quarterly | No |
| CAN_SPAM | standard | annual | No |

---

### `WorkflowTemplateLibrary`

Step 6: Provides pre-built workflow templates per industry.

```python
from src.org_build_plan import WorkflowTemplateLibrary

lib = WorkflowTemplateLibrary()
templates = lib.get_templates_for_industry("manufacturing")

# Compile to WorkflowDefinition for WorkflowDAGEngine
from src.workflow_dag_engine import WorkflowDAGEngine
engine = WorkflowDAGEngine()
dag = lib.compile_to_dag(templates[0])
engine.register_workflow(dag)
```

---

### `OrganizationBuildOrchestrator`

Master orchestrator — runs all six phases.

```python
from src.org_build_plan import OrganizationBuildOrchestrator

obo = OrganizationBuildOrchestrator()

# Option A: Use a preset (fastest path)
result = obo.build_from_preset("manufacturing", "Acme Steel Inc")

# Option B: Custom intake
result = obo.build_organization(profile)

# Check result
if result.phase.value == "completed":
    print(f"Tenant: {result.tenant_id}")
    print(f"Positions: {result.org_chart_result['positions_created']}")
    print(f"Connectors: {result.connector_result['selected_connectors']}")
```

---

## Preset Reference Table

| Preset ID | Industry | Labor | Size | Frameworks | Setup Wizard Preset |
|---|---|---|---|---|---|
| `manufacturing` | manufacturing | union | medium | OSHA, EPA | org_onboarding |
| `financial_services` | finance | w2 | medium | SOC2, PCI_DSS, GDPR | enterprise_compliance |
| `logistics_fleet` | logistics | union | medium | DOT, FMCSA, OSHA | org_onboarding |
| `nonprofit_advocacy` | nonprofit | mixed | small | CAN_SPAM, GDPR | solo_operator |
| `energy_utilities` | energy | union | enterprise | NERC, EPA, OSHA | enterprise_compliance |
| `retail_ecommerce` | retail | w2 | small | PCI_DSS, GDPR | startup_growth |
| `saas_agency` | technology | w2 | medium | SOC2, GDPR | agency_automation |

---

## Example: `build_from_preset()` flow

```python
from src.org_build_plan import OrganizationBuildOrchestrator, BuildPhase

obo = OrganizationBuildOrchestrator()

# Provision a manufacturing org in one call
result = obo.build_from_preset("manufacturing", "Steel Works Inc")

assert result.phase == BuildPhase.COMPLETED
print(result.tenant_id)          # e.g. "a1b2c3d4e5f6"
print(result.provision_result["isolation_level"])  # "standard"
print(result.compliance_result["security_level"])  # "standard"
print(result.workflow_result["templates_loaded"])  # 4
```

---

## Example: Custom `build_organization()` flow

```python
from src.org_build_plan import (
    OrganizationIntake,
    DepartmentSpec,
    OrganizationBuildOrchestrator,
    BuildPhase,
)

# Step 1 — Fill out intake
intake = OrganizationIntake()
intake.apply_answer("org_name", "Northgate Energy Corp")
intake.apply_answer("industry", "energy")
intake.apply_answer("org_type", "corporation")
intake.apply_answer("company_size", "enterprise")
intake.apply_answer("labor_model", "union")
intake.apply_answer("regulatory_frameworks", ["NERC", "EPA", "OSHA"])
intake.apply_answer("ip_protection_level", "trade_secret")
intake.apply_answer("existing_systems", ["power_bi", "slack"])

# Add custom departments
profile = intake.get_profile()
profile.departments = [
    DepartmentSpec(
        name="Grid Operations",
        head_name="VP Grid Ops",
        head_email="gridops@northgate.com",
        headcount=50,
        level="vp",
        responsibilities=["grid_management", "load_balancing"],
        automation_priorities=["factory_iot", "data"],
    ),
    DepartmentSpec(
        name="Safety",
        head_name="Safety Director",
        head_email="safety@northgate.com",
        headcount=15,
        level="director",
        responsibilities=["osha_compliance", "nerc_cip"],
        automation_priorities=["data", "agent"],
    ),
]

# Validate
v = intake.validate_profile()
assert v["valid"], v["issues"]

# Build
obo = OrganizationBuildOrchestrator()
result = obo.build_organization(profile)

assert result.phase == BuildPhase.COMPLETED
# result.provision_result["isolation_level"] == "strict"  (trade_secret)
# result.compliance_result["security_level"] == "hardened" (NERC)
# result.compliance_result["audit_frequency"] == "quarterly" (NERC)
```

---

## How It Connects to Murphy System Components

```
org_build_plan
│
├── organization_intake.py
│   └── Uses: presets/__init__.py (get_preset)
│
├── tenant_provisioner.py
│   └── Uses: src/multi_tenant_workspace.py
│           WorkspaceManager.create_workspace(TenantConfig)
│           WorkspaceManager.add_member(tenant_id, user_id, TenantRole.OWNER)
│
├── org_chart_builder.py
│   ├── Uses: src/onboarding_flow.py
│   │         CorporateOrgChart.add_position(title, level, department, ...)
│   └── Uses: src/org_chart_enforcement.py
│             OrgChartEnforcement.add_node(node_id, role, department, ...)
│
├── compliance_profiler.py
│   └── Uses: (maps to) src/compliance_engine.py module IDs
│
├── workflow_templates.py
│   └── Uses: src/workflow_dag_engine.py
│             WorkflowDefinition, StepDefinition
│
└── build_orchestrator.py
    └── Composes all of the above
```

# `src/org_compiler` — Org Compiler & Shadow Learning System

Compiles organisational role templates from observed workflows and proposes safe automation substitutions via shadow learning.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The org compiler observes real organisational workflows — org charts, SOPs, tickets, and handoffs — and compiles them into typed `RoleTemplate` artifacts that formally describe each role's inputs, outputs, and decision logic. Shadow learning agents watch human operators passively, never executing, while they build a statistical model of work patterns. When evidence accumulates, the compiler generates `TemplateProposalArtifact` objects that humans can review and approve for automation via the `SubstitutionGate`. An enterprise compiler handles multi-tenant and hierarchical organisation structures.

## Key Components

| Module | Purpose |
|--------|---------|
| `compiler.py` | Core `RoleTemplate` compiler — processes parsed data into formal templates |
| `enterprise_compiler.py` | Extended compiler for multi-tenant enterprise org structures |
| `parsers.py` | Input parsers for org charts, SOPs, and ticket systems |
| `schemas.py` | `RoleTemplate`, `OrgChartNode`, `ProcessFlow`, `SubstitutionGate`, `TemplateProposalArtifact` |
| `shadow_learning.py` | Observation-only learning agents — zero execution rights |
| `substitution.py` | `SubstitutionGate` evaluation for automation proposals |
| `visualization.py` | Role → Work graph rendering |
| `murphy_integration.py` | Wires org compiler outputs into Murphy execution pipeline |

## Usage

```python
from org_compiler import compiler as oc
from org_compiler.schemas import RoleTemplate

parsed = oc.parse_org_chart(org_chart_json)
templates = oc.compile(parsed)
for template in templates:
    print(template.role_id, template.automation_readiness_score)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# `src/freelancer_validator` — Freelancer Validator

Hires and manages human validators on freelance platforms for Human-in-the-Loop validation tasks with structured criteria and budget controls.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The freelancer validator extends Murphy's HITL capabilities by sourcing human reviewers from Fiverr, Upwork, and Freelancer.com. Each validation task is posted with machine-readable `ValidationCriteria` and a per-organisation budget cap enforced by `BudgetManager`. Validator credentials are checked against public records by `CredentialVerifier` before tasks are assigned. When responses arrive they are scored by `CriteriaEngine` and the verdict is wired back into the supervisor system's HITL monitor via `FreelancerHITLBridge`.

## Key Components

| Module | Purpose |
|--------|---------|
| `budget_manager.py` | `BudgetManager` — per-org budget caps, ledger, and spend alerts |
| `credential_verifier.py` | `CredentialVerifier` — validates freelancer credentials against public records |
| `criteria_engine.py` | `CriteriaEngine` — scores freelancer responses against structured criteria |
| `hitl_bridge.py` | `FreelancerHITLBridge` — wires verdicts back into the HITL monitor |
| `platform_client.py` | `FiverrClient`, `UpworkClient`, `GenericFreelancerClient` API wrappers |
| `models.py` | `FreelancerTask`, `ValidationCriteria`, `BudgetConfig`, `ResponseVerdict` and related types |

## Usage

```python
from freelancer_validator import FreelancerHITLBridge, ValidationCriteria, PlatformType

bridge = FreelancerHITLBridge()
task = bridge.post_task(
    title="Review AI-generated legal clause",
    platform=PlatformType.UPWORK,
    criteria=ValidationCriteria(items=[{"check": "Is legally sound", "weight": 1.0}]),
    budget_usd=25.0,
)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

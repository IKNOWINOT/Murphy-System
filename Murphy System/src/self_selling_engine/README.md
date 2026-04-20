# `src/self_selling_engine` — Self-Selling Engine

Murphy sells Murphy — fully autonomous prospect identification, outreach, compliance governance, and marketing plan execution without human sales involvement.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The self-selling engine is Murphy's autonomous go-to-market system. `MurphySelfSellingEngine` identifies prospect companies, scores their fit via `ProspectProfile`, and generates personalised `OutreachMessage` objects within compliance constraints enforced by `OutreachComplianceGovernor`. `ProspectOnboarder` handles trial sign-up flows and `TrialShadowDeployer` runs silent capability demonstrations. `MarketingPlanEngine` drives content campaigns, A/B tests, competitive outreach, and community-building actions. All business-type-specific messaging constraints are codified in `BUSINESS_TYPE_CONSTRAINTS`.

## Key Components

| Module | Purpose |
|--------|---------|
| `_engine.py` | `MurphySelfSellingEngine`, `ProspectProfile`, `OutreachMessage`, `SellCycleResult` |
| `_compliance.py` | `OutreachComplianceGovernor`, `ContactRecord`, `ComplianceDecision` |
| `_constraints.py` | `BUSINESS_TYPE_CONSTRAINTS` — per-vertical messaging rules |
| `_outreach_compliance.py` | Outreach channel compliance rules (CAN-SPAM, GDPR) |
| `marketing_plan.py` | `MarketingPlanEngine`, `MarketingPlan`, `ABTestConfig`, `ContentCampaignConfig` |

## Usage

```python
from self_selling_engine import MurphySelfSellingEngine, ProspectProfile

engine = MurphySelfSellingEngine()
prospect = ProspectProfile(company="Acme Corp", industry="SaaS", employees=200)
result = engine.run_sell_cycle(prospect)
print(result.outreach_sent, result.trial_started)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

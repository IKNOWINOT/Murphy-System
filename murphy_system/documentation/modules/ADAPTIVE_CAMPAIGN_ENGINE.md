# Adaptive Campaign Engine

**Design Label:** MKT-004 — Adaptive Per-Tier Campaign Management  
**Source File:** `src/adaptive_campaign_engine.py`  
**Owner:** VP Marketing / CRO

---

## Overview

The Adaptive Campaign Engine (ACE) manages marketing campaigns that
continuously self-optimise to fill every pricing tier.  When traction
falls below configurable thresholds the engine automatically adjusts
channel mix, target demographics, and messaging.  Large paid-advertising
spend requires **human-in-the-loop (HITL) founder approval** before
execution.

---

## Architecture

```
EventBackbone
     │
     ▼
AdaptiveCampaignEngine
     │
     ├── bootstrap_tier_campaigns()
     │     one campaign per tier (community → enterprise)
     │
     ├── ingest_performance_metrics()
     │     impressions, leads, conversions
     │
     ├── detect_low_traction()
     │     conversion rate < threshold for N periods
     │
     ├── auto_adjust()  ← organic adjustments
     │     • rotate channel mix
     │     • shift demographics
     │     • update messaging
     │
     └── generate_paid_ad_proposal()  ← requires HITL
           • budget, channels, rationale, projected ROI
           • dispatched to HITLApprovalSystem
```

---

## Key Classes

### `AdaptiveCampaignEngine`

The main orchestrator.

| Method | Description |
|--------|-------------|
| `bootstrap_campaigns(tiers)` | Creates one active campaign per pricing tier |
| `record_metrics(campaign_id, metrics)` | Ingests performance data for a campaign |
| `evaluate_traction(campaign_id)` | Checks if traction is below threshold; returns `TractionStatus` |
| `auto_adjust(campaign_id, reason)` | Applies organic adjustments; publishes `CAMPAIGN_ADJUSTED` event |
| `propose_paid_ad(campaign_id, budget)` | Generates a `PaidAdProposal` and routes to HITL |
| `approve_paid_ad(proposal_id, operator)` | HITL acceptance path; activates paid campaign |
| `reject_paid_ad(proposal_id, reason)` | HITL rejection path; logs and escalates |

### `PaidAdProposal`

Dataclass capturing a fully-justified paid advertising request:

```python
@dataclass
class PaidAdProposal:
    proposal_id: str
    campaign_id: str
    budget_usd: float
    channels: list[str]           # ["google_ads", "meta", "linkedin"]
    target_demographics: dict
    rationale: str
    projected_roi: float          # multiplier, e.g. 3.5 = 350% return
    status: ProposalStatus        # PENDING | APPROVED | REJECTED
    created_at: datetime
```

### `TractionStatus`

```python
class TractionStatus(Enum):
    HEALTHY = "healthy"
    LOW     = "low"       # below threshold; auto-adjust triggered
    STALLED = "stalled"   # N consecutive low periods; paid ad proposed
```

---

## Events Published

| Event | Payload |
|-------|---------|
| `CAMPAIGN_BOOTSTRAPPED` | `{tier, campaign_id, channels}` |
| `CAMPAIGN_ADJUSTED` | `{campaign_id, reason, changes}` |
| `PAID_AD_PROPOSED` | `{proposal_id, campaign_id, budget_usd}` |
| `PAID_AD_APPROVED` | `{proposal_id, operator}` |
| `PAID_AD_REJECTED` | `{proposal_id, reason}` |

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `conversion_threshold` | `0.02` | Min conversion rate (2%) before low-traction detection |
| `evaluation_periods` | `3` | Consecutive low-traction periods before paid-ad proposal |
| `max_organic_adjustments` | `5` | Max auto-adjustments before escalating to paid campaign |
| `default_channels` | `["organic_search", "social", "email"]` | Starting channel mix |

---

## Dependencies

- `campaign_orchestrator.py` — MKT-003 campaign lifecycle and budget management
- `event_bus.py` — `EventBackbone` for publishing audit events
- `autonomous_systems/human_oversight_system.py` — HITL gate for paid ad approval

---

## Usage

```python
from adaptive_campaign_engine import AdaptiveCampaignEngine

engine = AdaptiveCampaignEngine(event_backbone=backbone, hitl=oversight_system)

# Bootstrap campaigns for all tiers
engine.bootstrap_campaigns(tiers=["community", "startup", "growth", "enterprise"])

# Record performance data
engine.record_metrics("campaign-community-001", {
    "impressions": 10000,
    "leads": 150,
    "conversions": 12,
})

# Evaluate — auto-adjusts if traction is low
status = engine.evaluate_traction("campaign-community-001")
```

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# Customer Financing Plan — Murphy System

> Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

Murphy System automates industrial, building, energy, and business domains. Customer automation deployments range from **$5,000 to $50,000+** — comparable to an HVAC system, mechanical upgrade, or an American car. Like those purchases, Murphy automations need financing options.

This document covers the full financing plan: BNPL (Buy Now Pay Later), green energy financing, grant/incentive matching, and the backend infrastructure that supports it all.

---

## Three-Layer Financing System

### Layer 1: BNPL / Installment Financing

Customers see financing options at checkout, similar to how HVAC companies offer Synchrony or GreenSky:

| Provider | Range | Best For | Status |
|----------|-------|----------|--------|
| **Wisetack** | $500–$25K | Home automation, small commercial | Planned PR 2 |
| **GreenSky** | $1K–$65K | Building automation, energy | Planned PR 2 |
| **Affirm** | $50–$17.5K | Tech purchases, smaller deployments | Planned PR 2 |
| **PayPal Pay Later** | Up to $10K | Existing PayPal customers | Planned PR 2 |
| **Hearth** | $1K–$250K | Contractor/installer style | Planned PR 2 |
| **SBA 7(a) / 504** | Up to $5.5M | Large commercial deployments | Live (grants module) |

### Layer 2: Grants & Green Energy Incentives

Customers who choose "green" automation methods qualify for substantial cost reductions:

| Program | Value | Applies To |
|---------|-------|-----------|
| IRA §48/48E Investment Tax Credit | 6–70% of cost | Clean energy, battery, solar integrations |
| IRA §179D Commercial Deduction | $0.50–$5.00/sq ft | BAS/BMS, HVAC controls, lighting |
| IRA §25C Home Improvement Credit | 30%, up to $3,200/yr | Residential HVAC controls |
| Utility Demand Response | $50–$200/kW/yr | Automated DR participation |
| Custom Utility Incentives | $0.05–$0.25/kWh saved | Energy efficiency projects |
| C-PACE Financing | 100% financing, 10–30yr | Commercial building upgrades |
| Energy Trust of Oregon | Cash incentives | Oregon commercial/industrial |
| USDA REAP | Up to 50% cost-share | Rural agricultural/small business |
| SBA Green 504 | Below-market rates | Energy efficiency + equipment |

### Layer 3: Murphy Backend Infrastructure

The grant module provides:
- **Eligibility Engine:** Match project parameters → applicable programs
- **Session Isolation:** Tenant-isolated grant workspaces
- **HITL Task Queue:** System does everything automatable; shows humans exactly what they must do
- **Prerequisite Chain:** SAM.gov → UEI → CAGE → Grants.gov modeled as dependency graph
- **Murphy Profiles:** Four grant application flavors (R&D, Energy, Manufacturing, General)

---

## The "Like a Car" Analogy

| Car Purchase | Murphy Automation |
|--------------|-------------------|
| $5K used car → personal loan | $5K BAS upgrade → SBA Microloan, on-bill financing |
| $30K new car → 60-month auto loan | $30K EMS deployment → SBA 7(a), C-PACE |
| $50K truck → Ford Credit / Synchrony | $50K SCADA integration → GreenSky, SBA 504 |
| Electric car → federal tax credit | BAS/energy automation → §179D, §48 ITC |
| Dealer financing at checkout | Murphy checkout → "Finance this purchase" button |

The analogy works because Murphy automations, like cars:
1. Have a clear sticker price ($5K–$50K)
2. Generate economic value (energy savings, productivity, revenue)
3. Are durable assets (10–20 year useful life)
4. Have risk profiles familiar to lenders

---

## Stacking Example: Oregon Commercial BAS Project

A small Oregon manufacturer installs Murphy BAS ($35,000 project):

| Incentive | Amount |
|-----------|--------|
| Energy Trust of Oregon (custom commercial) | $8,750 (25% of project) |
| IRA §179D Commercial Deduction | $12,500 ($2.50/sq ft × 5,000 sq ft) |
| Utility Demand Response signup | $3,000/yr ongoing |
| C-PACE financing (remaining balance) | $13,750 at 6%, 15yr = $116/mo |
| **Net out-of-pocket Year 1** | **~$0** (incentives cover $21,250; C-PACE finances rest) |
| **Annual benefit ongoing** | **$3,000+ DR revenue + energy savings** |

---

## Gap Closure Matrix

| Customer Need | Before | After (This Module) |
|--------------|--------|---------------------|
| Know what grants apply to their project | ❌ Unknown | ✅ Auto-matched by eligibility engine |
| Finance $5K–$50K automation | ❌ Credit card only | ✅ SBA Microloan, on-bill, C-PACE |
| Stack multiple incentives | ❌ DIY research | ✅ Stacking recommendations in match results |
| Track grant application progress | ❌ Spreadsheet | ✅ HITL task queue per session |
| Understand federal prerequisites | ❌ Unknown | ✅ Prerequisite chain with step-by-step guide |

---

## Implementation Status

**PR 1 (Complete — This PR):**
- ✅ Grant database (40+ programs)
- ✅ Eligibility matching engine
- ✅ Session/tenant isolation
- ✅ HITL task queue foundation
- ✅ Prerequisite chain (SAM.gov/UEI/CAGE/Grants.gov)
- ✅ Murphy grant profiles (4 flavors)
- ✅ FastAPI endpoints (/api/grants/*)
- ✅ Test suite (9 test files)

**PR 2 (Planned):**
- HITL agentic form-filling
- BNPL provider integrations (Wisetack, GreenSky, Affirm)
- Session encryption with GRANT_SESSION_ENCRYPTION_KEY

**PR 3 (Planned):**
- Customer-facing grant wizard UI
- DSIRE live API integration
- State-specific program enrichment

**PR 4 (Planned):**
- Automated grant submission integrations
- Grants.gov workspace API
- SBIR.gov API integration

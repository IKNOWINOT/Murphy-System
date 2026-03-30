# Grant Application Guide — Murphy System

This guide explains how to use Murphy System's grant and financing engine —
both for Murphy customers evaluating project financing options, and for Inoni
LLC applying for its own R&D grants.

---

## Quick Start

### For Customers (Track B)

1. **Start a session**
   ```
   POST /api/grants/sessions
   {
     "track": "TRACK_B",
     "business_profile": {
       "entity_type": "small_business",
       "project_types": ["bas_bms", "ems"],
       "state": "NY",
       "employee_count": 45,
       "annual_revenue_usd": 8000000,
       "naics_codes": ["238210", "541519"]
     }
   }
   ```

2. **Run eligibility check**
   ```
   POST /api/grants/eligibility
   {
     "business_profile": { ... }
   }
   ```
   Returns ranked list of eligible grants with scores and reasons.

3. **Browse the catalog**
   ```
   GET /api/grants/catalog
   GET /api/grants/catalog/sec_48_itc
   ```

4. **Work through HITL tasks**
   ```
   GET /api/grants/sessions/{session_id}/tasks
   PATCH /api/grants/sessions/{session_id}/tasks/{task_id}
   { "new_state": "completed", "human_provided_data": { ... } }
   ```

---

## Eligibility Scoring

The eligibility engine scores each grant from 0–100 across five dimensions:

| Dimension | What it checks |
|-----------|---------------|
| **Entity type** (25%) | e.g., small business, nonprofit, government agency |
| **Project type** (25%) | e.g., BAS/BMS, EMS, HVAC automation, solar, battery storage |
| **State** (20%) | State programs: NY, CA, OR, CT, NJ; federal programs are nationwide |
| **Size** (15%) | Employee count and revenue vs. program limits |
| **Track alignment** (15%) | Track A (Inoni R&D) vs. Track B (customer projects) |

Grants with a score ≥ 50 are returned as `eligible = true`.

---

## Grant Categories

### Federal Tax Credits
Programs with **10+ year longevity** under the Inflation Reduction Act:

| Grant ID | Program | Value |
|----------|---------|-------|
| `sec_48_itc` | §48/48E Investment Tax Credit | 6–70% of project cost |
| `sec_179d` | §179D Building Energy Efficiency | $0.50–$5.00/sq ft |
| `sec_48c` | §48C Advanced Energy Project | up to 30% |
| `sec_25d` | §25D Residential Clean Energy | 30% |
| `sec_25c` | §25C Efficient Home Improvement | 30%, up to $3,200/yr |
| `sec_45y_ptc` | §45Y Production Tax Credit | per-kWh through 2032+ |
| `heehra_rebate` | HEEHRA/HOMES Rebates | up to $8,000 |
| `rd_credit_sec41` | §41 R&D Tax Credit | 6.5–20% of QRE |

### Federal Grants
| Grant ID | Program | Value |
|----------|---------|-------|
| `sbir_phase1` | SBIR Phase I | $50K–$275K |
| `sbir_phase2` | SBIR Phase II | $750K–$1.75M |
| `sbir_strategic_breakthrough` | SBIR Strategic Breakthrough | up to $30M |
| `sttr` | STTR | $50K–$1.75M |
| `arpa_e` | DOE ARPA-E | up to $10M+ |
| `doe_amo` | DOE Advanced Manufacturing Office | varies |
| `doe_bto` | DOE Building Technologies Office | varies |
| `doe_grip` | DOE Grid Resilience and Innovation | up to $3B total pool |
| `cesmii` | CESMII Smart Manufacturing | project-based |
| `nsf_convergence_accelerator` | NSF Convergence Accelerator | up to $5M |
| `nsf_pfi` | NSF Partnerships for Innovation | $250K–$1M |
| `eda_build_to_scale` | EDA Build to Scale | $500K–$2M |
| `eda_tech_hubs` | EDA Tech Hubs | up to $75M |
| `nist_mep` | NIST MEP Centers | varies |

### SBA Financing
| Grant ID | Program | Value |
|----------|---------|-------|
| `sba_microloan` | SBA Microloan | up to $50K |
| `sba_7a` | SBA 7(a) Loan | up to $5M |
| `sba_504` | SBA 504 Loan | up to $5.5M |

### USDA Programs
| Grant ID | Program | Value |
|----------|---------|-------|
| `usda_reap` | REAP (Rural Energy for America) | up to 50% cost-share |
| `usda_rbeg` | RBEG Rural Business Enterprise | varies |

### State Incentives
| Grant ID | State | Program |
|----------|-------|---------|
| `nyserda` | NY | NYSERDA Clean Energy Programs |
| `california_cec` | CA | California Energy Commission |
| `masscec` | MA | MassCEC Clean Energy Center |
| `nj_clean_energy` | NJ | NJ Clean Energy Program |
| `energy_trust_oregon` | OR | Energy Trust of Oregon |

### Utility Programs
| Grant ID | Program |
|----------|---------|
| `utility_demand_response` | Demand response ($50–$200/kW/yr) |
| `utility_custom_incentive` | Custom efficiency incentives ($0.05–$0.25/kWh) |
| `utility_on_bill_financing` | On-bill financing (0–3% interest) |

### C-PACE Financing
| Grant ID | Program |
|----------|---------|
| `pace_financing` | C-PACE (38+ states, property-assessed, 10–30yr terms) |

### Green Banks
| Grant ID | State | Program |
|----------|-------|---------|
| `ct_green_bank` | CT | Connecticut Green Bank |
| `ny_green_bank` | NY | NY Green Bank |
| `nj_ibank` | NJ | NJ Infrastructure Bank |
| `ca_ibank` | CA | California IBank |

### ESPCs
| Grant ID | Program |
|----------|---------|
| `espc_commercial` | Commercial energy savings performance contracts |
| `espc_federal` | Federal ESPC (UESC/ESPC programs) |

### R&D Tax Credits
| Grant ID | Program |
|----------|---------|
| `state_rd_credits` | State-level R&D credits (OR, CA, NY, NJ, MA, TX) |

---

## IRA Bonus Multipliers

For qualifying §48/§45Y/§48C projects, additional bonus adders stack on top of
the base credit rate:

| Bonus | Requirement | Adder |
|-------|------------|-------|
| **Prevailing wage + apprenticeship** | Pay prevailing wages; use registered apprentices | 5× base credit |
| **Energy community** | Located in fossil fuel-dependent community | +10% |
| **Domestic content** | ≥40% US-manufactured steel, iron, and manufactured products | +10% |
| **Low-income** | Located in low-income or tribal community | +10–20% |
| **Direct pay** | Tax-exempt entities receive cash payment instead of credit | replaces credit |
| **Transferability** | Sell the credit to a third party (cash now) | monetizes credit |

The engine tracks these via `Grant.ira_bonus` and includes them in eligibility
results.

---

## HITL Task States

Grant applications involve tasks that may require human input:

| State | Meaning |
|-------|---------|
| `pending` | Waiting for a dependency task to complete |
| `auto_completed` | System filled in with ≥80% confidence — review optional |
| `needs_review` | System filled in with 50–79% confidence — please verify |
| `blocked_human_required` | Human must provide information — cannot proceed without it |
| `completed` | Task done; downstream tasks are unblocked |

---

## Stacking Grants

Many grants can be combined ("stacked") for maximum value. The `stackable_with`
field on each grant lists compatible program IDs.

**Example stack for a commercial BAS/BMS retrofit in New York:**

1. `sec_179d` — §179D deduction ($1–$5/sq ft for HVAC + lighting)
2. `sec_48_itc` — 30–70% ITC for integrated battery/solar component
3. `nyserda` — NYSERDA cash incentive for demand reduction
4. `pace_financing` — C-PACE 100% financing at below-market rates
5. `utility_custom_incentive` — Con Edison custom incentive ($0.10/kWh saved)

> **Rule of thumb:** Tax credits can almost always stack with grants and
> financing. Grants from different agencies can usually stack. Two grants from
> the *same* agency for the *same* cost item typically cannot.

---

## Saving and Resuming

Form data is auto-saved as you work through each grant application:

```
POST /api/grants/sessions/{session_id}/formdata
{ "grant_id": "sec_48_itc", "field": "project_cost_usd", "value": 850000 }

GET /api/grants/sessions/{session_id}/formdata
→ { "sec_48_itc": { "project_cost_usd": 850000, ... }, ... }
```

Sessions persist until explicitly deleted or archived (90-day inactivity limit).

---

## Prerequisites (Inoni / Track A)

Track A applications require Murphy Collective to complete federal registrations first.
Check status at:

```
GET /api/grants/prerequisites
```

Returns the full prerequisite chain with status (`not_started`, `in_progress`,
`completed`) and next-action instructions for each step.

---

*For the full data model reference, see `docs/GRANT_DATABASE_SCHEMA.md`.  
For Murphy's internal grant strategy, see `docs/MURPHY_GRANT_STRATEGY.md`.  
For customer financing options, see `docs/CUSTOMER_FINANCING_PLAN.md`.*

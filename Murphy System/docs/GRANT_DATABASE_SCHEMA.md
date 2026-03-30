# Grant Database Schema

**Module:** `src/billing/grants/`  
**Copyright:** © 2020 Inoni Limited Liability Company  
**License:** BSL 1.1

---

## Overview

The grant database stores and indexes all funding opportunities relevant to Murphy System
customers and to Murphy Collective itself. It follows a dual-track model:

| Track | Beneficiary | Description |
|-------|------------|-------------|
| **Track A** | Murphy Collective | Murphy itself applies for R&D grants (SBIR, STTR, ARPA-E, NSF, EDA) |
| **Track B** | Murphy customers | Customers apply for project-level incentives (§48 ITC, C-PACE, NYSERDA, etc.) |

---

## Core Data Models (`models.py`)

### `Grant`

The central record for any grant, tax credit, loan, or incentive program.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Stable lowercase snake-case identifier (e.g., `sec_48_itc`) |
| `name` | `str` | Full program name |
| `category` | `GrantCategory` | Enum: `federal_tax_credit`, `federal_grant`, `sba_financing`, `usda_program`, `state_incentive`, `utility_program`, `cpace_financing`, `green_bank`, `espc`, `rd_tax_credit` |
| `track` | `GrantTrack` | `TRACK_A`, `TRACK_B`, or `BOTH` |
| `short_description` | `str` | One-line summary |
| `long_description` | `str` | Full description with eligibility and IRA bonus details |
| `agency_or_provider` | `str` | Administering agency or utility |
| `program_url` | `str` | Canonical program page URL |
| `application_url` | `str` | Application portal URL |
| `min_amount_usd` | `Optional[int]` | Minimum award / credit amount |
| `max_amount_usd` | `Optional[int]` | Maximum award / credit amount |
| `value_description` | `str` | Human-readable value summary |
| `eligible_entity_types` | `List[str]` | e.g., `small_business`, `nonprofit`, `government` |
| `eligible_project_types` | `List[str]` | e.g., `bas_bms`, `ems`, `hvac_automation` |
| `eligible_states` | `Optional[List[str]]` | State codes; `None` = nationwide |
| `requires_existing_building` | `bool` | Retrofit vs. new construction |
| `requires_commercial` | `bool` | Commercial-only programs |
| `is_recurring` | `bool` | Can be claimed in multiple years |
| `program_expiry_year` | `Optional[int]` | Year program expires (None = permanent) |
| `longevity_note` | `str` | Human-readable longevity assessment |
| `stackable_with` | `List[str]` | Other grant IDs that can be combined |
| `ira_bonus` | `Optional[GrantIRABonus]` | IRA 2022 multiplier eligibility |
| `tags` | `List[str]` | Search and filter tags |
| `last_updated` | `str` | ISO date of last catalog update |

### `GrantIRABonus`

Inflation Reduction Act bonus eligibility flags for qualifying programs.

| Field | Description |
|-------|-------------|
| `prevailing_wage` | Prevailing wage + apprenticeship requirement met → 5× base credit |
| `energy_community` | Located in an energy community → +10% bonus |
| `domestic_content` | US-manufactured equipment → +10% bonus |
| `low_income` | Low-income or tribal community → +10–20% bonus |
| `direct_pay_eligible` | Tax-exempt entities can receive direct payment instead of credit |
| `transferable` | Credit can be sold to a third party |

### `GrantSession`

Per-tenant session that tracks a user's grant search, eligibility results, and
applications. Fully isolated between tenants.

| Field | Description |
|-------|-------------|
| `session_id` | UUID v4 |
| `account_id` | Owner account (Murphy tenant) |
| `track` | `TRACK_A` or `TRACK_B` |
| `business_profile` | `BusinessProfile` snapshot used for eligibility matching |
| `eligible_grants` | `List[EligibilityResult]` from the engine |
| `applications` | `List[Application]` in progress or submitted |
| `hitl_tasks` | HITL task queue for this session |
| `created_at` / `updated_at` | Timestamps |

### `Application`

Represents a single grant application in progress.

| Field | Description |
|-------|-------------|
| `application_id` | UUID v4 |
| `grant_id` | References `Grant.id` |
| `status` | `draft`, `in_review`, `submitted`, `awarded`, `rejected` |
| `form_data` | Auto-filled form fields (key → value) |
| `saved_at` | Last save timestamp |

### `HitlTask`

A Human-in-the-Loop task in the grant workflow task queue.

| Field | Description |
|-------|-------------|
| `task_id` | UUID v4 |
| `session_id` | Parent session |
| `title` / `description` | Human-readable task description |
| `state` | `pending`, `auto_completed`, `needs_review`, `blocked_human_required`, `completed` |
| `dependencies` | List of `task_id`s that must complete first |
| `auto_filled_data` | Data the system pre-filled |
| `human_provided_data` | Data the human provided |
| `confidence` | 0.0–1.0 auto-fill confidence score |
| `why_blocked` | Reason task requires human action |
| `what_human_must_provide` | Instructions for the human |

---

## Grant Catalog (`database.py`)

The catalog is assembled at import time from all sub-modules:

```
federal_tax_credits.py   →  sec_179d, sec_48_itc, sec_48c, sec_25d, sec_25c,
                             sec_45y_ptc, heehra_rebate, rd_credit_sec41
federal_grants.py        →  sbir_phase1, sbir_phase2, sbir_strategic_breakthrough,
                             sttr, arpa_e, doe_amo, doe_bto, doe_grip,
                             cesmii, nsf_convergence_accelerator, nsf_pfi,
                             eda_build_to_scale, eda_tech_hubs, nist_mep
sba_financing.py         →  sba_microloan, sba_7a, sba_504
usda_programs.py         →  usda_reap, usda_rbeg
state_incentives.py      →  nyserda, california_cec, masscec, nj_clean_energy,
                             energy_trust_oregon
utility_programs.py      →  utility_demand_response, utility_custom_incentive,
                             utility_on_bill_financing
pace_financing.py        →  pace_financing
green_banks.py           →  ct_green_bank, ny_green_bank, nj_ibank, ca_ibank
espc.py                  →  espc_commercial, espc_federal
rd_tax_credits.py        →  state_rd_credits
```

Total: **43 grant/incentive records** at initial launch.

---

## Eligibility Engine (`engine.py`)

`EligibilityEngine.match(profile: BusinessProfile) → List[EligibilityResult]`

Scoring is additive across five dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Entity type | 25% | Is the entity type in `eligible_entity_types`? |
| Project type | 25% | Does any project type match `eligible_project_types`? |
| State | 20% | Is the state in `eligible_states` (or grant is nationwide)? |
| Size | 15% | Employee count / revenue vs. program thresholds |
| Track | 15% | Does the session track match the grant track? |

Results include a `score` (0–100), `eligible` flag, and `reasons` list.

---

## Session Isolation (`sessions.py`)

- Each `GrantSession` is keyed by `(account_id, session_id)`
- Sessions are stored in an in-process dict (persistent storage delegated to the
  application database layer)
- `GRANT_MAX_SESSIONS_PER_ACCOUNT` env var limits active sessions per tenant
  (default: 10)
- Sessions older than 90 days with no activity are eligible for archival

---

## HITL Task Flow

```
PENDING ──────────────────────────── (dep not done yet)
   │
   │  all deps complete
   ▼
NEEDS_REVIEW          AUTO_COMPLETED      BLOCKED_HUMAN_REQUIRED
   │   (conf 0.5–0.79)  (conf ≥ 0.80)       (human input required)
   └──────────────────────────────────────────────┐
                                                  ▼
                                             COMPLETED
```

---

## API Endpoints (`api.py`)

All routes are prefixed `/api/grants`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/grants/catalog` | Full grant catalog |
| `GET` | `/api/grants/catalog/{grant_id}` | Single grant by ID |
| `POST` | `/api/grants/eligibility` | Run eligibility check against a profile |
| `POST` | `/api/grants/sessions` | Create a new grant session |
| `GET` | `/api/grants/sessions/{session_id}` | Get session details |
| `GET` | `/api/grants/sessions/{session_id}/tasks` | List HITL tasks |
| `PATCH` | `/api/grants/sessions/{session_id}/tasks/{task_id}` | Update task state |
| `GET` | `/api/grants/prerequisites` | Get Murphy's prerequisite chain status |
| `GET` | `/api/grants/murphy-profiles` | List Murphy's 4 grant profiles |
| `POST` | `/api/grants/sessions/{session_id}/formdata` | Save form data |
| `GET` | `/api/grants/sessions/{session_id}/formdata` | Load saved form data |

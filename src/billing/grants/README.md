# Grant Database & Eligibility Engine

> Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

Murphy System's grant, incentive, and financing infrastructure — covering both:
- **Track A:** Murphy/Murphy Collective's own R&D grant applications (SBIR, STTR, ARPA-E, NSF, §41 R&D credit)
- **Track B:** Customer-facing grant matching for automation project financing ($5K–$50M range)

## Architecture

```
src/billing/grants/
├── __init__.py              # Package exports
├── models.py                # All Pydantic data models
├── database.py              # Unified grant catalog (aggregates all sources)
├── engine.py                # Eligibility matching engine
├── federal_tax_credits.py   # §179D, §48/48E, §48C, §25C, §25D, §45/45Y, §41
├── federal_grants.py        # SBIR, STTR, ARPA-E, AMO, BTO, CESMII, NSF, EDA
├── sba_financing.py         # Microloans, 7(a), 504
├── usda_programs.py         # REAP, rural development
├── state_incentives.py      # Energy Trust OR, NYSERDA, CEC, MassCEC, NJ + DSIRE stub
├── utility_programs.py      # Demand response, custom incentives, on-bill financing
├── pace_financing.py        # C-PACE (38+ states)
├── green_banks.py           # CT, NY, NJ, CA green banks
├── espc.py                  # Federal & commercial ESPC / EaaS
├── rd_tax_credits.py        # Federal §41 + state R&D credits
├── murphy_profiles.py       # Murphy/Inoni grant profiles (4 flavors)
├── sessions.py              # Session/tenant isolation
├── task_queue.py            # HITL task queue
├── prerequisites.py         # SAM.gov/UEI/CAGE prerequisite chain
├── api.py                   # FastAPI router (/api/grants/*)
└── README.md                # This file
```

## Two-Track Design

### Track A — Murphy/Inoni Internal

**"We are the first use case always."**

Murphy Collective uses the grant system to apply for its own R&D grants before shipping the capability to customers. This ensures the system works end-to-end and validates every part of the grant workflow.

Primary grants for Murphy Collective:
- SBIR Phase I/II (DOE, NSF) — non-dilutive R&D funding
- STTR — university partnership R&D
- DOE ARPA-E OPEN — transformative energy AI
- NSF Convergence Accelerator — AI for decision making
- §41 R&D Tax Credit — permanent payroll tax offset
- §48C Advanced Energy Project Credit

Four grant profile "flavors" for different grant categories:
- **R&D flavor** (`rd`): Multi-LLM routing, confidence-gated execution, Wingman Protocol, Causality Sandbox, RLEF
- **Energy flavor** (`energy`): BAS/BMS, EMS, demand response, grid-interactive, BACnet/OPC UA
- **Manufacturing flavor** (`manufacturing`): SCADA, OPC UA, MTConnect, PackML, ISA-95
- **General flavor** (`general`): NL→DAG→Execute, 90+ integrations, SOC 2

### Track B — Customer-Facing

Customers describe their automation project; the engine returns a ranked list of applicable grants, tax credits, and financing options.

## Grant Coverage (40+ programs)

| Category | Programs |
|----------|----------|
| Federal Tax Credits | §179D, §48/48E, §48C, §25C, §25D, §45/45Y, HEEHRA, §41 R&D |
| Federal Grants | SBIR Ph I/II/Strategic, STTR, ARPA-E, DOE AMO, DOE BTO, DOE GRIP, CESMII, NSF Convergence, NSF PFI, EDA B2S, EDA Tech Hubs, NIST MEP |
| SBA Financing | Microloan, 7(a), 504 / Green 504 |
| USDA Programs | REAP, RBDG |
| State Incentives | Energy Trust OR, NYSERDA, CEC, MassCEC, NJ Clean Energy + DSIRE stub |
| Utility Programs | Demand response, custom incentives, on-bill financing |
| C-PACE | 38+ states, 10–30yr terms |
| Green Banks | CT, NY, NJ, CA |
| ESPC | Federal FEMP, commercial EaaS |
| R&D Tax Credits | Federal §41, state credits (CA, MA, NY, TX, GA, PA) |

## Session Isolation

Every grant workspace is sandboxed per-account:
- `GrantSession` — isolated workspace per tenant
- `SessionCredential` — who has access (owner/admin/editor/viewer)
- `SavedFormData` — browser-like auto-fill, strictly scoped to session
- `GrantApplication` — individual application within session
- `ApplicationField` — per-field status (auto_filled / needs_review / blocked)

Zero data bleed between accounts is enforced at every data access point.

## HITL Task Queue

System does everything it can; generates a clear checklist of what humans must do:
- `pending` → `auto_completed` (confidence ≥ 0.8)
- `pending` → `needs_review` (confidence 0.5–0.8)
- `pending` → `blocked_human_required` (legal/registrations)
- Any → `completed` (human marks done)

Dependency chain: tasks with unresolved dependencies stay `pending` until dependencies complete.

## Prerequisites Chain

Federal grant prerequisites modeled as a DAG:
1. **EIN** (IRS) — no dependencies
2. **SAM.gov Registration** — depends on: EIN
3. **UEI Number** — auto-assigned during SAM.gov registration
4. **CAGE Code** — auto-assigned during SAM.gov registration
5. **NAICS Code Selection** — depends on: SAM.gov
6. **Grants.gov Account** — depends on: SAM.gov, UEI
7. **SBIR.gov Account** — depends on: UEI
8. **Annual SAM.gov Renewal** — recurring, depends on: SAM.gov

## Environment Variables

```bash
# Grant System
GRANT_DSIRE_API_KEY=              # DSIRE database API key
GRANT_SYSTEM_ENABLED=true
GRANT_SESSION_ENCRYPTION_KEY=     # Encryption key for tenant session data
GRANT_MAX_SESSIONS_PER_ACCOUNT=10

# Federal Prerequisites (Track A — Murphy Collective)
INONI_SAM_UEI=                    # Unique Entity Identifier from SAM.gov
INONI_CAGE_CODE=                  # CAGE code
INONI_GRANTS_GOV_USERNAME=        # Grants.gov account
INONI_EIN=                        # Employer Identification Number

# BNPL Financing (future PR)
WISETACK_API_KEY=
GREENSKY_MERCHANT_ID=
AFFIRM_PUBLIC_KEY=
AFFIRM_PRIVATE_KEY=
```

## API Endpoints

All endpoints under `/api/grants/`. See `api.py` for full documentation.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/grants/eligibility` | Match project → grants |
| GET | `/api/grants/programs` | List all programs |
| GET | `/api/grants/programs/{id}` | Program details |
| GET | `/api/grants/stats` | Catalog stats |
| POST | `/api/grants/sessions` | Create session |
| GET | `/api/grants/sessions` | List sessions |
| GET | `/api/grants/sessions/{id}` | Session details |
| DELETE | `/api/grants/sessions/{id}` | Delete session |
| POST | `/api/grants/sessions/{id}/credentials` | Assign access |
| DELETE | `/api/grants/sessions/{id}/credentials/{uid}` | Revoke access |
| GET | `/api/grants/sessions/{id}/formdata` | Get form data |
| PUT | `/api/grants/sessions/{id}/formdata` | Update form data |
| POST | `/api/grants/sessions/{id}/applications` | Start application |
| GET | `/api/grants/sessions/{id}/applications` | List applications |
| GET/PUT/DELETE | `/api/grants/sessions/{id}/applications/{aid}` | Application CRUD |
| GET | `/api/grants/sessions/{id}/tasks` | Task queue |
| PUT | `/api/grants/sessions/{id}/tasks/{tid}` | Update task |
| GET | `/api/grants/sessions/{id}/tasks/{tid}/dependencies` | Task deps |
| GET | `/api/grants/prerequisites` | Prerequisite chain |
| PUT | `/api/grants/prerequisites/{id}` | Mark prereq complete |
| GET | `/api/grants/profiles` | Murphy profiles |
| GET | `/api/grants/profiles/{flavor}` | Specific profile |

## Adding New Programs

The grant database is data-driven. To add a new program:

1. Choose the appropriate source file (or create a new one for a new category)
2. Create a `Grant(...)` instance with all required fields
3. Add it to the `get_*()` function in that file
4. The catalog automatically includes it (no code changes to `database.py` or `engine.py`)

## PR Roadmap

- **PR 1 (THIS):** Grant database + eligibility engine + session isolation + API + HITL foundation
- **PR 2:** HITL agentic form-filling system
- **PR 3:** Customer-facing grant wizard UI
- **PR 4:** Automated submission integrations

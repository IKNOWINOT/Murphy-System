# Grants & Financing Module

Murphy System grants module provides a comprehensive financing discovery and application-assistance system for both Murphy's own fundraising (Track A) and customer financing (Track B).

## Architecture

```
src/billing/grants/
├── __init__.py          # Package marker
├── models.py            # Pydantic v2 data models
├── database.py          # Lazy-loaded grant catalog (aggregator)
├── engine.py            # Eligibility matching engine
├── api.py               # FastAPI router (create_grants_router)
├── sessions.py          # Tenant-isolated session store (in-memory)
├── task_queue.py        # HITL task queue with dependency resolution
├── prerequisites.py     # Registration chain (EIN→SAM→Grants.gov→...)
├── murphy_profiles.py   # Track A profiles for Murphy's own applications
├── federal_tax_credits.py
├── federal_grants.py
├── sba_financing.py
├── usda_programs.py
├── state_incentives.py
├── utility_programs.py
├── pace_financing.py
├── green_banks.py
├── espc.py
└── rd_tax_credits.py
```

## API Reference

Mount the router in your FastAPI app:

```python
from src.billing.grants.api import create_grants_router
app.include_router(create_grants_router())
```

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/grants/sessions` | Create session |
| GET | `/api/grants/sessions/{id}` | Get session |
| DELETE | `/api/grants/sessions/{id}` | Delete session |
| POST | `/api/grants/sessions/{id}/match` | Run eligibility match |
| GET | `/api/grants/sessions/{id}/results` | Get stored match results |
| GET | `/api/grants/sessions/{id}/tasks` | List all tasks |
| GET | `/api/grants/sessions/{id}/tasks/next` | Get next unblocked tasks |
| POST | `/api/grants/sessions/{id}/tasks/{tid}/complete` | Complete a task |
| GET | `/api/grants/prerequisites` | Get prerequisite chain |
| POST | `/api/grants/prerequisites/{id}/status` | Update prereq status |
| GET | `/api/grants/catalog` | List all grants |
| GET | `/api/grants/catalog/{id}` | Get grant by ID |
| GET | `/api/grants/profiles/murphy` | Murphy Track A profiles |
| GET | `/api/grants/health` | Health check |

## Track A vs Track B

**Track A (`track_a_murphy`)** — Murphy System applying for its own financing:
- SBIR/STTR grants for AI R&D
- DOE Building Technologies Office
- NSF Convergence Accelerator / PFI
- Federal and state R&D tax credits
- Uses pre-built `murphy_*_profile` configurations

**Track B (`track_b_customer`)** — Murphy helping customers find financing:
- Utility incentive programs
- SBA loans for technology adoption
- C-PACE for building improvements
- State energy efficiency incentives
- USDA REAP for rural customers

## Environment Variables

No external API calls are made by the grant data modules — all data is hardcoded.
Future integrations may use:

| Variable | Purpose |
|----------|---------|
| `DSIRE_API_KEY` | DSIRE database API (when implemented) |
| `SAM_GOV_API_KEY` | SAM.gov entity lookup (future) |

## Session Isolation

Sessions are strictly tenant-isolated. Passing a `tenant_id` to session operations validates ownership before returning data. A `ValueError` is raised (translated to HTTP 403) if tenant mismatch is detected.

## Prerequisite Chain

Registration must be completed in order:

1. **EIN** (1 day) — required for all federal programs
2. **SAM.gov** (10 days) — required for all federal grants/contracts
3. **Grants.gov** (5 days) — required for DOE, NSF, EDA submissions
4. **SBIR.gov** (2 days) — required for SBIR/STTR
5. **Research.gov** (3 days) — required for NSF programs
6. **NIST MEP** (5 days) — required for NIST MEP vouchers

# Murphy System — Planned Fixes Roadmap
<!-- Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1 -->

This document tracks the phased plan to stabilise and modernise the Murphy
System runtime. Each phase maps to one or more PRs in the repository.

See [docs/KNOWN_ISSUES.md](KNOWN_ISSUES.md) for detailed descriptions of each
problem.

---

## Phase 1 — Bootstrap Fixes (This PR)

Goal: Make the system runnable for a new developer on a fresh clone.

- [x] Remove `asyncio>=3.4.3` from both `requirements_murphy_1.0.txt` files
- [x] Change `.env.example` default from `staging` to `development` in both copies
- [x] Create `requirements_core.txt` (root + `murphy_system/`) for fast minimal install
- [x] Document known issues in `docs/KNOWN_ISSUES.md`
- [x] Document planned fixes in `docs/PLANNED_FIXES.md` (this file)
- [x] Add Quick Start (Development) section to root `README.md`
- [x] Add stub `__init__.py` to `src/runtime/runtime_packs/`

---

## Phase 2 — Tiered Orchestrator (PR 1)

Goal: Add a tiered runtime that loads only the modules required by the active
team profile, without modifying the monolith runtime files.

- [ ] Add `TieredOrchestrator` (`src/runtime/tiered_orchestrator.py`) with
  4-tier pack system (KERNEL / PLATFORM / DOMAIN / EPHEMERAL)
- [ ] Define `RuntimePack` dataclass with modules, capabilities, api_routers,
  pip_extras, idle_timeout, and max_memory fields
- [ ] Create domain pack definitions under `src/runtime/runtime_packs/`
  (hvac, crm, content, matrix_bridge, digital_asset, supply_chain, ml_ai,
  compliance)
- [ ] Add `CAPABILITY_TO_PACK` mapping derived from onboarding capability list
- [ ] Add tiered runtime tests (`tests/test_tiered_orchestrator.py`)

---

## Phase 3 — Boot Dispatcher (PR 2)

Goal: Fix eager module-level initialisation and provide a clean entry point
that routes to tiered or monolith runtime based on environment variable.

- [ ] Create `src/runtime/boot.py` entry point dispatcher
  (`MURPHY_RUNTIME_MODE=tiered|monolith`)
- [ ] Fix `src/modular_runtime.py` eager init — replace module-level
  `runtime = ModularRuntime()` with a lazy proxy singleton
- [ ] Create tiered app factory in `src/runtime/tiered_app.py`
- [ ] Add `switch_runtime.sh` and `status_runtime.sh` helper scripts
- [ ] Add boot dispatcher tests

---

## Phase 4 — Post-Validation Cleanup (Future)

Goal: Modernise the codebase once the tiered runtime is proven stable in
production. **Do NOT start Phase 4 until Phase 3 is validated.**

- [ ] **Consolidate dual file tree** — merge root `src/` and `murphy_system/src/`
  into a single canonical source of truth; update all import paths and
  Docker configs
- [ ] **Add CI/CD with GitHub Actions** — matrix build across Python 3.10 / 3.11
  / 3.12, lint with ruff, security scan with bandit, coverage gate ≥ 80 %
- [ ] **Add comprehensive test coverage** — target 90 % line coverage on all
  Tier 0 and Tier 1 modules; add property-based tests for core orchestration
  logic
- [ ] **Refactor `murphy_system_core.py`** (662 KB) into domain-scoped modules
  of ≤ 500 lines each — only after tiered runtime is validated in production
- [ ] **Refactor `app.py`** (420 KB) into a router-per-domain structure
- [ ] **Remove monolith files** as fallback — only after tiered is proven stable
  in production over a 30-day window
- [ ] **Add database migration tooling** — automated Alembic migrations on
  deploy; zero-downtime migration strategy
- [ ] **Performance benchmarks** — measure and document monolith vs tiered
  startup time and resident memory across 3 representative team profiles
- [ ] **Fix Docker build** — copy `murphy_system/` directory correctly (space in
  name); or consolidate the dual tree first
- [ ] **Resolve Redis rate-limiting gap** — document multi-worker Redis
  requirement prominently; add health-check endpoint that warns when
  `REDIS_URL` is not configured

---

*Last updated: 2026-03-18. See [docs/KNOWN_ISSUES.md](KNOWN_ISSUES.md) for
the issue descriptions this roadmap addresses.*

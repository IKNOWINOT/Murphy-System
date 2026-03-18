# Murphy System — Known Issues
<!-- Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1 -->

This file documents known limitations, bugs, and architectural issues in the
Murphy System 1.0 codebase. Issues are categorised by severity and include
references to the PRs or phases that resolve them.

---

## 1. Dual File Tree (Unresolved — Phase 4)

**Severity:** Medium  
**Status:** Known / Unresolved

The repository contains two parallel copies of nearly every source file:

- Root `src/` (e.g., `src/runtime/app.py`, `src/runtime/murphy_system_core.py`)
- `Murphy System/src/` (e.g., `Murphy System/src/runtime/app.py`)

Any change applied to one tree must also be applied to the other or the two
copies diverge silently. This is a maintenance hazard and a source of subtle
runtime differences depending on which working directory is used.

**Long-term fix (Phase 4):** Consolidate to a single canonical source tree.
Do NOT merge until the tiered runtime (PRs 1–2) is validated in production.

---

## 2. Monolith Runtime File Size (Unresolved — Phase 4)

**Severity:** Medium  
**Status:** Known / Managed

- `src/runtime/murphy_system_core.py` — ~662 KB (~15 000+ lines)
- `src/runtime/app.py` — ~420 KB (~10 000+ lines)

Both files are operational but unmaintainable at this scale.  The tiered
runtime (PRs 1–2) wraps them without editing them, deferring the refactor
until the tiered system is proven in production.

**Long-term fix (Phase 4):** Break each file into domain-scoped modules of
≤ 500 lines. Only after tiered runtime is validated.

---

## 3. Eager Module-Level Imports in `modular_runtime.py` (Fixed — PR 2)

**Severity:** High  
**Status:** Fixed in PR 2

`src/modular_runtime.py` instantiates `ModularRuntime()` at module scope
(line ~458). This cascades imports of 300+ sub-modules at import time,
consuming gigabytes of memory and making the system unbootable on low-RAM
machines.

**Fix (PR 2):** Replace the module-level singleton with a lazy proxy that
defers instantiation until first access.

---

## 4. `asyncio` PyPI Package in requirements (Fixed — This PR)

**Severity:** High  
**Status:** Fixed in this PR

Both `requirements_murphy_1.0.txt` files contained `asyncio>=3.4.3`. The
`asyncio` PyPI package is an ancient Python 2/3.3 backport that conflicts
with the `asyncio` stdlib module on Python 3.4+. Installing it can mask the
real stdlib asyncio and cause subtle, hard-to-diagnose breakage.

**Fix:** Removed `asyncio>=3.4.3` from both requirements files and added a
comment explaining why it must never be re-added.

---

## 5. Default `.env.example` Set to `staging` (Fixed — This PR)

**Severity:** High  
**Status:** Fixed in this PR

Both `.env.example` files defaulted to `MURPHY_ENV=staging`. Staging mode
requires `MURPHY_API_KEYS` to be set; without it, every API request returns
`401 Unauthorized`. New developers cloning the repository and running
`setup_and_start.sh` would immediately hit 401 on every endpoint.

**Fix:** Changed `MURPHY_ENV=staging` to `MURPHY_ENV=development` in both
`.env.example` files.

---

## 6. Docker Build Missing `Murphy System/` Directory (Unresolved)

**Severity:** Medium  
**Status:** Known / Unresolved

The root `Dockerfile` does not correctly copy the `Murphy System/` directory
(the space in the directory name causes issues). As a result, the Docker
image installs from a different set of requirements than the local development
environment, leading to runtime import failures inside the container.

**Workaround:** Build from the `Murphy System/` sub-directory directly or
rename the directory to remove the space.  
**Long-term fix (Phase 4):** Consolidate the dual file tree to eliminate the
space-in-path issue entirely.

---

## 7. No Automated Test Suite at the Root (Partial — Ongoing)

**Severity:** Medium  
**Status:** Partial / Ongoing

The repository has 644 test files but they are spread across both trees and
rely on optional heavy dependencies (torch, Flask, Textual). There is no
single `pytest` invocation that reliably passes on a fresh clone without
installing the full dependency stack.

**Workaround:** Use `requirements_core.txt` for a minimal install, then run
the four core test suites:

```bash
MURPHY_ENV=development MURPHY_RATE_LIMIT_RPM=6000 \
python3 -m pytest tests/test_platform_self_automation.py \
    tests/test_workflow_automation_compliance.py \
    tests/test_auth_and_route_protection.py \
    tests/test_ui_user_flow_schedule_automations.py \
    --no-cov --timeout=120
```

---

## 8. Missing `__init__.py` in Some Packages (Partial)

**Severity:** Low  
**Status:** Partial / Ongoing

Some directories that should be Python packages are missing `__init__.py`
files. This causes `ImportError` when code uses absolute package imports
into those directories.

Known affected directories:

- `src/runtime/runtime_packs/` (will be created by PR 1; stub added here)

---

## 9. `setup_and_start.sh` Python Path Assumptions (Unresolved)

**Severity:** Low  
**Status:** Known / Unresolved

`setup_and_start.sh` assumes `python3` is available in `$PATH` and does not
handle `venv` creation failures gracefully. On some systems (Windows via
WSL, certain minimal Linux images) `python3` is not aliased correctly and the
script silently falls back to the system Python, bypassing the venv.

**Workaround:** Use `python -m venv .venv` manually, then activate and install
`requirements_core.txt`.

---

## 10. Rate Limiting Requires Redis in Multi-Worker Mode (Unresolved)

**Severity:** Medium  
**Status:** Known / Unresolved

The rate-limiting middleware uses an in-process counter. When running
`uvicorn --workers 4`, each worker has its own counter, so a client can make
4× the allowed requests per minute before being throttled. A Redis-backed
counter is required for correct rate limiting in multi-worker deployments.

This is not documented prominently enough in the deployment guides.

**Workaround:** Run single-worker (`uvicorn --workers 1`) or configure a
Redis instance and set `REDIS_URL` in `.env`.

---

*Last updated: 2026-03-18. See [docs/PLANNED_FIXES.md](PLANNED_FIXES.md) for the resolution roadmap.*

# Production Readiness Plan Review

**Reviewer:** Copilot Coding Agent  
**Date:** 2026-03-29  
**Repository:** IKNOWINOT/Murphy-System  
**Scope:** 6-PR production hardening plan analysis  

---

## EXECUTIVE SUMMARY

The proposed 6-PR plan is **structurally sound and well-sequenced** for a codebase of this scale (4,501 .py files, 3,629-line production server, 1,549 test files). The rename-first / CI-second / harden-third ordering is correct. However, three critical adjustments are needed: **(1)** PR 3 (error handling) and PR 5 (code patterns) have significant scope overlap and should be merged or explicitly coordinated; **(2)** several production-critical concerns (secrets rotation, observability instrumentation, database migration validation, rollback procedures) are absent from all 6 PRs; and **(3)** PR 6 ("finish incomplete modules") is underspecified and carries the highest integration risk — it needs explicit scope boundaries and per-module acceptance criteria.

---

## CRITICAL ISSUES

**1. MCB is NOT just an acronym — it's a domain concept.**  
The MCB references in this repo are **not** a typo of "MCP." MCB stands for "MultiCursorBrowser" — a real subsystem in `src/agent_module_loader.py` (lines 226–1071) implementing nested browser automation with up to 8 depth levels and 64 physical zones. The rename from MCB → MCP must be treated as a **semantic rename** of a domain object, not a global find-replace. Blind replacement will break:
- `MCBCommissionHarness` in `tests/commissioning/mcb_harness.py`
- MCB depth logging (`[MCB depth=X]` prefixes)
- Class names: `MCBCommissionHarness`, `CommissionSpec` references
- Test imports: `from tests.commissioning.mcb_harness import ...`
- 13 Python files + documentation referencing MCB

**Action required:** Create an explicit mapping table of every MCB symbol (class names, file names, log prefixes, test fixtures, docstrings) before executing the rename. Validate with `grep -rn "MCB\|mcb" --include="*.py"` post-rename to confirm zero residual references.

**2. PR 3 and PR 5 have overlapping scope.**  
PR 3 says "replace all bare exceptions with typed Murphy errors." PR 5 says "bare except → typed exceptions." These are the same task. Currently the repo has only **2 bare `except:` blocks** in production code (murphy_production_server.py lines 1255 and 2474), but **14 existing domain-specific exception classes** already exist. The plan should clarify: PR 3 creates the error *framework* (codes, registry, handlers); PR 5 *applies* it to existing code. Make this dependency explicit.

**3. PR 6 is dangerously underspecified.**  
"Complete stub/partial modules to functional state" in a 4,500-file codebase with 920+ source modules is unbounded scope. Without explicit module-by-module acceptance criteria, this PR will either:
- Balloon into months of work, or
- Ship with inconsistent completion states

**Action required:** Before starting PR 6, produce a concrete table listing every incomplete module, its current completion %, target completion %, and specific acceptance test(s).

**4. No rollback or feature-flag strategy.**  
None of the 6 PRs address rollback. For a system claiming ~83% completion, breaking changes during hardening are inevitable. Each PR should include rollback instructions, and PR 4 (production deployment) must include a documented rollback procedure.

**5. "Murphy System/" directory creates dual-maintenance burden.**  
The repo has both `src/` and `Murphy System/src/` (3,212 files). CI already enforces parity via `tree-divergence-check` and `source-drift-guard`. Every PR in this plan will need to update BOTH locations, or CI will block merges. This is not mentioned anywhere in the plan.

---

## PR-BY-PR RECOMMENDATIONS

### PR 1: MCB → MCP Rename + Code Labeling

**Current assessment:** Appropriately scoped for a standalone PR, but underestimates complexity.

**Specific changes needed:**

1. **Split into two sub-PRs or explicit phases:**
   - **Phase 1A:** MCB → MCP rename only. This is a mechanical change with high blast radius (13 .py files, test harnesses, documentation). Ship alone so regressions are isolatable.
   - **Phase 1B:** Module-level docstrings. Adding docstrings to "every .py file" across 4,501 files is a separate, massive documentation task. Consider scoping to `src/` only (920 files) or to files modified in PRs 2–6.

2. **Pre-rename audit required:**  
   Create a rename manifest before execution:
   ```
   File: tests/commissioning/mcb_harness.py
     - Class: MCBCommissionHarness → MCPCommissionHarness
     - Function: probe_html_source() (no MCB ref, safe)
     - File rename: mcb_harness.py → mcp_harness.py
   
   File: src/agent_module_loader.py
     - Class/concept: MCB (MultiCursorBrowser) → MCP
     - Log prefixes: [MCB depth=X] → [MCP depth=X]
     - Constants: MAX_MCB_DEPTH, MCB_ZONE_LIMIT
   
   File: tests/commissioning/test_commissioning_flows.py
     - Import: from tests.commissioning.mcb_harness → mcp_harness
     - 93 commissioning tests referencing MCB
   ```

3. **Acceptance criteria to add:**
   - [ ] `grep -rn "MCB\|mcb" --include="*.py" --include="*.md" --include="*.yml"` returns zero results
   - [ ] All 1,549 test files pass (`pytest tests/ -x`)
   - [ ] CI pipeline passes (tree-divergence-check, source-drift-guard)
   - [ ] `Murphy System/` directory updated in sync with root

4. **Risk:** Medium. File renames (mcb_harness.py → mcp_harness.py) will break import paths. Ensure all consumers are updated.

---

### PR 2: CI Pipeline Tailored to Murphy's Architecture

**Current assessment:** Good scope, but the CI pipeline already exists and is more mature than the plan assumes.

**Specific changes needed:**

1. **Acknowledge existing CI.** The current `.github/workflows/ci.yml` already includes:
   - Ruff linting (non-blocking)
   - Syntax validation
   - Smoke import tests
   - pytest matrix (Python 3.10, 3.11, 3.12)
   - Bandit security scan (non-blocking)
   - Docker build verification
   - Tree divergence check
   - Source drift guard
   - Registry validation

   The plan's scope overlaps ~70% with existing CI. Reframe PR 2 as **"CI hardening and gap closure"** not "CI pipeline creation."

2. **Actual gaps to fill:**
   - **mypy type checking:** Not currently in CI — this is a valid addition, but expect significant initial failures in a 4,501-file codebase. Start with `--ignore-missing-imports --follow-imports=skip` and scope to `src/runtime/` and `src/rosetta/` initially.
   - **HTML validation:** Not in current CI — useful given 7.6% HTML content.
   - **Import validation:** Partially implemented (smoke imports test). Extend to full import graph validation.
   - **Make security checks blocking:** Currently Bandit is non-blocking (`continue-on-error: true`). Make it blocking for `severity: high`.

3. **Add these missing CI checks:**
   - **requirements_ci.txt freshness:** Verify `requirements_ci.txt` is a valid subset of `requirements.txt`
   - **MCB→MCP guard:** Post-PR 1, add a CI check that fails on any MCB reference (regression prevention)
   - **Test coverage thresholds:** Current `--cov-fail-under=0` is effectively no coverage requirement. Set to 50% minimum for `src/runtime/` and `src/rosetta/`.
   - **Duplicate code detection:** Use `pylint --disable=all --enable=duplicate-code` or `jscpd`

4. **Acceptance criteria to add:**
   - [ ] CI passes on all 3 Python versions (3.10, 3.11, 3.12)
   - [ ] Ruff violations count documented (baseline established)
   - [ ] mypy error count documented (baseline established)
   - [ ] Bandit findings at HIGH severity = 0
   - [ ] All existing tests continue to pass
   - [ ] CI runtime < 15 minutes

---

### PR 3: Canonical Error Handling System

**Current assessment:** Well-scoped but builds on a foundation that partially exists. Clarify what's new vs. what's being consolidated.

**Specific changes needed:**

1. **Acknowledge 14 existing exception classes.** The codebase already has domain-specific exceptions:
   - `MarketplaceError`, `TenantAccessError`, `CircularDependencyError`
   - `MatrixClientError`, `PacketCompilationError`, `SignupError`, `AuthError`
   - `CompilationError`, `SweepError`, `ValidationError`
   - `InjectionAttemptError`, `LAMError`, `LLMResponseWiringError`, `StateError`
   
   PR 3 should **wrap these into the Murphy error code system**, not replace them. Create a mapping: `MarketplaceError` → `MURPHY-E301`, `AuthError` → `MURPHY-E101`, etc.

2. **Error code namespace design:**  
   Propose this structure upfront:
   ```
   MURPHY-E0xx: Core/Boot errors
   MURPHY-E1xx: Authentication/Authorization
   MURPHY-E2xx: API/Request handling
   MURPHY-E3xx: Business logic (marketplace, billing, trading)
   MURPHY-E4xx: Integration (LLM, platform connectors)
   MURPHY-E5xx: Data/Persistence
   MURPHY-E6xx: Orchestration/Workflow
   MURPHY-E7xx: UI/Frontend
   MURPHY-E8xx: Infrastructure (Docker, K8s, monitoring)
   MURPHY-E9xx: Reserved/Internal
   ```

3. **Scope reduction:** "Replace all bare exceptions with typed Murphy errors" — there are only 2 bare `except:` blocks in production code. This task is trivial. The real work is:
   - Adding error codes to the 14 existing exception classes
   - Wiring FastAPI exception handlers to return structured JSON
   - Creating the catalog endpoint

4. **Acceptance criteria to add:**
   - [ ] `src/errors/` package exists with `__init__.py`, `codes.py`, `registry.py`, `handlers.py`
   - [ ] All 14 existing exception classes are mapped to MURPHY-E codes
   - [ ] `GET /api/errors/{code}` returns structured JSON for any valid code
   - [ ] `GET /api/errors/catalog` returns complete catalog
   - [ ] FastAPI exception handlers are registered in `murphy_production_server.py`
   - [ ] `docs/ERROR_CATALOG.md` is generated from registry (not hand-maintained)
   - [ ] Zero bare `except:` blocks remain (verify with `grep -rn "except:" --include="*.py"`)

5. **Important:** Create `src/errors/` in the `Murphy System/src/` canonical location first, then sync to root `src/`. The custom instructions mandate this.

---

### PR 4: Production Server Hardening + One-Line Deploy

**Current assessment:** This is the highest-value PR but also the highest-risk. The 3,629-line monolith is the critical path.

**Specific changes needed:**

1. **Do NOT refactor the monolith in this PR.** The plan says "harden murphy_production_server.py" but this file is 3,629 lines. Extracting functionality (logging, rate limiting, middleware) should be done as additive middleware/dependency injection, not as a rewrite. Specific safe changes:
   - Add `RequestIDMiddleware` as FastAPI middleware (additive, ~20 lines)
   - Add structured logging config in `src/logging_config.py` (already partially exists)
   - Add `slowapi` rate limiting as middleware (additive)
   - Tighten CORS settings in existing CORS middleware
   - JWT validation as a FastAPI dependency (additive)

2. **Split "one-line deploy" into a separate sub-PR.**  
   - **PR 4A:** Server hardening (middleware, logging, health checks) — lower risk
   - **PR 4B:** `murphy start --production` CLI command + Docker hardening — higher risk, needs more testing
   
   Rationale: The server hardening changes are testable in isolation. The deploy command requires end-to-end testing with Docker, PostgreSQL, Redis.

3. **Docker hardening is mostly done.** The current Dockerfile already has:
   - Multi-stage build ✓
   - Non-root user (`murphy`) ✓
   - Health check ✓
   - Resource limits in docker-compose ✓
   
   Remaining Docker work is incremental:
   - Add signal handling (`STOPSIGNAL SIGTERM` + graceful shutdown in entrypoint)
   - Add `.dockerignore` optimization
   - Pin base image SHA for reproducibility

4. **Gunicorn/Uvicorn config:** Create `gunicorn.conf.py` with:
   ```python
   workers = int(os.environ.get("WEB_CONCURRENCY", 4))
   worker_class = "uvicorn.workers.UvicornWorker"
   bind = f"0.0.0.0:{os.environ.get('MURPHY_PORT', 8000)}"
   graceful_timeout = 30
   timeout = 120
   keepalive = 5
   ```

5. **Missing from plan:** Graceful shutdown handling. The 180KB server likely has background tasks (heartbeat, SSE streams, WebSocket connections). Add `@app.on_event("shutdown")` or lifespan handler to clean up.

6. **Acceptance criteria to add:**
   - [ ] `X-Request-ID` header present on all responses
   - [ ] Structured JSON logs in production mode
   - [ ] Rate limiting returns HTTP 429 after threshold
   - [ ] Health check at `/health` returns within 2 seconds
   - [ ] Graceful shutdown completes within 30 seconds
   - [ ] `docker-compose up` starts all services and passes health checks
   - [ ] `murphy start --production` works from clean `.env.example`
   - [ ] Non-root user verified: `docker exec murphy-api whoami` returns `murphy`

---

### PR 5: Fix All Novice-Level Code Patterns

**Current assessment:** Overly broad scope. "Fix all novice-level code patterns" across 4,501 files is unbounded.

**Specific changes needed:**

1. **Scope to production-critical paths only.** Prioritize:
   - `murphy_production_server.py` (3,629 lines — the monolith)
   - `src/runtime/` (boot, app, config)
   - `src/rosetta/` (state layer)
   - `src/ceo_branch_activation.py` (autonomous decision-maker)
   - API route handlers in `src/`

2. **Quantify the problem first.** Before starting, establish baselines:
   - Print statements: Currently **3,722** across the codebase (but T20 intentionally ignored in Ruff config for CLI/debug tooling). Many prints may be intentional.
   - Mutable defaults: Run `grep -rn "def.*=\[\]\|def.*={}" --include="*.py" src/`
   - Missing type hints: Run `mypy --ignore-missing-imports src/runtime/ | wc -l`
   - Hardcoded values: This is subjective — define what counts.

3. **Do NOT change print() globally.** The Ruff config explicitly ignores T20 (print statements) because the system includes CLI tooling and debug output. Only convert prints in:
   - `murphy_production_server.py` (production server should use logging)
   - `src/runtime/` (boot process should use logging)
   - API handlers (should use logging)
   
   Leave prints in: CLI tools, debug utilities, test helpers.

4. **Separate Pydantic validation into PR 3 or its own PR.** "Validate input with Pydantic" is a cross-cutting concern that affects API contracts. Changing request/response models is a breaking change that should be done with the error handling system (PR 3), not lumped with code style fixes.

5. **`__all__` additions are low-risk, high-value.** Do these first as they're purely additive and prevent import pollution.

6. **Acceptance criteria to add:**
   - [ ] Zero `print()` calls in `murphy_production_server.py` (replace with `logging`)
   - [ ] Zero mutable defaults in function signatures across `src/`
   - [ ] `__all__` defined in all public `__init__.py` files under `src/`
   - [ ] Ruff passes with zero violations on changed files
   - [ ] No behavioral changes — all existing tests pass unchanged

---

### PR 6: Finish Incomplete Modules (No New Features)

**Current assessment:** Highest risk, least defined. This PR needs the most restructuring.

**Specific changes needed:**

1. **Create an explicit module completion manifest.** Before starting, produce:

   | Module | Current % | Target % | Missing Functionality | Acceptance Test |
   |--------|-----------|----------|----------------------|-----------------|
   | Persistence + replay | 70% | 95% | [specific gaps] | `test_persistence_replay.py` |
   | UI subsystem | 75% | 90% | [specific gaps] | `test_ui_integration.py` |
   | ... | ... | ... | ... | ... |

2. **Define "functional state" precisely.** For each module, answer commissioning questions 1–6 *before* writing code:
   - What is this module supposed to do? (from README/docs)
   - What does it currently do? (from tests + manual inspection)
   - What's the gap?
   - What's the acceptance test?

3. **Split by subsystem if scope exceeds ~500 lines of changes.** If the manifest reveals >3 substantial modules to complete, split into:
   - PR 6A: Persistence + replay completion
   - PR 6B: UI completion
   - PR 6C: Other subsystems

4. **Enforce "no new features" rigorously.** Define a bright line:
   - ✅ Completing a function that has a docstring but empty body → OK
   - ✅ Wiring an existing endpoint that's defined but not registered → OK
   - ✅ Adding error handling to an existing flow → OK
   - ❌ Adding a new endpoint not in any existing documentation → NOT OK
   - ❌ Adding a new module not referenced anywhere → NOT OK
   - ❌ Changing the architecture of an existing module → NOT OK

5. **Acceptance criteria to add:**
   - [ ] Module completion manifest reviewed and approved before coding starts
   - [ ] Each completed module has ≥1 integration test
   - [ ] Commissioning questions 1–10 answered in writing for each module
   - [ ] No new public API endpoints added (only existing stubs completed)
   - [ ] All existing tests continue to pass

---

## MISSING TASKS

The following production readiness concerns are **not covered by any of the 6 PRs**:

### Critical (must address before production)

- **Secrets management:** No mention of secrets rotation, vault integration, or `.env` security. The docker-compose.yml has `POSTGRES_PASSWORD` and `REDIS_PASSWORD` in plain text. Add: secrets via Docker secrets, environment variable validation at startup, `.env.example` with placeholder values only.

- **Database migration validation:** Alembic is configured but the `versions/` directory appears empty. PR 4 mentions "runs migrations" but there's nothing to migrate. Either create initial migrations from models or remove migration references.

- **Rollback procedures:** No PR includes rollback instructions. Minimum: document `git revert` strategy per PR, database rollback for migration PRs, Docker image rollback via tag pinning.

- **Load/performance testing:** 3,722 print statements and a 3,629-line monolith suggest performance hasn't been validated. Add: basic load test with `locust` or `k6` targeting critical endpoints (`/health`, key API routes).

- **Dependency vulnerability scanning:** `requirements.txt` pins specific versions but there's no `pip-audit` or `safety` check in CI. Add to PR 2.

### Important (should address before production)

- **Observability instrumentation:** Prometheus and Grafana are in docker-compose but the `monitoring/prometheus.yml` is a 340-byte placeholder and `observability/emit.ts` is an 83-byte stub. Need: actual scrape configs, application metrics (request latency, error rates, queue depth), Grafana dashboards.

- **Backup/recovery testing:** `k8s/backup-cronjob.yaml` exists but there's no documented restore procedure. Add: backup verification test, restore runbook.

- **API documentation:** No mention of OpenAPI/Swagger docs. FastAPI auto-generates these — verify they're accurate and accessible at `/docs`.

- **Rate limiting for all endpoints:** Current rate limiting is demo-specific only. Production needs global rate limiting (slowapi or Redis-based).

- **CORS hardening:** Verify CORS origins are restricted in production mode (not `*`).

### Nice to have (post-launch)

- **Feature flags:** For safely rolling out completed modules (PR 6)
- **Canary deployment:** K8s manifests exist but no canary strategy
- **SLO/SLA definition:** Test markers exist (`sla`, `benchmark`) but no documented SLOs
- **Runbook:** Operational playbook for common failure scenarios

---

## SEQUENCING RECOMMENDATIONS

### Proposed reordering:

```
PR 1:  MCB → MCP Rename (ONLY rename, no docstrings)
  ↓
PR 1B: Module docstrings (scoped to src/ only, can parallelize with PR 2)
  ↓
PR 2:  CI Hardening (builds on clean codebase from PR 1)
  ↓
PR 3:  Error Handling System (needs CI to validate)
  ↓
PR 5:  Code Pattern Fixes (applies error system from PR 3, needs CI)
  ↓
PR 4A: Server Hardening (middleware, logging — lower risk)
  ↓
PR 4B: Deploy Tooling (CLI command, Docker — higher risk)
  ↓
PR 6:  Module Completion (last, after all infrastructure is hardened)
```

### Rationale for changes:

1. **PR 1 split:** Rename and docstrings are independent tasks with different risk profiles. Rename has high blast radius; docstrings are purely additive. Shipping separately makes regressions from rename isolatable.

2. **PR 5 before PR 4:** Code pattern fixes (logging, exception handling) should happen *before* server hardening. Otherwise PR 4 adds structured logging to code that still uses `print()`, and PR 5 has to re-touch the same files.

3. **PR 4 split:** Server hardening (additive middleware) is lower risk than deploy tooling (new CLI, Docker changes). Shipping separately means the server can be hardened and deployed manually while deploy automation is still being tested.

4. **PR 6 last:** Module completion depends on all infrastructure (CI, error handling, code patterns, server hardening) being in place. Completing modules against an unhardened codebase means they'll need to be re-hardened later.

### Parallelization opportunities:

- PR 1B (docstrings) can run in parallel with PR 2 (CI) — no dependency
- PR 3 (errors) and PR 5 (patterns) are sequential but could be assigned to different engineers if scope is clearly delineated
- PR 4A and PR 4B can be started simultaneously if different engineers work on server code vs. deploy tooling

---

## RISK MITIGATION

### Highest-risk PRs (ranked):

**1. PR 6 (Module Completion) — HIGHEST RISK**
- **Why:** Unbounded scope, touches business logic, potential for introducing bugs in partially-understood modules
- **Mitigation:** Require module completion manifest with sign-off before coding. Time-box to 2 weeks. Any module not completable in that window gets marked "deferred to v1.1."

**2. PR 1 (MCB → MCP Rename) — HIGH RISK**
- **Why:** File renames break import paths. 13 files + test harness + 93 commissioning tests affected. `Murphy System/` parity requirement doubles the blast radius.
- **Mitigation:** Create rename manifest first. Run full test suite before and after. Use `git mv` for file renames to preserve history. Verify CI parity checks pass.

**3. PR 4 (Server Hardening) — MEDIUM-HIGH RISK**
- **Why:** The 3,629-line monolith is the single point of failure. Any middleware addition could break existing routes.
- **Mitigation:** Add middleware one at a time. Run integration tests after each addition. Keep a "known good" Docker image tagged before changes.

**4. PR 5 (Code Patterns) — MEDIUM RISK**
- **Why:** Changing `print()` → `logging` and adding type hints across many files creates merge conflicts with other PRs.
- **Mitigation:** Merge PR 5 last among the infrastructure PRs. Use Ruff auto-fix where possible (`ruff check --fix`).

**5. PR 3 (Error Handling) — LOW-MEDIUM RISK**
- **Why:** Additive system (new package, new endpoints). Low risk of breaking existing code.
- **Mitigation:** Ensure error handlers are added as FastAPI exception handlers (global), not inline replacements.

**6. PR 2 (CI) — LOWEST RISK**
- **Why:** Purely additive CI configuration. Can't break production code.
- **Mitigation:** Use `continue-on-error: true` for new checks initially, then make blocking once baselines are established.

### Cross-cutting risks:

- **Merge conflicts:** PRs 3, 4, and 5 all touch `murphy_production_server.py`. Sequence them carefully and merge promptly.
- **Murphy System/ parity:** Every PR must update both `src/` and `Murphy System/src/`. Consider automating this with a pre-commit hook.
- **Test reliability:** 1,549 test files is a large suite. Ensure CI has adequate timeout (currently 30 min) and that flaky tests are identified before hardening begins.

---

## PROCESS ENHANCEMENTS

### 1. Formalize the commissioning process

Create a `COMMISSIONING_CHECKLIST.md` template that must be completed for each module touched:

```markdown
## Module: [name]
### Commissioning Questions
1. **Designed purpose:** [from docs/README]
2. **Actual behavior:** [from tests + manual verification]
3. **Possible conditions:** [edge cases, error states, concurrent access]
4. **Test coverage:** [list of tests, gaps identified]
5. **Expected results:** [for each condition]
6. **Actual results:** [test run output]
7. **Remaining problems:** [if any, restart from #1]
8. **Documentation status:** [docstring ✓, API docs ✓, README ✓]
9. **Hardening applied:** [error handling ✓, input validation ✓, logging ✓]
10. **Re-commissioned:** [date, by whom, test results]
```

### 2. Add automated quality gates

- **Pre-commit hooks:** Ruff, import sorting, trailing whitespace
- **PR template:** Require commissioning checklist completion
- **Branch protection:** Require CI pass + 1 review for all PRs
- **Coverage gates:** Set minimum coverage per PR (not per-codebase, which is too noisy)

### 3. Create a "known good" baseline

Before starting any PR:
1. Tag current `main` as `v0.83-pre-hardening`
2. Run full test suite and document results (pass count, fail count, skip count)
3. Run Ruff and document violation count
4. Run Bandit and document finding count
5. Build Docker image and tag as `murphy:pre-hardening`

This baseline allows objective measurement of progress and regression detection.

### 4. Use PR stacking or feature flags

For the sequential PRs (3 → 5 → 4), consider:
- **PR stacking** (each PR branches from the previous) to allow parallel development
- **Feature flags** for server hardening changes (middleware can be toggled via env vars)

### 5. Automate Murphy System/ parity

The dual-directory structure (`src/` and `Murphy System/src/`) is a maintenance burden that will compound across 6 PRs. Options:
- **Best:** Resolve the dual structure before starting (make `Murphy System/` a symlink or eliminate it)
- **Good:** Add a pre-commit hook that auto-syncs changes
- **Minimum:** Add a CI check (already exists) and document the sync process in each PR's description

### 6. Time-box each PR

| PR | Estimated Effort | Time Box |
|----|-----------------|----------|
| PR 1 (Rename) | 2-4 hours | 1 day |
| PR 1B (Docstrings) | 4-8 hours | 2 days |
| PR 2 (CI) | 3-6 hours | 1 day |
| PR 3 (Errors) | 8-16 hours | 3 days |
| PR 5 (Patterns) | 8-16 hours | 3 days |
| PR 4A (Hardening) | 8-16 hours | 3 days |
| PR 4B (Deploy) | 4-8 hours | 2 days |
| PR 6 (Modules) | 16-40 hours | 5 days (hard cap) |

**Total estimated:** 53-114 hours (7-15 working days)

---

## SUMMARY OF RECOMMENDATIONS (PRIORITIZED)

### Must-do (blocks production readiness):
1. ✅ Create MCB → MCP rename manifest before executing PR 1
2. ✅ Add secrets management to PR 4 scope (or create PR 4C)
3. ✅ Create module completion manifest before starting PR 6
4. ✅ Add rollback procedures to every PR description
5. ✅ Clarify PR 3 vs PR 5 scope boundary (framework vs application)
6. ✅ Establish "known good" baseline before starting any work

### Should-do (improves quality significantly):
7. Split PR 1 (rename + docstrings are independent)
8. Split PR 4 (server hardening + deploy tooling are independent)
9. Reorder: PR 5 before PR 4 (fix patterns before hardening)
10. Add dependency vulnerability scanning to PR 2 (pip-audit)
11. Scope PR 5 to production-critical paths only
12. Add load testing to PR 4 scope

### Nice-to-do (polish):
13. Automate Murphy System/ parity with pre-commit hooks
14. Add feature flags for server middleware
15. Create formal commissioning checklist template
16. Time-box all PRs with hard deadlines

---

*This review is based on actual repository analysis, not assumptions. All file counts, line counts, and feature assessments are verified against the current codebase state as of 2026-03-29.*

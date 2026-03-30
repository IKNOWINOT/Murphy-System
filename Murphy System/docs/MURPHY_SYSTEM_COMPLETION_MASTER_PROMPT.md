# MURPHY SYSTEM — ITERATIVE COMPLETION PROMPT

> **Instructions:** Paste this entire prompt into a new Copilot session each time you want to continue work. The AI will scan the repository, determine current completion %, identify the next highest-priority workstream, and produce a PR or actionable code changes. Repeat until 100%.

---

## ROLE & AUTHORITY

You are a **Staff-level Platform Engineer** operating as the lead of a virtual engineering team composed of:

- **Staff SRE** — infrastructure, CI/CD, Docker, observability, reliability
- **Staff Backend Engineer** — Python, FastAPI, async, system design, API contracts
- **Staff ML/AI Engineer** — LLM integration, prompt engineering, RAG, vector stores, agent orchestration
- **Staff Security Engineer** — AuthN/AuthZ, secrets management, input validation, compliance
- **Staff QA/Test Engineer** — integration tests, E2E tests, coverage enforcement, chaos engineering
- **Technical Program Manager** — tracking completion %, unblocking dependencies, enforcing the roadmap

You make all implementation decisions using **industry best practices** from FAANG/tier-1 engineering organizations. When a choice must be made (library, pattern, architecture), choose the option that a principal engineer at a top-5 tech company would choose for a production system. Do not ask — decide and document the rationale in code comments.

---

## REFERENCE SPECIFICATION

This work is governed by the **"MURPHY SYSTEM — SPECIFICATIONS, GAP ANALYSIS & COMPLETION ROADMAP"** document, located at:

```
Murphy System/docs/MURPHY_SYSTEM_SPECIFICATIONS_GAP_ANALYSIS_COMPLETION_ROADMAP.md
```

That document defines:

- **5 Critical Gaps** (C-01 through C-05)
- **5 High-Priority Gaps** (H-01 through H-05)
- **6 Medium-Priority Gaps** (M-01 through M-06)
- **3 Low-Priority Gaps** (L-01 through L-03)
- **20 Recommended Incorporations** (INC-01 through INC-20)

The repository is: **`IKNOWINOT/Murphy-System`**

---

## EXECUTION PROTOCOL

Every time this prompt is entered, perform these steps **in order**:

### STEP 1 — AUDIT CURRENT STATE

Recursively scan the repository to determine which of the 20 INC items and 19 gaps are **closed**, **in-progress**, or **open**. Use these concrete signals:

| Signal | Means |
|--------|-------|
| `src/openai_compatible_provider.py` exists AND is >1KB AND `llm_controller.py` imports it | INC-01 CLOSED |
| `execution_compiler.py` is >1KB AND contains class `ExecutionCompiler` with `compile()` method | INC-02 CLOSED |
| Only ONE start script referenced across ALL README/GETTING_STARTED files | INC-03 CLOSED |
| `tests/test_e2e_smoke.py` exists AND `.github/workflows/ci.yml` exists | INC-04 CLOSED |
| Zero references to port 5000 or 8052 in docs (only 8000 or `MURPHY_PORT`) | INC-05 CLOSED |
| Server startup prints feature-availability summary based on env vars | INC-06 CLOSED |
| All 6 Rosetta P3 wiring tasks have code AND tests | INC-07 CLOSED |
| `playwright_task_definitions.py` is >5KB AND imports playwright | INC-08 CLOSED |
| `docker-compose.yml` exists at repo root or `Murphy System/` | INC-09 CLOSED |
| No duplicate directory pairs (comms/comms_system, supervisor/supervisor_system, etc.) | INC-10 CLOSED |
| A real SMTP/SendGrid integration exists with test | INC-11 CLOSED |
| Webhook receiver has E2E test proving inbound→trigger→execute | INC-12 CLOSED |
| `murphy_system_1.0_runtime.py` is <100KB (refactored into `runtime/` package) | INC-13 CLOSED |
| `pytest --cov` reports >80% on core paths | INC-14 CLOSED |
| `rag_vector_integration.py` imports a real vector store (chromadb/pinecone/etc.) | INC-15 CLOSED |
| Multi-tenant test with 2+ isolated sessions exists | INC-16 CLOSED |
| PostgreSQL or SQLite WAL persistence with migration script exists | INC-17 CLOSED |
| Rate limiting middleware + JWT validation on protected endpoints | INC-18 CLOSED |
| `pymodbus` or `asyncua` in requirements AND sensor read test exists | INC-19 CLOSED |
| `prometheus_metrics_exporter.py` tested with real metric emission | INC-20 CLOSED |

### STEP 2 — CALCULATE COMPLETION %

Use this weighted formula:

```
COMPLETION = Σ(closed_items × weight) / Σ(all_items × weight) × 100

Weights:
  Critical gaps (C-01..C-05):     10 points each  =  50 points max
  High-priority gaps (H-01..H-05): 6 points each  =  30 points max
  Medium gaps (M-01..M-06):        3 points each   =  18 points max
  Low gaps (L-01..L-03):           1 point each    =   3 points max
  ─────────────────────────────────────────────────
  TOTAL POSSIBLE:                                   101 points
```

**Gap-to-INC Mapping:**

```
INC-01 → C-01 (10pts)    INC-02 → C-02 (10pts)    INC-04 → C-03 (10pts)
INC-11 → C-04 (10pts)    INC-03 + INC-05 → C-05 (10pts)
INC-06 → H-01 (6pts)     INC-07 → H-03 (6pts)
H-02 closes when C-01 closes (6pts)
H-04 closes when INC-13 done (6pts)    H-05 closes when INC-17 done (6pts)
INC-09 → M-01 (3pts)     INC-05 → M-02 (3pts)     INC-08 → M-03 (3pts)
M-04 closes when requirements.txt has pinned versions (3pts)
INC-14 → M-05 (3pts)     M-06 closes when WebSocket test exists (3pts)
INC-10 → L-01 (1pt)      INC-13 → L-02 (1pt)      L-03 → 1 canonical doc (1pt)
```

### STEP 3 — PRINT STATUS DASHBOARD

Output this exact format (fill in actual values):

```
╔══════════════════════════════════════════════════════════════╗
║  MURPHY SYSTEM COMPLETION TRACKER                           ║
║  Repository: IKNOWINOT/Murphy-System                        ║
║  Scan Date:  2026-03-09 20:41:40                          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  OVERALL COMPLETION:  ██████░░░░░░░░░░░░░░  XX.X%           ║
║                                                              ║
║  CRITICAL (50 pts):   ░░░░░░░░░░  X/5 closed   XX pts      ║
║  HIGH     (30 pts):   ░░░░░░░░░░  X/5 closed   XX pts      ║
║  MEDIUM   (18 pts):   ░░░░░░░░░░  X/6 closed   XX pts      ║
║  LOW      ( 3 pts):   ░░░░░░░░░░  X/3 closed   XX pts      ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  ITEM STATUS:                                                ║
║                                                              ║
║  [C-01] LLM Provider            ❌ OPEN / ✅ CLOSED         ║
║  [C-02] Execution Compiler      ❌ OPEN / ✅ CLOSED         ║
║  [C-03] E2E Tests + CI          ❌ OPEN / ✅ CLOSED         ║
║  [C-04] Real Integration        ❌ OPEN / ✅ CLOSED         ║
║  [C-05] Canonical Startup       ❌ OPEN / ✅ CLOSED         ║
║  [H-01] Credential Validation   ❌ OPEN / ✅ CLOSED         ║
║  [H-02] Onboarding Flow         ❌ OPEN / ✅ CLOSED         ║
║  [H-03] Rosetta Wiring          ❌ OPEN / ✅ CLOSED         ║
║  [H-04] Frontend-Backend Wire   ❌ OPEN / ✅ CLOSED         ║
║  [H-05] Persistence Verified    ❌ OPEN / ✅ CLOSED         ║
║  [M-01] Docker Compose          ❌ OPEN / ✅ CLOSED         ║
║  [M-02] Port Consistency        ❌ OPEN / ✅ CLOSED         ║
║  [M-03] Playwright Automation   ❌ OPEN / ✅ CLOSED         ║
║  [M-04] Dependency Pinning      ❌ OPEN / ✅ CLOSED         ║
║  [M-05] Test Coverage >80%      ❌ OPEN / ✅ CLOSED         ║
║  [M-06] WebSocket Verified      ❌ OPEN / ✅ CLOSED         ║
║  [L-01] Dir Consolidation       ❌ OPEN / ✅ CLOSED         ║
║  [L-02] Runtime Refactored      ❌ OPEN / ✅ CLOSED         ║
║  [L-03] Doc Consolidation       ❌ OPEN / ✅ CLOSED         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### STEP 4 — SELECT NEXT WORK ITEM

Use this **strict priority order** (dependency-aware):

```
PHASE 1 — FOUNDATION (must be first; everything depends on these)
  1. INC-01 (C-01) — LLM Provider           [UNBLOCKS: H-02, all NL features]
  2. INC-03 + INC-05 (C-05) — Startup/Ports  [UNBLOCKS: onboarding, docs]
  3. INC-04 (C-03) — E2E Smoke Test + CI     [UNBLOCKS: confidence in changes]
  4. INC-02 (C-02) — Execution Compiler       [UNBLOCKS: two-phase execution]

PHASE 2 — CORE WIRING (enables basic operation)
  5. INC-06 (H-01) — Credential Validation
  6. M-04 — Pin Dependencies
  7. INC-10 (L-01) — Consolidate Directories
  8. INC-07 (H-03) — Rosetta Wiring

PHASE 3 — FIRST REAL AUTOMATION (proves the system works)
  9.  INC-11 (C-04) — Email Integration (SMTP/SendGrid)
  10. INC-12 — Webhook Receiver
  11. INC-09 (M-01) — Docker Compose
  12. INC-15 — RAG/Vector Knowledge Base

PHASE 4 — ROBUSTNESS (makes it reliable)
  13. ✅ INC-13 (L-02, H-04) — Refactor Runtime (COMPLETE — see src/runtime/)
  14. INC-14 (M-05) — Test Coverage to 80%+
  15. INC-08 (M-03) — Playwright Automation
  16. M-06 — WebSocket Verification
  17. L-03 — Documentation Consolidation

PHASE 5 — PRODUCTION (makes it deployable)
  18. INC-17 (H-05) — Production Persistence
  19. INC-18 — Security Hardening
  20. INC-16 — Multi-Tenant Testing
  21. INC-19 — Real IoT Protocols
  22. INC-20 — Monitoring & Alerting
```

**Always pick the lowest-numbered OPEN item.** If an item has a dependency that isn't closed, skip to the next unblocked item and note the blocked dependency.

### STEP 5 — IMPLEMENT

For the selected work item, produce a **complete, production-ready implementation** as a Pull Request. Follow these standards:

#### Code Standards

- **Python**: PEP 8, type hints on all public functions, docstrings (Google style), `logging` not `print`
- **Async**: Use `async/await` for all I/O-bound operations
- **Error handling**: Never bare `except:`. Catch specific exceptions. Always log with context.
- **Configuration**: All tunables via environment variables with sensible defaults
- **Secrets**: Never hardcode. Always `os.getenv()` with validation.
- **Tests**: Every new module gets a test file. Minimum: happy path + error path + edge case.
- **Imports**: Lazy imports for heavy dependencies. Guard with `try/except ImportError`.

#### Architecture Standards

- **12-Factor App**: Config in env, stateless processes, port binding, dev/prod parity
- **SOLID**: Single responsibility per module. Open for extension. Dependency injection.
- **Circuit Breaker**: All external API calls wrapped in circuit breaker pattern
- **Retry**: Exponential backoff with jitter for transient failures
- **Observability**: Structured logging (JSON), metrics emission, trace correlation IDs

#### PR Standards

- Branch name: `fix/[gap-id]-short-description` (e.g., `fix/c01-llm-provider`)
- Commit messages: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`)
- PR description references the gap ID and INC number
- Files changed listed explicitly
- Before/after behavior documented

### STEP 6 — UPDATE TRACKING

After implementing, re-scan and output the updated dashboard showing the new completion %.

---

## DECISION FRAMEWORK

When implementation choices arise, use this decision matrix:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM Provider SDK | `openai` Python package | Industry standard; works with OpenAI, Azure, DeepInfra, Ollama, vLLM, LiteLLM — one client for all |
| Vector Store | ChromaDB (local) → Pinecone (prod) | ChromaDB is zero-config for dev; Pinecone for production scale |
| Task Queue | `asyncio` built-in → Celery/Redis for scale | Start with stdlib; add Celery only when needed |
| Database | SQLite WAL mode (dev) → PostgreSQL (prod) | SQLite for zero-dependency dev; Postgres for ACID production |
| Secrets | `python-dotenv` + `os.getenv()` | No Vault complexity until multi-tenant production |
| HTTP Client | `httpx` (async) | Modern, async-native, HTTP/2 support, timeout defaults |
| Testing | `pytest` + `pytest-asyncio` + `pytest-cov` | Industry standard Python testing stack |
| CI/CD | GitHub Actions | Native to the repository host |
| Containerization | Docker + docker-compose | Standard; Kubernetes configs are premature |
| API Framework | FastAPI (already chosen) | Correct choice; keep it |
| Rate Limiting | `slowapi` (FastAPI middleware) | Lightweight, proven, FastAPI-native |
| Auth | JWT via `python-jose` + API keys | Standard dual-auth pattern |
| Monitoring | Prometheus client → Grafana | Industry standard observability stack |
| Browser Automation | Playwright (Python) | Microsoft-backed, async-native, multi-browser |
| Email | `aiosmtplib` + SendGrid SDK | Async SMTP for self-hosted; SendGrid for SaaS |

---

## QUALITY GATES

Before any PR is considered complete, verify:

- [ ] `python -m pytest tests/ -x --tb=short` passes with 0 failures
- [ ] No new `# TODO` or `# FIXME` without a linked gap ID
- [ ] All new files have module-level docstrings with copyright header
- [ ] No secrets or API keys in committed code
- [ ] Type hints on all public function signatures
- [ ] Logging uses structured format: `logger.info("msg", extra={...})`
- [ ] New endpoints have OpenAPI schema (FastAPI auto-generates from Pydantic)
- [ ] If a gap is being closed, the audit signal from STEP 1 now passes

---

## ANTI-PATTERNS TO AVOID

1. **No new stubs.** Every file created must be functional. If a feature needs an external service that isn't available, implement a mock adapter with a clear interface AND the real adapter, switchable via env var.
2. **No monolith growth.** Do not add code to `murphy_system_1.0_runtime.py`. All new logic goes in `src/` modules imported by the runtime.
3. **No phantom docs.** If documentation describes a feature, that feature must work. If it doesn't work yet, the docs must say "🚧 Coming Soon" with the gap ID.
4. **No orphan modules.** Every new module must be imported somewhere, registered in the capability map, and have at least one test.
5. **No implicit dependencies.** If module A needs module B, it must be in the import chain and in the dependency graph, not assumed to be loaded by the runtime.

---

## SESSION CONTINUITY

This prompt is designed to be **entered repeatedly**. Each session:

1. Scans the repo fresh (no stale assumptions)
2. Recalculates completion %
3. Picks up the next unfinished item
4. Produces working code
5. Shows updated progress

**The work is done when the dashboard reads 100% and all 19 gap items show ✅ CLOSED.**

---

*Reference: Murphy System/docs/MURPHY_SYSTEM_SPECIFICATIONS_GAP_ANALYSIS_COMPLETION_ROADMAP.md*
*Repository: IKNOWINOT/Murphy-System*
*License: BSL 1.1 — © 2020-2026 Murphy Collective — Created by Corey Post*
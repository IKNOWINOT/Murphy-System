# Murphy System — Documentation vs. Code Gap Analysis

## Date: 2026-03-24

---

## Phase 4 Closure Status (PR #407)

| Gap Category | Status | Notes |
|-------------|--------|-------|
| CRITICAL: MURPHY_API_KEY mismatch | ✅ Resolved | Code now accepts both MURPHY_API_KEY (canonical) and MURPHY_API_KEYS (legacy) |
| ARCH-001/002: Phantom entry point | ✅ Resolved | ARCHITECTURE_MAP.md and DEPENDENCY_GRAPH.md updated to reference src/runtime/app.py |
| API Routes (151 missing) | ✅ Resolved | API_ROUTES.md updated with all missing routes |
| API Routes (83 stale) | ✅ Resolved | Stale /api/comms/* routes marked as Planned/Not Yet Implemented |
| ENV-001+: .env.example canonical name | ✅ Resolved | MURPHY_API_KEY documented as canonical |
| SEC-001-008: Security docs gaps | ✅ Resolved | SECURITY.md updated with CSRF, rate limiting, brute-force, key rotation docs |
| DEPLOY-001+: Alembic/POSTGRES_PASSWORD | ✅ Resolved | DEPLOYMENT_GUIDE.md updated with Alembic migration steps |
| XREF-001-007: Broken links | ✅ Resolved | 25 broken relative links fixed across README.md, GETTING_STARTED.md, USER_MANUAL.md, CONTRIBUTING.md, SECURITY.md, docs/MONITORING.md |

---

## Methodology

This analysis was performed by:

1. **Code scan** — extracting all `@app.get/post/put/delete/patch` route decorators from
   `src/runtime/app.py`; all `os.environ`/`os.getenv` references across every `*.py` file
   in `src/`; all Python module files; all HTML page files; all shell scripts; all Docker
   and Kubernetes configuration files.
2. **Documentation scan** — extracting all documented API routes, environment variables,
   architecture claims, feature claims, setup steps, and cross-references from every
   Markdown file in the repository root, `docs/`, and `documentation/`.
3. **Cross-reference** — performing set-difference comparisons between code-extracted
   facts and documentation-extracted facts, then classifying each discrepancy.

**Tools used:** Python AST (for docstring detection), ripgrep pattern extraction,
Unix `comm`/`diff` for set diffing.

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Total gaps found | **279** |
| Critical gaps (code works differently than documented) | **8** |
| Missing documentation (code exists, no docs) | **195** |
| Stale documentation (docs exist, no code) | **59** |
| Minor discrepancies | **17** |

---

## Gap Catalog

---

### Category 1: API Routes

> **Summary:** 444 routes exist in `src/runtime/app.py`. 376 routes are documented in
> `API_ROUTES.md`. **151 routes exist in code but are absent from `API_ROUTES.md`**;
> **83 entries in `API_ROUTES.md` do not correspond to any route in the runtime.**

#### 1a. Routes in code but not documented (Missing Documentation)

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| API-001 | Missing Doc | src/runtime/app.py | — | `GET/POST/DELETE /api/admin/*` (13 endpoints: audit-log, organizations, sessions, stats, users, user reset/suspend/unsuspend) | High |
| API-002 | Missing Doc | src/runtime/app.py | — | `GET /api/ambient/stats` | Low |
| API-003 | Missing Doc | src/runtime/app.py | — | `GET/POST/GET /api/artifacts`, `/api/artifacts/create`, `/api/artifacts/{artifact_id}` | Medium |
| API-004 | Missing Doc | src/runtime/app.py | — | `POST /api/auar/provision` | Medium |
| API-005 | Missing Doc | src/runtime/app.py | — | `POST /api/auth/change-password`, `POST /api/auth/request-password-reset`, `GET /api/auth/reset-password/validate`, `POST /api/auth/reset-password` (password reset system) | High |
| API-006 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/automations/commission`, `/executions`, `/executions/{id}`, `/fire-trigger`, `/workflows/{id}`, `/workflows/{id}/execute` (6 endpoints) | High |
| API-007 | Missing Doc | src/runtime/app.py | — | `POST /api/billing/checkout`, `POST /api/billing/start-trial` | High |
| API-008 | Missing Doc | src/runtime/app.py | — | `GET/POST/GET /api/client-portfolio/*` (3 endpoints) | Medium |
| API-009 | Missing Doc | src/runtime/app.py | — | `GET /api/corrections/training-data` | Low |
| API-010 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/costs/*` (5 endpoints: assign, budget, by-bot, by-department, by-project, summary) | Medium |
| API-011 | Missing Doc | src/runtime/app.py | — | `GET /api/creator/moderation/check`, `GET /api/creator/moderation/status` | Low |
| API-012 | Missing Doc | src/runtime/app.py | — | `GET /api/credentials/*` (3 endpoints: metrics, profiles, profiles/{id}/interactions, store) | Medium |
| API-013 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/demo/*` (3 endpoints) | Low |
| API-014 | Missing Doc | src/runtime/app.py | — | `GET /api/diagnostics/activation`, `GET /api/diagnostics/activation/last` | Low |
| API-015 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/documents/*` (6 endpoints: blocks, gates, magnify, simplify, solidify) | High |
| API-016 | Missing Doc | src/runtime/app.py | — | `GET/DELETE /api/domains/{did}`, `POST /api/domains/{did}/verify` | Medium |
| API-017 | Missing Doc | src/runtime/app.py | — | `GET /api/efficiency/costs` | Low |
| API-018 | Missing Doc | src/runtime/app.py | — | `GET /api/events/history/{subscriber_id}`, `GET /api/events/stream/{subscriber_id}` | Medium |
| API-019 | Missing Doc | src/runtime/app.py | — | `POST /api/feedback` | Low |
| API-020 | Missing Doc | src/runtime/app.py | — | `GET /api/flows/inbound`, `outbound`, `processing`, `state` (4 endpoints) | Medium |
| API-021 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/forms/*` (7 endpoints: correction, list, plan-generation, plan-upload, submission, task-execution, validation, form_type) | High |
| API-022 | Missing Doc | src/runtime/app.py | — | `GET /api/golden-path`, `GET /api/golden-path/{workflow_id}` | Medium |
| API-023 | Missing Doc | src/runtime/app.py | — | `GET /api/graph/health`, `POST /api/graph/query` | Medium |
| API-024 | Missing Doc | src/runtime/app.py | — | `GET /api/heatmap/coverage` | Low |
| API-025 | Missing Doc | src/runtime/app.py | — | `GET /api/hitl-graduation/candidates`, `GET /api/hitl/pending`, `/hitl/queue`, `/hitl/statistics`, `POST /api/hitl/interventions/{id}/respond`, `POST /api/hitl/{tid}/decide` (6 endpoints) | High |
| API-026 | Missing Doc | src/runtime/app.py | — | `GET /api/images/generate`, `/images/stats`, `/images/styles` | Medium |
| API-027 | Missing Doc | src/runtime/app.py | — | `GET /api/integrations/active`, `POST /api/integrations/add`, `/wire`, `/{id}/approve`, `/{id}/reject` | Medium |
| API-028 | Missing Doc | src/runtime/app.py | — | `GET /api/legal/privacy`, `GET /api/legal/terms` | Low |
| API-029 | Missing Doc | src/runtime/app.py | — | `POST /api/onboarding/finalize`, `POST /api/onboarding/mfgc-chat` | Medium |
| API-030 | Missing Doc | src/runtime/app.py | — | `POST /api/org/create`, 9× `/api/org/portal/{org_id}/*` endpoints | High |
| API-031 | Missing Doc | src/runtime/app.py | — | `GET /api/orgchart/inoni-agents` | Low |
| API-032 | Missing Doc | src/runtime/app.py | — | `GET /api/platform/automation-status`, `GET /api/platform/capabilities` | Low |
| API-033 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/repair/*` (5 endpoints: history, proposals, run, status, wiring) | Medium |
| API-034 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/scheduler/*` (4 endpoints: start, status, stop, trigger) | Medium |
| API-035 | Missing Doc | src/runtime/app.py | — | `GET /api/sdk/status` | Low |
| API-036 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/self-automation/*`, `/self-fix/*`, `/self-improvement/*` (9 endpoints) | High |
| API-037 | Missing Doc | src/runtime/app.py | — | `POST /api/sessions/create` | Low |
| API-038 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/setup/api-collection/*` (5 endpoints) and `/api/setup/checklist` | Medium |
| API-039 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/swarm/*` (5 endpoints: execute, phase, propose, rosetta, status) | High |
| API-040 | Missing Doc | src/runtime/app.py | — | `GET /api/usage/daily` | Low |
| API-041 | Missing Doc | src/runtime/app.py | — | `GET/POST /api/wingman/*` (6 endpoints) | Medium |
| API-042 | Missing Doc | src/runtime/app.py | — | `POST /api/workflow-terminal/execute`, `POST /api/workflows/generate`, `POST /api/workflows/{workflow_id}/execute` | High |
| API-043 | Missing Doc | src/runtime/app.py | — | `GET /favicon.ico` | Low |

#### 1b. Routes documented but absent from code (Stale Documentation)

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| API-044 | Stale Doc | — | API_ROUTES.md | `GET/POST /api/comms/*` (27 endpoints: email, IM threads, video sessions, voice sessions) | High |
| API-045 | Stale Doc | — | API_ROUTES.md | `GET /api/domains/{id}/verify` (different path format from code's `/api/domains/{did}/verify`) | Low |
| API-046 | Stale Doc | — | API_ROUTES.md | `GET/POST /api/events/history/{id}`, `/events/stream/{id}` (uses `{id}` not `{subscriber_id}`) | Low |
| API-047 | Stale Doc | — | API_ROUTES.md | `POST /api/hitl/interventions/{id}/respond` (code uses `{intervention_id}` not `{id}`) | Low |
| API-048 | Stale Doc | — | API_ROUTES.md | `POST /api/hitl/{id}/decide` (code uses `{tid}` not `{id}`) | Low |
| API-049 | Stale Doc | — | API_ROUTES.md | `GET/POST /api/moderator/*` (17 endpoints: audit, automod, broadcast, users) — no corresponding implementation | High |
| API-050 | Stale Doc | — | API_ROUTES.md | `GET/POST/DELETE /api/presets/*` (3 endpoints) | Medium |
| API-051 | Stale Doc | — | API_ROUTES.md | `GET /api/profiles/me` (code has `/api/profiles/me/terminal-config` but not just `/me`) | Low |
| API-052 | Stale Doc | — | API_ROUTES.md | `GET/POST/PUT/DELETE /api/system-updates/*` (16 endpoints) | High |
| API-053 | Stale Doc | — | API_ROUTES.md | `GET/POST /api/trading/backtest`, `/trading/calibration/*`, `/trading/paper/*` (11 endpoints) | High |
| API-054 | Stale Doc | — | API_ROUTES.md | `POST /api/vci/parse`, `/vci/process`, `/vci/recognise` | Medium |
| API-055 | Stale Doc | — | API_ROUTES.md | `POST /api/auth/register` documented as an alias for signup — code has both but docs list it separately as if it's unique | Low |
| API-056 | Stale Doc | — | API_ROUTES.md | `GET /api/` (root listed but code has no bare `/api/` route) | Low |
| API-057 | Stale Doc | — | API_ROUTES.md | `GET /api/endpoints.py` (clearly a documentation typo — not a real route) | Medium |

#### 1c. Critical route discrepancies

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| API-058 | Incorrect Doc | src/runtime/app.py:10706 | API_ROUTES.md, .env.example | Auth key env var is `MURPHY_API_KEY` (singular) in code, but `.env.example` and comments say `MURPHY_API_KEYS` (plural). `API_ROUTES.md` says `MURPHY_API_KEY`. | Critical |

---

### Category 2: Environment Variables

> **Summary:** 205 environment variables are referenced in `src/*.py` but absent from
> `.env.example`. 33 variables appear in `.env.example` but are not referenced anywhere
> in the source code.

#### 2a. Environment variables in code but not in `.env.example` (Missing Documentation)

A selection of the highest-impact missing env vars (full list: 205 total):

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| ENV-001 | Missing Doc | src/ (multiple) | — | `ALPACA_API_KEY`, `ALPACA_API_SECRET` — trading system API credentials | High |
| ENV-002 | Missing Doc | src/ (multiple) | — | `ALPHA_VANTAGE_API_KEY` — market data API key | Medium |
| ENV-003 | Missing Doc | src/ (multiple) | — | `AUAR_*` (12 vars) — AUAR routing and ML configuration | Medium |
| ENV-004 | Missing Doc | src/ (multiple) | — | `BINANCE_API_KEY`, `BINANCE_API_SECRET` — crypto exchange credentials | High |
| ENV-005 | Missing Doc | src/ (multiple) | — | `CHROMADB_PATH`, `CHROMADB_COLLECTION` — vector DB config | Medium |
| ENV-006 | Missing Doc | src/ (multiple) | — | `COINBASE_API_KEY`, `COINBASE_API_SECRET`, `COINBASE_COMMERCE_API_KEY`, `COINBASE_WEBHOOK_SECRET`, `COINBASE_LIVE_MODE` | High |
| ENV-007 | Missing Doc | src/ (multiple) | — | `COMPLIANCE_MIN_PAPER_DAYS`, `COMPLIANCE_MIN_PROFITABLE_DAYS`, `COMPLIANCE_MIN_RETURN_PCT` | Medium |
| ENV-008 | Missing Doc | src/ (multiple) | — | `DATABASE_URL`, `DB_BUSY_TIMEOUT`, `DB_POOL_SIZE`, `DB_WAL_MODE` | High |
| ENV-009 | Missing Doc | src/ (multiple) | — | `FLASK_DEBUG` — Flask debug flag used alongside FastAPI | Medium |
| ENV-010 | Missing Doc | src/ (multiple) | — | `IBKR_CLIENT_ID`, `IBKR_HOST`, `IBKR_PORT` — Interactive Brokers connection | High |
| ENV-011 | Missing Doc | src/ (multiple) | — | `IEX_CLOUD_API_KEY`, `IEX_TOKEN` — IEX market data keys | Medium |
| ENV-012 | Missing Doc | src/ (multiple) | — | `LIVE_TRADING_ENABLED` — safety gate for live trading | Critical |
| ENV-013 | Missing Doc | src/ (multiple) | — | `MATRIX_*` (16 vars) — Matrix chat protocol integration | Medium |
| ENV-014 | Missing Doc | src/ (multiple) | — | `MFM_*` (9 vars) — Murphy Fine-tuning Model configuration | Medium |
| ENV-015 | Missing Doc | src/ (multiple) | — | `MURPHY_API_KEY` (singular) — the actual runtime auth key (vs. the `MURPHY_API_KEYS` in `.env.example`) | Critical |
| ENV-016 | Missing Doc | src/ (multiple) | — | `MURPHY_CSRF_SECRET`, `MURPHY_CSRF_TTL` — CSRF protection keys | High |
| ENV-017 | Missing Doc | src/ (multiple) | — | `MURPHY_CREDENTIAL_MASTER_KEY` — master encryption key | Critical |
| ENV-018 | Missing Doc | src/ (multiple) | — | `MURPHY_FOUNDER_EMAIL`, `MURPHY_FOUNDER_PASSWORD` — founder account seeding | High |
| ENV-019 | Missing Doc | src/ (multiple) | — | `MURPHY_JWT_SECRET`, `MURPHY_JWT_ALGORITHM`, `MURPHY_JWT_ISSUER` | High |
| ENV-020 | Missing Doc | src/ (multiple) | — | `MURPHY_OAUTH_GOOGLE_CLIENT_ID`, `MURPHY_OAUTH_GOOGLE_SECRET`, `MURPHY_OAUTH_REDIRECT_URI` | High |
| ENV-021 | Missing Doc | src/ (multiple) | — | `MURPHY_RATE_LIMIT_RPM`, `MURPHY_RATE_LIMIT_BURST`, `MURPHY_RATE_LIMIT_SWARM_*` | Medium |
| ENV-022 | Missing Doc | src/ (multiple) | — | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_SECRET`, and 5 PAYPAL plan IDs | High |
| ENV-023 | Missing Doc | src/ (multiple) | — | `POLYGON_API_KEY` — market data key | Medium |
| ENV-024 | Missing Doc | src/ (multiple) | — | `SCADA_BACNET_IP`, `SCADA_MODBUS_HOST`, `SCADA_OPCUA_URL` — industrial SCADA connections | Medium |
| ENV-025 | Missing Doc | src/ (multiple) | — | `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` | Medium |
| ENV-026 | Missing Doc | src/ (multiple) | — | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_FROM_EMAIL` | High |
| ENV-027 | Missing Doc | src/ (multiple) | — | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, and 6 Stripe price IDs | High |
| ENV-028 | Missing Doc | src/ (multiple) | — | `SWEEP_ASSET`, `SWEEP_HOUR`, `SWEEP_MINUTE`, `SWEEP_TIMEZONE`, `PROFIT_SWEEP_ENABLED` | Medium |
| ENV-029 | Missing Doc | src/ (multiple) | — | `WEBHOOK_SECRET_GITHUB`, `WEBHOOK_SECRET_STRIPE` | High |
| ENV-030 | Missing Doc | src/ (multiple) | — | `WULFRUM_API_KEY`, `WULFRUM_API_URL` — fuzzy-match engine (partially in `.env.example` as commented) | Low |

#### 2b. Environment variables in `.env.example` but not referenced in code (Stale Documentation)

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| ENV-031 | Stale Doc | — | .env.example | `AIRTABLE_API_KEY` — no code reference found | Low |
| ENV-032 | Stale Doc | — | .env.example | `ASANA_ACCESS_TOKEN` — no code reference found | Low |
| ENV-033 | Stale Doc | — | .env.example | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — no code reference found | Low |
| ENV-034 | Stale Doc | — | .env.example | `COINBASE_PROD_URL`, `COINBASE_SANDBOX_URL` — code uses `COINBASE_API_KEY` pattern instead | Low |
| ENV-035 | Stale Doc | — | .env.example | `DATADOG_API_KEY` — no code reference found | Low |
| ENV-036 | Stale Doc | — | .env.example | `DEBUG`, `AUTO_RELOAD`, `ENABLE_CORS` — not used in src/ | Low |
| ENV-037 | Stale Doc | — | .env.example | `GITHUB_TOKEN` — no code reference found | Low |
| ENV-038 | Stale Doc | — | .env.example | `GRAFANA_ADMIN_PASSWORD`, `GRAFANA_ADMIN_USER` — only in docker-compose, not src/ | Low |
| ENV-039 | Stale Doc | — | .env.example | `HUBSPOT_API_KEY`, `JIRA_API_TOKEN`, `MONDAY_API_KEY`, `NOTION_API_KEY`, `PIPEDRIVE_API_TOKEN`, `SALESFORCE_CONSUMER_KEY` | Low |
| ENV-040 | Stale Doc | — | .env.example | `STRIPE_SECRET_KEY` — code uses `STRIPE_API_KEY` | Medium |
| ENV-041 | Stale Doc | — | .env.example | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` — no code reference found | Low |
| ENV-042 | Stale Doc | — | .env.example | `ZOOM_API_KEY` — no code reference found | Low |
| ENV-043 | Stale Doc | — | .env.example | `MURPHY_MAIL_DOMAIN`, `MURPHY_MAIL_ENABLED`, `MURPHY_MAIL_HOSTNAME`, `MURPHY_WEBMAIL_PORT` — not referenced in src/ | Low |
| ENV-044 | Stale Doc | — | .env.example | `GOOGLE_ANALYTICS_API_KEY` — no code reference found | Low |
| ENV-045 | Stale Doc | — | .env.example | `PAGERDUTY_API_KEY`, `OPENWEATHER_API_KEY` — no code reference found | Low |

#### 2c. Critical env var discrepancy

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| ENV-046 | Incorrect Doc | src/runtime/app.py:10706 | .env.example, SECURITY.md | Code reads `MURPHY_API_KEY` (singular) but `.env.example` and comments throughout use `MURPHY_API_KEYS` (plural). This is the primary API authentication variable. Operators setting `MURPHY_API_KEYS` will find authentication broken. | Critical |

---

### Category 3: Configuration Options

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| CFG-001 | Incorrect Doc | k8s/configmap.yaml | DEPLOYMENT_GUIDE.md | K8s ConfigMap uses `MURPHY_CORS_ORIGINS` but DEPLOYMENT_GUIDE.md does not document this variable | Medium |
| CFG-002 | Missing Doc | src/runtime/app.py | — | `MURPHY_DB_MODE` (live/test/stub) — controls database backend selection; undocumented | High |
| CFG-003 | Missing Doc | src/runtime/app.py | — | `MURPHY_RUNTIME_MODE` — undocumented runtime mode switch | Medium |
| CFG-004 | Missing Doc | src/runtime/app.py | — | `MURPHY_POOL_MODE` — connection pool mode; undocumented | Medium |
| CFG-005 | Missing Doc | src/ (multiple) | — | `MURPHY_MAX_BODY_BYTES`, `MURPHY_MAX_RESPONSE_SIZE_MB` — request/response size limits; undocumented | Medium |
| CFG-006 | Missing Doc | src/ | — | `MURPHY_AUTH_LOCKOUT_SECONDS`, `MURPHY_AUTH_MAX_ATTEMPTS`, `MURPHY_AUTH_WINDOW_SECONDS` — brute-force protection config; undocumented | High |
| CFG-007 | Missing Doc | src/ | — | `MURPHY_KEY_ROTATION_INTERVAL`, `MURPHY_KEY_ROTATION_OVERLAP` — automatic key rotation config; undocumented | High |
| CFG-008 | Stale Doc | — | GETTING_STARTED.md | `Murphy System/config/murphy.yaml` is referenced as containing "sensible defaults"; file exists in `config/` at root, not `Murphy System/config/` | Low |
| CFG-009 | Missing Doc | docker-compose.yml | DEPLOYMENT_GUIDE.md | `MURPHY_DB_MODE=live` is injected via docker-compose environment but not documented in DEPLOYMENT_GUIDE.md | Medium |
| CFG-010 | Stale Doc | — | MURPHY_1.0_QUICK_START.md | References `requirements_murphy_1.0.txt` as the primary requirements file; multiple requirements files exist (`requirements.txt`, `requirements_ci.txt`, `requirements_core.txt`, `requirements_murphy_1.0.txt`) with no documentation on which to use when | Medium |

---

### Category 4: Architecture Claims

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| ARCH-001 | Incorrect Doc | — | ARCHITECTURE_MAP.md | `murphy_complete_backend_extended.py` is the documented primary backend entry point in the architecture diagram, but this file does not exist. Actual entry point is `src/runtime/app.py`. | Critical |
| ARCH-002 | Incorrect Doc | src/runtime/app.py | ARCHITECTURE_MAP.md | Architecture diagram shows REST API entry as `FastAPI - Port 8000` via `murphy_complete_backend_extended.py`. Entry point is `src/runtime/app.py`; `murphy_complete_backend_extended.py` is referenced but absent. | Critical |
| ARCH-003 | Missing Doc | src/ | ARCHITECTURE_MAP.md | `src/` contains 522+ modules not represented in the architecture diagram. Many subsystems (e.g., `auar/`, `billing/`, `matrix_bridge/`, `trading/`, `additive_manufacturing_connectors.py`, `ambient_*`) are missing from the architecture overview. | High |
| ARCH-004 | Stale Doc | — | ARCHITECTURE_MAP.md | References `murphy_terminal.py` (96KB) as a terminal UI component. File exists at root but is not integrated via imports in `src/runtime/app.py`. | Medium |
| ARCH-005 | Incorrect Doc | src/ | LLM_SUBSYSTEM.md | LLM_SUBSYSTEM.md states the model probe order starts with `phi3`. `src/llm_integration_layer.py` and related files may use different defaults depending on `OLLAMA_MODEL` env var (which is absent from `.env.example`). | Medium |
| ARCH-006 | Missing Doc | src/aionmind/ | — | `src/aionmind/` directory contains an entire cognitive pipeline subsystem (AionMind 2.0a). ARCHITECTURE_MAP.md mentions it by name but provides no structural documentation. | High |
| ARCH-007 | Missing Doc | src/deterministic_compute_plane/ | — | `DeterministicComputePlane` is a major dispatch subsystem. Not documented in ARCHITECTURE_MAP.md beyond passing mention. | High |
| ARCH-008 | Missing Doc | src/founder_update_orchestrator.py | — | `FounderUpdateOrchestrator` with 19 `RecommendationType` values. FastAPI router at `/api/founder/`. Not documented in ARCHITECTURE_MAP.md or API_ROUTES.md. | Medium |
| ARCH-009 | Missing Doc | src/founder_maintenance_recommendation_engine.py | — | `FounderMaintenanceRecommendationEngine` at `/api/founder/maintenance/`. Not in ARCHITECTURE_MAP.md or API_ROUTES.md. | Medium |
| ARCH-010 | Missing Doc | src/system_update_recommendation_engine.py | — | `SystemUpdateRecommendationEngine` (ARCH-020 in internal tracking). Not documented in ARCHITECTURE_MAP.md; API_ROUTES.md has some `/api/system-updates/*` routes (stale) that don't match the actual implementation. | High |
| ARCH-011 | Stale Doc | — | ARCHITECTURE_MAP.md | Architecture diagram references `Murphy System/` directory as containing system modules, implying it is a first-class source directory. In practice it is a mirror of root HTML/JS/test files for a different serve context. | Low |

---

### Category 5: Setup / Installation Steps

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| SETUP-001 | Incorrect Doc | — | GETTING_STARTED.md | `GETTING_STARTED.md` references `<Murphy System/src/nocode_workflow_terminal.py>`, `<Murphy System/src/ai_workflow_generator.py>`, `<Murphy System/src/execution_engine/workflow_orchestrator.py>`, `<Murphy System/src/gate_execution_wiring.py>`, `<Murphy System/workflow_canvas.html>` as clickable links. These paths do not resolve from the repository root — they should be `src/nocode_workflow_terminal.py` etc. | Medium |
| SETUP-002 | Incorrect Doc | — | README.md | `README.md` links to `<Murphy System/src/ai_workflow_generator.py>`, `Murphy%20System/MURPHY_1.0_QUICK_START.md`, `Murphy%20System/API_DOCUMENTATION.md`, `Murphy%20System/DEPLOYMENT_GUIDE.md`, `Murphy%20System/strategic/PRODUCTION_READINESS_AUDIT.md`, `<Murphy System/documentation/api/AUTHENTICATION.md>` — all broken relative links (25 broken links found in root *.md files). | High |
| SETUP-003 | Incorrect Doc | — | SECURITY.md | `SECURITY.md` links to `Murphy%20System/DEPLOYMENT_GUIDE.md` — broken relative link | Low |
| SETUP-004 | Incorrect Doc | — | USER_MANUAL.md | `USER_MANUAL.md` links to `../LICENSE` — broken relative link (LICENSE is at repo root, not in a parent directory of where USER_MANUAL.md lives) | Low |
| SETUP-005 | Incorrect Doc | GETTING_STARTED.md | — | `GETTING_STARTED.md` step 2 says `setup_and_start.sh` "Creates a virtual environment and installs dependencies from `requirements_murphy_1.0.txt`". Multiple requirements files exist but no documentation on their purpose or when each is used. | Medium |
| SETUP-006 | Missing Doc | install.sh, start.sh | — | `install.sh` and `start.sh` exist at the repository root but are not mentioned in `GETTING_STARTED.md`. `setup_and_start.sh` is the only install method documented. | Medium |
| SETUP-007 | Incorrect Doc | — | README.md | `README.md` shows `python -m src.runtime.boot` as the start command. The actual file is `src/runtime/boot.py` but `GETTING_STARTED.md` uses `bash setup_and_start.sh`. Both exist, but the README start command is not the primary recommended path. | Low |

---

### Category 6: Feature Claims

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| FEAT-001 | Incorrect Doc | — | README.md badge | README.md badge claims `tests-17368 passing`. Actual test function count from `tests/*.py` is approximately 24,246. Test pass rate is separately documented as "1,611 verified passing". Badge count is inconsistent. | Medium |
| FEAT-002 | Missing Doc | src/agent_module_loader.py | — | `MultiCursorBrowser` with 70 action types is not documented in USER_MANUAL.md or ARCHITECTURE_MAP.md despite being a major UI interaction subsystem. | High |
| FEAT-003 | Missing Doc | src/agent_module_loader.py | — | `ToolRegistry` with 194 tools is not documented in USER_MANUAL.md or API_ROUTES.md | High |
| FEAT-004 | Missing Doc | src/agent_module_loader.py | — | `HITLModalSystem` (Human-in-the-Loop modals) and `CreationChainManager` are undocumented features in USER_MANUAL.md | High |
| FEAT-005 | Missing Doc | src/agent_module_loader.py | — | `LibrarianExecutionSuggestor` (Copilot-style PR suggestions) is not documented | Medium |
| FEAT-006 | Missing Doc | src/trading/ | — | Trading subsystem (paper trading, compliance, graduation, emergency stop) is present in code but only partially documented in API_ROUTES.md and not in ARCHITECTURE_MAP.md or USER_MANUAL.md | High |
| FEAT-007 | Missing Doc | src/billing/ | — | Billing subsystem (Stripe, PayPal, Coinbase integration, subscription tiers, trials) present in code but the billing section of documentation does not cover PayPal or Coinbase flows | Medium |
| FEAT-008 | Missing Doc | src/additive_manufacturing_connectors.py | — | Additive manufacturing (3D printing) integration exists in code and has a docs/ADDITIVE_MANUFACTURING_INTEGRATION_PLAN.md, but is not mentioned in README.md feature list | Low |
| FEAT-009 | Missing Doc | src/auar/ | — | AUAR (Autonomous Uncertainty-Aware Routing) subsystem has 12 tunable env vars and a FastAPI sub-router but is not described in ARCHITECTURE_MAP.md | Medium |
| FEAT-010 | Stale Doc | — | ROADMAP.md | ROADMAP.md contains sections marked as `TODO` or future plans for features that already exist in code (e.g., multi-org support, self-healing, trading compliance). ROADMAP.md has not been reconciled with what was actually delivered. | Medium |
| FEAT-011 | Missing Doc | src/matrix_bridge/ | — | Matrix (Element/chat) protocol bridge is an entire subsystem (16 env vars) with no documentation in README.md, USER_MANUAL.md, or ARCHITECTURE_MAP.md | High |
| FEAT-012 | Missing Doc | src/scada/ (env vars) | — | SCADA industrial protocol support (BACnet, Modbus, OPC-UA) via env vars is undocumented anywhere in user-facing docs | High |
| FEAT-013 | Stale Doc | — | STATUS.md | `STATUS.md` contains a `TODO` item and references milestones that are marked complete in code but the status document has not been updated | Low |

---

### Category 7: Security Documentation

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| SEC-001 | Critical | src/runtime/app.py:10706 | .env.example, API_ROUTES.md, SECURITY.md | `MURPHY_API_KEY` vs `MURPHY_API_KEYS` mismatch (see ENV-046, API-058). Operators reading `.env.example` will configure `MURPHY_API_KEYS` but authentication checks `MURPHY_API_KEY`. Production deployments may run with no effective API key. | Critical |
| SEC-002 | Missing Doc | src/fastapi_security.py, src/flask_security.py | SECURITY.md | CSRF protection (`_CSRFProtection` class and `FlaskCSRFProtection`) is implemented but not documented in SECURITY.md | High |
| SEC-003 | Missing Doc | src/secure_key_manager.py | SECURITY.md | `ScheduledKeyRotator` with `MURPHY_KEY_ROTATION_INTERVAL` and `MURPHY_KEY_ROTATION_OVERLAP` env vars implements automatic key rotation; SECURITY.md does not mention this | High |
| SEC-004 | Missing Doc | src/input_validation.py | SECURITY.md | `FileUploadInput`, `WebhookPayloadInput`, `APIParameterInput` input sanitisation classes are implemented but not documented in SECURITY.md | Medium |
| SEC-005 | Missing Doc | src/ | SECURITY.md | `MURPHY_AUTH_LOCKOUT_SECONDS`, `MURPHY_AUTH_MAX_ATTEMPTS`, `MURPHY_AUTH_WINDOW_SECONDS` implement brute-force protection that is not documented in SECURITY.md | High |
| SEC-006 | Missing Doc | src/runtime/app.py | SECURITY.md | Rate-limit response headers (`X-RateLimit-*`) are added to responses but not documented | Low |
| SEC-007 | Incorrect Doc | src/runtime/app.py | SECURITY.md | SECURITY.md states sessions are stored in `_session_store` (in-memory dict) and recommends replacing with Redis. The DEPLOYMENT_GUIDE.md does not warn that the default in-memory session store is not safe for multi-process/multi-replica deployments. | High |
| SEC-008 | Missing Doc | — | SECURITY.md | `MURPHY_CSRF_SECRET` and `MURPHY_CSRF_TTL` are security-critical but absent from SECURITY.md and `.env.example` | High |

---

### Category 8: Deployment Documentation

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| DEP-001 | Incorrect Doc | — | DEPLOYMENT_GUIDE.md | Dockerfile and `docker-compose.yml` include a `murphy-mailserver` and `murphy-webmail` (Roundcube) service. DEPLOYMENT_GUIDE.md does not document these services or how to configure them. | Medium |
| DEP-002 | Missing Doc | k8s/ | DEPLOYMENT_GUIDE.md | K8s manifests include `hpa.yaml` (HorizontalPodAutoscaler), `limit-range.yaml`, `resource-quota.yaml`, `pdb.yaml` (PodDisruptionBudget) but DEPLOYMENT_GUIDE.md does not explain these resources or recommended resource limits. | Medium |
| DEP-003 | Missing Doc | k8s/staging/ | DEPLOYMENT_GUIDE.md | A `k8s/staging/` directory exists (staging K8s config) but is not mentioned in DEPLOYMENT_GUIDE.md | Low |
| DEP-004 | Incorrect Doc | docker-compose.yml | DEPLOYMENT_GUIDE.md | `docker-compose.yml` requires `POSTGRES_PASSWORD` to be set (fails with error if absent) but DEPLOYMENT_GUIDE.md does not list `POSTGRES_PASSWORD` as a required variable | High |
| DEP-005 | Missing Doc | docker-compose.hetzner.yml | DEPLOYMENT_GUIDE.md | `docker-compose.hetzner.yml` and `scripts/hetzner_load.sh` implement a distinct Hetzner-specific stack that is only partially covered in DEPLOYMENT_GUIDE.md | Medium |
| DEP-006 | Missing Doc | fleet_manifests/ | DEPLOYMENT_GUIDE.md | `fleet_manifests/` directory (Rancher Fleet GitOps configs) is not mentioned in DEPLOYMENT_GUIDE.md | Low |
| DEP-007 | Missing Doc | deploy/ | DEPLOYMENT_GUIDE.md | `deploy/` directory (deployment scripts) is not described in DEPLOYMENT_GUIDE.md | Low |
| DEP-008 | Incorrect Doc | k8s/configmap.yaml | DEPLOYMENT_GUIDE.md | K8s ConfigMap uses `MURPHY_DATA_DIR=/app/data` but Dockerfile and DEPLOYMENT_GUIDE.md reference `/app/data` inconsistently with `MURPHY_PERSISTENCE_DIR` in `.env.example` | Low |
| DEP-009 | Missing Doc | grafana/, prometheus-rules/ | DEPLOYMENT_GUIDE.md | Grafana dashboards (`grafana/dashboards/`) and Prometheus alerting rules (`prometheus-rules/murphy-alerts.yml`) exist but are not documented in DEPLOYMENT_GUIDE.md or monitoring docs | Medium |
| DEP-010 | Incorrect Doc | — | DEPLOYMENT_GUIDE.md | DEPLOYMENT_GUIDE.md references Python 3.10+ requirement. `setup.py` states `python_requires=">=3.10"`. System is tested on Python 3.12. No explicit 3.12 compatibility statement exists. | Low |
| DEP-011 | Missing Doc | alembic/ | DEPLOYMENT_GUIDE.md | Alembic database migration system (`alembic/`, `alembic.ini`) is present but not mentioned in DEPLOYMENT_GUIDE.md. Database migrations are undocumented. | High |

---

### Category 9: Python Modules Without Docstrings

> **Summary:** 28 Python modules in `src/` have no module-level docstring, violating the
> requirement that all modules have at least a docstring. The affected modules are
> concentrated in `src/billing/grants/submission/`.

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| DOC-001 | Missing Doc | src/billing/grants/api.py | — | Module has no docstring | Low |
| DOC-002 | Missing Doc | src/billing/grants/submission/submission_manager.py | — | Module has no docstring | Low |
| DOC-003 | Missing Doc | src/billing/grants/submission/models.py | — | Module has no docstring | Low |
| DOC-004 | Missing Doc | src/billing/grants/submission/__init__.py | — | Module has no docstring | Low |
| DOC-005 | Missing Doc | src/billing/grants/submission/submission_tracker.py | — | Module has no docstring | Low |
| DOC-006 | Missing Doc | src/billing/grants/submission/api_clients/base_client.py | — | Module has no docstring | Low |
| DOC-007 | Missing Doc | src/billing/grants/submission/api_clients/sam_gov_api.py | — | Module has no docstring | Low |
| DOC-008 | Missing Doc | src/billing/grants/submission/api_clients/__init__.py | — | Module has no docstring | Low |
| DOC-009 | Missing Doc | src/billing/grants/submission/api_clients/grants_gov_api.py | — | Module has no docstring | Low |
| DOC-010 | Missing Doc | src/billing/grants/submission/portal_instructions/*.py | — | 8 portal instruction files have no docstrings | Low |
| DOC-011 | Missing Doc | src/billing/grants/submission/format_adapters/*.py | — | Multiple format adapter files have no docstrings | Low |

---

### Category 10: Placeholder / TODO Text in Documentation

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| TODO-001 | Stale Doc | — | ARCHITECTURE_MAP.md | Contains 1 TODO marker | Low |
| TODO-002 | Stale Doc | — | CHANGELOG.md | Contains 2 TODO markers | Low |
| TODO-003 | Stale Doc | — | README.md | Contains 2 TODO markers | Low |
| TODO-004 | Stale Doc | — | STATUS.md | Contains 1 TODO marker | Low |
| TODO-005 | Stale Doc | — | docs/DESIGN_SYSTEM.md | Contains 5 TODO markers | Low |
| TODO-006 | Stale Doc | — | docs/K8S_PRODUCTION_HARDENING.md | Contains 1 TODO marker | Low |
| TODO-007 | Stale Doc | — | docs/KNOWN_ISSUES.md | Contains 1 TODO marker | Low |
| TODO-008 | Stale Doc | — | docs/LAUNCH_AUTOMATION_PLAN.md | Contains 1 TODO marker | Low |
| TODO-009 | Stale Doc | — | docs/MURPHY_CODE_HEALER.md | Contains 1 TODO marker | Low |
| TODO-010 | Stale Doc | — | docs/MURPHY_SYSTEM_COMPLETION_MASTER_PROMPT.md | Contains 1 TODO marker | Low |
| TODO-011 | Stale Doc | — | docs/MURPHY_SYSTEM_SPECIFICATIONS_GAP_ANALYSIS_COMPLETION_ROADMAP.md | Contains 1 TODO marker | Low |
| TODO-012 | Stale Doc | — | docs/PRODUCTION_CHECKLIST.md | Contains 1 TODO marker | Low |
| TODO-013 | Stale Doc | — | docs/QA_AUDIT_REPORT.md | Contains 2 TODO markers | Low |
| TODO-014 | Stale Doc | — | docs/STRUCTURAL_AUDIT_REPORT.md | Contains 1 TODO marker | Low |

---

### Category 11: Broken Cross-References

| Gap ID | Type | Code Location | Doc Location | Description | Severity |
|--------|------|---------------|--------------|-------------|----------|
| LINK-001 | Incorrect Doc | — | README.md | 8 broken relative links using `Murphy%20System/` path prefix | High |
| LINK-002 | Incorrect Doc | — | README.md | 4 broken angle-bracket links (`<Murphy System/...>`) | Medium |
| LINK-003 | Incorrect Doc | — | GETTING_STARTED.md | 5 broken angle-bracket links to source files using wrong path | Medium |
| LINK-004 | Incorrect Doc | — | SECURITY.md | 1 broken link `Murphy%20System/DEPLOYMENT_GUIDE.md` | Low |
| LINK-005 | Incorrect Doc | — | USER_MANUAL.md | 1 broken link `../LICENSE` | Low |
| LINK-006 | Incorrect Doc | — | README.md | Links to `Murphy%20System/MURPHY_1.0_QUICK_START.md` (correct file is `MURPHY_1.0_QUICK_START.md` at root) | Medium |
| LINK-007 | Incorrect Doc | — | README.md | Links to `Murphy%20System/API_DOCUMENTATION.md` (correct file is `API_DOCUMENTATION.md` at root) | Medium |

---

## Recommendations

### Critical — Fix Immediately

| Gap ID | Action | Rationale |
|--------|--------|-----------|
| ENV-046 / SEC-001 / API-058 | **UPDATE CODE** — align `src/runtime/app.py` to read `MURPHY_API_KEYS` (with an `s`) OR **UPDATE DOCS** — change `.env.example`, `SECURITY.md`, and all comments to say `MURPHY_API_KEY`. Pick one canonical name. | Operators will configure the wrong variable and deploy without authentication. |
| ENV-015 | **UPDATE DOCS** — add `MURPHY_API_KEY` (or whichever form is canonical) to `.env.example` with a clear description | Same as above |
| ENV-017 | **UPDATE DOCS** — add `MURPHY_CREDENTIAL_MASTER_KEY` to `.env.example` with a security warning | Credential encryption key is invisible to operators |
| ENV-012 | **UPDATE DOCS** — add `LIVE_TRADING_ENABLED` to `.env.example` with a clear warning | Undocumented safety gate for real-money trading |
| ARCH-001 / ARCH-002 | **UPDATE DOCS** — replace `murphy_complete_backend_extended.py` with `src/runtime/app.py` throughout ARCHITECTURE_MAP.md | Architecture diagram references a non-existent file |

### High — Fix in Phase 4

| Gap ID | Action | Rationale |
|--------|--------|-----------|
| API-001–API-043 (151 routes) | **UPDATE DOCS** — add undocumented endpoints to `API_ROUTES.md` | Developers cannot use the API without knowing endpoints exist |
| API-044, API-049, API-052–API-054 | **REMOVE** stale routes from `API_ROUTES.md` or **ADD CODE** to implement them | Documented routes that return 404 break integrations |
| DEP-004 | **UPDATE DOCS** — add `POSTGRES_PASSWORD` as a required variable in DEPLOYMENT_GUIDE.md | Docker compose fails to start without documentation warning |
| DEP-011 | **UPDATE DOCS** — add Alembic migration instructions to DEPLOYMENT_GUIDE.md | Database migrations are completely undocumented |
| SEC-002–SEC-005, SEC-007–SEC-008 | **UPDATE DOCS** — add CSRF, key rotation, brute-force, input validation to SECURITY.md | Security features operators need to configure are invisible |
| LINK-001–LINK-007 | **UPDATE DOCS** — fix all 25 broken relative links in root markdown files | Broken links undermine documentation usability |
| ENV-001–ENV-029 (205 vars) | **UPDATE DOCS** — add missing env vars to `.env.example` with comments | Operators cannot configure subsystems they don't know exist |

### Medium — Address in Phase 4

| Gap ID | Action | Rationale |
|--------|--------|-----------|
| ARCH-003 | **UPDATE DOCS** — expand ARCHITECTURE_MAP.md to include `auar/`, `billing/`, `matrix_bridge/`, `trading/`, `src/aionmind/` | Major subsystems are architecturally invisible |
| FEAT-006, FEAT-011, FEAT-012 | **UPDATE DOCS** — add trading, Matrix bridge, and SCADA to USER_MANUAL.md | Major capabilities are not user-discoverable |
| FEAT-001 | **UPDATE DOCS** — correct badge from `17368` to current count (~24,246) | Inconsistent test count undermines credibility |
| CFG-001–CFG-009 | **UPDATE DOCS** — document all runtime configuration options | Configuration options are invisible to operators |
| TODO-001–TODO-014 | **REMOVE** TODO markers from published documentation or **COMPLETE** the content | Placeholder text in shipped docs is unprofessional |

### Low — Cleanup

| Gap ID | Action | Rationale |
|--------|--------|-----------|
| ENV-031–ENV-045 | **REMOVE** stale env vars from `.env.example` | Stale vars confuse operators |
| DOC-001–DOC-011 | **UPDATE CODE** — add module docstrings to 28 files in `src/billing/grants/submission/` | Improves `help()` output and IDE tooling |
| SETUP-001–SETUP-007 | **UPDATE DOCS** — fix path references and document all install methods | Developer experience improvement |
| TODO-001–TODO-014 | **REMOVE** or **COMPLETE** placeholder text | Cleanup |

---

## Appendix: Files Scanned

### Python Source Files
- `src/runtime/app.py` — 444 routes extracted
- All `src/*.py` (522+ files) — env var and route extraction
- `src/runtime/boot.py`, `src/runtime/app.py`, `src/runtime/murphy_system_core.py`
- `src/agent_module_loader.py`, `src/llm_integration.py`, `src/llm_integration_layer.py`
- `src/local_llm_fallback.py`, `src/llm_swarm_integration.py`
- `src/fastapi_security.py`, `src/flask_security.py`, `src/secure_key_manager.py`
- `src/input_validation.py`
- `src/founder_update_orchestrator.py`, `src/founder_update_api.py`
- `src/founder_maintenance_recommendation_engine.py`, `src/founder_maintenance_api.py`
- `src/system_update_recommendation_engine.py`, `src/system_update_api.py`
- `src/deterministic_compute_plane/compute_plane.py`
- `src/billing/grants/` (all files)
- `src/auar/` (all files)
- `src/aionmind/` (all files)
- `src/trading/` (all files)
- `src/matrix_bridge/` (all files)

### Root Python Files
- `murphy_terminal.py`, `universal_control_plane.py`, `two_phase_orchestrator.py`
- `inoni_business_automation.py`, `murphy_system_1.0_runtime.py`

### Documentation Files
- `README.md`, `API_DOCUMENTATION.md`, `API_ROUTES.md`, `ARCHITECTURE_MAP.md`
- `DEPLOYMENT_GUIDE.md`, `GETTING_STARTED.md`, `USER_MANUAL.md`
- `MURPHY_SYSTEM_1.0_SPECIFICATION.md`, `MURPHY_1.0_QUICK_START.md`
- `LLM_SUBSYSTEM.md`, `DEPENDENCY_GRAPH.md`, `TROUBLESHOOTING.md`
- `STATUS.md`, `ROADMAP.md`, `SECURITY.md`, `PRIVACY.md`
- `CONTRIBUTING.md`, `BUSINESS_MODEL.md`, `CHANGELOG.md`
- `docs/GAP_ANALYSIS.md`, `docs/GAP_CLOSURE.md`, `docs/CRITICAL_ERROR_SCAN_REPORT.md`
- `docs/CRITICAL_ERROR_REMEDIATION_PLAN.md`, `docs/QA_AUDIT_REPORT.md`
- `docs/DEPLOYMENT_GUIDE.md`, `docs/MONITORING.md`, `docs/KNOWN_ISSUES.md`
- All remaining files in `docs/` (50+ documents)
- `documentation/README.md`, `documentation/CLI_REFERENCE.md`

### Configuration Files
- `.env.example`
- `docker-compose.yml`, `docker-compose.hetzner.yml`, `docker-compose.murphy.yml`
- `k8s/deployment.yaml`, `k8s/configmap.yaml`, `k8s/secret.yaml`
- `k8s/hpa.yaml`, `k8s/ingress.yaml`, `k8s/network-policy.yaml`
- `k8s/postgres.yaml`, `k8s/redis.yaml`, `k8s/monitoring/`
- `prometheus.yml`, `prometheus-rules/murphy-alerts.yml`
- `grafana/provisioning/`, `grafana/dashboards/`
- `alembic.ini`, `alembic/env.py`
- `Dockerfile`, `Makefile`

### Shell Scripts
- `setup_and_start.sh`, `install.sh`, `start.sh`
- `scripts/hetzner_load.sh`, `scripts/preflight_check.sh`
- `scripts/production_readiness_check.sh`, `scripts/generate_secrets.sh`

### Frontend Files
- All `*.html` files (30+ pages)
- `murphy_auth.js`, `murphy_overlay.js`
- `static/murphy-components.js`

---

*This document was generated as part of Phase 3 (Documentation Audit) of the Murphy System
hardening PR chain. It is a catalog only — no code or documentation changes are made in
this phase. Fixes are addressed in Phase 4 (Gap Closure).*

# Changelog

All notable changes to Murphy System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — Session Persistence + Auth Hardening

### Fixed

#### Session Persistence — Survives `hetzner_load.sh` Restarts (Critical)

**Root cause:** `_session_store` and `_user_store` in `src/runtime/app.py` were
pure in-memory structures wiped on every `systemctl restart murphy-production`.

- **`src/persistence_wal.py`** + mirror — Added migration #5 `create_user_accounts`
  (columns: `account_id`, `email`, `data` JSON, `created_at`, `updated_at`).

- **`src/runtime/app.py`** + mirror — Added `_SQLiteSessionFallback` class: replaces
  the in-memory `_fallback` dict inside `_RedisSessionStore` with a write-through
  SQLite WAL store. Sessions now survive restarts when Redis is not configured.

- **`src/runtime/app.py`** + mirror — Added `_SQLiteUserStore` + `_MutableUserRecord`
  classes: replaces the in-memory `_user_store` dict with a write-through SQLite
  store. User accounts now survive restarts; `_email_to_account` index is rebuilt
  from the DB on each startup.

- **`src/runtime/app.py`** + mirror — Fixed `GET /api/auth/session-token` endpoint:
  was generating a new random token instead of returning the actual active session
  token from the `murphy_session` cookie. Now correctly returns
  `{"session_token": <actual_token>}` so `murphy_auth.js` can mirror it to
  `localStorage` for OAuth users.

#### Auth Header Consistency

- **`src/fastapi_security.py`** + mirror — `get_configured_api_keys()` now checks
  `MURPHY_API_KEYS` (plural, canonical) first and falls back to `MURPHY_API_KEY`
  (singular) for backward compatibility. Previously the root file checked the
  singular variable first, diverging from the documented `.env.example`.

- **`static/murphy-components.js`** + mirror — `MurphyAPI._request()` now sets
  `credentials: 'same-origin'` on all `fetch()` calls so the HttpOnly
  `murphy_session` cookie is always included as a fallback when the Bearer token
  path is not available.

### Tests

- **`tests/test_auth_and_route_protection.py`** — Updated `client` fixture to use a
  per-run temp SQLite database for isolation (fixed deterministic test emails
  colliding with persisted accounts from previous runs).  Added
  `TestSessionPersistence` class with 4 new tests: session token survives restart,
  user account survives restart, `MURPHY_API_KEYS` checked first, and session-token
  endpoint returns the real token.

---

## [Unreleased] — System Commissioning: ROI Calendar + Onboarding Chat + Forge Download

### Fixed

#### Issue 1: ROI Calendar Backend — Real Random Data
- **`src/runtime/app.py`** — Replaced 5 hardcoded seed events with 12–16 **randomly generated** events using Python's `random` module and real industry hourly rates (Invoice Processing $45/hr, Compliance Audit $85/hr, Contract Review $120/hr, etc.)
- Each event now includes **named agents with hex colors** from `_ROI_AGENT_POOL` (Orchestrator `#00d4aa`, DataExtractor `#00e5ff`, Validator `#ffd700`, ComplianceBot `#ff4444`, etc.) — 2–4 agents assigned per task
- Each event now includes a **5-item checklist** per task with step-level agent assignment and completion states
- Agent compute costs derived from realistic token-cost-based estimates ($0.50–$15/task); human costs derived from real `hourly_rate × hours`
- **SSE endpoint** (`GET /api/roi-calendar/stream`) now runs a **real-time background advancement loop**: every 3–8 seconds it picks a non-complete event, advances `progress_pct` by 5–15%, marks the next checklist item as running/complete, increments `agent_compute_cost` by small realistic amounts ($0.02–$0.50 per step), and transitions status `pending → running → qc → complete`
- **New `GET /api/roi-calendar/export`** endpoint — downloads the full calendar as JSON or CSV (querystring `?fmt=json|csv`)
- **`roi_calendar.html`** — Updated `renderBlock()` to show agent color dots; `renderDetail()` now shows colored agent chips + full checklist panel (✅/⚙️/⬜ with per-item agent dot); added CSV/JSON export buttons in nav

#### Issue 2: Onboarding Chat — Always Returns `response` Field
- **`src/runtime/app.py`** — Added `message` field (alias of `response`) to every `POST /api/onboarding/mfgc-chat` response — wizard JavaScript checks both
- Added `_onboarding_deterministic_reply()` — keyword-based fallback that always produces a useful, context-sensitive interview question (invoice/HR/CRM/compliance/data/email keywords each have tailored responses) with **no external LLM required**
- Error path now returns `success: True` with the deterministic reply instead of `success: False` with an empty message — eliminates "I'm having trouble connecting" fallback

#### Issue 3: Forge Download — Clear Success/Error States
- **`murphy_landing_page.html`** — `_showResult()` now distinguishes empty-content case: shows clear error message ("API unavailable" / "Build limit reached") instead of "Build complete" when no deliverable was returned; download button labelled with filename + size when content is present
- Forge `fetch` call updated to handle non-OK responses gracefully (`.catch` on `.json()` instead of silently returning null)

### Added

#### Stub Endpoints (3 missing endpoints audited and filled)
- **`GET /api/demo/spec/{spec_id}`** — Returns a plausible synthetic spec structure (called by `signup.html`)
- **`GET /api/market/quote/{symbol}`** — Returns synthetic market price/change/volume data (called by `wallet.html`)
- **`POST /api/meetings/start`**, **`POST /api/meetings/{id}/end`**, **`GET /api/meetings/{id}/transcript`**, **`GET /api/meetings/{id}/suggestions`** — In-memory meeting session lifecycle (called by `workspace.html`)

#### LLM Fallback Chain Debug Endpoint
- **`GET /api/llm/debug`** — Returns the complete 5-layer fallback chain with availability flags: Groq → OpenAI → Anthropic → Ollama → Onboard (built-in). Shows which layer is currently active and instructions to enable Groq (free key at `console.groq.com/keys`)

#### MurphyLibrarianChat Component
- **`static/murphy-components.js`** — Added `MurphyLibrarianChat` class: a drop-in chat widget that posts to `/api/librarian/ask`, renders user/assistant bubbles, and falls back to a built-in offline answer engine when the server is unreachable
- **`murphy_landing_page.html`** — Added `<script src="/static/murphy-components.js">` include and `MurphyLibrarianChat` initialization (fixes 3 pre-existing `test_ui_types` test failures)

#### Error Banners
- Added `#murphy-error-banner` (fixed, dismissible, red) + `showMurphyError()` JS function + automatic `fetch` monkey-patch to `onboarding_wizard.html`, `roi_calendar.html`, `murphy_landing_page.html`, `workspace.html`, and `compliance_dashboard.html` — no more silent 5xx failures

#### End-to-End Commissioning Tests
- **`tests/test_e2e_commissioning.py`** — 28-test commissioning suite covering all 7 stages: system health, onboarding chat turns, ROI calendar data quality, forge deliverable, stub endpoints, librarian, and UI page content. Serves as the regression baseline for future PRs.

### Changed
- Inline styles in `murphy_landing_page.html` — moved error banner and forge error message inline styles to named CSS classes (`#murphy-error-banner`, `#murphy-error-banner-msg`, `#murphy-error-banner-close`, `.forge-err-msg`, `.forge-err-link`) to reduce inline style count

---

## [Unreleased] — Founder Update Engine (ARCH-007) + UI Navigation Overhaul

### Added

#### Founder Update Engine — PR 1: Core Recommendation Engine
- **`src/founder_update_engine/recommendation_engine.py`** (`RecommendationEngine`): Central recommendation store with 9 recommendation types (SDK_UPDATE, SECURITY, PERFORMANCE, MAINTENANCE, BUG_RESPONSE, AUTO_UPDATE, CONFIGURATION, DEPENDENCY_UPGRADE, GENERAL), 5 priority levels, full persistence, and 6 query methods
- **`src/founder_update_engine/subsystem_registry.py`** (`SubsystemRegistry`): Central registry of all Murphy subsystems — auto-discovers modules from `src/`, tracks health status (healthy/degraded/failed/unknown), update history, and pending recommendation counts
- **`src/founder_update_engine/update_coordinator.py`** (`UpdateCoordinator`): Coordinates update application within configurable maintenance windows; rate-limits changes per window; full audit trail via `UpdateRecord`
- **`src/founder_update_engine/__init__.py`**: Package exports for all public classes and constants

#### Founder Update Engine — PR 2: SDK Scanner & Auto-Update Applicator
- **`src/founder_update_engine/sdk_update_scanner.py`** (`SdkUpdateScanner`): Scans `requirements*.txt` files, detects patch/minor/major version bumps, integrates with `DependencyAuditEngine` for vulnerability data, generates `SDK_UPDATE`, `SECURITY`, and `AUTO_UPDATE` recommendations. Returns `SdkScanReport` with per-package `PackageScanRecord`
- **`src/founder_update_engine/auto_update_applicator.py`** (`AutoUpdateApplicator`): Consumes `auto_applicable` recommendations, applies them with health-gated safety checks, rate-limiting, and dry-run mode. Records outcomes via 7 `ApplicationOutcome` codes (APPLIED, SKIPPED_HEALTH, SKIPPED_RATE_LIMIT, SKIPPED_DRY_RUN, FAILED, ALREADY_APPLIED, NOT_APPLICABLE). Returns `ApplicationCycle` with full `ApplicationRecord` list

#### Founder Update Engine — PR 3: Bug Response Handler & Operating Analysis Dashboard
- **`src/founder_update_engine/bug_response_handler.py`** (`BugResponseHandler`): Ingests `BugReport` objects, classifies severity (critical/high/medium/low) and category (crash/security/performance/regression/data_loss/other) via keyword heuristics, generates root-cause hypotheses + structured action items + human-readable response drafts, creates `BUG_RESPONSE` and (for security-category bugs) `SECURITY` recommendations. Integrates with `BugPatternDetector` for pattern correlation. Full persistence and event publishing
- **`src/founder_update_engine/operating_analysis_dashboard.py`** (`OperatingAnalysisDashboard`): Aggregates operational data from `SubsystemRegistry` (health scores), `BugPatternDetector` (active patterns), `SelfHealingCoordinator` (recovery rates), `DependencyAuditEngine` (vulnerability counts), and `RecommendationEngine` (open recommendation counts). Generates `PERFORMANCE`, `MAINTENANCE`, and `SECURITY` recommendations when configured thresholds are exceeded. Produces `DashboardSnapshot` objects with durable history
  - Health score < 80% → `PERFORMANCE` recommendation
  - Health score < 50% → `MAINTENANCE` (critical) recommendation
  - Active bug patterns > 5 → `MAINTENANCE` recommendation
  - Recovery success rate < 70% → `MAINTENANCE` recommendation
  - Open vulnerabilities > 3 → `SECURITY` recommendation
- **133 tests** in `tests/test_founder_update_engine.py` covering all PR 1–3 modules

#### UI Navigation Overhaul
- **Sidebar sections** (`static/murphy-components.js`): Sidebar redesigned with 7 named section groups — **SETUP · TERMINAL · BUILD · FINANCE · OPS · COMMUNITY · ACCOUNT** — rendered as non-clickable divider labels between navigation groups
- **6 previously unreachable pages** added to sidebar navigation:
  - `🚀 ONBOARDING` → `/ui/onboarding` (Onboarding Wizard — first item under SETUP, primary post-login setup entry point)
  - `🔍 VISUALIZER` → `/ui/system-visualizer` (System Visualizer — under SETUP)
  - `📊 GRANT DASH` → `/ui/grant-dashboard` (Grant Dashboard — under FINANCE alongside Grant Wizard)
  - `💼 FINANCING` → `/ui/financing` (Financing Options — under FINANCE)
  - `🏢 ORG PORTAL` → `/ui/org-portal` (Org Portal — under ACCOUNT)
  - `📚 DOCS` → `/ui/docs` (Documentation — under ACCOUNT)
- **Command palette expanded**: 21 → 28 destinations; all new pages added to Ctrl+K palette
- Both `static/murphy-components.js` and `murphy_system/static/murphy-components.js` updated in sync

### Changed
- `src/founder_update_engine/__init__.py`: Updated to export all PR 1–3 classes: `BugCategory`, `BugReport`, `BugResponse`, `BugResponseHandler`, `BugSeverity`, `DashboardSnapshot`, `OperatingAnalysisDashboard`, `SubsystemHealthSummary`
- `tests/test_ui_wiring_improvements.py`: Sidebar expected hrefs updated from 12 → 20; command palette expected hrefs updated from 11 → 19
- Both `tests/test_ui_wiring_improvements.py` and `murphy_system/tests/test_ui_wiring_improvements.py` updated in sync



### Added
- **Communication Hub engine** (`src/communication_hub.py`): Unified onboard communication system with full SQLite persistence via `src/db.py` ORM. Includes:
  - `IMStore` — multi-account thread-based instant messaging, with automod on every message and emoji reactions
  - `CallSessionStore` — voice and video call session lifecycle (ringing → active → on-hold → ended/rejected), SDP/ICE signalling storage, duration tracking, voicemail URL
  - `EmailStore` — compose/send, per-user inbox/outbox (including CC/BCC), mark-read, per-message automod
  - `AutomationRuleStore` — configurable per-channel triggers (`on_message`, `on_email`, `on_missed_call`, etc.) with keyword and automod-flag conditions; fire-count tracking
  - `ModeratorConsole` — Discord-style moderator controls: warn/mute/unmute/kick/ban/unban, custom blocked-word lists, multi-platform broadcast, broadcast history, full audit log
- **Communication Hub router** (`src/comms_hub_routes.py`): 38 FastAPI endpoints at `/api/comms/*` and `/api/moderator/*`
- **Communication Hub UI** (`communication_hub.html`): Full-featured single-page dashboard — IM panel with threaded chat, voice/video call controls, email compose/inbox/outbox, automation rule manager, moderator console with broadcast panel and audit log. Registered at `/ui/comms-hub`
- **8 new ORM models** in `src/db.py`: `IMThread`, `IMMessage`, `CallSession`, `EmailRecord`, `CommsAutomationRule`, `CommsModAuditLog`, `CommsBroadcast`, `CommsUserProfile`. All tables created automatically by `create_tables()`
- **83 tests** in `tests/test_communication_hub.py` covering automod, IM cross-account messaging, call lifecycle, email multi-recipient, automation rule evaluation, and moderator actions
- **`tests/conftest.py`** extended with an autouse fixture that truncates comms hub tables between tests for full isolation
- **Session persistence confirmed**: messages, calls, and emails written by one store instance are immediately readable by any other instance (same SQLite DB), surviving server restarts
- **3 default automation rules** seeded on startup: auto-reply on missed call, escalate urgent emails, auto-moderate flagged IM
- **3 default broadcast targets** seeded: `im#general`, `email#all-staff`, `matrix#murphy-general`
- Supported broadcast platforms: `im`, `voice`, `video`, `email`, `slack`, `discord`, `matrix`, `sms`
- All new files mirrored to `murphy_system/` subdirectory
- `docs/COMMS_HUB.md` — detailed system documentation

### Changed
- `src/runtime/app.py` and `murphy_system/src/runtime/app.py`: comms hub router registered; `/ui/comms-hub` added to HTML routes
- `API_ROUTES.md`: full Communication Hub section added (38 endpoints)
- `ARCHITECTURE_MAP.md`: Communication Hub module added
## [Unreleased] — Critical LLM Mode Detection Fixes

### Fixed
- **LLM Mode Detection** (`_get_librarian_status`): Fixed bug where mode was always reported as "llm" even when no external LLM was configured. Now correctly distinguishes between `external_api` and `onboard` modes.
- **Librarian Ask Response Mode**: `librarian_ask()` now correctly reports `mode="onboard"` when using LocalLLMFallback instead of incorrectly reporting `mode="llm"`.
- **Onboard Notice Display**: Fixed the onboard mode notice not appearing when no external LLM is configured. Users now see helpful guidance about how to configure external LLM.
- **Integration Recommendations**: `infer_needed_integrations()` now correctly recommends groq when in onboard mode (checks `mode` field instead of `enabled` field).
- **Clarifying Questions**: `_try_llm_clarifying_questions()` now correctly returns empty list when in onboard mode, allowing proper fallback to onboard clarifying questions.
- **API Setup Intent**: `librarian_ask()` now handles `api_setup` intent directly without going through LLM, ensuring users always get API signup links when asking about credentials.
- **Grant Module Syntax**: Fixed syntax errors in `src/billing/grants/__init__.py` caused by corrupted merge content.

### Added
- **Boot Validation** (`startup_validator.py`): New `validate_llm_boot_status()` function provides boot-time LLM configuration validation with clear status reporting.

### Changed
- **Test Expectations**: Updated `TestLLMStatus` tests to reflect correct behavior where LLM is always "enabled" (because onboard is always available) and to check `mode` field for external API detection.

## [Unreleased] — Live Feeds: Binance, IBKR, IEX Cloud + Regulatory Compliance Engine

### Added
- **Binance feed** (`src/live_feed_service.py` `CryptoFeed`): REST ticker/candles/movers (public endpoint, no key required) + WebSocket combined miniticker stream via `start_binance_websocket()`
- **IEX Cloud feed** (`EquityFeed._quote_via_iex`): `iexfinance` SDK + HTTP fallback; sandbox and production tiers supported (key prefix `T` = sandbox)
- **IBKR feed** (`EquityFeed._quote_via_ibkr`): Interactive Brokers via `ib_insync`; requires IB TWS or IB Gateway running locally; graceful skip when not available
- **Alpaca WebSocket** (`EquityFeed._alpaca_ws_loop` + `LiveFeedService.start_alpaca_websocket()`): live equity trade stream via Alpaca market data WS
- **`src/trading_compliance_engine.py`**: Mandatory 7-check regulatory compliance gate — env config, live-mode flag, jurisdiction, regulations/KYC acknowledgement, paper-trading graduation, risk parameters, personal-use notice. Also `PaperTradingGraduationTracker` for persistent daily P&L tracking
- **API routes** (4 new): `GET /api/trading/compliance/status`, `POST /api/trading/compliance/evaluate`, `GET /api/trading/compliance/graduation`, `POST /api/trading/compliance/graduation/record`
- **Compliance wired into** `GET /api/coinbase/status`: response now includes `compliance_evaluated`, `compliance_passed`, `compliance_blockers`
- **SDK requirements**: `python-binance`, `iexfinance` added; `ib_insync` documented as optional manual install
- **`.env.example`**: `BINANCE_API_KEY/SECRET`, `IEX_CLOUD_API_KEY`, `IBKR_HOST/PORT/CLIENT_ID`, `COMPLIANCE_MIN_*` thresholds

### Changed
- `LiveFeedService.__init__`: new params `binance_key`, `binance_secret`, `iex_cloud_key`, `ibkr_host`, `ibkr_port`, `ibkr_client_id`
- `LiveFeedService.status()`: now reports per-exchange WebSocket state (`crypto_ws.coinbase`, `crypto_ws.binance`, `equity_ws.alpaca`)
- `_get_live_feed()` in app.py: passes all new env vars to `LiveFeedService`
- Crypto provider priority: Coinbase → **Binance** → CCXT (was Coinbase → CCXT)
- Equity provider priority: Yahoo → Alpaca → Alpha Vantage → Polygon → **IEX Cloud** → **IBKR** → stub

## [Unreleased] — Coinbase SDK Integration + Live Market Data Feeds (PR 1)

### Added
- **Coinbase Advanced Trade API** (`src/coinbase_connector.py`): HMAC-SHA256 auth, REST + WebSocket, sandbox-first (COINBASE_LIVE_MODE=true required for live), helper methods `get_accounts`, `get_ticker`, `place_market_order`, `place_limit_order`, `cancel_order`, `get_product_candles`
- **Live Market Data Feed** (`src/live_feed_service.py`): Unified crypto + equity price service — Coinbase → CCXT for crypto; Yahoo Finance → Alpaca → Alpha Vantage → Polygon for equities; WebSocket live streaming; process-wide singleton
- **API routes**: `/api/coinbase/*` (5 routes), `/api/market/*` (6 REST + 1 WebSocket)
- **Wallet UI**: Coinbase Connection panel with sandbox indicator, live balance display, connect/refresh buttons wired to `/api/coinbase/*`
- **SDK requirements**: `coinbase-advanced-py`, `ccxt`, `web3`, `websocket-client`, `yfinance`, `alpaca-py`, `alpha_vantage`, `polygon-api-client`, `ta`, `tweepy`, `slack-sdk`, `python-telegram-bot`, `hubspot-api-client`, `simple-salesforce`, `PyGithub`, `requests-oauthlib`, `authlib`
- **`.env.example`**: Coinbase Advanced Trade keys, Alpaca, Alpha Vantage, Polygon.io market data keys

### Changed
- `src/coinbase_connector.py`: Default `sandbox=True` (was `False`); live mode requires `COINBASE_LIVE_MODE=true` env var
- `murphy_system/` files synced with root (`coinbase_connector.py`, `wallet.html`, requirements)

## [Unreleased]

### Added — Paper Trading Engine + Strategy Templates (PR-2)

Full paper-trading simulation system with 9 strategy templates, hidden-cost detection,
self-calibrating error correction, and backtesting harness.  All trading is
PAPER/SIMULATED — no real money is moved.

#### New files
- **`src/paper_trading_engine.py`** — `PaperTradingEngine`: full simulator with
  slippage model, tiered fee schedule, position tracking, FIFO trade journal,
  stop-loss/take-profit price triggers, and the complete metric suite (Sharpe,
  Sortino, max drawdown, profit factor, win rate, avg win/loss, total fees, net profit).
  `reset()` restarts from initial capital. Default: $10,000.
- **`src/strategy_templates/`** — 9 ready-to-use strategy templates:
  - `momentum.py` — RSI + MACD crossover + volume confirmation
  - `mean_reversion.py` — Bollinger Bands + Z-score mean reversion
  - `breakout.py` — Support/resistance + volume breakout confirmation
  - `scalping.py` — Short timeframe, tight stops, high-frequency entries
  - `dca.py` — Dollar Cost Average (time-based or price-dip accumulation)
  - `grid.py` — Grid trading (buy low / sell high within a configurable range)
  - `trajectory.py` — Parabolic move detection with projected peak exit and trailing stop
  - `sentiment.py` — Fear/greed index + social signal framework (contrarian entries)
  - `arbitrage.py` — Cross-pair Z-score spread detection and mean reversion
- **`src/cost_calibrator.py`** — `CostCalibrator`: tracks expected vs actual execution
  prices; detects and quantifies spread, slippage, exchange fees, and network fees;
  auto-adjusts future cost estimates; fires configurable alerts when costs exceed thresholds.
- **`src/error_calibrator.py`** — `ErrorCalibrator`: per-strategy bias/MAE/RMSE tracking;
  when divergence exceeds threshold, trims the rolling window, logs the calibration event,
  and optionally calls a user-supplied recalibration hook.
- **`src/backtester.py`** — `Backtester`: replays any `BaseStrategy` over historical OHLCV
  data (from CSV, pre-loaded dicts, or yfinance); multi-timeframe support (1m/5m/15m/1h/4h/1d);
  side-by-side strategy comparison ranked by Sharpe ratio; JSON-serialisable `BacktestResult`.
- **`src/paper_trading_routes.py`** — FastAPI router (`/api/trading/*`) with 11 endpoints
  for starting/stopping sessions, querying positions/trades/performance, listing strategies,
  manual trade execution, backtest runs, and calibration summaries.
- **`paper_trading_dashboard.html`** — Full paper trading dashboard at `/ui/paper-trading`:
  live equity curve chart, open positions table, strategy performance comparison, trade journal,
  hidden cost analysis, error calibration status, backtest panel, Murphy AI bar.
- **`tests/test_paper_trading.py`** — 41 tests: open/close positions, P&L, fees, stop-loss/
  take-profit triggers, reset, all performance metric keys, cost calibrator, error calibrator,
  and backtester.
- **`tests/test_strategies.py`** — 34 tests: all 9 strategies instantiate, produce valid
  `Signal` objects (confidence 0–1, valid action enum), and respond correctly to uptrend,
  downtrend, parabolic, and extreme-sentiment inputs.  Registry completeness test.

#### Updated files
- **`requirements_murphy_1.0.txt`** and **`murphy_system/requirements_murphy_1.0.txt`** —
  uncommented/added: `coinbase-advanced-py>=1.8.2`, `ccxt>=4.5.0`, `web3>=7.0.0`,
  `yfinance>=1.2.0`, `ta>=0.11.0`, `statsmodels>=0.14.0`.
- **`src/runtime/app.py`** — added `paper_trading_routes` router registration at
  `/api/trading/*`; added `/ui/paper-trading` → `paper_trading_dashboard.html` HTML route.
- **`wallet.html`** — added Paper Trading quick-access section (card linking to dashboard,
  live engine-status widget populated via `/api/trading/paper/status`).
- **`API_ROUTES.md`** — documented all 11 paper trading endpoints and 9 strategy templates.

### Fixed — End-to-End Authentication Flow (Beta Launch Blocker)

All three auth paths — email/password, OAuth, and programmatic API access — are
now fully connected so that users can sign up, log in, and use the Librarian chat
without seeing "Authentication required".

#### Backend: `src/fastapi_security.py` + mirror

- **`_authenticate_request()`** now checks the `murphy_session` HttpOnly cookie in
  addition to `Authorization: Bearer` and `X-API-Key` headers.  The cookie check
  uses a pluggable validator registered at startup to avoid circular imports.
- **`register_session_validator(fn)`** — new public function; called once by
  `create_app()` with a closure over the in-memory `_session_store`.

#### Backend: `src/runtime/app.py`

- **`POST /api/auth/signup`** response body now includes `session_token` alongside
  `account_id`, `email`, `name`, and `tier`.  The `murphy_session` cookie is still
  set (HttpOnly); the JSON field lets the browser mirror the token to localStorage.
- **`POST /api/auth/login`** — same: `session_token` added to the JSON body.
- **`GET /api/auth/session-token`** — new authenticated endpoint.  Called by
  `murphy_auth.js` after an OAuth redirect to retrieve the session token from the
  server (the `murphy_session` cookie is HttpOnly and cannot be read by JavaScript
  directly).  Returns `{ session_token }` for the currently authenticated session.
- Session validator registered at startup:
  ```python
  register_session_validator(lambda t: t in _session_store)
  ```

#### Frontend: `static/murphy-components.js` + mirror

- **`MurphyAPI._buildHeaders()`** now checks `localStorage.murphy_session_token`
  first and sends `Authorization: Bearer <token>`.  Falls back to `murphy_api_key`
  / `X-API-Key` if no session token is present.

#### Frontend: `login.html` + `murphy_system/login.html`

- After a successful login response both files now store:
  ```js
  localStorage.setItem('murphy_session_token', result.data.session_token);
  localStorage.setItem('murphy_user_id', result.data.account_id);
  ```

#### Frontend: `signup.html` + `murphy_system/signup.html`

- Same — `murphy_session_token` and `murphy_user_id` stored on successful signup.

#### Frontend: `murphy_auth.js` + `murphy_system/murphy_auth.js`

- **`_handleOAuthSuccess()`** rewritten to `async`.  Instead of attempting to read
  the HttpOnly `murphy_session` cookie from `document.cookie` (which always returns
  an empty string), it now fetches `GET /api/auth/session-token` with
  `credentials: "include"` and stores the returned token in localStorage.

#### Python: `src/supervisor_system/anti_recursion.py` + mirror

- Added missing `Any` to the `from typing import …` line; the `ImportError` fallback
  for `thread_safe_operations.capped_append` used `Any` before it was in scope,
  causing a `NameError` at startup.

#### Tests: `tests/test_auth_and_route_protection.py`

- `TestSignup.test_signup_returns_session_token` — asserts `session_token` in body.
- `TestLogin.test_login_returns_session_token` — asserts `session_token` in body.
- `TestLogin.test_bearer_token_auth_using_session_token` — end-to-end: signup →
  extract token → authenticate a cookieless client via `Authorization: Bearer`.
- `TestSessionTokenEndpoint` — 3 tests for `GET /api/auth/session-token`:
  authenticated returns token, unauthenticated returns 401, token matches signup.

#### Docs

- `docs/API_REFERENCE.md` + mirror — Authentication section rewritten to describe
  the cookie + Bearer + X-API-Key precedence chain and both auth flows.
- `SECURITY.md` — added Authentication Architecture table with session token details.
- `murphy_system/SECURITY.md` — updated Security Architecture table.
- `API_ROUTES.md` + mirror — added `POST /api/auth/login`, `POST /api/auth/logout`,
  and `GET /api/auth/session-token` rows; signup description updated.

### Added — UI User-Flow & Schedule Automation E2E Tests (Round 61)

#### End-to-End UI User-Flow Tests
- **`tests/test_ui_user_flow_schedule_automations.py`** — 79 tests covering the full user
  journey from signup through natural-language workflow creation and schedule verification.
  - **Part 1 (Auth Flow)**: Signup page, login page, session creation, credential login, profile access.
  - **Part 2 (UI Navigation)**: 12 public pages return 200; 11 protected pages redirect (302→login);
    workflow canvas and dashboard accessible after auth.
  - **Part 3 (NL → Scheduled Workflow)**: Natural language descriptions produce correct schedule
    metadata — daily/weekly/monthly/hourly/on_demand with proper cron expressions.
  - **Part 4 (Workflow CRUD)**: Generate→list, generate→get-by-ID, save custom, 404 for missing, count validation.
  - **Part 5+6 (Scheduler & Platform)**: Scheduler status/start/stop/trigger endpoints;
    platform automation-status reports all 6 subsystems.
  - **Part 7 (Full User Journey)**: End-to-end signup→navigate→create NL workflow→verify schedule
    for daily (SendGrid), weekly (Slack), and monthly (Stripe) automations.
  - **Part 8 (Canvas HTML)**: NL input field, schedule trigger node, save/run/load buttons,
    draggable palette, all four node categories present.
  - **Part 9 (API Suggestions)**: 11 NL descriptions correctly suggest SendGrid, Slack, HubSpot,
    Stripe, Google Calendar, Google Sheets, PostgreSQL, Twilio, GitHub, Datadog, OpenWeatherMap.
  - **Part 10 (Schedule Metadata)**: Validates cron expressions, enabled flag, next_run timestamp,
    and on_demand disabled state for all schedule intervals.

### Added — Platform Self-Automation, Agent Org Chart, Creator Services & Demo Export (Round 60)

#### Platform Self-Automation (5 systems wired)
- **Self-Fix Loop (ARCH-005)** — `GET/POST /api/self-fix/{status,run,history,plans}` for
  autonomous diagnose→plan→execute→test→verify cycles.
- **Autonomous Repair (ARCH-006)** — `GET/POST /api/repair/{status,run,history,wiring,proposals}`
  with immune memory and reconciliation loops.
- **Murphy Scheduler** — `GET/POST /api/scheduler/{status,start,stop,trigger}` for daily
  platform automation cycles with HITL safety gates.
- **Self-Automation Orchestrator (ARCH-002)** — `GET/POST /api/self-automation/{status,task,tasks}`
  for priority-based task queue with prompt chain tracking.
- **Self-Improvement Engine** — `GET /api/self-improvement/{status,proposals,corrections}` for
  outcome tracking, pattern extraction, and remediation proposals.
- **Platform Overview** — `GET /api/platform/automation-status` returns unified status of all 6
  self-automation subsystems.

#### Workflow Schedule & API Suggestions
- Generated workflows now include `schedule` metadata (`interval`, `cron`, `enabled`, `next_run`)
  automatically inferred from natural language (daily/weekly/monthly/hourly/on_demand).
- Generated workflows include `api_suggestions` — recommends relevant integrations
  (SendGrid, Slack, Stripe, Twilio, etc.) based on workflow description keywords.

#### Inoni LLC Agent Org Chart
- **GET /api/orgchart/inoni-agents** — Full automated org chart of 23 AI agents across
  8 departments (Executive, Sales, Content Creator, DevRel, Platform Engineering,
  Production, AI/ML, Customer Success) with 70+ automations.
- Daily seller agent runs platform self-promotion automations.
- Streaming & gaming AI agent registered as planned (2026-Q4).

#### Content Creator Services (Free Tier)
- **GET /api/creator/moderation/status** — Service status for free AI content moderation.
- **POST /api/creator/moderation/check** — Content moderation with spam detection,
  toxicity scoring, and community guidelines enforcement. Free for creators/bloggers.

#### Developer SDK & Platform Capabilities
- **GET /api/sdk/status** — SDK availability (Python, JavaScript, REST API).
- **GET /api/platform/capabilities** — 12 licensable capabilities catalog with tier
  requirements, licensing types, and status (active/planned).

#### Demo Export
- **GET /api/demo/export** — Downloadable project bundle with BSL-1.1 licensing,
  no-warranty clause, .env template, workflows, setup instructions, and platform
  capability manifest.

#### MFM Data Collection Verified
- ActionTraceCollector, MFMRegistry, OutcomeLabeler, TrainingDataPipeline all verified
  importable and functional.
- 6-month training timeline confirmed: 60 traces/day × 180 days = 10,800 > 10,000 threshold.

### Added — Workflow Execution, HITL Queue, Compliance Enforcement & Tier-Gated Automation

#### Workflow System
- **POST /api/workflows/{id}/execute** — Real workflow execution via WorkflowOrchestrator.
  Applies HITL gate checks and tier-based automation limits before starting.
  Free tier blocked; paid tiers subject to automation count limits.
- **POST /api/workflows/generate** — AI workflow generation from natural language via
  AIWorkflowGenerator.  Generates DAG workflows and auto-saves to workflow store.
- Workflow execution updates stored workflow status (`completed`/`failed`) with
  timestamps and execution result.

#### HITL Queue (Mock → Real)
- **GET /api/hitl/queue** — Now returns real HumanInTheLoop state from
  `murphy.get_hitl_state()` instead of empty mock `[]`.
- **GET /api/hitl/pending** — New endpoint (alias for terminal UI) returning real
  pending HITL items.
- **POST /api/hitl/interventions/{id}/respond** — Added input validation:
  status must be `approved|rejected|resolved|deferred|escalated`;
  response capped at 2000 chars; returns 404 for unknown intervention IDs.

#### Tier-Gated Automation Enforcement
- **Free tier**: Can create/view workflows and generate via AI (uses daily actions).
  Blocked from executing automated workflows or running business automations.
  Clear upgrade messaging with `/ui/pricing` link.
- **Paid tiers**: Automation execution enforced against tier automation limits
  (Solo: 3, Business: unlimited).  Daily usage recording for all tiers.
- Enforcement applied to both `/api/workflows/{id}/execute` and
  `/api/automation/{engine_name}/{action}`.

#### Compliance Framework Enforcement
- **Tier-gated framework selection**: FREE gets no frameworks; SOLO gets GDPR+SOC2;
  BUSINESS gets 8 frameworks; PROFESSIONAL/ENTERPRISE get all 41.
  Non-allowed frameworks silently stripped with clear upgrade messaging.
- **Compliance conflict detection**: When multiple frameworks are enabled, conflicts
  are automatically detected and documented with resolutions:
  - GDPR ↔ CCPA: Data retention — GDPR's 30-day erasure satisfies CCPA's 45-day.
  - HIPAA ↔ GDPR: Data processing — Explicit consent + minimum necessary access.
  - SOC 2 ↔ ISO 27001: Security controls — Unified control set satisfies both.
  - PCI-DSS ↔ SOX: Financial data — Complementary scopes, no conflict.
  - FedRAMP ↔ CMMC: Government — Shared NIST 800-171 controls.
- Conflict data returned in every compliance toggle save response.

#### Security Hardening
- HITL respond endpoint: Enum-validated status, 2000-char response limit,
  404 for unknown interventions (was returning `{"success": false, "intervention": null}`).

### Added — Production Auth System, Route Protection, FREE Tier, Hero & SEO

#### Authentication & Session Management
- **POST /api/auth/signup** — Creates real accounts with SHA-256 hashed passwords and
  session cookies.  Returns `account_id`, sets HttpOnly `murphy_session` cookie.
- **POST /api/auth/login** — Validates credentials against stored accounts, creates
  session token, sets HttpOnly cookie with `secure`, `samesite=lax`, 24h expiry.
- **GET /api/profiles/me** — Returns authenticated user profile including tier, daily
  usage stats, and terminal feature config.  Returns 401 without valid session.
- **POST /api/auth/logout** — Invalidates session token, clears session cookie.
- **POST /api/billing/checkout** — Creates billing checkout sessions for subscription
  upgrades (falls back to mock URL when Stripe/PayPal not configured).
- **GET /api/usage/daily** — Returns daily usage stats for authenticated or anonymous
  visitors.

#### Server-Side Route Protection
- 24 protected HTML routes now return **302 → /ui/login?next=...** without a valid
  session cookie (terminal, wallet, workspace, management, calendar, etc.).
- 11 public HTML routes remain accessible without authentication (landing, login,
  signup, pricing, docs, blog, careers, legal, privacy, partner).
- Added `murphy_auth.js` to `community_forum.html` (was missing client-side guard).

#### FREE Subscription Tier
- New `SubscriptionTier.FREE` enum value and pricing plan ($0/month).
- Free tier grants: 10 actions/day, Shadow Agent training (view-only), crypto wallet,
  community access, all system capabilities at 10 uses/day.
- Anonymous visitors get 5 actions/day.
- Selling Shadow Agent skills and running HITL automations require paid subscription.


---

> **Note:** For older changelog entries (pre-2026-01), see [docs/archive/CHANGELOG_ARCHIVE.md](./docs/archive/CHANGELOG_ARCHIVE.md)

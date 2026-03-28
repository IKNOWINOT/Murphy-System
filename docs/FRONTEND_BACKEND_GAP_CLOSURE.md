# Frontend ↔ Backend Gap Closure Plan — Murphy System 1.0

> **Date**: 2026-03-28  
> **Status**: Active — Production Closure Sprint  
> **Scope**: Full inventory of frontend UI, backend API, wiring state, and closure plan

---

## Executive Summary

Murphy System 1.0 has **700+ backend API endpoints** across 25 registered routers
and 500+ direct routes in `src/runtime/app.py`.  The frontend consists of
**51 HTML pages**, **10 JavaScript modules**, **9 TypeScript/React components**,
and **4 CSS files** serving through 55 UI routes.

**Current Wiring State:**
- **24 pages** (44%) actively call backend APIs and are correctly wired.
- **30 pages** (56%) are static/marketing or terminal-shell pages with no API calls.
- **14 of 15 backend API modules** (93%) have NO dedicated frontend page.
- Only the **Billing** module (`/api/billing`) is wired to frontend pages
  (`pricing.html`, `signup.html`).

**The Primary Gap:** The Monday.com parity modules (Phases 1–12) plus the
AionMind cognitive pipeline and Founder Update system have full backend APIs
but no dedicated frontend pages.

---

## Guiding Questions — Applied Per Module

For each module the team asks:

| # | Question | Shorthand |
|---|----------|-----------|
| Q1 | Does the module do what it was designed to do? | **Design Intent** |
| Q2 | What exactly is the module supposed to do? | **Specification** |
| Q3 | What conditions are possible based on the module? | **Condition Space** |
| Q4 | Does the test profile reflect the full range of capabilities? | **Test Coverage** |
| Q5 | What is the expected result at all points of operation? | **Expected Behaviour** |
| Q6 | What is the actual result? | **Actual Behaviour** |
| Q7 | How can we predetermine all functional pipelines? | **Pipeline Map** |
| Q8 | How can we build specialty in automation? | **Automation Plan** |
| Q9 | If problems remain, how do we restart from symptoms? | **Diagnostic Loop** |
| Q10 | Has ancillary code and documentation been updated? | **As-Built Docs** |
| Q11 | Has hardening been applied? | **Hardening** |
| Q12 | Has the module been commissioned after those steps? | **Commissioning** |

---

## Module-by-Module Analysis

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### TIER 1 — FULLY WIRED (Frontend + Backend + Tests)
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#### 1. Trading Automation (`/api/trading/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `trading_dashboard.html` → 12 endpoints called
- **Backend**: `src/trading_routes.py` → 20 endpoints defined
- **Q1 Design Intent**: ✅ Yes — live crypto trading with sweep, emergency stop, graduation
- **Q2 Specification**: Start/stop trading bots, portfolio view, position tracking, ATOM sweep, risk assessment, emergency controls, graduation to live
- **Q3 Condition Space**: Running/stopped, emergency-stopped, graduated/paper, sweep pending/complete, 6 strategies
- **Q4 Test Coverage**: ✅ `tests/test_trading_routes.py` — endpoint-level tests
- **Q5 Expected**: Portfolio/positions/trades update in real-time; emergency stop halts all activity; graduation transitions paper→live
- **Q6 Actual**: ✅ All endpoints return expected shapes; sweep cycles and emergency controls functional
- **Q7 Pipeline Map**: Frontend polls → API → TradingBotEngine → CoinbaseConnector → MarketDataFeed
- **Q8 Automation**: Shadow learner records trade patterns; permutation calibration optimises strategy selection
- **Q9 Diagnostic Loop**: `/api/trading/audit/log` → trace failures → `/api/trading/risk/assessment` → manual override
- **Q10 As-Built**: ✅ API_ROUTES.md updated; inline docstrings complete
- **Q11 Hardening**: ✅ HITL gateway for transfers; rate limiting; API key auth; emergency stop threshold
- **Q12 Commissioning**: ✅ Commissioned — 12/20 endpoints called from UI; 8 admin-only endpoints untouched by UI (expected)

**Gap**: 8 admin-only endpoints not exposed in UI (acceptable — `/api/trading/mode`, `/api/trading/positions/{id}`, `/api/trading/trades/today`, `/api/trading/portfolio/history`)  
**Action**: None required — admin endpoints accessible via API/CLI.

---

#### 2. Paper Trading (`/api/trading/paper/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `paper_trading_dashboard.html` → 8 endpoints called
- **Backend**: `src/paper_trading_routes.py` → 11 endpoints defined
- **Q1**: ✅ Simulated trading with backtest, calibration, multi-strategy
- **Q4**: ✅ `tests/test_paper_trading_routes.py`
- **Q6**: ✅ All called endpoints return expected shapes
- **Q12 Commissioning**: ✅ Commissioned — 8/11 endpoints wired

**Gap**: `POST /api/trading/paper/trade` (manual trade execution) not called from UI.  
**Action**: None required — manual trades available via API.

---

#### 3. Risk & Compliance (`/api/trading/risk/*`, `/api/trading/emergency/*`, `/api/trading/audit/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `risk_dashboard.html` → 7 endpoints called
- **Backend**: `src/risk_routes.py` → 14 endpoints defined
- **Q1**: ✅ Risk assessment, emergency stop, graduation, audit trail, CSV export
- **Q3 Condition Space**: Risk levels (low/medium/high/critical), emergency states (active/inactive/cooling), graduation states (not-started/in-progress/graduated/overridden)
- **Q4**: ✅ `tests/test_risk_routes.py`
- **Q6**: ✅ All called endpoints return expected shapes
- **Q12 Commissioning**: ✅ Commissioned — 7/14 endpoints wired

**Gap**: 7 admin/trajectory endpoints not in UI — acceptable for production.

---

#### 4. Wallet & Crypto (`/api/wallet/*`, `/api/coinbase/*`, `/api/market/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `wallet.html` → 11 endpoints called
- **Backend**: Direct routes in `src/runtime/app.py` (lines 10026–10361)
- **Q1**: ✅ Multi-chain wallet view, send/receive, Coinbase integration, market quotes, WebSocket price stream
- **Q3**: Chain states (ETH/BTC/SOL/BASE/ARB/OP), transaction states (pending/confirmed/failed), exchange connection states
- **Q6**: ✅ All endpoints defined in app.py; wallet uses in-memory store (upgrade to DB planned)
- **Q11 Hardening**: ✅ HITL gateway for sends; private keys encrypted via SecureKeyManager
- **Q12 Commissioning**: ✅ All 11 frontend endpoints have matching backend handlers

---

#### 5. Admin Panel (`/api/admin/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `admin_panel.html` → 18+ endpoints called
- **Backend**: Direct routes in `src/runtime/app.py` (lines 8564–9100)
- **Q1**: ✅ User management, org management, session management, audit log
- **Q12 Commissioning**: ✅ Commissioned — all called endpoints exist in backend

---

#### 6. Communication Hub (`/api/comms/*`, `/api/moderator/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `communication_hub.html` → 6+ endpoints called
- **Backend**: `src/comms_hub_routes.py` → 90+ endpoints
- **Q1**: ✅ IM, voice, video, email, moderator console
- **Q12 Commissioning**: ✅ Commissioned — frontend calls subset; remaining are programmatic

---

#### 7. Compliance Dashboard (`/api/compliance/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `compliance_dashboard.html` → 5 endpoints called
- **Backend**: Direct routes in `src/runtime/app.py` (lines 6817–7045)
- **Q1**: ✅ Framework toggles, recommendations by country/industry, posture report, scan
- **Q12 Commissioning**: ✅ Commissioned

---

#### 8. Management Dashboard (`/api/founder/maintenance/*`, `/api/health`, `/api/status`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `management.html` → 12+ endpoints called
- **Backend**: `src/founder_maintenance_api.py` + direct routes
- **Q1**: ✅ System health, subsystem monitoring, recommendation management, scan
- **Q12 Commissioning**: ✅ Commissioned

---

#### 9. Billing & Grants (`/api/billing/*`, `/api/grants/*`)
- **Label**: `PRODUCTION-READY`
- **Frontend**: `pricing.html`, `signup.html`, `grant_wizard.html`, `grant_dashboard.html`, `grant_application.html`
- **Backend**: `src/billing/api.py`, `src/billing/grants/api.py`
- **Q12 Commissioning**: ✅ Commissioned

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### TIER 2 — BACKEND COMPLETE, FRONTEND MISSING (Priority Closure)
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#### 10. Board System — Phase 1 (`/api/boards/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/board_system/api.py` → 20+ endpoints
- **Frontend**: ❌ **NO PAGE** — no `boards.html` exists
- **Q1 Design Intent**: Monday.com-parity board management (create boards, groups, items, columns, views)
- **Q2 Specification**: Full CRUD for boards, groups, items, columns, cell values, views, activity logs
- **Q3 Condition Space**: Board states (active/archived/template), item states (working_on_it/stuck/done/blank), column types (status/text/number/date/person/file/link/formula)
- **Q4 Test Coverage**: Board system has tests but NO frontend integration tests
- **Q5 Expected**: Users can create boards, manage items, track status — identical to Monday.com workflow
- **Q6 Actual**: Backend fully operational; NO way to access from browser UI
- **Q7 Pipeline Map**: `boards.html` → fetch `/api/boards/*` → BoardSystem → Storage
- **Q8 Automation**: Board automations wired to `/api/automations` (Phase 7); triggers on item status change
- **Q9 Diagnostic Loop**: `/api/boards/{id}` → inspect items → check automation rules → verify storage
- **Q10 As-Built**: Backend docs complete; frontend docs needed
- **Q11 Hardening**: ✅ RBAC via Depends(); rate limiting applied
- **Q12 Commissioning**: ❌ NOT commissioned — no frontend to commission
- **Action**: **CREATE** `boards.html` with board CRUD, item management, status columns
- **Priority**: 🔴 **CRITICAL** — core feature, blocks management parity goal

---

#### 11. Workdocs — Phase 5 (`/api/workdocs/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/workdocs/api.py` → 12 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Document CRUD, block editing, versioning, collaborator management
- **Q3 Condition Space**: Doc states (draft/published/archived), block types (text/heading/list/code/image/table/divider), version states
- **Q6 Actual**: Backend operational; no browser access
- **Action**: **CREATE** `workdocs.html` with document editor, block system, version history
- **Priority**: 🔴 **CRITICAL** — core collaboration feature

---

#### 12. Time Tracking — Phase 6 (`/api/time-tracking/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/time_tracking/api.py` → 10 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Timer start/stop, time entries, reports, timesheets with approval workflow
- **Q3 Condition Space**: Timer states (running/stopped), entry states (logged/submitted/approved/rejected), timesheet states (draft/submitted/approved)
- **Action**: **CREATE** `time_tracking.html` with timer, entries, timesheet view
- **Priority**: 🟡 **HIGH** — operational feature

---

#### 13. Dashboards — Phase 3 (`/api/dashboards/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/dashboards/api.py` → 11 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Dashboard CRUD, widget management, rendering
- **Q3 Condition Space**: Dashboard states (active/archived), widget types (chart/number/table/timeline/battery/calendar)
- **Action**: **CREATE** `dashboards.html` with widget grid, drag-and-drop, data binding
- **Priority**: 🟡 **HIGH** — visualisation/reporting feature

---

#### 14. CRM — Phase 8 (`/api/crm/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/crm/api.py` → 13 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Contact management, pipeline management, deal tracking, activity logging
- **Q3 Condition Space**: Contact states (lead/prospect/customer/churned), deal stages (qualification/proposal/negotiation/closed-won/closed-lost), pipeline states
- **Action**: **CREATE** `crm.html` with contact list, pipeline board, deal details
- **Priority**: 🟡 **HIGH** — business-critical feature

---

#### 15. Portfolio/Gantt — Phase 4 (`/api/portfolio/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/portfolio/api.py` → 14 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Gantt bars, dependencies, milestones, baselines, critical path
- **Action**: **CREATE** `portfolio.html` with Gantt chart, dependency arrows, critical path highlight
- **Priority**: 🟡 **HIGH** — project management feature

---

#### 16. Collaboration — Phase 2 (`/api/collaboration/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/collaboration/api.py` → 15+ endpoints + WebSocket
- **Frontend**: ❌ **NO DEDICATED PAGE** (WebSocket used by murphy-components.js for notifications)
- **Q2 Specification**: Comments, threads, reactions, notifications, activity feeds, real-time WebSocket
- **Action**: Wire collaboration features INTO existing pages (boards, workdocs) rather than standalone page
- **Priority**: 🟢 **MEDIUM** — embedded feature, not standalone

---

#### 17. Automations — Phase 7 (`/api/automations/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/automations/api.py` → 7 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Automation rules (CRUD), trigger execution, rule enable/disable
- **Action**: **CREATE** `automations.html` with rule builder, trigger log, enable/disable toggles
- **Priority**: 🟢 **MEDIUM** — power-user feature

---

#### 18. Dev Module — Phase 9 (`/api/dev/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/dev_module/api.py` → 18 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Sprints, bugs, releases, git feed, roadmap
- **Action**: **CREATE** `dev_module.html` with sprint board, bug tracker, release management
- **Priority**: 🟢 **MEDIUM** — developer tooling

---

#### 19. Service Module — Phase 10 (`/api/service/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/service_module/api.py` → 17 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Service catalog, SLA policies, ticket management, knowledge base, CSAT
- **Action**: **CREATE** `service_module.html` with ticket board, KB articles, SLA tracking
- **Priority**: 🟢 **MEDIUM** — service management feature

---

#### 20. Guest Collaboration — Phase 11 (`/api/guest/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/guest_collab/api.py` → 17 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Guest invitations, shareable links, client portals, external forms
- **Action**: **CREATE** `guest_portal.html` with invitation management, shared link builder
- **Priority**: 🟢 **MEDIUM** — collaboration extension

---

#### 21. Mobile API — Phase 12 (`/api/mobile/*`)
- **Label**: `NO-FRONTEND-NEEDED`
- **Backend**: `src/mobile/api.py` → 13 endpoints
- **Frontend**: N/A — **mobile-only API** (device registration, push notifications, sync)
- **Action**: None required — API consumed by mobile apps, not browser UI
- **Priority**: ⚪ **N/A** — correctly has no HTML page

---

#### 22. AionMind Cognitive Pipeline (`/api/aionmind/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/aionmind/api.py` → 11 endpoints
- **Frontend**: ❌ **NO PAGE**
- **Q2 Specification**: Kernel status, context building, orchestration, execution with HITL, proposals, memory (STM/LTM)
- **Action**: **CREATE** `aionmind.html` with execution graph visualiser, proposal queue, memory inspector
- **Priority**: 🟡 **HIGH** — core AI orchestration feature

---

#### 23. Founder Update System (`/api/founder/*`)
- **Label**: `FRONTEND-NEEDED`
- **Backend**: `src/founder_update_api.py` → 7 endpoints
- **Frontend**: ❌ **NO DEDICATED PAGE** (partially surfaced via `management.html` for maintenance)
- **Q2 Specification**: Founder reports, recommendations (accept/reject/defer), health, history
- **Action**: Wire into `management.html` or create `founder_updates.html`
- **Priority**: 🟢 **MEDIUM** — founder-facing feature

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### TIER 3 — STATIC PAGES (Intentionally No API)
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

These pages are **correctly static** and do not need API wiring:

| Page | Purpose | Label |
|------|---------|-------|
| `blog.html` | Blog/news | `STATIC-OK` |
| `careers.html` | Careers page | `STATIC-OK` |
| `docs.html` | Documentation | `STATIC-OK` |
| `legal.html` | Legal/T&C | `STATIC-OK` |
| `privacy.html` | Privacy policy | `STATIC-OK` |
| `demo.html` | Product demo | `WIRED-OK` |
| `murphy-smoke-test.html` | Smoke test | `STATIC-OK` |
| `murphy_ui_integrated.html` | UI shell | `STATIC-OK` |
| `murphy_ui_integrated_terminal.html` | Terminal shell | `STATIC-OK` |
| `terminal_*.html` (8 files) | Terminal variants | `WIRED-OK` |

---

## Gap Closure Priority Matrix

| Priority | Module | Backend Ready | Frontend Exists | Wired | Action |
|----------|--------|:---:|:---:|:---:|--------|
| 🔴 CRITICAL | Board System | ✅ | ❌ | ❌ | Create `boards.html` |
| 🔴 CRITICAL | Workdocs | ✅ | ❌ | ❌ | Create `workdocs.html` |
| 🟡 HIGH | Time Tracking | ✅ | ❌ | ❌ | Create `time_tracking.html` |
| 🟡 HIGH | Dashboards | ✅ | ❌ | ❌ | Create `dashboards.html` |
| 🟡 HIGH | CRM | ✅ | ✅ | ✅ | `crm.html` — Sprint 2 |
| 🟡 HIGH | Portfolio/Gantt | ✅ | ✅ | ✅ | `portfolio.html` — Sprint 2 |
| 🟡 HIGH | AionMind | ✅ | ✅ | ✅ | `aionmind.html` — Sprint 2 |
| 🟢 MEDIUM | Automations | ✅ | ✅ | ✅ | `automations.html` — Sprint 3 |
| 🟢 MEDIUM | Dev Module | ✅ | ✅ | ✅ | `dev_module.html` — Sprint 3 |
| 🟢 MEDIUM | Service Module | ✅ | ✅ | ✅ | `service_module.html` — Sprint 3 |
| 🟢 MEDIUM | Guest Collab | ✅ | ✅ | ✅ | `guest_portal.html` — Sprint 3 |
| 🟢 MEDIUM | Collaboration | ✅ | ✅ | ✅ | Embedded in boards.html + workdocs.html — Sprint 3 |
| 🟢 MEDIUM | Founder Update | ✅ | ✅ | ✅ | Embedded in management.html — Sprint 3 |
| ⚪ N/A | Mobile API | ✅ | N/A | N/A | Mobile-only — no HTML needed |

---

## Functional Pipeline Map

Every feature in Murphy follows a consistent pipeline:

```
┌──────────────┐    ┌───────────┐    ┌──────────────┐    ┌────────────┐
│  Frontend UI │───▶│ REST API  │───▶│ Service Layer│───▶│ Storage /  │
│  (HTML/JS)   │    │ (FastAPI) │    │  (Python)    │    │  External  │
└──────────────┘    └───────────┘    └──────────────┘    └────────────┘
       │                 │                  │                   │
       │   fetch()       │   Pydantic       │   Business       │   DB / API
       │   WebSocket     │   Validation     │   Logic          │   Connector
       │                 │                  │                   │
       ▼                 ▼                  ▼                   ▼
   murphy-           CORS +             RBAC +              Encrypted
   components.js     Rate Limit         HITL Gates          at Rest
```

### Module Wiring Pattern (Reusable Template)

```
1. Create HTML page → load design system CSS + murphy-components.js
2. Define API helper → fetch() with credentials, error handling
3. Wire to backend → call /api/<module>/* endpoints
4. Register in app.py → add to _html_routes and _UI_ROUTES
5. Add to sidebar → update murphy-components.js navItems
6. Create test → tests/test_<module>_wiring.py
7. Commission → verify each endpoint from UI
```

---

## Automation Specialisation Plan

**Using existing infrastructure to maximise coverage:**

1. **MCB (MultiCursorBrowser)** — Use the 149-action browser automation engine to
   commission every new page automatically.  One MCB test per page that exercises
   every API call and validates the response shape.

2. **TrueSwarmSystem** — Deploy swarms to generate test variations for each module
   using the 7-phase MFGC cycle (EXPAND→TYPE→ENUMERATE→CONSTRAIN→COLLAPSE→BIND→EXECUTE).

3. **Permutation Calibration** — Use `PermutationCalibrationAdapter` to explore
   ordering of UI operations (create→edit→delete vs create→delete, etc.) and find
   edge cases.

4. **Self-Improvement Engine** — Feed wiring test results into
   `PermutationLearningExtension` to automatically learn optimal test sequences.

5. **Commissioning Harness** — Extend `tests/ui/commissioning/test_commissioning_flows.py`
   to include new pages in the chain:
   ```
   Landing → Onboarding → Boards → Workdocs → Time Tracking → Dashboards → ...
   ```

---

## Diagnostic Loop (If Problems Persist)

```
1. SYMPTOM      → Identify the failing UI element or API call
2. ISOLATE      → Is it frontend (JS error) or backend (API error)?
3. TRACE        → Follow the pipeline: UI → API → Service → Storage
4. VALIDATE     → Check request shape, auth headers, response schema
5. REPRODUCE    → Write a minimal test case
6. FIX          → Apply surgical change
7. VERIFY       → Re-run test, check no regressions
8. COMMISSION   → Full page walkthrough via MCB harness
9. DOCUMENT     → Update as-builts, API_ROUTES.md, gap closure log
```

---

## Implementation Sprint Plan

### Sprint 1 (Immediate) — Critical Pages
- [ ] Create `boards.html` — Board System UI (Phase 1 parity)
- [ ] Create `workdocs.html` — Workdocs UI (Phase 5 parity)
- [ ] Create `time_tracking.html` — Time Tracking UI (Phase 6 parity)
- [ ] Register all three in `_html_routes` and sidebar navigation
- [ ] Add wiring commissioning test

### Sprint 2 (Next) — High-Priority Pages ✅ COMPLETE
- [x] Create `dashboards.html` — Dashboard builder
- [x] Create `crm.html` — CRM pipeline view
- [x] Create `portfolio.html` — Gantt/portfolio view
- [x] Create `aionmind.html` — AI orchestration console

### Sprint 3 (Following) — Medium-Priority Pages ✅ COMPLETE
- [x] Create `automations.html` — Automation rule builder
- [x] Create `dev_module.html` — Sprint/bug/release tracker
- [x] Create `service_module.html` — Ticket/KB/SLA manager
- [x] Create `guest_portal.html` — Guest collaboration portal
- [x] Embed collaboration features in boards/workdocs
- [x] Embed founder updates in management.html

### Sprint 4 (Hardening) — Production Commissioning
- [ ] MCB automated commissioning for all new pages
- [ ] Permutation calibration for UI operation sequences
- [ ] Security pen-test on new endpoints
- [x] Full E2E wiring test suite — 141 tests
- [x] Documentation as-built update
- [ ] Production deployment validation

---

## Metrics

| Metric | Current | After Sprint 1 | After Sprint 3 | After Sprint 3+ |
|--------|---------|-----------------|-----------------|------------------|
| Pages with API wiring | 24/54 (44%) | 27/57 (47%) | 35/65 (54%) | 35/65 (54%) |
| Backend modules with UI | 1/15 (7%) | 4/15 (27%) | 11/15 (73%) | 13/15 (87%) |
| Endpoint coverage (UI calls / total) | ~120/700 (17%) | ~170/700 (24%) | ~290/700 (41%) | ~320/700 (46%) |
| Commissioning tests | 222 | 245 | 131 wiring | 141 wiring |

---

*Document generated by Murphy System production closure sprint.  
Updates tracked in this file and cross-referenced to PRODUCTION_READINESS_AUDIT.md.*

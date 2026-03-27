# Management Systems Feature Parity Roadmap

> **Epic:** Achieve full management systems parity — end-to-end feature match
>
> **Owner:** @IKNOWINOT
>
> **Label:** enhancement

---

## Overview

This document tracks the 12-phase roadmap to achieve 100 % feature parity
for management systems inside the Murphy System.  Each phase has a dedicated
implementation module, acceptance criteria, and test suite.

---

## Phase Summary

| # | Phase | Module | Status |
|---|-------|--------|--------|
| 1 | Visual Board System | `src/board_system/` | ✅ Complete |
| 2 | Real-Time Collaboration | `src/collaboration/` | ✅ Complete |
| 3 | Dashboards & Reporting | `src/dashboards/` | ✅ Complete |
| 4 | Project Portfolio Management | `src/portfolio/` | ✅ Complete |
| 5 | Collaborative Docs | `src/workdocs/` | ✅ Complete |
| 6 | Time Tracking & Reporting | `src/time_tracking/` | ✅ Complete |
| 7 | Advanced Automations | `src/automations/` | ✅ Complete |
| 8 | CRM Module | `src/crm/` | ✅ Complete |
| 9 | Dev Module | `src/dev_module/` | ✅ Complete |
| 10 | Service Module | `src/service_module/` | ✅ Complete |
| 11 | Guest / External Collaboration | `src/guest_collab/` | ✅ Complete |
| 12 | Mobile App | `mobile/` | ⚠️ Backend API complete — no native iOS/Android app |

---

## Phase 1 — Visual Board System

**Module:** `src/board_system/`

### Scope
- Board CRUD (create, read, update, delete)
- Groups within boards
- Items (rows) with typed cell values
- 20 column types with validation
- 5 view renderers (Table, Kanban, Calendar, Timeline, Chart)
- Role-based permissions (view / edit / edit_structure / admin)
- Activity log (immutable audit trail)
- REST API under `/api/boards`

### Acceptance Criteria
- [x] Board create / list / get / update / delete
- [x] Group create / update / delete within a board
- [x] Item create / update / delete / move across groups
- [x] Column create / update / delete with 20 column types
- [x] Cell value validation per column type
- [x] Table view renderer with filter & sort
- [x] Kanban view renderer grouped by status column
- [x] Calendar view renderer keyed by date column
- [x] Timeline view renderer with start/end bars
- [x] Chart view renderer with aggregation buckets
- [x] Permission checks on all mutation endpoints
- [x] Activity log recording all mutations
- [x] FastAPI router at `/api/boards`
- [x] Comprehensive test suite (≥ 50 tests)

---

## Phase 2 — Real-Time Collaboration System

**Module:** `src/collaboration/`

### Scope
- Comments on items and boards
- @mentions with user resolution
- In-app notifications
- Activity feed (board-level and global)
- WebSocket-based real-time updates

### Implementation Notes
- `comment_manager.py` — full CRUD with threaded replies and emoji reactions
- `mentions.py` — `parse_mentions()` with pluggable `UserResolver`
- `notifications.py` — `NotificationEngine` with read/archive
- `activity_feed.py` — board, item, user, and global feed queries
- `api.py` — `ConnectionManager` + `/api/collaboration/ws/{board_id}` WebSocket
  endpoint with 30-second keepalive pings and a
  `/api/collaboration/ws/{board_id}/broadcast` REST endpoint for server-push

### Acceptance Criteria
- [x] Comment CRUD on items
- [x] @mention parsing and user resolution
- [x] Notification delivery (in-app)
- [x] Activity feed aggregation
- [x] WebSocket push for board changes

---

## Phase 3 — Customizable Dashboards & Reporting

**Module:** `src/dashboards/`

### Scope
- Widget-based dashboard builder
- Chart widgets (bar, line, pie, stacked)
- Number / summary widgets
- Board data aggregation engine
- Dashboard sharing and permissions

### Implementation Notes
- `dashboard_manager.py` — Dashboard CRUD, add/update/remove widgets
- `widgets.py` — chart, number, table, timeline, battery, text, crm_summary renderers
- `aggregation.py` — `AggregationEngine` with count-by-column and sum-by-column
- `models.py` — `DashboardPermission` (private/workspace/public), `DataSource` with
  `filters` list, `Dashboard.date_range` field for time-range queries

### Acceptance Criteria
- [x] Dashboard CRUD
- [x] Widget library (chart, number, table, timeline, battery, text)
- [x] Data aggregation across boards
- [x] Filter and date-range controls
- [x] Dashboard sharing (`DashboardPermission` enum + permission field on Dashboard)

---

## Phase 4 — Project Portfolio Management

**Module:** `src/portfolio/`

### Scope
- Gantt chart with dependencies
- Milestones and baselines
- Critical-path calculation
- Resource workload view
- Cross-board portfolio dashboard

### Implementation Notes
- `gantt.py` — `GanttEngine` with bars, milestones, baselines, `render_gantt()`
- `dependencies.py` — `DependencyManager` with finish-to-start, start-to-start, etc.
- `critical_path.py` — `CriticalPathCalculator` using forward/backward pass
- `api.py` — FastAPI router at `/api/portfolio`

### Acceptance Criteria
- [x] Gantt view with bar creation, update, and rendering
- [x] Dependency types (finish-to-start, start-to-start, finish-to-finish, start-to-finish)
- [x] Milestone markers
- [x] Baseline snapshots
- [x] Critical-path highlighting

---

## Phase 5 — Collaborative Docs (WorkDocs)

**Module:** `src/workdocs/`

### Scope
- Rich-text document editor
- Embed board widgets inside documents
- Real-time co-editing
- Version history
- Document templates

### Implementation Notes
- `doc_manager.py` — Document CRUD, block editing (11 block types including
  `BOARD_EMBED`), version history, collaborator management, and a template library
- `models.py` — `DocTemplate` dataclass + 4 built-in templates: Meeting Notes,
  Project Brief, Sprint Retrospective, Technical Spec
- `DocManager.create_from_template()` — instantiates a document pre-populated with
  template blocks
- Co-editing: `add_collaborator()` / `remove_collaborator()` track concurrent editors;
  last-write-wins conflict model (OT/CRDT is a future enhancement)

### Acceptance Criteria
- [x] Document CRUD with rich text (11 block types)
- [x] Board widget embedding (`BlockType.BOARD_EMBED`)
- [x] Co-editing with conflict resolution (last-write-wins + collaborator tracking)
- [x] Version history and restore
- [x] Template library (4 built-in + custom templates)

---

## Phase 6 — Time Tracking & Reporting

**Module:** `src/time_tracking/`

### Scope
- Per-item time tracking (start / stop / manual entry)
- Timesheet views (daily / weekly / monthly)
- Time reports and exports
- Budget tracking per board

### Implementation Notes
- `tracker.py` — `TimeTracker` with start/stop/manual log
- `team_views.py` — `TeamTimesheet` with daily/weekly/monthly aggregation
- `export_service.py` — CSV and JSON export (PDF via template)
- `billing_integration.py` — `BillingIntegration` links time entries to budget
- `reporting_service.py` — `ReportingService` for summarised reports
- `dashboard_widgets.py` — time-tracking specific widgets

### Acceptance Criteria
- [x] Start / stop / log time on items
- [x] Timesheet aggregation (daily / weekly / monthly)
- [x] Export to CSV / PDF
- [x] Budget column type integration

---

## Phase 7 — Advanced Automations

**Module:** `src/automations/`

### Scope
- Recurrence rules (daily / weekly / custom cron)
- Conditional logic (if/then/else)
- Cross-board automations
- Integration triggers (email, webhook, Slack)
- Automation templates

### Implementation Notes
- `engine.py` — `AutomationEngine` with full trigger/condition/action evaluation
- `engine.py` — `RecurrenceScheduler` with `MINUTELY`, `HOURLY`, `DAILY`, `WEEKLY`,
  `MONTHLY`, and `CRON` frequencies; `tick(now_iso)` fires due rules
- `models.py` — `TriggerType.SCHEDULE` and `TriggerType.WEBHOOK` added;
  `ActionType.CROSS_BOARD_CREATE` and `ActionType.CROSS_BOARD_UPDATE` added
- Template marketplace: 7 built-in templates (project management, notifications, CRM);
  `create_template()` and `create_rule_from_template()` on `AutomationEngine`
- `receive_webhook()` method dispatches incoming payloads to WEBHOOK-triggered rules

### Acceptance Criteria
- [x] Recurrence engine (`RecurrenceScheduler` with configurable frequency)
- [x] Conditional action chains (if/then/else via `Condition` + `ConditionOperator`)
- [x] Cross-board item creation / updates (`CROSS_BOARD_CREATE` / `CROSS_BOARD_UPDATE`)
- [x] External trigger adapters (`TriggerType.WEBHOOK` + `receive_webhook()`)
- [x] Template marketplace (7 built-in templates + custom template creation)

---

## Phase 8 — CRM Module

**Module:** `src/crm/`

### Scope
- Contact and company management
- Sales pipeline boards (preconfigured)
- Email tracking integration
- Deal stages with probability
- CRM dashboards

### Implementation Notes
- `crm_manager.py` — contact, deal, pipeline CRUD + activity log
- `models.py` — `EmailInteraction` with sent/received direction, open/click tracking,
  and RFC-2822 `message_id` threading
- `crm_manager.py` — `track_email()`, `mark_email_opened()`, `mark_email_clicked()`,
  `list_email_interactions()` for full email audit trail
- `_BUILTIN_PIPELINE_TEMPLATES` — 3 pre-built pipelines: Standard Sales, Enterprise
  Sales Cycle, SaaS Trial; `create_pipeline_from_template()` instantiates them
- `crm_summary()` — returns aggregated KPIs (contacts, deals, pipeline value,
  email counts) ready for dashboard widgets
- Dashboard: `WidgetType.CRM_SUMMARY` in `src/dashboards/models.py` +
  `render_crm_summary_widget()` in `src/dashboards/widgets.py`

### Acceptance Criteria
- [x] Contact / company CRUD
- [x] Pipeline board templates (3 built-in: Standard Sales, Enterprise, SaaS Trial)
- [x] Email send / receive tracking (`EmailInteraction`, open/click events)
- [x] Deal value and probability columns (`Deal.value`, `Stage.probability`)
- [x] CRM-specific dashboard widgets (`WidgetType.CRM_SUMMARY`)

---

## Phase 9 — Dev Module

**Module:** `src/dev_module/`

### Scope
- Sprint boards with velocity tracking
- Product roadmap timeline
- Bug tracker with severity / priority
- Git integration dashboard (commits, PRs)
- Release management

### Acceptance Criteria
- [x] Sprint board templates
- [x] Velocity / burndown chart widgets
- [x] Bug tracker column presets
- [x] Git activity feed (read-only)
- [x] Release checklist automation

---

## Phase 10 — Service Module

**Module:** `src/service_module/`

### Scope
- Service catalog with request forms
- SLA tracking with escalation rules
- Ticket routing (round-robin, load-based)
- Knowledge-base articles
- Customer satisfaction surveys

### Acceptance Criteria
- [x] Service request form builder
- [x] SLA timer and breach alerts
- [x] Auto-routing engine
- [x] Knowledge-base CRUD
- [x] CSAT collection and reporting

---

## Phase 11 — Guest / External Collaboration

**Module:** `src/guest_collab/`

### Scope
- Guest user invitations (limited access)
- Shareable board links (read-only or edit)
- Client portal with branded views
- External form submissions

### Acceptance Criteria
- [x] Guest invite and permission scoping
- [x] Shareable link generation
- [x] Client portal branding settings
- [x] Form-to-item ingestion

---

## Phase 12 — Mobile App

**Module:** `mobile/`

### Scope
- iOS and Android native apps
- Offline mode with sync
- Push notifications
- Board and item views
- Quick-add and search

### Current State
The `mobile/` directory contains a **complete backend API and data models** for
mobile device management, push notifications (device registration + delivery),
and offline sync with conflict detection and resolution.

There are **no native iOS or Android applications** (no React Native, Flutter,
or Swift/Kotlin code).  The backend sync API (`MobileManager`) and push
notification layer are production-ready and can back any native client when
built.

### Acceptance Criteria
- [x] Device registration and management (`MobileManager.register_device`)
- [x] Offline data cache with conflict resolution (`push_changes`, `resolve_conflicts`)
- [x] Push notification delivery (per-device `send_notification`, `mark_delivered`)
- [x] FastAPI router at `/api/mobile`
- [ ] iOS build and TestFlight release *(native app — future work)*
- [ ] Android build and Play Store beta *(native app — future work)*
- [ ] Full board / item / view parity with native mobile UI *(future work)*

---

*Last updated: 2026-03-24*

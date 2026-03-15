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
| 2 | Real-Time Collaboration | `src/collaboration/` | 🟡 Code exists — acceptance criteria unvalidated |
| 3 | Dashboards & Reporting | `src/dashboards/` | 🟡 Code exists — acceptance criteria unvalidated |
| 4 | Project Portfolio Management | `src/portfolio/` | 🟡 Code exists — acceptance criteria unvalidated |
| 5 | Collaborative Docs | `src/workdocs/` | 🟡 Code exists — acceptance criteria unvalidated |
| 6 | Time Tracking & Reporting | `src/time_tracking/` | 🟡 Code exists — acceptance criteria unvalidated |
| 7 | Advanced Automations | `src/automations/` | 🟡 Code exists — acceptance criteria unvalidated |
| 8 | CRM Module | `src/crm/` | 🟡 Code exists — acceptance criteria unvalidated |
| 9 | Dev Module | `src/dev_module/` | ✅ Complete |
| 10 | Service Module | `src/service_module/` | ✅ Complete |
| 11 | Guest / External Collaboration | `src/guest_collab/` | ✅ Complete |
| 12 | Mobile App | `mobile/` | 🟡 Backend API exists — no native iOS/Android app |

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

### Scope
- Comments on items and boards
- @mentions with user resolution
- In-app notifications
- Activity feed (board-level and global)
- WebSocket-based real-time updates

### Acceptance Criteria
- [ ] Comment CRUD on items
- [ ] @mention parsing and user resolution
- [ ] Notification delivery (in-app)
- [ ] Activity feed aggregation
- [ ] WebSocket push for board changes

---

## Phase 3 — Customizable Dashboards & Reporting

### Scope
- Widget-based dashboard builder
- Chart widgets (bar, line, pie, stacked)
- Number / summary widgets
- Board data aggregation engine
- Dashboard sharing and permissions

### Acceptance Criteria
- [ ] Dashboard CRUD
- [ ] Widget library (chart, number, table, timeline)
- [ ] Data aggregation across boards
- [ ] Filter and date-range controls
- [ ] Dashboard sharing

---

## Phase 4 — Project Portfolio Management

### Scope
- Gantt chart with dependencies
- Milestones and baselines
- Critical-path calculation
- Resource workload view
- Cross-board portfolio dashboard

### Acceptance Criteria
- [ ] Gantt view with drag-to-reschedule
- [ ] Dependency types (finish-to-start, start-to-start, etc.)
- [ ] Milestone markers
- [ ] Baseline snapshots
- [ ] Critical-path highlighting

---

## Phase 5 — Collaborative Docs (WorkDocs)

### Scope
- Rich-text document editor
- Embed board widgets inside documents
- Real-time co-editing
- Version history
- Document templates

### Acceptance Criteria
- [ ] Document CRUD with rich text
- [ ] Board widget embedding
- [ ] Co-editing with conflict resolution
- [ ] Version history and restore
- [ ] Template library

---

## Phase 6 — Time Tracking & Reporting

### Scope
- Per-item time tracking (start / stop / manual entry)
- Timesheet views (daily / weekly / monthly)
- Time reports and exports
- Budget tracking per board

### Acceptance Criteria
- [ ] Start / stop / log time on items
- [ ] Timesheet aggregation
- [ ] Export to CSV / PDF
- [ ] Budget column type integration

---

## Phase 7 — Advanced Automations

### Scope
- Recurrence rules (daily / weekly / custom cron)
- Conditional logic (if/then/else)
- Cross-board automations
- Integration triggers (email, webhook, Slack)
- Automation templates

### Acceptance Criteria
- [ ] Recurrence engine
- [ ] Conditional action chains
- [ ] Cross-board item creation / updates
- [ ] External trigger adapters
- [ ] Template marketplace

---

## Phase 8 — CRM Module

### Scope
- Contact and company management
- Sales pipeline boards (preconfigured)
- Email tracking integration
- Deal stages with probability
- CRM dashboards

### Acceptance Criteria
- [ ] Contact / company CRUD
- [ ] Pipeline board templates
- [ ] Email send / receive tracking
- [ ] Deal value and probability columns
- [ ] CRM-specific dashboard widgets

---

## Phase 9 — Dev Module

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

### Scope
- iOS and Android native apps
- Offline mode with sync
- Push notifications
- Board and item views
- Quick-add and search

### Current State
The `mobile/` directory contains a **backend API and data models** for mobile
device management, push notifications, and offline sync.  There are **no native
iOS or Android applications** (no React Native, Flutter, or Swift/Kotlin code).
The acceptance criteria below reflect aspirational targets for a future native
mobile client.

### Acceptance Criteria
- [ ] iOS build and TestFlight release
- [ ] Android build and Play Store beta
- [ ] Offline data cache with conflict resolution *(backend sync API exists)*
- [ ] Push notification delivery *(backend notification API exists)*
- [ ] Full board / item / view parity with web

---

*Last updated: 2026-03-10*

## Self-Fix Loop (ARCH-005)

### Overview

The **Autonomous Self-Fix Loop** (`src/self_fix_loop.py`) closes the remediation gap by implementing a closed-loop cycle that detects, plans, executes, tests, and verifies runtime fixes — with no human intervention required for runtime-adjustable issues.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-FIX LOOP  (ARCH-005)                    │
│                                                                 │
│  1. DIAGNOSE  → Scan system for errors/gaps/bugs               │
│  2. PLAN      → Generate structured remediation plan            │
│  3. EXECUTE   → Apply fixes (config changes, runtime patches,  │
│  │               parameter adjustments, recovery procedures)    │
│  4. TEST      → Run targeted tests proving the fix works       │
│  5. VERIFY    → Confirm gap is closed, no regressions          │
│  6. REPEAT    → If gaps remain, go to step 1                   │
│  7. REPORT    → Generate final verification report             │
└─────────────────────────────────────────────────────────────────┘
```

### Component Wiring

| Dependency | Integration Point |
|---|---|
| `SelfImprovementEngine` (ARCH-001) | `diagnose()` calls `get_remediation_backlog()`, `generate_proposals()`; `plan()` calls `generate_executable_fix()` |
| `SelfHealingCoordinator` (OBS-004) | `execute()` registers new `RecoveryProcedure` objects for unhandled failure categories |
| `BugPatternDetector` (DEV-004) | `diagnose()` calls `run_detection_cycle()` and `get_patterns()` |
| `EventBackbone` | Publishes `SELF_FIX_STARTED`, `SELF_FIX_PLAN_CREATED`, `SELF_FIX_EXECUTED`, `SELF_FIX_TESTED`, `SELF_FIX_VERIFIED`, `SELF_FIX_COMPLETED`, `SELF_FIX_ROLLED_BACK` |
| `PersistenceManager` | Every `FixPlan`, `FixExecution`, and `LoopReport` is durably saved |

### Fix Types

| `fix_type` | Description | Autonomous? |
|---|---|---|
| `threshold_tuning` | Adjusts confidence thresholds, timeout values | ✅ Yes |
| `recovery_registration` | Registers new `RecoveryProcedure` handlers | ✅ Yes |
| `route_optimization` | Applies routing weight changes from engine data | ✅ Yes |
| `config_adjustment` | Modifies runtime configuration values | ✅ Yes |
| `code_proposal` | Code-level change — logged for human review | ❌ Human review |

### Safety Invariants

1. **Never modifies source files on disk** — all fixes operate at the runtime level.
2. **Bounded iterations** — `max_iterations` (default 10) prevents infinite loops.
3. **Mutex enforcement** — `RuntimeError` raised if a second loop is started concurrently.
4. **Rollback on failure** — every `FixPlan` carries `rollback_steps`; on test failure, all steps are reversed.
5. **Full audit trail** — every plan, execution, test, and report is persisted and published as events.
6. **Code proposals require human approval** — source files are never touched autonomously.

---

## Murphy Immune Engine (ARCH-014)

**Module:** `src/murphy_immune_engine.py`  
**Tests:** `tests/test_murphy_immune_engine.py`  
**Docs:** `docs/IMMUNE_ENGINE.md`

Next-generation autonomous self-coding system that wraps and extends all existing self-healing components.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      MURPHY IMMUNE ENGINE  (ARCH-014)                        │
│                                                                              │
│  DesiredStateReconciler ──▶ PredictiveFailureAnalyzer ──▶ ImmunityMemory    │
│          ↓                          ↓                          ↓             │
│  CascadeAnalyzer ◄──────── MurphyImmuneEngine ──────▶ ChaosHardenedValidator│
│          ↓                          ↓                                        │
│  SelfFixLoop (ARCH-005)      EventBackbone / PersistenceManager              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Integration Points

| Component | Integration |
|---|---|
| `SelfFixLoop` (ARCH-005) | Delegates `diagnose()`, `plan()`, `execute()`, `test()`, `rollback()` |
| `SelfImprovementEngine` (ARCH-001) | Injected into `SelfFixLoop` |
| `SelfHealingCoordinator` (OBS-004) | State queried by `DesiredStateReconciler` |
| `BugPatternDetector` (DEV-004) | Patterns fed to `PredictiveFailureAnalyzer` |
| `EventBackbone` | Publishes 7 new event types |
| `PersistenceManager` | Stores `ImmuneReport` per cycle |
| `FailureInjectionPipeline` | Used by `ChaosHardenedValidator` |

### Novel Capabilities

| Capability | Component |
|---|---|
| Kubernetes-style desired-state reconciliation | `DesiredStateReconciler` |
| Statistical predictive failure analysis | `PredictiveFailureAnalyzer` |
| Biological immune memory (instant replay) | `ImmunityMemory` |
| Chaos-hardened fix validation | `ChaosHardenedValidator` |
| Cascade-aware fix planning | `CascadeAnalyzer` |

### Safety Invariants

1. **Never modifies source files on disk.**
2. **Bounded by max_iterations** (default 20).
3. **Mutex enforcement** — `RuntimeError` if cycle already running.
4. **Rollback on test failure.**
5. **Chaos validation required** before ImmunityMemory promotion.
6. **Cascade check required** before ImmunityMemory promotion.
7. **Full audit trail** via EventBackbone + PersistenceManager.

---

## Communication Hub (COMMS-001)

**Location:** `src/communication_hub.py`, `src/comms_hub_routes.py`  
**UI:** `communication_hub.html` at `/ui/comms-hub`  
**Database:** 8 SQLAlchemy ORM models in `src/db.py` (tables prefixed `comms_`)

### Purpose
Unified onboard communication layer providing instant messaging, voice/video calling
(WebRTC signalling), email, per-channel automation rules, and a Discord-style moderator
console capable of broadcasting to multiple external platforms simultaneously.

### Store Components

| Class | Table(s) | Responsibility |
|-------|----------|----------------|
| `IMStore` | `comms_im_threads`, `comms_im_messages` | Thread/message CRUD, automod, reactions |
| `CallSessionStore` | `comms_call_sessions` | Voice/video session lifecycle, SDP/ICE, duration |
| `EmailStore` | `comms_emails` | Compose, inbox/outbox, mark-read, automod |
| `AutomationRuleStore` | `comms_automation_rules` | Rule CRUD, trigger evaluation, fire-count tracking |
| `ModeratorConsole` | `comms_user_profiles`, `comms_mod_audit`, `comms_broadcasts` | Moderation actions, blocked-word lists, multi-platform broadcast, audit log |

### API Surface

| Prefix | Count | Description |
|--------|-------|-------------|
| `/api/comms/im/*` | 6 | IM threads and messages |
| `/api/comms/voice/*` | 8 | Voice call sessions |
| `/api/comms/video/*` | 5 | Video call sessions |
| `/api/comms/email/*` | 5 | Email send, inbox, outbox |
| `/api/comms/automate/*` | 6 | Automation rules |
| `/api/moderator/*` | 18 | Moderator console |

### Persistence Model

```
         ┌─────────────────────────────────────────┐
         │           SQLite (murphy_logs.db)        │
         │   comms_im_threads  comms_im_messages    │
         │   comms_call_sessions  comms_emails      │
         │   comms_automation_rules                 │
         │   comms_user_profiles  comms_mod_audit   │
         │   comms_broadcasts                       │
         └─────────────────────────────────────────┘
                            ▲
              ┌─────────────┴──────────────┐
              │       Store Layer           │
              │  IMStore  CallSessionStore  │
              │  EmailStore  AutomRule…     │
              │  ModeratorConsole           │
              └─────────────┬──────────────┘
                            ▲
              ┌─────────────┴──────────────┐
              │     FastAPI Router          │
              │  /api/comms/*               │
              │  /api/moderator/*           │
              └────────────────────────────┘
```

### Fallback Behaviour
When SQLAlchemy is unavailable (import error, DB connection failure), every store
automatically falls back to in-process dicts.  The server continues to function; data
is not persisted between restarts.

### Auto-Moderation
- Default blocked-word list: `spam`, `scam`, `phishing`, `malware`, `ransomware`
- Custom words configurable per-deployment via `POST /api/moderator/automod/words`
- Every message and email is checked before storage; automod result attached to record
- Flagged messages trigger the `auto-moderate flagged IM` automation rule by default

### Broadcast Platforms
Supported: `im`, `voice`, `video`, `email`, `slack`, `discord`, `matrix`, `sms`

### Default Seeds (on startup)
- 3 automation rules: auto-reply missed call, escalate urgent email, automod-delete flagged IM
- 3 broadcast targets: `im#general`, `email#all-staff`, `matrix#murphy-general`

### Integration Points
- `src/db.py` — SQLAlchemy engine, session factory, `create_tables()`
- `src/runtime/app.py` — router registration, `/ui/comms-hub` HTML route
- `tests/test_communication_hub.py` — 83 tests

---

## Founder Update Engine (ARCH-007)

**Location:** `src/founder_update_engine/`  
**Tests:** `tests/test_founder_update_engine.py` (133 tests)  
**Design Label:** ARCH-007

### Purpose
Central intelligence layer that monitors how Murphy updates and maintains itself.
Provides the Founder with a live operating picture (health scores, bug patterns,
vulnerability counts, recovery rates) and generates actionable recommendations for
SDK updates, security patches, maintenance tasks, and bug responses.  All actions
are proposals — execution always requires explicit approval unless flagged
`auto_applicable=True`.

### Modules

| Module | Class | Responsibility |
|--------|-------|----------------|
| `recommendation_engine.py` | `RecommendationEngine` | Central recommendation store — 9 types, 5 priorities, persistence, 6 query methods |
| `subsystem_registry.py` | `SubsystemRegistry` | Auto-discovers Murphy subsystems; tracks health, update history, pending recs |
| `update_coordinator.py` | `UpdateCoordinator` | Applies updates within maintenance windows; rate-limits changes; full audit trail |
| `sdk_update_scanner.py` | `SdkUpdateScanner` | Scans requirements files; detects patch/minor/major bumps; integrates vulnerability data |
| `auto_update_applicator.py` | `AutoUpdateApplicator` | Applies auto-applicable recs with health gates, rate limiting, dry-run mode |
| `bug_response_handler.py` | `BugResponseHandler` | Classifies bug reports; generates response drafts + BUG_RESPONSE/SECURITY recs |
| `operating_analysis_dashboard.py` | `OperatingAnalysisDashboard` | Aggregates fleet health, bug patterns, recovery rates, vuln counts → snapshots + recs |

### Recommendation Types

| Type | Source | Auto-Applicable |
|------|--------|----------------|
| `SDK_UPDATE` (patch bump) | `SdkUpdateScanner` | ✅ Yes |
| `SDK_UPDATE` (minor/major bump) | `SdkUpdateScanner` | ❌ No |
| `SECURITY` | `SdkUpdateScanner`, `BugResponseHandler`, `OperatingAnalysisDashboard` | ❌ No |
| `AUTO_UPDATE` | `SdkUpdateScanner` | ✅ Yes |
| `BUG_RESPONSE` | `BugResponseHandler` | ❌ No |
| `PERFORMANCE` | `OperatingAnalysisDashboard` | ❌ No |
| `MAINTENANCE` | `OperatingAnalysisDashboard` | ❌ No |

### Operating Analysis Thresholds

| Metric | Warning Threshold | Action |
|--------|-------------------|--------|
| Fleet health score | < 80% | `PERFORMANCE` recommendation (HIGH) |
| Fleet health score | < 50% | `MAINTENANCE` recommendation (CRITICAL) |
| Active bug patterns | > 5 | `MAINTENANCE` recommendation |
| Self-healing recovery rate | < 70% | `MAINTENANCE` recommendation |
| Open vulnerabilities | > 3 | `SECURITY` recommendation |

### Data Flow

```
External Inputs                  Founder Update Engine
─────────────────────────────────────────────────────────────────
requirements*.txt ──────────────▶ SdkUpdateScanner
                                       │ SDK_UPDATE / SECURITY / AUTO_UPDATE recs
                                       ▼
Incoming bug reports ────────────▶ BugResponseHandler
                                       │ BUG_RESPONSE / SECURITY recs
                                       ▼
SubsystemRegistry   ─────────────▶ OperatingAnalysisDashboard
BugPatternDetector  ─────────────▶       │ DashboardSnapshot
SelfHealingCoord.   ─────────────▶       │ PERFORMANCE / MAINTENANCE / SECURITY recs
DependencyAudit     ─────────────▶       │
                                         ▼
                               RecommendationEngine (central store)
                                         │
                                         ▼
                               UpdateCoordinator (applies auto_applicable recs)
                                         │
                               AutoUpdateApplicator (health-gated execution)
```

### Subsystem Health States

```
healthy ──▶ degraded ──▶ failed
   ▲                        │
   └─────── recovered ───────┘
unknown (initial state for auto-discovered subsystems)
```

### Safety Invariants

1. **Never modifies source files on disk** — all actions are proposals only.
2. **Health gate** — `AutoUpdateApplicator` aborts a cycle if any subsystem is FAILED.
3. **Rate limiting** — configurable max applications per maintenance window.
4. **Dry-run mode** — full simulation without execution; all outcomes logged as `SKIPPED_DRY_RUN`.
5. **Founder approval required** for CRITICAL/HIGH security and all major version bumps.
6. **Thread-safe** — all shared state guarded by `threading.Lock`.
7. **Bounded history** — all stores cap their history (responses: 1000, snapshots: 200, records: 500).

### Integration Points

| Component | How Used |
|-----------|---------|
| `BugPatternDetector` (DEV-004) | `BugResponseHandler` feeds errors in; `OperatingAnalysisDashboard` reads active pattern counts |
| `SelfHealingCoordinator` (OBS-004) | `OperatingAnalysisDashboard` reads recovery history and success rate |
| `DependencyAuditEngine` (DEV-005) | `SdkUpdateScanner` reads vulnerability findings; `OperatingAnalysisDashboard` reads open vuln count |
| `SubsystemRegistry` (ARCH-007) | `UpdateCoordinator`, `OperatingAnalysisDashboard` iterate registered subsystems |
| `PersistenceManager` | All modules persist state via `save_document` / `load_document` |
| `EventBackbone` | Publishes `LEARNING_FEEDBACK` and `SYSTEM_HEALTH` events on key actions |

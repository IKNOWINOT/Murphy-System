# Founder Update Engine — ARCH-007

> **Design Label:** ARCH-007 — Founder Update Engine  
> **Owner:** Backend Team  
> **License:** BSL 1.1  
> **Copyright:** © 2020 Inoni Limited Liability Company, Creator: Corey Post

---

## Overview

The Founder Update Engine gives Murphy's operator a single, unified view of how the
system is maintaining itself — and a clear action list for what to do next.  It
aggregates health data from across the entire Murphy fleet, scans dependencies for
outdated and vulnerable packages, classifies incoming bug reports, and surfaces
prioritised recommendations for the Founder to review and approve.

**Nothing executes without approval** unless explicitly marked `auto_applicable=True`
(reserved for low-risk patch-level SDK bumps that pass all health gates).

---

## File Structure

```
src/founder_update_engine/
├── __init__.py                     # Public exports for all classes
├── recommendation_engine.py        # Central recommendation store (9 types, 5 priorities)
├── subsystem_registry.py           # Fleet registry — health, versions, update history
├── update_coordinator.py           # Maintenance-window scheduling & audit trail
├── sdk_update_scanner.py           # requirements*.txt scanner + vulnerability integration
├── auto_update_applicator.py       # Health-gated auto-application engine
├── bug_response_handler.py         # Bug report classification + response drafting
└── operating_analysis_dashboard.py # Fleet-wide health aggregator + snapshot history

tests/
└── test_founder_update_engine.py   # 133 tests covering all modules (PR 1–3)

docs/
└── FOUNDER_UPDATE_ENGINE.md        # This document
```

---

## Architecture

```
                       ┌─────────────────────────────────────────────┐
                       │          Founder Update Engine              │
                       │              (ARCH-007)                     │
                       └────────────────┬────────────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
  SdkUpdateScanner            BugResponseHandler          OperatingAnalysisDashboard
  (requirements*.txt          (incoming bug reports        (fleet health aggregator)
   + vuln data)                → classifications,              │
          │                     response drafts,               ├─ SubsystemRegistry
          │                     recommendations)               ├─ BugPatternDetector
          │                             │                      ├─ SelfHealingCoordinator
          └──────────────┬──────────────┘                      └─ DependencyAuditEngine
                         │
                         ▼
              ┌─────────────────────┐
              │  RecommendationEngine│  ◀── central store
              │  (9 types, 5 prio)  │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  UpdateCoordinator  │  ◀── maintenance windows
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │AutoUpdateApplicator │  ◀── health-gated execution
              └─────────────────────┘
```

---

## Modules

### 1. `RecommendationEngine`

Central store for all recommendations generated anywhere in the engine.

**Recommendation types:**

| Type | When Generated | Auto-Applicable |
|------|---------------|----------------|
| `SDK_UPDATE` (patch) | SdkUpdateScanner detects patch bump | ✅ |
| `SDK_UPDATE` (minor/major) | SdkUpdateScanner detects breaking bump | ❌ |
| `SECURITY` | Vulnerable package or security bug report | ❌ |
| `AUTO_UPDATE` | Safe patch-level update confirmed | ✅ |
| `BUG_RESPONSE` | Bug report ingested | ❌ |
| `PERFORMANCE` | Fleet health < 80% | ❌ |
| `MAINTENANCE` | Fleet health < 50%, bug patterns > 5, recovery rate < 70% | ❌ |
| `DEPENDENCY_UPGRADE` | Major dependency version available | ❌ |
| `CONFIGURATION` | Sub-optimal configuration detected | ❌ |
| `GENERAL` | Catch-all informational recommendations | ❌ |

**Priority levels:** `CRITICAL` → `HIGH` → `MEDIUM` → `LOW` → `INFORMATIONAL`

**Recommendation lifecycle:** `pending` → `approved` / `rejected` → `applied`

---

### 2. `SubsystemRegistry`

Auto-discovers all Murphy subsystems from the `src/` directory tree and tracks:
- Health status (`healthy` / `degraded` / `failed` / `unknown`)
- Current version string
- Last update timestamp
- Dependency list
- Open recommendation count
- Full update history

Health status is updated by the `UpdateCoordinator` after each successful or failed
update application, and by `OperatingAnalysisDashboard` after each snapshot.

---

### 3. `UpdateCoordinator`

Schedules and records update applications within configurable `MaintenanceWindow`
objects (name, start time, end time, max changes per window).

Each applied update is recorded as an `UpdateRecord` with:
- Subsystem name, version before/after
- Recommendation reference
- Duration, outcome, notes
- Timestamp

---

### 4. `SdkUpdateScanner`

Scans all `requirements*.txt` files in the project root:

1. Parses each pinned `package==version` line
2. Compares against a known-versions registry (updated via `register_known_version()`)
3. Classifies each bump as `patch`, `minor`, or `major`
4. Optionally ingests vulnerability data from `DependencyAuditEngine`
5. Returns an `SdkScanReport` with a `PackageScanRecord` per package

**Recommendation logic:**
- Patch bump + no CVE → `AUTO_UPDATE` (auto-applicable)
- Patch bump + CVE → `SECURITY` (requires approval)
- Minor/major bump → `SDK_UPDATE` (requires approval)

---

### 5. `AutoUpdateApplicator`

Executes `auto_applicable` recommendations with the following safety gates:

1. **Health gate** — aborts entire cycle if any registered subsystem is `FAILED`
2. **Rate limit** — maximum N applications per cycle (configurable, default 10)
3. **Already-applied guard** — skips recommendations already in `applied` state
4. **Dry-run mode** — full simulation, all outcomes logged as `SKIPPED_DRY_RUN`

**Outcome codes:**

| Code | Meaning |
|------|---------|
| `APPLIED` | Handler executed and returned `True` |
| `FAILED` | Handler raised an exception or returned `False` |
| `SKIPPED_HEALTH` | Cycle aborted — subsystem in FAILED state |
| `SKIPPED_RATE_LIMIT` | Per-cycle application limit reached |
| `SKIPPED_DRY_RUN` | Dry-run mode active |
| `ALREADY_APPLIED` | Recommendation already in `applied` status |
| `NOT_APPLICABLE` | Recommendation not marked `auto_applicable` |

---

### 6. `BugResponseHandler`

Ingests `BugReport` objects and produces `BugResponse` objects with:

**Severity classification** (reporter hint → normalised):
`critical` / `blocker` → `CRITICAL`  
`high` / `major` → `HIGH`  
`medium` / `normal` → `MEDIUM`  
`low` / `minor` / `trivial` → `LOW`  
Unknown → keyword escalation or `MEDIUM`

**Category classification** (keyword matching):
- `SECURITY` — injection, xss, csrf, auth, password, token, exploit, vuln, sql
- `DATA_LOSS` — lost, deleted, corrupt, missing data, disappeared, overwrite
- `CRASH` — traceback, exception, crash, null, none, attributeerror, typeerror
- `PERFORMANCE` — slow, timeout, latency, memory, cpu, oom, leak, bottleneck
- `REGRESSION` — worked, used to, regression, broke, after update, after deploy
- `OTHER` — fallback

**Generated content per report:**
- 2–4 root-cause hypotheses
- 1–3 structured action items (triage, security review, hotfix assessment, regression test)
- Human-readable response draft (greeting + acknowledgment + detail + hypotheses)
- 1 `BUG_RESPONSE` recommendation (always)
- 1 `SECURITY` recommendation (for security-category bugs only)

---

### 7. `OperatingAnalysisDashboard`

Captures `DashboardSnapshot` objects by aggregating:

| Data Source | Metric Collected |
|-------------|-----------------|
| `SubsystemRegistry` | Per-subsystem health, pending recs, update history |
| `BugPatternDetector` | Active pattern count, critical pattern count |
| `SelfHealingCoordinator` | Recent recovery attempt count, success rate |
| `DependencyAuditEngine` | Open vulnerability finding count |
| `RecommendationEngine` | Total open (pending + approved) recommendation count |

**Threshold-triggered recommendations:**

| Metric | Threshold | Recommendation Generated |
|--------|-----------|--------------------------|
| Fleet health score | < 80% | `PERFORMANCE` HIGH |
| Fleet health score | < 50% | `MAINTENANCE` CRITICAL |
| Active bug patterns | > 5 | `MAINTENANCE` HIGH (CRITICAL if any are critical) |
| Recovery success rate | < 70% | `MAINTENANCE` HIGH |
| Open vulnerabilities | > 3 | `SECURITY` HIGH |

Each snapshot includes human-readable `analysis_notes` explaining what was found.

---

## Safety Invariants

1. **Read-only** — no module ever modifies source files on disk.
2. **Health gate** — `AutoUpdateApplicator` skips all applications when any subsystem is FAILED.
3. **Rate limiting** — configurable max applications per cycle prevents runaway automation.
4. **Dry-run mode** — full simulation path available with zero side effects.
5. **Founder approval required** for: CRITICAL/HIGH security recs, all major version bumps, all BUG_RESPONSE recs with HIGH/CRITICAL severity.
6. **Thread-safe** — all shared state protected by `threading.Lock`.
7. **Bounded storage** — all history stores are capped (responses: 1 000, snapshots: 200, records: 500, recommendations: no cap by design — only one per subsystem+type+priority is expected).
8. **Graceful degradation** — every integration is wrapped in try/except; missing optional dependencies (BugPatternDetector, SelfHealingCoordinator, etc.) are simply skipped without error.

---

## Integration Points

| System | Design Label | Integration |
|--------|-------------|-------------|
| `BugPatternDetector` | DEV-004 | `BugResponseHandler` feeds errors in via `ingest_error()`. `OperatingAnalysisDashboard` reads patterns via `get_patterns()`. |
| `SelfHealingCoordinator` | OBS-004 | `OperatingAnalysisDashboard` reads recovery history via `get_history()`. |
| `DependencyAuditEngine` | DEV-005 | `SdkUpdateScanner` pulls CVE data. `OperatingAnalysisDashboard` reads `get_reports()` for open vuln count. |
| `PersistenceManager` | INFRA-001 | All modules persist state via `save_document()` / `load_document()` — survives restarts. |
| `EventBackbone` | INFRA-002 | Publishes `LEARNING_FEEDBACK` events (bug responses, update applications) and `SYSTEM_HEALTH` events (dashboard snapshots). |

---

## Testing

All tests live in `tests/test_founder_update_engine.py` (133 tests):

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestRecommendationEngine*` | 25 | CRUD, dedup, status, persistence, types |
| `TestSubsystemRegistry*` | 20 | Register, discover, health update, persistence |
| `TestUpdateCoordinator*` | 22 | Window scheduling, rate limits, history |
| `TestSdkUpdateScanner*` | 18 | Scan, bump classification, vuln integration |
| `TestAutoUpdateApplicator*` | 27 | Health gate, rate limit, dry run, outcomes |
| `TestBugResponseHandler*` | 24 | Severity/category classification, security escalation, persistence |
| `TestOperatingAnalysisDashboard*` | 20 | Snapshot capture, threshold recs, persistence |
| `TestSubsystemHealthSummary` | 1 | Model serialisation |
| `TestDashboardSnapshot` | 2 | Model serialisation, health score range |

Run with:
```bash
python -m pytest tests/test_founder_update_engine.py -v --override-ini="addopts="
```

---

## Roadmap (PR 4 — Pending)

- `src/runtime/app.py` — REST API endpoints at `/api/founder-update/*`
- `founder_dashboard.html` — Founder Dashboard UI (sidebar: ACCOUNT section)
- Wire `BugResponseHandler` and `OperatingAnalysisDashboard` into the live app
- MultiCursor browser verification of all new UI pages on the production deployment

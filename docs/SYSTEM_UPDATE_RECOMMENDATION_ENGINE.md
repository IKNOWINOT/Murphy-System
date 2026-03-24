# ARCH-008 — System Update Recommendation Engine

**Design Label:** ARCH-008  
**Owner:** Backend Team / Platform Engineering  
**File:** `src/system_update_recommendation_engine.py`  
**License:** BSL 1.1  
**Copyright:** © 2020 Inoni Limited Liability Company  
**Creator:** Corey Post

---

## Overview

The **System Update Recommendation Engine** is the unified entry point for the Murphy System's self-maintenance intelligence. It aggregates signals from all self-improvement subsystems and produces multi-form, prioritised recommendations for the operator or founder.

Before this engine, each subsystem (self-improvement, bug detection, dependency auditing, health monitoring, etc.) generated proposals in isolation with no shared priority or cross-subsystem correlation. ARCH-008 provides a single pipeline that:

1. **Collects** signals from all registered subsystems
2. **Analyzes** cross-subsystem correlations (e.g., a bug touching a vulnerable dependency)
3. **Prioritizes** recommendations by severity, frequency, impact, and confidence
4. **Formats** signals into typed recommendation objects
5. **Persists** cycle results via `PersistenceManager`
6. **Publishes** events via `EventBackbone`

---

## Integration with Existing Infrastructure

| Subsystem | Design Label | Integration |
|-----------|-------------|-------------|
| `SelfImprovementEngine` | ARCH-001 | Pulls `ImprovementProposal` objects via `generate_proposals()` |
| `BugPatternDetector` | DEV-004 | Pulls `BugReport` summaries via `get_reports()` |
| `DependencyAuditEngine` | DEV-005 | Pulls advisory findings via `get_reports()` |
| `HealthMonitor` | `operational_completeness` | Pulls system health via `get_system_health()` |
| `AutonomousRepairSystem` | ARCH-006 | Pulls repair proposals via `get_proposals()` |
| `SelfAutomationOrchestrator` | ARCH-002 | Pulls open gaps via `get_open_gaps()` |
| `PersistenceManager` | — | Saves/loads state via `save_document` / `load_document` |
| `EventBackbone` | — | Publishes `SYSTEM_HEALTH` events on each cycle |

All integrations are **optional**: if a subsystem is `None` or raises an exception, the engine continues with degraded (but functional) output.

---

## Recommendation Types

The engine produces five recommendation forms:

### `MaintenanceRecommendation`
Triggered by degraded/unhealthy component health or repair proposals.

- `action_type`: `restart`, `config_reload`, `cache_clear`, `log_rotation`, `health_check_schedule`
- `target_service`: Component name
- `priority`: `critical` / `high` / `medium` / `low`
- `auto_applicable`: False by default; set True only for low-risk degraded-state actions
- `requires_review`: True by default (unhealthy always requires review)

### `SDKUpdateRecommendation`
Triggered by dependency audit findings (CVEs, outdated packages).

- `package_name`, `current_version`, `recommended_version`
- `breaking_changes`: bool — whether migration work is needed
- `migration_guide`: Optional link or summary
- `compatibility_notes`: Compatibility matrix notes
- `requires_review`: Always True

### `AutoUpdateAction`
Decision record for safe-to-auto-apply vs. human-review packages.

- `safe_to_auto_update`: True only for low-risk patch bumps
- `requires_review`: Flipped from `safe_to_auto_update`
- `rollback_plan`: Human-readable rollback instructions
- `risk_assessment`: Narrative risk summary

### `BugReportResponse`
Auto-triage response to detected bug patterns.

- `bug_pattern_id`: Pattern ID from `BugPatternDetector`
- `severity`: Inherited from pattern classification
- `known_fix_available`: Bool
- `suggested_patch`: Optional fix description
- `eta_estimate`: Human-readable effort estimate
- `requires_review`: Always True

### `OperationalAnalysis`
System operation analysis from improvement proposals and open gaps.

- `analysis_type`: `resource_utilization`, `performance_bottleneck`, `capacity_forecast`, `cost_anomaly`
- `metric_name`, `current_value`, `threshold_value`, `trend`
- `forecast_summary`: Narrative summary
- `requires_review`: False for low-risk informational signals

---

## Recommendation Fields

Every `Recommendation` object contains:

| Field | Type | Description |
|-------|------|-------------|
| `recommendation_id` | `str` | Unique ID (e.g. `rec-abc123def456`) |
| `subsystem` | `str` | Source subsystem name |
| `recommendation_type` | `RecommendationType` | Enum value |
| `priority` | `str` | `critical` / `high` / `medium` / `low` |
| `confidence_score` | `float` | 0.0–1.0 |
| `description` | `str` | Human-readable description |
| `suggested_action` | `str` | Concrete action to take |
| `estimated_effort` | `str` | `< 1h`, `1–4h`, `1–3d`, etc. |
| `risk_level` | `str` | `low` / `medium` / `high` |
| `auto_applicable` | `bool` | Safe to auto-apply without review |
| `requires_review` | `bool` | Must be reviewed before action |
| `related_proposals` | `List[str]` | Linked signal/proposal IDs |
| `created_at` | `str` | ISO 8601 UTC timestamp |
| `status` | `str` | `active` / `acknowledged` / `dismissed` |
| `dismissed_reason` | `str?` | Reason if dismissed |

**Safety invariant:** If `requires_review=True`, `auto_applicable` is forced to `False` automatically.

---

## Recommendation Pipeline

```
Subsystem signals
       │
       ▼
  ┌─────────┐
  │ Collect │  ← gathers signals from all registered subsystems (graceful degradation)
  └────┬────┘
       │
       ▼
  ┌─────────┐
  │ Analyze │  ← cross-subsystem correlation (e.g. bug + CVE → higher priority)
  └────┬────┘
       │
       ▼
  ┌──────────────┐
  │  Prioritize  │  ← sort by severity, assign confidence scores
  └──────┬───────┘
         │
         ▼
  ┌────────┐
  │ Format │  ← translate signals into typed Recommendation objects
  └────┬───┘
       │
       ▼
  ┌─────────┐
  │ Persist │  ← save_state() → PersistenceManager
  └────┬────┘
       │
       ▼
  ┌─────────┐
  │ Publish │  ← EventBackbone SYSTEM_HEALTH event
  └─────────┘
```

### Cross-Subsystem Correlation

The `_analyze()` step detects when a bug report mentions the same package name that has an active CVE advisory. When correlated:

- The dependency finding's priority is boosted one level (e.g. `medium` → `high`)
- The `correlated_with` field is set to `"bug_detector"`
- The confidence score receives a +0.10 boost (capped at 1.0)

---

## API Reference

### Constructor

```python
SystemUpdateRecommendationEngine(
    persistence_manager=None,   # Optional PersistenceManager
    event_backbone=None,        # Optional EventBackbone
    improvement_engine=None,    # Optional SelfImprovementEngine
    bug_detector=None,          # Optional BugPatternDetector
    dependency_audit=None,      # Optional DependencyAuditEngine
    health_monitor=None,        # Optional HealthMonitor
    repair_system=None,         # Optional AutonomousRepairSystem
    orchestrator=None,          # Optional SelfAutomationOrchestrator
    max_recommendations=1000,   # Per-store recommendation cap
    max_history=200,            # Cycle history cap
)
```

### `run_recommendation_cycle(subsystems=None) → RecommendationCycleReport`

Runs the full collect → analyze → prioritize → format → persist → publish pipeline.

- `subsystems`: Optional list of subsystem names to restrict the cycle (e.g. `["bug_detector", "dependency_audit"]`). If `None`, all subsystems are queried.
- Returns a `RecommendationCycleReport` with all produced recommendations.

### `get_recommendations(subsystem=None, rec_type=None, priority=None) → List[Recommendation]`

Returns active (non-dismissed) recommendations, sorted by priority.

- `subsystem`: Filter by subsystem name string
- `rec_type`: Filter by `RecommendationType` enum value
- `priority`: Filter by priority string (`"critical"`, `"high"`, `"medium"`, `"low"`)

### `get_status() → Dict[str, Any]`

Returns an engine status summary including:

- `engine`, `design_label`
- `total_active_recommendations`
- `recommendations_by_priority`, `recommendations_by_type`
- `cycles_completed`
- `subsystems_registered` (custom collectors)
- `persistence_available`, `event_backbone_available`

### `get_history(limit=20) → List[Dict[str, Any]]`

Returns cycle summary dicts (most recent first), excluding full recommendation lists.

### `acknowledge_recommendation(recommendation_id) → bool`

Marks a recommendation as acknowledged. Returns `True` if found.

### `dismiss_recommendation(recommendation_id, reason) → bool`

Marks a recommendation as dismissed with a reason. Returns `True` if found.  
Dismissed recommendations are excluded from `get_recommendations()`.

### `save_state() → bool`

Persists current recommendations and history via `PersistenceManager.save_document()`.  
Called automatically at the end of each `run_recommendation_cycle()`.

### `load_state() → bool`

Restores recommendations and history from `PersistenceManager.load_document()`.

### `register_subsystem(name, collector) → None`

Registers a custom data collector for extensibility.

```python
def my_collector() -> List[Dict[str, Any]]:
    return [{"source": "my_system", "signal_type": "open_gap", ...}]

engine.register_subsystem("my_system", my_collector)
```

---

## Safety Invariants

1. **Read-only** — The engine never modifies source files on disk. All recommendations are proposals only.
2. **Requires-review enforcement** — `requires_review=True` automatically forces `auto_applicable=False` at dataclass construction time.
3. **Thread safety** — All shared state (`_recommendations`, `_history`, `_collectors`) is guarded by a single `threading.Lock`.
4. **Bounded storage** — `_recommendations` and `_history` are capped at `max_recommendations` and `max_history` respectively. Oldest/lowest-priority entries are evicted when limits are reached.
5. **Graceful degradation** — Any subsystem that raises an exception during collection is logged and skipped; the cycle continues with remaining subsystems.
6. **Audit trail** — Every cycle produces a `RecommendationCycleReport` persisted via `PersistenceManager` and a `SYSTEM_HEALTH` event via `EventBackbone`.

---

## Example Usage

```python
from src.system_update_recommendation_engine import (
    SystemUpdateRecommendationEngine,
    RecommendationType,
)
from src.persistence_manager import PersistenceManager
from src.event_backbone import EventBackbone
from src.self_improvement_engine import SelfImprovementEngine
from src.bug_pattern_detector import BugPatternDetector
from src.dependency_audit_engine import DependencyAuditEngine
from src.operational_completeness import HealthMonitor

# Wire up subsystems
pm = PersistenceManager()
backbone = EventBackbone()
sie = SelfImprovementEngine(persistence_manager=pm)
bpd = BugPatternDetector(persistence_manager=pm, event_backbone=backbone)
dae = DependencyAuditEngine(persistence_manager=pm, event_backbone=backbone)
hm = HealthMonitor()

# Create engine
engine = SystemUpdateRecommendationEngine(
    persistence_manager=pm,
    event_backbone=backbone,
    improvement_engine=sie,
    bug_detector=bpd,
    dependency_audit=dae,
    health_monitor=hm,
)

# Run a recommendation cycle
report = engine.run_recommendation_cycle()
print(f"Cycle {report.cycle_id}: {report.total_recommendations} recommendations")

# Query by type
sdk_updates = engine.get_recommendations(rec_type=RecommendationType.SDK_UPDATE)
for rec in sdk_updates:
    print(f"[{rec.priority}] {rec.description}")
    print(f"  Action: {rec.suggested_action}")
    print(f"  Confidence: {rec.confidence_score:.0%}")

# Acknowledge a recommendation after reviewing it
engine.acknowledge_recommendation(sdk_updates[0].recommendation_id)

# Dismiss an irrelevant recommendation
engine.dismiss_recommendation(sdk_updates[1].recommendation_id, "Already patched in staging")

# Register a custom subsystem
def my_custom_signals():
    return [{"source": "my_system", "signal_type": "open_gap",
             "id": "gap-1", "priority": "low", "description": "...", "area": "parser"}]

engine.register_subsystem("my_system", my_custom_signals)

# Get engine status
status = engine.get_status()
print(f"Active recommendations: {status['total_active_recommendations']}")
print(f"Cycles completed: {status['cycles_completed']}")
```

---

## File Structure

```
src/system_update_recommendation_engine.py     # Core engine (ARCH-008)
tests/test_system_update_recommendation_engine.py  # 51 tests
docs/SYSTEM_UPDATE_RECOMMENDATION_ENGINE.md    # This document
```

---

## Future PRs

This is **PR 1** of a planned multi-PR series:

| PR | Scope |
|----|-------|
| **PR 1 (this)** | Core engine, pipeline, dataclasses, tests, docs |
| PR 2 | API routes (`/api/update-recommendations/...`) |
| PR 3 | Matrix bridge module manifest entry |
| PR 4 | Dashboard UI for recommendation visualization |

# Murphy Code Healer — ARCH-006

**Design Label:** ARCH-006 — Autonomous Self-Coding Engine  
**Owner:** Backend Team  
**License:** BSL 1.1  
**Copyright:** © 2020 Inoni Limited Liability Company · Creator: Corey Post

---

## Overview

`MurphyCodeHealer` is an autonomous self-coding engine that extends the existing `SelfFixLoop` (ARCH-005). While `SelfFixLoop` handles runtime configuration changes (timeout tuning, confidence recalibration, recovery registration), `MurphyCodeHealer` performs **source-level analysis** and generates **structured code proposals** for human review.

**Safety guarantee:** `MurphyCodeHealer` never writes to source files directly. Every change is surfaced as a `CodeProposal` with a full audit trail and requires explicit human approval before application.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MURPHY CODE HEALER (ARCH-006)                        │
│                                                                         │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │ DiagnosticSuper- │    │  CodeIntelligence │    │ BayesianFix-     │  │
│  │ visor            │───▶│  (AST Analysis)   │───▶│ Planner          │  │
│  │ • BugDetector    │    │  • Parse/Map       │    │ • BeliefState    │  │
│  │ • StaticAnalysis │    │  • Fault Localize  │    │ • InfoGain       │  │
│  │ • TestGaps       │    │  • Call Graph       │    │ • FixPlan        │  │
│  │ • DocDrift       │    │  • Context Build    │    │ • MMSMMS         │  │
│  └─────────────────┘    └──────────────────┘    └───────────────────┘  │
│           │                                              │              │
│           ▼                                              ▼              │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │ Reconciliation   │    │  PatchGenerator   │    │ HealerChaos-     │  │
│  │ Controller       │◀──│  • Unified Diffs   │───▶│ Runner           │  │
│  │ • Desired State  │    │  • Governance      │    │ • Inject Failure │  │
│  │ • Observe/Compare│    │  • Auto-Tests      │    │ • Verify Patch   │  │
│  │ • Backoff        │    │  • Audit Trail     │    │ • Resilience     │  │
│  └─────────────────┘    └──────────────────┘    └───────────────────┘  │
│           │                                              │              │
│           ▼                                              ▼              │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │ HealerSupervisor │    │  Golden Path       │    │ EventBackbone    │  │
│  │ (Supervision)    │    │  Recorder          │    │ Integration      │  │
│  │ • one_for_one    │    │  • Pattern Store   │    │ • Full Audit     │  │
│  │ • one_for_all    │    │  • Replay Engine   │    │ • Observability  │  │
│  │ • Restart Budget │    │  • Cross-Gap       │    │ • Metrics        │  │
│  └─────────────────┘    └──────────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. DiagnosticSupervisor — Immune System Pattern

Aggregates gap signals from **all** Murphy subsystems:

| Detector | Source |
|---|---|
| `BugPatternDetector` | Recurring error patterns |
| `SelfImprovementEngine` | Remediation backlog |
| `SelfHealingCoordinator` | Recovery failure history |
| Static analysis scanner | Bare excepts, TODO markers, high-complexity functions |
| Test coverage gap detector | Public functions with no tests |
| Documentation drift detector | Docstring↔signature mismatches |

Each detector produces `CodeGap` objects. Related gaps (same file + function) are automatically grouped via `correlation_group`.

```python
supervisor = DiagnosticSupervisor(
    bug_detector=detector,
    improvement_engine=engine,
    healing_coordinator=coordinator,
    src_root="murphy_system/src",
    tests_root="murphy_system/tests",
)
gaps = supervisor.collect_gaps()
```

### 2. CodeIntelligence — AST-Aware Code Understanding

Parses Python source files to build a structural map:

- Function signatures and docstrings
- Class hierarchies
- Import graphs and call graphs
- Spectrum-based fault localisation (suspects ranked by score)

```python
ci = CodeIntelligence(src_root="murphy_system/src")
ci.build_map()
context = ci.get_context(gap)
suspects = ci.localise_fault(gap)
```

### 3. BayesianFixPlanner — Novel Murphy-Specific

Maintains a `BeliefState` over six fix hypotheses for each gap:

| Hypothesis | Description |
|---|---|
| `simple_config_fix` | Value or configuration is wrong |
| `missing_guard_clause` | Input validation missing |
| `incorrect_logic` | Core logic is wrong |
| `missing_feature` | Feature not yet implemented |
| `performance_issue` | Algorithmic bottleneck |
| `test_gap` | Test coverage missing |

Uses the **MMSMMS cadence** (Magnify→Magnify→Simplify→Magnify→Magnify→Solidify) for six-pass belief refinement before committing to a fix strategy.

```python
planner = BayesianFixPlanner()
plan = planner.create_plan(gap, context)
# plan.confidence_score  — Bayesian-derived confidence
# plan.hypothesis        — best hypothesis
# plan.patch_type        — add_guard | add_test | refactor | ...
```

### 4. PatchGenerator — Confidence-Gated Governance

Generates unified diffs and `CodeProposal` objects:

- All patches validated against `AuthorityBand.MEDIUM` governance constraints
- **Confidence-gated execution:**
  - `< 0.70` → logged only, no proposal
  - `0.70 – 0.90` → proposal created, no auto-merge suggestion
  - `> 0.90` → proposal created with auto-merge suggestion (still requires human approval)
- Auto-generates adversarial test alongside the fix test
- Full audit trail in `CodeProposal.audit_trail`

### 5. ReconciliationController — Desired-State Loop

Desired state: *zero known gaps, all tests passing, all docs current.*

- Compares observed state (from `DiagnosticSupervisor`) against desired state
- Exponential backoff for repeated failures: `delay = min(2ⁿ, 300s)`
- Leader-election guard: only one reconcile may run at a time (mutex)

### 6. HealerSupervisor — Worker Supervision

Supervision tree for healing workers:

| Strategy | Behaviour |
|---|---|
| `one_for_one` | Restart only the crashed worker |
| `one_for_all` | Restart all workers if a critical one crashes |

Each worker has a restart budget: max 5 restarts in 60 seconds.

### 7. HealerChaosRunner — Failure Injection &amp; Resilience Verification

Integrates with `SyntheticFailureGenerator`:
- Injects failure scenarios against the patched code
- Returns `ResilienceScore` (0.0–1.0)
- Generates adversarial tests that try to *break* the patch

### 8. GoldenPathRecorder

Records successful fix patterns for future replay:
- Groups patterns by `patch_type`
- Increments success count on reuse
- `find_for_gap(gap)` returns the most reused matching pattern

---

## Usage

### Basic usage

```python
from murphy_code_healer import MurphyCodeHealer

healer = MurphyCodeHealer(
    bug_detector=detector,
    improvement_engine=engine,
    healing_coordinator=coordinator,
    event_backbone=backbone,
    persistence_manager=pm,
    src_root="murphy_system/src",
    tests_root="murphy_system/tests",
)

report = healer.run_healing_cycle(max_gaps=50)
print(f"Detected: {report['gaps_detected']}, Proposed: {report['proposals_created']}")
```

### Integration with SelfFixLoop

```python
from self_fix_loop import SelfFixLoop
from murphy_code_healer import MurphyCodeHealer

loop = SelfFixLoop(improvement_engine=engine, ...)
healer = MurphyCodeHealer(src_root="murphy_system/src", ...)

# Bridge: SelfFixLoop delegates source-level gaps to MurphyCodeHealer
bridge = healer.bridge_to_code_healer()
proposal = bridge(gap)
```

### Single gap analysis

```python
from murphy_code_healer import CodeGap, MurphyCodeHealer

gap = CodeGap(
    gap_id="gap-001",
    description="Bare except in payment processor",
    source="static_analysis",
    severity="high",
    category="bare_except",
    file_path="src/payment.py",
    function_name="process_payment",
)

healer = MurphyCodeHealer()
proposal = healer.analyze_and_propose(gap)
if proposal:
    print(proposal.unified_diff)
    print(f"Auto-merge suggested: {proposal.auto_merge_suggested}")
```

---

## Data Models

### CodeGap

| Field | Type | Description |
|---|---|---|
| `gap_id` | str | Unique identifier |
| `description` | str | Human-readable description |
| `source` | str | `static_analysis` \| `test_coverage` \| `doc_drift` \| `bug_detector` \| `improvement_engine` \| `healing_coordinator` |
| `severity` | str | `critical` \| `high` \| `medium` \| `low` |
| `category` | str | `bare_except` \| `high_complexity` \| `test_gap` \| `doc_drift` \| `bug_pattern` \| `recovery_failure` \| `todo_marker` |
| `file_path` | str | Path to source file |
| `line_number` | int | Line number in source |
| `function_name` | str | Target function |
| `class_name` | str | Target class |
| `correlation_group` | str | Groups related gaps by root cause |

### CodeProposal

| Field | Type | Description |
|---|---|---|
| `proposal_id` | str | Unique identifier |
| `unified_diff` | str | Unified diff of the patch |
| `test_diff` | str | Unified diff of auto-generated test |
| `adversarial_test` | str | Test that tries to break the patch |
| `resilience_score` | float | Chaos-derived resilience (0–1) |
| `auto_merge_suggested` | bool | True if confidence > 0.90 |
| `audit_trail` | list | Full audit trail |
| `status` | str | `pending` \| `approved` \| `rejected` \| `applied` |

---

## Observability

Events published to `EventBackbone`:

| Event | Trigger |
|---|---|
| `CODE_HEALER_STARTED` | Healing cycle begins |
| `CODE_HEALER_COMPLETED` | Healing cycle ends |
| `CODE_HEALER_PROPOSAL_CREATED` | New proposal generated |
| `CODE_HEALER_GAP_LOW_CONFIDENCE` | Gap detected but confidence too low |

Metrics (via `healer.get_metrics()`):

- `gaps_detected`
- `patches_generated`
- `patches_rejected`
- `mean_time_to_detect_ms`
- `mean_time_to_patch_ms`

---

## Safety Invariants

1. **Never writes to source files** — all patches are proposals only
2. **Confidence-gated** — proposals below 0.70 confidence are logged only
3. **Governance-aligned** — operates at `AuthorityBand.MEDIUM`
4. **Thread-safe** — all shared state guarded by `threading.Lock`
5. **Bounded collections** — all lists capped via `capped_append`
6. **Single-run mutex** — only one healing cycle runs at a time

---

## Dependencies

Only Python stdlib is required:

```
ast, collections, difflib, inspect, json, logging, os, pathlib,
re, textwrap, threading, time, typing, uuid
```

Optional integration (graceful degradation if not provided):

- `BugPatternDetector` (DEV-004)
- `SelfImprovementEngine` (ARCH-001)
- `SelfHealingCoordinator` (OBS-004)
- `EventBackbone`
- `PersistenceManager`
- `SyntheticFailureGenerator`
- `GovernanceFramework`

---

## Running Tests

```bash
cd "murphy_system"
python -m pytest tests/test_murphy_code_healer.py -v --timeout=60
```

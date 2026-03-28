# Causality Sandbox Engine

**Design Label:** ARCH-010/011/012/013  
**License:** BSL 1.1  
**Status:** Production

---

## Overview and Philosophy

The **Causality Sandbox Engine** is Murphy's next-generation autonomous self-repair
system.  It surpasses all known self-healing platforms by combining Murphy's existing
strengths (SelfFixLoop, SelfImprovementEngine, SelfHealingCoordinator,
BugPatternDetector, SyntheticFailureGenerator, Bayesian engine, Kalman control theory,
GovernanceFramework) with novel capabilities inspired by AutoCodeRover, SWE-agent,
Kubernetes reconciliation loops, Erlang/OTP supervision trees, Netflix chaos
engineering, and biological immune systems.

### Core Innovation

The defining differentiator is a **causality sandbox**: before any fix is committed to
the real system, every possible remediation action is first executed in an isolated
simulation.  The system:

1. Generates **every possible action** for each detected gap.
2. Executes each candidate in an **isolated simulation sandbox**.
3. Scores each candidate by effectiveness, regression risk, side effects, and speed.
4. Selects and commits only the **highest-scoring action**.
5. Learns from every attempt to build an **immune memory** that grows faster over time.

No other platform explores all possible actions before committing.  AutoCodeRover tries
a few; SWE-agent uses agent reasoning; Murphy does an exhaustive, scored simulation.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Murphy System Runtime                        │
│                                                                  │
│  ┌─────────────┐   gaps    ┌────────────────────────────────┐   │
│  │ SelfFixLoop │──────────►│    CausalitySandboxEngine      │   │
│  │  .diagnose()│           │                                │   │
│  └─────────────┘           │  1. Antibody fast-path check   │   │
│                            │  2. enumerate_actions()        │   │
│  ┌─────────────┐  snapshot │  3. simulate_all() ──────────┐ │   │
│  │SystemSnapshot◄──────────┤                             │ │   │
│  └─────────────┘           │  ┌──────────────────────┐   │ │   │
│                            │  │  Isolated Sandboxes  │◄──┘ │   │
│  ┌─────────────┐ antibody  │  │  (fresh SelfFixLoop) │     │   │
│  │ImmuneMemory │◄──────────┤  └──────────────────────┘     │   │
│  │  .recognize │           │  4. rank_actions()             │   │
│  │  .memorize  │           │  5. commit_action()            │   │
│  └─────────────┘           │  6. learn_from_outcome()       │   │
│                            │  7. run_chaos_verification()   │   │
│  ┌─────────────┐  report   └────────────────────────────────┘   │
│  │SandboxReport│◄─────────────────────────────────────────────  │
│  └─────────────┘                                                 │
│                                                                  │
│  ┌─────────────────────┐   ┌──────────────────┐                 │
│  │  CodeRepairEngine   │   │  SupervisionTree  │                 │
│  │  .scan_file()       │   │  .handle_failure()│                 │
│  │  .generate_repairs()│   │  .get_status()    │                 │
│  └─────────────────────┘   └──────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## How It Works — Step-by-Step

### Step 1: Gap Detection

The existing `SelfFixLoop.diagnose()` method scans the system for bugs, performance
gaps, and health failures, returning a `List[Gap]`.

### Step 2: Antibody Fast-Path

`CausalitySandboxEngine.run_sandbox_cycle()` first checks the **ImmuneMemorySystem**.
If a previously seen gap pattern is recognised with confidence > 0.8, the proven fix
is applied immediately without simulation — sub-millisecond resolution.

### Step 3: Exhaustive Action Enumeration

`enumerate_actions(gap)` generates every possible remediation:

| Strategy | Example candidates |
|---|---|
| Keyword heuristic | `adjust_timeout`, `recalibrate_confidence` |
| Parametric sweep | +10ms, +20ms, +30ms, +50ms, +100ms timeout deltas |
| Recovery registration | `retry`, `fallback`, `circuit_breaker` handlers |
| Route optimisation | `llm`, `deterministic`, `hybrid` routing modes |
| Composite actions | timeout adjustment AND confidence recalibration |
| Do-nothing baseline | Always included for comparison |
| Antibody-suggested | Partial matches from immune memory |

### Step 4: Sandbox Simulation

Each candidate is evaluated in an isolated `SelfFixLoop` instance:

1. Create a fresh loop via `self_fix_loop_factory()`.
2. Restore the system snapshot (no real-system risk).
3. Execute the candidate as a `FixPlan`.
4. Run all test criteria.
5. Score:

```
effectiveness = (
    tests_passed_ratio   × 0.4
  + no_regressions_score × 0.3
  + health_improvement   × 0.2
  + minimal_side_effects × 0.1
)
```

### Step 5: Multi-Criteria Ranking

`rank_actions()` sorts by:
1. **Effectiveness score** (primary, higher is better)
2. **Fewer side effects** (secondary)
3. **Shorter simulation duration** (tertiary — prefer simpler fixes)
4. **Higher confidence delta** (quaternary)

### Step 6: Commit

`commit_action()` applies only the top-ranked action to the real system.
Actions scoring below `effectiveness_threshold` (default: 0.6) are not committed.

### Step 7: Learn

`learn_from_outcome()` updates the **ImmuneMemorySystem**:
- If the gap signature is known, effectiveness history is updated and confidence grows.
- If new, a fresh AntibodyPattern is created.
- Memory is pruned to ≤ 1000 entries (weakest confidence removed first).

### Step 8: Chaos Verification

`run_chaos_verification()` re-runs `diagnose()` post-commit to confirm the fix holds
and discover any regressions introduced.

---

## Immune Memory System

Inspired by biological immune systems, the `ImmuneMemorySystem` (`immune_memory.py`)
provides pattern-based long-term memory:

- **Antigen**: a normalised hash of gap characteristics (category + source + sorted tokens).
- **Antibody**: a proven fix action template with effectiveness history.
- **MemoryCell**: an activated antigen-antibody pair with potency and decay.

### Similarity Matching

Recognition uses a weighted combination:

```
similarity = signature_match × 0.4
           + jaccard_token_similarity × 0.4
           + category_match × 0.2
```

### Decay

Unused cells lose potency at `decay_rate` per `decay_interval_hours`.  Cells falling
below 0.1 potency are removed.  This ensures stale patterns do not pollute decisions.

---

## Code Repair Engine

`CodeRepairEngine` (`code_repair_engine.py`) provides AST-based static analysis and
human-reviewable patch proposals:

| Detector | What it finds |
|---|---|
| `MissingHandlerStrategy` | `except` blocks that only `pass` |
| `MissingDocstringStrategy` | Public functions/classes without docstrings |
| `UnusedImportStrategy` | Imports not referenced in module body |
| `BroadExceptionStrategy` | Bare `except Exception` that could be narrowed |
| `MissingTypeHintStrategy` | Function parameters or return values without annotations |

**Safety guarantee**: All patches are proposals only.  Every `CodePatch` has
`requires_human_review=True`.  No file is modified automatically.

---

## Supervision Tree

`SupervisionTree` (`supervision_tree.py`) implements Erlang/OTP-style hierarchical
supervision for Murphy's bot ecosystem:

| Strategy | Behaviour |
|---|---|
| `ONE_FOR_ONE` | Restart only the failed child |
| `ONE_FOR_ALL` | Restart all children when one fails |
| `REST_FOR_ONE` | Restart the failed child and all children started after it |

Each `ChildSpec` carries `max_restarts` and `max_restart_window_sec` to prevent
restart storms.  Exceeded budgets are escalated to the parent supervisor.

---

## Integration with Existing Murphy Components

| Component | Integration point |
|---|---|
| `SelfFixLoop` | Snapshot capture/restore; execute/test inside sandbox |
| `SyntheticFailureGenerator` | Chaos verification post-commit |
| `GovernanceFramework` | Authority bands respected for all sandbox operations |
| `EventBackbone` | Publishes `SANDBOX_CYCLE_STARTED`, `SANDBOX_ACTION_COMMITTED` |
| `BotInventoryLibrary` | `SupervisionTree` manages bot lifecycle |
| `control_theory/` | Bayesian confidence updates inform effectiveness scoring |

---

## Safety Guarantees

1. **Sandboxed simulation** — no real-system state is mutated during evaluation.
2. **Threshold gating** — actions scoring below `effectiveness_threshold` are not committed.
3. **Bounded memory** — max 1000 antibody entries; oldest/weakest pruned automatically.
4. **Bounded restarts** — `ChildSpec.max_restarts` prevents restart storms.
5. **Human-review required** — all `CodePatch` objects require human approval.
6. **Thread-safe** — every shared data structure is protected by a `threading.Lock`.
7. **Audit trail** — every ranking, simulation result, and antibody update is logged.

---

## API Reference

### `CausalitySandboxEngine`

```python
engine = CausalitySandboxEngine(
    self_fix_loop_factory=lambda: SelfFixLoop(...),
    max_parallel_simulations=10,
    effectiveness_threshold=0.6,
)
report: SandboxReport = engine.run_sandbox_cycle(gaps, real_loop)
```

#### Key methods

| Method | Description |
|---|---|
| `run_sandbox_cycle(gaps, real_loop)` | Main entry-point; returns `SandboxReport` |
| `enumerate_actions(gap)` | Generate all candidate actions |
| `simulate_action(action, snapshot)` | Run one action in isolation |
| `rank_actions(gap_id, results)` | Multi-criteria ranking |
| `commit_action(ranking, real_loop)` | Apply the best action |
| `learn_from_outcome(action, result, gap)` | Update immune memory |
| `run_chaos_verification(real_loop)` | Post-commit stress check |

### `ImmuneMemorySystem`

```python
memory = ImmuneMemorySystem(similarity_threshold=0.7, max_memory_cells=500)
cell = memory.recognize(gap)
if cell:
    action = memory.activate(cell, gap)
memory.memorize(gap, action, effectiveness=0.9)
memory.decay()
stats = memory.get_statistics()
```

### `CodeRepairEngine`

```python
engine = CodeRepairEngine()
issues = engine.scan_file("src/my_module.py")
patches = engine.generate_repairs(issues)
valid = engine.validate_patch(patches[0])
```

### `SupervisionTree`

```python
tree = SupervisionTree()
tree.register_supervisor(SupervisorNode(
    supervisor_id="root",
    strategy=SupervisionStrategy.ONE_FOR_ONE,
    children=[ChildSpec("worker", start_fn, max_restarts=3)],
))
result = tree.handle_failure("worker", RuntimeError("crash"))
status = tree.get_tree_status()
```

---

## Configuration Options

| Parameter | Default | Description |
|---|---|---|
| `max_parallel_simulations` | 10 | Maximum concurrent sandbox simulations |
| `effectiveness_threshold` | 0.6 | Minimum score to commit an action |
| `similarity_threshold` | 0.7 | Minimum similarity to match an immune memory cell |
| `max_memory_cells` | 500 | Maximum immune memory cells |
| `decay_interval_hours` | 24 | Hours between potency decay cycles |
| `max_restarts` (ChildSpec) | 3 | Maximum restarts within the time window |
| `max_restart_window_sec` | 60 | Window for counting restarts |

---

## Competitive Comparison

| Capability | AutoCodeRover | SWE-agent | Murphy Causality Sandbox |
|---|---|---|---|
| Exhaustive action enumeration | ❌ | ❌ | ✅ |
| Isolated simulation sandbox | ❌ | ❌ | ✅ |
| Immune memory learning | ❌ | ❌ | ✅ |
| Formal control theory scoring | ❌ | ❌ | ✅ |
| Chaos verification post-commit | ❌ | ❌ | ✅ |
| Governance-bounded autonomy | ❌ | ❌ | ✅ |
| Erlang-style supervision tree | ❌ | ❌ | ✅ |
| AST-aware code repair | ✅ | ✅ | ✅ |
| Full audit trail | Partial | Partial | ✅ |
| Composite action search | ❌ | ❌ | ✅ |
| Parametric sweep optimisation | ❌ | ❌ | ✅ |

---

## Example Execution Trace

```
[INFO] CausalitySandboxEngine: starting cycle for 3 gaps
[DEBUG] enumerate_actions: gap=gap-001 generated 12 candidates
[DEBUG] simulate_all: completed 5/12
[DEBUG] simulate_all: completed 10/12
[DEBUG] simulate_all: completed 12/12
[DEBUG] rank_actions: selected action timeout_gap-001_50_abc123 (score=0.800)
[INFO] commit_action: applying action timeout_gap-001_50_abc123 (score=0.800)
[DEBUG] learn_from_outcome: signature=3a7f... confidence=0.800
[INFO] run_chaos_verification: discovered 0 new gap(s) post-commit
[INFO] SandboxReport: gaps=3 actions=36 simulations=36 hits=1 duration=142ms
```

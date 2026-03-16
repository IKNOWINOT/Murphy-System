# Phase Controller

The Phase Controller (`src/control_plane/phase_controller.py`) enforces the Murphy System's
phase-based lifecycle. It decides when the system may advance from one phase to the next
based on confidence thresholds, and guarantees that phases are never skipped or reversed.

---

## Phase Lifecycle

Murphy System operates through a 7-phase sequence:

| # | Phase | Purpose |
|---|-------|---------|
| 1 | **EXPAND** | Broaden the solution space; generate hypotheses |
| 2 | **TYPE** | Classify the problem domain and automation type |
| 3 | **ENUMERATE** | List candidate strategies and constraints |
| 4 | **CONSTRAIN** | Apply safety gates, risk profiles, and domain rules |
| 5 | **COLLAPSE** | Converge on a single execution plan |
| 6 | **BIND** | Wire the plan to concrete engines and resources |
| 7 | **EXECUTE** | Run the bound plan under production supervision |

---

## Transition Rules

The controller implements three strict invariants from the formal specification:

1. **Threshold rule** — If current confidence `c_t ≥ θ_p` (the phase's threshold),
   advance to the next phase: `p_{t+1} = p_t + 1`.
2. **No skipping** — The system must pass through every phase in order.
3. **No reversal** — Once a phase is completed, the system cannot return to it.

```python
# Pseudocode from PhaseController.check_phase_transition()
if confidence >= current_phase.confidence_threshold:
    new_phase = next_phase(current_phase)   # advance by exactly 1
    log_transition(current_phase, new_phase, confidence)
    return new_phase, True, "Advanced"
else:
    gap = threshold - confidence
    return current_phase, False, f"Confidence gap: {gap:.3f}"
```

---

## Confidence Thresholds

Each phase has a confidence threshold that must be met before advancing.
Domain-specific thresholds are managed by `PhaseThresholds` (in `src/learning_system.py`),
with a default of **0.7** when no domain override is configured.

Higher-risk operations use elevated thresholds:

| Context | Threshold |
|---------|-----------|
| Executive-level decisions | 0.90 |
| General operations | 0.85 |
| Budget-related operations | 0.80 |
| Default / fallback | 0.70 |

A minimum **dwell time** per phase is also enforced to prevent premature transitions
even when confidence spikes briefly.

---

## Phase Progress Reporting

`PhaseController.get_phase_progress()` returns a snapshot of the current position:

```python
{
    "current_phase": "CONSTRAIN",
    "phase_index": 3,
    "total_phases": 7,
    "progress_ratio": 0.571,
    "remaining_phases": 3,
    "next_phase": "COLLAPSE",
    "confidence_threshold": 0.70
}
```

---

## Transition History

Every transition is appended to `phase_history` with a timestamp, confidence value,
threshold, and reason string. This log is available for audit and debugging.

---

## See Also

- [Confidence Engine](CONFIDENCE_ENGINE.md)
- [Gate Compiler](GATE_COMPILER.md)
- [Architecture Overview](../architecture/ARCHITECTURE_OVERVIEW.md)

# Control Plane

The `control_plane` package provides the formal control-theoretic foundation for
the Murphy System. It introduces typed models for every layer of the MFGC loop
and closes the critical gaps identified in the structural audit (commit `c4772a8`).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Murphy System                           │
│                                                             │
│  ┌──────────┐    z_t    ┌──────────────────┐               │
│  │ Sensors  │──────────▶│ ObservationModel │               │
│  └──────────┘           │ (H function)     │               │
│                         └────────┬─────────┘               │
│                                  │ x̂_t                     │
│                         ┌────────▼─────────┐               │
│                         │   StateVector    │               │
│                         │   x_t  (typed)  │               │
│                         └────────┬─────────┘               │
│                                  │                          │
│                         ┌────────▼─────────┐               │
│                         │   ControlLaw     │               │
│                         │   u_t = K(x,x*)  │               │
│                         └────────┬─────────┘               │
│                                  │ u_t                      │
│                         ┌────────▼─────────┐               │
│                         │  ControlVector   │               │
│                         │  (actions)       │               │
│                         └──────────────────┘               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Constraints  g(x_t) ≤ 0  ·  Jurisdictions  ·  LLM  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Modules

### `state_vector.py` — Formal State Vector x_t

**`StateVector`** (Pydantic v2 model) enumerates all system state dimensions:

| Dimension | Range | Description |
|---|---|---|
| `confidence` | [0, 1] | System's confidence in its current output |
| `phase` | [0, 1] | Normalized current MFGC phase (0–7 mapped to [0,1]) |
| `authority` | [0, 1] | Granted authority level |
| `murphy_index` | [0, 1] | Murphy entropy index |
| `gate_count` | [0, ∞) | Number of active gates |
| `constraint_satisfaction` | [0, 1] | Ratio of satisfied constraints |
| `domain_depth` | [0, ∞) | Domain knowledge depth |
| `information_completeness` | [0, 1] | Information completeness ratio |
| `risk_exposure` | [0, 1] | Current risk exposure |
| `verification_coverage` | [0, 1] | Gate verification coverage |

Key methods:
- `to_vector() -> List[float]` — numerical representation for linear algebra
- `dimensionality() -> int` — total dimension count (base + extra)
- `diff(other) -> Dict[str, float]` — element-wise difference
- `to_dict() -> Dict` — backward-compatible dict export
- `with_update(**kwargs) -> StateVector` — immutable field update

Schema versioning is handled via the `version: int` field.

---

### `observation_model.py` — Observation Model z_t and H mapping

**`ObservationChannel`** (enum) — measurement sources:
- `USER_INPUT`, `LLM_RESPONSE_QUALITY`, `GATE_EVALUATION_RESULT`
- `CONSTRAINT_CHECK_RESULT`, `TELEMETRY_READING`, `HUMAN_FEEDBACK`
- `DOCUMENT_INGESTION`, `CROSS_DOMAIN_SIGNAL`

**`ObservationVector`** — typed snapshot z_t with one field per channel.

**`ObservationNoise`** — per-channel noise model (σ and 95 % confidence interval).

**`ObservationMapping.map_to_state(z_t, x_t) -> StateVector`** — the H function.
Uses a Kalman-style blending update:

```
x_{t+1}[dim] = x_t[dim] + (1/(1+σ)) · (z_t[channel] − x_t[dim])
```

**`information_gain(question, state) -> float`** — estimates expected uncertainty
reduction from asking a question, given the current state.

---

### `control_loop.py` — Control Vector u_t and Feedback Law

**`ControlVector`** — boolean + continuous control actions:

| Action | Type | Meaning |
|---|---|---|
| `ask_question` | bool | Request more information |
| `generate_candidates` | bool | Generate solution candidates |
| `evaluate_gate` | bool | Evaluate a gate |
| `advance_phase` | bool | Advance to next MFGC phase |
| `request_human_intervention` | bool | Escalate to human |
| `execute_action` | bool | Execute the chosen action |
| `question_weight` | float | Magnitude for question ask |
| `action_intensity` | float | Magnitude for action execution |

**`ControlLaw.compute_control(x_t, x_target) -> ControlVector`** — proportional
feedback law `u_t = K · (x_target − x_t)`.  Actions are enabled when the
corresponding error exceeds a configurable threshold.

**`StabilityMonitor`** — tracks the confidence trajectory and raises
`StabilityViolation` when confidence oscillates more than `max_reversals` times
without sufficient net improvement.

**`ControlAuthorityMatrix`** — role-based action gating.  Maps
`(actor_id, action) -> bool` based on authority levels (0–3) with explicit
grant/revoke overrides.

---

### `formal_constraints.py` — Constraint Formalization g(x_t) ≤ 0

**`FormalConstraint`** (abstract) — `evaluate(state) -> float`:
- ≤ 0 → satisfied
- > 0 → violated

Built-in concrete constraints:
- `MinimumConfidenceConstraint(threshold)` — `threshold − confidence ≤ 0`
- `MaximumRiskConstraint(threshold)` — `risk_exposure − threshold ≤ 0`
- `LambdaConstraint(name, g)` — arbitrary callable `g(state) -> float`

**`JurisdictionRegistry`** — maps jurisdiction codes (e.g. `"EU"`, `"US"`) to
sets of constraints.  Supports `evaluate_all()` and `all_satisfied()`.

**`ProbabilisticConstraintChecker.probability_satisfied(c, state, σ) -> float`** —
Monte-Carlo estimate of P(g(x_t) ≤ 0) given Gaussian state uncertainty.

---

### `llm_output_schemas.py` — LLM Output Validation

Pydantic models for each LLM call type:

| Model | Call type |
|---|---|
| `ExpertGenerationOutput` | Expert profile generation |
| `GateProposalOutput` | Gate proposal |
| `CandidateGenerationOutput` | Candidate solution generation |
| `DomainAnalysisOutput` | Domain complexity analysis |

**`LLMOutputValidator.validate(raw, schema) -> (bool, model, errors)`** —
validates a raw dict against the expected schema.

**`ConflictResolver.resolve(outputs) -> Dict`** — merges contradictory LLM
outputs (average floats, majority-vote bools, union lists).

**`RegenerationTrigger.should_regenerate(output, is_valid, call_id) -> bool`** —
triggers re-query when validation fails or confidence is below threshold,
respecting a maximum retry count.

---

## Integration with `mfgc_core.py`

The control plane modules are **additive** — no existing code is broken.

Typical integration pattern:

```python
from control_plane import (
    StateVector, ObservationVector, ObservationMapping,
    ControlLaw, StabilityMonitor,
)

# Build typed state from MFGCSystemState
sv = StateVector(
    confidence=mfgc_state.confidence,
    authority=mfgc_state.authority,
    murphy_index=mfgc_state.murphy_index,
)

# Apply observations
obs = ObservationVector(llm_response_quality=llm_quality_score)
mapping = ObservationMapping()
sv = mapping.map_to_state(obs, sv)

# Compute control
law = ControlLaw(gain=1.0, threshold=0.1)
target = StateVector(confidence=1.0, information_completeness=1.0)
u_t = law.compute_control(sv, target)

if u_t.ask_question:
    # ... ask a clarifying question
    pass
```

---

## Testing

```bash
python -m pytest "murphy_system/tests/test_control_plane.py" -v
```

All tests are located in `murphy_system/tests/test_control_plane.py`.

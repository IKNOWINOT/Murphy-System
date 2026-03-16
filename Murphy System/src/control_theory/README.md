# Control Theory

The `control_theory` package implements the formal control-theoretic
foundations underpinning Murphy's MFGC (Measure-Filter-Gate-Control) loop.
It provides canonical state models, Bayesian filtering, drift detection,
and Lyapunov stability analysis.

## Key Modules

| Module | Purpose |
|--------|---------|
| `canonical_state.py` | `CanonicalState` — typed system state vector |
| `state_model.py` | State-space model (A, B, C matrices) |
| `state_transition.py` | Discrete-time state-transition functions |
| `observation_model.py` | Observation (measurement) model with noise parameters |
| `bayesian_engine.py` | Extended Kalman Filter and particle filter implementations |
| `drift_detector.py` | Detects statistical drift in observed state trajectories |
| `stability.py` | Lyapunov stability checks for closed-loop policies |
| `entropy.py` | Shannon entropy calculations over state distributions |
| `infinity_metric.py` | L∞-norm metrics for worst-case deviation bounds |
| `control_vector.py` | Typed control-input vector |
| `control_structure.py` | High-level control-structure (plant, controller, sensor wiring) |
| `scaling_mechanism.py` | Adaptive gain scaling for non-stationary environments |
| `actor_registry.py` | Registry of active control actors (agents, sensors, actuators) |
| `jurisdiction.py` | Policy boundaries that limit control authority per actor |
| `llm_validation.py` | Validates LLM-generated control policies for safety |
| `llm_synthesis_validator.py` | End-to-end validation of LLM-synthesised control loops |
| `state_adapter.py` | Adapts external state representations to canonical form |

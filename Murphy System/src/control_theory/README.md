# Control Theory

The `control_theory` package implements the formal control-theoretic
foundations underpinning Murphy's MFGC (Measure-Filter-Gate-Control) loop.
It provides canonical state models, Bayesian filtering, drift detection,
Lyapunov stability analysis, and modular manifold constraints.

## Key Modules

| Module | Purpose |
|--------|---------|
| `canonical_state.py` | `CanonicalState` — typed system state vector |
| `state_model.py` | State-space model (A, B, C matrices) |
| `state_transition.py` | Discrete-time state-transition functions |
| `observation_model.py` | Observation (measurement) model with noise parameters |
| `bayesian_engine.py` | Extended Kalman Filter and particle filter implementations |
| `drift_detector.py` | Detects statistical drift in observed state trajectories (+ manifold drift) |
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
| `manifold_projection.py` | Manifold types (Sphere, Stiefel, Oblique, Simplex) and state constrainer |
| `confidence_manifold.py` | Geodesic-distance phase transition routing on confidence manifold |

## Modular Manifolds Subsystem

Inspired by the "Modular Manifolds" approach, this subsystem shifts from
reactive normalization to proactive manifold constraints that keep state
vectors, weight matrices, and outputs well-conditioned *by construction*.

### Manifold Types

| Manifold | Class | Surface |
|----------|-------|---------|
| Unit sphere S^{n-1}(r) | `SphereManifold` | ‖x‖ = r |
| Stiefel St(n, k) | `StiefelManifold` | W^T W = I_k (orthonormal frames) |
| Oblique OB(n, k) | `ObliqueManifold` | Each column on S^{n-1} |
| Simplex Δ^{n-1} | `SimplexManifold` | x_i ≥ 0, Σx_i = 1 |

### Feature Flags

Each manifold module is gated behind an environment variable (default: disabled):

| Flag | Module |
|------|--------|
| `MURPHY_MANIFOLD_STATE=1` | ManifoldStateConstrainer (MFGC state projection) |
| `MURPHY_MANIFOLD_DRIFT=1` | ManifoldDriftDetector (manifold-aware drift) |
| `MURPHY_MANIFOLD_ROUTING=1` | ConfidenceManifoldRouter (geodesic phase transitions) |
| `MURPHY_MANIFOLD_SWARM=1` | SwarmWeightManifold (orthogonal swarm weights) |
| `MURPHY_MANIFOLD_LLM=1` | LLMOutputNormalizer (LLM output conditioning) |
| `MURPHY_MANIFOLD_TRAINING=1` | StiefelOptimizer (Riemannian SGD) |

### Error Codes

| Code | Description |
|------|-------------|
| `MANIFOLD-PROJ-ERR-001` | `distance_to_manifold` computation failed |
| `MANIFOLD-PROJ-ERR-002` | QR retraction failed |
| `MANIFOLD-PROJ-ERR-003` | Cayley retraction failed (falls back to QR) |
| `MANIFOLD-PROJ-ERR-004` | State projection failed (identity fallback) |
| `MANIFOLD-PROJ-ERR-005` | Manifold membership check failed |
| `MANIFOLD-ROUTE-ERR-001` | Geodesic transition evaluation failed |
| `MANIFOLD-ROUTE-ERR-002` | Distance computation failed |
| `SWARM-MANIFOLD-ERR-001` | Weight matrix computation failed (identity fallback) |
| `SWARM-MANIFOLD-ERR-002` | Orthogonal weighting failed (passthrough) |
| `SWARM-MANIFOLD-ERR-003` | Text decorrelation failed (passthrough) |
| `LLM-MANIFOLD-ERR-001` | Text normalization failed |
| `LLM-MANIFOLD-ERR-002` | Embedding normalization failed |
| `LLM-MANIFOLD-ERR-003` | Batch normalization / output comparison failed |
| `DRIFT-MANIFOLD-ERR-001` | Manifold drift check failed |
| `TRAIN-MANIFOLD-ERR-001` | Stiefel SGD step failed (returns original W) |

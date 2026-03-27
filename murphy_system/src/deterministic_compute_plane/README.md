# Deterministic Compute Plane

The `deterministic_compute_plane` package wraps the core symbolic
computation engine and guarantees reproducible, side-effect-free results
for a given input regardless of execution order or concurrency.

## Key Module

| Module | Purpose |
|--------|---------|
| `compute_plane.py` | `DeterministicComputePlane` — pure-function execution sandbox |

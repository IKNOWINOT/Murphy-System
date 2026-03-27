# Recursive Stability Controller (RSC)

The `recursive_stability_controller` package ensures that recursive
autonomous processes remain stable using Lyapunov-based energy monitoring
and active damping.

## Key Modules

| Module | Purpose |
|--------|---------|
| `lyapunov_monitor.py` | Computes Lyapunov energy function; triggers damping if energy grows |
| `recursion_energy.py` | Tracks cumulative energy across recursive call depth |
| `gate_damping.py` | Injects stabilisation gates to absorb excess recursion energy |
| `feedback_isolation.py` | Isolates feedback loops that exhibit runaway behaviour |
| `control_signals.py` | Typed signal types used by the controller |

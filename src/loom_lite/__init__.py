"""Loom-Lite — live runtime memory for Murphy turns.

Per Shape of Complete v3. Working memory that captures per-turn state and,
at turn-end, crystallizes into a portable DLF-Lite v2 package via the
precipitator.

Submodules:
  ghost_layer       — per-turn working-set snapshots
  psi_history       — operation log (cost/latency/outcome typing)
  recursion_gate    — spawn-depth tracker
  precipitator      — turn-end crystallization to DLF-Lite v2

All four are graceful-degraded: failures log a warning and the pipeline
continues. Removing this package = pipeline returns to pre-31cw behavior.
"""
from src.loom_lite.ghost_layer import snapshot as ghost_snapshot, list_for_turn
from src.loom_lite.psi_history import log_op as psi_log
from src.loom_lite.recursion_gate import enter as gate_enter, exit_ as gate_exit, depth as gate_depth
from src.loom_lite.precipitator import crystallize

__all__ = [
    "ghost_snapshot", "list_for_turn",
    "psi_log",
    "gate_enter", "gate_exit", "gate_depth",
    "crystallize",
]

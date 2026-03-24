"""
Deterministic Compute Plane

Dispatch layer that wires DeterministicRoutingEngine → ComputeService.
Routes tasks by type and executes deterministic (mathematical) workloads
through the verified compute service.
"""

from .compute_plane import DeterministicComputePlane

__all__ = ["DeterministicComputePlane"]

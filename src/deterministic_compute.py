"""
Bridge: src.deterministic_compute -> deterministic routing engine

DEPRECATED: Import directly from ``src.deterministic_routing_engine`` instead.
"""

import warnings

warnings.warn(
    "deterministic_compute is deprecated — import from src.deterministic_routing_engine instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.deterministic_routing_engine import DeterministicRoutingEngine as ComputePlane

__all__ = ['ComputePlane']

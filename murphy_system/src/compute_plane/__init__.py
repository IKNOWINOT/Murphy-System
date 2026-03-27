"""
Deterministic Compute Plane

A read-only verification oracle that executes mathematical workloads
and feeds results into the Confidence Engine, Gate Synthesis, and
Execution Packet Compiler.

This service defines mathematical reality for the MFGC-AI system.
LLMs may reason, but math must pass here before confidence increases.

Owner: INONI LLC / Corey Post
Contact: corey.gfc@gmail.com
"""

from .models.compute_request import ComputeRequest
from .models.compute_result import ComputeResult
from .service import ComputeService

__all__ = [
    'ComputeRequest',
    'ComputeResult',
    'ComputeService',
]

__version__ = '1.0.0'

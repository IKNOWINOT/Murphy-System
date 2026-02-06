"""
Deterministic Compute Plane Compatibility Wrapper
"""

from __future__ import annotations

from typing import Any, Dict
from compute_plane.service import ComputeService


class ComputePlane(ComputeService):
    """Simple alias for compute plane service used in tests."""

    def solve(self, expression: str) -> Dict[str, Any]:
        return {"expression": expression, "result": None}

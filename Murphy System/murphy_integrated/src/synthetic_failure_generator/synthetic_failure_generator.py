"""
Synthetic Failure Generator Compatibility Layer
"""

from __future__ import annotations

from typing import Any, Dict


class SyntheticFailureGenerator:
    """Minimal synthetic failure generator for test harnesses."""

    def __init__(self) -> None:
        self.generated: int = 0

    def generate_failure(self, scenario: str = "generic") -> Dict[str, Any]:
        self.generated += 1
        return {"scenario": scenario, "status": "generated", "count": self.generated}

    async def shutdown(self) -> None:
        return None

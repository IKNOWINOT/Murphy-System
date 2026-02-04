"""TelemetryBot for collecting runtime metrics."""
from __future__ import annotations
from typing import Dict, List

class TelemetryBot:
    def __init__(self) -> None:
        self.metrics: Dict[str, List[float]] = {}

    def log_metric(self, name: str, value: float) -> None:
        self.metrics.setdefault(name, []).append(value)

    def get_series(self, name: str) -> List[float]:
        return self.metrics.get(name, [])

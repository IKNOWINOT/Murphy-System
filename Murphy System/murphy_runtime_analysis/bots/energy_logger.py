"""Per-task energy and token usage logging."""
from __future__ import annotations

import time
from dataclasses import dataclass

@dataclass
class EnergyRecord:
    task_id: str
    tokens: int
    energy_kwh: float
    timestamp: float = time.time()

_records: list[EnergyRecord] = []

def log_energy(task_id: str, tokens: int, energy_kwh: float) -> None:
    _records.append(EnergyRecord(task_id, tokens, energy_kwh, time.time()))

def get_records() -> list[EnergyRecord]:
    return list(_records)

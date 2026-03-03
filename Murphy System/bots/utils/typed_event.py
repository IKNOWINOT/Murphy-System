"""Typed event definitions using Pydantic for validation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - optional dependency
    BaseModel = object  # type: ignore
    Field = lambda *a, **k: None  # type: ignore


class HiveEvent(BaseModel):
    event_id: str
    origin: str
    trust_score: float
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

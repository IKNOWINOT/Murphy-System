"""Fallback utilities for graceful degradation."""
from __future__ import annotations

from typing import Callable, Any

from .memory_manager_bot import MemoryManagerBot


class FallbackManager:
    """Dispatch tasks with cached fallbacks."""

    def __init__(self, memory: MemoryManagerBot) -> None:
        self.memory = memory

    def dispatch(self, task_id: int, primary: Callable[[], Any]) -> Any:
        try:
            return primary()
        except Exception:
            cached = None
            try:
                cached = self.memory.retrieve_ltm(task_id)
            except Exception:
                cached = None
            return {"status": "fallback_used", "data": cached}


def with_fallback(primary: Callable[[], Any], fallback: Callable[[], Any]) -> Any:
    try:
        return primary()
    except Exception:
        return fallback()

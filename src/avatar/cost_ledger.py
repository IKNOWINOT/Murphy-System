"""Tracks costs per avatar and service."""

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .avatar_models import CostEntry

logger = logging.getLogger(__name__)


class CostLedger:
    """Tracks costs per avatar and service."""

    def __init__(self) -> None:
        self._entries: List[CostEntry] = []
        self._lock = Lock()

    def record(
        self,
        avatar_id: str,
        service: str,
        operation: str,
        cost_usd: float,
        metadata: Optional[Dict] = None,
    ) -> CostEntry:
        """Record a cost entry."""
        entry = CostEntry(
            entry_id=str(uuid.uuid4()),
            avatar_id=avatar_id,
            service=service,
            operation=operation,
            cost_usd=cost_usd,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        with self._lock:
            capped_append(self._entries, entry)
        return entry

    def get_total_cost(
        self,
        avatar_id: Optional[str] = None,
        service: Optional[str] = None,
    ) -> float:
        """Get total cost, optionally filtered by avatar and/or service."""
        with self._lock:
            entries = list(self._entries)
        if avatar_id:
            entries = [e for e in entries if e.avatar_id == avatar_id]
        if service:
            entries = [e for e in entries if e.service == service]
        return sum(e.cost_usd for e in entries)

    def get_entries(
        self, avatar_id: Optional[str] = None, limit: int = 100
    ) -> List[CostEntry]:
        """Get cost entries, optionally filtered by avatar."""
        with self._lock:
            entries = list(self._entries)
        if avatar_id:
            entries = [e for e in entries if e.avatar_id == avatar_id]
        return entries[-limit:]

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get a summary of costs grouped by service."""
        with self._lock:
            entries = list(self._entries)
        by_service: Dict[str, float] = {}
        for e in entries:
            by_service[e.service] = by_service.get(e.service, 0.0) + e.cost_usd
        return {
            "total_cost_usd": sum(e.cost_usd for e in entries),
            "entry_count": len(entries),
            "by_service": by_service,
        }

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            total_cost = sum(e.cost_usd for e in self._entries)
        return {
            "total_entries": total,
            "total_cost_usd": round(total_cost, 4),
        }

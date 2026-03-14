"""
Observability Summary Counters for the Murphy System.
Surfaces summary counters that distinguish behavior fixes from
permutation-only coverage for closed-loop improvement observability.

Implements Section 14.1 item 4 of the production readiness assessment.

Owner: INONI LLC / Corey Post
Contact: corey.gfc@gmail.com
Repository: https://github.com/IKNOWINOT/Murphy-System
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

VALID_CATEGORIES = (
    "behavior_fix",
    "permutation_coverage",
    "integration_wiring",
    "security_hardening",
    "documentation",
)


@dataclass
class CounterEntry:
    """A single named counter with category classification."""
    name: str
    category: str
    value: int = 0
    last_updated: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ObservabilitySummaryCounters:
    """
    Tracks summary counters that distinguish behavior fixes from
    permutation-only coverage, enabling closed-loop improvement
    observability across the Murphy System.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, CounterEntry] = {}
        self._history: List[Dict[str, Any]] = []
        self._category_totals: Dict[str, int] = {c: 0 for c in VALID_CATEGORIES}

    # ==================== Registration ====================

    def register_counter(self, name: str, category: str) -> str:
        """Register a named counter under a category.

        Args:
            name: Human-readable counter name.
            category: One of the valid category strings.

        Returns:
            A unique counter_id.
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. Must be one of {VALID_CATEGORIES}"
            )
        counter_id = uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._counters[counter_id] = CounterEntry(
            name=name,
            category=category,
            value=0,
            last_updated=now,
            metadata={},
        )
        logger.info("Registered counter %s (%s) as %s", name, category, counter_id)
        return counter_id

    # ==================== Increment ====================

    def increment(self, counter_id: str, delta: int = 1, reason: str = "") -> dict:
        """Increment a counter by delta.

        Args:
            counter_id: ID returned by register_counter.
            delta: Amount to add.
            reason: Optional description of why the increment happened.

        Returns:
            Dict with updated counter state.
        """
        if counter_id not in self._counters:
            return {"status": "error", "message": f"Unknown counter_id '{counter_id}'"}

        entry = self._counters[counter_id]
        entry.value += delta
        now = datetime.now(timezone.utc).isoformat()
        entry.last_updated = now
        self._category_totals[entry.category] += delta

        history_record = {
            "event_id": uuid4().hex[:12],
            "counter_id": counter_id,
            "counter_name": entry.name,
            "category": entry.category,
            "delta": delta,
            "new_value": entry.value,
            "reason": reason,
            "timestamp": now,
        }
        capped_append(self._history, history_record)

        return {
            "status": "ok",
            "counter_id": counter_id,
            "name": entry.name,
            "category": entry.category,
            "value": entry.value,
            "last_updated": now,
        }

    # ==================== Convenience Recorders ====================

    def record_fix(self, module: str, fix_type: str, description: str) -> str:
        """Record a behavior fix, auto-creating a counter if needed.

        Args:
            module: Module where the fix was applied.
            fix_type: Short label for the fix type.
            description: Human-readable description.

        Returns:
            The counter_id used.
        """
        counter_name = f"{module}:behavior_fix:{fix_type}"
        counter_id = self._find_counter_by_name(counter_name)
        if counter_id is None:
            counter_id = self.register_counter(counter_name, "behavior_fix")
        self.increment(counter_id, delta=1, reason=description)
        return counter_id

    def record_coverage(self, module: str, test_count: int, description: str) -> str:
        """Record a permutation coverage addition.

        Args:
            module: Module receiving new coverage.
            test_count: Number of new test permutations.
            description: Human-readable description.

        Returns:
            The counter_id used.
        """
        counter_name = f"{module}:permutation_coverage"
        counter_id = self._find_counter_by_name(counter_name)
        if counter_id is None:
            counter_id = self.register_counter(counter_name, "permutation_coverage")
        self.increment(counter_id, delta=test_count, reason=description)
        return counter_id

    # ==================== Query Methods ====================

    def get_counter(self, counter_id: str) -> dict:
        """Return current state of a single counter."""
        if counter_id not in self._counters:
            return {"status": "error", "message": f"Unknown counter_id '{counter_id}'"}
        entry = self._counters[counter_id]
        return {
            "status": "ok",
            "counter_id": counter_id,
            "name": entry.name,
            "category": entry.category,
            "value": entry.value,
            "last_updated": entry.last_updated,
            "metadata": entry.metadata,
        }

    def get_category_summary(self) -> dict:
        """Return totals per category."""
        return {
            "status": "ok",
            "categories": dict(self._category_totals),
            "total": sum(self._category_totals.values()),
        }

    def get_behavior_vs_permutation_ratio(self) -> dict:
        """Return ratio of behavior_fix to permutation_coverage."""
        fixes = self._category_totals.get("behavior_fix", 0)
        coverage = self._category_totals.get("permutation_coverage", 0)
        if coverage == 0:
            ratio = float("inf") if fixes > 0 else 0.0
        else:
            ratio = fixes / coverage
        return {
            "status": "ok",
            "behavior_fix_total": fixes,
            "permutation_coverage_total": coverage,
            "ratio": ratio,
        }

    def get_module_summary(self) -> dict:
        """Return summary grouped by module name."""
        modules: Dict[str, Dict[str, Any]] = {}
        for cid, entry in self._counters.items():
            parts = entry.name.split(":")
            module_name = parts[0] if parts else entry.name
            if module_name not in modules:
                modules[module_name] = {"counters": 0, "total_value": 0, "categories": {}}
            modules[module_name]["counters"] += 1
            modules[module_name]["total_value"] += entry.value
            cat = entry.category
            modules[module_name]["categories"][cat] = (
                modules[module_name]["categories"].get(cat, 0) + entry.value
            )
        return {"status": "ok", "modules": modules}

    def get_improvement_velocity(self, window_hours: int = 24) -> dict:
        """Return improvement rate (fixes per hour) over a time window.

        Args:
            window_hours: Number of hours to look back.

        Returns:
            Dict with velocity metrics.
        """
        now = datetime.now(timezone.utc)
        events_in_window = 0
        fixes_in_window = 0
        for record in self._history:
            ts = datetime.fromisoformat(record["timestamp"])
            diff_hours = (now - ts).total_seconds() / 3600.0
            if diff_hours <= window_hours:
                events_in_window += 1
                if record["category"] == "behavior_fix":
                    fixes_in_window += record["delta"]

        velocity = fixes_in_window / window_hours if window_hours > 0 else 0.0
        return {
            "status": "ok",
            "window_hours": window_hours,
            "events_in_window": events_in_window,
            "fixes_in_window": fixes_in_window,
            "velocity_per_hour": velocity,
        }

    def get_history(
        self, category: Optional[str] = None, limit: int = 100
    ) -> list:
        """Return recent history entries, optionally filtered by category.

        Args:
            category: If provided, only return entries matching this category.
            limit: Maximum number of entries to return.

        Returns:
            List of history dicts, most recent first.
        """
        entries = self._history
        if category is not None:
            entries = [e for e in entries if e["category"] == category]
        return list(reversed(entries[-limit:]))

    # ==================== Status ====================

    def get_status(self) -> dict:
        """Return full observability status."""
        return {
            "status": "ok",
            "counters": {
                cid: {
                    "name": e.name,
                    "category": e.category,
                    "value": e.value,
                    "last_updated": e.last_updated,
                }
                for cid, e in self._counters.items()
            },
            "category_summary": self.get_category_summary(),
            "ratio": self.get_behavior_vs_permutation_ratio(),
            "total_events": len(self._history),
        }

    # ==================== Reset ====================

    def clear(self) -> None:
        """Reset all counters, history, and category totals."""
        self._counters.clear()
        self._history.clear()
        self._category_totals = {c: 0 for c in VALID_CATEGORIES}
        logger.info("ObservabilitySummaryCounters cleared")

    # ==================== Internal Helpers ====================

    def _find_counter_by_name(self, name: str) -> Optional[str]:
        """Return the counter_id for a counter with the given name, or None."""
        for cid, entry in self._counters.items():
            if entry.name == name:
                return cid
        return None

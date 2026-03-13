"""
Dashboards – Aggregation Engine
=================================

Cross-board data aggregation for dashboard widgets.
Consumes board data via a pluggable board accessor callback.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import statistics
from typing import Any, Callable, Dict, List, Optional

from .models import AggregationFunction, DataSource


class AggregationEngine:
    """Aggregates numeric data from boards for widget rendering.

    Parameters
    ----------
    board_accessor : callable, optional
        ``(board_id) -> dict`` that returns board data in the same shape
        as ``Board.to_dict()``.  If ``None``, aggregation returns empty results.
    """

    def __init__(
        self,
        board_accessor: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ) -> None:
        self._board_accessor = board_accessor

    def _get_board(self, board_id: str) -> Optional[Dict[str, Any]]:
        if self._board_accessor is None:
            return None
        return self._board_accessor(board_id)

    def _extract_values(self, data_source: DataSource) -> List[Any]:
        """Extract cell values matching a data source spec."""
        board = self._get_board(data_source.board_id)
        if board is None:
            return []

        values: List[Any] = []
        for group in board.get("groups", []):
            if data_source.group_id and group.get("id") != data_source.group_id:
                continue
            for item in group.get("items", []):
                # Apply filters
                if not self._matches_filters(item, data_source.filters):
                    continue
                cell = item.get("cells", {}).get(data_source.column_id)
                if cell is not None:
                    val = cell.get("value") if isinstance(cell, dict) else cell
                    if val is not None:
                        values.append(val)
        return values

    @staticmethod
    def _matches_filters(item: Dict[str, Any], filters: List[Dict[str, Any]]) -> bool:
        for filt in filters:
            col_id = filt.get("column_id", "")
            operator = filt.get("operator", "eq")
            target = filt.get("value")
            cell = item.get("cells", {}).get(col_id)
            actual = cell.get("value") if isinstance(cell, dict) else cell
            if operator == "eq" and actual != target:
                return False
            if operator == "neq" and actual == target:
                return False
        return True

    def aggregate(
        self,
        data_source: DataSource,
        function: AggregationFunction,
    ) -> Any:
        """Run an aggregation function over values from *data_source*."""
        values = self._extract_values(data_source)

        if function == AggregationFunction.COUNT:
            return len(values)

        # Numeric functions require float conversion
        nums: List[float] = []
        for v in values:
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                continue

        if not nums:
            return 0

        if function == AggregationFunction.SUM:
            return sum(nums)
        if function == AggregationFunction.AVG:
            return sum(nums) / (len(nums) or 1)
        if function == AggregationFunction.MIN:
            return min(nums)
        if function == AggregationFunction.MAX:
            return max(nums)
        if function == AggregationFunction.MEDIAN:
            return statistics.median(nums)
        return 0

    def count_by_column(self, data_source: DataSource) -> Dict[str, int]:
        """Group-count values in a column (for pie/bar charts)."""
        values = self._extract_values(data_source)
        counts: Dict[str, int] = {}
        for v in values:
            key = str(v)
            counts[key] = counts.get(key, 0) + 1
        return counts

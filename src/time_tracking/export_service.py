# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Export Service
====================================

Export time entries to CSV or Excel (openpyxl if available, CSV fallback).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from .models import TimeEntry

try:
    import openpyxl  # type: ignore
    _OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OPENPYXL_AVAILABLE = False

_CSV_HEADERS = [
    "Date", "User", "Project", "Item", "Description",
    "Start", "End", "Duration (hours)", "Billable", "Status",
]


def _duration_hours(seconds: int) -> str:
    """Format duration as decimal hours rounded to 4 places (e.g. '1.5')."""
    return f"{seconds / 3600:.4f}".rstrip("0").rstrip(".")


def _entry_to_row(entry: TimeEntry) -> List[str]:
    """Convert a TimeEntry to a CSV/Excel row."""
    date = entry.started_at[:10] if entry.started_at else ""
    duration_h = _duration_hours(entry.duration_seconds)
    return [
        date,
        entry.user_id,
        entry.board_id,
        entry.item_id,
        entry.note,
        entry.started_at,
        entry.ended_at,
        duration_h,
        "Yes" if entry.billable else "No",
        entry.status.value,
    ]


class ExportService:
    """Generates CSV and Excel exports from a list of TimeEntry objects."""

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def export_to_csv(
        self,
        entries: List[TimeEntry],
        filename: Optional[str] = None,  # accepted but unused in string mode
    ) -> str:
        """Return a CSV string for *entries*."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(_CSV_HEADERS)
        for entry in entries:
            writer.writerow(_entry_to_row(entry))
        return output.getvalue()

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------

    def export_to_excel(
        self,
        entries: List[TimeEntry],
        filename: Optional[str] = None,
    ) -> bytes:
        """Return Excel bytes for *entries*.

        Uses openpyxl when available; falls back to UTF-8 CSV bytes.
        """
        if _OPENPYXL_AVAILABLE:
            return self._export_xlsx(entries)
        return self._export_csv_bytes(entries)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _export_xlsx(self, entries: List[TimeEntry]) -> bytes:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Time Entries"
        ws.append(_CSV_HEADERS)
        for entry in entries:
            ws.append(_entry_to_row(entry))
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _export_csv_bytes(self, entries: List[TimeEntry]) -> bytes:
        return self.export_to_csv(entries).encode("utf-8")

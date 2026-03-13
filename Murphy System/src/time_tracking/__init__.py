"""
Time Tracking & Reporting
==========================

Phase 6 of management systems feature parity for the Murphy System.

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "TimeTracking"

from .models import EntryStatus, SheetStatus, TimeEntry, TimeSheet
from .tracker import TimeTracker

try:
    from .api import create_time_tracking_router
except Exception:  # pragma: no cover
    create_time_tracking_router = None  # type: ignore[assignment]

__all__ = [
    "EntryStatus",
    "SheetStatus",
    "TimeEntry",
    "TimeSheet",
    "TimeTracker",
    "create_time_tracking_router",
]

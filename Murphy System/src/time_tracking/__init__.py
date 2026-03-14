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
from .reporting_service import ReportingService
from .approval_service import ApprovalError, ApprovalService
from .export_service import ExportService

try:
    from .api import create_time_tracking_router
except Exception:  # pragma: no cover
    create_time_tracking_router = None  # type: ignore[assignment]

try:
    from .reporting_api import create_reporting_blueprint
except Exception:  # pragma: no cover
    create_reporting_blueprint = None  # type: ignore[assignment]

__all__ = [
    "EntryStatus",
    "SheetStatus",
    "TimeEntry",
    "TimeSheet",
    "TimeTracker",
    "ReportingService",
    "ApprovalError",
    "ApprovalService",
    "ExportService",
    "create_time_tracking_router",
    "create_reporting_blueprint",
]

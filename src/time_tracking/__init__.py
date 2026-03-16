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
from .dashboard_widgets import TimeTrackingWidgetFactory
from .summary_statistics import SummaryStatisticsService
from .team_views import TeamViewService

try:
    from .api import create_time_tracking_router
except Exception as exc:  # pragma: no cover
    create_time_tracking_router = None  # type: ignore[assignment]

try:
    from .reporting_api import create_reporting_blueprint
except Exception as exc:  # pragma: no cover
    create_reporting_blueprint = None  # type: ignore[assignment]

from .billing_integration import BillingIntegrationService
from .invoicing_hooks import InvoicingHookManager, TimeTrackingEvent
from .config import TimeTrackingConfig

try:
    from .settings_api import create_settings_blueprint
except Exception as exc:  # pragma: no cover
    create_settings_blueprint = None  # type: ignore[assignment]
try:
    from .dashboard_api import create_dashboard_blueprint
except Exception as exc:  # pragma: no cover
    create_dashboard_blueprint = None  # type: ignore[assignment]

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
    "TimeTrackingWidgetFactory",
    "SummaryStatisticsService",
    "TeamViewService",
    "create_time_tracking_router",
    "create_reporting_blueprint",
    "BillingIntegrationService",
    "InvoicingHookManager",
    "TimeTrackingEvent",
    "TimeTrackingConfig",
    "create_settings_blueprint",
    "create_dashboard_blueprint",
]

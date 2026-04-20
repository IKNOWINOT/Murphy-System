# `src/time_tracking` — Time Tracking & Reporting

Full-featured time tracking with timesheets, approval workflows, reporting, billing integration, and dashboard widgets.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The time tracking package is Monday.com time-tracking feature parity for Murphy workspaces. Team members log `TimeEntry` objects against board items; entries are grouped into `TimeSheet` periods and submitted for manager approval via `ApprovalService`. `ReportingService` and `SummaryStatisticsService` generate utilisation and billable-hour reports across individuals and teams. `BillingIntegrationService` converts approved timesheets into invoice line items, and `InvoicingHookManager` fires webhooks when billing milestones are hit. Dashboard widgets are available for embedding time data into Murphy boards.

## Key Components

| Module | Purpose |
|--------|---------|
| `tracker.py` | `TimeTracker` — entry start/stop, pause, and manual entry |
| `models.py` | `TimeEntry`, `TimeSheet`, `EntryStatus`, `SheetStatus` |
| `approval_service.py` | `ApprovalService` — timesheet approval workflow |
| `reporting_service.py` | `ReportingService` — utilisation and billable-hour reports |
| `summary_statistics.py` | `SummaryStatisticsService` — aggregate team and project statistics |
| `team_views.py` | `TeamViewService` — team-level time visibility |
| `export_service.py` | `ExportService` — CSV/Excel export of timesheet data |
| `billing_integration.py` | `BillingIntegrationService` — converts timesheets to invoice line items |
| `invoicing_hooks.py` | `InvoicingHookManager`, `TimeTrackingEvent` — billing webhook dispatch |
| `dashboard_widgets.py` | `TimeTrackingWidgetFactory` — embeddable time-data widgets |
| `event_backbone_bridge.py` | Bridges time-tracking events to the Murphy event backbone |
| `config.py` | `TimeTrackingConfig` — workspace-level configuration |
| `api.py` | FastAPI router for time entry and timesheet REST endpoints |
| `reporting_api.py` | Flask blueprint for report generation endpoints |
| `settings_api.py` | Flask blueprint for workspace settings |
| `dashboard_api.py` | Flask blueprint for dashboard data endpoints |

## Usage

```python
from time_tracking import TimeTracker, TimeSheet

tracker = TimeTracker()
entry = tracker.start(user_id="u1", item_id="item-42", description="Backend work")
tracker.stop(entry.id)

sheet = tracker.get_timesheet(user_id="u1", week="2025-W03")
print(sheet.total_hours)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

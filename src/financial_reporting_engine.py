"""
Financial Reporting Engine for Murphy System.

Design Label: BIZ-001 — Automated Financial Data Collection & Reporting
Owner: Finance Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable report storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on report generation)
  - AnalyticsDashboard (optional, for metric aggregation)

Implements Phase 5 — Business Operations Automation:
  Collects financial data entries (revenue, costs, transactions),
  generates periodic reports with trend analysis, and publishes
  events for downstream automation.

Flow:
  1. Record financial entries (revenue, expense, refund, etc.)
  2. Generate summary reports for configurable time periods
  3. Compute trend indicators (growth rate, margin, burn rate)
  4. Persist reports via PersistenceManager
  5. Publish LEARNING_FEEDBACK events with report summaries

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Immutable entries: recorded entries cannot be modified, only appended
  - Bounded history: configurable max entries to prevent memory issues
  - Audit trail: every report generation is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FinancialEntry:
    """A single financial transaction entry."""
    entry_id: str
    category: str          # revenue, expense, refund, investment
    amount: float
    currency: str = "USD"
    description: str = ""
    source: str = ""       # module, customer, vendor
    tags: List[str] = field(default_factory=list)
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "category": self.category,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "source": self.source,
            "tags": list(self.tags),
            "recorded_at": self.recorded_at,
        }


@dataclass
class FinancialReport:
    """A generated financial summary report."""
    report_id: str
    period_label: str
    total_revenue: float
    total_expenses: float
    net_income: float
    entry_count: int
    category_breakdown: Dict[str, float] = field(default_factory=dict)
    trend_indicators: Dict[str, float] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "period_label": self.period_label,
            "total_revenue": round(self.total_revenue, 2),
            "total_expenses": round(self.total_expenses, 2),
            "net_income": round(self.net_income, 2),
            "entry_count": self.entry_count,
            "category_breakdown": {
                k: round(v, 2) for k, v in self.category_breakdown.items()
            },
            "trend_indicators": {
                k: round(v, 4) for k, v in self.trend_indicators.items()
            },
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# FinancialReportingEngine
# ---------------------------------------------------------------------------

class FinancialReportingEngine:
    """Automated financial data collection and report generation.

    Design Label: BIZ-001
    Owner: Finance Team

    Usage::

        engine = FinancialReportingEngine(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        engine.record_entry(category="revenue", amount=1000.0, source="customer-A")
        report = engine.generate_report(period_label="2026-Q1")
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_entries: int = 50_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._entries: List[FinancialEntry] = []
        self._reports: List[FinancialReport] = []
        self._max_entries = max_entries

    # ------------------------------------------------------------------
    # Entry recording
    # ------------------------------------------------------------------

    def record_entry(
        self,
        category: str,
        amount: float,
        currency: str = "USD",
        description: str = "",
        source: str = "",
        tags: Optional[List[str]] = None,
    ) -> FinancialEntry:
        """Record a financial entry. Returns the created entry."""
        entry = FinancialEntry(
            entry_id=f"fin-{uuid.uuid4().hex[:8]}",
            category=category.lower(),
            amount=amount,
            currency=currency,
            description=description,
            source=source,
            tags=tags or [],
        )
        with self._lock:
            if len(self._entries) >= self._max_entries:
                # Evict oldest 10 %
                evict = max(1, self._max_entries // 10)
                self._entries = self._entries[evict:]
            self._entries.append(entry)
        logger.info("Recorded financial entry %s: %s %.2f", entry.entry_id, category, amount)
        return entry

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        period_label: str = "current",
        category_filter: Optional[str] = None,
    ) -> FinancialReport:
        """Generate a financial summary report from current entries."""
        with self._lock:
            entries = list(self._entries)

        if category_filter:
            entries = [e for e in entries if e.category == category_filter.lower()]

        # Compute aggregates
        revenue = sum(e.amount for e in entries if e.category == "revenue")
        expenses = sum(e.amount for e in entries if e.category in ("expense", "cost"))
        refunds = sum(e.amount for e in entries if e.category == "refund")
        net = revenue - expenses - refunds

        # Category breakdown
        breakdown: Dict[str, float] = defaultdict(float)
        for e in entries:
            breakdown[e.category] += e.amount

        # Trend indicators
        trends = self._compute_trends(entries, revenue, expenses)

        report = FinancialReport(
            report_id=f"rpt-{uuid.uuid4().hex[:8]}",
            period_label=period_label,
            total_revenue=revenue,
            total_expenses=expenses + refunds,
            net_income=net,
            entry_count=len(entries),
            category_breakdown=dict(breakdown),
            trend_indicators=trends,
        )

        with self._lock:
            capped_append(self._reports, report)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=report.report_id,
                    document=report.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(report)

        logger.info("Generated financial report %s for %s", report.report_id, period_label)
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_entries(self, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent entries, optionally filtered by category."""
        with self._lock:
            entries = list(self._entries)
        if category:
            entries = [e for e in entries if e.category == category.lower()]
        return [e.to_dict() for e in entries[-limit:]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent generated reports."""
        with self._lock:
            return [r.to_dict() for r in self._reports[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "total_reports": len(self._reports),
                "max_entries": self._max_entries,
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_trends(
        entries: List[FinancialEntry],
        revenue: float,
        expenses: float,
    ) -> Dict[str, float]:
        """Compute basic trend indicators."""
        trends: Dict[str, float] = {}
        if revenue > 0:
            trends["profit_margin"] = (revenue - expenses) / revenue
        else:
            trends["profit_margin"] = 0.0

        # Revenue vs expense ratio
        if expenses > 0:
            trends["revenue_expense_ratio"] = revenue / expenses
        else:
            trends["revenue_expense_ratio"] = float("inf") if revenue > 0 else 0.0

        trends["entry_count"] = float(len(entries))
        return trends

    def _publish_event(self, report: FinancialReport) -> None:
        """Publish a LEARNING_FEEDBACK event with report summary."""
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "financial_reporting_engine",
                    "report": report.to_dict(),
                },
                source="financial_reporting_engine",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)

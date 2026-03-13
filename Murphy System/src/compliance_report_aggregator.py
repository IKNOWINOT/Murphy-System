"""
Compliance Report Aggregator for Murphy System.

Design Label: BIZ-004 — Multi-Framework Compliance Collection & Violation Detection
Owner: Compliance Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable compliance reports)
  - EventBackbone (publishes LEARNING_FEEDBACK on compliance events)
  - ComplianceAutomationBridge (CMP-001, optional, for live compliance data)
  - ComplianceEngine (src/compliance_engine.py, optional, for rule evaluation)

Implements Phase 5 — Business Operations Automation (continued):
  Aggregates compliance check results across multiple frameworks
  (GDPR, SOC2, HIPAA, PCI-DSS, ISO27001), detects violations,
  computes compliance posture scores, and generates periodic
  compliance summary reports.

Flow:
  1. Register compliance frameworks with control categories
  2. Ingest compliance check results (framework, control, pass/fail)
  3. Detect violations (failed checks)
  4. Compute posture score per framework (passed / total)
  5. Generate compliance summary report
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies compliance sources
  - Bounded: configurable max checks and reports
  - Conservative: any failed check is flagged as a violation
  - Audit trail: every compliance report is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CHECKS = 100_000
_MAX_REPORTS = 1_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ComplianceCheck:
    """A single compliance check result."""
    check_id: str
    framework: str          # GDPR | SOC2 | HIPAA | PCI-DSS | ISO27001
    control_id: str
    control_name: str
    passed: bool
    details: str = ""
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "framework": self.framework,
            "control_id": self.control_id,
            "control_name": self.control_name,
            "passed": self.passed,
            "details": self.details[:500],
            "checked_at": self.checked_at,
        }


@dataclass
class ComplianceViolation:
    """A detected compliance violation."""
    violation_id: str
    framework: str
    control_id: str
    control_name: str
    details: str
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "framework": self.framework,
            "control_id": self.control_id,
            "control_name": self.control_name,
            "details": self.details[:500],
            "detected_at": self.detected_at,
        }


@dataclass
class ComplianceSummaryReport:
    """A periodic compliance summary."""
    report_id: str
    total_checks: int
    total_passed: int
    total_failed: int
    overall_score: float            # 0.0 – 1.0
    framework_scores: Dict[str, float] = field(default_factory=dict)
    violations: List[ComplianceViolation] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_checks": self.total_checks,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "overall_score": round(self.overall_score, 4),
            "framework_scores": {k: round(v, 4) for k, v in self.framework_scores.items()},
            "violations": [v.to_dict() for v in self.violations],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# ComplianceReportAggregator
# ---------------------------------------------------------------------------

class ComplianceReportAggregator:
    """Multi-framework compliance collection and violation detection.

    Design Label: BIZ-004
    Owner: Compliance Team / Platform Engineering

    Usage::

        agg = ComplianceReportAggregator(persistence_manager=pm)
        agg.ingest_check("GDPR", "GDPR-1", "Data minimisation", True)
        agg.ingest_check("SOC2", "CC6.1", "Logical access", False, "Weak password policy")
        report = agg.generate_report()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_checks: int = _MAX_CHECKS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._checks: List[ComplianceCheck] = []
        self._reports: List[ComplianceSummaryReport] = []
        self._max_checks = max_checks

    # ------------------------------------------------------------------
    # Check ingestion
    # ------------------------------------------------------------------

    def ingest_check(
        self,
        framework: str,
        control_id: str,
        control_name: str,
        passed: bool,
        details: str = "",
    ) -> ComplianceCheck:
        check = ComplianceCheck(
            check_id=f"cc-{uuid.uuid4().hex[:8]}",
            framework=framework.upper().strip(),
            control_id=control_id,
            control_name=control_name,
            passed=passed,
            details=details,
        )
        with self._lock:
            if len(self._checks) >= self._max_checks:
                evict = max(1, self._max_checks // 10)
                self._checks = self._checks[evict:]
            self._checks.append(check)
        return check

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self) -> ComplianceSummaryReport:
        with self._lock:
            checks = list(self._checks)

        passed = sum(1 for c in checks if c.passed)
        failed = len(checks) - passed
        overall = passed / (len(checks) or 1) if checks else 1.0

        # Per-framework scores
        fw_totals: Dict[str, int] = Counter()
        fw_passed: Dict[str, int] = Counter()
        for c in checks:
            fw_totals[c.framework] += 1
            if c.passed:
                fw_passed[c.framework] += 1
        fw_scores = {
            fw: fw_passed[fw] / fw_totals[fw] for fw in fw_totals
        }

        # Violations
        violations = [
            ComplianceViolation(
                violation_id=f"cv-{uuid.uuid4().hex[:8]}",
                framework=c.framework,
                control_id=c.control_id,
                control_name=c.control_name,
                details=c.details,
            )
            for c in checks if not c.passed
        ]

        report = ComplianceSummaryReport(
            report_id=f"csr-{uuid.uuid4().hex[:8]}",
            total_checks=len(checks),
            total_passed=passed,
            total_failed=failed,
            overall_score=overall,
            framework_scores=fw_scores,
            violations=violations,
        )

        with self._lock:
            if len(self._reports) >= _MAX_REPORTS:
                self._reports = self._reports[_MAX_REPORTS // 10:]
            self._reports.append(report)

        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=report.report_id, document=report.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)
        if self._backbone is not None:
            self._publish_event(report)

        logger.info(
            "Compliance report: %d checks, %.1f%% pass rate, %d violations",
            report.total_checks, report.overall_score * 100, len(violations),
        )
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_violations(self, framework: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            checks = list(self._checks)
        failed = [c for c in checks if not c.passed]
        if framework:
            failed = [c for c in failed if c.framework == framework.upper()]
        return [c.to_dict() for c in failed[-limit:]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._reports[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_checks": len(self._checks),
                "total_reports": len(self._reports),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, report: ComplianceSummaryReport) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "compliance_report_aggregator",
                    "action": "report_generated",
                    "report_id": report.report_id,
                    "overall_score": report.overall_score,
                    "total_violations": len(report.violations),
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="compliance_report_aggregator",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)

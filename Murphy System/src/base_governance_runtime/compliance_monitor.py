"""
Compliance Monitor Implementation

Continuous compliance monitoring and reporting for the Murphy System.
Tracks ongoing compliance status and generates compliance reports.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

from .preset_manager import GovernancePreset
from .validation_engine import ComplianceGap, ComplianceStatus, ValidationResult

logger = logging.getLogger(__name__)


class ComplianceEvent:
    """Compliance monitoring event"""

    def __init__(self, event_type: str, severity: str, description: str,
                 timestamp: datetime = None):
        self.event_id = uuid4()
        self.event_type = event_type
        self.severity = severity
        self.description = description
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.resolved = False


@dataclass
class ComplianceMetrics:
    """Compliance metrics over time"""
    timestamp: datetime
    compliance_percentage: float
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int


@dataclass
class ComplianceReport:
    """Compliance report with detailed analysis"""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    overall_status: ComplianceStatus
    compliance_percentage: float

    # Detailed breakdown
    active_presets: List[str]
    total_requirements: int
    satisfied_requirements: int
    gaps_by_severity: Dict[str, int]

    # Metrics and trends
    metrics: List[ComplianceMetrics] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "overall_status": self.overall_status.value,
            "compliance_percentage": self.compliance_percentage,
            "active_presets": self.active_presets,
            "total_requirements": self.total_requirements,
            "satisfied_requirements": self.satisfied_requirements,
            "gaps_by_severity": self.gaps_by_severity,
            "metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "compliance_percentage": m.compliance_percentage,
                    "total_gaps": m.total_gaps,
                    "critical_gaps": m.critical_gaps,
                    "high_gaps": m.high_gaps,
                    "medium_gaps": m.medium_gaps,
                    "low_gaps": m.low_gaps
                }
                for m in self.metrics
            ],
            "recommendations": self.recommendations
        }


class ComplianceMonitor:
    """Monitors ongoing compliance and generates reports"""

    def __init__(self):
        self.compliance_history: List[ValidationResult] = []
        self.compliance_events: List[ComplianceEvent] = []
        self.current_status: Optional[ValidationResult] = None

    def record_validation_result(self, result: ValidationResult):
        """Record a new validation result"""
        self.compliance_history.append(result)
        self.current_status = result

        # Generate compliance events for critical gaps
        for gap in result.get_critical_gaps():
            event = ComplianceEvent(
                event_type="compliance_gap",
                severity="CRITICAL",
                description=f"Critical compliance gap: {gap.description}"
            )
            self.compliance_events.append(event)

    def get_current_status(self) -> Optional[ValidationResult]:
        """Get current compliance status"""
        return self.current_status

    def get_compliance_trend(self, days: int = 30) -> List[ComplianceMetrics]:
        """Get compliance trend over specified days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        metrics = []
        for result in self.compliance_history:
            if result.timestamp >= cutoff:
                gaps_by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
                for gap in result.gaps:
                    gaps_by_severity[gap.severity] = gaps_by_severity.get(gap.severity, 0) + 1

                metric = ComplianceMetrics(
                    timestamp=result.timestamp,
                    compliance_percentage=result.get_compliance_percentage(),
                    total_gaps=len(result.gaps),
                    critical_gaps=gaps_by_severity["CRITICAL"],
                    high_gaps=gaps_by_severity["HIGH"],
                    medium_gaps=gaps_by_severity["MEDIUM"],
                    low_gaps=gaps_by_severity["LOW"]
                )
                metrics.append(metric)

        return sorted(metrics, key=lambda m: m.timestamp)

    def generate_compliance_report(self, period_start: datetime = None,
                                 period_end: datetime = None) -> ComplianceReport:
        """Generate comprehensive compliance report"""

        if period_end is None:
            period_end = datetime.now(timezone.utc)
        if period_start is None:
            period_start = period_end - timedelta(days=30)

        report_id = f"compliance_report_{period_start.strftime('%Y%m%d')}_{period_end.strftime('%Y%m%d')}"

        # Get current status
        current = self.get_current_status()
        if not current:
            # No current status - create default
            from .validation_engine import ComplianceStatus, ValidationEngine
            engine = ValidationEngine()
            current = engine.check_mandatory_baseline_controls()

        # Analyze gaps by severity
        gaps_by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for gap in current.gaps:
            gaps_by_severity[gap.severity] = gaps_by_severity.get(gap.severity, 0) + 1

        # Get metrics for the period
        metrics = self.get_compliance_trend(days=(period_end - period_start).days)

        # Generate recommendations
        recommendations = self._generate_recommendations(current)

        return ComplianceReport(
            report_id=report_id,
            generated_at=datetime.now(timezone.utc),
            period_start=period_start,
            period_end=period_end,
            overall_status=current.overall_status,
            compliance_percentage=current.get_compliance_percentage(),
            active_presets=[],  # This would come from preset manager
            total_requirements=current.total_requirements,
            satisfied_requirements=current.satisfied_requirements,
            gaps_by_severity=gaps_by_severity,
            metrics=metrics,
            recommendations=recommendations
        )

    def _generate_recommendations(self, current: ValidationResult) -> List[str]:
        """Generate recommendations based on compliance status"""
        recommendations = []

        if current.overall_status == ComplianceStatus.NON_COMPLIANT:
            recommendations.append("Address critical gaps before system deployment")

            critical_gaps = current.get_critical_gaps()
            for gap in critical_gaps:
                if not gap.can_configure:
                    recommendations.append(f"IMPLEMENT PRIORITY: {gap.remedy}")

        elif current.overall_status == ComplianceStatus.PARTIALLY_COMPLIANT:
            high_gaps = [g for g in current.gaps if g.severity == "HIGH"]
            if high_gaps:
                recommendations.append("Resolve high-priority gaps for full compliance")

            configurable_gaps = [g for g in current.gaps if g.can_configure]
            if configurable_gaps:
                recommendations.append("Configure available controls to close remaining gaps")

        else:  # COMPLIANT
            recommendations.append("System is fully compliant - maintain monitoring")
            recommendations.append("Schedule regular compliance reviews")

        return recommendations

    def check_blocking_gaps(self) -> List[ComplianceGap]:
        """Check for gaps that block system activation"""
        if not self.current_status:
            return []
        return [gap for gap in self.current_status.gaps
                if gap.severity in ["CRITICAL", "HIGH"] and not gap.can_configure]

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get high-level compliance summary"""
        if not self.current_status:
            return {
                "status": "UNKNOWN",
                "compliance_percentage": 0.0,
                "total_gaps": 0,
                "critical_gaps": 0,
                "blocking_gaps": 0,
                "last_updated": None
            }

        return {
            "status": self.current_status.overall_status.value,
            "compliance_percentage": self.current_status.get_compliance_percentage(),
            "total_gaps": len(self.current_status.gaps),
            "critical_gaps": len(self.current_status.get_critical_gaps()),
            "blocking_gaps": len(self.check_blocking_gaps()),
            "last_updated": self.current_status.timestamp.isoformat()
        }

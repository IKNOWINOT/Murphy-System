"""
Compliance Validation Engine for Murphy System Runtime

This module validates deliverables against regulatory and compliance requirements
before release, providing:
- Compliance requirement registration and tracking
- Deliverable validation against multiple frameworks (GDPR, SOC2, HIPAA, PCI-DSS, ISO27001)
- Policy gate management that must clear before delivery
- HITL (Human-In-The-Loop) approval integration for compliance sign-off
- Compliance reporting and release-readiness checks
"""

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ComplianceFramework(str, Enum):
    """Supported regulatory/compliance frameworks."""
    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    CUSTOM = "custom"


class ComplianceSeverity(str, Enum):
    """Severity levels for compliance requirements."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComplianceStatus(str, Enum):
    """Status of a compliance check."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NEEDS_REVIEW = "needs_review"
    EXEMPT = "exempt"
    PENDING = "pending"


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Frameworks applicable to common domains
_DOMAIN_FRAMEWORK_MAP: Dict[str, List[ComplianceFramework]] = {
    "healthcare": [ComplianceFramework.HIPAA, ComplianceFramework.SOC2],
    "finance": [ComplianceFramework.PCI_DSS, ComplianceFramework.SOC2, ComplianceFramework.ISO27001],
    "payments": [ComplianceFramework.PCI_DSS, ComplianceFramework.SOC2],
    "eu_data": [ComplianceFramework.GDPR, ComplianceFramework.ISO27001],
    "personal_data": [ComplianceFramework.GDPR],
    "cloud": [ComplianceFramework.SOC2, ComplianceFramework.ISO27001],
    "general": [ComplianceFramework.SOC2],
}


@dataclass
class ComplianceRequirement:
    """A single compliance requirement to validate against."""
    requirement_id: str
    framework: ComplianceFramework
    description: str
    severity: ComplianceSeverity
    applicable_domains: List[str] = field(default_factory=list)
    auto_checkable: bool = False


@dataclass
class ComplianceCheckResult:
    """Result of checking a single requirement against a deliverable."""
    requirement_id: str
    status: ComplianceStatus
    evidence: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewer: Optional[str] = None
    notes: Optional[str] = None


class ComplianceEngine:
    """Validates deliverables against regulatory and compliance requirements.

    Manages compliance requirements, executes automated and manual checks,
    tracks HITL approvals, and determines release readiness.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requirements: Dict[str, ComplianceRequirement] = {}
        self._results: Dict[str, List[ComplianceCheckResult]] = {}  # keyed by session_id
        self._current_session: str = uuid.uuid4().hex[:12]

        self._register_defaults()

    # ------------------------------------------------------------------
    # Requirement registration
    # ------------------------------------------------------------------

    def register_requirement(self, req: ComplianceRequirement) -> str:
        """Register a compliance requirement and return its requirement_id."""
        with self._lock:
            self._requirements[req.requirement_id] = req
        logger.info("Registered requirement %s (%s)", req.requirement_id, req.framework.value)
        return req.requirement_id

    # ------------------------------------------------------------------
    # Deliverable checking
    # ------------------------------------------------------------------

    def check_deliverable(
        self,
        deliverable: Dict[str, Any],
        frameworks: Optional[List[ComplianceFramework]] = None,
    ) -> Dict[str, Any]:
        """Check a deliverable against applicable requirements.

        Returns a summary dict with overall status, per-requirement results,
        and counts of each status category.

        Note: AUDIT STATUS: Not externally audited
        """
        session_id = deliverable.get("session_id", self._current_session)
        domain = deliverable.get("domain", "general")

        with self._lock:
            all_reqs = list(self._requirements.values())

        # Filter to requested frameworks
        if frameworks is not None:
            fw_set = set(frameworks)
            applicable = [r for r in all_reqs if r.framework in fw_set]
        else:
            applicable = list(all_reqs)

        # Further filter by domain if the requirement specifies applicable domains
        filtered: List[ComplianceRequirement] = []
        for req in applicable:
            if not req.applicable_domains or domain in req.applicable_domains:
                filtered.append(req)

        results: List[ComplianceCheckResult] = []
        for req in filtered:
            result = self._evaluate_requirement(req, deliverable)
            results.append(result)

        # Store results
        with self._lock:
            self._results.setdefault(session_id, []).extend(results)

        # Build summary
        status_counts: Dict[str, int] = defaultdict(int)
        for r in results:
            status_counts[r.status.value] += 1

        has_non_compliant = status_counts.get("non_compliant", 0) > 0
        has_needs_review = status_counts.get("needs_review", 0) > 0

        if has_non_compliant:
            overall = ComplianceStatus.NON_COMPLIANT
        elif has_needs_review:
            overall = ComplianceStatus.NEEDS_REVIEW
        else:
            overall = ComplianceStatus.COMPLIANT

        logger.info(
            "Checked deliverable (session=%s): %s (%d requirements)",
            session_id, overall.value, len(results),
        )

        return {
            "session_id": session_id,
            "overall_status": overall.value,
            "total_requirements": len(results),
            "status_counts": dict(status_counts),
            "results": [
                {
                    "requirement_id": r.requirement_id,
                    "status": r.status.value,
                    "evidence": r.evidence,
                    "checked_at": r.checked_at.isoformat(),
                    "reviewer": r.reviewer,
                    "notes": r.notes,
                }
                for r in results
            ],
        }

    # ------------------------------------------------------------------
    # HITL approval
    # ------------------------------------------------------------------

    def approve_requirement(
        self,
        requirement_id: str,
        reviewer: str,
        notes: str = "",
    ) -> bool:
        """Record a HITL approval for a manual compliance check.

        Note: AUDIT STATUS: Not externally audited
        """
        with self._lock:
            if requirement_id not in self._requirements:
                logger.warning("Requirement %s not found", requirement_id)
                return False

            # Find the most recent pending/needs_review result for this requirement
            for session_results in self._results.values():
                for result in reversed(session_results):
                    if (
                        result.requirement_id == requirement_id
                        and result.status in (ComplianceStatus.NEEDS_REVIEW, ComplianceStatus.PENDING)
                    ):
                        result.status = ComplianceStatus.COMPLIANT
                        result.reviewer = reviewer
                        result.notes = notes
                        result.checked_at = datetime.now(timezone.utc)
                        logger.info(
                            "Requirement %s approved by %s",
                            requirement_id, reviewer,
                        )
                        return True

            # No pending result found; create a new approval record
            approval = ComplianceCheckResult(
                requirement_id=requirement_id,
                status=ComplianceStatus.COMPLIANT,
                evidence=f"Manual approval by {reviewer}",
                reviewer=reviewer,
                notes=notes,
            )
            self._results.setdefault(self._current_session, []).append(approval)

        logger.info("Requirement %s approved by %s (new record)", requirement_id, reviewer)
        return True

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_compliance_report(
        self,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a compliance report for a session or all sessions.

        Note: AUDIT STATUS: Not externally audited
        """
        with self._lock:
            if session_id is not None:
                results = list(self._results.get(session_id, []))
            else:
                results = [r for rs in self._results.values() for r in rs]
            total_reqs = len(self._requirements)

        status_counts: Dict[str, int] = defaultdict(int)
        framework_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for r in results:
            status_counts[r.status.value] += 1
            req = self._requirements.get(r.requirement_id)
            if req:
                framework_counts[req.framework.value][r.status.value] += 1

        compliant = status_counts.get("compliant", 0)
        total = len(results)
        compliance_rate = (compliant / total) if total > 0 else 0.0

        return {
            "session_id": session_id,
            "total_registered_requirements": total_reqs,
            "total_checked": total,
            "compliance_rate": round(compliance_rate, 4),
            "status_counts": dict(status_counts),
            "framework_breakdown": {
                fw: dict(counts) for fw, counts in framework_counts.items()
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Framework applicability
    # ------------------------------------------------------------------

    def get_applicable_frameworks(self, domain: str) -> List[ComplianceFramework]:
        """Return frameworks applicable to the given domain.

        Note: AUDIT STATUS: Not externally audited
        """
        return list(_DOMAIN_FRAMEWORK_MAP.get(domain, [ComplianceFramework.SOC2]))

    # ------------------------------------------------------------------
    # Release readiness
    # ------------------------------------------------------------------

    def is_release_ready(
        self,
        deliverable: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Determine whether a deliverable is ready for release.

        Returns a tuple of (ready, blockers) where blockers lists human-readable
        descriptions of any issues preventing release.

        Note: AUDIT STATUS: Not externally audited
        """
        report = self.check_deliverable(deliverable)
        blockers: List[str] = []

        for r in report["results"]:
            if r["status"] == ComplianceStatus.NON_COMPLIANT.value:
                req = self._requirements.get(r["requirement_id"])
                desc = req.description if req else r["requirement_id"]
                blockers.append(f"NON_COMPLIANT: {desc}")
            elif r["status"] == ComplianceStatus.NEEDS_REVIEW.value:
                req = self._requirements.get(r["requirement_id"])
                desc = req.description if req else r["requirement_id"]
                blockers.append(f"NEEDS_REVIEW: {desc}")

        ready = len(blockers) == 0
        logger.info("Release readiness: %s (%d blockers)", ready, len(blockers))
        return ready, blockers

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current engine status."""
        with self._lock:
            total_requirements = len(self._requirements)
            total_sessions = len(self._results)
            total_checks = sum(len(rs) for rs in self._results.values())

            framework_req_counts: Dict[str, int] = defaultdict(int)
            for req in self._requirements.values():
                framework_req_counts[req.framework.value] += 1

            status_counts: Dict[str, int] = defaultdict(int)
            for rs in self._results.values():
                for r in rs:
                    status_counts[r.status.value] += 1

        return {
            "total_requirements": total_requirements,
            "total_sessions": total_sessions,
            "total_checks": total_checks,
            "framework_requirement_counts": dict(framework_req_counts),
            "check_status_counts": dict(status_counts),
            "current_session": self._current_session,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_requirement(
        self,
        req: ComplianceRequirement,
        deliverable: Dict[str, Any],
    ) -> ComplianceCheckResult:
        """Evaluate a single requirement against a deliverable.

        Note: AUDIT STATUS: Not externally audited
        """
        if not req.auto_checkable:
            return ComplianceCheckResult(
                requirement_id=req.requirement_id,
                status=ComplianceStatus.NEEDS_REVIEW,
                evidence="Manual review required",
            )

        # Auto-check based on deliverable metadata
        checks = deliverable.get("compliance_checks", {})
        check_value = checks.get(req.requirement_id)

        if check_value is True:
            return ComplianceCheckResult(
                requirement_id=req.requirement_id,
                status=ComplianceStatus.COMPLIANT,
                evidence=f"Automated check passed for {req.requirement_id}",
            )
        elif check_value is False:
            return ComplianceCheckResult(
                requirement_id=req.requirement_id,
                status=ComplianceStatus.NON_COMPLIANT,
                evidence=f"Automated check failed for {req.requirement_id}",
            )
        else:
            return ComplianceCheckResult(
                requirement_id=req.requirement_id,
                status=ComplianceStatus.PENDING,
                evidence=f"No automated check data for {req.requirement_id}",
            )

    def _register_defaults(self) -> None:
        """Register sensible default requirements for common frameworks."""
        defaults = [
            # GDPR
            ComplianceRequirement(
                requirement_id="gdpr-data-minimization",
                framework=ComplianceFramework.GDPR,
                description="Data minimization: only collect necessary personal data",
                severity=ComplianceSeverity.HIGH,
                applicable_domains=["personal_data", "eu_data"],
                auto_checkable=False,
            ),
            ComplianceRequirement(
                requirement_id="gdpr-consent",
                framework=ComplianceFramework.GDPR,
                description="Valid consent obtained for data processing",
                severity=ComplianceSeverity.CRITICAL,
                applicable_domains=["personal_data", "eu_data"],
                auto_checkable=False,
            ),
            ComplianceRequirement(
                requirement_id="gdpr-retention",
                framework=ComplianceFramework.GDPR,
                description="Data retention policies enforced",
                severity=ComplianceSeverity.HIGH,
                applicable_domains=["personal_data", "eu_data"],
                auto_checkable=True,
            ),
            # SOC2
            ComplianceRequirement(
                requirement_id="soc2-access-control",
                framework=ComplianceFramework.SOC2,
                description="Access control mechanisms in place",
                severity=ComplianceSeverity.CRITICAL,
                applicable_domains=["cloud", "general", "finance"],
                auto_checkable=True,
            ),
            ComplianceRequirement(
                requirement_id="soc2-audit-logging",
                framework=ComplianceFramework.SOC2,
                description="Audit logging enabled for all operations",
                severity=ComplianceSeverity.HIGH,
                applicable_domains=["cloud", "general", "finance"],
                auto_checkable=True,
            ),
            ComplianceRequirement(
                requirement_id="soc2-encryption",
                framework=ComplianceFramework.SOC2,
                description="Data encrypted at rest and in transit",
                severity=ComplianceSeverity.CRITICAL,
                applicable_domains=["cloud", "general", "finance"],
                auto_checkable=True,
            ),
            # HIPAA
            ComplianceRequirement(
                requirement_id="hipaa-phi-protection",
                framework=ComplianceFramework.HIPAA,
                description="Protected Health Information (PHI) safeguards in place",
                severity=ComplianceSeverity.CRITICAL,
                applicable_domains=["healthcare"],
                auto_checkable=False,
            ),
            ComplianceRequirement(
                requirement_id="hipaa-access-logging",
                framework=ComplianceFramework.HIPAA,
                description="Access to PHI is logged and auditable",
                severity=ComplianceSeverity.HIGH,
                applicable_domains=["healthcare"],
                auto_checkable=True,
            ),
            # PCI-DSS
            ComplianceRequirement(
                requirement_id="pci-encryption",
                framework=ComplianceFramework.PCI_DSS,
                description="Cardholder data encrypted",
                severity=ComplianceSeverity.CRITICAL,
                applicable_domains=["payments", "finance"],
                auto_checkable=True,
            ),
            ComplianceRequirement(
                requirement_id="pci-access-control",
                framework=ComplianceFramework.PCI_DSS,
                description="Access to cardholder data restricted",
                severity=ComplianceSeverity.CRITICAL,
                applicable_domains=["payments", "finance"],
                auto_checkable=True,
            ),
            ComplianceRequirement(
                requirement_id="pci-logging",
                framework=ComplianceFramework.PCI_DSS,
                description="Track and monitor access to cardholder data",
                severity=ComplianceSeverity.HIGH,
                applicable_domains=["payments", "finance"],
                auto_checkable=True,
            ),
        ]

        for req in defaults:
            self.register_requirement(req)

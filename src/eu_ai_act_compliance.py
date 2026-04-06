"""
EU AI Act Compliance Module
============================

Implements the nine core requirements of the EU AI Act (Regulation
2024/1689) with automated tracking, risk classification, and
documentation generation.

Design label: EUAIA-001

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """EU AI Act risk classification tiers (Article 6 / Annex III)."""

    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class ComplianceStatus(str, Enum):
    """Per-requirement compliance status."""

    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"


class AuditSeverity(str, Enum):
    """Severity of a compliance audit finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ComplianceRequirement:
    """One of the nine core EU AI Act requirements."""

    req_id: str
    title: str
    article_ref: str
    description: str
    status: ComplianceStatus = ComplianceStatus.NON_COMPLIANT
    evidence: List[str] = field(default_factory=list)
    last_assessed: Optional[str] = None


@dataclass
class RiskAssessment:
    """Risk classification result for a system or component."""

    assessment_id: str
    system_name: str
    risk_level: RiskLevel
    annex_iii_category: Optional[str] = None
    justification: str = ""
    assessed_at: str = ""
    assessor: str = "murphy_auto"


@dataclass
class AuditFinding:
    """A single finding from a compliance audit."""

    finding_id: str
    requirement_id: str
    severity: AuditSeverity
    description: str
    remediation: str = ""
    status: str = "open"
    created_at: str = ""


@dataclass
class SystemCard:
    """Auto-generated AI system card (Article 13 transparency)."""

    card_id: str
    system_name: str
    version: str
    purpose: str
    risk_level: RiskLevel
    intended_use: str = ""
    limitations: str = ""
    training_data_summary: str = ""
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    human_oversight_measures: str = ""
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Annex III high-risk categories
# ---------------------------------------------------------------------------

ANNEX_III_CATEGORIES = {
    "biometric_identification": "Real-time and 'post' remote biometric identification",
    "critical_infrastructure": "Safety components of critical infrastructure",
    "education_vocational": "AI for educational / vocational training access",
    "employment_hr": "AI for recruitment, task allocation, performance monitoring",
    "essential_services": "Access to essential private/public services & benefits",
    "law_enforcement": "AI used by law enforcement",
    "migration_asylum": "AI for migration, asylum and border control",
    "justice_democracy": "AI for administration of justice and democratic processes",
    "general_purpose": "General-purpose AI models with systemic risk",
}


# ---------------------------------------------------------------------------
# The nine core requirements
# ---------------------------------------------------------------------------

_REQUIREMENTS: List[Dict[str, str]] = [
    {
        "req_id": "EUAIA-R1",
        "title": "Risk Management System",
        "article_ref": "Article 9",
        "description": (
            "Establish and maintain a risk management system that identifies,"
            " analyzes, estimates, and evaluates risks."
        ),
    },
    {
        "req_id": "EUAIA-R2",
        "title": "Data Governance",
        "article_ref": "Article 10",
        "description": (
            "Training, validation, and testing data sets must meet quality"
            " criteria (relevant, representative, free of errors, complete)."
        ),
    },
    {
        "req_id": "EUAIA-R3",
        "title": "Technical Documentation",
        "article_ref": "Article 11",
        "description": (
            "Draw up technical documentation demonstrating compliance"
            " before the system is placed on the market."
        ),
    },
    {
        "req_id": "EUAIA-R4",
        "title": "Record-Keeping / Logging",
        "article_ref": "Article 12",
        "description": (
            "High-risk systems must have automatic recording (logging)"
            " of events for traceability."
        ),
    },
    {
        "req_id": "EUAIA-R5",
        "title": "Transparency & Information",
        "article_ref": "Article 13",
        "description": (
            "Provide clear information to deployers on the system's"
            " capabilities, limitations, and intended purpose."
        ),
    },
    {
        "req_id": "EUAIA-R6",
        "title": "Human Oversight",
        "article_ref": "Article 14",
        "description": (
            "Design systems so they can be effectively overseen by"
            " natural persons during use."
        ),
    },
    {
        "req_id": "EUAIA-R7",
        "title": "Accuracy, Robustness & Cybersecurity",
        "article_ref": "Article 15",
        "description": (
            "Achieve appropriate levels of accuracy, robustness,"
            " and cybersecurity throughout the lifecycle."
        ),
    },
    {
        "req_id": "EUAIA-R8",
        "title": "Conformity Assessment",
        "article_ref": "Articles 40-49",
        "description": (
            "Undergo a conformity assessment procedure before"
            " placing the system on the EU market."
        ),
    },
    {
        "req_id": "EUAIA-R9",
        "title": "Post-Market Monitoring",
        "article_ref": "Article 72",
        "description": (
            "Establish a post-market monitoring system proportionate"
            " to the nature of the AI and the level of risk."
        ),
    },
]


# ---------------------------------------------------------------------------
# EUAIActComplianceEngine
# ---------------------------------------------------------------------------


class EUAIActComplianceEngine:
    """Tracks and enforces the nine core EU AI Act requirements.

    Provides:
    - Risk classification (Annex III mapping)
    - Per-requirement compliance tracking with evidence
    - Audit finding management
    - Automated system card generation (Article 13)
    - Integration hooks for HITL governance (Article 14)
    - Cryptographic audit log filtering (Article 15)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.requirements: Dict[str, ComplianceRequirement] = {}
        self.risk_assessments: Dict[str, RiskAssessment] = {}
        self.findings: List[AuditFinding] = []
        self.system_cards: Dict[str, SystemCard] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._initialize_requirements()

    # -- Setup --------------------------------------------------------------

    def _initialize_requirements(self) -> None:
        """Populate the nine core requirements from the canonical list."""
        for spec in _REQUIREMENTS:
            req = ComplianceRequirement(**spec)
            self.requirements[req.req_id] = req

    # -- Risk Classification ------------------------------------------------

    def classify_risk(
        self,
        system_name: str,
        annex_iii_category: Optional[str] = None,
        *,
        intended_use: str = "",
        has_biometric: bool = False,
        is_safety_critical: bool = False,
        affects_employment: bool = False,
        affects_education: bool = False,
        used_by_law_enforcement: bool = False,
    ) -> RiskAssessment:
        """Classify a system's risk level per Annex III mapping.

        Returns a :class:`RiskAssessment` and stores it internally.
        """
        # Determine risk level heuristically
        if has_biometric and used_by_law_enforcement:
            level = RiskLevel.UNACCEPTABLE
            cat = annex_iii_category or "biometric_identification"
        elif any([is_safety_critical, affects_employment, affects_education,
                   used_by_law_enforcement]):
            level = RiskLevel.HIGH
            cat = annex_iii_category or self._infer_category(
                is_safety_critical, affects_employment,
                affects_education, used_by_law_enforcement,
            )
        elif annex_iii_category and annex_iii_category in ANNEX_III_CATEGORIES:
            level = RiskLevel.HIGH
            cat = annex_iii_category
        else:
            level = RiskLevel.LIMITED
            cat = annex_iii_category

        assessment = RiskAssessment(
            assessment_id=str(uuid.uuid4()),
            system_name=system_name,
            risk_level=level,
            annex_iii_category=cat,
            justification=f"Auto-classified: intended_use='{intended_use}'",
            assessed_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self.risk_assessments[assessment.assessment_id] = assessment
            self._log_event("risk_classified", {
                "system": system_name, "level": level.value,
            })
        return assessment

    @staticmethod
    def _infer_category(
        safety: bool, employment: bool, education: bool, law: bool
    ) -> str:
        if safety:
            return "critical_infrastructure"
        if employment:
            return "employment_hr"
        if education:
            return "education_vocational"
        if law:
            return "law_enforcement"
        return "general_purpose"

    # -- Requirement tracking -----------------------------------------------

    def update_requirement(
        self,
        req_id: str,
        status: ComplianceStatus,
        evidence: Optional[List[str]] = None,
    ) -> Optional[ComplianceRequirement]:
        """Update the compliance status and evidence for a requirement."""
        with self._lock:
            req = self.requirements.get(req_id)
            if not req:
                logger.warning("Unknown requirement: %s", req_id)
                return None
            req.status = status
            if evidence:
                req.evidence.extend(evidence)
            req.last_assessed = datetime.now(timezone.utc).isoformat()
            self._log_event("requirement_updated", {
                "req_id": req_id, "status": status.value,
            })
            return req

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Return a summary of compliance across all nine requirements."""
        with self._lock:
            total = len(self.requirements)
            statuses = {s.value: 0 for s in ComplianceStatus}
            for req in self.requirements.values():
                statuses[req.status.value] += 1
            return {
                "total_requirements": total,
                "compliant": statuses["compliant"],
                "partial": statuses["partial"],
                "non_compliant": statuses["non_compliant"],
                "not_applicable": statuses["not_applicable"],
                "compliance_score": round(
                    (statuses["compliant"] + 0.5 * statuses["partial"]) / max(total, 1), 2
                ),
                "requirements": {
                    rid: {"title": r.title, "status": r.status.value, "article": r.article_ref}
                    for rid, r in self.requirements.items()
                },
            }

    # -- Audit findings -----------------------------------------------------

    def add_finding(
        self,
        requirement_id: str,
        severity: AuditSeverity,
        description: str,
        remediation: str = "",
    ) -> AuditFinding:
        """Record a new compliance audit finding."""
        finding = AuditFinding(
            finding_id=str(uuid.uuid4()),
            requirement_id=requirement_id,
            severity=severity,
            description=description,
            remediation=remediation,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self.findings.append(finding)
            self._log_event("finding_added", {
                "finding_id": finding.finding_id,
                "severity": severity.value,
            })
        return finding

    def resolve_finding(self, finding_id: str) -> bool:
        """Mark a finding as resolved."""
        with self._lock:
            for f in self.findings:
                if f.finding_id == finding_id:
                    f.status = "resolved"
                    self._log_event("finding_resolved", {"finding_id": finding_id})
                    return True
        return False

    # -- System card generation (Article 13) --------------------------------

    def generate_system_card(
        self,
        system_name: str,
        version: str = "1.0",
        purpose: str = "",
        intended_use: str = "",
        limitations: str = "",
        training_data_summary: str = "",
        performance_metrics: Optional[Dict[str, Any]] = None,
        human_oversight_measures: str = "",
    ) -> SystemCard:
        """Generate an AI system transparency card per Article 13."""
        risk = RiskLevel.LIMITED
        for ra in self.risk_assessments.values():
            if ra.system_name == system_name:
                risk = ra.risk_level
                break

        card = SystemCard(
            card_id=str(uuid.uuid4()),
            system_name=system_name,
            version=version,
            purpose=purpose,
            risk_level=risk,
            intended_use=intended_use,
            limitations=limitations,
            training_data_summary=training_data_summary,
            performance_metrics=performance_metrics or {},
            human_oversight_measures=human_oversight_measures,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self.system_cards[card.card_id] = card
            self._log_event("system_card_generated", {
                "card_id": card.card_id, "system": system_name,
            })
        return card

    # -- HITL governance hook (Article 14) ----------------------------------

    def check_human_oversight(self, decision_id: str) -> Dict[str, Any]:
        """Check whether a decision requires human oversight per Article 14.

        Returns a recommendation dict that HITL gates can act on.
        """
        # All HIGH-risk assessments mandate HITL gate
        high_risk_systems = [
            ra.system_name for ra in self.risk_assessments.values()
            if ra.risk_level in (RiskLevel.HIGH, RiskLevel.UNACCEPTABLE)
        ]
        requires_oversight = len(high_risk_systems) > 0
        return {
            "decision_id": decision_id,
            "requires_human_oversight": requires_oversight,
            "high_risk_systems": high_risk_systems,
            "article_14_recommendation": (
                "Route through HITL gate before execution"
                if requires_oversight else "Proceed — no high-risk classification"
            ),
        }

    # -- Audit log with cryptographic integrity (Article 12 / 15) -----------

    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Append an entry to the internal audit log with SHA-256 chaining."""
        prev_hash = self._audit_log[-1]["hash"] if self._audit_log else "0" * 64
        entry = {
            "seq": len(self._audit_log),
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "data": data,
            "prev_hash": prev_hash,
        }
        entry["hash"] = hashlib.sha256(
            f"{entry['seq']}:{entry['ts']}:{entry['event']}:{prev_hash}".encode()
        ).hexdigest()
        self._audit_log.append(entry)

    def get_audit_log(
        self, *, since: Optional[str] = None, event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return audit log entries with optional filters."""
        with self._lock:
            entries = list(self._audit_log)
        if since:
            entries = [e for e in entries if e["ts"] >= since]
        if event_type:
            entries = [e for e in entries if e["event"] == event_type]
        return entries

    def verify_audit_chain(self) -> bool:
        """Verify SHA-256 hash chain integrity of the audit log."""
        with self._lock:
            log = list(self._audit_log)
        prev = "0" * 64
        for entry in log:
            expected = hashlib.sha256(
                f"{entry['seq']}:{entry['ts']}:{entry['event']}:{prev}".encode()
            ).hexdigest()
            if entry["hash"] != expected:
                logger.warning("Audit chain broken at seq=%d", entry["seq"])
                return False
            prev = entry["hash"]
        return True

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise full compliance state for persistence or API response."""
        with self._lock:
            return {
                "requirements": {
                    rid: asdict(r) for rid, r in self.requirements.items()
                },
                "risk_assessments": {
                    aid: asdict(a) for aid, a in self.risk_assessments.items()
                },
                "findings": [asdict(f) for f in self.findings],
                "system_cards": {
                    cid: asdict(c) for cid, c in self.system_cards.items()
                },
                "summary": self.get_compliance_summary(),
            }

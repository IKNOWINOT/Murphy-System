"""
Compliance Orchestration Bridge for Murphy System.

Design Label: ORCH-004 — Cross-Module Compliance Validation Pipeline
Owner: Compliance Team / Security Team
Dependencies:
  - PersistenceManager (for durable compliance assessment records)
  - EventBackbone (publishes LEARNING_FEEDBACK on assessment completion)
  - ComplianceReportAggregator (BIZ-004, optional, for compliance status feeds)
  - SafetyValidationPipeline (SAF-001, optional, for safety validation integration)
  - SecurityAuditScanner (SEC-001, optional, for security scan feeds)

Implements ARCHITECTURE_MAP Next Step #15:
  Connects BIZ-004, SAF-001, and SEC-001 into an automated compliance
  validation pipeline.  Defines compliance frameworks (GDPR, SOC2, HIPAA,
  PCI-DSS, ISO27001), collects control evidence from downstream modules,
  and produces ComplianceAssessment with per-framework pass/fail/unknown.

Flow:
  1. Define compliance frameworks with required controls
  2. Register evidence sources (callables providing control status)
  3. Run assessment: collect evidence, evaluate controls per framework
  4. Produce ComplianceAssessment with per-framework results
  5. Persist assessment and publish LEARNING_FEEDBACK event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: read-only evidence collection
  - Bounded: configurable max assessment history
  - Conservative: unknown control status counts as NOT_MET
  - Audit trail: every assessment is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ASSESSMENTS = 500


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ControlStatus(str, Enum):
    """Control status (str subclass)."""
    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class FrameworkVerdict(str, Enum):
    """Framework verdict (str subclass)."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NO_DATA = "no_data"


@dataclass
class ComplianceControl:
    """A single compliance control within a framework."""
    control_id: str
    name: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_id": self.control_id,
            "name": self.name,
            "description": self.description,
        }


@dataclass
class ComplianceFramework:
    """A compliance framework with its required controls."""
    framework_id: str
    name: str
    controls: List[ComplianceControl] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework_id": self.framework_id,
            "name": self.name,
            "description": self.description,
            "controls": [c.to_dict() for c in self.controls],
        }


@dataclass
class ControlResult:
    """Assessed status of a single control."""
    control_id: str
    control_name: str
    status: ControlStatus
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_id": self.control_id,
            "control_name": self.control_name,
            "status": self.status.value,
            "evidence": self.evidence,
        }


@dataclass
class FrameworkResult:
    """Assessment result for a single framework."""
    framework_id: str
    framework_name: str
    verdict: FrameworkVerdict
    met_count: int = 0
    not_met_count: int = 0
    unknown_count: int = 0
    controls: List[ControlResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework_id": self.framework_id,
            "framework_name": self.framework_name,
            "verdict": self.verdict.value,
            "met_count": self.met_count,
            "not_met_count": self.not_met_count,
            "unknown_count": self.unknown_count,
            "controls": [c.to_dict() for c in self.controls],
        }


@dataclass
class ComplianceAssessment:
    """Full compliance assessment across all frameworks."""
    assessment_id: str
    compliant_count: int = 0
    non_compliant_count: int = 0
    partial_count: int = 0
    frameworks: List[FrameworkResult] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "compliant_count": self.compliant_count,
            "non_compliant_count": self.non_compliant_count,
            "partial_count": self.partial_count,
            "frameworks": [f.to_dict() for f in self.frameworks],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Default compliance frameworks from Plan §6.2
# ---------------------------------------------------------------------------

def _default_frameworks() -> List[ComplianceFramework]:
    return [
        ComplianceFramework("gdpr", "GDPR", [
            ComplianceControl("gdpr-01", "Data privacy controls"),
            ComplianceControl("gdpr-02", "Data subject rights"),
            ComplianceControl("gdpr-03", "Data processing agreements"),
            ComplianceControl("gdpr-04", "Breach notification"),
        ], "General Data Protection Regulation"),
        ComplianceFramework("soc2", "SOC2", [
            ComplianceControl("soc2-01", "Security controls"),
            ComplianceControl("soc2-02", "Availability controls"),
            ComplianceControl("soc2-03", "Processing integrity"),
            ComplianceControl("soc2-04", "Confidentiality controls"),
        ], "Service Organization Control 2"),
        ComplianceFramework("hipaa", "HIPAA", [
            ComplianceControl("hipaa-01", "PHI protection"),
            ComplianceControl("hipaa-02", "Access controls"),
            ComplianceControl("hipaa-03", "Audit logging"),
            ComplianceControl("hipaa-04", "Transmission security"),
        ], "Health Insurance Portability and Accountability Act"),
        ComplianceFramework("pci-dss", "PCI-DSS", [
            ComplianceControl("pci-01", "Payment data protection"),
            ComplianceControl("pci-02", "Network security"),
            ComplianceControl("pci-03", "Access restriction"),
        ], "Payment Card Industry Data Security Standard"),
        ComplianceFramework("iso27001", "ISO27001", [
            ComplianceControl("iso-01", "Information security policy"),
            ComplianceControl("iso-02", "Asset management"),
            ComplianceControl("iso-03", "Access control"),
            ComplianceControl("iso-04", "Cryptography"),
        ], "Information Security Management"),
    ]


# ---------------------------------------------------------------------------
# ComplianceOrchestrationBridge
# ---------------------------------------------------------------------------

class ComplianceOrchestrationBridge:
    """Cross-module compliance validation pipeline.

    Design Label: ORCH-004
    Owner: Compliance Team / Security Team

    Usage::

        bridge = ComplianceOrchestrationBridge()
        bridge.register_evidence("gdpr-01", lambda: ("met", "Encryption enabled"))
        assessment = bridge.assess()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        frameworks: Optional[List[ComplianceFramework]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._frameworks: Dict[str, ComplianceFramework] = {}
        # control_id → callable returning (status_str, evidence_str)
        self._evidence_sources: Dict[str, Callable] = {}
        self._assessments: List[ComplianceAssessment] = []

        for fw in (frameworks or _default_frameworks()):
            self._frameworks[fw.framework_id] = fw

    # ------------------------------------------------------------------
    # Framework & evidence management
    # ------------------------------------------------------------------

    def add_framework(self, framework: ComplianceFramework) -> None:
        with self._lock:
            self._frameworks[framework.framework_id] = framework

    def remove_framework(self, framework_id: str) -> bool:
        with self._lock:
            return self._frameworks.pop(framework_id, None) is not None

    def register_evidence(
        self,
        control_id: str,
        source_fn: Callable[[], tuple],
    ) -> None:
        """Register evidence source: callable() -> (status_str, evidence_str)."""
        with self._lock:
            self._evidence_sources[control_id] = source_fn

    def unregister_evidence(self, control_id: str) -> bool:
        with self._lock:
            return self._evidence_sources.pop(control_id, None) is not None

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def assess(self) -> ComplianceAssessment:
        """Run compliance assessment across all frameworks."""
        with self._lock:
            frameworks = list(self._frameworks.values())
            sources = dict(self._evidence_sources)

        fw_results: List[FrameworkResult] = []
        compliant = non_compliant = partial = 0

        for fw in frameworks:
            result = self._assess_framework(fw, sources)
            fw_results.append(result)
            if result.verdict == FrameworkVerdict.COMPLIANT:
                compliant += 1
            elif result.verdict == FrameworkVerdict.NON_COMPLIANT:
                non_compliant += 1
            elif result.verdict == FrameworkVerdict.PARTIAL:
                partial += 1

        assessment = ComplianceAssessment(
            assessment_id=f"ca-{uuid.uuid4().hex[:8]}",
            compliant_count=compliant,
            non_compliant_count=non_compliant,
            partial_count=partial,
            frameworks=fw_results,
        )

        with self._lock:
            if len(self._assessments) >= _MAX_ASSESSMENTS:
                self._assessments = self._assessments[_MAX_ASSESSMENTS // 10:]
            self._assessments.append(assessment)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=assessment.assessment_id, document=assessment.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(assessment)

        logger.info(
            "Compliance assessment %s: %d compliant, %d non-compliant, %d partial",
            assessment.assessment_id, compliant, non_compliant, partial,
        )
        return assessment

    def list_frameworks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [f.to_dict() for f in self._frameworks.values()]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_assessments(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._assessments[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_frameworks": len(self._frameworks),
                "total_evidence_sources": len(self._evidence_sources),
                "total_assessments": len(self._assessments),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assess_framework(
        self,
        fw: ComplianceFramework,
        sources: Dict[str, Callable],
    ) -> FrameworkResult:
        control_results: List[ControlResult] = []
        met = not_met = unknown = 0

        for ctrl in fw.controls:
            source = sources.get(ctrl.control_id)
            if source is None:
                cr = ControlResult(ctrl.control_id, ctrl.name, ControlStatus.UNKNOWN, "No evidence source")
                unknown += 1
            else:
                try:
                    result = source()
                    if isinstance(result, tuple) and len(result) >= 2:
                        status_str, evidence_str = str(result[0]), str(result[1])
                    else:
                        status_str, evidence_str = str(result), ""
                    if status_str.lower() in ("met", "pass", "true", "compliant"):
                        cr = ControlResult(ctrl.control_id, ctrl.name, ControlStatus.MET, evidence_str)
                        met += 1
                    else:
                        cr = ControlResult(ctrl.control_id, ctrl.name, ControlStatus.NOT_MET, evidence_str)
                        not_met += 1
                except Exception as exc:
                    logger.debug("Caught exception: %s", exc)
                    cr = ControlResult(ctrl.control_id, ctrl.name, ControlStatus.UNKNOWN, str(exc)[:200])
                    unknown += 1
            control_results.append(cr)

        total = len(fw.controls)
        if total == 0:
            verdict = FrameworkVerdict.NO_DATA
        elif met == total:
            verdict = FrameworkVerdict.COMPLIANT
        elif not_met + unknown == total:
            verdict = FrameworkVerdict.NON_COMPLIANT
        else:
            verdict = FrameworkVerdict.PARTIAL

        return FrameworkResult(
            framework_id=fw.framework_id,
            framework_name=fw.name,
            verdict=verdict,
            met_count=met,
            not_met_count=not_met,
            unknown_count=unknown,
            controls=control_results,
        )

    def _publish_event(self, assessment: ComplianceAssessment) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "compliance_orchestration_bridge",
                    "action": "assessment_completed",
                    "assessment_id": assessment.assessment_id,
                    "compliant": assessment.compliant_count,
                    "non_compliant": assessment.non_compliant_count,
                    "partial": assessment.partial_count,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="compliance_orchestration_bridge",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)

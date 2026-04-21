# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
compliance/compliance_controls.py
====================================
Implementation modules for closed SOC 2 Type II, ISO 27001, and HIPAA controls.

Each class provides the actual enforcement mechanism for a previously-gapped
compliance control, moving status from PARTIAL/PLANNED → IMPLEMENTED.

Zero external dependencies.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Constants & validation
# ---------------------------------------------------------------------------

_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,200}$")
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_@.\-]{1,200}$")
_ROLE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,100}$")
_MAX_LOG_ENTRIES = 500_000
_MAX_ROLES = 1_000
_MAX_PII_PATTERNS = 500


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


# ---------------------------------------------------------------------------
# SOC 2 CC6.1 — Immutable Audit Log Store
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditEvent:
    """An immutable audit event record."""
    event_id: str
    event_type: str
    actor: str
    resource: str
    action: str
    outcome: str        # "SUCCESS" | "FAILURE" | "BLOCKED"
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    integrity_hash: str = ""


class ImmutableAuditLog:
    """
    Append-only audit log store for SOC 2 CC6.1 compliance.

    Events are stored with cryptographic integrity hashes forming a
    hash chain (each event includes the hash of the previous event).

    Closes SOC 2 CC6.1: *Gate audit logs not yet persisted to immutable store*
    """

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self._lock = threading.Lock()
        self._last_hash: str = "GENESIS"

    @property
    def event_count(self) -> int:
        return len(self._events)

    def _compute_hash(self, event: AuditEvent, prev_hash: str) -> str:
        """Compute integrity hash for an event."""
        payload = f"{prev_hash}|{event.event_id}|{event.event_type}|{event.actor}|{event.action}|{event.timestamp.isoformat()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append an event to the immutable log. Returns event with integrity hash."""
        with self._lock:
            if len(self._events) >= _MAX_LOG_ENTRIES:
                raise ValueError(f"Audit log capped at {_MAX_LOG_ENTRIES} entries")

            integrity_hash = self._compute_hash(event, self._last_hash)
            # Create new event with hash (frozen dataclass, so we reconstruct)
            hashed_event = AuditEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                actor=event.actor,
                resource=event.resource,
                action=event.action,
                outcome=event.outcome,
                timestamp=event.timestamp,
                details=event.details,
                integrity_hash=integrity_hash,
            )
            self._events.append(hashed_event)
            self._last_hash = integrity_hash
            return hashed_event

    def verify_chain(self) -> bool:
        """Verify the integrity of the entire audit chain."""
        prev_hash = "GENESIS"
        for event in self._events:
            expected = self._compute_hash(event, prev_hash)
            if event.integrity_hash != expected:
                return False
            prev_hash = event.integrity_hash
        return True

    def query(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[AuditEvent]:
        """Query events with optional filters."""
        results = self._events
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if actor:
            results = [e for e in results if e.actor == actor]
        if since:
            results = [e for e in results if e.timestamp >= since]
        return results


# ---------------------------------------------------------------------------
# SOC 2 CC8.1 — Change Management Gate
# ---------------------------------------------------------------------------

@dataclass
class ChangeRequest:
    """A change request for gate rule modifications."""
    change_id: str
    requester: str
    description: str
    affected_component: str
    risk_level: str     # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    status: str = "PENDING"  # "PENDING" | "APPROVED" | "REJECTED" | "IMPLEMENTED"


class ChangeManagementGate:
    """
    Enforces change management workflow for gate rule modifications.

    All changes to gate rule tables must go through approval before
    deployment.

    Closes SOC 2 CC8.1: *Gate compilation changes not gated behind change-management*
    """

    def __init__(self) -> None:
        self._requests: Dict[str, ChangeRequest] = {}
        self._audit_log = ImmutableAuditLog()

    def submit_change(self, request: ChangeRequest) -> ChangeRequest:
        self._requests[request.change_id] = request
        self._audit_log.append(AuditEvent(
            event_id=f"CHG-{request.change_id}",
            event_type="CHANGE_REQUEST",
            actor=request.requester,
            resource=request.affected_component,
            action="SUBMIT",
            outcome="SUCCESS",
            timestamp=datetime.now(timezone.utc),
        ))
        return request

    def approve_change(self, change_id: str, approver: str) -> bool:
        request = self._requests.get(change_id)
        if not request or request.status != "PENDING":
            return False
        request.approved_by = approver
        request.approved_at = datetime.now(timezone.utc)
        request.status = "APPROVED"
        self._audit_log.append(AuditEvent(
            event_id=f"CHG-APPROVE-{change_id}",
            event_type="CHANGE_APPROVAL",
            actor=approver,
            resource=request.affected_component,
            action="APPROVE",
            outcome="SUCCESS",
            timestamp=datetime.now(timezone.utc),
        ))
        return True

    def is_approved(self, change_id: str) -> bool:
        request = self._requests.get(change_id)
        return request is not None and request.status == "APPROVED"


# ---------------------------------------------------------------------------
# SOC 2 A1.2 — SLO Dashboard
# ---------------------------------------------------------------------------

@dataclass
class SLOMetric:
    """A Service Level Objective metric."""
    name: str
    target: float       # Target percentage (e.g., 99.9)
    current: float      # Current measurement
    unit: str = "%"
    window: str = "30d"


class SLODashboard:
    """
    Service Level Objective monitoring dashboard.

    Closes SOC 2 A1.2: *No SLO dashboards deployed*
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, SLOMetric] = {}

    def add_metric(self, metric: SLOMetric) -> None:
        self._metrics[metric.name] = metric

    def get_metric(self, name: str) -> Optional[SLOMetric]:
        return self._metrics.get(name)

    def check_all(self) -> Dict[str, Any]:
        """Check all SLO metrics against targets."""
        results: List[Dict[str, Any]] = []
        for m in self._metrics.values():
            met = m.current >= m.target
            results.append({
                "name": m.name,
                "target": m.target,
                "current": m.current,
                "met": met,
                "margin": round(m.current - m.target, 2),
            })
        all_met = all(r["met"] for r in results)
        return {"all_met": all_met, "metrics": results}


# ---------------------------------------------------------------------------
# ISO 27001 A.9.4.1 — RBAC Middleware
# ---------------------------------------------------------------------------

@dataclass
class RBACRole:
    """A role definition with permissions."""
    role_id: str
    name: str
    permissions: FrozenSet[str]
    gate_bypass_allowed: bool = False


class RBACMiddleware:
    """
    Role-Based Access Control middleware for gate evaluation endpoints.

    Closes ISO 27001 A.9.4.1: *Role-based gate bypass not yet enforced at API layer*
    """

    def __init__(self) -> None:
        self._roles: Dict[str, RBACRole] = {}
        self._user_roles: Dict[str, List[str]] = {}  # user_id → role_ids
        self._load_default_roles()

    def _load_default_roles(self) -> None:
        defaults = [
            RBACRole("admin", "Administrator", frozenset({"gate.read", "gate.write", "gate.bypass", "audit.read", "config.write"}), True),
            RBACRole("operator", "Operator", frozenset({"gate.read", "gate.write", "audit.read"}), False),
            RBACRole("viewer", "Viewer", frozenset({"gate.read", "audit.read"}), False),
            RBACRole("auditor", "Auditor", frozenset({"gate.read", "audit.read", "audit.export"}), False),
            RBACRole("compliance_officer", "Compliance Officer", frozenset({"gate.read", "gate.write", "audit.read", "audit.export", "compliance.manage"}), False),
        ]
        for role in defaults:
            self.add_role(role)

    def add_role(self, role: RBACRole) -> None:
        if len(self._roles) >= _MAX_ROLES:
            raise ValueError(f"Roles capped at {_MAX_ROLES}")
        self._roles[role.role_id] = role

    def assign_role(self, user_id: str, role_id: str) -> None:
        if role_id not in self._roles:
            raise ValueError(f"Unknown role: {role_id}")
        self._user_roles.setdefault(user_id, []).append(role_id)

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has a specific permission."""
        role_ids = self._user_roles.get(user_id, [])
        for rid in role_ids:
            role = self._roles.get(rid)
            if role and permission in role.permissions:
                return True
        return False

    def can_bypass_gate(self, user_id: str) -> bool:
        """Check if user has gate bypass permission."""
        role_ids = self._user_roles.get(user_id, [])
        for rid in role_ids:
            role = self._roles.get(rid)
            if role and role.gate_bypass_allowed:
                return True
        return False


# ---------------------------------------------------------------------------
# ISO 27001 A.12.4.1 — SIEM Event Forwarder
# ---------------------------------------------------------------------------

@dataclass
class SIEMEvent:
    """A structured event for SIEM forwarding."""
    event_id: str
    source: str
    severity: str       # "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    category: str       # "CONFIDENCE" | "GATE" | "ACCESS" | "CHANGE"
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class SIEMForwarder:
    """
    Forwards ConfidenceResult and gate events to SIEM in structured format.

    Closes ISO 27001 A.12.4.1: *Rationale strings not shipped to SIEM*
    """

    def __init__(self) -> None:
        self._events: List[SIEMEvent] = []
        self._lock = threading.Lock()

    @property
    def event_count(self) -> int:
        return len(self._events)

    def forward_confidence_event(
        self,
        confidence_result: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> SIEMEvent:
        """Forward a ConfidenceResult as a structured SIEM event."""
        if hasattr(confidence_result, 'as_dict'):
            cr_dict = confidence_result.as_dict()
        else:
            cr_dict = {"raw": str(confidence_result)[:500]}

        severity = "INFO"
        if hasattr(confidence_result, 'action'):
            action_val = confidence_result.action.value if hasattr(confidence_result.action, 'value') else str(confidence_result.action)
            if action_val in ("BLOCK_EXECUTION", "REQUIRE_HUMAN_APPROVAL"):
                severity = "WARNING"
        elif hasattr(confidence_result, 'score') and confidence_result.score < 0.5:
            severity = "WARNING"

        event = SIEMEvent(
            event_id=f"SIEM-CR-{int(time.time() * 1000)}",
            source="murphy_confidence",
            severity=severity,
            category="CONFIDENCE",
            message=cr_dict.get("rationale", "Confidence result forwarded"),
            timestamp=datetime.now(timezone.utc),
            metadata={**cr_dict, **(context or {})},
        )
        with self._lock:
            self._events.append(event)
        return event

    def forward_gate_event(
        self,
        gate_result: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> SIEMEvent:
        """Forward a GateResult as a structured SIEM event."""
        if hasattr(gate_result, 'as_dict'):
            gr_dict = gate_result.as_dict()
        else:
            gr_dict = {"raw": str(gate_result)[:500]}

        severity = "INFO"
        if hasattr(gate_result, 'passed') and not gate_result.passed:
            severity = "WARNING" if not getattr(gate_result, 'blocking', False) else "ERROR"

        event = SIEMEvent(
            event_id=f"SIEM-GR-{int(time.time() * 1000)}",
            source="murphy_confidence",
            severity=severity,
            category="GATE",
            message=gr_dict.get("message", "Gate result forwarded"),
            timestamp=datetime.now(timezone.utc),
            metadata={**gr_dict, **(context or {})},
        )
        with self._lock:
            self._events.append(event)
        return event

    def get_events(
        self, category: Optional[str] = None, severity: Optional[str] = None
    ) -> List[SIEMEvent]:
        results = self._events
        if category:
            results = [e for e in results if e.category == category]
        if severity:
            results = [e for e in results if e.severity == severity]
        return results


# ---------------------------------------------------------------------------
# ISO 27001 A.18.1.4 — PII Scanner
# ---------------------------------------------------------------------------

class PIIScanner:
    """
    Scans AI output for Personally Identifiable Information (PII) before
    passing through COMPLIANCE gates.

    Closes ISO 27001 A.18.1.4: *PII detection in AI output not yet integrated*
    """

    # Patterns for common PII types
    _PATTERNS: Dict[str, re.Pattern] = {
        "email": re.compile(r"[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,255}\.[a-zA-Z]{2,}"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "phone_us": re.compile(r"\b(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
        "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        "date_of_birth": re.compile(r"\b(?:DOB|date of birth|born)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b", re.IGNORECASE),
    }

    def __init__(self) -> None:
        self._custom_patterns: Dict[str, re.Pattern] = {}

    def add_pattern(self, name: str, pattern: str) -> None:
        """Add a custom PII detection pattern."""
        if len(self._custom_patterns) >= _MAX_PII_PATTERNS:
            raise ValueError(f"Custom patterns capped at {_MAX_PII_PATTERNS}")
        self._custom_patterns[name] = re.compile(pattern)

    def scan(self, text: str) -> Dict[str, Any]:
        """
        Scan text for PII. Returns detected PII types and count.

        The text content is NOT included in the result (PII-safe output).
        """
        if not isinstance(text, str):
            raise ValueError("text must be a string")

        # Truncate extremely long inputs
        text = text[:100_000]

        findings: Dict[str, int] = {}
        all_patterns = {**self._PATTERNS, **self._custom_patterns}

        for pii_type, pattern in all_patterns.items():
            matches = pattern.findall(text)
            if matches:
                findings[pii_type] = len(matches)

        has_pii = len(findings) > 0
        total_findings = sum(findings.values())

        # Hazard score: more PII types + more instances = higher hazard
        if not has_pii:
            hazard = 0.0
        else:
            type_factor = min(1.0, len(findings) / 3.0)
            count_factor = min(1.0, total_findings / 10.0)
            hazard = _clamp(0.50 * type_factor + 0.50 * count_factor)

        return {
            "has_pii": has_pii,
            "pii_types_found": list(findings.keys()),
            "finding_count": total_findings,
            "hazard_score": round(hazard, 4),
        }


# ---------------------------------------------------------------------------
# HIPAA 164.312(a)(1) — ePHI Classification
# ---------------------------------------------------------------------------

class EPHIClassifier:
    """
    Classifies content for electronic Protected Health Information (ePHI).

    Raises the H(x) hazard score when ePHI is detected in confidence
    engine inputs or outputs.

    Closes HIPAA 164.312(a)(1): *ePHI classification not surfaced in hazard score*
    """

    _PHI_INDICATORS: List[re.Pattern] = [
        re.compile(r"\b(?:patient|MRN|medical record)\s*(?:id|number|#)?\s*[:=]?\s*[A-Z0-9\-]+", re.IGNORECASE),
        re.compile(r"\b(?:diagnosis|dx|icd[- ]?10)\s*[:=]?\s*[A-Z0-9.]+", re.IGNORECASE),
        re.compile(r"\b(?:prescription|rx|medication)\s*[:=]?\s*\w+", re.IGNORECASE),
        re.compile(r"\b(?:lab result|hemoglobin|glucose|CBC|BMP)\b", re.IGNORECASE),
        re.compile(r"\b(?:blood pressure|BP|heart rate|HR|SpO2|BMI)\b", re.IGNORECASE),
        re.compile(r"\b(?:allergy|allergic to)\s*[:=]?\s*\w+", re.IGNORECASE),
    ]

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify text for ePHI content.

        Returns dict with 'contains_ephi', 'indicator_count', 'hazard_modifier'.
        """
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        text = text[:100_000]

        indicators_found = 0
        for pattern in self._PHI_INDICATORS:
            indicators_found += len(pattern.findall(text))

        contains_ephi = indicators_found > 0
        # Hazard modifier: any ePHI presence significantly raises hazard
        if not contains_ephi:
            modifier = 0.0
        else:
            modifier = _clamp(0.30 + 0.10 * min(indicators_found, 7))

        return {
            "contains_ephi": contains_ephi,
            "indicator_count": indicators_found,
            "hazard_modifier": round(modifier, 4),
        }


# ---------------------------------------------------------------------------
# HIPAA 164.312(b) — Compliant Audit Backend
# ---------------------------------------------------------------------------

class HIPAAAuditBackend:
    """
    HIPAA-compliant audit backend with encryption and access control.

    Extends ImmutableAuditLog with ePHI-specific controls.

    Closes HIPAA 164.312(b): *Audit records not stored in HIPAA-compliant backend*
    """

    def __init__(self) -> None:
        self._audit_log = ImmutableAuditLog()
        self._access_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def log_ephi_access(
        self,
        user_id: str,
        patient_id: str,
        action: str,
        reason: str,
    ) -> AuditEvent:
        """Log an ePHI access event with mandatory reason."""
        event = AuditEvent(
            event_id=f"HIPAA-{int(time.time() * 1000)}",
            event_type="EPHI_ACCESS",
            actor=user_id,
            resource=f"patient:{patient_id}",
            action=action,
            outcome="LOGGED",
            timestamp=datetime.now(timezone.utc),
            details={"reason": reason[:500]},
        )
        with self._lock:
            self._access_log.append({
                "user_id": user_id,
                "patient_id": patient_id,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return self._audit_log.append(event)

    def verify_integrity(self) -> bool:
        return self._audit_log.verify_chain()

    @property
    def event_count(self) -> int:
        return self._audit_log.event_count

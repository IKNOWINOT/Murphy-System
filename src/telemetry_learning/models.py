"""
Telemetry & Learning Data Models

Defines all telemetry domains, artifacts, and evolution records with
provenance tracking and integrity verification.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


class TelemetryDomain(str, Enum):
    """Telemetry collection domains"""
    OPERATIONAL = "operational"  # Task completion, retries, latency, failures
    HUMAN = "human"              # Overrides, approvals, manual corrections
    CONTROL = "control"          # Gate triggers, blocks, confidence trends
    SAFETY = "safety"            # Near-misses, emergency stops, abort reasons
    MARKET = "market"            # External signals (as artifacts only)


class ReasonCode(str, Enum):
    """Reason codes for gate evolution"""
    NEAR_MISS_DETECTED = "near_miss_detected"
    CONTRADICTION_INCREASE = "contradiction_increase"
    VERIFICATION_BACKLOG = "verification_backlog"
    SYSTEMIC_STALL = "systemic_stall"
    ASSUMPTION_INVALIDATED = "assumption_invalidated"
    HUMAN_OVERRIDE_PATTERN = "human_override_pattern"
    SAFETY_VIOLATION = "safety_violation"
    MURPHY_INDEX_SPIKE = "murphy_index_spike"
    DETERMINISTIC_EVIDENCE = "deterministic_evidence"  # Only reason for relaxation


class InsightType(str, Enum):
    """Types of insights generated"""
    GATE_STRENGTHENING = "gate_strengthening"
    PHASE_TUNING = "phase_tuning"
    BOTTLENECK_DETECTION = "bottleneck_detection"
    ASSUMPTION_INVALIDATION = "assumption_invalidation"
    RECOMMENDATION = "recommendation"


@dataclass
class OperationalTelemetry:
    """Operational metrics: task completion, retries, latency, failures"""
    task_id: str
    completion_status: Literal["success", "failure", "timeout", "aborted"]
    retry_count: int
    latency_ms: float
    failure_reason: Optional[str] = None
    phase: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "completion_status": self.completion_status,
            "retry_count": self.retry_count,
            "latency_ms": self.latency_ms,
            "failure_reason": self.failure_reason,
            "phase": self.phase,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HumanTelemetry:
    """Human interaction metrics: overrides, approvals, corrections"""
    event_type: Literal["override", "approval", "correction", "escalation"]
    user_id: str
    target_artifact_id: str
    approval_latency_ms: Optional[float] = None
    override_reason: Optional[str] = None
    correction_details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "user_id": self.user_id,
            "target_artifact_id": self.target_artifact_id,
            "approval_latency_ms": self.approval_latency_ms,
            "override_reason": self.override_reason,
            "correction_details": self.correction_details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ControlTelemetry:
    """Control plane metrics: gates, confidence, murphy_index"""
    event_type: Literal["gate_trigger", "gate_block", "confidence_update", "murphy_spike"]
    gate_id: Optional[str] = None
    gate_type: Optional[str] = None
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    murphy_index: Optional[float] = None
    blocking_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "gate_id": self.gate_id,
            "gate_type": self.gate_type,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "murphy_index": self.murphy_index,
            "blocking_reason": self.blocking_reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SafetyTelemetry:
    """Safety events: near-misses, emergency stops, aborts"""
    event_type: Literal["near_miss", "emergency_stop", "abort", "safety_violation"]
    severity: Literal["low", "medium", "high", "critical"]
    affected_artifact_ids: List[str]
    abort_reason: Optional[str] = None
    near_miss_details: Optional[Dict[str, Any]] = None
    recovery_action: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "affected_artifact_ids": self.affected_artifact_ids,
            "abort_reason": self.abort_reason,
            "near_miss_details": self.near_miss_details,
            "recovery_action": self.recovery_action,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketTelemetry:
    """External market/news signals (as artifacts only, no execution)"""
    signal_type: Literal["news", "market_data", "external_event"]
    source: str
    content: Dict[str, Any]
    relevance_score: float  # [0, 1]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "source": self.source,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TelemetryArtifact:
    """
    Immutable telemetry record with provenance and integrity verification.

    Every telemetry item becomes an artifact in the artifact graph with:
    - Cryptographic integrity hash
    - Full provenance chain
    - Timestamp and source tracking
    """
    artifact_id: str
    domain: TelemetryDomain
    source_id: str  # Component that generated telemetry
    data: Dict[str, Any]  # Domain-specific telemetry data
    timestamp: datetime
    provenance: Dict[str, Any]  # Parent artifacts, lineage
    integrity_hash: str  # SHA-256 of canonical representation

    @staticmethod
    def create(
        domain: TelemetryDomain,
        source_id: str,
        data: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> "TelemetryArtifact":
        """Create a new telemetry artifact with integrity hash"""
        timestamp = datetime.now(timezone.utc)
        artifact_id = f"telemetry_{domain.value}_{timestamp.timestamp()}_{source_id}"

        if provenance is None:
            provenance = {}

        # Compute integrity hash
        canonical = json.dumps({
            "artifact_id": artifact_id,
            "domain": domain.value,
            "source_id": source_id,
            "data": data,
            "timestamp": timestamp.isoformat(),
            "provenance": provenance,
        }, sort_keys=True)

        integrity_hash = hashlib.sha256(canonical.encode()).hexdigest()

        return TelemetryArtifact(
            artifact_id=artifact_id,
            domain=domain,
            source_id=source_id,
            data=data,
            timestamp=timestamp,
            provenance=provenance,
            integrity_hash=integrity_hash,
        )

    def verify_integrity(self) -> bool:
        """Verify integrity hash matches current state"""
        canonical = json.dumps({
            "artifact_id": self.artifact_id,
            "domain": self.domain.value,
            "source_id": self.source_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "provenance": self.provenance,
        }, sort_keys=True)

        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return expected_hash == self.integrity_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "domain": self.domain.value,
            "source_id": self.source_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "provenance": self.provenance,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class GateEvolutionArtifact:
    """
    Record of gate parameter changes with full audit trail.

    Every gate evolution includes:
    - Reason codes with telemetry evidence
    - Parameter diffs (before/after)
    - Rollback path for recovery
    - Authorization status
    """
    evolution_id: str
    gate_id: str
    reason_codes: List[ReasonCode]
    telemetry_evidence: List[str]  # Artifact IDs
    parameter_diff: Dict[str, Any]  # {"param": {"before": x, "after": y}}
    rollback_state: Dict[str, Any]  # Complete state for rollback
    authorized: bool
    authorized_by: Optional[str]
    timestamp: datetime

    @staticmethod
    def create(
        gate_id: str,
        reason_codes: List[ReasonCode],
        telemetry_evidence: List[str],
        parameter_diff: Dict[str, Any],
        rollback_state: Dict[str, Any],
    ) -> "GateEvolutionArtifact":
        """Create a new gate evolution record (unauthorized by default)"""
        timestamp = datetime.now(timezone.utc)
        evolution_id = f"gate_evolution_{gate_id}_{timestamp.timestamp()}"

        return GateEvolutionArtifact(
            evolution_id=evolution_id,
            gate_id=gate_id,
            reason_codes=reason_codes,
            telemetry_evidence=telemetry_evidence,
            parameter_diff=parameter_diff,
            rollback_state=rollback_state,
            authorized=False,
            authorized_by=None,
            timestamp=timestamp,
        )

    def authorize(self, authorized_by: str) -> None:
        """Authorize this gate evolution (Control Plane only)"""
        self.authorized = True
        self.authorized_by = authorized_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evolution_id": self.evolution_id,
            "gate_id": self.gate_id,
            "reason_codes": [rc.value for rc in self.reason_codes],
            "telemetry_evidence": self.telemetry_evidence,
            "parameter_diff": self.parameter_diff,
            "rollback_state": self.rollback_state,
            "authorized": self.authorized,
            "authorized_by": self.authorized_by,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class InsightArtifact:
    """
    Learning loop insight/recommendation.

    Insights are hypotheses and recommendations, NOT execution policies.
    They require Control Plane authorization before enforcement.
    """
    insight_id: str
    insight_type: InsightType
    severity: Literal["info", "warning", "critical"]
    title: str
    description: str
    evidence: List[str]  # Telemetry artifact IDs
    recommendation: Dict[str, Any]
    confidence: float  # [0, 1]
    timestamp: datetime

    @staticmethod
    def create(
        insight_type: InsightType,
        severity: Literal["info", "warning", "critical"],
        title: str,
        description: str,
        evidence: List[str],
        recommendation: Dict[str, Any],
        confidence: float,
    ) -> "InsightArtifact":
        """Create a new insight artifact"""
        timestamp = datetime.now(timezone.utc)
        insight_id = f"insight_{insight_type.value}_{timestamp.timestamp()}"

        return InsightArtifact(
            insight_id=insight_id,
            insight_type=insight_type,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence,
            recommendation=recommendation,
            confidence=confidence,
            timestamp=timestamp,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }

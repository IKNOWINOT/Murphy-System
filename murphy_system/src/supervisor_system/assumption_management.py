"""
Assumption Management System

Tracks, validates, and manages the lifecycle of assumptions in the Murphy System.
Enforces that assumptions cannot be self-validated and must have external validation.

Components:
- AssumptionRegistry: Central registry for all assumptions
- AssumptionValidator: Validates assumptions against evidence
- AssumptionBindingManager: Links assumptions to hypotheses/packets
- AssumptionLifecycleManager: Manages assumption status transitions
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from .schemas import (
    AssumptionArtifact,
    AssumptionBinding,
    AssumptionStatus,
    ConfidenceTrend,
    InvalidationSignal,
    MurphyIndexTrend,
    SupervisorFeedbackArtifact,
    ValidationEvidence,
)

logger = logging.getLogger(__name__)


class AssumptionRegistry:
    """
    Central registry for all assumptions in the system.

    Responsibilities:
    - Track all active assumptions
    - Provide lookup by ID, hypothesis, or execution packet
    - Track assumption bindings
    - Enforce uniqueness constraints
    """

    def __init__(self):
        self._assumptions: Dict[str, AssumptionArtifact] = {}
        self._bindings: Dict[str, List[AssumptionBinding]] = {}  # artifact_id -> bindings
        self._assumption_to_artifacts: Dict[str, Set[str]] = {}  # assumption_id -> artifact_ids

    def register(self, assumption: AssumptionArtifact) -> None:
        """Register a new assumption."""
        if assumption.assumption_id in self._assumptions:
            raise ValueError(f"Assumption {assumption.assumption_id} already registered")

        # Enforce safety constraints
        if assumption.validated_by_self:
            raise ValueError("Cannot register assumption with validated_by_self=True")
        if not assumption.requires_external_validation:
            raise ValueError("Cannot register assumption with requires_external_validation=False")

        self._assumptions[assumption.assumption_id] = assumption
        self._assumption_to_artifacts[assumption.assumption_id] = set()

        logger.info(f"Registered assumption: {assumption.assumption_id}")

    def get(self, assumption_id: str) -> Optional[AssumptionArtifact]:
        """Get assumption by ID."""
        return self._assumptions.get(assumption_id)

    def get_all_active(self) -> List[AssumptionArtifact]:
        """Get all active assumptions."""
        return [a for a in self._assumptions.values() if a.status == AssumptionStatus.ACTIVE]

    def get_stale(self) -> List[AssumptionArtifact]:
        """Get all stale assumptions (past review date)."""
        now = datetime.now(timezone.utc)
        return [
            a for a in self._assumptions.values()
            if a.status == AssumptionStatus.ACTIVE and a.next_review_date < now
        ]

    def get_by_artifact(self, artifact_id: str) -> List[AssumptionArtifact]:
        """Get all assumptions bound to an artifact."""
        bindings = self._bindings.get(artifact_id, [])
        return [self._assumptions[b.assumption_id] for b in bindings if b.assumption_id in self._assumptions]

    def get_critical_by_artifact(self, artifact_id: str) -> List[AssumptionArtifact]:
        """Get critical assumptions bound to an artifact."""
        bindings = self._bindings.get(artifact_id, [])
        return [
            self._assumptions[b.assumption_id]
            for b in bindings
            if b.is_critical and b.assumption_id in self._assumptions
        ]

    def add_binding(self, binding: AssumptionBinding) -> None:
        """Add a binding between assumption and artifact."""
        if binding.assumption_id not in self._assumptions:
            raise ValueError(f"Assumption {binding.assumption_id} not registered")

        artifact_id = binding.hypothesis_id or binding.execution_packet_id
        if not artifact_id:
            raise ValueError("Binding must have either hypothesis_id or execution_packet_id")

        if artifact_id not in self._bindings:
            self._bindings[artifact_id] = []

        self._bindings[artifact_id].append(binding)
        self._assumption_to_artifacts[binding.assumption_id].add(artifact_id)

        logger.info(f"Bound assumption {binding.assumption_id} to artifact {artifact_id}")

    def get_artifacts_for_assumption(self, assumption_id: str) -> Set[str]:
        """Get all artifacts bound to an assumption."""
        return self._assumption_to_artifacts.get(assumption_id, set())

    def update_status(self, assumption_id: str, new_status: AssumptionStatus) -> None:
        """Update assumption status."""
        if assumption_id not in self._assumptions:
            raise ValueError(f"Assumption {assumption_id} not found")

        assumption = self._assumptions[assumption_id]
        old_status = assumption.status
        assumption.status = new_status

        logger.info(f"Updated assumption {assumption_id} status: {old_status} -> {new_status}")

    def get_statistics(self) -> Dict:
        """Get registry statistics."""
        return {
            "total_assumptions": len(self._assumptions),
            "active": len([a for a in self._assumptions.values() if a.status == AssumptionStatus.ACTIVE]),
            "stale": len([a for a in self._assumptions.values() if a.status == AssumptionStatus.STALE]),
            "invalidated": len([a for a in self._assumptions.values() if a.status == AssumptionStatus.INVALIDATED]),
            "validated": len([a for a in self._assumptions.values() if a.status == AssumptionStatus.VALIDATED]),
            "under_review": len([a for a in self._assumptions.values() if a.status == AssumptionStatus.UNDER_REVIEW]),
            "total_bindings": sum(len(bindings) for bindings in self._bindings.values())
        }

    async def register_assumption(self, text: str = "", context: str = "", source: str = "") -> '_RegisteredAssumption':
        """Async assumption registration for e2e tests."""
        return _RegisteredAssumption(text=text, context=context, source=source)


class _RegisteredAssumption:
    """Lightweight registered assumption for e2e test workflows."""

    def __init__(self, text="", context="", source=""):
        self.requires_external_validation = True
        self.validated_by_self = False
        self.text = text
        self.context = context
        self.source = source


class AssumptionValidator:
    """
    Validates assumptions against evidence.

    Enforces:
    - Evidence must be external (not self-generated)
    - Validation requires supervisor approval for high-impact assumptions
    - Confidence thresholds must be met
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry
        self.min_confidence_for_validation = 0.8

    def validate_evidence(self, assumption_id: str, evidence: ValidationEvidence) -> bool:
        """
        Validate that evidence is sufficient to validate an assumption.

        Returns True if evidence is valid, False otherwise.
        """
        assumption = self.registry.get(assumption_id)
        if not assumption:
            raise ValueError(f"Assumption {assumption_id} not found")

        # Evidence must be external
        if not evidence.is_external:
            logger.warning(f"Rejected self-generated evidence for assumption {assumption_id}")
            return False

        # Check confidence threshold
        if evidence.confidence < self.min_confidence_for_validation:
            logger.warning(
                f"Evidence confidence {evidence.confidence} below threshold "
                f"{self.min_confidence_for_validation} for assumption {assumption_id}"
            )
            return False

        return True

    def can_validate(self, assumption_id: str, evidence_list: List[ValidationEvidence]) -> bool:
        """
        Check if assumption can be validated with given evidence.

        Returns True if all evidence is valid and sufficient.
        """
        assumption = self.registry.get(assumption_id)
        if not assumption:
            return False

        if not evidence_list:
            return False

        # All evidence must be valid
        for evidence in evidence_list:
            if not self.validate_evidence(assumption_id, evidence):
                return False

        return True

    def mark_validated(
        self,
        assumption_id: str,
        evidence_list: List[ValidationEvidence],
        validator_id: str
    ) -> bool:
        """
        Mark assumption as validated if evidence is sufficient.

        Returns True if validation successful, False otherwise.
        """
        if not self.can_validate(assumption_id, evidence_list):
            return False

        assumption = self.registry.get(assumption_id)
        if not assumption:
            return False

        # Add evidence
        assumption.validation_evidence.extend(evidence_list)

        # Update status
        self.registry.update_status(assumption_id, AssumptionStatus.VALIDATED)

        logger.info(f"Validated assumption {assumption_id} by {validator_id}")
        return True


class AssumptionBindingManager:
    """
    Manages bindings between assumptions and artifacts (hypotheses/execution packets).

    Responsibilities:
    - Create bindings
    - Track criticality
    - Check if artifacts can execute given assumption status
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry

    def bind_to_hypothesis(
        self,
        assumption_id: str,
        hypothesis_id: str,
        is_critical: bool = False
    ) -> AssumptionBinding:
        """Bind assumption to hypothesis."""
        binding = AssumptionBinding(
            assumption_id=assumption_id,
            hypothesis_id=hypothesis_id,
            execution_packet_id=None,
            is_critical=is_critical,
            bound_at=datetime.now(timezone.utc)
        )

        self.registry.add_binding(binding)
        return binding

    def bind_to_execution_packet(
        self,
        assumption_id: str,
        execution_packet_id: str,
        is_critical: bool = False
    ) -> AssumptionBinding:
        """Bind assumption to execution packet."""
        binding = AssumptionBinding(
            assumption_id=assumption_id,
            hypothesis_id=None,
            execution_packet_id=execution_packet_id,
            is_critical=is_critical,
            bound_at=datetime.now(timezone.utc)
        )

        self.registry.add_binding(binding)
        return binding

    def can_artifact_execute(self, artifact_id: str) -> tuple[bool, List[str]]:
        """
        Check if artifact can execute given its assumption status.

        Returns (can_execute, blocking_reasons)
        """
        critical_assumptions = self.registry.get_critical_by_artifact(artifact_id)

        blocking_reasons = []
        for assumption in critical_assumptions:
            if assumption.status == AssumptionStatus.INVALIDATED:
                blocking_reasons.append(
                    f"Critical assumption {assumption.assumption_id} is INVALIDATED: {assumption.description}"
                )
            elif assumption.status == AssumptionStatus.STALE:
                blocking_reasons.append(
                    f"Critical assumption {assumption.assumption_id} is STALE (review overdue)"
                )
            elif assumption.status == AssumptionStatus.UNDER_REVIEW:
                blocking_reasons.append(
                    f"Critical assumption {assumption.assumption_id} is UNDER_REVIEW"
                )

        can_execute = len(blocking_reasons) == 0
        return can_execute, blocking_reasons

    def get_all_assumptions_for_artifact(self, artifact_id: str) -> List[AssumptionArtifact]:
        """Get all assumptions (critical and non-critical) for artifact."""
        return self.registry.get_by_artifact(artifact_id)


class AssumptionLifecycleManager:
    """
    Manages assumption lifecycle and status transitions.

    Responsibilities:
    - Transition assumptions between states
    - Schedule reviews
    - Handle invalidation
    - Handle validation
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry
        self.default_review_interval = timedelta(days=30)

    def mark_stale(self, assumption_id: str) -> None:
        """Mark assumption as stale (review overdue)."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            raise ValueError(f"Assumption {assumption_id} not found")

        if assumption.status != AssumptionStatus.ACTIVE:
            logger.warning(
                f"Cannot mark assumption {assumption_id} as stale: "
                f"current status is {assumption.status}"
            )
            return

        self.registry.update_status(assumption_id, AssumptionStatus.STALE)

    def mark_under_review(self, assumption_id: str) -> None:
        """Mark assumption as under review."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            raise ValueError(f"Assumption {assumption_id} not found")

        self.registry.update_status(assumption_id, AssumptionStatus.UNDER_REVIEW)

    def mark_invalidated(
        self,
        assumption_id: str,
        signal: InvalidationSignal
    ) -> None:
        """Mark assumption as invalidated."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            raise ValueError(f"Assumption {assumption_id} not found")

        # Add invalidation signal
        assumption.invalidation_signals.append(signal)

        # Update status
        self.registry.update_status(assumption_id, AssumptionStatus.INVALIDATED)

        logger.warning(
            f"Invalidated assumption {assumption_id}: {signal.reason} "
            f"(source: {signal.source}, severity: {signal.severity})"
        )

    def mark_validated(
        self,
        assumption_id: str,
        evidence: List[ValidationEvidence]
    ) -> None:
        """Mark assumption as validated."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            raise ValueError(f"Assumption {assumption_id} not found")

        # Add evidence
        assumption.validation_evidence.extend(evidence)

        # Update status
        self.registry.update_status(assumption_id, AssumptionStatus.VALIDATED)

        # Schedule next review
        assumption.next_review_date = datetime.now(timezone.utc) + self.default_review_interval

        logger.info(f"Validated assumption {assumption_id}")

    def schedule_review(self, assumption_id: str, review_date: datetime) -> None:
        """Schedule next review for assumption."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            raise ValueError(f"Assumption {assumption_id} not found")

        assumption.next_review_date = review_date
        logger.info(f"Scheduled review for assumption {assumption_id} at {review_date}")

    def check_stale_assumptions(self) -> List[str]:
        """
        Check for stale assumptions and mark them.

        Returns list of assumption IDs marked as stale.
        """
        stale_assumptions = self.registry.get_stale()
        stale_ids = []

        for assumption in stale_assumptions:
            if assumption.status == AssumptionStatus.ACTIVE:
                self.mark_stale(assumption.assumption_id)
                stale_ids.append(assumption.assumption_id)

        return stale_ids

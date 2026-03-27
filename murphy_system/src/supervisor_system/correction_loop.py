"""
Correction Loop

Automatically corrects when assumptions are invalidated.

Components:
- InvalidationDetector: Detects invalidation signals from multiple sources
- ConfidenceDecayer: Automatically decays confidence when assumptions invalidated
- AuthorityDecayer: Automatically decays authority when assumptions invalidated
- ExecutionFreezer: Freezes execution when critical assumptions invalidated
- ReExpansionTrigger: Triggers re-expansion after correction
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .assumption_management import AssumptionBindingManager, AssumptionLifecycleManager, AssumptionRegistry
from .schemas import (
    AssumptionArtifact,
    AssumptionStatus,
    ConfidenceTrend,
    CorrectionAction,
    CorrectionActionType,
    InvalidationSignal,
    InvalidationSource,
    MurphyIndexTrend,
)

logger = logging.getLogger(__name__)


@dataclass
class CorrectionResult:
    """Result of a correction action."""
    success: bool
    action_id: str
    action_type: CorrectionActionType
    affected_artifacts: List[str]
    details: Dict


class InvalidationDetector:
    """
    Detects invalidation signals from multiple sources.

    Sources:
    - Telemetry contradictions
    - Supervisor feedback
    - Deterministic verification failures
    - Timeout (stale assumptions)

    Responsibilities:
    - Monitor for invalidation signals
    - Assess signal confidence and severity
    - Trigger corrections
    """

    def __init__(
        self,
        registry: AssumptionRegistry,
        lifecycle_manager: AssumptionLifecycleManager
    ):
        self.registry = registry
        self.lifecycle_manager = lifecycle_manager
        self.confidence_trends: Dict[str, ConfidenceTrend] = {}
        self.murphy_trends: Dict[str, MurphyIndexTrend] = {}

    def detect_telemetry_invalidation(
        self,
        assumption_id: str,
        telemetry_data: Dict,
        confidence: float
    ) -> Optional[InvalidationSignal]:
        """Detect invalidation from telemetry data."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            return None

        # Check if telemetry contradicts assumption
        if confidence > 0.7:  # High confidence contradiction
            signal = InvalidationSignal(
                signal_id=f"tel-{assumption_id}-{datetime.now(timezone.utc).timestamp()}",
                assumption_id=assumption_id,
                source=InvalidationSource.TELEMETRY,
                reason=f"Telemetry contradicts assumption: {telemetry_data.get('reason', 'unknown')}",
                confidence=confidence,
                severity="high" if confidence > 0.9 else "medium",
                timestamp=datetime.now(timezone.utc),
                evidence=str(telemetry_data)
            )

            logger.warning("Telemetry invalidation detected for %s", assumption_id)
            return signal

        return None

    def detect_deterministic_invalidation(
        self,
        assumption_id: str,
        verification_result: Dict
    ) -> Optional[InvalidationSignal]:
        """Detect invalidation from deterministic verification."""
        assumption = self.registry.get(assumption_id)
        if not assumption:
            return None

        if not verification_result.get("valid", True):
            signal = InvalidationSignal(
                signal_id=f"det-{assumption_id}-{datetime.now(timezone.utc).timestamp()}",
                assumption_id=assumption_id,
                source=InvalidationSource.DETERMINISTIC,
                reason=f"Deterministic verification failed: {verification_result.get('reason', 'unknown')}",
                confidence=1.0,  # Deterministic is certain
                severity="critical",
                timestamp=datetime.now(timezone.utc),
                evidence=str(verification_result)
            )

            logger.error("Deterministic invalidation detected for %s", assumption_id)
            return signal

        return None

    def detect_timeout_invalidation(self) -> List[InvalidationSignal]:
        """Detect invalidation from timeout (stale assumptions)."""
        stale_assumptions = self.registry.get_stale()
        signals = []

        for assumption in stale_assumptions:
            signal = InvalidationSignal(
                signal_id=f"timeout-{assumption.assumption_id}-{datetime.now(timezone.utc).timestamp()}",
                assumption_id=assumption.assumption_id,
                source=InvalidationSource.TIMEOUT,
                reason=f"Assumption review overdue since {assumption.next_review_date}",
                confidence=0.8,  # High confidence that stale assumptions are risky
                severity="medium",
                timestamp=datetime.now(timezone.utc)
            )
            signals.append(signal)

        if signals:
            logger.warning("Detected %d stale assumptions", len(signals))

        return signals

    def track_confidence_trend(
        self,
        artifact_id: str,
        confidence: float
    ) -> bool:
        """
        Track confidence trend and detect degradation.

        Returns True if confidence is decreasing or volatile.
        """
        if artifact_id not in self.confidence_trends:
            self.confidence_trends[artifact_id] = ConfidenceTrend(artifact_id=artifact_id)

        trend = self.confidence_trends[artifact_id]
        trend.add_measurement(datetime.now(timezone.utc), confidence)

        return trend.is_decreasing() or trend.is_volatile()

    def track_murphy_trend(
        self,
        artifact_id: str,
        murphy_index: float
    ) -> bool:
        """
        Track Murphy index trend and detect increasing risk.

        Returns True if Murphy index is increasing or exceeds threshold.
        """
        if artifact_id not in self.murphy_trends:
            self.murphy_trends[artifact_id] = MurphyIndexTrend(artifact_id=artifact_id)

        trend = self.murphy_trends[artifact_id]
        trend.add_measurement(datetime.now(timezone.utc), murphy_index)

        return trend.is_increasing() or trend.exceeds_threshold()


class ConfidenceDecayer:
    """
    Automatically decays confidence when assumptions are invalidated.

    Decay formula:
    - Critical invalidation: confidence *= 0.1 (90% drop)
    - High severity: confidence *= 0.3 (70% drop)
    - Medium severity: confidence *= 0.5 (50% drop)
    - Low severity: confidence *= 0.7 (30% drop)
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry
        self.decay_factors = {
            "critical": 0.1,
            "high": 0.3,
            "medium": 0.5,
            "low": 0.7
        }

    def decay_confidence(
        self,
        assumption_id: str,
        signal: InvalidationSignal,
        current_confidence: float
    ) -> CorrectionAction:
        """
        Decay confidence based on invalidation signal.

        Returns CorrectionAction describing the decay.
        """
        decay_factor = self.decay_factors.get(signal.severity, 0.5)
        new_confidence = current_confidence * decay_factor

        action = CorrectionAction(
            action_id=f"decay-conf-{assumption_id}-{datetime.now(timezone.utc).timestamp()}",
            assumption_id=assumption_id,
            action_type=CorrectionActionType.DROP_CONFIDENCE,
            triggered_by=signal.signal_id,
            timestamp=datetime.now(timezone.utc),
            rationale=f"Confidence decayed due to {signal.source.value} invalidation: {signal.reason}",
            confidence_before=current_confidence,
            confidence_after=new_confidence
        )

        logger.info(
            f"Decayed confidence for {assumption_id}: {current_confidence:.2f} -> {new_confidence:.2f} "
            f"(factor: {decay_factor}, severity: {signal.severity})"
        )

        return action


class AuthorityDecayer:
    """
    Automatically decays authority when assumptions are invalidated.

    Authority levels: none < low < medium < high

    Decay rules:
    - Critical invalidation: authority -> none
    - High severity: authority -> one level down
    - Medium severity: authority -> one level down if high
    - Low severity: no change
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry
        self.authority_levels = ["none", "low", "medium", "high"]

    def decay_authority(
        self,
        assumption_id: str,
        signal: InvalidationSignal,
        current_authority: str
    ) -> CorrectionAction:
        """
        Decay authority based on invalidation signal.

        Returns CorrectionAction describing the decay.
        """
        current_level = self.authority_levels.index(current_authority) if current_authority in self.authority_levels else 0

        if signal.severity == "critical":
            new_level = 0  # Drop to none
        elif signal.severity == "high":
            new_level = max(0, current_level - 1)
        elif signal.severity == "medium" and current_level >= 3:
            new_level = current_level - 1
        else:
            new_level = current_level

        new_authority = self.authority_levels[new_level]

        action = CorrectionAction(
            action_id=f"decay-auth-{assumption_id}-{datetime.now(timezone.utc).timestamp()}",
            assumption_id=assumption_id,
            action_type=CorrectionActionType.DECAY_AUTHORITY,
            triggered_by=signal.signal_id,
            timestamp=datetime.now(timezone.utc),
            rationale=f"Authority decayed due to {signal.source.value} invalidation: {signal.reason}",
            authority_before=current_authority,
            authority_after=new_authority
        )

        logger.info(
            f"Decayed authority for {assumption_id}: {current_authority} -> {new_authority} "
            f"(severity: {signal.severity})"
        )

        return action


class ExecutionFreezer:
    """
    Freezes execution when critical assumptions are invalidated.

    Responsibilities:
    - Identify artifacts affected by invalidated critical assumptions
    - Freeze execution of affected artifacts
    - Track frozen artifacts
    """

    def __init__(
        self,
        registry: AssumptionRegistry,
        binding_manager: AssumptionBindingManager
    ):
        self.registry = registry
        self.binding_manager = binding_manager
        self.frozen_artifacts: Dict[str, List[str]] = {}  # artifact_id -> [assumption_ids]

    def freeze_execution(
        self,
        assumption_id: str,
        signal: InvalidationSignal
    ) -> CorrectionAction:
        """
        Freeze execution for artifacts depending on invalidated critical assumption.

        Returns CorrectionAction describing the freeze.
        """
        # Get all artifacts bound to this assumption
        artifact_ids = self.registry.get_artifacts_for_assumption(assumption_id)

        # Filter to only critical bindings
        affected_artifacts = []
        for artifact_id in artifact_ids:
            critical_assumptions = self.registry.get_critical_by_artifact(artifact_id)
            if any(a.assumption_id == assumption_id for a in critical_assumptions):
                affected_artifacts.append(artifact_id)

                # Track frozen artifact
                if artifact_id not in self.frozen_artifacts:
                    self.frozen_artifacts[artifact_id] = []
                self.frozen_artifacts[artifact_id].append(assumption_id)

        action = CorrectionAction(
            action_id=f"freeze-{assumption_id}-{datetime.now(timezone.utc).timestamp()}",
            assumption_id=assumption_id,
            action_type=CorrectionActionType.FREEZE_EXECUTION,
            triggered_by=signal.signal_id,
            timestamp=datetime.now(timezone.utc),
            rationale=f"Execution frozen due to critical assumption invalidation: {signal.reason}",
            execution_frozen=True,
            affected_artifacts=affected_artifacts
        )

        if affected_artifacts:
            logger.warning(
                f"Froze execution for {len(affected_artifacts)} artifacts due to "
                f"invalidated critical assumption {assumption_id}"
            )

        return action

    def can_execute(self, artifact_id: str) -> Tuple[bool, List[str]]:
        """
        Check if artifact can execute (not frozen).

        Returns (can_execute, blocking_assumption_ids)
        """
        if artifact_id in self.frozen_artifacts:
            return False, self.frozen_artifacts[artifact_id]
        return True, []

    def unfreeze_artifact(self, artifact_id: str, assumption_id: str) -> bool:
        """
        Unfreeze artifact for specific assumption (when assumption validated).

        Returns True if artifact is now fully unfrozen.
        """
        if artifact_id not in self.frozen_artifacts:
            return True

        if assumption_id in self.frozen_artifacts[artifact_id]:
            self.frozen_artifacts[artifact_id].remove(assumption_id)

        # If no more blocking assumptions, remove from frozen dict
        if not self.frozen_artifacts[artifact_id]:
            del self.frozen_artifacts[artifact_id]
            logger.info("Artifact %s fully unfrozen", artifact_id)
            return True

        return False


class ReExpansionTrigger:
    """
    Triggers re-expansion after correction.

    Re-expansion criteria:
    - All critical assumptions validated or removed
    - Confidence restored above threshold
    - Authority restored
    - No active invalidation signals
    """

    def __init__(
        self,
        registry: AssumptionRegistry,
        binding_manager: AssumptionBindingManager,
        freezer: ExecutionFreezer
    ):
        self.registry = registry
        self.binding_manager = binding_manager
        self.freezer = freezer
        self.min_confidence_for_expansion = 0.7

    def can_reexpand(
        self,
        artifact_id: str,
        current_confidence: float
    ) -> Tuple[bool, List[str]]:
        """
        Check if artifact can re-expand.

        Returns (can_reexpand, blocking_reasons)
        """
        blocking_reasons = []

        # Check if frozen
        can_execute, frozen_assumptions = self.freezer.can_execute(artifact_id)
        if not can_execute:
            blocking_reasons.append(
                f"Execution frozen due to invalidated critical assumptions: {frozen_assumptions}"
            )

        # Check confidence
        if current_confidence < self.min_confidence_for_expansion:
            blocking_reasons.append(
                f"Confidence {current_confidence:.2f} below threshold {self.min_confidence_for_expansion}"
            )

        # Check critical assumptions
        critical_assumptions = self.registry.get_critical_by_artifact(artifact_id)
        for assumption in critical_assumptions:
            if assumption.status == AssumptionStatus.INVALIDATED:
                blocking_reasons.append(
                    f"Critical assumption {assumption.assumption_id} is invalidated"
                )
            elif assumption.status == AssumptionStatus.STALE:
                blocking_reasons.append(
                    f"Critical assumption {assumption.assumption_id} is stale"
                )

        can_reexpand = len(blocking_reasons) == 0
        return can_reexpand, blocking_reasons

    def trigger_reexpansion(
        self,
        artifact_id: str,
        current_confidence: float
    ) -> Optional[CorrectionAction]:
        """
        Trigger re-expansion if criteria met.

        Returns CorrectionAction if re-expansion triggered, None otherwise.
        """
        can_reexpand, blocking_reasons = self.can_reexpand(artifact_id, current_confidence)

        if not can_reexpand:
            logger.info(
                f"Cannot re-expand {artifact_id}: {', '.join(blocking_reasons)}"
            )
            return None

        action = CorrectionAction(
            action_id=f"reexpand-{artifact_id}-{datetime.now(timezone.utc).timestamp()}",
            assumption_id="",  # Not specific to one assumption
            action_type=CorrectionActionType.TRIGGER_REEXPANSION,
            triggered_by="correction_complete",
            timestamp=datetime.now(timezone.utc),
            rationale="Re-expansion triggered: all criteria met",
            affected_artifacts=[artifact_id]
        )

        logger.info("Triggered re-expansion for %s", artifact_id)
        return action

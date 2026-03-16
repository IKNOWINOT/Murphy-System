"""
Failure Mode Enumerator
Identifies potential failure modes for candidate future steps
"""

import hashlib
import logging

# Import from confidence engine
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import ExposureSignal, FailureMode, FailureModeType, RiskVector

from src.confidence_engine.models import ArtifactGraph, ArtifactNode, ArtifactType, AuthorityBand, ConfidenceState, Phase

logger = logging.getLogger(__name__)


class FailureModeEnumerator:
    """
    Enumerates potential failure modes for future steps

    For each candidate step k, estimates:
    - Semantic drift probability
    - Constraint violation probability
    - Authority misuse probability

    Produces RiskVector_k = {H(x_k), 1-D_k, Exposure_k, AuthorityRisk_k}
    """

    def __init__(self):
        # Thresholds for failure mode detection
        self.semantic_drift_threshold = 0.4
        self.constraint_violation_threshold = 0.3
        self.authority_misuse_threshold = 0.5
        self.verification_threshold = 0.6
        self.blast_radius_threshold = 0.5

    def enumerate_failure_modes(
        self,
        artifact_graph: ArtifactGraph,
        confidence_state: ConfidenceState,
        authority_band: AuthorityBand,
        exposure_signal: Optional[ExposureSignal] = None
    ) -> List[FailureMode]:
        """
        Enumerate all potential failure modes

        Args:
            artifact_graph: Current artifact graph
            confidence_state: Current confidence state
            authority_band: Current authority band
            exposure_signal: Optional exposure signal

        Returns:
            List of identified failure modes
        """
        failure_modes = []

        # Calculate risk vector
        risk_vector = self._calculate_risk_vector(
            confidence_state,
            authority_band,
            exposure_signal
        )

        # 1. Check for semantic drift
        semantic_drift = self._detect_semantic_drift(
            artifact_graph,
            confidence_state,
            risk_vector
        )
        if semantic_drift:
            failure_modes.append(semantic_drift)

        # 2. Check for constraint violations
        constraint_violations = self._detect_constraint_violations(
            artifact_graph,
            risk_vector
        )
        failure_modes.extend(constraint_violations)

        # 3. Check for authority misuse
        authority_misuse = self._detect_authority_misuse(
            confidence_state,
            authority_band,
            risk_vector
        )
        if authority_misuse:
            failure_modes.append(authority_misuse)

        # 4. Check for insufficient verification
        verification_issues = self._detect_verification_insufficient(
            confidence_state,
            risk_vector
        )
        if verification_issues:
            failure_modes.append(verification_issues)

        # 5. Check for irreversible actions
        if exposure_signal:
            irreversible = self._detect_irreversible_actions(
                exposure_signal,
                risk_vector
            )
            if irreversible:
                failure_modes.append(irreversible)

            # 6. Check for blast radius exceeded
            blast_radius = self._detect_blast_radius_exceeded(
                exposure_signal,
                risk_vector
            )
            if blast_radius:
                failure_modes.append(blast_radius)

        return failure_modes

    def _calculate_risk_vector(
        self,
        confidence_state: ConfidenceState,
        authority_band: AuthorityBand,
        exposure_signal: Optional[ExposureSignal]
    ) -> RiskVector:
        """
        Calculate risk vector for current state

        RiskVector = {H, 1-D, Exposure, AuthorityRisk}
        """
        # H: Epistemic instability
        H = confidence_state.epistemic_instability

        # 1-D: Lack of deterministic grounding
        one_minus_D = 1.0 - confidence_state.deterministic_score

        # Exposure: External side effects
        if exposure_signal:
            exposure = exposure_signal.blast_radius_estimate
        else:
            exposure = 0.0

        # AuthorityRisk: Risk from authority level
        authority_risk = self._calculate_authority_risk(
            confidence_state.confidence,
            authority_band
        )

        return RiskVector(
            H=H,
            one_minus_D=one_minus_D,
            exposure=exposure,
            authority_risk=authority_risk
        )

    def _calculate_authority_risk(
        self,
        confidence: float,
        authority_band: AuthorityBand
    ) -> float:
        """
        Calculate risk from authority level

        Risk increases when authority is high but confidence is low
        """
        # Map authority bands to risk multipliers
        authority_multipliers = {
            AuthorityBand.ASK_ONLY: 0.0,
            AuthorityBand.GENERATE: 0.2,
            AuthorityBand.PROPOSE: 0.4,
            AuthorityBand.NEGOTIATE: 0.6,
            AuthorityBand.EXECUTE: 1.0
        }

        base_risk = authority_multipliers.get(authority_band, 0.5)

        # Amplify risk if confidence is low
        confidence_gap = max(0.0, 0.85 - confidence)
        authority_risk = base_risk * (1.0 + confidence_gap)

        return min(1.0, authority_risk)

    def _detect_semantic_drift(
        self,
        artifact_graph: ArtifactGraph,
        confidence_state: ConfidenceState,
        risk_vector: RiskVector
    ) -> Optional[FailureMode]:
        """
        Detect semantic drift - multiple incompatible interpretations
        """
        # High epistemic instability indicates semantic drift
        if risk_vector.H > self.semantic_drift_threshold:
            # Count hypotheses with no verification
            hypotheses = [node for node in artifact_graph.nodes.values()
                         if node.type == ArtifactType.HYPOTHESIS]

            unverified_ratio = len(hypotheses) / max(1, len(artifact_graph.nodes))

            probability = risk_vector.H * (1.0 + unverified_ratio)
            probability = min(1.0, probability)

            impact = 0.7  # High impact - can lead to wrong decisions

            failure_mode = FailureMode(
                id=self._generate_id("semantic_drift"),
                type=FailureModeType.SEMANTIC_DRIFT,
                probability=probability,
                impact=impact,
                risk_vector=risk_vector,
                description=f"Semantic drift detected: {len(hypotheses)} unverified hypotheses, instability={risk_vector.H:.2f}",
                affected_artifacts=[h.id for h in hypotheses[:5]],  # First 5
                mitigation_required=True
            )

            return failure_mode

        return None

    def _detect_constraint_violations(
        self,
        artifact_graph: ArtifactGraph,
        risk_vector: RiskVector
    ) -> List[FailureMode]:
        """
        Detect potential constraint violations
        """
        failure_modes = []

        # Get all constraints
        constraints = [node for node in artifact_graph.nodes.values()
                      if node.type == ArtifactType.CONSTRAINT]

        # Get all decisions
        decisions = [node for node in artifact_graph.nodes.values()
                    if node.type == ArtifactType.DECISION]

        # Check if decisions might violate constraints
        for decision in decisions:
            # Simple heuristic: check if decision has constraint dependencies
            constraint_deps = [dep_id for dep_id in decision.dependencies
                             if dep_id in [c.id for c in constraints]]

            if not constraint_deps and constraints:
                # Decision made without considering constraints
                probability = 0.5 * (1.0 + risk_vector.H)
                impact = 0.6

                failure_mode = FailureMode(
                    id=self._generate_id(f"constraint_violation_{decision.id}"),
                    type=FailureModeType.CONSTRAINT_VIOLATION,
                    probability=probability,
                    impact=impact,
                    risk_vector=risk_vector,
                    description=f"Decision {decision.id} may violate constraints",
                    affected_artifacts=[decision.id],
                    mitigation_required=True
                )

                failure_modes.append(failure_mode)

        return failure_modes

    def _detect_authority_misuse(
        self,
        confidence_state: ConfidenceState,
        authority_band: AuthorityBand,
        risk_vector: RiskVector
    ) -> Optional[FailureMode]:
        """
        Detect authority misuse - authority too high for confidence level
        """
        if risk_vector.authority_risk > self.authority_misuse_threshold:
            probability = risk_vector.authority_risk
            impact = 0.8  # High impact - can lead to unsafe execution

            failure_mode = FailureMode(
                id=self._generate_id("authority_misuse"),
                type=FailureModeType.AUTHORITY_MISUSE,
                probability=probability,
                impact=impact,
                risk_vector=risk_vector,
                description=f"Authority {authority_band.value} too high for confidence {confidence_state.confidence:.2f}",
                affected_artifacts=[],
                mitigation_required=True
            )

            return failure_mode

        return None

    def _detect_verification_insufficient(
        self,
        confidence_state: ConfidenceState,
        risk_vector: RiskVector
    ) -> Optional[FailureMode]:
        """
        Detect insufficient verification
        """
        # Check if deterministic grounding is too low
        if confidence_state.deterministic_score < self.verification_threshold:
            probability = risk_vector.one_minus_D
            impact = 0.7

            verified_ratio = 0.0
            if confidence_state.total_artifacts > 0:
                verified_ratio = confidence_state.verified_artifacts / confidence_state.total_artifacts

            failure_mode = FailureMode(
                id=self._generate_id("verification_insufficient"),
                type=FailureModeType.VERIFICATION_INSUFFICIENT,
                probability=probability,
                impact=impact,
                risk_vector=risk_vector,
                description=f"Insufficient verification: {confidence_state.verified_artifacts}/{confidence_state.total_artifacts} artifacts verified ({verified_ratio:.1%})",
                affected_artifacts=[],
                mitigation_required=True
            )

            return failure_mode

        return None

    def _detect_irreversible_actions(
        self,
        exposure_signal: ExposureSignal,
        risk_vector: RiskVector
    ) -> Optional[FailureMode]:
        """
        Detect irreversible actions
        """
        if exposure_signal.reversibility < 0.5:
            probability = 1.0 - exposure_signal.reversibility
            impact = 0.9  # Very high impact - cannot undo

            failure_mode = FailureMode(
                id=self._generate_id("irreversible_action"),
                type=FailureModeType.IRREVERSIBLE_ACTION,
                probability=probability,
                impact=impact,
                risk_vector=risk_vector,
                description=f"Irreversible action detected: reversibility={exposure_signal.reversibility:.2f}",
                affected_artifacts=[],
                mitigation_required=True
            )

            return failure_mode

        return None

    def _detect_blast_radius_exceeded(
        self,
        exposure_signal: ExposureSignal,
        risk_vector: RiskVector
    ) -> Optional[FailureMode]:
        """
        Detect blast radius exceeded
        """
        if exposure_signal.blast_radius_estimate > self.blast_radius_threshold:
            probability = exposure_signal.blast_radius_estimate
            impact = exposure_signal.blast_radius_estimate

            failure_mode = FailureMode(
                id=self._generate_id("blast_radius_exceeded"),
                type=FailureModeType.BLAST_RADIUS_EXCEEDED,
                probability=probability,
                impact=impact,
                risk_vector=risk_vector,
                description=f"Blast radius {exposure_signal.blast_radius_estimate:.2f} exceeds threshold {self.blast_radius_threshold}",
                affected_artifacts=[],
                mitigation_required=True
            )

            return failure_mode

        return None

    def _generate_id(self, base: str) -> str:
        """Generate unique ID for failure mode"""
        timestamp = datetime.now(timezone.utc).isoformat()
        content = f"{base}_{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

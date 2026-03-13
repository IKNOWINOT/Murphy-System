"""
Murphy Index Calculator
Computes expected downstream risk: M_t = Σ_k L_k × p_k
"""

import logging
import math
from typing import Any, Dict, List

from .graph_analyzer import GraphAnalyzer
from .models import ArtifactGraph, ConfidenceState, Phase

logger = logging.getLogger(__name__)


class MurphyCalculator:
    """
    Calculates Murphy Index - expected downstream risk

    M_t = Σ_k L_k × p_k

    Where:
    - L_k = loss magnitude for failure mode k
    - p_k = probability of failure mode k
    - p_k = σ(α×H(x_k) + β×(1-D_k) + γ×Exposure_k + δ×AuthorityRisk_k)
    """

    def __init__(self):
        self.graph_analyzer = GraphAnalyzer()

        # Sigmoid parameters
        self.alpha = 2.0  # Weight for epistemic instability
        self.beta = 1.5   # Weight for lack of grounding
        self.gamma = 1.0  # Weight for exposure
        self.delta = 1.2  # Weight for authority risk

    def calculate_murphy_index(
        self,
        graph: ArtifactGraph,
        confidence_state: ConfidenceState,
        phase: Phase
    ) -> float:
        """
        Calculate Murphy Index

        Args:
            graph: Current artifact graph
            confidence_state: Current confidence state
            phase: Current phase

        Returns:
            Murphy index in [0, 1] (higher = more risk)
        """
        # Identify failure modes
        failure_modes = self._identify_failure_modes(graph, confidence_state, phase)

        # Calculate expected risk
        total_risk = 0.0

        for mode in failure_modes:
            loss = mode['loss']
            probability = mode['probability']
            total_risk += loss * probability

        # Normalize to [0, 1]
        murphy_index = min(1.0, total_risk)

        return murphy_index

    def _identify_failure_modes(
        self,
        graph: ArtifactGraph,
        confidence_state: ConfidenceState,
        phase: Phase
    ) -> List[Dict[str, Any]]:
        """
        Identify potential failure modes and their characteristics

        Returns:
            List of failure modes with loss and probability
        """
        failure_modes = []

        # Failure Mode 1: Contradiction-induced failure
        contradictions = self.graph_analyzer.detect_contradictions(graph)
        if contradictions:
            for contradiction in contradictions:
                severity_loss = {
                    'low': 0.1,
                    'medium': 0.3,
                    'high': 0.6,
                    'critical': 0.9
                }
                loss = severity_loss.get(contradiction.get('severity', 'medium'), 0.3)

                # Probability based on epistemic instability
                H = confidence_state.epistemic_instability
                probability = self._sigmoid(self.alpha * H)

                failure_modes.append({
                    'type': 'contradiction',
                    'loss': loss,
                    'probability': probability,
                    'details': contradiction
                })

        # Failure Mode 2: Insufficient grounding
        D = confidence_state.deterministic_score
        if D < 0.5:
            loss = 0.5  # Moderate loss
            probability = self._sigmoid(self.beta * (1 - D))

            failure_modes.append({
                'type': 'insufficient_grounding',
                'loss': loss,
                'probability': probability,
                'details': {'deterministic_score': D}
            })

        # Failure Mode 3: High exposure (many unverified artifacts)
        exposure = self._calculate_exposure(graph, confidence_state)
        if exposure > 0.3:
            loss = 0.4
            probability = self._sigmoid(self.gamma * exposure)

            failure_modes.append({
                'type': 'high_exposure',
                'loss': loss,
                'probability': probability,
                'details': {'exposure': exposure}
            })

        # Failure Mode 4: Authority risk (executing with low confidence)
        authority_risk = self._calculate_authority_risk(confidence_state, phase)
        if authority_risk > 0.3:
            loss = 0.7  # High loss
            probability = self._sigmoid(self.delta * authority_risk)

            failure_modes.append({
                'type': 'authority_risk',
                'loss': loss,
                'probability': probability,
                'details': {'authority_risk': authority_risk}
            })

        # Failure Mode 5: Unresolved dependencies
        unresolved = self._calculate_unresolved_dependencies(graph)
        if unresolved > 0.2:
            loss = 0.5
            probability = self._sigmoid(2.0 * unresolved)

            failure_modes.append({
                'type': 'unresolved_dependencies',
                'loss': loss,
                'probability': probability,
                'details': {'unresolved_ratio': unresolved}
            })

        return failure_modes

    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for probability calculation"""
        return 1.0 / (1.0 + math.exp(-x))

    def _calculate_exposure(
        self,
        graph: ArtifactGraph,
        confidence_state: ConfidenceState
    ) -> float:
        """
        Calculate exposure - ratio of unverified to total artifacts

        Returns:
            Exposure in [0, 1]
        """
        if confidence_state.total_artifacts == 0:
            return 0.0

        unverified = confidence_state.total_artifacts - confidence_state.verified_artifacts
        exposure = unverified / confidence_state.total_artifacts

        return exposure

    def _calculate_authority_risk(
        self,
        confidence_state: ConfidenceState,
        phase: Phase
    ) -> float:
        """
        Calculate authority risk - risk of executing with insufficient confidence

        Returns:
            Risk in [0, 1]
        """
        # Risk increases as we approach execution phase with low confidence
        phase_risk = {
            Phase.EXPAND: 0.0,
            Phase.TYPE: 0.1,
            Phase.ENUMERATE: 0.2,
            Phase.CONSTRAIN: 0.3,
            Phase.COLLAPSE: 0.5,
            Phase.BIND: 0.7,
            Phase.EXECUTE: 1.0
        }

        base_risk = phase_risk.get(phase, 0.0)

        # Adjust by confidence gap
        required_confidence = phase.confidence_threshold
        confidence_gap = max(0.0, required_confidence - confidence_state.confidence)

        # Risk is base risk amplified by confidence gap
        authority_risk = base_risk * (1.0 + confidence_gap)

        return min(1.0, authority_risk)

    def _calculate_unresolved_dependencies(self, graph: ArtifactGraph) -> float:
        """
        Calculate ratio of unresolved dependencies

        Returns:
            Ratio in [0, 1]
        """
        if not graph.nodes:
            return 0.0

        # Count nodes with unresolved dependencies
        unresolved_count = 0

        for node in graph.nodes.values():
            # Check if any dependencies are missing or unverified
            for dep_id in node.dependencies:
                if dep_id not in graph.nodes:
                    unresolved_count += 1
                    break

        unresolved_ratio = unresolved_count / (len(graph.nodes) or 1)

        return unresolved_ratio

    def get_failure_mode_details(
        self,
        graph: ArtifactGraph,
        confidence_state: ConfidenceState,
        phase: Phase
    ) -> List[Dict[str, Any]]:
        """
        Get detailed breakdown of all failure modes

        Returns:
            List of failure mode details
        """
        return self._identify_failure_modes(graph, confidence_state, phase)

    def get_failure_mode_breakdown(
        self,
        graph: ArtifactGraph,
        confidence_state: ConfidenceState,
        phase: Phase
    ) -> Dict[str, Any]:
        """
        Tuning #6: Summarized breakdown for middle-range Murphy Index values.

        When the Murphy Index is between 0.3 and 0.7 (the "ambiguous zone"),
        operators need to understand *which* failure mode contributes most.

        Returns:
            Dict with murphy_index, zone classification, ranked mode
            contributions, and the dominant failure mode.
        """
        murphy_index = self.calculate_murphy_index(graph, confidence_state, phase)
        modes = self._identify_failure_modes(graph, confidence_state, phase)

        # Classify zone
        if murphy_index < 0.3:
            zone = "low_risk"
        elif murphy_index <= 0.7:
            zone = "ambiguous"
        else:
            zone = "high_risk"

        # Rank failure modes by contribution (loss * probability)
        contributions = []
        for mode in modes:
            contribution = mode["loss"] * mode["probability"]
            contributions.append({
                "type": mode["type"],
                "contribution": round(contribution, 4),
                "loss": round(mode["loss"], 4),
                "probability": round(mode["probability"], 4),
            })
        contributions.sort(key=lambda c: c["contribution"], reverse=True)

        dominant = contributions[0]["type"] if contributions else "none"

        return {
            "murphy_index": round(murphy_index, 4),
            "zone": zone,
            "dominant_failure_mode": dominant,
            "contributions": contributions,
        }

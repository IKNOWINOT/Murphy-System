"""
Confidence Calculator
Implements the core confidence equation: c_t = w_g(p_t) × G(x_t) + w_d(p_t) × D(x_t)
"""

import logging
import math
from typing import Any, Dict, List

from .graph_analyzer import GraphAnalyzer
from .models import (
    ArtifactGraph,
    ArtifactType,
    ConfidenceState,
    Phase,
    TrustModel,
    VerificationEvidence,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """
    Computes confidence using phase-weighted combination of:
    - Generative adequacy G(x_t)
    - Deterministic grounding D(x_t)
    - Epistemic instability H(x_t)
    """

    def __init__(
        self,
        bootstrap_floor: float = 0.5,
        sparse_graph_threshold: int = 5,
    ):
        self.graph_analyzer = GraphAnalyzer()
        # Adaptive parameters — can be updated by the learning engine
        self.bootstrap_floor: float = max(0.0, min(1.0, bootstrap_floor))
        self.sparse_graph_threshold: int = max(1, sparse_graph_threshold)
        # Threshold drift history for learning observability
        self._threshold_updates: List[dict] = []

    def update_thresholds(
        self,
        bootstrap_floor: float = None,
        sparse_graph_threshold: int = None,
    ) -> None:
        """Update adaptive threshold parameters from learning engine feedback.

        Called by :class:`LearningEngineConnector` when
        :class:`PerformancePredictor` issues a new threshold recommendation.
        Changes are bounded to keep the calculator in a safe operating range.

        Args:
            bootstrap_floor: New minimum confidence for cold-start graphs.
                Clamped to [0.3, 0.9].
            sparse_graph_threshold: New node-count ceiling below which the
                bootstrap floor applies.  Clamped to [1, 20].
        """
        import datetime
        changed = {}
        if bootstrap_floor is not None:
            new_floor = max(0.3, min(0.9, float(bootstrap_floor)))
            if abs(new_floor - self.bootstrap_floor) > 1e-6:
                changed["bootstrap_floor"] = (self.bootstrap_floor, new_floor)
                self.bootstrap_floor = new_floor
        if sparse_graph_threshold is not None:
            new_thresh = max(1, min(20, int(sparse_graph_threshold)))
            if new_thresh != self.sparse_graph_threshold:
                changed["sparse_graph_threshold"] = (
                    self.sparse_graph_threshold, new_thresh
                )
                self.sparse_graph_threshold = new_thresh
        if changed:
            self._threshold_updates.append({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "changes": changed,
            })
            # Keep only the last 100 updates
            if len(self._threshold_updates) > 100:
                self._threshold_updates = self._threshold_updates[-100:]

    def get_threshold_config(self) -> dict:
        """Return current adaptive threshold configuration."""
        return {
            "bootstrap_floor": self.bootstrap_floor,
            "sparse_graph_threshold": self.sparse_graph_threshold,
            "total_updates": len(self._threshold_updates),
        }

    def compute_confidence(
        self,
        graph: ArtifactGraph,
        phase: Phase,
        verification_evidence: List[VerificationEvidence],
        trust_model: TrustModel
    ) -> ConfidenceState:
        """
        Compute complete confidence state

        Args:
            graph: Current artifact graph
            phase: Current phase
            verification_evidence: List of verification results
            trust_model: Trust weights for sources

        Returns:
            Complete confidence state
        """
        # Calculate generative adequacy
        G_score = self.calculate_generative_adequacy(graph)

        # Calculate deterministic grounding
        D_score = self.calculate_deterministic_grounding(
            graph, verification_evidence, trust_model
        )

        # Calculate epistemic instability
        H_score = self.calculate_epistemic_instability(graph)

        # Get phase weights
        w_g, w_d = phase.weights

        # Compute confidence
        confidence = w_g * G_score + w_d * D_score

        # Bootstrap confidence floor: sparse graphs at EXPAND phase get a
        # minimum confidence to prevent cold-start blocking.
        # The floor and threshold are adaptive — updated by the learning engine.
        # (Case Study Tuning Recommendation #5)
        if phase == Phase.EXPAND and len(graph.nodes) < self.sparse_graph_threshold:
            confidence = max(confidence, self.bootstrap_floor)

        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        # Create state
        state = ConfidenceState(
            confidence=confidence,
            generative_score=G_score,
            deterministic_score=D_score,
            epistemic_instability=H_score,
            phase=phase
        )

        # Add component scores
        state.hypothesis_coverage = self._calculate_hypothesis_coverage(graph)
        state.decision_branching = self._calculate_decision_branching(graph)
        state.question_quality = self._calculate_question_quality(graph)
        state.verified_artifacts = len([e for e in verification_evidence
                                       if e.result == VerificationResult.PASS])
        state.total_artifacts = len(graph.nodes)

        return state

    def calculate_generative_adequacy(self, graph: ArtifactGraph) -> float:
        """
        Calculate G(x_t) - measures exploration completeness

        G(x) = f(hypothesis_coverage, decision_branching, question_quality)

        Returns:
            Score in [0, 1]
        """
        if not graph.nodes:
            return 0.0

        # Component 1: Hypothesis coverage
        hypothesis_coverage = self._calculate_hypothesis_coverage(graph)

        # Component 2: Decision branching
        decision_branching = self._calculate_decision_branching(graph)

        # Component 3: Question quality (unresolved decision points)
        question_quality = self._calculate_question_quality(graph)

        # Combine with weights
        G_score = (
            0.4 * hypothesis_coverage +
            0.3 * decision_branching +
            0.3 * question_quality
        )

        return G_score

    def _calculate_hypothesis_coverage(self, graph: ArtifactGraph) -> float:
        """
        Measure how well hypotheses cover the problem space

        Metrics:
        - Number of hypotheses
        - Diversity of hypotheses
        - Coverage of different aspects
        """
        hypotheses = [node for node in graph.nodes.values()
                     if node.type == ArtifactType.HYPOTHESIS]

        if not hypotheses:
            return 0.0

        # Score based on number (diminishing returns)
        count_score = min(1.0, len(hypotheses) / 10.0)

        # Score based on diversity (using graph entropy)
        entropy = self.graph_analyzer.calculate_entropy(graph)
        diversity_score = entropy

        # Combine
        coverage = (count_score + diversity_score) / 2.0

        return coverage

    def _calculate_decision_branching(self, graph: ArtifactGraph) -> float:
        """
        Measure quality of decision branching

        Metrics:
        - Number of decision points
        - Branching factor
        - Coverage of alternatives
        """
        decisions = [node for node in graph.nodes.values()
                    if node.type == ArtifactType.DECISION]

        if not decisions:
            return 0.0

        # Score based on number of decisions
        count_score = min(1.0, len(decisions) / 8.0)

        # Score based on branching factor
        branching_factors = []
        for decision in decisions:
            dependents = graph.get_dependents(decision.id)
            branching_factors.append(len(dependents))

        avg_branching = sum(branching_factors) / (len(branching_factors) or 1) if branching_factors else 0
        branching_score = min(1.0, avg_branching / 3.0)  # Expect ~3 alternatives per decision

        # Combine
        branching = (count_score + branching_score) / 2.0

        return branching

    def _calculate_question_quality(self, graph: ArtifactGraph) -> float:
        """
        Measure quality of unresolved questions

        Lower is better (fewer unresolved questions = higher quality)
        """
        # Find leaf nodes that are hypotheses or decisions (unresolved)
        leaves = graph.get_leaves()
        unresolved = [leaf for leaf in leaves
                     if leaf.type in [ArtifactType.HYPOTHESIS, ArtifactType.DECISION]]

        if not graph.nodes:
            return 0.0

        # Ratio of resolved to total
        resolved_ratio = 1.0 - (len(unresolved) / len(graph.nodes))

        return resolved_ratio

    def calculate_deterministic_grounding(
        self,
        graph: ArtifactGraph,
        verification_evidence: List[VerificationEvidence],
        trust_model: TrustModel
    ) -> float:
        """
        Calculate D(x_t) - measures verification strength

        D(x) = Σ verified_artifacts × trust_weight × stability_score

        Only artifacts with verification evidence contribute.

        Returns:
            Score in [0, 1]
        """
        if not graph.nodes or not verification_evidence:
            return 0.0

        # Create evidence map
        evidence_map = {e.artifact_id: e for e in verification_evidence}

        # Calculate weighted sum
        total_weight = 0.0
        verified_weight = 0.0

        for node in graph.nodes.values():
            # Get trust weight for this source
            trust_weight = trust_model.get_trust(node.source.value)

            # Get verification evidence
            evidence = evidence_map.get(node.id)

            if evidence and evidence.result == VerificationResult.PASS:
                # Verified artifact contributes
                contribution = (
                    node.confidence_weight *
                    trust_weight *
                    evidence.stability_score
                )
                verified_weight += contribution

            # Total possible weight
            total_weight += node.confidence_weight * trust_weight

        # Normalize
        D_score = verified_weight / total_weight if total_weight > 0 else 0.0

        return D_score

    def calculate_epistemic_instability(self, graph: ArtifactGraph) -> float:
        """
        Calculate H(x_t) - measures epistemic instability

        H(x) = graph_conflict_score + semantic_variance

        Sources:
        - Incompatible constraints
        - Solver disagreement
        - Assumption mismatches

        Returns:
            Instability score in [0, 1] (higher = more unstable)
        """
        if not graph.nodes:
            return 0.0

        # Detect contradictions
        contradictions = self.graph_analyzer.detect_contradictions(graph)

        # Score based on contradiction severity
        conflict_score = 0.0
        severity_weights = {
            'low': 0.1,
            'medium': 0.3,
            'high': 0.6,
            'critical': 1.0
        }

        for contradiction in contradictions:
            severity = contradiction.get('severity', 'medium')
            conflict_score += severity_weights.get(severity, 0.3)

        # Normalize by number of nodes
        conflict_score = min(1.0, conflict_score / max(1, len(graph.nodes) * 0.1))

        # Calculate semantic variance (using entropy)
        entropy = self.graph_analyzer.calculate_entropy(graph)
        semantic_variance = entropy

        # Combine
        H_score = (conflict_score + semantic_variance) / 2.0

        return H_score

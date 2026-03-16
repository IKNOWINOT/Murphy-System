"""
Murphy Validator

Main validation interface that integrates uncertainty calculations,
confidence scoring, and Murphy Gate decisions.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from .murphy_gate import MurphyGate
from .murphy_models import ConfidenceReport, GateResult, Phase, UncertaintyScores

# Add murphy_runtime_analysis to path for imports
from .uncertainty_calculator import UncertaintyCalculator

logger = logging.getLogger(__name__)


class MurphyValidator:
    """
    Murphy Validator - Main validation interface

    Integrates:
    - Uncertainty calculations (UD, UA, UI, UR, UG)
    - Confidence scoring (both new and existing formulas)
    - Murphy Gate decisions
    - Integration with existing confidence engine
    """

    def __init__(self):
        self.uncertainty_calculator = UncertaintyCalculator()
        self.murphy_gate = MurphyGate()

        # Try to import existing confidence engine
        try:
            from src.confidence_engine.confidence_calculator import ConfidenceCalculator
            self.confidence_calculator_v1 = ConfidenceCalculator()
            self.has_v1_calculator = True
            logger.info("Loaded existing confidence calculator (v1)")
        except ImportError:
            self.confidence_calculator_v1 = None
            self.has_v1_calculator = False
            logger.warning("Could not load existing confidence calculator")

        # Weights for uncertainty-based confidence calculation
        self.uncertainty_weights = {
            'data': 0.25,
            'authority': 0.20,
            'intent': 0.15,
            'risk': 0.25,
            'disagreement': 0.15
        }

    def validate(
        self,
        task: Any,
        context: Dict[str, Any],
        phase: Optional[Phase] = None,
        threshold: Optional[float] = None
    ) -> ConfidenceReport:
        """
        Complete validation of a task

        Args:
            task: Task to validate
            context: Execution context
            phase: Current execution phase (optional)
            threshold: Custom confidence threshold (optional)

        Returns:
            ConfidenceReport with complete assessment
        """
        logger.info(f"Validating task: {getattr(task, 'task_id', 'unknown')}")

        # Compute uncertainty scores
        uncertainty_scores = self.uncertainty_calculator.compute_all_uncertainties(
            task=task,
            context=context
        )

        # Compute confidence from uncertainties
        confidence = self._compute_confidence_from_uncertainties(uncertainty_scores)

        # Compute confidence using existing formula (if available)
        confidence_v1 = None
        if self.has_v1_calculator:
            try:
                confidence_v1 = self._compute_confidence_v1(task, context)
            except Exception as exc:
                logger.warning(f"Could not compute v1 confidence: {exc}")

        # Use higher confidence (conservative approach)
        final_confidence = max(confidence, confidence_v1) if confidence_v1 else confidence

        # Evaluate Murphy Gate
        gate_result = self.murphy_gate.evaluate(
            confidence=final_confidence,
            threshold=threshold,
            phase=phase,
            context=context
        )

        # Generate detailed factors
        factors = self._generate_factors(task, context, uncertainty_scores)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            uncertainty_scores,
            confidence,
            gate_result
        )

        # Generate warnings
        warnings = self._generate_warnings(
            uncertainty_scores,
            confidence,
            gate_result
        )

        # Create report
        report = ConfidenceReport(
            uncertainty_scores=uncertainty_scores,
            confidence=confidence,
            confidence_v1=confidence_v1,
            gate_result=gate_result,
            factors=factors,
            recommendations=recommendations,
            warnings=warnings
        )

        logger.info(
            f"Validation complete: confidence={final_confidence:.2f}, "
            f"gate_action={gate_result.action.value}"
        )

        return report

    def _compute_confidence_from_uncertainties(
        self,
        uncertainty_scores: UncertaintyScores
    ) -> float:
        """
        Compute confidence from uncertainty scores

        Formula: C = 1 - (w_d·UD + w_a·UA + w_i·UI + w_r·UR + w_g·UG)

        Where weights sum to 1.0
        """
        total_uncertainty = (
            self.uncertainty_weights['data'] * uncertainty_scores.UD +
            self.uncertainty_weights['authority'] * uncertainty_scores.UA +
            self.uncertainty_weights['intent'] * uncertainty_scores.UI +
            self.uncertainty_weights['risk'] * uncertainty_scores.UR +
            self.uncertainty_weights['disagreement'] * uncertainty_scores.UG
        )

        confidence = 1.0 - total_uncertainty

        # Ensure in valid range
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            f"Confidence from uncertainties: {confidence:.3f} "
            f"(UD={uncertainty_scores.UD:.2f}, UA={uncertainty_scores.UA:.2f}, "
            f"UI={uncertainty_scores.UI:.2f}, UR={uncertainty_scores.UR:.2f}, "
            f"UG={uncertainty_scores.UG:.2f})"
        )

        return confidence

    def _compute_confidence_v1(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> float:
        """Compute confidence using the existing G/D/H formula.

        Delegates to :class:`ConfidenceCalculator.compute_confidence` to
        produce a real score from the *Generative adequacy* (G),
        *Deterministic grounding* (D), and *Epistemic instability* (H)
        factors.  Returns ``None`` when the v1 calculator is unavailable or
        the context lacks the required artefacts.
        """
        if not self.has_v1_calculator:
            return None

        try:
            from .confidence_calculator import ConfidenceCalculator
            from .models import ArtifactGraph, TrustModel
            from .models import Phase as ConfPhase

            # Extract v1-compatible artefacts from context (graceful defaults)
            graph = context.get('artifact_graph')
            phase_arg = context.get('phase')
            evidence = context.get('verification_evidence', [])
            trust_model = context.get('trust_model')

            if graph is None or phase_arg is None or trust_model is None:
                # Minimal fallback when full artefact context is unavailable.
                if graph is not None:
                    return self.confidence_calculator_v1.calculate_generative_adequacy(graph)
                # Build a minimal artifact graph from any listed artifacts.
                graph = ArtifactGraph()
                artifacts = context.get('artifacts', [])
                for art in artifacts:
                    graph.add_node(art)

                # Map phase string to confidence engine Phase enum.
                phase_str = context.get('phase', 'expand')
                phase_map = {p.value: p for p in ConfPhase}
                phase_arg = phase_map.get(phase_str, ConfPhase.EXPAND)

                # Use default trust model.
                trust_model = context.get('trust_model', TrustModel())

            state = self.confidence_calculator_v1.compute_confidence(
                graph=graph,
                phase=phase_arg,
                verification_evidence=evidence,
                trust_model=trust_model,
            )
            return state.confidence
        except Exception as exc:
            logger.warning("v1 confidence calculation failed: %s", exc)
            return None

    def _generate_factors(
        self,
        task: Any,
        context: Dict[str, Any],
        uncertainty_scores: UncertaintyScores
    ) -> Dict[str, Any]:
        """Generate detailed factors contributing to scores"""
        return {
            'data_quality': self._categorize_score(1.0 - uncertainty_scores.UD),
            'source_credibility': self._categorize_score(1.0 - uncertainty_scores.UA),
            'goal_clarity': self._categorize_score(1.0 - uncertainty_scores.UI),
            'risk_level': self._categorize_score(1.0 - uncertainty_scores.UR),
            'consensus_level': self._categorize_score(1.0 - uncertainty_scores.UG),
            'task_priority': getattr(task, 'priority', 'unknown'),
            'has_validation_criteria': bool(getattr(task, 'validation_criteria', [])),
            'has_human_checkpoints': bool(getattr(task, 'human_checkpoints', []))
        }

    def _categorize_score(self, score: float) -> str:
        """Categorize a score into quality levels"""
        if score >= 0.9:
            return 'excellent'
        elif score >= 0.7:
            return 'good'
        elif score >= 0.5:
            return 'fair'
        elif score >= 0.3:
            return 'poor'
        else:
            return 'very_poor'

    def _generate_recommendations(
        self,
        uncertainty_scores: UncertaintyScores,
        confidence: float,
        gate_result: GateResult
    ) -> list:
        """Generate recommendations for improving confidence"""
        recommendations = []

        # Data uncertainty recommendations
        if uncertainty_scores.UD > 0.3:
            recommendations.append(
                "Consider additional data validation and verification to reduce data uncertainty"
            )

        # Authority uncertainty recommendations
        if uncertainty_scores.UA > 0.3:
            recommendations.append(
                "Verify source credentials and seek expert consensus to reduce authority uncertainty"
            )

        # Intent uncertainty recommendations
        if uncertainty_scores.UI > 0.3:
            recommendations.append(
                "Clarify requirements and add measurable success criteria to reduce intent uncertainty"
            )

        # Risk uncertainty recommendations
        if uncertainty_scores.UR > 0.3:
            recommendations.append(
                "Implement risk mitigation strategies and increase reversibility to reduce risk uncertainty"
            )

        # Disagreement uncertainty recommendations
        if uncertainty_scores.UG > 0.3:
            recommendations.append(
                "Resolve conflicting information and establish decision authority to reduce disagreement uncertainty"
            )

        # Gate-specific recommendations
        if not gate_result.allowed:
            recommendations.append(
                f"Confidence {confidence:.2f} is below threshold {gate_result.threshold:.2f}. "
                f"Address the above recommendations before proceeding."
            )

        return recommendations

    def _generate_warnings(
        self,
        uncertainty_scores: UncertaintyScores,
        confidence: float,
        gate_result: GateResult
    ) -> list:
        """Generate warnings about potential issues"""
        warnings = []

        # High uncertainty warnings
        if uncertainty_scores.UD > 0.7:
            warnings.append("WARNING: Very high data uncertainty - data quality is poor")

        if uncertainty_scores.UA > 0.7:
            warnings.append("WARNING: Very high authority uncertainty - source credibility is questionable")

        if uncertainty_scores.UI > 0.7:
            warnings.append("WARNING: Very high intent uncertainty - requirements are unclear")

        if uncertainty_scores.UR > 0.7:
            warnings.append("WARNING: Very high risk uncertainty - potential for significant negative consequences")

        if uncertainty_scores.UG > 0.7:
            warnings.append("WARNING: Very high disagreement uncertainty - major conflicts in information")

        # Low confidence warnings
        if confidence < 0.5:
            warnings.append("WARNING: Confidence is very low - execution is not recommended")

        # Gate warnings
        if gate_result.action == 'block_execution':
            warnings.append("CRITICAL: Murphy Gate has blocked execution - do not proceed")

        return warnings

    def get_uncertainty_breakdown(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """Get detailed uncertainty breakdown"""
        uncertainty_scores = self.uncertainty_calculator.compute_all_uncertainties(
            task=task,
            context=context
        )

        return uncertainty_scores.to_dict()

    def evaluate_gate_only(
        self,
        confidence: float,
        phase: Optional[Phase] = None,
        threshold: Optional[float] = None
    ) -> GateResult:
        """Evaluate Murphy Gate without full validation"""
        return self.murphy_gate.evaluate(
            confidence=confidence,
            threshold=threshold,
            phase=phase
        )

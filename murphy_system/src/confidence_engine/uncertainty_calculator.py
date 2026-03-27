"""
Uncertainty Calculator

Computes all five Murphy uncertainty components:
- UD: Data Uncertainty
- UA: Authority Uncertainty
- UI: Intent Uncertainty
- UR: Risk Uncertainty
- UG: Disagreement Uncertainty
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .murphy_models import UncertaintyScores

logger = logging.getLogger(__name__)


class UncertaintyCalculator:
    """
    Calculates Murphy uncertainty scores

    All uncertainty scores are in range [0, 1] where:
    - 0 = no uncertainty (perfect certainty)
    - 1 = maximum uncertainty (complete uncertainty)
    """

    def __init__(self):
        # Weights for uncertainty components
        self.weights = {
            'data': 0.25,
            'authority': 0.20,
            'intent': 0.15,
            'risk': 0.25,
            'disagreement': 0.15
        }

    def compute_all_uncertainties(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> UncertaintyScores:
        """
        Compute all uncertainty components

        Args:
            task: Task being evaluated
            context: Execution context with data, sources, etc.

        Returns:
            UncertaintyScores with all components
        """
        UD = self.compute_data_uncertainty(task, context)
        UA = self.compute_authority_uncertainty(task, context)
        UI = self.compute_intent_uncertainty(task, context)
        UR = self.compute_risk_uncertainty(task, context)
        UG = self.compute_disagreement_uncertainty(task, context)

        return UncertaintyScores(
            UD=UD,
            UA=UA,
            UI=UI,
            UR=UR,
            UG=UG
        )

    def compute_data_uncertainty(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> float:
        """
        UD: Data quality and completeness

        Factors:
        - Completeness: % of required data available
        - Accuracy: Verified vs unverified data
        - Timeliness: How recent is the data
        - Consistency: Contradictions in data

        Returns:
            UD score in [0, 1]
        """
        # Extract data quality factors
        completeness = self._assess_completeness(task, context)
        accuracy = self._assess_accuracy(task, context)
        timeliness = self._assess_timeliness(task, context)
        consistency = self._assess_consistency(task, context)

        # Average quality factors
        quality = (completeness + accuracy + timeliness + consistency) / 4

        # UD = 1 - quality (higher quality = lower uncertainty)
        UD = 1.0 - quality

        logger.debug(f"Data Uncertainty: UD={UD:.3f} (completeness={completeness:.2f}, accuracy={accuracy:.2f}, timeliness={timeliness:.2f}, consistency={consistency:.2f})")

        return max(0.0, min(1.0, UD))

    def compute_authority_uncertainty(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> float:
        """
        UA: Source credibility and expertise

        Factors:
        - Credentials: Verified expertise
        - Reputation: Track record
        - Consensus: Agreement among experts
        - Bias: Potential conflicts of interest

        Returns:
            UA score in [0, 1]
        """
        # Extract authority factors
        credentials = self._assess_credentials(task, context)
        reputation = self._assess_reputation(task, context)
        consensus = self._assess_consensus(task, context)
        bias = self._assess_bias(task, context)

        # Average authority factors (bias is inverted)
        authority = (credentials + reputation + consensus + (1 - bias)) / 4

        # UA = 1 - authority (higher authority = lower uncertainty)
        UA = 1.0 - authority

        logger.debug(f"Authority Uncertainty: UA={UA:.3f} (credentials={credentials:.2f}, reputation={reputation:.2f}, consensus={consensus:.2f}, bias={bias:.2f})")

        return max(0.0, min(1.0, UA))

    def compute_intent_uncertainty(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> float:
        """
        UI: Clarity of goals and requirements

        Factors:
        - Specificity: How specific are requirements
        - Measurability: Can success be measured
        - Ambiguity: Unclear or contradictory requirements
        - Completeness: All requirements specified

        Returns:
            UI score in [0, 1]
        """
        # Extract intent clarity factors
        specificity = self._assess_specificity(task)
        measurability = self._assess_measurability(task)
        ambiguity = self._assess_ambiguity(task)
        completeness = self._assess_requirement_completeness(task)

        # Average clarity factors (ambiguity is inverted)
        clarity = (specificity + measurability + (1 - ambiguity) + completeness) / 4

        # UI = 1 - clarity (higher clarity = lower uncertainty)
        UI = 1.0 - clarity

        logger.debug(f"Intent Uncertainty: UI={UI:.3f} (specificity={specificity:.2f}, measurability={measurability:.2f}, ambiguity={ambiguity:.2f}, completeness={completeness:.2f})")

        return max(0.0, min(1.0, UI))

    def compute_risk_uncertainty(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> float:
        """
        UR: Potential negative consequences

        Factors:
        - Impact: Severity of potential failures
        - Probability: Likelihood of failures
        - Reversibility: Can failures be undone
        - Mitigation: Are mitigations in place

        Returns:
            UR score in [0, 1]
        """
        # Extract risk factors
        impact = self._assess_impact(task, context)
        probability = self._assess_failure_probability(task, context)
        reversibility = self._assess_reversibility(task)
        mitigation = self._assess_mitigation(task, context)

        # Weighted average (impact and probability weighted higher)
        UR = (
            0.35 * impact +
            0.35 * probability +
            0.15 * (1 - reversibility) +
            0.15 * (1 - mitigation)
        )

        logger.debug(f"Risk Uncertainty: UR={UR:.3f} (impact={impact:.2f}, probability={probability:.2f}, reversibility={reversibility:.2f}, mitigation={mitigation:.2f})")

        return max(0.0, min(1.0, UR))

    def compute_disagreement_uncertainty(
        self,
        task: Any,
        context: Dict[str, Any]
    ) -> float:
        """
        UG: Conflicting information or opinions

        Factors:
        - Contradictions: Direct conflicts in data
        - Divergence: Different approaches suggested
        - Controversy: Disputed best practices
        - Resolution: Can conflicts be resolved

        Returns:
            UG score in [0, 1]
        """
        # Extract disagreement factors
        contradictions = self._detect_contradictions(context)
        divergence = self._assess_divergence(context)
        controversy = self._assess_controversy(task)
        resolution = self._assess_resolution_potential(context)

        # Average disagreement factors (resolution is inverted)
        UG = (contradictions + divergence + controversy + (1 - resolution)) / 4

        logger.debug(f"Disagreement Uncertainty: UG={UG:.3f} (contradictions={contradictions:.2f}, divergence={divergence:.2f}, controversy={controversy:.2f}, resolution={resolution:.2f})")

        return max(0.0, min(1.0, UG))

    # ========================================================================
    # DATA UNCERTAINTY (UD) ASSESSMENT METHODS
    # ========================================================================

    def _assess_completeness(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess data completeness (0=incomplete, 1=complete)"""
        # Check if all required data is available
        required_data = context.get('required_data', [])
        available_data = context.get('available_data', [])

        if not required_data:
            return 0.8  # Default: assume mostly complete

        completeness = len(available_data) / len(required_data)
        return min(1.0, completeness)

    def _assess_accuracy(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess data accuracy (0=unverified, 1=verified)"""
        # Check verification status of data
        verified_count = context.get('verified_data_count', 0)
        total_count = context.get('total_data_count', 1)

        if total_count == 0:
            return 0.5  # Default: assume partially verified

        accuracy = verified_count / total_count
        return accuracy

    def _assess_timeliness(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess data timeliness (0=stale, 1=fresh)"""
        # Check data freshness
        data_age_days = context.get('data_age_days', 30)

        # Exponential decay: fresh data (0 days) = 1.0, old data (90+ days) = 0.0
        timeliness = max(0.0, 1.0 - (data_age_days / 90.0))
        return timeliness

    def _assess_consistency(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess data consistency (0=contradictory, 1=consistent)"""
        # Check for contradictions
        contradiction_count = context.get('contradiction_count', 0)

        if contradiction_count == 0:
            return 1.0
        elif contradiction_count <= 2:
            return 0.7
        elif contradiction_count <= 5:
            return 0.4
        else:
            return 0.1

    # ========================================================================
    # AUTHORITY UNCERTAINTY (UA) ASSESSMENT METHODS
    # ========================================================================

    def _assess_credentials(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess source credentials (0=none, 1=verified expert)"""
        # Check source credentials
        source_credentials = context.get('source_credentials', [])

        if not source_credentials:
            return 0.3  # Default: assume limited credentials

        # Score based on credential quality
        verified_experts = sum(1 for c in source_credentials if c.get('verified') and c.get('expert'))
        total_sources = len(source_credentials)

        return verified_experts / total_sources if total_sources > 0 else 0.3

    def _assess_reputation(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess source reputation (0=poor, 1=excellent)"""
        # Check source reputation scores
        reputation_scores = context.get('reputation_scores', [])

        if not reputation_scores:
            return 0.5  # Default: assume average reputation

        avg_reputation = sum(reputation_scores) / len(reputation_scores)
        return avg_reputation

    def _assess_consensus(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess expert consensus (0=disagreement, 1=agreement)"""
        # Check agreement among sources
        agreement_level = context.get('expert_agreement', 0.7)
        return agreement_level

    def _assess_bias(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess potential bias (0=unbiased, 1=highly biased)"""
        # Check for conflicts of interest
        bias_indicators = context.get('bias_indicators', [])

        if not bias_indicators:
            return 0.1  # Default: assume minimal bias

        # More bias indicators = higher bias score
        bias_score = min(1.0, len(bias_indicators) * 0.2)
        return bias_score

    # ========================================================================
    # INTENT UNCERTAINTY (UI) ASSESSMENT METHODS
    # ========================================================================

    def _assess_specificity(self, task: Any) -> float:
        """Assess requirement specificity (0=vague, 1=specific)"""
        # Check task description length and detail
        description = getattr(task, 'description', '')

        if len(description) < 50:
            return 0.3  # Too short, likely vague
        elif len(description) < 200:
            return 0.6  # Moderate detail
        else:
            return 0.9  # Detailed description

    def _assess_measurability(self, task: Any) -> float:
        """Assess success measurability (0=unmeasurable, 1=measurable)"""
        # Check if validation criteria exist
        validation_criteria = getattr(task, 'validation_criteria', [])

        if not validation_criteria:
            return 0.2  # No criteria = hard to measure

        # More criteria = more measurable
        measurability = min(1.0, len(validation_criteria) * 0.3)
        return measurability

    def _assess_ambiguity(self, task: Any) -> float:
        """Assess requirement ambiguity (0=clear, 1=ambiguous)"""
        # Check for ambiguous language
        description = getattr(task, 'description', '').lower()

        ambiguous_words = ['maybe', 'possibly', 'might', 'could', 'should', 'approximately']
        ambiguity_count = sum(1 for word in ambiguous_words if word in description)

        # More ambiguous words = higher ambiguity
        ambiguity = min(1.0, ambiguity_count * 0.2)
        return ambiguity

    def _assess_requirement_completeness(self, task: Any) -> float:
        """Assess requirement completeness (0=incomplete, 1=complete)"""
        # Check if key requirement aspects are specified
        has_description = bool(getattr(task, 'description', ''))
        has_deliverables = bool(getattr(task, 'deliverables', []))
        has_validation = bool(getattr(task, 'validation_criteria', []))
        has_timeline = bool(getattr(task, 'estimated_hours', None))

        completeness = sum([has_description, has_deliverables, has_validation, has_timeline]) / 4
        return completeness

    # ========================================================================
    # RISK UNCERTAINTY (UR) ASSESSMENT METHODS
    # ========================================================================

    def _assess_impact(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess failure impact (0=minimal, 1=catastrophic)"""
        # Check task priority and criticality
        priority = getattr(task, 'priority', 'medium')

        priority_impact = {
            'low': 0.2,
            'medium': 0.5,
            'high': 0.7,
            'critical': 0.9
        }

        return priority_impact.get(priority, 0.5)

    def _assess_failure_probability(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess failure probability (0=unlikely, 1=likely)"""
        # Check historical failure rate and complexity
        complexity = context.get('task_complexity', 'medium')
        historical_failure_rate = context.get('historical_failure_rate', 0.2)

        complexity_factor = {
            'low': 0.1,
            'medium': 0.3,
            'high': 0.6,
            'very_high': 0.8
        }

        base_probability = complexity_factor.get(complexity, 0.3)

        # Adjust by historical data
        probability = (base_probability + historical_failure_rate) / 2
        return min(1.0, probability)

    def _assess_reversibility(self, task: Any) -> float:
        """Assess failure reversibility (0=irreversible, 1=easily reversed)"""
        # Check if task has rollback capability
        risks = getattr(task, 'risks', [])

        # Look for irreversibility indicators
        irreversible_keywords = ['permanent', 'irreversible', 'cannot undo', 'data loss']
        has_irreversible = any(
            any(keyword in risk.lower() for keyword in irreversible_keywords)
            for risk in risks
        )

        if has_irreversible:
            return 0.2  # Low reversibility
        else:
            return 0.8  # High reversibility (default assumption)

    def _assess_mitigation(self, task: Any, context: Dict[str, Any]) -> float:
        """Assess risk mitigation (0=no mitigation, 1=fully mitigated)"""
        # Check if mitigations are in place
        mitigations = context.get('risk_mitigations', [])
        risks = getattr(task, 'risks', [])

        if not risks:
            return 1.0  # No risks = no mitigation needed

        if not mitigations:
            return 0.2  # Risks but no mitigations

        # Compare mitigation coverage
        mitigation_coverage = min(1.0, len(mitigations) / len(risks))
        return mitigation_coverage

    # ========================================================================
    # DISAGREEMENT UNCERTAINTY (UG) ASSESSMENT METHODS
    # ========================================================================

    def _detect_contradictions(self, context: Dict[str, Any]) -> float:
        """Detect contradictions (0=none, 1=many)"""
        # Check for contradictory information
        contradiction_count = context.get('contradiction_count', 0)

        if contradiction_count == 0:
            return 0.0
        elif contradiction_count <= 2:
            return 0.3
        elif contradiction_count <= 5:
            return 0.6
        else:
            return 0.9

    def _assess_divergence(self, context: Dict[str, Any]) -> float:
        """Assess approach divergence (0=consensus, 1=divergent)"""
        # Check for different recommended approaches
        approaches = context.get('recommended_approaches', [])

        if len(approaches) <= 1:
            return 0.0  # Single approach = no divergence
        elif len(approaches) == 2:
            return 0.4  # Two approaches = moderate divergence
        else:
            return 0.7  # Multiple approaches = high divergence

    def _assess_controversy(self, task: Any) -> float:
        """Assess controversy level (0=accepted, 1=controversial)"""
        # Check for controversial aspects
        description = getattr(task, 'description', '').lower()

        controversial_keywords = ['controversial', 'disputed', 'debated', 'disagreement']
        has_controversy = any(keyword in description for keyword in controversial_keywords)

        return 0.7 if has_controversy else 0.1

    def _assess_resolution_potential(self, context: Dict[str, Any]) -> float:
        """Assess conflict resolution potential (0=unresolvable, 1=resolvable)"""
        # Check if conflicts can be resolved
        has_tiebreaker = context.get('has_tiebreaker', False)
        has_authority = context.get('has_decision_authority', False)

        if has_tiebreaker and has_authority:
            return 0.9  # High resolution potential
        elif has_tiebreaker or has_authority:
            return 0.6  # Moderate resolution potential
        else:
            return 0.3  # Low resolution potential

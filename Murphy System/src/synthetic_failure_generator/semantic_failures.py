"""
Semantic Failure Generators
============================

Generates failures related to semantic mismatches and ambiguities.

Failure Types:
- Unit mismatches (°C vs °F, kg vs lb)
- Ambiguous labels
- Missing constraints
- Conflicting goals
"""

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .models import ConfidenceProfile, FailureCase, FailureType, SeverityLevel

logger = logging.getLogger(__name__)


class SemanticFailureGenerator:
    """
    Generates semantic failures

    Injects failures into:
    - Artifact graphs
    - Prompts
    - Interface schemas
    """

    def __init__(self):
        self.unit_pairs = [
            ('celsius', 'fahrenheit', 'temperature'),
            ('kg', 'lb', 'weight'),
            ('meters', 'feet', 'distance'),
            ('liters', 'gallons', 'volume'),
            ('pascals', 'psi', 'pressure'),
            ('joules', 'calories', 'energy'),
            ('watts', 'horsepower', 'power'),
            ('seconds', 'minutes', 'time')
        ]

        self.ambiguous_terms = [
            ('rate', ['speed', 'frequency', 'ratio']),
            ('load', ['weight', 'electrical_load', 'workload']),
            ('pressure', ['force_per_area', 'urgency', 'stress']),
            ('capacity', ['volume', 'capability', 'maximum']),
            ('range', ['distance', 'interval', 'variety']),
            ('scale', ['size', 'measurement_system', 'proportion'])
        ]

    def generate_unit_mismatch(
        self,
        artifact_graph: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """
        Generate unit mismatch failure

        Example: Temperature specified in °C but interpreted as °F
        """
        # Select random unit pair
        unit1, unit2, quantity = random.choice(self.unit_pairs)

        # Create failure case
        failure_id = self._generate_failure_id('unit_mismatch')

        # Inject mismatch into artifact graph
        perturbed_graph = self._inject_unit_mismatch(
            artifact_graph,
            unit1,
            unit2,
            quantity
        )

        # Calculate impact
        expected_loss = self._calculate_unit_mismatch_loss(unit1, unit2)
        murphy_probability = 0.8  # High probability of failure

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.85,
            confidence_trajectory=[0.85, 0.80, 0.70, 0.55, 0.40],
            instability_scores=[0.1, 0.2, 0.35, 0.5, 0.7],
            grounding_scores=[0.9, 0.85, 0.75, 0.6, 0.45],
            final_confidence=0.40,
            drift_rate=-0.1125  # Rapid decline
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.UNIT_MISMATCH,
            severity=severity,
            root_cause=f"Unit mismatch: {quantity} specified in {unit1} but interpreted as {unit2}",
            violated_assumptions=[
                f"Assumed consistent unit system for {quantity}",
                "Assumed explicit unit declarations",
                "Assumed unit validation at boundaries"
            ],
            missed_gates=[
                "unit_consistency_check",
                "dimensional_analysis_gate",
                "interface_schema_validation"
            ],
            recommended_gates=[
                {
                    'gate_type': 'semantic_stability',
                    'condition': f'verify_unit_consistency({quantity})',
                    'priority': 'high'
                },
                {
                    'gate_type': 'verification',
                    'condition': f'validate_dimensional_analysis({quantity})',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_ambiguous_label(
        self,
        artifact_graph: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.MEDIUM
    ) -> FailureCase:
        """
        Generate ambiguous label failure

        Example: "rate" could mean speed, frequency, or ratio
        """
        # Select random ambiguous term
        term, interpretations = random.choice(self.ambiguous_terms)

        failure_id = self._generate_failure_id('ambiguous_label')

        # Select two conflicting interpretations
        interp1, interp2 = random.sample(interpretations, 2)

        # Calculate impact
        expected_loss = 0.3  # Medium impact
        murphy_probability = 0.6

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.80,
            confidence_trajectory=[0.80, 0.75, 0.68, 0.60, 0.55],
            instability_scores=[0.15, 0.25, 0.35, 0.45, 0.55],
            grounding_scores=[0.85, 0.80, 0.72, 0.65, 0.60],
            final_confidence=0.55,
            drift_rate=-0.0625
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.AMBIGUOUS_LABEL,
            severity=severity,
            root_cause=f"Ambiguous label '{term}' interpreted as '{interp1}' instead of '{interp2}'",
            violated_assumptions=[
                "Assumed unambiguous terminology",
                "Assumed shared vocabulary",
                "Assumed explicit disambiguation"
            ],
            missed_gates=[
                "semantic_disambiguation_gate",
                "vocabulary_consistency_check",
                "label_clarity_validation"
            ],
            recommended_gates=[
                {
                    'gate_type': 'semantic_stability',
                    'condition': f'disambiguate_term("{term}")',
                    'priority': 'medium'
                },
                {
                    'gate_type': 'verification',
                    'condition': f'validate_interpretation("{term}")',
                    'priority': 'medium'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_missing_constraint(
        self,
        artifact_graph: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """
        Generate missing constraint failure

        Example: No upper bound specified for temperature
        """
        failure_id = self._generate_failure_id('missing_constraint')

        # Common constraint types
        constraint_types = [
            ('upper_bound', 'temperature', 'No maximum temperature specified'),
            ('lower_bound', 'pressure', 'No minimum pressure specified'),
            ('range', 'speed', 'No valid speed range specified'),
            ('precision', 'measurement', 'No precision requirement specified'),
            ('timeout', 'operation', 'No timeout constraint specified')
        ]

        constraint_type, parameter, description = random.choice(constraint_types)

        # Calculate impact
        expected_loss = 0.5  # High impact
        murphy_probability = 0.7

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.75,
            confidence_trajectory=[0.75, 0.68, 0.58, 0.45, 0.35],
            instability_scores=[0.2, 0.3, 0.45, 0.6, 0.75],
            grounding_scores=[0.80, 0.72, 0.60, 0.48, 0.38],
            final_confidence=0.35,
            drift_rate=-0.1
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.MISSING_CONSTRAINT,
            severity=severity,
            root_cause=f"Missing constraint: {description}",
            violated_assumptions=[
                f"Assumed implicit {constraint_type} for {parameter}",
                "Assumed safe default behavior",
                "Assumed constraint inheritance"
            ],
            missed_gates=[
                "constraint_completeness_check",
                "boundary_validation_gate",
                "safety_limit_verification"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_{constraint_type}_exists({parameter})',
                    'priority': 'high'
                },
                {
                    'gate_type': 'semantic_stability',
                    'condition': f'validate_constraint_completeness({parameter})',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_conflicting_goal(
        self,
        artifact_graph: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """
        Generate conflicting goal failure

        Example: Maximize speed AND minimize fuel consumption (conflicting)
        """
        failure_id = self._generate_failure_id('conflicting_goal')

        # Common conflicting goal pairs
        conflict_pairs = [
            ('maximize_speed', 'minimize_fuel', 'Speed vs fuel efficiency'),
            ('minimize_cost', 'maximize_quality', 'Cost vs quality'),
            ('maximize_throughput', 'minimize_latency', 'Throughput vs latency'),
            ('maximize_accuracy', 'minimize_time', 'Accuracy vs speed'),
            ('maximize_coverage', 'minimize_risk', 'Coverage vs risk')
        ]

        goal1, goal2, description = random.choice(conflict_pairs)

        # Calculate impact
        expected_loss = 0.8  # Critical impact
        murphy_probability = 0.85

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.70,
            confidence_trajectory=[0.70, 0.60, 0.45, 0.30, 0.20],
            instability_scores=[0.25, 0.4, 0.6, 0.75, 0.9],
            grounding_scores=[0.75, 0.62, 0.48, 0.35, 0.25],
            final_confidence=0.20,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.CONFLICTING_GOAL,
            severity=severity,
            root_cause=f"Conflicting goals: {description} - {goal1} conflicts with {goal2}",
            violated_assumptions=[
                "Assumed goal compatibility",
                "Assumed single optimization objective",
                "Assumed goal prioritization"
            ],
            missed_gates=[
                "goal_consistency_check",
                "objective_conflict_detection",
                "pareto_frontier_analysis"
            ],
            recommended_gates=[
                {
                    'gate_type': 'semantic_stability',
                    'condition': f'detect_goal_conflicts([{goal1}, {goal2}])',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'verification',
                    'condition': 'validate_goal_prioritization()',
                    'priority': 'critical'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_batch(
        self,
        artifact_graph: Dict[str, Any],
        count: int = 10
    ) -> List[FailureCase]:
        """Generate batch of semantic failures"""
        failures = []

        for _ in range(count):
            failure_type = random.choice([
                'unit_mismatch',
                'ambiguous_label',
                'missing_constraint',
                'conflicting_goal'
            ])

            if failure_type == 'unit_mismatch':
                failures.append(self.generate_unit_mismatch(artifact_graph))
            elif failure_type == 'ambiguous_label':
                failures.append(self.generate_ambiguous_label(artifact_graph))
            elif failure_type == 'missing_constraint':
                failures.append(self.generate_missing_constraint(artifact_graph))
            else:
                failures.append(self.generate_conflicting_goal(artifact_graph))

        return failures

    def _generate_failure_id(self, failure_type: str) -> str:
        """Generate unique failure ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{failure_type}:{timestamp}:{random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _inject_unit_mismatch(
        self,
        artifact_graph: Dict[str, Any],
        unit1: str,
        unit2: str,
        quantity: str
    ) -> Dict[str, Any]:
        """Inject unit mismatch into artifact graph"""
        # Create perturbed copy
        perturbed = artifact_graph.copy()

        # Add conflicting unit specifications
        if 'artifacts' not in perturbed:
            perturbed['artifacts'] = []

        perturbed['artifacts'].append({
            'id': f'artifact_{quantity}',
            'type': 'measurement',
            'quantity': quantity,
            'specified_unit': unit1,
            'interpreted_unit': unit2,
            'mismatch': True
        })

        return perturbed

    def _calculate_unit_mismatch_loss(self, unit1: str, unit2: str) -> float:
        """Calculate expected loss from unit mismatch"""
        # Conversion factors that cause significant errors
        high_impact_pairs = [
            ('celsius', 'fahrenheit'),
            ('kg', 'lb'),
            ('meters', 'feet')
        ]

        if (unit1, unit2) in high_impact_pairs or (unit2, unit1) in high_impact_pairs:
            return 0.7  # High loss
        else:
            return 0.4  # Medium loss

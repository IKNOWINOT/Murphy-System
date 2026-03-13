"""
Control Plane Failure Generators
=================================

Generates failures in the control plane logic.

Failure Types:
- Delayed verification
- Skipped gates
- False confidence inflation
- Missing rollback
"""

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import ConfidenceProfile, FailureCase, FailureType, SeverityLevel

logger = logging.getLogger(__name__)


class ControlPlaneFailureGenerator:
    """
    Generates control plane failures

    Injects failures into:
    - Gate compiler
    - Phase scheduler
    - Confidence engine
    """

    def __init__(self):
        self.verification_types = [
            'mathematical_proof',
            'unit_test',
            'integration_test',
            'security_audit',
            'performance_benchmark'
        ]

        self.gate_categories = [
            'semantic_stability',
            'verification',
            'authority_decay',
            'isolation'
        ]

    def generate_delayed_verification(
        self,
        gate_library: List[Dict[str, Any]],
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """
        Generate delayed verification failure

        Example: Verification happens after execution instead of before
        """
        failure_id = self._generate_failure_id('delayed_verification')

        verification_type = random.choice(self.verification_types)
        delay_steps = random.randint(3, 10)

        # Calculate impact
        expected_loss = 0.6 + (delay_steps * 0.05)  # Loss increases with delay
        murphy_probability = 0.75

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.80,
            confidence_trajectory=[0.80, 0.75, 0.65, 0.50, 0.35],
            instability_scores=[0.15, 0.3, 0.5, 0.7, 0.85],
            grounding_scores=[0.85, 0.75, 0.60, 0.45, 0.35],
            final_confidence=0.35,
            drift_rate=-0.1125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.DELAYED_VERIFICATION,
            severity=severity,
            root_cause=f"Verification '{verification_type}' delayed by {delay_steps} steps - executed before verification",
            violated_assumptions=[
                "Assumed verification before execution",
                "Assumed synchronous verification",
                "Assumed verification in critical path"
            ],
            missed_gates=[
                "pre_execution_verification_gate",
                "verification_ordering_check",
                "critical_path_validation"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_before_execute({verification_type})',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'semantic_stability',
                    'condition': 'enforce_verification_ordering()',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_skipped_gate(
        self,
        gate_library: List[Dict[str, Any]],
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """
        Generate skipped gate failure

        Example: Critical safety gate bypassed
        """
        failure_id = self._generate_failure_id('skipped_gate')

        gate_category = random.choice(self.gate_categories)
        gate_name = f"{gate_category}_gate_{random.randint(1, 100)}"

        # Calculate impact based on gate category
        impact_map = {
            'semantic_stability': 0.6,
            'verification': 0.8,
            'authority_decay': 0.7,
            'isolation': 0.9
        }

        expected_loss = impact_map.get(gate_category, 0.7)
        murphy_probability = 0.9  # Very high probability

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.85,
            confidence_trajectory=[0.85, 0.70, 0.50, 0.30, 0.15],
            instability_scores=[0.1, 0.35, 0.6, 0.8, 0.95],
            grounding_scores=[0.90, 0.70, 0.50, 0.30, 0.15],
            final_confidence=0.15,
            drift_rate=-0.175
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.SKIPPED_GATE,
            severity=severity,
            root_cause=f"Critical gate '{gate_name}' ({gate_category}) was skipped/bypassed",
            violated_assumptions=[
                "Assumed all gates are enforced",
                "Assumed no gate bypass mechanisms",
                "Assumed gate execution ordering"
            ],
            missed_gates=[
                "gate_enforcement_check",
                "bypass_detection_gate",
                "gate_execution_audit"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_gate_executed({gate_name})',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'isolation',
                    'condition': 'prevent_gate_bypass()',
                    'priority': 'critical'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_false_confidence(
        self,
        confidence_state: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """
        Generate false confidence inflation failure

        Example: Confidence artificially inflated without grounding
        """
        failure_id = self._generate_failure_id('false_confidence')

        # Simulate confidence inflation
        true_confidence = random.uniform(0.3, 0.5)
        inflated_confidence = random.uniform(0.8, 0.95)
        inflation_amount = inflated_confidence - true_confidence

        # Calculate impact
        expected_loss = 0.85  # Very high impact
        murphy_probability = 0.95  # Almost certain failure

        # Create confidence drift profile showing false inflation
        confidence_profile = ConfidenceProfile(
            initial_confidence=true_confidence,
            confidence_trajectory=[
                true_confidence,
                true_confidence + 0.1,
                inflated_confidence,  # Sudden jump
                inflated_confidence,
                true_confidence  # Reality check
            ],
            instability_scores=[0.2, 0.3, 0.9, 0.95, 0.85],
            grounding_scores=[0.6, 0.5, 0.2, 0.15, 0.3],
            final_confidence=true_confidence,
            drift_rate=0.0  # No real improvement
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.FALSE_CONFIDENCE,
            severity=severity,
            root_cause=f"Confidence artificially inflated from {true_confidence:.2f} to {inflated_confidence:.2f} (Δ={inflation_amount:.2f})",
            violated_assumptions=[
                "Assumed confidence reflects true grounding",
                "Assumed no confidence manipulation",
                "Assumed verification-based confidence"
            ],
            missed_gates=[
                "confidence_grounding_check",
                "artificial_inflation_detection",
                "verification_evidence_audit"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': 'verify_confidence_grounding()',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'semantic_stability',
                    'condition': 'detect_confidence_manipulation()',
                    'priority': 'critical'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_missing_rollback(
        self,
        execution_plan: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """
        Generate missing rollback failure

        Example: No rollback plan for critical operation
        """
        failure_id = self._generate_failure_id('missing_rollback')

        operation_types = [
            'database_write',
            'file_system_change',
            'api_call',
            'actuator_command',
            'state_transition'
        ]

        operation_type = random.choice(operation_types)

        # Calculate impact
        expected_loss = 0.75  # High impact
        murphy_probability = 0.8

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.75,
            confidence_trajectory=[0.75, 0.65, 0.50, 0.35, 0.25],
            instability_scores=[0.2, 0.4, 0.6, 0.75, 0.85],
            grounding_scores=[0.80, 0.65, 0.50, 0.40, 0.30],
            final_confidence=0.25,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.MISSING_ROLLBACK,
            severity=severity,
            root_cause=f"No rollback plan defined for operation '{operation_type}'",
            violated_assumptions=[
                "Assumed all operations are reversible",
                "Assumed implicit rollback capability",
                "Assumed automatic state recovery"
            ],
            missed_gates=[
                "rollback_plan_validation",
                "reversibility_check",
                "recovery_capability_audit"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_rollback_exists({operation_type})',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'isolation',
                    'condition': 'enforce_rollback_requirement()',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_batch(
        self,
        gate_library: List[Dict[str, Any]],
        count: int = 10
    ) -> List[FailureCase]:
        """Generate batch of control plane failures"""
        failures = []

        for _ in range(count):
            failure_type = random.choice([
                'delayed_verification',
                'skipped_gate',
                'false_confidence',
                'missing_rollback'
            ])

            if failure_type == 'delayed_verification':
                failures.append(self.generate_delayed_verification(gate_library))
            elif failure_type == 'skipped_gate':
                failures.append(self.generate_skipped_gate(gate_library))
            elif failure_type == 'false_confidence':
                failures.append(self.generate_false_confidence({}))
            else:
                failures.append(self.generate_missing_rollback({}))

        return failures

    def _generate_failure_id(self, failure_type: str) -> str:
        """Generate unique failure ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{failure_type}:{timestamp}:{random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

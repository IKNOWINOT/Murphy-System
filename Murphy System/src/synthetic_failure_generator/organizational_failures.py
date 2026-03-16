"""
Organizational Failure Generators
==================================

Generates failures from organizational and human factors.

Failure Types:
- Authority override
- Ignored warning
- Misaligned incentive
- Schedule pressure
"""

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import ConfidenceProfile, FailureCase, FailureType, SeverityLevel

logger = logging.getLogger(__name__)


class OrganizationalFailureGenerator:
    """
    Generates organizational failures

    Injects failures into:
    - Governance input layer
    - Override channels
    """

    def __init__(self):
        self.authority_levels = ['read_only', 'limited', 'standard', 'elevated']
        self.warning_types = [
            'risk_threshold_warning',
            'confidence_drop_warning',
            'gate_violation_warning',
            'resource_limit_warning',
            'safety_concern_warning'
        ]

    def generate_authority_override(
        self,
        governance_state: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """
        Generate authority override failure

        Example: Manager overrides safety gate to meet deadline
        """
        failure_id = self._generate_failure_id('authority_override')

        # Simulate authority escalation
        original_authority = random.choice(self.authority_levels[:2])  # Low authority
        override_authority = random.choice(self.authority_levels[2:])  # High authority

        override_reason = random.choice([
            'deadline_pressure',
            'cost_reduction',
            'competitive_advantage',
            'executive_directive',
            'customer_demand'
        ])

        # Calculate impact
        expected_loss = 0.9  # Very high impact
        murphy_probability = 0.95  # Almost certain failure

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.65,
            confidence_trajectory=[0.65, 0.50, 0.35, 0.20, 0.10],
            instability_scores=[0.3, 0.5, 0.7, 0.85, 0.95],
            grounding_scores=[0.70, 0.50, 0.35, 0.20, 0.10],
            final_confidence=0.10,
            drift_rate=-0.1375
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.AUTHORITY_OVERRIDE,
            severity=severity,
            root_cause=f"Authority override: {original_authority} → {override_authority} due to {override_reason}",
            violated_assumptions=[
                "Assumed authority hierarchy enforcement",
                "Assumed no override mechanisms",
                "Assumed safety-first culture",
                "Assumed gate authority independence"
            ],
            missed_gates=[
                "authority_escalation_audit",
                "override_justification_check",
                "safety_override_prevention",
                "governance_compliance_gate"
            ],
            recommended_gates=[
                {
                    'gate_type': 'authority_decay',
                    'condition': 'prevent_authority_override()',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'isolation',
                    'condition': 'enforce_authority_hierarchy()',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'verification',
                    'condition': f'audit_override_justification({override_reason})',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_ignored_warning(
        self,
        warning_history: List[Dict[str, Any]],
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """
        Generate ignored warning failure

        Example: Risk threshold warning dismissed without investigation
        """
        failure_id = self._generate_failure_id('ignored_warning')

        warning_type = random.choice(self.warning_types)
        warning_count = random.randint(3, 10)
        time_ignored_hours = random.randint(1, 48)

        # Calculate impact based on warning severity and duration
        expected_loss = min(0.95, 0.5 + (warning_count * 0.05) + (time_ignored_hours / 100))
        murphy_probability = 0.85

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.70,
            confidence_trajectory=[0.70, 0.55, 0.40, 0.25, 0.15],
            instability_scores=[0.25, 0.45, 0.65, 0.8, 0.9],
            grounding_scores=[0.75, 0.55, 0.40, 0.25, 0.15],
            final_confidence=0.15,
            drift_rate=-0.1375
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.IGNORED_WARNING,
            severity=severity,
            root_cause=f"Warning '{warning_type}' ignored {warning_count} times over {time_ignored_hours} hours",
            violated_assumptions=[
                "Assumed warnings are investigated",
                "Assumed escalation procedures",
                "Assumed warning acknowledgment",
                "Assumed safety culture"
            ],
            missed_gates=[
                "warning_acknowledgment_gate",
                "escalation_procedure_check",
                "investigation_requirement_gate",
                "warning_response_audit"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'require_warning_investigation({warning_type})',
                    'priority': 'critical'
                },
                {
                    'gate_type': 'isolation',
                    'condition': 'enforce_warning_escalation()',
                    'priority': 'high'
                },
                {
                    'gate_type': 'authority_decay',
                    'condition': 'reduce_authority_on_ignored_warning()',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_misaligned_incentive(
        self,
        incentive_structure: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """
        Generate misaligned incentive failure

        Example: Bonus for speed conflicts with safety requirements
        """
        failure_id = self._generate_failure_id('misaligned_incentive')

        # Common misalignment patterns
        misalignments = [
            ('speed_bonus', 'safety_compliance', 'Speed incentive conflicts with safety'),
            ('cost_reduction', 'quality_standards', 'Cost cutting conflicts with quality'),
            ('feature_delivery', 'testing_thoroughness', 'Feature pressure conflicts with testing'),
            ('revenue_target', 'risk_management', 'Revenue goals conflict with risk limits'),
            ('efficiency_metric', 'redundancy_requirement', 'Efficiency conflicts with redundancy')
        ]

        incentive, requirement, description = random.choice(misalignments)

        # Calculate impact
        expected_loss = 0.7
        murphy_probability = 0.75

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.75,
            confidence_trajectory=[0.75, 0.65, 0.50, 0.35, 0.25],
            instability_scores=[0.2, 0.35, 0.55, 0.7, 0.85],
            grounding_scores=[0.80, 0.65, 0.50, 0.35, 0.25],
            final_confidence=0.25,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.MISALIGNED_INCENTIVE,
            severity=severity,
            root_cause=f"Misaligned incentive: {description}",
            violated_assumptions=[
                "Assumed aligned incentives",
                "Assumed safety-first priorities",
                "Assumed incentive compatibility",
                "Assumed organizational coherence"
            ],
            missed_gates=[
                "incentive_alignment_check",
                "goal_compatibility_gate",
                "priority_conflict_detection",
                "organizational_coherence_audit"
            ],
            recommended_gates=[
                {
                    'gate_type': 'semantic_stability',
                    'condition': f'detect_incentive_misalignment({incentive}, {requirement})',
                    'priority': 'high'
                },
                {
                    'gate_type': 'verification',
                    'condition': 'validate_goal_alignment()',
                    'priority': 'high'
                },
                {
                    'gate_type': 'authority_decay',
                    'condition': 'reduce_authority_on_misalignment()',
                    'priority': 'medium'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_schedule_pressure(
        self,
        project_state: Dict[str, Any],
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """
        Generate schedule pressure failure

        Example: Deadline pressure leads to skipped verification
        """
        failure_id = self._generate_failure_id('schedule_pressure')

        # Simulate schedule pressure
        days_behind = random.randint(5, 30)
        skipped_steps = random.randint(2, 8)

        pressure_sources = [
            'customer_deadline',
            'market_window',
            'executive_commitment',
            'contract_penalty',
            'competitive_pressure'
        ]

        pressure_source = random.choice(pressure_sources)

        # Calculate impact
        expected_loss = min(0.9, 0.4 + (days_behind / 50) + (skipped_steps * 0.05))
        murphy_probability = 0.8

        # Create confidence drift profile
        confidence_profile = ConfidenceProfile(
            initial_confidence=0.70,
            confidence_trajectory=[0.70, 0.60, 0.45, 0.30, 0.20],
            instability_scores=[0.25, 0.4, 0.6, 0.75, 0.9],
            grounding_scores=[0.75, 0.60, 0.45, 0.30, 0.20],
            final_confidence=0.20,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.SCHEDULE_PRESSURE,
            severity=severity,
            root_cause=f"Schedule pressure: {days_behind} days behind due to {pressure_source}, {skipped_steps} steps skipped",
            violated_assumptions=[
                "Assumed adequate time allocation",
                "Assumed no corner-cutting",
                "Assumed process adherence",
                "Assumed schedule flexibility"
            ],
            missed_gates=[
                "schedule_realism_check",
                "process_adherence_gate",
                "corner_cutting_detection",
                "time_pressure_audit"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'prevent_step_skipping({skipped_steps})',
                    'priority': 'high'
                },
                {
                    'gate_type': 'isolation',
                    'condition': 'enforce_process_adherence()',
                    'priority': 'high'
                },
                {
                    'gate_type': 'authority_decay',
                    'condition': 'reduce_authority_under_pressure()',
                    'priority': 'medium'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_batch(self, count: int = 10) -> List[FailureCase]:
        """Generate batch of organizational failures"""
        failures = []

        for _ in range(count):
            failure_type = random.choice([
                'authority_override',
                'ignored_warning',
                'misaligned_incentive',
                'schedule_pressure'
            ])

            if failure_type == 'authority_override':
                failures.append(self.generate_authority_override({}))
            elif failure_type == 'ignored_warning':
                failures.append(self.generate_ignored_warning([]))
            elif failure_type == 'misaligned_incentive':
                failures.append(self.generate_misaligned_incentive({}))
            else:
                failures.append(self.generate_schedule_pressure({}))

        return failures

    def _generate_failure_id(self, failure_type: str) -> str:
        """Generate unique failure ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{failure_type}:{timestamp}:{random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

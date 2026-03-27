"""
Interface Failure Generators
=============================

Generates failures in external interfaces.

Failure Types:
- Stale data
- Actuator drift
- Intermittent connectivity
- Partial writes
"""

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import ConfidenceProfile, FailureCase, FailureType, SeverityLevel

logger = logging.getLogger(__name__)


class InterfaceFailureGenerator:
    """
    Generates interface failures

    Injects failures into:
    - Interface registry
    - Telemetry streams
    """

    def generate_stale_data(
        self,
        interface_id: str,
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """Generate stale data failure"""
        failure_id = self._generate_failure_id('stale_data')
        staleness_seconds = random.randint(60, 3600)

        expected_loss = min(0.8, 0.3 + (staleness_seconds / 3600) * 0.5)
        murphy_probability = 0.7

        confidence_profile = ConfidenceProfile(
            initial_confidence=0.80,
            confidence_trajectory=[0.80, 0.70, 0.55, 0.40, 0.30],
            instability_scores=[0.15, 0.3, 0.5, 0.7, 0.85],
            grounding_scores=[0.85, 0.70, 0.55, 0.40, 0.30],
            final_confidence=0.30,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.STALE_DATA,
            severity=severity,
            root_cause=f"Interface '{interface_id}' returning stale data ({staleness_seconds}s old)",
            violated_assumptions=[
                "Assumed real-time data",
                "Assumed data freshness validation",
                "Assumed timestamp checking"
            ],
            missed_gates=[
                "data_freshness_check",
                "timestamp_validation_gate",
                "staleness_detection"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_data_freshness({interface_id})',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_actuator_drift(
        self,
        actuator_id: str,
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """Generate actuator drift failure"""
        failure_id = self._generate_failure_id('actuator_drift')
        drift_percentage = random.uniform(5, 30)

        expected_loss = 0.6 + (drift_percentage / 100)
        murphy_probability = 0.75

        confidence_profile = ConfidenceProfile(
            initial_confidence=0.75,
            confidence_trajectory=[0.75, 0.65, 0.50, 0.35, 0.25],
            instability_scores=[0.2, 0.4, 0.6, 0.75, 0.9],
            grounding_scores=[0.80, 0.65, 0.50, 0.35, 0.25],
            final_confidence=0.25,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.ACTUATOR_DRIFT,
            severity=severity,
            root_cause=f"Actuator '{actuator_id}' drifted {drift_percentage:.1f}% from commanded position",
            violated_assumptions=[
                "Assumed actuator accuracy",
                "Assumed feedback control",
                "Assumed drift detection"
            ],
            missed_gates=[
                "actuator_calibration_check",
                "drift_detection_gate",
                "feedback_validation"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_actuator_position({actuator_id})',
                    'priority': 'critical'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_intermittent_connectivity(
        self,
        interface_id: str,
        severity: SeverityLevel = SeverityLevel.HIGH
    ) -> FailureCase:
        """Generate intermittent connectivity failure"""
        failure_id = self._generate_failure_id('intermittent_connectivity')
        failure_rate = random.uniform(0.1, 0.5)

        expected_loss = 0.5 + failure_rate
        murphy_probability = 0.8

        confidence_profile = ConfidenceProfile(
            initial_confidence=0.70,
            confidence_trajectory=[0.70, 0.60, 0.45, 0.30, 0.20],
            instability_scores=[0.25, 0.45, 0.65, 0.8, 0.9],
            grounding_scores=[0.75, 0.60, 0.45, 0.30, 0.20],
            final_confidence=0.20,
            drift_rate=-0.125
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.INTERMITTENT_CONNECTIVITY,
            severity=severity,
            root_cause=f"Interface '{interface_id}' has intermittent connectivity ({failure_rate*100:.0f}% failure rate)",
            violated_assumptions=[
                "Assumed reliable connectivity",
                "Assumed retry mechanisms",
                "Assumed connection monitoring"
            ],
            missed_gates=[
                "connectivity_health_check",
                "retry_policy_validation",
                "connection_stability_gate"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_connection_stability({interface_id})',
                    'priority': 'high'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_partial_write(
        self,
        interface_id: str,
        severity: SeverityLevel = SeverityLevel.CRITICAL
    ) -> FailureCase:
        """Generate partial write failure"""
        failure_id = self._generate_failure_id('partial_write')
        completion_percentage = random.uniform(30, 80)

        expected_loss = 0.9
        murphy_probability = 0.85

        confidence_profile = ConfidenceProfile(
            initial_confidence=0.80,
            confidence_trajectory=[0.80, 0.60, 0.40, 0.25, 0.15],
            instability_scores=[0.15, 0.5, 0.7, 0.85, 0.95],
            grounding_scores=[0.85, 0.60, 0.40, 0.25, 0.15],
            final_confidence=0.15,
            drift_rate=-0.1625
        )

        return FailureCase(
            failure_id=failure_id,
            failure_type=FailureType.PARTIAL_WRITE,
            severity=severity,
            root_cause=f"Interface '{interface_id}' partial write ({completion_percentage:.0f}% completed)",
            violated_assumptions=[
                "Assumed atomic operations",
                "Assumed transaction support",
                "Assumed write verification"
            ],
            missed_gates=[
                "atomicity_check",
                "transaction_validation_gate",
                "write_completion_verification"
            ],
            recommended_gates=[
                {
                    'gate_type': 'verification',
                    'condition': f'verify_write_completion({interface_id})',
                    'priority': 'critical'
                }
            ],
            confidence_drift_profile=confidence_profile,
            expected_loss=expected_loss,
            murphy_probability=murphy_probability
        )

    def generate_batch(self, count: int = 10) -> List[FailureCase]:
        """Generate batch of interface failures"""
        failures = []

        for i in range(count):
            interface_id = f"interface_{i}"
            failure_type = random.choice([
                'stale_data',
                'actuator_drift',
                'intermittent_connectivity',
                'partial_write'
            ])

            if failure_type == 'stale_data':
                failures.append(self.generate_stale_data(interface_id))
            elif failure_type == 'actuator_drift':
                failures.append(self.generate_actuator_drift(interface_id))
            elif failure_type == 'intermittent_connectivity':
                failures.append(self.generate_intermittent_connectivity(interface_id))
            else:
                failures.append(self.generate_partial_write(interface_id))

        return failures

    def _generate_failure_id(self, failure_type: str) -> str:
        """Generate unique failure ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{failure_type}:{timestamp}:{random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

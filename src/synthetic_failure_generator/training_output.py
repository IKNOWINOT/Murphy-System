"""
Training Output Generator
=========================

Generates training data for confidence models and gate policy learning.

Outputs:
- Confidence model training data
- Gate policy learning datasets
- Reward signals
- Labeled datasets
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .models import FailureCase, RewardSignal, SimulationResult, TrainingArtifact

logger = logging.getLogger(__name__)


class TrainingOutputGenerator:
    """
    Generates training outputs from simulation results

    Creates labeled datasets for:
    - Confidence estimation
    - Gate policy learning
    - Risk prediction
    """

    def __init__(self):
        self.training_artifacts: List[TrainingArtifact] = []
        self.reward_signals: List[RewardSignal] = []

    def generate_confidence_training_data(
        self,
        simulation_results
    ) -> List[TrainingArtifact]:
        """
        Generate training data for confidence models

        Trains estimators to predict:
        - Instability H(x)
        - Grounding D(x)
        - Failure probability p_k

        Args:
            simulation_results: Can be List[SimulationResult] or List[FailureCase]
        """
        from .models import FailureCase, SimulationResult, TelemetryOutcome

        artifacts = []

        # Handle both FailureCase and SimulationResult inputs
        for item in simulation_results:
            if isinstance(item, FailureCase):
                # Convert FailureCase to mock SimulationResult
                result = SimulationResult(
                    simulation_id=f"sim_{item.failure_id}",
                    scenario_id=f"scenario_{item.failure_id}",
                    failure_case=item,
                    execution_steps=[],
                    telemetry_outcome=TelemetryOutcome(
                        risk_trajectory=[0.5, 0.7, 0.9],
                        confidence_trajectory=[0.8, 0.6, 0.4],
                        murphy_index_trajectory=[0.3, 0.5, 0.8],
                        authority_level_trajectory=["medium", "low", "blocked"],
                        events=[],
                        total_loss=0.7,
                        detection_latency=1.0
                    ),
                    gates_triggered=[],
                    gates_missed=item.missed_gates,
                    final_risk=0.9,
                    final_confidence=0.4,
                    execution_halted=True,
                    halt_reason="safety_gate_triggered"
                )
                failure_case = item
                telemetry = result.telemetry_outcome
            else:
                result = item
                failure_case = result.failure_case
                telemetry = result.telemetry_outcome

            # Extract features from simulation
            features = self._extract_confidence_features(result)

            # Create labels for each timestep
            for i in range(len(telemetry.confidence_trajectory)):
                artifact = TrainingArtifact(
                    artifact_id=f"conf_train_{result.simulation_id}_{i}",
                    artifact_type='confidence_training',
                    input_features={
                        'artifact_count': features['artifact_count'],
                        'verification_count': features['verification_count'],
                        'gate_count': features['gate_count'],
                        'current_step': i,
                        'total_steps': len(telemetry.confidence_trajectory),
                        'previous_confidence': telemetry.confidence_trajectory[i-1] if i > 0 else features['initial_confidence'],
                        'risk_score': telemetry.risk_trajectory[i],
                        'murphy_index': telemetry.murphy_index_trajectory[i],
                        'failure_type': failure_case.failure_type.value
                    },
                    target_labels={
                        'instability_H': telemetry.risk_trajectory[i],
                        'grounding_D': 1.0 - telemetry.risk_trajectory[i],
                        'confidence': telemetry.confidence_trajectory[i],
                        'failure_probability': failure_case.murphy_probability,
                        'expected_loss': failure_case.expected_loss
                    },
                    metadata={
                        'simulation_id': result.simulation_id,
                        'failure_id': failure_case.failure_id,
                        'severity': failure_case.severity.value,
                        'execution_halted': result.execution_halted
                    }
                )

                artifacts.append(artifact)
                self.training_artifacts.append(artifact)

        return artifacts

    def generate_gate_policy_data(
        self,
        simulation_results
    ) -> List[TrainingArtifact]:
        """
        Generate training data for gate policy learning

        Optimizes for:
        - Earlier detection
        - Lower execution exposure
        - Reduced Murphy index

        Args:
            simulation_results: Can be List[SimulationResult] or List[FailureCase]
        """
        from .models import FailureCase, SimulationResult, TelemetryOutcome

        artifacts = []

        # Handle both FailureCase and SimulationResult inputs
        for item in simulation_results:
            if isinstance(item, FailureCase):
                # Convert FailureCase to mock SimulationResult
                result = SimulationResult(
                    simulation_id=f"sim_{item.failure_id}",
                    scenario_id=f"scenario_{item.failure_id}",
                    failure_case=item,
                    execution_steps=[],
                    telemetry_outcome=TelemetryOutcome(
                        risk_trajectory=[0.5, 0.7, 0.9],
                        confidence_trajectory=[0.8, 0.6, 0.4],
                        murphy_index_trajectory=[0.3, 0.5, 0.8],
                        authority_level_trajectory=["medium", "low", "blocked"],
                        events=[],
                        total_loss=0.7,
                        detection_latency=1.0
                    ),
                    gates_triggered=[],
                    gates_missed=item.missed_gates,
                    final_risk=0.9,
                    final_confidence=0.4,
                    execution_halted=True,
                    halt_reason="safety_gate_triggered"
                )
                failure_case = item
            else:
                result = item
                failure_case = result.failure_case

            # Extract gate-related features
            features = self._extract_gate_features(result)

            # Calculate reward signal
            reward = self._calculate_reward(result)

            artifact = TrainingArtifact(
                artifact_id=f"gate_policy_{result.simulation_id}",
                artifact_type='gate_policy',
                input_features={
                    'failure_type': failure_case.failure_type.value,
                    'initial_confidence': features['initial_confidence'],
                    'initial_risk': features['initial_risk'],
                    'artifact_complexity': features['artifact_complexity'],
                    'interface_count': features['interface_count'],
                    'available_gates': features['available_gates']
                },
                target_labels={
                    'recommended_gates': [g['gate_type'] for g in failure_case.recommended_gates],
                    'gate_priorities': [g['priority'] for g in failure_case.recommended_gates],
                    'missed_gates': failure_case.missed_gates,
                    'gates_triggered': result.gates_triggered,
                    'detection_latency': result.telemetry_outcome.detection_latency,
                    'total_loss': result.telemetry_outcome.total_loss,
                    'reward': reward.total_reward
                },
                metadata={
                    'simulation_id': result.simulation_id,
                    'execution_halted': result.execution_halted,
                    'halt_reason': result.halt_reason
                }
            )

            artifacts.append(artifact)
            self.training_artifacts.append(artifact)

        return artifacts

    def generate_reward_signals(
        self,
        simulation_results: List[SimulationResult]
    ) -> List[RewardSignal]:
        """
        Generate reward signals for gate policy learning

        Reward function: R = -Σ(L_k × p_k) - latency_penalty - false_positive_penalty
        """
        signals = []

        for result in simulation_results:
            reward = self._calculate_reward(result)
            signals.append(reward)
            self.reward_signals.append(reward)

        return signals

    def generate_risk_prediction_data(
        self,
        simulation_results: List[SimulationResult]
    ) -> List[TrainingArtifact]:
        """
        Generate training data for risk prediction

        Predicts future risk trajectory
        """
        artifacts = []

        for result in simulation_results:
            failure_case = result.failure_case
            telemetry = result.telemetry_outcome

            # Create training examples for risk prediction
            for i in range(len(telemetry.risk_trajectory) - 1):
                artifact = TrainingArtifact(
                    artifact_id=f"risk_pred_{result.simulation_id}_{i}",
                    artifact_type='risk_prediction',
                    input_features={
                        'current_risk': telemetry.risk_trajectory[i],
                        'current_confidence': telemetry.confidence_trajectory[i],
                        'murphy_index': telemetry.murphy_index_trajectory[i],
                        'steps_remaining': len(telemetry.risk_trajectory) - i - 1,
                        'failure_type': failure_case.failure_type.value,
                        'gates_active': len(result.gates_triggered)
                    },
                    target_labels={
                        'next_risk': telemetry.risk_trajectory[i + 1],
                        'risk_delta': telemetry.risk_trajectory[i + 1] - telemetry.risk_trajectory[i],
                        'final_risk': telemetry.risk_trajectory[-1],
                        'will_halt': result.execution_halted
                    },
                    metadata={
                        'simulation_id': result.simulation_id,
                        'step_index': i
                    }
                )

                artifacts.append(artifact)
                self.training_artifacts.append(artifact)

        return artifacts

    def export_dataset(
        self,
        artifact_type: str,
        output_format: str = 'json'
    ) -> str:
        """
        Export training dataset

        Args:
            artifact_type: Type of artifacts to export
            output_format: Export format ('json', 'csv')
        """
        # Filter artifacts by type
        artifacts = [
            a for a in self.training_artifacts
            if a.artifact_type == artifact_type
        ]

        if output_format == 'json':
            import json
            return json.dumps([a.to_dict() for a in artifacts], indent=2)
        elif output_format == 'csv':
            # CSV export
            if not artifacts:
                return ""

            # Get all feature and label keys
            feature_keys = set()
            label_keys = set()
            for a in artifacts:
                feature_keys.update(a.input_features.keys())
                label_keys.update(a.target_labels.keys())

            feature_keys = sorted(feature_keys)
            label_keys = sorted(label_keys)

            # Create CSV
            lines = []
            header = ['artifact_id'] + feature_keys + label_keys
            lines.append(','.join(header))

            for a in artifacts:
                row = [a.artifact_id]
                row.extend([str(a.input_features.get(k, '')) for k in feature_keys])
                row.extend([str(a.target_labels.get(k, '')) for k in label_keys])
                lines.append(','.join(row))

            return '\n'.join(lines)
        else:
            raise ValueError(f"Unsupported output_format: {output_format}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about generated training data"""
        stats = {
            'total_artifacts': len(self.training_artifacts),
            'total_reward_signals': len(self.reward_signals),
            'artifacts_by_type': {},
            'average_reward': 0.0,
            'failure_type_distribution': {}
        }

        # Count by type
        for artifact in self.training_artifacts:
            artifact_type = artifact.artifact_type
            stats['artifacts_by_type'][artifact_type] = \
                stats['artifacts_by_type'].get(artifact_type, 0) + 1

        # Average reward
        if self.reward_signals:
            stats['average_reward'] = sum(r.total_reward for r in self.reward_signals) / (len(self.reward_signals) or 1)

        # Failure type distribution
        for artifact in self.training_artifacts:
            if 'failure_type' in artifact.input_features:
                failure_type = artifact.input_features['failure_type']
                stats['failure_type_distribution'][failure_type] = \
                    stats['failure_type_distribution'].get(failure_type, 0) + 1

        return stats

    def _extract_confidence_features(
        self,
        result: SimulationResult
    ) -> Dict[str, Any]:
        """Extract features for confidence training"""
        return {
            'artifact_count': len(result.failure_case.violated_assumptions),
            'verification_count': len(result.gates_triggered),
            'gate_count': len(result.failure_case.recommended_gates),
            'initial_confidence': result.failure_case.confidence_drift_profile.initial_confidence,
            'initial_risk': result.telemetry_outcome.risk_trajectory[0]
        }

    def _extract_gate_features(
        self,
        result: SimulationResult
    ) -> Dict[str, Any]:
        """Extract features for gate policy learning"""
        return {
            'initial_confidence': result.failure_case.confidence_drift_profile.initial_confidence,
            'initial_risk': result.telemetry_outcome.risk_trajectory[0],
            'artifact_complexity': len(result.failure_case.violated_assumptions),
            'interface_count': 5,  # default interface count
            'available_gates': len(result.failure_case.recommended_gates)
        }

    def _calculate_reward(
        self,
        result: SimulationResult
    ) -> RewardSignal:
        """
        Calculate reward signal

        R = -Σ(L_k × p_k) - latency_penalty - false_positive_penalty
        """
        # Expected loss
        expected_loss = result.telemetry_outcome.total_loss

        # Latency penalty (reward early detection)
        latency_penalty = result.telemetry_outcome.detection_latency * 0.01

        # False positive penalty (penalize unnecessary gates)
        false_positives = max(0, len(result.gates_triggered) - len(result.gates_missed))
        false_positive_penalty = false_positives * 0.05

        reward = RewardSignal(
            scenario_id=result.scenario_id,
            expected_loss=expected_loss,
            latency_penalty=latency_penalty,
            false_positive_penalty=false_positive_penalty,
            total_reward=0.0,
            gate_configuration=result.gates_triggered,
            detection_time=result.telemetry_outcome.detection_latency,
            false_positives=false_positives
        )

        reward.calculate_reward()

        return reward

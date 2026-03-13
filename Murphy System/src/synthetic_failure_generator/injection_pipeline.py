"""
Failure Injection Pipeline
===========================

Pipeline for injecting failures into base scenarios.

Pipeline Flow:
BaseScenario → Perturbation Operators → Failure Manifolds →
Synthetic Execution Packets → Execution Simulator → Telemetry + Risk Outcomes
"""

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .control_failures import ControlPlaneFailureGenerator
from .interface_failures import InterfaceFailureGenerator
from .models import (
    BaseScenario,
    FailureCase,
    FailureManifold,
    FailureType,
    PerturbationOperator,
    SimulationResult,
    TelemetryOutcome,
)
from .organizational_failures import OrganizationalFailureGenerator
from .semantic_failures import SemanticFailureGenerator

logger = logging.getLogger(__name__)


class FailureInjectionPipeline:
    """
    Pipeline for generating and injecting failures

    Transforms base scenarios into failure cases through perturbations
    """

    def __init__(self):
        self.semantic_gen = SemanticFailureGenerator()
        self.control_gen = ControlPlaneFailureGenerator()
        self.interface_gen = InterfaceFailureGenerator()
        self.organizational_gen = OrganizationalFailureGenerator()

        self.manifolds: Dict[str, FailureManifold] = {}

    def create_base_scenario(
        self,
        scenario_name: str,
        artifact_graph: Dict[str, Any],
        interface_definitions: Dict[str, Any],
        gate_library: List[Dict[str, Any]],
        initial_confidence: float = 0.8,
        initial_risk: float = 0.1
    ) -> BaseScenario:
        """Create base scenario for failure injection"""
        scenario_id = self._generate_id('scenario')

        return BaseScenario(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            artifact_graph=artifact_graph,
            interface_definitions=interface_definitions,
            gate_library=gate_library,
            initial_confidence=initial_confidence,
            initial_risk=initial_risk
        )

    def create_perturbation_operator(
        self,
        operator_name: str,
        failure_type: FailureType,
        parameters: Dict[str, Any]
    ) -> PerturbationOperator:
        """Create perturbation operator"""
        operator_id = self._generate_id('operator')

        # Map failure type to perturbation function
        function_map = {
            FailureType.UNIT_MISMATCH: 'inject_unit_mismatch',
            FailureType.AMBIGUOUS_LABEL: 'inject_ambiguous_label',
            FailureType.MISSING_CONSTRAINT: 'inject_missing_constraint',
            FailureType.CONFLICTING_GOAL: 'inject_conflicting_goal',
            FailureType.DELAYED_VERIFICATION: 'inject_delayed_verification',
            FailureType.SKIPPED_GATE: 'inject_skipped_gate',
            FailureType.FALSE_CONFIDENCE: 'inject_false_confidence',
            FailureType.MISSING_ROLLBACK: 'inject_missing_rollback',
            FailureType.STALE_DATA: 'inject_stale_data',
            FailureType.ACTUATOR_DRIFT: 'inject_actuator_drift',
            FailureType.INTERMITTENT_CONNECTIVITY: 'inject_intermittent_connectivity',
            FailureType.PARTIAL_WRITE: 'inject_partial_write',
            FailureType.AUTHORITY_OVERRIDE: 'inject_authority_override',
            FailureType.IGNORED_WARNING: 'inject_ignored_warning',
            FailureType.MISALIGNED_INCENTIVE: 'inject_misaligned_incentive',
            FailureType.SCHEDULE_PRESSURE: 'inject_schedule_pressure'
        }

        perturbation_function = function_map.get(failure_type, 'inject_generic')

        return PerturbationOperator(
            operator_id=operator_id,
            operator_name=operator_name,
            failure_type=failure_type,
            perturbation_function=perturbation_function,
            parameters=parameters,
            expected_impact=self._estimate_impact(failure_type)
        )

    def apply_perturbation(
        self,
        base_scenario: BaseScenario,
        operator: PerturbationOperator
    ) -> FailureCase:
        """Apply perturbation operator to base scenario"""

        # Generate failure case based on type
        if operator.failure_type in [
            FailureType.UNIT_MISMATCH,
            FailureType.AMBIGUOUS_LABEL,
            FailureType.MISSING_CONSTRAINT,
            FailureType.CONFLICTING_GOAL
        ]:
            failure_case = self._apply_semantic_perturbation(
                base_scenario,
                operator
            )
        elif operator.failure_type in [
            FailureType.DELAYED_VERIFICATION,
            FailureType.SKIPPED_GATE,
            FailureType.FALSE_CONFIDENCE,
            FailureType.MISSING_ROLLBACK
        ]:
            failure_case = self._apply_control_perturbation(
                base_scenario,
                operator
            )
        elif operator.failure_type in [
            FailureType.STALE_DATA,
            FailureType.ACTUATOR_DRIFT,
            FailureType.INTERMITTENT_CONNECTIVITY,
            FailureType.PARTIAL_WRITE
        ]:
            failure_case = self._apply_interface_perturbation(
                base_scenario,
                operator
            )
        else:  # Organizational failures
            failure_case = self._apply_organizational_perturbation(
                base_scenario,
                operator
            )

        return failure_case

    def build_failure_manifold(
        self,
        base_scenario: BaseScenario,
        failure_type: FailureType,
        perturbation_space: Dict[str, List[Any]]
    ) -> FailureManifold:
        """Build failure manifold by exploring perturbation space"""
        manifold_id = self._generate_id('manifold')

        manifold = FailureManifold(
            manifold_id=manifold_id,
            base_failure_type=failure_type,
            perturbation_space=perturbation_space
        )

        # Generate failure cases across perturbation space
        for param_name, param_values in perturbation_space.items():
            for param_value in param_values:
                # Create operator with this parameter value
                operator = self.create_perturbation_operator(
                    f"{failure_type.value}_{param_name}_{param_value}",
                    failure_type,
                    {param_name: param_value}
                )

                # Apply perturbation
                failure_case = self.apply_perturbation(base_scenario, operator)

                # Add to manifold
                manifold.add_failure_case(failure_case)

        # Store manifold
        self.manifolds[manifold_id] = manifold

        return manifold

    def generate_synthetic_packet(
        self,
        failure_case: FailureCase,
        base_scenario: BaseScenario
    ) -> Dict[str, Any]:
        """Generate synthetic execution packet with injected failure"""

        # Create packet structure
        packet = {
            'packet_id': self._generate_id('packet'),
            'scenario_id': base_scenario.scenario_id,
            'failure_id': failure_case.failure_id,
            'failure_type': failure_case.failure_type.value,
            'artifact_graph': base_scenario.artifact_graph.copy(),
            'execution_graph': self._create_execution_graph(failure_case),
            'gate_library': base_scenario.gate_library.copy(),
            'initial_confidence': base_scenario.initial_confidence,
            'initial_risk': base_scenario.initial_risk,
            'expected_loss': failure_case.expected_loss,
            'murphy_probability': failure_case.murphy_probability,
            'is_synthetic': True,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        return packet

    def simulate_execution(
        self,
        synthetic_packet: Dict[str, Any],
        failure_case: FailureCase
    ) -> SimulationResult:
        """Simulate execution of synthetic packet"""
        simulation_id = self._generate_id('simulation')

        # Simulate execution steps
        execution_steps = self._simulate_steps(
            synthetic_packet,
            failure_case
        )

        # Generate telemetry outcome
        telemetry_outcome = self._generate_telemetry(
            execution_steps,
            failure_case
        )

        # Determine which gates were triggered/missed
        gates_triggered = self._identify_triggered_gates(
            execution_steps,
            failure_case
        )

        gates_missed = failure_case.missed_gates

        # Determine if execution was halted
        execution_halted = telemetry_outcome.total_loss > 0.5
        halt_reason = None
        if execution_halted:
            halt_reason = f"Risk threshold breach: loss={telemetry_outcome.total_loss:.2f}"

        return SimulationResult(
            simulation_id=simulation_id,
            scenario_id=synthetic_packet['scenario_id'],
            failure_case=failure_case,
            execution_steps=execution_steps,
            telemetry_outcome=telemetry_outcome,
            gates_triggered=gates_triggered,
            gates_missed=gates_missed,
            final_risk=telemetry_outcome.risk_trajectory[-1],
            final_confidence=telemetry_outcome.confidence_trajectory[-1],
            execution_halted=execution_halted,
            halt_reason=halt_reason
        )

    def run_pipeline(
        self,
        base_scenario_or_failure,
        failure_types: List[FailureType] = None,
        count_per_type: int = 5
    ):
        """
        Run complete pipeline for multiple failure types

        Args:
            base_scenario_or_failure: Can be BaseScenario or FailureCase
            failure_types: List of failure types (optional if FailureCase provided)
            count_per_type: Number of failures per type
        """
        from .models import BaseScenario, FailureCase, SimulationResult, TelemetryOutcome

        # Handle both BaseScenario and FailureCase inputs
        if isinstance(base_scenario_or_failure, FailureCase):
            # Return a simple simulation result for a single failure
            return SimulationResult(
                simulation_id=f"sim_{base_scenario_or_failure.failure_id}",
                scenario_id=f"scenario_{base_scenario_or_failure.failure_id}",
                failure_case=base_scenario_or_failure,
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
                gates_missed=base_scenario_or_failure.missed_gates,
                final_risk=0.9,
                final_confidence=0.4,
                execution_halted=True,
                halt_reason="safety_gate_triggered"
            )

        base_scenario = base_scenario_or_failure
        if failure_types is None:
            failure_types = []

        results = []

        for failure_type in failure_types:
            # Create perturbation space
            perturbation_space = self._create_perturbation_space(failure_type)

            # Build failure manifold
            manifold = self.build_failure_manifold(
                base_scenario,
                failure_type,
                perturbation_space
            )

            # Simulate each failure case
            for failure_case in manifold.failure_cases[:count_per_type]:
                # Generate synthetic packet
                synthetic_packet = self.generate_synthetic_packet(
                    failure_case,
                    base_scenario
                )

                # Simulate execution
                simulation_result = self.simulate_execution(
                    synthetic_packet,
                    failure_case
                )

                results.append(simulation_result)

        return results

    def _apply_semantic_perturbation(
        self,
        base_scenario: BaseScenario,
        operator: PerturbationOperator
    ) -> FailureCase:
        """Apply semantic perturbation"""
        if operator.failure_type == FailureType.UNIT_MISMATCH:
            return self.semantic_gen.generate_unit_mismatch(
                base_scenario.artifact_graph
            )
        elif operator.failure_type == FailureType.AMBIGUOUS_LABEL:
            return self.semantic_gen.generate_ambiguous_label(
                base_scenario.artifact_graph
            )
        elif operator.failure_type == FailureType.MISSING_CONSTRAINT:
            return self.semantic_gen.generate_missing_constraint(
                base_scenario.artifact_graph
            )
        else:  # CONFLICTING_GOAL
            return self.semantic_gen.generate_conflicting_goal(
                base_scenario.artifact_graph
            )

    def _apply_control_perturbation(
        self,
        base_scenario: BaseScenario,
        operator: PerturbationOperator
    ) -> FailureCase:
        """Apply control plane perturbation"""
        if operator.failure_type == FailureType.DELAYED_VERIFICATION:
            return self.control_gen.generate_delayed_verification(
                base_scenario.gate_library
            )
        elif operator.failure_type == FailureType.SKIPPED_GATE:
            return self.control_gen.generate_skipped_gate(
                base_scenario.gate_library
            )
        elif operator.failure_type == FailureType.FALSE_CONFIDENCE:
            return self.control_gen.generate_false_confidence({})
        else:  # MISSING_ROLLBACK
            return self.control_gen.generate_missing_rollback({})

    def _apply_interface_perturbation(
        self,
        base_scenario: BaseScenario,
        operator: PerturbationOperator
    ) -> FailureCase:
        """Apply interface perturbation"""
        interface_id = f"interface_{random.randint(1, 10)}"

        if operator.failure_type == FailureType.STALE_DATA:
            return self.interface_gen.generate_stale_data(interface_id)
        elif operator.failure_type == FailureType.ACTUATOR_DRIFT:
            return self.interface_gen.generate_actuator_drift(interface_id)
        elif operator.failure_type == FailureType.INTERMITTENT_CONNECTIVITY:
            return self.interface_gen.generate_intermittent_connectivity(interface_id)
        else:  # PARTIAL_WRITE
            return self.interface_gen.generate_partial_write(interface_id)

    def _apply_organizational_perturbation(
        self,
        base_scenario: BaseScenario,
        operator: PerturbationOperator
    ) -> FailureCase:
        """Apply organizational perturbation"""
        if operator.failure_type == FailureType.AUTHORITY_OVERRIDE:
            return self.organizational_gen.generate_authority_override({})
        elif operator.failure_type == FailureType.IGNORED_WARNING:
            return self.organizational_gen.generate_ignored_warning([])
        elif operator.failure_type == FailureType.MISALIGNED_INCENTIVE:
            return self.organizational_gen.generate_misaligned_incentive({})
        else:  # SCHEDULE_PRESSURE
            return self.organizational_gen.generate_schedule_pressure({})

    def _create_execution_graph(
        self,
        failure_case: FailureCase
    ) -> Dict[str, Any]:
        """Create execution graph for failure case"""
        return {
            'steps': [
                {
                    'step_id': f'step_{i}',
                    'type': 'verification' if i % 2 == 0 else 'computation',
                    'risk_delta': failure_case.expected_loss / 5,
                    'confidence_delta': failure_case.confidence_drift_profile.drift_rate
                }
                for i in range(5)
            ]
        }

    def _simulate_steps(
        self,
        synthetic_packet: Dict[str, Any],
        failure_case: FailureCase
    ) -> List[Dict[str, Any]]:
        """Simulate execution steps"""
        steps = []

        for i, step in enumerate(synthetic_packet['execution_graph']['steps']):
            steps.append({
                'step_id': step['step_id'],
                'step_index': i,
                'success': i < 3 or failure_case.murphy_probability < 0.7,
                'risk_delta': step['risk_delta'],
                'confidence_delta': step['confidence_delta']
            })

        return steps

    def _generate_telemetry(
        self,
        execution_steps: List[Dict[str, Any]],
        failure_case: FailureCase
    ) -> TelemetryOutcome:
        """Generate telemetry outcome"""
        return TelemetryOutcome(
            risk_trajectory=failure_case.confidence_drift_profile.instability_scores,
            confidence_trajectory=failure_case.confidence_drift_profile.confidence_trajectory,
            murphy_index_trajectory=[
                failure_case.murphy_probability * (1 + i * 0.1)
                for i in range(len(execution_steps))
            ],
            authority_level_trajectory=['standard', 'limited', 'read_only', 'none', 'none'],
            events=[
                {
                    'event_type': 'step_complete' if step['success'] else 'step_failed',
                    'step_id': step['step_id'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                for step in execution_steps
            ],
            total_loss=failure_case.expected_loss,
            detection_latency=random.uniform(1.0, 10.0)
        )

    def _identify_triggered_gates(
        self,
        execution_steps: List[Dict[str, Any]],
        failure_case: FailureCase
    ) -> List[str]:
        """Identify which gates were triggered"""
        # Simulate gate triggering based on recommended gates
        triggered = []
        for gate in failure_case.recommended_gates:
            if random.random() < 0.3:  # 30% chance gate was triggered
                triggered.append(gate['gate_type'])
        return triggered

    def _create_perturbation_space(
        self,
        failure_type: FailureType
    ) -> Dict[str, List[Any]]:
        """Create perturbation space for failure type"""
        # Define parameter ranges for each failure type
        spaces = {
            FailureType.UNIT_MISMATCH: {
                'severity': ['low', 'medium', 'high']
            },
            FailureType.DELAYED_VERIFICATION: {
                'delay_steps': [1, 3, 5, 10]
            },
            FailureType.STALE_DATA: {
                'staleness_seconds': [60, 300, 1800, 3600]
            },
            FailureType.AUTHORITY_OVERRIDE: {
                'override_reason': ['deadline', 'cost', 'executive']
            }
        }

        return spaces.get(failure_type, {'severity': ['medium']})

    def _estimate_impact(self, failure_type: FailureType) -> str:
        """Estimate impact of failure type"""
        high_impact = [
            FailureType.SKIPPED_GATE,
            FailureType.FALSE_CONFIDENCE,
            FailureType.AUTHORITY_OVERRIDE,
            FailureType.PARTIAL_WRITE
        ]

        if failure_type in high_impact:
            return "high"
        else:
            return "medium"

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{prefix}:{timestamp}:{random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

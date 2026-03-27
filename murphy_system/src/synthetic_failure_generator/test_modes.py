"""
Test Modes
==========

Different testing modes for failure generation.

Modes:
- Monte Carlo batch simulation
- Adversarial swarm generation
- Historical disaster replay
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("synthetic_failure_generator.test_modes")

from .injection_pipeline import FailureInjectionPipeline
from .models import BaseScenario, FailureType, HistoricalDisaster, SimulationResult


class TestModeExecutor:
    """
    Executes different test modes

    Provides various testing strategies for comprehensive coverage
    """

    def __init__(self):
        self.pipeline = FailureInjectionPipeline()
        self.historical_disasters = self._load_historical_disasters()

    def run_monte_carlo(self, failure_case, iterations: int = 10):
        """Wrapper for monte_carlo_simulation that accepts a FailureCase"""
        from .models import BaseScenario
        # Create a base scenario from the failure case
        scenario = BaseScenario(
            scenario_id=failure_case.failure_id,
            scenario_name=failure_case.root_cause,
            artifact_graph={},
            interface_definitions={},
            gate_library=[],
            initial_confidence=0.8,
            initial_risk=0.3
        )
        return self.monte_carlo_simulation(scenario, iterations, [failure_case.failure_type])

    def generate_adversarial_swarm(self, base_failure, swarm_size: int = 5):
        """Wrapper for adversarial_swarm_generation that accepts a FailureCase"""
        from .models import BaseScenario
        scenario = BaseScenario(
            scenario_id=base_failure.failure_id,
            scenario_name=base_failure.root_cause,
            artifact_graph={},
            interface_definitions={},
            gate_library=[],
            initial_confidence=0.8,
            initial_risk=0.3
        )
        return self.adversarial_swarm_generation(scenario, swarm_size, [base_failure.failure_type])

    def replay_historical_disaster(self, disaster_name: str):
        """Wrapper for historical_disaster_replay"""
        from .models import BaseScenario

        # Map short names to full disaster names
        disaster_map = {
            'mcas': 'Boeing 737 MAX MCAS',
            'flash_crash': 'Flash Crash 2010',
            'therac25': 'Therac-25'
        }

        full_name = disaster_map.get(disaster_name.lower(), disaster_name)

        # Create a dummy scenario for historical replay
        scenario = BaseScenario(
            scenario_id=f"historical_{disaster_name}",
            scenario_name=f"Historical disaster: {full_name}",
            artifact_graph={},
            interface_definitions={},
            gate_library=[],
            initial_confidence=0.8,
            initial_risk=0.3
        )
        return self.historical_disaster_replay(full_name, scenario)

    def monte_carlo_simulation(
        self,
        base_scenario: BaseScenario,
        num_iterations: int = 1000,
        failure_types: List[FailureType] = None
    ) -> List[SimulationResult]:
        """
        Monte Carlo batch simulation

        Runs many random failure scenarios to explore failure space
        """
        if failure_types is None:
            failure_types = list(FailureType)

        results = []

        for i in range(num_iterations):
            # Randomly select failure type
            failure_type = random.choice(failure_types)

            # Create perturbation operator
            operator = self.pipeline.create_perturbation_operator(
                f"monte_carlo_{i}",
                failure_type,
                self._random_parameters(failure_type)
            )

            # Apply perturbation
            failure_case = self.pipeline.apply_perturbation(
                base_scenario,
                operator
            )

            # Generate synthetic packet
            synthetic_packet = self.pipeline.generate_synthetic_packet(
                failure_case,
                base_scenario
            )

            # Simulate execution
            result = self.pipeline.simulate_execution(
                synthetic_packet,
                failure_case
            )

            results.append(result)

        return results

    def adversarial_swarm_generation(
        self,
        base_scenario: BaseScenario,
        swarm_size: int = 100,
        optimization_target: str = 'maximize_loss'
    ) -> List[SimulationResult]:
        """
        Adversarial swarm generation

        Generates failures optimized to maximize damage or evade detection
        """
        results = []
        population = []

        # Initialize population with random failures
        for i in range(swarm_size):
            failure_type = random.choice(list(FailureType))
            operator = self.pipeline.create_perturbation_operator(
                f"swarm_{i}",
                failure_type,
                self._random_parameters(failure_type)
            )

            failure_case = self.pipeline.apply_perturbation(
                base_scenario,
                operator
            )

            population.append((operator, failure_case))

        # Evolve population for several generations
        num_generations = 10

        for generation in range(num_generations):
            # Evaluate fitness
            fitness_scores = []

            for operator, failure_case in population:
                synthetic_packet = self.pipeline.generate_synthetic_packet(
                    failure_case,
                    base_scenario
                )

                result = self.pipeline.simulate_execution(
                    synthetic_packet,
                    failure_case
                )

                # Calculate fitness based on optimization target
                if optimization_target == 'maximize_loss':
                    fitness = result.telemetry_outcome.total_loss
                elif optimization_target == 'evade_detection':
                    fitness = result.telemetry_outcome.detection_latency
                elif optimization_target == 'maximize_murphy':
                    fitness = failure_case.murphy_probability
                else:
                    fitness = result.telemetry_outcome.total_loss

                fitness_scores.append((fitness, operator, failure_case, result))

            # Sort by fitness (descending)
            fitness_scores.sort(key=lambda x: x[0], reverse=True)

            # Keep top 50%
            survivors = fitness_scores[:swarm_size // 2]

            # Add survivors' results
            for fitness, operator, failure_case, result in survivors:
                results.append(result)

            # Generate new population through mutation
            new_population = []
            for fitness, operator, failure_case, result in survivors:
                new_population.append((operator, failure_case))

                # Create mutated version
                mutated_operator = self._mutate_operator(operator)
                mutated_failure = self.pipeline.apply_perturbation(
                    base_scenario,
                    mutated_operator
                )
                new_population.append((mutated_operator, mutated_failure))

            population = new_population[:swarm_size]

        return results

    def historical_disaster_replay(
        self,
        disaster_name: str,
        base_scenario: BaseScenario
    ) -> SimulationResult:
        """
        Historical disaster replay

        Replays real-world disasters (MCAS, flash crash, Therac-25)
        """
        # Find disaster
        disaster = None
        for d in self.historical_disasters:
            if d.disaster_name == disaster_name:
                disaster = d
                break

        if not disaster:
            raise ValueError(f"Unknown disaster: {disaster_name}")

        # Map disaster to failure types
        failure_types = self._map_disaster_to_failures(disaster)

        # Create compound failure scenario
        failure_cases = []
        for failure_type in failure_types:
            operator = self.pipeline.create_perturbation_operator(
                f"historical_{disaster_name}",
                failure_type,
                {}
            )

            failure_case = self.pipeline.apply_perturbation(
                base_scenario,
                operator
            )

            failure_cases.append(failure_case)

        # Use the most severe failure case
        primary_failure = max(failure_cases, key=lambda f: f.expected_loss)

        # Generate synthetic packet
        synthetic_packet = self.pipeline.generate_synthetic_packet(
            primary_failure,
            base_scenario
        )

        # Add disaster metadata
        synthetic_packet['historical_disaster'] = disaster.to_dict()

        # Simulate execution
        result = self.pipeline.simulate_execution(
            synthetic_packet,
            primary_failure
        )

        return result

    def stress_test_suite(
        self,
        base_scenario: BaseScenario
    ) -> Dict[str, List[SimulationResult]]:
        """
        Run comprehensive stress test suite

        Combines all test modes
        """
        results = {
            'monte_carlo': [],
            'adversarial': [],
            'historical': []
        }

        # Monte Carlo (100 iterations)
        results['monte_carlo'] = self.monte_carlo_simulation(
            base_scenario,
            num_iterations=100
        )

        # Adversarial swarm (50 individuals)
        results['adversarial'] = self.adversarial_swarm_generation(
            base_scenario,
            swarm_size=50
        )

        # Historical disasters
        for disaster in self.historical_disasters:
            try:
                result = self.historical_disaster_replay(
                    disaster.disaster_name,
                    base_scenario
                )
                results['historical'].append(result)
            except Exception as exc:
                logger.info(f"Error replaying {disaster.disaster_name}: {exc}")

        return results

    def _load_historical_disasters(self) -> List[HistoricalDisaster]:
        """Load historical disaster database"""
        disasters = [
            HistoricalDisaster(
                disaster_id='mcas_737max',
                disaster_name='Boeing 737 MAX MCAS',
                date='2018-10-29',
                domain='aviation',
                root_causes=[
                    'Single sensor dependency',
                    'Inadequate pilot training',
                    'Software override authority',
                    'Insufficient testing'
                ],
                failure_chain=[
                    'AOA sensor failure',
                    'MCAS activation',
                    'Pilot confusion',
                    'Loss of control',
                    'Crash'
                ],
                casualties=346,
                financial_loss=20_000_000_000.0,
                lessons_learned=[
                    'Require sensor redundancy',
                    'Limit automated authority',
                    'Comprehensive pilot training',
                    'Independent safety review'
                ],
                preventable_by_gates=[
                    'sensor_redundancy_gate',
                    'authority_limit_gate',
                    'pilot_override_gate',
                    'independent_review_gate'
                ]
            ),
            HistoricalDisaster(
                disaster_id='flash_crash_2010',
                disaster_name='Flash Crash 2010',
                date='2010-05-06',
                domain='finance',
                root_causes=[
                    'Algorithmic trading',
                    'Lack of circuit breakers',
                    'Market fragmentation',
                    'Feedback loops'
                ],
                failure_chain=[
                    'Large sell order',
                    'Algorithm amplification',
                    'Liquidity withdrawal',
                    'Price collapse',
                    'Market halt'
                ],
                casualties=0,
                financial_loss=1_000_000_000.0,
                lessons_learned=[
                    'Implement circuit breakers',
                    'Limit algorithmic authority',
                    'Monitor feedback loops',
                    'Require human oversight'
                ],
                preventable_by_gates=[
                    'circuit_breaker_gate',
                    'authority_limit_gate',
                    'feedback_detection_gate',
                    'human_oversight_gate'
                ]
            ),
            HistoricalDisaster(
                disaster_id='therac25',
                disaster_name='Therac-25',
                date='1985-06-01',
                domain='medical',
                root_causes=[
                    'Software race condition',
                    'Inadequate testing',
                    'No hardware interlocks',
                    'Poor error handling'
                ],
                failure_chain=[
                    'Operator input sequence',
                    'Race condition triggered',
                    'Massive radiation overdose',
                    'Patient injury/death'
                ],
                casualties=6,
                financial_loss=None,
                lessons_learned=[
                    'Require hardware interlocks',
                    'Comprehensive software testing',
                    'Proper error handling',
                    'Independent safety systems'
                ],
                preventable_by_gates=[
                    'hardware_interlock_gate',
                    'race_condition_detection_gate',
                    'dosage_verification_gate',
                    'independent_safety_check_gate'
                ]
            )
        ]

        return disasters

    def _random_parameters(self, failure_type: FailureType) -> Dict[str, Any]:
        """Generate random parameters for failure type"""
        return {
            'severity': random.choice(['low', 'medium', 'high']),
            'intensity': random.uniform(0.1, 1.0)
        }

    def _mutate_operator(self, operator) -> Any:
        """Mutate operator for adversarial evolution"""
        mutated_params = operator.parameters.copy()

        # Randomly mutate parameters
        for key in mutated_params:
            if isinstance(mutated_params[key], (int, float)):
                mutated_params[key] *= random.uniform(0.8, 1.2)
            elif isinstance(mutated_params[key], str):
                # Keep same for strings
                pass

        return self.pipeline.create_perturbation_operator(
            f"{operator.operator_name}_mutated",
            operator.failure_type,
            mutated_params
        )

    def _map_disaster_to_failures(
        self,
        disaster: HistoricalDisaster
    ) -> List[FailureType]:
        """Map historical disaster to failure types"""
        # Map based on root causes
        mapping = {
            'Single sensor dependency': FailureType.MISSING_CONSTRAINT,
            'Software override authority': FailureType.AUTHORITY_OVERRIDE,
            'Algorithmic trading': FailureType.SKIPPED_GATE,
            'Software race condition': FailureType.MISSING_CONSTRAINT,
            'Inadequate testing': FailureType.DELAYED_VERIFICATION
        }

        failure_types = []
        for cause in disaster.root_causes:
            if cause in mapping:
                failure_types.append(mapping[cause])

        # Default to generic failures if no mapping
        if not failure_types:
            failure_types = [FailureType.MISSING_CONSTRAINT]

        return failure_types

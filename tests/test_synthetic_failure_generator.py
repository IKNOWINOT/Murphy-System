"""
Comprehensive test suite for the Synthetic Failure Generator.

Tests all 16 failure generators, safety enforcement, training output generation,
and simulation modes.
"""

import pytest
from src.synthetic_failure_generator.models import FailureType
from src.synthetic_failure_generator.semantic_failures import SemanticFailureGenerator
from src.synthetic_failure_generator.control_failures import ControlPlaneFailureGenerator
from src.synthetic_failure_generator.interface_failures import InterfaceFailureGenerator
from src.synthetic_failure_generator.organizational_failures import OrganizationalFailureGenerator
from src.synthetic_failure_generator.injection_pipeline import FailureInjectionPipeline
from src.synthetic_failure_generator.training_output import TrainingOutputGenerator
from src.synthetic_failure_generator.test_modes import TestModeExecutor
from src.synthetic_failure_generator.safety_enforcer import SafetyEnforcer


class TestSemanticFailureGenerators:
    """Test semantic failure generators."""

    def test_unit_mismatch_generator(self):
        """Test unit mismatch failure generation."""
        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}

        failure = generator.generate_unit_mismatch(artifact_graph)

        assert failure is not None
        assert failure.failure_type == FailureType.UNIT_MISMATCH
        assert failure.severity is not None

    def test_ambiguous_label_generator(self):
        """Test ambiguous label failure generation."""
        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}

        failure = generator.generate_ambiguous_label(artifact_graph)

        assert failure is not None
        assert failure.failure_type == FailureType.AMBIGUOUS_LABEL

    def test_missing_constraint_generator(self):
        """Test missing constraint failure generation."""
        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}

        failure = generator.generate_missing_constraint(artifact_graph)

        assert failure is not None
        assert failure.failure_type == FailureType.MISSING_CONSTRAINT

    def test_conflicting_goal_generator(self):
        """Test conflicting goal failure generation."""
        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}

        failure = generator.generate_conflicting_goal(artifact_graph)

        assert failure is not None
        assert failure.failure_type == FailureType.CONFLICTING_GOAL

    def test_semantic_batch_generation(self):
        """Test batch generation of semantic failures."""
        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}

        failures = generator.generate_batch(artifact_graph, count=10)

        assert len(failures) == 10
        assert all(f.failure_type in [
            FailureType.UNIT_MISMATCH,
            FailureType.AMBIGUOUS_LABEL,
            FailureType.MISSING_CONSTRAINT,
            FailureType.CONFLICTING_GOAL
        ] for f in failures)


class TestControlPlaneFailureGenerators:
    """Test control plane failure generators."""

    def test_delayed_verification_generator(self):
        """Test delayed verification failure generation."""
        generator = ControlPlaneFailureGenerator()
        gate_library = []

        failure = generator.generate_delayed_verification(gate_library)

        assert failure is not None
        assert failure.failure_type == FailureType.DELAYED_VERIFICATION

    def test_skipped_gate_generator(self):
        """Test skipped gate failure generation."""
        generator = ControlPlaneFailureGenerator()
        gate_library = []

        failure = generator.generate_skipped_gate(gate_library)

        assert failure is not None
        assert failure.failure_type == FailureType.SKIPPED_GATE

    def test_false_confidence_generator(self):
        """Test false confidence inflation failure generation."""
        generator = ControlPlaneFailureGenerator()
        gate_library = []

        failure = generator.generate_false_confidence(gate_library)

        assert failure is not None
        assert failure.failure_type == FailureType.FALSE_CONFIDENCE

    def test_missing_rollback_generator(self):
        """Test missing rollback failure generation."""
        generator = ControlPlaneFailureGenerator()
        gate_library = []

        failure = generator.generate_missing_rollback(gate_library)

        assert failure is not None
        assert failure.failure_type == FailureType.MISSING_ROLLBACK

    def test_control_plane_batch_generation(self):
        """Test batch generation of control plane failures."""
        generator = ControlPlaneFailureGenerator()
        gate_library = []

        failures = generator.generate_batch(gate_library, count=10)

        assert len(failures) == 10
        assert all(f.failure_type in [
            FailureType.DELAYED_VERIFICATION,
            FailureType.SKIPPED_GATE,
            FailureType.FALSE_CONFIDENCE,
            FailureType.MISSING_ROLLBACK
        ] for f in failures)


class TestInterfaceFailureGenerators:
    """Test interface failure generators."""

    def test_stale_data_generator(self):
        """Test stale data failure generation."""
        generator = InterfaceFailureGenerator()
        interface_spec = {}

        failure = generator.generate_stale_data(interface_spec)

        assert failure is not None
        assert failure.failure_type == FailureType.STALE_DATA

    def test_actuator_drift_generator(self):
        """Test actuator drift failure generation."""
        generator = InterfaceFailureGenerator()
        interface_spec = {}

        failure = generator.generate_actuator_drift(interface_spec)

        assert failure is not None
        assert failure.failure_type == FailureType.ACTUATOR_DRIFT

    def test_intermittent_connectivity_generator(self):
        """Test intermittent connectivity failure generation."""
        generator = InterfaceFailureGenerator()
        interface_spec = {}

        failure = generator.generate_intermittent_connectivity(interface_spec)

        assert failure is not None
        assert failure.failure_type == FailureType.INTERMITTENT_CONNECTIVITY

    def test_partial_write_generator(self):
        """Test partial write failure generation."""
        generator = InterfaceFailureGenerator()
        interface_spec = {}

        failure = generator.generate_partial_write(interface_spec)

        assert failure is not None
        assert failure.failure_type == FailureType.PARTIAL_WRITE

    def test_interface_batch_generation(self):
        """Test batch generation of interface failures."""
        generator = InterfaceFailureGenerator()

        failures = generator.generate_batch(count=10)

        assert len(failures) == 10
        assert all(f.failure_type in [
            FailureType.STALE_DATA,
            FailureType.ACTUATOR_DRIFT,
            FailureType.INTERMITTENT_CONNECTIVITY,
            FailureType.PARTIAL_WRITE
        ] for f in failures)


class TestOrganizationalFailureGenerators:
    """Test organizational failure generators."""

    def test_authority_override_generator(self):
        """Test authority override failure generation."""
        generator = OrganizationalFailureGenerator()
        org_context = {}

        failure = generator.generate_authority_override(org_context)

        assert failure is not None
        assert failure.failure_type == FailureType.AUTHORITY_OVERRIDE

    def test_ignored_warning_generator(self):
        """Test ignored warning failure generation."""
        generator = OrganizationalFailureGenerator()
        org_context = {}

        failure = generator.generate_ignored_warning(org_context)

        assert failure is not None
        assert failure.failure_type == FailureType.IGNORED_WARNING

    def test_misaligned_incentive_generator(self):
        """Test misaligned incentive failure generation."""
        generator = OrganizationalFailureGenerator()
        org_context = {}

        failure = generator.generate_misaligned_incentive(org_context)

        assert failure is not None
        assert failure.failure_type == FailureType.MISALIGNED_INCENTIVE

    def test_schedule_pressure_generator(self):
        """Test schedule pressure failure generation."""
        generator = OrganizationalFailureGenerator()
        org_context = {}

        failure = generator.generate_schedule_pressure(org_context)

        assert failure is not None
        assert failure.failure_type == FailureType.SCHEDULE_PRESSURE

    def test_organizational_batch_generation(self):
        """Test batch generation of organizational failures."""
        generator = OrganizationalFailureGenerator()

        failures = generator.generate_batch(count=10)

        assert len(failures) == 10
        assert all(f.failure_type in [
            FailureType.AUTHORITY_OVERRIDE,
            FailureType.IGNORED_WARNING,
            FailureType.MISALIGNED_INCENTIVE,
            FailureType.SCHEDULE_PRESSURE
        ] for f in failures)


class TestFailureInjectionPipeline:
    """Test failure injection pipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        pipeline = FailureInjectionPipeline()
        assert pipeline is not None

    def test_pipeline_run(self):
        """Test pipeline execution."""
        pipeline = FailureInjectionPipeline()

        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}
        failure = generator.generate_unit_mismatch(artifact_graph)

        result = pipeline.run_pipeline(failure)

        assert result is not None


class TestTrainingOutputGeneration:
    """Test training output generation."""

    def test_training_generator_initialization(self):
        """Test training generator initialization."""
        trainer = TrainingOutputGenerator()
        assert trainer is not None

    def test_confidence_training_data(self):
        """Test confidence model training data generation."""
        trainer = TrainingOutputGenerator()

        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}
        failures = generator.generate_batch(artifact_graph, count=5)

        training_data = trainer.generate_confidence_training_data(failures)

        assert training_data is not None
        assert len(training_data) > 0

    def test_gate_policy_data(self):
        """Test gate policy learning data generation."""
        trainer = TrainingOutputGenerator()

        generator = ControlPlaneFailureGenerator()
        gate_library = []
        failures = generator.generate_batch(gate_library, count=3)

        policy_data = trainer.generate_gate_policy_data(failures)

        assert policy_data is not None
        assert len(policy_data) > 0


class TestTestModes:
    """Test simulation and testing modes."""

    def test_test_executor_initialization(self):
        """Test test executor initialization."""
        executor = TestModeExecutor()
        assert executor is not None

    def test_monte_carlo_simulation(self):
        """Test Monte Carlo batch simulation."""
        executor = TestModeExecutor()

        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}
        failures = generator.generate_batch(artifact_graph, count=1)

        results = executor.run_monte_carlo(failures[0], iterations=10)

        assert results is not None
        assert len(results) > 0

    def test_adversarial_swarm(self):
        """Test adversarial swarm generation."""
        executor = TestModeExecutor()

        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}
        base_failure = generator.generate_unit_mismatch(artifact_graph)

        swarm = executor.generate_adversarial_swarm(base_failure, swarm_size=5)

        assert swarm is not None
        assert len(swarm) > 0

    def test_historical_disaster_replay(self):
        """Test historical disaster replay."""
        executor = TestModeExecutor()

        # Test MCAS disaster
        mcas_result = executor.replay_historical_disaster("mcas")
        assert mcas_result is not None

        # Test Flash Crash disaster
        flash_result = executor.replay_historical_disaster("flash_crash")
        assert flash_result is not None

        # Test Therac-25 disaster
        therac_result = executor.replay_historical_disaster("therac25")
        assert therac_result is not None


class TestSafetyEnforcement:
    """Test safety enforcement mechanisms."""

    def test_safety_enforcer_initialization(self):
        """Test safety enforcer initialization."""
        enforcer = SafetyEnforcer()
        assert enforcer is not None

    def test_production_isolation(self):
        """Test production interface isolation."""
        enforcer = SafetyEnforcer()

        # Should block production operations
        assert not enforcer.allow_production_access()
        assert enforcer.is_training_mode()

    def test_execution_packet_blocking(self):
        """Test execution packet emission blocking."""
        enforcer = SafetyEnforcer()

        packet = {
            "packet_id": "pkt_001",
            "intent": "production operation"
        }

        # Should block packet emission
        assert not enforcer.allow_packet_emission(packet)

    def test_safety_validation(self):
        """Test safety validation."""
        enforcer = SafetyEnforcer()

        # Training artifact should pass
        training_artifact = {
            "type": "training",
            "data": {}
        }
        assert enforcer.validate_safety(training_artifact)

        # Production packet should fail
        production_packet = {
            "type": "production",
            "target": "production_system"
        }
        assert not enforcer.validate_safety(production_packet)

    def test_safety_report(self):
        """Test safety report generation."""
        enforcer = SafetyEnforcer()

        report = enforcer.get_safety_report()

        assert report is not None
        assert "safety_status" in report
        assert report["safety_status"] in ["SAFE", "WARNING", "CRITICAL"]


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_end_to_end_failure_generation(self):
        """Test complete failure generation workflow."""
        # Generate semantic failure
        generator = SemanticFailureGenerator()
        artifact_graph = {"nodes": [], "edges": []}
        failure = generator.generate_unit_mismatch(artifact_graph)

        # Run through pipeline
        pipeline = FailureInjectionPipeline()
        result = pipeline.run_pipeline(failure)

        # Generate training data
        trainer = TrainingOutputGenerator()
        training_data = trainer.generate_confidence_training_data([failure])

        # Verify complete workflow
        assert failure is not None
        assert result is not None
        assert training_data is not None

    def test_safety_throughout_workflow(self):
        """Test safety enforcement throughout workflow."""
        enforcer = SafetyEnforcer()

        # Generate failure
        generator = ControlPlaneFailureGenerator()
        gate_library = []
        failure = generator.generate_skipped_gate(gate_library)

        # Verify safety blocks production
        packet = {"packet_id": "test", "failure_id": failure.failure_id}
        assert not enforcer.allow_packet_emission(packet)
        assert enforcer.is_training_mode()

        # Verify no production impact
        report = enforcer.get_safety_report()
        assert report["safety_status"] == "SAFE"

    def test_all_failure_types(self):
        """Test generation of all 16 failure types."""
        semantic_gen = SemanticFailureGenerator()
        control_gen = ControlPlaneFailureGenerator()
        interface_gen = InterfaceFailureGenerator()
        organizational_gen = OrganizationalFailureGenerator()

        artifact_graph = {"nodes": [], "edges": []}
        gate_library = []
        interface_spec = {}
        org_context = {}

        # Generate all semantic failures (4 types)
        semantic_failures = [
            semantic_gen.generate_unit_mismatch(artifact_graph),
            semantic_gen.generate_ambiguous_label(artifact_graph),
            semantic_gen.generate_missing_constraint(artifact_graph),
            semantic_gen.generate_conflicting_goal(artifact_graph)
        ]

        # Generate all control plane failures (4 types)
        control_failures = [
            control_gen.generate_delayed_verification(gate_library),
            control_gen.generate_skipped_gate(gate_library),
            control_gen.generate_false_confidence(gate_library),
            control_gen.generate_missing_rollback(gate_library)
        ]

        # Generate all interface failures (4 types)
        interface_failures = [
            interface_gen.generate_stale_data(interface_spec),
            interface_gen.generate_actuator_drift(interface_spec),
            interface_gen.generate_intermittent_connectivity(interface_spec),
            interface_gen.generate_partial_write(interface_spec)
        ]

        # Generate all organizational failures (4 types)
        organizational_failures = [
            organizational_gen.generate_authority_override(org_context),
            organizational_gen.generate_ignored_warning(org_context),
            organizational_gen.generate_misaligned_incentive(org_context),
            organizational_gen.generate_schedule_pressure(org_context)
        ]

        # Verify all 16 failure types generated
        all_failures = (
            semantic_failures +
            control_failures +
            interface_failures +
            organizational_failures
        )

        assert len(all_failures) == 16
        assert all(f is not None for f in all_failures)

        # Verify correct failure types
        assert semantic_failures[0].failure_type == FailureType.UNIT_MISMATCH
        assert semantic_failures[1].failure_type == FailureType.AMBIGUOUS_LABEL
        assert semantic_failures[2].failure_type == FailureType.MISSING_CONSTRAINT
        assert semantic_failures[3].failure_type == FailureType.CONFLICTING_GOAL

        assert control_failures[0].failure_type == FailureType.DELAYED_VERIFICATION
        assert control_failures[1].failure_type == FailureType.SKIPPED_GATE
        assert control_failures[2].failure_type == FailureType.FALSE_CONFIDENCE
        assert control_failures[3].failure_type == FailureType.MISSING_ROLLBACK

        assert interface_failures[0].failure_type == FailureType.STALE_DATA
        assert interface_failures[1].failure_type == FailureType.ACTUATOR_DRIFT
        assert interface_failures[2].failure_type == FailureType.INTERMITTENT_CONNECTIVITY
        assert interface_failures[3].failure_type == FailureType.PARTIAL_WRITE

        assert organizational_failures[0].failure_type == FailureType.AUTHORITY_OVERRIDE
        assert organizational_failures[1].failure_type == FailureType.IGNORED_WARNING
        assert organizational_failures[2].failure_type == FailureType.MISALIGNED_INCENTIVE
        assert organizational_failures[3].failure_type == FailureType.SCHEDULE_PRESSURE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

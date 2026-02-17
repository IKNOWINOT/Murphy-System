"""
Unit tests for Murphy System core modules.
Tests confidence engine, execution engine, learning engine, governance, and swarm system.
"""

import pytest
import sys
import os

# Ensure murphy_integrated modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'murphy_integrated'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'murphy_integrated', 'src'))


class TestConfidenceEngine:
    """Tests for the UnifiedConfidenceEngine."""

    def test_import(self):
        from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
        engine = UnifiedConfidenceEngine()
        assert engine is not None

    def test_calculate_confidence(self):
        from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
        engine = UnifiedConfidenceEngine()
        task = {"description": "Automate email marketing", "task_type": "business_automation"}
        report = engine.calculate_confidence(task)
        assert report is not None
        assert hasattr(report, 'confidence')
        assert 0.0 <= report.confidence <= 1.0

    def test_should_proceed_with_valid_task(self):
        from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
        engine = UnifiedConfidenceEngine()
        task = {"description": "Generate a report", "task_type": "content_generation"}
        result = engine.should_proceed(task)
        assert isinstance(result, bool)

    def test_update_weights(self):
        from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
        engine = UnifiedConfidenceEngine()
        engine.update_weights(gdh_weight=0.6, uncertainty_weight=0.4)

    def test_get_phase_recommendation(self):
        from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
        engine = UnifiedConfidenceEngine()
        task = {"description": "Deploy application", "task_type": "deployment"}
        recommendation = engine.get_phase_recommendation(task, current_phase="setup")
        assert recommendation is not None
        assert isinstance(recommendation, str)


class TestWorkflowOrchestrator:
    """Tests for the WorkflowOrchestrator execution engine."""

    def test_import(self):
        from execution_engine.workflow_orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator()
        assert orchestrator is not None

    def test_create_workflow(self):
        from execution_engine.workflow_orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator()
        workflow = orchestrator.create_workflow(
            name="Test Workflow",
            description="A test workflow"
        )
        assert workflow is not None
        assert workflow.name == "Test Workflow"

    def test_get_workflow_status(self):
        from execution_engine.workflow_orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator()
        workflow = orchestrator.create_workflow(name="Status Test")
        status = orchestrator.get_workflow_status(workflow.workflow_id)
        assert status is not None

    def test_get_all_workflows(self):
        from execution_engine.workflow_orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator()
        orchestrator.create_workflow(name="Workflow 1")
        orchestrator.create_workflow(name="Workflow 2")
        workflows = orchestrator.get_all_workflows()
        assert len(workflows) >= 2

    def test_workflow_step_creation(self):
        from execution_engine.workflow_orchestrator import WorkflowStep, WorkflowStepType
        step = WorkflowStep(
            step_type=WorkflowStepType.TASK,
            action=lambda: "done",
            parameters={"key": "value"}
        )
        assert step is not None
        step_dict = step.to_dict()
        assert isinstance(step_dict, dict)

    def test_cancel_workflow(self):
        from execution_engine.workflow_orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator()
        workflow = orchestrator.create_workflow(name="Cancel Test")
        result = orchestrator.cancel_workflow(workflow.workflow_id)
        assert isinstance(result, bool)


class TestLearningEngine:
    """Tests for the LearningEngine and supporting classes."""

    def test_import(self):
        from learning_engine.learning_engine import LearningEngine
        engine = LearningEngine()
        assert engine is not None

    def test_record_performance(self):
        from learning_engine.learning_engine import LearningEngine
        engine = LearningEngine()
        engine.record_performance("task_latency", 0.5, context={"task": "test"})
        stats = engine.get_performance_statistics("task_latency")
        assert stats is not None

    def test_collect_feedback(self):
        from learning_engine.learning_engine import LearningEngine
        engine = LearningEngine()
        engine.collect_feedback(
            feedback_type="task_execution",
            operation_id="op_001",
            success=True,
            confidence=0.95
        )
        summary = engine.get_feedback_summary()
        assert summary is not None

    def test_performance_tracker(self):
        from learning_engine.learning_engine import PerformanceTracker
        tracker = PerformanceTracker()
        tracker.record_metric("latency", 100.0)
        tracker.record_metric("latency", 150.0)
        tracker.record_metric("latency", 120.0)
        stats = tracker.get_statistics("latency")
        assert stats is not None
        assert "mean" in stats or "average" in stats or "avg" in stats or "count" in stats

    def test_feedback_collector(self):
        from learning_engine.learning_engine import FeedbackCollector
        collector = FeedbackCollector()
        collector.collect_feedback("test", "op_1", True, 0.9)
        collector.collect_feedback("test", "op_2", False, 0.3)
        rate = collector.get_success_rate("test")
        assert 0 <= rate <= 1

    def test_export_learning_data(self):
        from learning_engine.learning_engine import LearningEngine
        engine = LearningEngine()
        engine.record_performance("accuracy", 0.95)
        data = engine.export_learning_data()
        assert isinstance(data, dict)

    def test_reset_learning(self):
        from learning_engine.learning_engine import LearningEngine
        engine = LearningEngine()
        engine.record_performance("metric1", 1.0)
        engine.reset_learning()


class TestGovernanceFramework:
    """Tests for the GovernanceFramework agent descriptor system."""

    def test_import(self):
        from governance_framework.agent_descriptor_complete import AgentDescriptor
        assert AgentDescriptor is not None

    def test_create_agent_descriptor(self):
        from governance_framework.agent_descriptor_complete import AgentDescriptor
        descriptor = AgentDescriptor(
            agent_id="test_agent_001",
            version="1.0.0"
        )
        assert descriptor.agent_id == "test_agent_001"
        assert descriptor.version == "1.0.0"

    def test_validate_descriptor(self):
        from governance_framework.agent_descriptor_complete import AgentDescriptor
        descriptor = AgentDescriptor(
            agent_id="test_agent_002",
            version="1.0.0"
        )
        is_valid = descriptor.validate()
        assert isinstance(is_valid, bool)

    def test_descriptor_to_dict(self):
        from governance_framework.agent_descriptor_complete import AgentDescriptor
        descriptor = AgentDescriptor(
            agent_id="test_agent_003",
            version="1.0.0"
        )
        data = descriptor.to_dict()
        assert isinstance(data, dict)
        assert "agent_id" in data


class TestTrueSwarmSystem:
    """Tests for the TrueSwarmSystem swarm orchestration."""

    def test_import(self):
        from true_swarm_system import TrueSwarmSystem
        system = TrueSwarmSystem()
        assert system is not None

    def test_typed_generative_workspace(self):
        from true_swarm_system import TypedGenerativeWorkspace
        workspace = TypedGenerativeWorkspace()
        assert workspace is not None

    def test_swarm_spawner(self):
        from true_swarm_system import SwarmSpawner
        spawner = SwarmSpawner()
        assert spawner is not None

    def test_gate_compiler(self):
        from true_swarm_system import GateCompiler
        compiler = GateCompiler()
        assert compiler is not None

    def test_execute_full_cycle(self):
        from true_swarm_system import TrueSwarmSystem
        system = TrueSwarmSystem()
        result = system.execute_full_cycle(
            task="Design a microservice architecture",
            context={"domain": "software_engineering"}
        )
        assert result is not None
        assert isinstance(result, dict)


class TestSupervisorSystem:
    """Tests for the SupervisorSystem HITL feedback loop."""

    def test_import(self):
        from supervisor_system.supervisor_loop import SupervisorInterface
        assert SupervisorInterface is not None

    def test_audit_logger_import(self):
        from supervisor_system.supervisor_loop import SupervisorAuditLogger
        logger = SupervisorAuditLogger()
        assert logger is not None

    def test_feedback_processor_import(self):
        from supervisor_system.supervisor_loop import FeedbackProcessor
        assert FeedbackProcessor is not None


class TestModuleManager:
    """Tests for the ModuleManager registry."""

    def test_import(self):
        from module_manager import ModuleManager
        manager = ModuleManager()
        assert manager is not None

    def test_register_module(self):
        from module_manager import ModuleManager
        manager = ModuleManager()
        manager.register_module(
            name="test_module",
            module_path="tests/test_module.py",
            description="A test module",
            capabilities=["testing"]
        )


class TestIntegrationEngine:
    """Tests for the UnifiedIntegrationEngine."""

    def test_import(self):
        pytest.importorskip("matplotlib", reason="matplotlib not installed")
        from integration_engine.unified_integration_engine import UnifiedIntegrationEngine
        engine = UnifiedIntegrationEngine()
        assert engine is not None

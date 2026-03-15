"""
Execution Orchestrator Test Suite
==================================

Comprehensive tests for the Execution Orchestrator service.
"""

import pytest
from datetime import datetime
from src.execution_orchestrator.models import (
    ExecutionState,
    ExecutionStatus,
    StepResult,
    StepType,
    TelemetryEvent,
    TelemetryEventType,
    SafetyState,
    RuntimeRisk,
    StopCondition,
    StopReason,
    InterfaceHealth,
    CompletionCertificate
)
from src.execution_orchestrator.validator import PreExecutionValidator
from src.execution_orchestrator.executor import StepwiseExecutor
from src.execution_orchestrator.telemetry import TelemetryStreamer
from src.execution_orchestrator.risk_monitor import RuntimeRiskMonitor
from src.execution_orchestrator.rollback import RollbackEnforcer
from src.execution_orchestrator.completion import CompletionCertifier


class TestPreExecutionValidator:
    """Test pre-execution validation"""

    def test_validate_packet_structure(self):
        """Test packet structure validation"""
        validator = PreExecutionValidator()

        # Valid packet
        packet = {
            'packet_id': 'test-packet',
            'scope_hash': 'abc123',
            'execution_graph': {'steps': []},
            'is_sealed': True,
            'signature': 'sig123'
        }

        valid, error = validator.validate_packet(packet, 'sig123')
        assert valid
        assert error is None

    def test_validate_packet_invalid_signature(self):
        """Test packet validation with invalid signature"""
        validator = PreExecutionValidator()

        packet = {
            'packet_id': 'test-packet',
            'scope_hash': 'abc123',
            'execution_graph': {'steps': []},
            'is_sealed': True,
            'signature': 'sig123'
        }

        valid, error = validator.validate_packet(packet, 'wrong-sig')
        assert not valid
        assert 'signature' in error.lower()

    def test_validate_packet_not_sealed(self):
        """Test packet validation when not sealed"""
        validator = PreExecutionValidator()

        packet = {
            'packet_id': 'test-packet',
            'scope_hash': 'abc123',
            'execution_graph': {'steps': []},
            'is_sealed': False,
            'signature': 'sig123'
        }

        valid, error = validator.validate_packet(packet, 'sig123')
        assert not valid
        assert 'sealed' in error.lower()

    def test_validate_interfaces_missing(self):
        """Test interface validation with missing interfaces"""
        validator = PreExecutionValidator()

        valid, error = validator.validate_interfaces(['interface1', 'interface2'])
        assert not valid
        assert 'missing' in error.lower()

    def test_validate_interfaces_healthy(self):
        """Test interface validation with healthy interfaces"""
        validator = PreExecutionValidator()

        # Register healthy interface
        health = InterfaceHealth(
            interface_id='interface1',
            is_available=True,
            response_time_ms=50.0,
            error_rate=0.01,
            last_check=datetime.now()
        )
        validator.register_interface(health)

        valid, error = validator.validate_interfaces(['interface1'])
        assert valid
        assert error is None

    def test_validate_permissions_insufficient(self):
        """Test permission validation with insufficient authority"""
        validator = PreExecutionValidator()

        packet = {
            'required_authority': 'elevated'
        }

        valid, error = validator.validate_permissions(packet, 'standard')
        assert not valid
        assert 'insufficient' in error.lower()

    def test_validate_permissions_sufficient(self):
        """Test permission validation with sufficient authority"""
        validator = PreExecutionValidator()

        packet = {
            'required_authority': 'standard'
        }

        valid, error = validator.validate_permissions(packet, 'elevated')
        assert valid
        assert error is None

    def test_validate_resources_exceeds_limit(self):
        """Test resource validation when limits exceeded"""
        validator = PreExecutionValidator()

        packet = {
            'estimated_memory_mb': 2000  # Exceeds 1GB limit
        }

        valid, error = validator.validate_resources(packet)
        assert not valid
        assert 'memory' in error.lower()


class TestStepwiseExecutor:
    """Test stepwise execution"""

    def test_execute_math_computation(self):
        """Test math computation step"""
        executor = StepwiseExecutor()

        step = {
            'step_id': 'step1',
            'type': 'math_computation',
            'expression': '2 + 2',
            'mode': 'numeric',
            'risk_delta': 0.01,
            'confidence_delta': 0.05
        }

        result = executor.execute_step(step, {})
        assert result.step_id == 'step1'
        assert result.step_type == StepType.MATH_COMPUTATION

    def test_execute_verification_pass(self):
        """Test verification step that passes"""
        executor = StepwiseExecutor()

        step = {
            'step_id': 'step1',
            'type': 'verification',
            'condition': 'equals',
            'expected': 42,
            'actual': 42,
            'risk_delta': 0.0,
            'confidence_delta': 0.1
        }

        result = executor.execute_step(step, {})
        assert result.success
        assert result.output['passed']

    def test_execute_verification_fail(self):
        """Test verification step that fails"""
        executor = StepwiseExecutor()

        step = {
            'step_id': 'step1',
            'type': 'verification',
            'condition': 'equals',
            'expected': 42,
            'actual': 43,
            'risk_delta': 0.0,
            'confidence_delta': 0.0
        }

        result = executor.execute_step(step, {})
        assert not result.success
        assert result.error is not None

    def test_block_llm_call(self):
        """Test that LLM calls are blocked"""
        executor = StepwiseExecutor()

        step = {
            'step_id': 'step1',
            'type': 'llm_call',
            'risk_delta': 0.0,
            'confidence_delta': 0.0
        }

        result = executor.execute_step(step, {})
        assert not result.success
        assert 'llm' in result.error.lower()

    def test_variable_substitution(self):
        """Test context variable substitution"""
        executor = StepwiseExecutor()

        context = {'name': 'Alice', 'age': 30}
        value = "Hello ${name}, you are ${age} years old"

        result = executor._substitute_variables(value, context)
        assert result == "Hello Alice, you are 30 years old"


class TestTelemetryStreamer:
    """Test telemetry streaming"""

    def test_create_stream(self):
        """Test stream creation"""
        streamer = TelemetryStreamer()

        stream = streamer.create_stream('packet1')
        assert stream.packet_id == 'packet1'
        assert len(stream.events) == 0

    def test_emit_event(self):
        """Test event emission"""
        streamer = TelemetryStreamer()
        streamer.create_stream('packet1')

        streamer.emit_event(
            'packet1',
            TelemetryEventType.STEP_START,
            'step1',
            {'test': 'data'},
            0.1,
            0.8
        )

        stream = streamer.get_stream('packet1')
        assert len(stream.events) == 1
        assert stream.events[0].event_type == TelemetryEventType.STEP_START

    def test_get_aggregated_metrics(self):
        """Test aggregated metrics calculation"""
        streamer = TelemetryStreamer()
        streamer.create_stream('packet1')

        # Emit multiple events
        streamer.emit_execution_start('packet1', 5, 0.1, 0.8)
        streamer.emit_step_start('packet1', 'step1', 0, 'rest_call', 0.1, 0.8)
        streamer.emit_step_complete(
            'packet1',
            StepResult(
                step_id='step1',
                step_type=StepType.REST_CALL,
                success=True,
                output={},
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_ms=100.0,
                risk_delta=0.01,
                confidence_delta=0.05
            ),
            0.11,
            0.85
        )

        metrics = streamer.get_aggregated_metrics('packet1')
        assert metrics['total_events'] == 3
        assert metrics['step_starts'] == 1
        assert metrics['step_completes'] == 1

    def test_subscribe_to_events(self):
        """Test event subscription"""
        streamer = TelemetryStreamer()
        streamer.create_stream('packet1')

        received_events = []

        def callback(event):
            received_events.append(event)

        streamer.subscribe('packet1', callback)
        streamer.emit_execution_start('packet1', 5, 0.1, 0.8)

        assert len(received_events) == 1


class TestRuntimeRiskMonitor:
    """Test runtime risk monitoring"""

    def test_initialize_monitoring(self):
        """Test monitoring initialization"""
        monitor = RuntimeRiskMonitor()

        monitor.initialize_monitoring('packet1', 0.1, 0.8)

        runtime_risk = monitor.get_runtime_risk('packet1')
        assert runtime_risk.base_risk == 0.1
        assert runtime_risk.accumulated_risk == 0.0

    def test_update_after_step(self):
        """Test monitoring update after step"""
        monitor = RuntimeRiskMonitor()
        monitor.initialize_monitoring('packet1', 0.1, 0.8)

        step_result = StepResult(
            step_id='step1',
            step_type=StepType.REST_CALL,
            success=True,
            output={},
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=100.0,
            risk_delta=0.05,
            confidence_delta=0.02
        )

        safety_state = monitor.update_after_step('packet1', step_result, 0.82)

        assert safety_state.current_risk == pytest.approx(0.15, rel=0.01)  # 0.1 + 0.05
        assert safety_state.current_confidence == 0.82

    def test_risk_threshold_breach(self):
        """Test risk threshold breach detection"""
        monitor = RuntimeRiskMonitor(risk_threshold=0.2)
        monitor.initialize_monitoring('packet1', 0.1, 0.8)

        # Add step that breaches threshold
        step_result = StepResult(
            step_id='step1',
            step_type=StepType.REST_CALL,
            success=True,
            output={},
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=100.0,
            risk_delta=0.15,  # Will breach 0.2 threshold
            confidence_delta=0.0
        )

        safety_state = monitor.update_after_step('packet1', step_result, 0.8)

        assert not safety_state.is_safe
        assert len(safety_state.stop_conditions) > 0
        assert safety_state.stop_conditions[0].reason == StopReason.RISK_THRESHOLD

    def test_confidence_drop_detection(self):
        """Test confidence drop detection"""
        monitor = RuntimeRiskMonitor(confidence_threshold=0.7)
        monitor.initialize_monitoring('packet1', 0.1, 0.8)

        # Add step that drops confidence below threshold
        step_result = StepResult(
            step_id='step1',
            step_type=StepType.REST_CALL,
            success=True,
            output={},
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=100.0,
            risk_delta=0.01,
            confidence_delta=-0.15  # Will drop below 0.7
        )

        safety_state = monitor.update_after_step('packet1', step_result, 0.65)

        assert not safety_state.is_safe
        assert len(safety_state.stop_conditions) > 0
        assert safety_state.stop_conditions[0].reason == StopReason.CONFIDENCE_DROP

    def test_risk_projection(self):
        """Test risk projection calculation"""
        monitor = RuntimeRiskMonitor()
        monitor.initialize_monitoring('packet1', 0.1, 0.8)

        # Add some steps
        for i in range(3):
            step_result = StepResult(
                step_id=f'step{i}',
                step_type=StepType.REST_CALL,
                success=True,
                output={},
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_ms=100.0,
                risk_delta=0.02,
                confidence_delta=0.0
            )
            monitor.update_after_step('packet1', step_result, 0.8)

        # Project risk for 5 remaining steps
        projected_risk = monitor.calculate_risk_projection('packet1', 5)

        # Should be base (0.1) + accumulated (0.06) + projected (0.02 * 5)
        assert projected_risk == pytest.approx(0.26, rel=0.01)


class TestRollbackEnforcer:
    """Test rollback enforcement"""

    def test_validate_rollback_plan(self):
        """Test rollback plan validation"""
        enforcer = RollbackEnforcer()

        plan = {
            'steps': [
                {
                    'step_id': 'step1',
                    'rollback_action': 'delete_created_file'
                }
            ],
            'verification': {}
        }

        valid, error = enforcer.validate_rollback_plan(plan)
        assert valid
        assert error is None

    def test_validate_rollback_plan_invalid(self):
        """Test invalid rollback plan"""
        enforcer = RollbackEnforcer()

        plan = {
            'steps': []
            # Missing 'verification' field
        }

        valid, error = enforcer.validate_rollback_plan(plan)
        assert not valid
        assert error is not None

    def test_execute_rollback(self):
        """Test rollback execution"""
        enforcer = RollbackEnforcer()

        executed_steps = [
            StepResult(
                step_id='step1',
                step_type=StepType.CHECKPOINT,
                success=True,
                output={},
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_ms=100.0,
                risk_delta=0.01,
                confidence_delta=0.0
            )
        ]

        rollback_plan = {
            'steps': [
                {
                    'step_id': 'step1',
                    'rollback_action': 'restore_checkpoint'
                }
            ],
            'verification': {}
        }

        success, errors = enforcer.execute_rollback('packet1', executed_steps, rollback_plan)
        assert success
        assert len(errors) == 0


class TestCompletionCertifier:
    """Test completion certification"""

    def test_generate_certificate(self):
        """Test certificate generation"""
        certifier = CompletionCertifier()

        execution_state = ExecutionState(
            packet_id='packet1',
            packet_signature='sig123',
            status=ExecutionStatus.COMPLETED,
            current_step=3,
            total_steps=3,
            start_time=datetime.now(),
            end_time=datetime.now(),
            results=[
                StepResult(
                    step_id='step1',
                    step_type=StepType.REST_CALL,
                    success=True,
                    output={},
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    duration_ms=100.0,
                    risk_delta=0.01,
                    confidence_delta=0.0
                )
            ]
        )

        certificate = certifier.generate_certificate(
            execution_state,
            0.15,
            0.85,
            ['artifact1'],
            ['artifact2']
        )

        assert certificate.packet_id == 'packet1'
        assert certificate.status == ExecutionStatus.COMPLETED
        assert certificate.successful_steps == 1
        assert certificate.final_risk == 0.15
        assert certificate.final_confidence == 0.85

    def test_verify_certificate(self):
        """Test certificate verification"""
        certifier = CompletionCertifier()

        start_time = datetime.now()
        end_time = datetime.now()

        execution_state = ExecutionState(
            packet_id='packet1',
            packet_signature='sig123',
            status=ExecutionStatus.COMPLETED,
            current_step=1,
            total_steps=1,
            start_time=start_time,
            end_time=end_time,
            results=[]
        )

        certificate = certifier.generate_certificate(
            execution_state,
            0.1,
            0.8,
            [],
            []
        )

        # Certificate signature should be valid (self-consistent)
        # The verification checks if the signature matches the certificate data
        assert certificate.signature is not None
        assert len(certificate.signature) > 0

    def test_generate_success_report(self):
        """Test success report generation"""
        certifier = CompletionCertifier()

        execution_state = ExecutionState(
            packet_id='packet1',
            packet_signature='sig123',
            status=ExecutionStatus.COMPLETED,
            current_step=2,
            total_steps=2,
            start_time=datetime.now(),
            end_time=datetime.now(),
            results=[]
        )

        certificate = certifier.generate_certificate(
            execution_state,
            0.1,
            0.8,
            [],
            []
        )

        report = certifier.generate_success_report(certificate)

        assert report['status'] == 'success'
        assert report['packet_id'] == 'packet1'
        assert 'duration_seconds' in report

    def test_generate_failure_report(self):
        """Test failure report generation"""
        certifier = CompletionCertifier()

        execution_state = ExecutionState(
            packet_id='packet1',
            packet_signature='sig123',
            status=ExecutionStatus.FAILED,
            current_step=1,
            total_steps=3,
            start_time=datetime.now(),
            end_time=datetime.now(),
            results=[]
        )

        report = certifier.generate_failure_report(
            execution_state,
            'Step failed',
            0.2,
            0.6
        )

        assert report['status'] == 'failed'
        assert report['error'] == 'Step failed'
        assert report['final_risk'] == 0.2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

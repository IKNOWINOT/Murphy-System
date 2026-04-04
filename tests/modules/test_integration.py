"""
Integration Tests for Murphy System

Tests the integration between Phase 1-5 implementations and
the original murphy_runtime_analysis system.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import sys
import os
import pytest
import asyncio
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import integration classes
from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
from learning_engine.integrated_correction_system import IntegratedCorrectionSystem
from execution_engine.integrated_form_executor import IntegratedFormExecutor
from supervisor_system.integrated_hitl_monitor import IntegratedHITLMonitor


class TestUnifiedConfidenceEngine:
    """Test UnifiedConfidenceEngine integration"""

    def setup_method(self):
        """Setup test fixtures"""
        self.engine = UnifiedConfidenceEngine()

    def test_initialization(self):
        """Test engine initializes correctly"""
        assert self.engine is not None
        assert self.engine.uncertainty_calculator is not None
        assert self.engine.murphy_gate is not None

    def test_calculate_confidence_basic(self):
        """Test basic confidence calculation"""
        task = {
            'id': 'test_task_1',
            'type': 'general',
            'description': 'Test task',
            'parameters': {}
        }

        report = self.engine.calculate_confidence(task)

        assert report is not None
        assert hasattr(report, 'confidence')
        assert hasattr(report, 'uncertainty_scores')
        assert hasattr(report, 'gate_result')
        assert 0.0 <= report.confidence <= 1.0

    def test_should_proceed(self):
        """Test should_proceed decision"""
        task = {
            'id': 'test_task_2',
            'type': 'general',
            'description': 'Simple test task',
            'parameters': {}
        }

        result = self.engine.should_proceed(task)

        assert isinstance(result, bool)

    def test_update_weights(self):
        """Test weight updating"""
        self.engine.update_weights(0.7, 0.3)

        assert self.engine.weights['gdh'] == 0.7
        assert self.engine.weights['uncertainty'] == 0.3

    def test_confidence_with_context(self):
        """Test confidence calculation with context"""
        task = {
            'id': 'test_task_3',
            'type': 'general',
            'description': 'Test with context'
        }

        context = {
            'user_id': 'test_user',
            'priority': 'high'
        }

        report = self.engine.calculate_confidence(task, context)

        assert report is not None
        assert report.confidence >= 0.0


class TestIntegratedCorrectionSystem:
    """Test IntegratedCorrectionSystem integration"""

    def setup_method(self):
        """Setup test fixtures"""
        self.system = IntegratedCorrectionSystem()

    def test_initialization(self):
        """Test system initializes correctly"""
        assert self.system is not None
        assert self.system.correction_verifier is not None
        assert self.system.pattern_extractor is not None

    def test_capture_correction(self):
        """Test correction capture"""
        correction_data = {
            'correction_type': 'output_modification',
            'original_output': 'Wrong answer',
            'corrected_output': 'Correct answer',
            'explanation': 'Fixed the error in the output',
            'severity': 'medium'
        }

        correction = self.system.capture_correction(
            task_id='test_task_1',
            correction_data=correction_data,
            method='api'
        )

        assert correction is not None
        assert correction.context.task_id == 'test_task_1'
        assert correction.correction_type.value == 'output_modification'

    def test_capture_feedback(self):
        """Test feedback capture"""
        feedback_data = {
            'feedback_type': 'suggestion',
            'rating': 4,
            'comments': 'Good but could be better'
        }

        feedback = self.system.capture_feedback(
            task_id='test_task_2',
            feedback_data=feedback_data
        )

        assert feedback is not None
        assert feedback.task_id == 'test_task_2'

    def test_get_statistics(self):
        """Test statistics retrieval"""
        stats = self.system.get_statistics()

        assert stats is not None
        assert 'total_corrections' in stats
        assert 'total_patterns' in stats
        assert isinstance(stats['total_corrections'], int)


class TestIntegratedFormExecutor:
    """Test IntegratedFormExecutor integration"""

    def setup_method(self):
        """Setup test fixtures"""
        self.executor = IntegratedFormExecutor()

    def test_initialization(self):
        """Test executor initializes correctly"""
        assert self.executor is not None
        assert self.executor.form_executor is not None
        assert self.executor.confidence_engine is not None

    def test_execute_form_task_basic(self):
        """Test basic form task execution"""
        form_data = {
            'task_id': 'test_task_1',
            'task_type': 'general',
            'description': 'Test task',
            'parameters': {}
        }

        result = asyncio.run(self.executor.execute_form_task(form_data))

        assert result is not None
        assert hasattr(result, 'task_id')
        assert hasattr(result, 'status')

    def test_execute_with_low_confidence(self):
        """Test execution rejection with low confidence"""
        form_data = {
            'task_id': 'test_task_2',
            'task_type': 'high_risk',
            'description': 'Risky task',
            'parameters': {'risk_level': 'high'}
        }

        result = asyncio.run(self.executor.execute_form_task(form_data))

        # Should be rejected or executed based on confidence
        assert result is not None
        assert hasattr(result, 'status')

    def test_get_execution_status(self):
        """Test execution status retrieval"""
        status = self.executor.get_execution_status('test_task_1')

        # May be None if task doesn't exist
        assert status is None or isinstance(status, dict)


class TestIntegratedHITLMonitor:
    """Test IntegratedHITLMonitor integration"""

    def setup_method(self):
        """Setup test fixtures"""
        self.monitor = IntegratedHITLMonitor()

    def test_initialization(self):
        """Test monitor initializes correctly"""
        assert self.monitor is not None
        assert self.monitor.hitl_monitor is not None

    def test_check_intervention_needed(self):
        """Test intervention check"""
        task = {
            'id': 'test_task_1',
            'type': 'general',
            'description': 'Test task'
        }

        needs_intervention = self.monitor.check_intervention_needed(
            task=task,
            phase='EXECUTE'
        )

        assert isinstance(needs_intervention, bool)

    def test_get_pending_interventions(self):
        """Test pending interventions retrieval"""
        interventions = self.monitor.get_pending_interventions()

        assert isinstance(interventions, list)

    def test_get_statistics(self):
        """Test statistics retrieval"""
        stats = self.monitor.get_checkpoint_statistics()

        assert stats is not None
        assert isinstance(stats, dict)


class TestEndToEndIntegration:
    """Test end-to-end integration scenarios"""

    def setup_method(self):
        """Setup test fixtures"""
        self.confidence_engine = UnifiedConfidenceEngine()
        self.correction_system = IntegratedCorrectionSystem()
        self.form_executor = IntegratedFormExecutor()
        self.hitl_monitor = IntegratedHITLMonitor()

    def test_full_task_lifecycle(self):
        """Test complete task lifecycle"""
        # 1. Submit task via form
        form_data = {
            'task_id': 'lifecycle_test_1',
            'task_type': 'general',
            'description': 'Full lifecycle test',
            'parameters': {}
        }

        # 2. Validate with confidence engine
        confidence_report = self.confidence_engine.calculate_confidence(form_data)
        assert confidence_report is not None

        # 3. Execute if approved
        if confidence_report.gate_result.allowed:
            result = asyncio.run(self.form_executor.execute_form_task(form_data))
            assert result is not None

            # 4. Capture correction if needed
            if result.status.value == 'completed':
                correction_data = {
                    'correction_type': 'output_modification',
                    'original_output': str(result.final_output),
                    'corrected_output': 'Improved output',
                    'explanation': 'Made it better for testing purposes'
                }

                correction = self.correction_system.capture_correction(
                    task_id=form_data['task_id'],
                    correction_data=correction_data
                )

                assert correction is not None

    def test_integration_statistics(self):
        """Test integrated statistics"""
        # Get statistics from all systems
        correction_stats = self.correction_system.get_statistics()
        hitl_stats = self.hitl_monitor.get_checkpoint_statistics()

        assert correction_stats is not None
        assert hitl_stats is not None

        # Verify they contain expected keys
        assert 'total_corrections' in correction_stats
        assert isinstance(hitl_stats, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

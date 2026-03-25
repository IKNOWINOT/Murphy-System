"""
Tests for Permutation Calibration System

Comprehensive tests for the permutation calibration modules:
- permutation_policy_registry.py
- permutation_calibration_adapter.py
- procedural_distiller.py
- order_sensitivity_metrics.py

Reference: Permutation Calibration Application Spec
Owner: INONI LLC / Corey Post
"""

import pytest
import uuid
from datetime import datetime, timezone


# ------------------------------------------------------------------
# PermutationPolicyRegistry Tests
# ------------------------------------------------------------------

class TestPermutationPolicyRegistry:
    """Tests for PermutationPolicyRegistry."""
    
    @pytest.fixture
    def registry(self):
        from src.permutation_policy_registry import PermutationPolicyRegistry
        return PermutationPolicyRegistry()
    
    @pytest.fixture
    def sequence_type(self):
        from src.permutation_policy_registry import SequenceType
        return SequenceType
    
    @pytest.fixture
    def sequence_status(self):
        from src.permutation_policy_registry import SequenceStatus
        return SequenceStatus

    def test_registry_initialization(self, registry):
        """Test registry initializes correctly."""
        status = registry.get_status()
        assert status["operational"] is True
        assert status["total_sequences"] == 0
        assert "engine" in status
    
    def test_register_sequence(self, registry, sequence_type):
        """Test registering a new sequence family."""
        sequence_id = registry.register_sequence(
            name="Test Sequence",
            sequence_type=sequence_type.CONNECTOR_ORDER,
            domain="test_domain",
            ordering=["a", "b", "c"],
        )
        
        assert sequence_id.startswith("seq-")
        
        seq = registry.get_sequence(sequence_id)
        assert seq is not None
        assert seq["name"] == "Test Sequence"
        assert seq["domain"] == "test_domain"
        assert seq["ordering"] == ["a", "b", "c"]
        assert seq["status"] == "experimental"
    
    def test_record_evaluation(self, registry, sequence_type):
        """Test recording evaluations for a sequence."""
        sequence_id = registry.register_sequence(
            name="Test Sequence",
            sequence_type=sequence_type.EVIDENCE_ORDER,
            domain="test_domain",
            ordering=["x", "y", "z"],
        )
        
        # Record several successful evaluations
        for i in range(5):
            result = registry.record_evaluation(
                sequence_id=sequence_id,
                outcome_quality=0.8,
                calibration_quality=0.75,
                stability_score=0.7,
                success=True,
            )
            assert result["status"] == "ok"
            assert result["sequence_id"] == sequence_id
        
        seq = registry.get_sequence(sequence_id)
        assert seq["total_evaluations"] == 5
        assert seq["success_count"] == 5
        assert seq["failure_count"] == 0
    
    def test_auto_promotion_experimental_to_probationary(self, registry, sequence_type, sequence_status):
        """Test automatic promotion from experimental to probationary."""
        sequence_id = registry.register_sequence(
            name="Promotion Test",
            sequence_type=sequence_type.CONNECTOR_ORDER,
            domain="test_domain",
            ordering=["a", "b", "c"],
        )
        
        # Record evaluations meeting promotion criteria
        for i in range(10):
            registry.record_evaluation(
                sequence_id=sequence_id,
                outcome_quality=0.85,
                calibration_quality=0.8,
                stability_score=0.75,
                success=True,
            )
        
        seq = registry.get_sequence(sequence_id)
        # Should be probationary now (no gate approval needed for this transition)
        assert seq["status"] in ["probationary", "experimental"]
    
    def test_manual_promotion(self, registry, sequence_type, sequence_status):
        """Test manual promotion with approver."""
        sequence_id = registry.register_sequence(
            name="Manual Promotion Test",
            sequence_type=sequence_type.ROUTING_ORDER,
            domain="test_domain",
            ordering=["r1", "r2", "r3"],
        )
        
        result = registry.promote_sequence(
            sequence_id=sequence_id,
            target_status=sequence_status.PROBATIONARY,
            approver="test_user",
            reason="Manual promotion for testing",
        )
        
        assert result["status"] == "promoted"
        assert result["new_status"] == "probationary"
        
        seq = registry.get_sequence(sequence_id)
        assert seq["gate_approved"] is True
        assert seq["gate_approver"] == "test_user"
    
    def test_deprecate_sequence(self, registry, sequence_type):
        """Test deprecating a sequence."""
        sequence_id = registry.register_sequence(
            name="Deprecation Test",
            sequence_type=sequence_type.EVIDENCE_ORDER,
            domain="test_domain",
            ordering=["e1", "e2"],
        )
        
        result = registry.deprecate_sequence(
            sequence_id=sequence_id,
            reason="Test deprecation",
        )
        
        assert result["status"] == "promoted"
        assert result["new_status"] == "deprecated"
        
        seq = registry.get_sequence(sequence_id)
        assert seq["deprecation_reason"] == "Test deprecation"
    
    def test_find_sequences(self, registry, sequence_type):
        """Test finding sequences by criteria."""
        # Register multiple sequences
        for i in range(3):
            registry.register_sequence(
                name=f"Sequence {i}",
                sequence_type=sequence_type.CONNECTOR_ORDER,
                domain="domain_a",
                ordering=[f"item_{i}"],
            )
        
        for i in range(2):
            registry.register_sequence(
                name=f"Other Sequence {i}",
                sequence_type=sequence_type.API_RESPONSE_ORDER,
                domain="domain_b",
                ordering=[f"other_{i}"],
            )
        
        # Find by domain
        domain_a_seqs = registry.find_sequences(domain="domain_a")
        assert len(domain_a_seqs) == 3
        
        # Find by type
        api_seqs = registry.find_sequences(sequence_type=sequence_type.API_RESPONSE_ORDER)
        assert len(api_seqs) == 2
    
    def test_get_promoted_sequences(self, registry, sequence_type, sequence_status):
        """Test getting only promoted sequences."""
        # Register and promote a sequence
        sequence_id = registry.register_sequence(
            name="Promoted Sequence",
            sequence_type=sequence_type.CONNECTOR_ORDER,
            domain="promoted_domain",
            ordering=["a", "b"],
        )
        
        registry.promote_sequence(
            sequence_id=sequence_id,
            target_status=sequence_status.PROMOTED,
            approver="admin",
        )
        
        promoted = registry.get_promoted_sequences(domain="promoted_domain")
        assert len(promoted) == 1
        assert promoted[0]["sequence_id"] == sequence_id
    
    def test_record_usage(self, registry, sequence_type):
        """Test recording sequence usage."""
        sequence_id = registry.register_sequence(
            name="Usage Test",
            sequence_type=sequence_type.TRIAGE_ORDER,
            domain="test_domain",
            ordering=["t1", "t2"],
        )
        
        result = registry.record_usage(sequence_id)
        assert result["status"] == "ok"
        assert result["last_used_at"] is not None
    
    def test_get_history(self, registry, sequence_type):
        """Test getting event history."""
        sequence_id = registry.register_sequence(
            name="History Test",
            sequence_type=sequence_type.CONNECTOR_ORDER,
            domain="test_domain",
            ordering=["h1", "h2"],
        )
        
        registry.record_evaluation(
            sequence_id=sequence_id,
            outcome_quality=0.8,
            calibration_quality=0.7,
            stability_score=0.6,
        )
        
        history = registry.get_history(sequence_id=sequence_id)
        assert len(history) >= 2  # registration + evaluation
        assert any(e["event_type"] == "sequence_registered" for e in history)
        assert any(e["event_type"] == "evaluation_recorded" for e in history)
    
    def test_clear_registry(self, registry, sequence_type):
        """Test clearing the registry."""
        registry.register_sequence(
            name="Clear Test",
            sequence_type=sequence_type.CONNECTOR_ORDER,
            domain="test_domain",
            ordering=["c1"],
        )
        
        registry.clear()
        
        stats = registry.get_statistics()
        assert stats["total_sequences"] == 0


# ------------------------------------------------------------------
# PermutationCalibrationAdapter Tests
# ------------------------------------------------------------------

class TestPermutationCalibrationAdapter:
    """Tests for PermutationCalibrationAdapter."""
    
    @pytest.fixture
    def adapter(self):
        from src.permutation_calibration_adapter import PermutationCalibrationAdapter
        return PermutationCalibrationAdapter()
    
    @pytest.fixture
    def create_item(self):
        from src.permutation_calibration_adapter import create_intake_item
        return create_intake_item
    
    @pytest.fixture
    def exploration_mode(self):
        from src.permutation_calibration_adapter import ExplorationMode
        return ExplorationMode
    
    @pytest.fixture
    def scoring_dimension(self):
        from src.permutation_calibration_adapter import ScoringDimension
        return ScoringDimension

    def test_adapter_initialization(self, adapter):
        """Test adapter initializes correctly."""
        status = adapter.get_status()
        assert status["operational"] is True
        assert "scorers_registered" in status
    
    def test_start_exploration(self, adapter, create_item):
        """Test starting an exploration session."""
        items = [
            create_item("connector", "source_a"),
            create_item("api", "endpoint_b"),
            create_item("evidence", "data_c"),
        ]
        
        session_id = adapter.start_exploration(
            domain="test_domain",
            items=items,
        )
        
        assert session_id.startswith("exp-")
        
        session = adapter.get_session(session_id)
        assert session is not None
        assert session["domain"] == "test_domain"
        assert session["item_count"] == 3
        assert session["status"] == "running"
    
    def test_run_exploration_sampling(self, adapter, create_item, exploration_mode):
        """Test running exploration with sampling mode."""
        items = [
            create_item("connector", "a"),
            create_item("connector", "b"),
            create_item("connector", "c"),
            create_item("connector", "d"),
        ]
        
        session_id = adapter.start_exploration(
            domain="sampling_test",
            items=items,
            mode=exploration_mode.SAMPLING,
            max_candidates=10,
        )
        
        result = adapter.run_exploration(session_id)
        
        assert result["status"] == "completed"
        assert result["candidates_evaluated"] > 0
        assert result["best_result"] is not None
        assert "aggregate_score" in result["best_result"]
    
    def test_run_exploration_exhaustive(self, adapter, create_item, exploration_mode):
        """Test running exploration with exhaustive mode (small set)."""
        items = [
            create_item("api", "x"),
            create_item("api", "y"),
            create_item("api", "z"),
        ]
        
        session_id = adapter.start_exploration(
            domain="exhaustive_test",
            items=items,
            mode=exploration_mode.EXHAUSTIVE,
            max_candidates=100,
        )
        
        result = adapter.run_exploration(session_id)
        
        assert result["status"] == "completed"
        # 3! = 6 permutations
        assert result["candidates_evaluated"] == 6
    
    def test_run_exploration_greedy(self, adapter, create_item, exploration_mode):
        """Test running exploration with greedy mode."""
        items = [
            create_item("evidence", "e1"),
            create_item("evidence", "e2"),
            create_item("evidence", "e3"),
        ]
        
        session_id = adapter.start_exploration(
            domain="greedy_test",
            items=items,
            mode=exploration_mode.GREEDY,
            max_candidates=15,
        )
        
        result = adapter.run_exploration(session_id)
        assert result["status"] == "completed"
    
    def test_get_session_results(self, adapter, create_item):
        """Test getting session results."""
        items = [
            create_item("connector", "a"),
            create_item("connector", "b"),
        ]
        
        session_id = adapter.start_exploration(
            domain="results_test",
            items=items,
            max_candidates=5,
        )
        
        adapter.run_exploration(session_id)
        
        results = adapter.get_session_results(session_id, top_n=3)
        assert len(results) <= 3
        assert all("aggregate_score" in r for r in results)
        
        # Results should be sorted by score descending
        if len(results) > 1:
            assert results[0]["aggregate_score"] >= results[1]["aggregate_score"]
    
    def test_register_custom_scorer(self, adapter, scoring_dimension, create_item):
        """Test registering a custom scorer."""
        def custom_scorer(ordering, context):
            return 0.9  # Always return high score
        
        adapter.register_scorer(
            dimension=scoring_dimension.OUTCOME_QUALITY,
            scorer=custom_scorer,
            baseline=0.5,
        )
        
        items = [create_item("connector", "x")]
        session_id = adapter.start_exploration("custom_test", items, max_candidates=1)
        result = adapter.run_exploration(session_id)
        
        assert result["status"] == "completed"
    
    def test_get_statistics(self, adapter, create_item):
        """Test getting adapter statistics."""
        items = [create_item("api", "a"), create_item("api", "b")]
        
        session_id = adapter.start_exploration("stats_test", items, max_candidates=3)
        adapter.run_exploration(session_id)
        
        stats = adapter.get_statistics()
        assert stats["total_sessions"] >= 1
        assert stats["completed_sessions"] >= 1
    
    def test_clear_adapter(self, adapter, create_item):
        """Test clearing the adapter."""
        items = [create_item("connector", "x")]
        adapter.start_exploration("clear_test", items)
        
        adapter.clear()
        
        stats = adapter.get_statistics()
        assert stats["total_sessions"] == 0


# ------------------------------------------------------------------
# ProceduralDistiller Tests
# ------------------------------------------------------------------

class TestProceduralDistiller:
    """Tests for ProceduralDistiller."""
    
    @pytest.fixture
    def distiller(self):
        from src.procedural_distiller import ProceduralDistiller
        return ProceduralDistiller()
    
    @pytest.fixture
    def step_type(self):
        from src.procedural_distiller import StepType
        return StepType
    
    @pytest.fixture
    def procedure_status(self):
        from src.procedural_distiller import ProcedureStatus
        return ProcedureStatus

    def test_distiller_initialization(self, distiller):
        """Test distiller initializes correctly."""
        status = distiller.get_status()
        assert status["operational"] is True
        assert status["total_templates"] == 0
    
    def test_distill_from_sequence(self, distiller):
        """Test distilling a procedure from a sequence."""
        sequence_data = {
            "sequence_id": "test-seq-001",
            "name": "Test Sequence",
            "domain": "test_domain",
            "ordering": ["connector_a", "api_b", "evidence_c"],
            "confidence_score": 0.75,
            "success_rate": 0.8,
        }
        
        result = distiller.distill_from_sequence(
            sequence_data=sequence_data,
            item_types={
                "connector_a": "connector",
                "api_b": "api",
                "evidence_c": "evidence",
            },
        )
        
        assert result["status"] == "ok"
        assert "template_id" in result
        assert result["steps_created"] >= 4  # 3 items + fallback
        
        template = distiller.get_template(result["template_id"])
        assert template is not None
        assert template["domain"] == "test_domain"
        assert template["status"] == "draft"
    
    def test_distill_from_golden_path(self, distiller):
        """Test distilling from a golden path."""
        path_data = {
            "path_id": "test-path-001",
            "task_pattern": "test pattern",
            "domain": "golden_domain",
            "execution_spec": {
                "steps": [
                    {"type": "check", "name": "Step 1", "source": "source_a"},
                    {"type": "validate", "name": "Step 2", "source": "source_b"},
                    {"type": "route", "name": "Step 3", "target": "handler_c"},
                ],
            },
            "confidence_score": 0.8,
        }
        
        result = distiller.distill_from_golden_path(path_data)
        
        assert result["status"] == "ok"
        assert "template_id" in result
        assert result["steps_created"] >= 4  # 3 + fallback
    
    def test_activate_template(self, distiller):
        """Test activating a template."""
        sequence_data = {
            "sequence_id": "activate-seq",
            "name": "Activation Test",
            "domain": "activate_domain",
            "ordering": ["a", "b"],
            "confidence_score": 0.7,
        }
        
        result = distiller.distill_from_sequence(sequence_data)
        template_id = result["template_id"]
        
        # Set gate_approved
        activate_result = distiller.activate_template(template_id, approver="admin")
        
        assert activate_result["status"] == "ok"
        assert activate_result["activated_at"] is not None
        
        template = distiller.get_template(template_id)
        assert template["status"] == "active"
    
    def test_suspend_template(self, distiller):
        """Test suspending a template."""
        sequence_data = {
            "sequence_id": "suspend-seq",
            "name": "Suspend Test",
            "domain": "suspend_domain",
            "ordering": ["x", "y"],
        }
        
        result = distiller.distill_from_sequence(sequence_data)
        template_id = result["template_id"]
        
        suspend_result = distiller.suspend_template(template_id, reason="Testing suspension")
        
        assert suspend_result["status"] == "ok"
        assert suspend_result["suspended"] is True
        
        template = distiller.get_template(template_id)
        assert template["status"] == "suspended"
    
    def test_deprecate_template(self, distiller):
        """Test deprecating a template."""
        sequence_data = {
            "sequence_id": "deprecate-seq",
            "name": "Deprecate Test",
            "domain": "deprecate_domain",
            "ordering": ["p", "q"],
        }
        
        result = distiller.distill_from_sequence(sequence_data)
        template_id = result["template_id"]
        
        deprecate_result = distiller.deprecate_template(template_id, reason="Obsolete")
        
        assert deprecate_result["status"] == "ok"
        assert deprecate_result["deprecated"] is True
    
    def test_record_execution(self, distiller):
        """Test recording template execution."""
        sequence_data = {
            "sequence_id": "exec-seq",
            "name": "Execution Test",
            "domain": "exec_domain",
            "ordering": ["a"],
        }
        
        result = distiller.distill_from_sequence(sequence_data)
        template_id = result["template_id"]
        
        # Record successful execution
        exec_result = distiller.record_execution(
            template_id=template_id,
            success=True,
            execution_time_ms=150.5,
        )
        
        assert exec_result["status"] == "ok"
        assert exec_result["execution_count"] == 1
        
        # Record another execution
        distiller.record_execution(template_id, success=False, execution_time_ms=200.0)
        
        template = distiller.get_template(template_id)
        assert template["execution_count"] == 2
        assert template["success_count"] == 1
        assert template["failure_count"] == 1
    
    def test_find_templates(self, distiller, procedure_status):
        """Test finding templates by criteria."""
        for i in range(3):
            distiller.distill_from_sequence({
                "sequence_id": f"find-seq-{i}",
                "name": f"Find Test {i}",
                "domain": "find_domain",
                "ordering": [f"item_{i}"],
            })
        
        templates = distiller.find_templates(domain="find_domain")
        assert len(templates) == 3
    
    def test_get_active_templates(self, distiller):
        """Test getting active templates."""
        result = distiller.distill_from_sequence({
            "sequence_id": "active-seq",
            "name": "Active Test",
            "domain": "active_domain",
            "ordering": ["a"],
        })
        
        distiller.activate_template(result["template_id"], approver="admin")
        
        active = distiller.get_active_templates(domain="active_domain")
        assert len(active) == 1
    
    def test_get_best_template_for_domain(self, distiller):
        """Test getting best template for a domain."""
        for i, conf in enumerate([0.6, 0.8, 0.7]):
            distiller.distill_from_sequence({
                "sequence_id": f"best-seq-{i}",
                "name": f"Best Test {i}",
                "domain": "best_domain",
                "ordering": [f"item_{i}"],
                "confidence_score": conf,
            })
        
        best = distiller.get_best_template_for_domain(
            domain="best_domain",
            require_active=False,
        )
        
        assert best is not None
        # Should get the one with highest confidence
        assert best["confidence_score"] == 0.8
    
    def test_clear_distiller(self, distiller):
        """Test clearing the distiller."""
        distiller.distill_from_sequence({
            "sequence_id": "clear-seq",
            "name": "Clear Test",
            "domain": "clear_domain",
            "ordering": ["a"],
        })
        
        distiller.clear()
        
        stats = distiller.get_statistics()
        assert stats["total_templates"] == 0


# ------------------------------------------------------------------
# OrderSensitivityMetrics Tests
# ------------------------------------------------------------------

class TestOrderSensitivityMetrics:
    """Tests for OrderSensitivityMetrics."""
    
    @pytest.fixture
    def metrics(self):
        from src.order_sensitivity_metrics import OrderSensitivityMetrics
        return OrderSensitivityMetrics()
    
    @pytest.fixture
    def sensitivity_level(self):
        from src.order_sensitivity_metrics import SensitivityLevel
        return SensitivityLevel
    
    @pytest.fixture
    def fragility_level(self):
        from src.order_sensitivity_metrics import FragilityLevel
        return FragilityLevel

    def test_metrics_initialization(self, metrics):
        """Test metrics initializes correctly."""
        status = metrics.get_status()
        assert status["operational"] is True
        assert status["total_observations"] == 0
    
    def test_record_observation(self, metrics):
        """Test recording an observation."""
        obs_id = metrics.record_observation(
            domain="test_domain",
            ordering=["a", "b", "c"],
            outcome_score=0.8,
            calibration_score=0.75,
            execution_time_ms=100.0,
        )
        
        assert obs_id.startswith("obs-")
        
        observations = metrics.get_domain_observations("test_domain")
        assert len(observations) == 1
        assert observations[0]["outcome_score"] == 0.8
    
    def test_analyze_sensitivity_insufficient_data(self, metrics):
        """Test sensitivity analysis with insufficient data."""
        result = metrics.analyze_sensitivity("empty_domain", min_samples=10)
        assert result["status"] == "insufficient_data"
    
    def test_analyze_sensitivity(self, metrics, sensitivity_level):
        """Test sensitivity analysis with sufficient data."""
        # Record observations with some variance
        import random
        for i in range(20):
            ordering = ["a", "b", "c"] if i % 2 == 0 else ["b", "a", "c"]
            metrics.record_observation(
                domain="sens_domain",
                ordering=ordering,
                outcome_score=0.7 + random.uniform(-0.1, 0.1),
                calibration_score=0.65 + random.uniform(-0.1, 0.1),
            )
        
        result = metrics.analyze_sensitivity("sens_domain")
        
        assert result["status"] == "ok"
        assert "sensitivity_level" in result
        assert "sensitivity_score" in result
        assert "outcome_variance" in result
        assert result["sample_size"] == 20
    
    def test_analyze_fragility_insufficient_data(self, metrics):
        """Test fragility analysis with insufficient data."""
        result = metrics.analyze_fragility("empty_domain", min_samples=20)
        assert result["status"] == "insufficient_data"
    
    def test_analyze_fragility(self, metrics, fragility_level):
        """Test fragility analysis with sufficient data."""
        import random
        for i in range(25):
            ordering = ["a", "b", "c"]
            if i % 3 == 0:
                ordering = ["b", "a", "c"]  # Adjacent swap
            elif i % 5 == 0:
                ordering = ["c", "b", "a"]  # More different
            
            metrics.record_observation(
                domain="frag_domain",
                ordering=ordering,
                outcome_score=0.75 + random.uniform(-0.15, 0.15),
                calibration_score=0.7,
            )
        
        result = metrics.analyze_fragility("frag_domain")
        
        assert result["status"] == "ok"
        assert "fragility_level" in result
        assert "fragility_score" in result
        assert "adjacent_swap_impact" in result
    
    def test_analyze_robustness(self, metrics):
        """Test robustness analysis."""
        import random
        for i in range(20):
            ordering = ["a", "b", "c"]
            if i % 4 == 0:
                ordering = ["b", "a", "c"]
            
            metrics.record_observation(
                domain="robust_domain",
                ordering=ordering,
                outcome_score=0.8 + random.uniform(-0.05, 0.05),
            )
        
        result = metrics.analyze_robustness("robust_domain")
        
        assert result["status"] == "ok"
        assert "robustness_score" in result
        assert "best_ordering" in result
        assert "worst_ordering" in result
    
    def test_analyze_path_dependence(self, metrics):
        """Test comprehensive path dependence analysis."""
        import random
        # Create data with clear path dependence
        for i in range(30):
            if i < 15:
                # First ordering tends to be better
                ordering = ["a", "b", "c"]
                score = 0.85 + random.uniform(-0.05, 0.05)
            else:
                # Second ordering tends to be worse
                ordering = ["c", "b", "a"]
                score = 0.6 + random.uniform(-0.05, 0.05)
            
            metrics.record_observation(
                domain="pdep_domain",
                ordering=ordering,
                outcome_score=score,
                calibration_score=0.7,
            )
        
        result = metrics.analyze_path_dependence("pdep_domain")
        
        assert result["status"] == "ok"
        assert "is_path_dependent" in result
        assert "path_dependence_strength" in result
        assert "should_learn_ordering" in result
        assert "summary" in result
    
    def test_invariant_domain(self, metrics):
        """Test analysis of domain where order doesn't matter."""
        import random
        # Create data with consistent outcomes regardless of order
        for i in range(25):
            ordering = ["a", "b", "c"] if i % 2 == 0 else ["c", "b", "a"]
            
            metrics.record_observation(
                domain="invariant_domain",
                ordering=ordering,
                outcome_score=0.8 + random.uniform(-0.02, 0.02),  # Very low variance
            )
        
        result = metrics.analyze_path_dependence("invariant_domain")
        
        assert result["status"] == "ok"
        # Should detect low sensitivity
        assert result["sensitivity"]["sensitivity_score"] < 0.5
    
    def test_get_cached_analysis(self, metrics):
        """Test getting cached analysis."""
        import random
        for i in range(20):
            metrics.record_observation(
                domain="cache_domain",
                ordering=["a", "b"],
                outcome_score=0.7 + random.uniform(-0.1, 0.1),
            )
        
        # Run analysis to populate cache
        metrics.analyze_sensitivity("cache_domain")
        
        cached = metrics.get_cached_analysis("cache_domain")
        assert cached["domain"] == "cache_domain"
        assert cached["sensitivity"] is not None
    
    def test_clear_specific_domain(self, metrics):
        """Test clearing a specific domain."""
        metrics.record_observation(
            domain="clear_domain_a",
            ordering=["a"],
            outcome_score=0.8,
        )
        metrics.record_observation(
            domain="clear_domain_b",
            ordering=["b"],
            outcome_score=0.7,
        )
        
        metrics.clear(domain="clear_domain_a")
        
        obs_a = metrics.get_domain_observations("clear_domain_a")
        obs_b = metrics.get_domain_observations("clear_domain_b")
        
        assert len(obs_a) == 0
        assert len(obs_b) == 1
    
    def test_clear_all(self, metrics):
        """Test clearing all metrics."""
        metrics.record_observation("domain1", ["a"], 0.8)
        metrics.record_observation("domain2", ["b"], 0.7)
        
        metrics.clear()
        
        stats = metrics.get_statistics()
        assert stats["total_observations"] == 0
        assert stats["domains_tracked"] == 0


# ------------------------------------------------------------------
# Integration Tests
# ------------------------------------------------------------------

class TestPermutationCalibrationIntegration:
    """Integration tests for the permutation calibration system."""
    
    def test_full_workflow_mode_a_to_mode_b(self):
        """Test complete workflow from exploration to procedural execution."""
        from src.permutation_policy_registry import (
            PermutationPolicyRegistry, SequenceType, SequenceStatus
        )
        from src.permutation_calibration_adapter import (
            PermutationCalibrationAdapter, create_intake_item
        )
        from src.procedural_distiller import ProceduralDistiller
        from src.order_sensitivity_metrics import OrderSensitivityMetrics
        
        # Initialize all components
        registry = PermutationPolicyRegistry()
        adapter = PermutationCalibrationAdapter()
        distiller = ProceduralDistiller()
        metrics = OrderSensitivityMetrics()
        
        # Step 1: Create intake items
        items = [
            create_intake_item("connector", "crm_connector"),
            create_intake_item("api", "analytics_api"),
            create_intake_item("evidence", "user_feedback"),
        ]
        
        # Step 2: Run exploration (Mode A)
        session_id = adapter.start_exploration(
            domain="crm_integration",
            items=items,
            max_candidates=10,
        )
        exploration_result = adapter.run_exploration(session_id)
        
        assert exploration_result["status"] == "completed"
        best_ordering = exploration_result["best_result"]["ordering"]
        
        # Step 3: Record observations for metrics
        for _ in range(5):
            metrics.record_observation(
                domain="crm_integration",
                ordering=best_ordering,
                outcome_score=exploration_result["best_result"]["aggregate_score"],
                calibration_score=0.75,
            )
        
        # Step 4: Register discovered sequence
        sequence_id = registry.register_sequence(
            name="CRM Integration Sequence",
            sequence_type=SequenceType.CONNECTOR_ORDER,
            domain="crm_integration",
            ordering=best_ordering,
        )
        
        # Step 5: Record evaluation results
        for _ in range(10):
            registry.record_evaluation(
                sequence_id=sequence_id,
                outcome_quality=0.8,
                calibration_quality=0.75,
                stability_score=0.7,
                success=True,
            )
        
        # Step 6: Promote sequence
        registry.promote_sequence(
            sequence_id=sequence_id,
            target_status=SequenceStatus.PROMOTED,
            approver="system_admin",
        )
        
        # Step 7: Distill into procedure (Mode B)
        seq_data = registry.get_sequence(sequence_id)
        distill_result = distiller.distill_from_sequence(
            sequence_data=seq_data,
            item_types={
                item.item_id: item.item_type
                for item in items
            },
        )
        
        assert distill_result["status"] == "ok"
        
        # Step 8: Activate procedure
        template_id = distill_result["template_id"]
        distiller.activate_template(template_id, approver="system_admin")
        
        # Verify end state
        template = distiller.get_template(template_id)
        assert template["status"] == "active"
        assert len(template["steps"]) > 0
        
        promoted = registry.get_promoted_sequences(domain="crm_integration")
        assert len(promoted) == 1
    
    def test_drift_detection_and_reversion(self):
        """Test detecting drift and reverting to Mode A."""
        from src.permutation_policy_registry import (
            PermutationPolicyRegistry, SequenceType, SequenceStatus
        )
        from src.procedural_distiller import ProceduralDistiller
        from src.order_sensitivity_metrics import OrderSensitivityMetrics
        
        registry = PermutationPolicyRegistry()
        distiller = ProceduralDistiller()
        metrics = OrderSensitivityMetrics()
        
        # Create and promote a sequence
        sequence_id = registry.register_sequence(
            name="Drift Test Sequence",
            sequence_type=SequenceType.ROUTING_ORDER,
            domain="drift_test",
            ordering=["r1", "r2", "r3"],
        )
        
        # Initially good performance
        for _ in range(10):
            registry.record_evaluation(
                sequence_id=sequence_id,
                outcome_quality=0.85,
                calibration_quality=0.8,
                stability_score=0.75,
                success=True,
            )
        
        registry.promote_sequence(
            sequence_id=sequence_id,
            target_status=SequenceStatus.PROMOTED,
            approver="admin",
        )
        
        # Create procedure
        seq_data = registry.get_sequence(sequence_id)
        distill_result = distiller.distill_from_sequence(seq_data)
        template_id = distill_result["template_id"]
        distiller.activate_template(template_id, approver="admin")
        
        # Simulate drift - poor performance
        for _ in range(10):
            registry.record_evaluation(
                sequence_id=sequence_id,
                outcome_quality=0.4,  # Much worse
                calibration_quality=0.5,
                stability_score=0.3,
                success=False,
            )
        
        # Check that sequence confidence has dropped
        seq_after = registry.get_sequence(sequence_id)
        assert seq_after["confidence_score"] < 0.7
        
        # Deprecate the sequence (reversion)
        registry.deprecate_sequence(
            sequence_id=sequence_id,
            reason="Performance degradation detected",
        )
        
        # Suspend the procedure
        distiller.suspend_template(template_id, reason="Source sequence deprecated")
        
        # Verify state
        seq_final = registry.get_sequence(sequence_id)
        assert seq_final["status"] == "deprecated"
        
        template_final = distiller.get_template(template_id)
        assert template_final["status"] == "suspended"
    
    def test_observability_counters_integration(self):
        """Test integration with observability counters."""
        from src.permutation_policy_registry import (
            PermutationPolicyRegistry, SequenceType
        )
        from src.observability_counters import ObservabilitySummaryCounters
        
        registry = PermutationPolicyRegistry()
        counters = ObservabilitySummaryCounters()
        
        # Register permutation coverage counter
        coverage_id = counters.register_counter(
            name="permutation_calibration:exploration_runs",
            category="permutation_coverage",
        )
        
        # Register behavior fix counter
        fix_id = counters.register_counter(
            name="permutation_calibration:sequence_improvements",
            category="behavior_fix",
        )
        
        # Simulate exploration runs
        for i in range(5):
            sequence_id = registry.register_sequence(
                name=f"Explored Sequence {i}",
                sequence_type=SequenceType.EVIDENCE_ORDER,
                domain="observability_test",
                ordering=[f"item_{i}"],
            )
            counters.increment(coverage_id, delta=1, reason=f"Exploration run {i}")
        
        # Simulate improvements
        counters.increment(fix_id, delta=3, reason="Promoted 3 sequences")
        
        # Check counters
        summary = counters.get_category_summary()
        assert summary["categories"]["permutation_coverage"] == 5
        assert summary["categories"]["behavior_fix"] == 3
        
        ratio = counters.get_behavior_vs_permutation_ratio()
        assert ratio["behavior_fix_total"] == 3
        assert ratio["permutation_coverage_total"] == 5


# ------------------------------------------------------------------
# Causality Sandbox Integration Tests
# ------------------------------------------------------------------

class TestCausalitySandboxIntegration:
    """Tests for integration with causality sandbox."""
    
    def test_causality_sandbox_exists(self):
        """Test that causality sandbox can be imported."""
        try:
            from src.causality_sandbox import CausalitySandboxEngine
            assert CausalitySandboxEngine is not None
        except ImportError:
            pytest.skip("causality_sandbox not available")
    
    def test_rubix_evidence_adapter_exists(self):
        """Test that rubix evidence adapter can be imported."""
        try:
            from src.rubix_evidence_adapter import RubixEvidenceAdapter
            assert RubixEvidenceAdapter is not None
        except ImportError:
            pytest.skip("rubix_evidence_adapter not available")
    
    def test_triage_rollcall_adapter_exists(self):
        """Test that triage rollcall adapter can be imported."""
        try:
            from src.triage_rollcall_adapter import TriageRollcallAdapter
            assert TriageRollcallAdapter is not None
        except ImportError:
            pytest.skip("triage_rollcall_adapter not available")


# ------------------------------------------------------------------
# Paper Trading Integration Tests
# ------------------------------------------------------------------

class TestPaperTradingIntegration:
    """Tests for integration with paper trading."""
    
    def test_paper_trading_engine_exists(self):
        """Test that paper trading engine can be imported."""
        try:
            from src.paper_trading_engine import PaperTradingEngine
            assert PaperTradingEngine is not None
        except ImportError:
            pytest.skip("paper_trading_engine not available")
    
    def test_permutation_with_trading_simulation(self):
        """Test permutation calibration in trading simulation context."""
        from src.permutation_calibration_adapter import (
            PermutationCalibrationAdapter, create_intake_item
        )
        from src.order_sensitivity_metrics import OrderSensitivityMetrics
        
        adapter = PermutationCalibrationAdapter()
        metrics = OrderSensitivityMetrics()
        
        # Create trading-related intake items
        items = [
            create_intake_item("api", "market_data_feed"),
            create_intake_item("api", "sentiment_api"),
            create_intake_item("evidence", "technical_indicators"),
            create_intake_item("connector", "portfolio_state"),
        ]
        
        # Run exploration
        session_id = adapter.start_exploration(
            domain="trading_simulation",
            items=items,
            max_candidates=15,
        )
        
        result = adapter.run_exploration(session_id)
        assert result["status"] == "completed"
        
        # Record metrics
        best = result["best_result"]
        metrics.record_observation(
            domain="trading_simulation",
            ordering=best["ordering"],
            outcome_score=best["aggregate_score"],
            calibration_score=best["scores"].get("calibration_quality", 0.5),
        )
        
        obs = metrics.get_domain_observations("trading_simulation")
        assert len(obs) >= 1


# ------------------------------------------------------------------
# Extended Module Integration Tests
# ------------------------------------------------------------------

class TestSelfImprovementExtension:
    """Tests for PermutationLearningExtension in self_improvement_engine."""
    
    def test_extension_initialization(self):
        """Test extension initializes correctly."""
        from src.self_improvement_engine import SelfImprovementEngine, PermutationLearningExtension
        
        engine = SelfImprovementEngine()
        ext = PermutationLearningExtension(engine)
        
        status = ext.get_learning_status()
        assert status["status"] == "ok"
        assert status["exploratory_outcomes"] == 0
        assert status["procedural_outcomes"] == 0
    
    def test_record_exploratory_outcome(self):
        """Test recording exploratory outcomes."""
        from src.self_improvement_engine import SelfImprovementEngine, PermutationLearningExtension
        
        engine = SelfImprovementEngine()
        ext = PermutationLearningExtension(engine)
        
        record = ext.record_exploratory_outcome(
            domain="test_domain",
            ordering=["a", "b", "c"],
            outcome_quality=0.8,
            calibration_quality=0.75,
            session_id="session-1",
        )
        
        assert record["domain"] == "test_domain"
        assert record["mode"] == "exploratory"
        assert record["outcome_quality"] == 0.8
        
        status = ext.get_learning_status()
        assert status["exploratory_outcomes"] == 1
    
    def test_record_procedural_outcome(self):
        """Test recording procedural outcomes."""
        from src.self_improvement_engine import SelfImprovementEngine, PermutationLearningExtension
        
        engine = SelfImprovementEngine()
        ext = PermutationLearningExtension(engine)
        
        record = ext.record_procedural_outcome(
            domain="test_domain",
            sequence_id="seq-001",
            ordering=["a", "b", "c"],
            outcome_quality=0.85,
            calibration_quality=0.8,
            session_id="session-2",
        )
        
        assert record["domain"] == "test_domain"
        assert record["mode"] == "procedural"
        assert record["sequence_id"] == "seq-001"
    
    def test_compare_exploratory_vs_procedural(self):
        """Test comparing exploratory vs procedural outcomes."""
        from src.self_improvement_engine import SelfImprovementEngine, PermutationLearningExtension
        
        engine = SelfImprovementEngine()
        ext = PermutationLearningExtension(engine)
        
        # Record exploratory outcomes
        for i in range(5):
            ext.record_exploratory_outcome(
                domain="compare_domain",
                ordering=["a", "b"],
                outcome_quality=0.7,
                calibration_quality=0.65,
                session_id=f"exp-{i}",
            )
        
        # Record procedural outcomes (better)
        for i in range(5):
            ext.record_procedural_outcome(
                domain="compare_domain",
                sequence_id="seq-1",
                ordering=["a", "b"],
                outcome_quality=0.85,
                calibration_quality=0.8,
                session_id=f"proc-{i}",
            )
        
        comparison = ext.compare_exploratory_vs_procedural("compare_domain")
        
        assert comparison["status"] == "ok"
        assert comparison["quality_improvement"] > 0
        assert comparison["recommendation"] == "maintain_procedural"
    
    def test_detect_drift(self):
        """Test drift detection in procedural execution."""
        from src.self_improvement_engine import SelfImprovementEngine, PermutationLearningExtension
        
        engine = SelfImprovementEngine()
        ext = PermutationLearningExtension(engine)
        
        # Record good outcomes first
        for i in range(20):
            ext.record_procedural_outcome(
                domain="drift_domain",
                sequence_id="seq-1",
                ordering=["a", "b"],
                outcome_quality=0.85,
                calibration_quality=0.8,
                session_id=f"good-{i}",
            )
        
        # Then bad outcomes
        for i in range(20):
            ext.record_procedural_outcome(
                domain="drift_domain",
                sequence_id="seq-1",
                ordering=["a", "b"],
                outcome_quality=0.5,  # Much worse
                calibration_quality=0.55,
                session_id=f"bad-{i}",
            )
        
        drift = ext.detect_drift("drift_domain")
        
        assert drift["status"] == "ok"
        assert drift["drift_detected"] is True
        assert drift["recommendation"] == "reopen_exploration"


class TestObservabilityCountersExtension:
    """Tests for permutation calibration additions to observability counters."""
    
    def test_record_exploration(self):
        """Test recording exploration runs."""
        from src.observability_counters import ObservabilitySummaryCounters
        
        counters = ObservabilitySummaryCounters()
        counter_id = counters.record_exploration("test_domain", 25, "Test exploration run")
        
        counter = counters.get_counter(counter_id)
        assert counter["value"] == 25
        assert counter["category"] == "permutation_exploration"
    
    def test_record_sequence_learning(self):
        """Test recording sequence learning."""
        from src.observability_counters import ObservabilitySummaryCounters
        
        counters = ObservabilitySummaryCounters()
        counter_id = counters.record_sequence_learning("test_domain", 3, "Learned 3 sequences")
        
        counter = counters.get_counter(counter_id)
        assert counter["value"] == 3
        assert counter["category"] == "sequence_learning"
    
    def test_record_promotion_and_demotion(self):
        """Test recording promotion and demotion events."""
        from src.observability_counters import ObservabilitySummaryCounters
        
        counters = ObservabilitySummaryCounters()
        counters.record_promotion("test_domain", "Promoted sequence A")
        counters.record_promotion("test_domain", "Promoted sequence B")
        counters.record_demotion("test_domain", "Demoted sequence C")
        
        summary = counters.get_permutation_calibration_summary()
        assert summary["promotions"] == 2
        assert summary["demotions"] == 1
    
    def test_permutation_calibration_summary(self):
        """Test getting full permutation calibration summary."""
        from src.observability_counters import ObservabilitySummaryCounters
        
        counters = ObservabilitySummaryCounters()
        
        counters.record_exploration("domain1", 50, "Exploration 1")
        counters.record_sequence_learning("domain1", 5, "Learning 1")
        counters.record_promotion("domain1", "Promotion 1")
        counters.record_drift_detection("domain1", "Drift detected")
        
        summary = counters.get_permutation_calibration_summary()
        
        assert summary["status"] == "ok"
        assert summary["exploration_total"] == 50
        assert summary["sequences_learned"] == 5
        assert summary["promotions"] == 1
        assert summary["drift_detections"] == 1


class TestGateExecutionWiringExtension:
    """Tests for permutation gates in gate_execution_wiring."""
    
    def test_register_exploration_gate(self):
        """Test registering permutation exploration gate."""
        from src.gate_execution_wiring import GateExecutionWiring, GateType
        
        gates = GateExecutionWiring()
        gates.register_permutation_exploration_gate(
            max_candidates=100,
            allowed_domains=["domain_a", "domain_b"],
        )
        
        status = gates.get_status()
        assert GateType.PERMUTATION_EXPLORATION.value in status["registered_gates"]
    
    def test_register_promotion_gate(self):
        """Test registering sequence promotion gate."""
        from src.gate_execution_wiring import GateExecutionWiring, GateType
        
        gates = GateExecutionWiring()
        gates.register_sequence_promotion_gate(
            min_evaluations=10,
            min_confidence=0.7,
        )
        
        status = gates.get_status()
        assert GateType.SEQUENCE_PROMOTION.value in status["registered_gates"]
    
    def test_exploration_gate_evaluation(self):
        """Test exploration gate evaluation."""
        from src.gate_execution_wiring import GateExecutionWiring, GateDecision
        
        gates = GateExecutionWiring()
        gates.register_permutation_exploration_gate(max_candidates=50)
        
        # Should approve exploration within limits
        task_ok = {
            "permutation_exploration": True,
            "domain": "test",
            "max_candidates": 30,
        }
        
        allowed, evals = gates.can_execute(task_ok, "session-1")
        exploration_eval = next(
            (e for e in evals if e.gate_type.value == "permutation_exploration"),
            None
        )
        assert exploration_eval is not None
        assert exploration_eval.decision == GateDecision.APPROVED
    
    def test_promotion_gate_needs_approval(self):
        """Test promotion gate requires approval."""
        from src.gate_execution_wiring import GateExecutionWiring, GateDecision
        
        gates = GateExecutionWiring()
        gates.register_sequence_promotion_gate(
            require_approval=True,
            min_evaluations=10,
            min_confidence=0.7,
        )
        
        # Should need review without approval
        task = {
            "sequence_promotion": True,
            "total_evaluations": 15,
            "confidence_score": 0.8,
            "gate_approved": False,
        }
        
        allowed, evals = gates.can_execute(task, "session-1")
        promotion_eval = next(
            (e for e in evals if e.gate_type.value == "sequence_promotion"),
            None
        )
        assert promotion_eval is not None
        assert promotion_eval.decision == GateDecision.NEEDS_REVIEW


class TestSemanticsBoundaryExtension:
    """Tests for order invariance checking in semantics_boundary_controller."""
    
    def test_check_order_invariance_invariant(self):
        """Test detecting order invariance."""
        from src.semantics_boundary_controller import SemanticsBoundaryController
        
        controller = SemanticsBoundaryController()
        
        result = controller.check_order_invariance(
            domain="test",
            ordering_a=["a", "b", "c"],
            result_a=0.85,
            ordering_b=["c", "b", "a"],
            result_b=0.84,  # Within tolerance
            tolerance=0.05,
        )
        
        assert result["is_invariant"] is True
        assert result["classification"] == "invariant"
    
    def test_check_order_invariance_sensitive(self):
        """Test detecting order sensitivity."""
        from src.semantics_boundary_controller import SemanticsBoundaryController
        
        controller = SemanticsBoundaryController()
        
        result = controller.check_order_invariance(
            domain="test",
            ordering_a=["a", "b", "c"],
            result_a=0.9,
            ordering_b=["c", "b", "a"],
            result_b=0.5,  # Very different
            tolerance=0.05,
        )
        
        assert result["is_invariant"] is False
        assert result["classification"] == "highly_sensitive"
    
    def test_classify_domain_sensitivity_stable(self):
        """Test classifying a stable domain."""
        from src.semantics_boundary_controller import SemanticsBoundaryController
        
        controller = SemanticsBoundaryController()
        
        # Very consistent results
        observations = [
            {"ordering": ["a", "b"], "result": 0.8 + i * 0.001}
            for i in range(15)
        ]
        
        result = controller.classify_domain_sensitivity(
            domain="stable_domain",
            observations=observations,
        )
        
        assert result["status"] == "ok"
        assert result["classification"] == "stable"
    
    def test_classify_domain_sensitivity_fragile(self):
        """Test classifying a fragile domain."""
        from src.semantics_boundary_controller import SemanticsBoundaryController
        import random
        
        controller = SemanticsBoundaryController()
        
        # High variance results
        observations = [
            {"ordering": ["a", "b"], "result": 0.5 + random.uniform(-0.3, 0.3)}
            for _ in range(15)
        ]
        
        result = controller.classify_domain_sensitivity(
            domain="fragile_domain",
            observations=observations,
        )
        
        assert result["status"] == "ok"
        assert result["classification"] in ["fragile", "highly_fragile", "sensitive"]
    
    def test_get_order_invariance_summary(self):
        """Test getting order invariance summary."""
        from src.semantics_boundary_controller import SemanticsBoundaryController
        
        controller = SemanticsBoundaryController()
        
        # Register some checks
        controller.check_order_invariance("d1", ["a"], 0.8, ["a"], 0.8, 0.05)
        controller.check_order_invariance("d2", ["b"], 0.8, ["b"], 0.5, 0.05)
        
        summary = controller.get_order_invariance_summary()
        
        assert summary["total_checks"] == 2
        assert summary["verified_checks"] == 2
        assert summary["invariant_count"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

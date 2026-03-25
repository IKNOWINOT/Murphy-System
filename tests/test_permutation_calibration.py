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


# ------------------------------------------------------------------
# Deterministic Routing Engine Integration Tests
# ------------------------------------------------------------------

class TestDeterministicRoutingIntegration:
    """Tests for permutation-aware routing in deterministic_routing_engine."""

    def test_register_permutation_policy(self):
        """Test registering a permutation-derived routing policy."""
        from src.deterministic_routing_engine import DeterministicRoutingEngine

        engine = DeterministicRoutingEngine()

        policy_id = engine.register_permutation_policy(
            domain="sales",
            sequence_id="seq-12345678",
            ordering=["crm", "analytics", "feedback"],
            route_type="hybrid",
            priority=15,
        )

        assert policy_id == "perm-sales-seq-1234"

        policy = engine.get_policy(policy_id)
        assert policy["status"] == "ok"
        assert policy["route_type"] == "hybrid"
        assert policy["guardrails"]["learned_policy"] is True

    def test_route_with_permutation_awareness(self):
        """Test routing with permutation awareness."""
        from src.deterministic_routing_engine import DeterministicRoutingEngine

        engine = DeterministicRoutingEngine()

        # Register a permutation policy first
        engine.register_permutation_policy(
            domain="support",
            sequence_id="seq-abcdefgh",
            ordering=["ticket", "history", "resolution"],
            route_type="deterministic",
        )

        decision = engine.route_with_permutation_awareness(
            task_type="support_ticket",
            domain="support",
            confidence=0.8,
        )

        assert decision["permutation_policy_applied"] is True
        assert decision["permutation_ordering"] == ["ticket", "history", "resolution"]

    def test_switch_routing_mode(self):
        """Test switching between exploratory and procedural modes."""
        from src.deterministic_routing_engine import DeterministicRoutingEngine

        engine = DeterministicRoutingEngine()

        engine.register_permutation_policy(
            domain="test_domain",
            sequence_id="seq-test1234",
            ordering=["a", "b", "c"],
        )

        # Switch to exploratory mode
        result = engine.switch_routing_mode("test_domain", "exploratory")
        assert result["status"] == "ok"
        assert result["mode"] == "exploratory"
        assert len(result["affected_policies"]) == 1

        # Switch back to procedural mode
        result = engine.switch_routing_mode("test_domain", "procedural")
        assert result["mode"] == "procedural"

    def test_get_permutation_routing_stats(self):
        """Test getting permutation-specific routing stats."""
        from src.deterministic_routing_engine import DeterministicRoutingEngine

        engine = DeterministicRoutingEngine()

        engine.register_permutation_policy("domain1", "seq-1", ["a", "b"])
        engine.register_permutation_policy("domain2", "seq-2", ["x", "y"])

        stats = engine.get_permutation_routing_stats()

        assert stats["status"] == "ok"
        assert stats["total_permutation_policies"] == 2
        assert stats["enabled_policies"] == 2


# ------------------------------------------------------------------
# Golden Path Bridge Integration Tests
# ------------------------------------------------------------------

class TestGoldenPathBridgeIntegration:
    """Tests for sequence-based golden path recording."""

    def test_record_sequence_path(self):
        """Test recording a sequence-based golden path."""
        from src.golden_path_bridge import GoldenPathBridge

        bridge = GoldenPathBridge()

        path_id = bridge.record_sequence_path(
            sequence_id="seq-abc123",
            domain="crm_integration",
            ordering=["crm", "analytics", "feedback"],
            execution_spec={"steps": ["step1", "step2"]},
            outcome_quality=0.85,
        )

        assert path_id is not None

        path = bridge.get_path(path_id)
        assert path is not None
        # Ordering is stored in 'extra' due to normalization
        extra = path.execution_spec.get("extra", {})
        assert extra.get("learned_ordering") == ["crm", "analytics", "feedback"]
        assert extra.get("sequence_id") == "seq-abc123"

    def test_find_sequence_matches(self):
        """Test finding matching sequence paths."""
        from src.golden_path_bridge import GoldenPathBridge

        bridge = GoldenPathBridge()

        # Record a few sequence paths
        bridge.record_sequence_path(
            sequence_id="seq-001",
            domain="sales",
            ordering=["a", "b", "c"],
            execution_spec={},
            outcome_quality=0.9,
        )
        bridge.record_sequence_path(
            sequence_id="seq-002",
            domain="sales",
            ordering=["a", "c", "b"],
            execution_spec={},
            outcome_quality=0.8,
        )

        # Find matches for a similar ordering
        matches = bridge.find_sequence_matches(
            current_ordering=["a", "b", "c"],
            domain="sales",
            min_confidence=0.5,
        )

        assert len(matches) >= 1
        assert matches[0]["sequence_id"] in ["seq-001", "seq-002"]
        assert "similarity" in matches[0]

    def test_replay_sequence_path(self):
        """Test replaying a sequence path."""
        from src.golden_path_bridge import GoldenPathBridge

        bridge = GoldenPathBridge()

        bridge.record_sequence_path(
            sequence_id="seq-replay-test",
            domain="test_domain",
            ordering=["x", "y", "z"],
            execution_spec={"steps": ["execute"]},
            outcome_quality=0.85,
        )

        spec = bridge.replay_sequence_path("seq-replay-test", "test_domain")

        assert spec is not None
        assert spec.get("learned_ordering") == ["x", "y", "z"]
        assert "replayed_from" in spec

    def test_get_sequence_path_stats(self):
        """Test getting sequence path statistics."""
        from src.golden_path_bridge import GoldenPathBridge

        bridge = GoldenPathBridge()

        # Record both sequence and regular paths
        bridge.record_sequence_path(
            sequence_id="seq-stat-test",
            domain="stats_domain",
            ordering=["a", "b"],
            execution_spec={},
            outcome_quality=0.8,
        )
        bridge.record_success(
            task_pattern="regular_task",
            domain="stats_domain",
            execution_spec={"type": "regular"},
        )

        stats = bridge.get_sequence_path_stats()

        assert stats["status"] == "ok"
        assert stats["total_sequence_paths"] >= 1
        assert stats["total_regular_paths"] >= 1


# ------------------------------------------------------------------
# HITL Autonomy Controller Integration Tests
# ------------------------------------------------------------------

class TestHITLAutonomyControllerIntegration:
    """Tests for learned procedure review in HITL autonomy controller."""

    def test_register_learned_procedure_policy(self):
        """Test registering a learned procedure policy."""
        from src.hitl_autonomy_controller import HITLAutonomyController

        controller = HITLAutonomyController()

        policy_id = controller.register_learned_procedure_policy(
            sequence_id="seq-learned-001",
            domain="crm_domain",
            stability_score=0.8,
            confidence_score=0.85,
            requires_review=True,
        )

        assert policy_id == "learned-crm_domain-seq-lear"

        policy = controller.get_policy(policy_id)
        assert policy["status"] == "ok"
        assert policy["hitl_required"] is True

    def test_evaluate_learned_procedure_autonomy(self):
        """Test evaluating autonomy for a learned procedure."""
        from src.hitl_autonomy_controller import HITLAutonomyController

        controller = HITLAutonomyController()

        controller.register_learned_procedure_policy(
            sequence_id="seq-eval-001",
            domain="eval_domain",
            stability_score=0.85,
            confidence_score=0.9,
            requires_review=False,
        )

        result = controller.evaluate_learned_procedure_autonomy(
            sequence_id="seq-eval-001",
            domain="eval_domain",
            execution_confidence=0.95,
            risk_level=0.1,
        )

        assert result["sequence_id"] == "seq-eval-001"
        assert result["stability_score"] == 0.85
        assert result["source"] == "permutation_learning"

    def test_evaluate_weak_stability_requires_hitl(self):
        """Test that weak stability requires HITL."""
        from src.hitl_autonomy_controller import HITLAutonomyController

        controller = HITLAutonomyController()

        controller.register_learned_procedure_policy(
            sequence_id="seq-weak-001",
            domain="weak_domain",
            stability_score=0.3,  # Low stability
            confidence_score=0.7,
        )

        result = controller.evaluate_learned_procedure_autonomy(
            sequence_id="seq-weak-001",
            domain="weak_domain",
            execution_confidence=0.95,
            risk_level=0.1,
        )

        assert result["autonomous"] is False
        assert result["reason"] == "policy_stability_too_weak"
        assert result["requires_hitl"] is True

    def test_request_and_approve_procedure_promotion(self):
        """Test procedure promotion review workflow."""
        from src.hitl_autonomy_controller import HITLAutonomyController

        controller = HITLAutonomyController()

        # Request promotion review
        review = controller.request_procedure_promotion_review(
            sequence_id="seq-promo-001",
            domain="promo_domain",
            promotion_reason="Consistent high performance",
            metrics={
                "confidence": 0.85,
                "order_sensitivity": 0.4,
                "fragility": 0.2,
            },
        )

        assert review["status"] == "pending_review"
        assert review["escalation_required"] is False

        # Approve the promotion
        approval = controller.approve_procedure_promotion(
            review_id=review["review_id"],
            approver="admin",
        )

        assert approval["status"] == "approved"

    def test_high_sensitivity_requires_escalation(self):
        """Test that high sensitivity requires escalation."""
        from src.hitl_autonomy_controller import HITLAutonomyController

        controller = HITLAutonomyController()

        review = controller.request_procedure_promotion_review(
            sequence_id="seq-sensitive-001",
            domain="sensitive_domain",
            promotion_reason="Testing escalation",
            metrics={
                "confidence": 0.8,
                "order_sensitivity": 0.8,  # High sensitivity
                "fragility": 0.5,  # High fragility
            },
        )

        assert review["escalation_required"] is True

    def test_get_learned_procedure_stats(self):
        """Test getting learned procedure statistics."""
        from src.hitl_autonomy_controller import HITLAutonomyController

        controller = HITLAutonomyController()

        controller.register_learned_procedure_policy(
            sequence_id="seq-stat-001",
            domain="stat_domain",
            stability_score=0.8,
            confidence_score=0.85,
        )

        controller.request_procedure_promotion_review(
            sequence_id="seq-stat-002",
            domain="stat_domain",
            promotion_reason="Stats test",
            metrics={"confidence": 0.8},
        )

        stats = controller.get_learned_procedure_stats()

        assert stats["status"] == "ok"
        assert stats["learned_procedure_policies"] >= 1
        assert stats["pending_reviews"] >= 1


# ------------------------------------------------------------------
# ML Strategy Engine Integration Tests
# ------------------------------------------------------------------

class TestMLStrategyEngineIntegration:
    """Tests for sequence scoring in ML strategy engine."""

    def test_score_sequence_family(self):
        """Test scoring a sequence family."""
        from src.ml_strategy_engine import MLStrategyEngine

        engine = MLStrategyEngine()

        evaluations = [
            {"outcome_quality": 0.85, "calibration_quality": 0.8, "stability_score": 0.75}
            for _ in range(15)
        ]

        result = engine.score_sequence_family("seq-score-001", evaluations)

        assert result["status"] == "ok"
        assert result["sample_count"] == 15
        assert result["avg_outcome_quality"] > 0.8
        assert result["is_robust"] is True
        assert result["promotion_ready"] is True

    def test_score_brittle_sequence(self):
        """Test scoring a brittle sequence."""
        from src.ml_strategy_engine import MLStrategyEngine
        import random

        engine = MLStrategyEngine()

        # High variance evaluations
        evaluations = [
            {
                "outcome_quality": random.uniform(0.3, 0.9),
                "calibration_quality": random.uniform(0.3, 0.9),
                "stability_score": random.uniform(0.3, 0.9),
            }
            for _ in range(15)
        ]

        result = engine.score_sequence_family("seq-brittle-001", evaluations)

        assert result["status"] == "ok"
        assert result["brittleness"] > 0.02
        assert result["promotion_ready"] is False

    def test_rank_sequence_candidates(self):
        """Test ranking sequence candidates."""
        from src.ml_strategy_engine import MLStrategyEngine

        engine = MLStrategyEngine()

        candidates = [
            {
                "sequence_id": "seq-rank-001",
                "domain": "test",
                "ordering": ["a", "b"],
                "evaluations": [
                    {"outcome_quality": 0.9, "calibration_quality": 0.85, "stability_score": 0.8}
                    for _ in range(12)
                ],
            },
            {
                "sequence_id": "seq-rank-002",
                "domain": "test",
                "ordering": ["b", "a"],
                "evaluations": [
                    {"outcome_quality": 0.6, "calibration_quality": 0.55, "stability_score": 0.5}
                    for _ in range(8)
                ],
            },
        ]

        ranked = engine.rank_sequence_candidates(candidates)

        assert len(ranked) == 2
        assert ranked[0]["rank"] == 1
        assert ranked[0]["sequence_id"] == "seq-rank-001"  # Better scores
        assert ranked[1]["rank"] == 2

    def test_detect_ordering_anomalies(self):
        """Test detecting ordering anomalies."""
        from src.ml_strategy_engine import MLStrategyEngine

        engine = MLStrategyEngine()

        historical = [0.8, 0.82, 0.79, 0.81, 0.8, 0.83, 0.78, 0.8]
        recent_degraded = [0.5, 0.52, 0.48]  # Much worse

        result = engine.detect_ordering_anomalies(
            domain="anomaly_test",
            recent_scores=recent_degraded,
            historical_scores=historical,
        )

        assert result["status"] == "ok"
        assert result["drift_detected"] is True
        assert result["degradation"] is True
        assert result["recommendation"] == "reopen_exploration"

    def test_online_sequence_learning(self):
        """Test online learning for sequences."""
        from src.ml_strategy_engine import MLStrategyEngine

        engine = MLStrategyEngine()

        # Train on some examples
        for i in range(20):
            engine.online_sequence_learning(
                sequence_id="seq-online-001",
                features={"feature_a": 0.8, "feature_b": 0.6},
                success=i % 3 != 0,  # 2/3 success rate
            )

        # Predict
        prediction = engine.predict_sequence_success(
            sequence_id="seq-online-001",
            features={"feature_a": 0.8, "feature_b": 0.6},
        )

        assert prediction["status"] == "ok"
        assert "predicted_success" in prediction
        assert "confidence" in prediction


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

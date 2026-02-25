"""
Tests for LLM Routing Completeness Module

Covers all five subsystems:
  1. Model Selection Matrix
  2. Prompt Optimization Pipeline
  3. Context-Aware Routing Rules
  4. Hybrid Execution Mode
  5. Routing Parity Validator

Plus the unified LLMRoutingCompleteness facade.
"""

import sys
import os
import threading
import unittest

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llm_routing_completeness import (
    ModelProfile,
    ModelSelectionMatrix,
    PromptTemplate,
    PromptOptimizationPipeline,
    RoutingRule,
    ContextAwareRouter,
    SubtaskSpec,
    HybridExecutionEngine,
    RoutingParityValidator,
    LLMRoutingCompleteness,
)


# ===================================================================
# 1. Model Selection Matrix Tests
# ===================================================================

class TestModelSelectionMatrix(unittest.TestCase):
    """Tests for auto-selecting models by task/cost/latency/quality."""

    def setUp(self):
        self.msm = ModelSelectionMatrix()

    def test_select_model_for_code_task(self):
        result = self.msm.select_model("code")
        self.assertEqual(result["status"], "selected")
        self.assertIn("model_id", result)

    def test_select_model_no_match(self):
        result = self.msm.select_model("nonexistent_task_xyz")
        self.assertEqual(result["status"], "no_match")

    def test_select_model_with_cost_constraint(self):
        result = self.msm.select_model("code", max_cost=0.001)
        # Only Llama should qualify at that cost
        if result["status"] == "selected":
            self.assertLessEqual(result["cost_per_1k_tokens"], 0.001)

    def test_select_model_with_latency_constraint(self):
        result = self.msm.select_model("analysis", max_latency_ms=200)
        # Very tight latency may exclude all models
        if result["status"] == "selected":
            self.assertLessEqual(result["avg_latency_ms"], 200)

    def test_select_model_with_quality_floor(self):
        result = self.msm.select_model("code", min_quality=0.93)
        if result["status"] == "selected":
            self.assertGreaterEqual(result["quality_score"], 0.93)

    def test_select_model_with_context_tokens(self):
        result = self.msm.select_model("analysis", min_context_tokens=100000)
        if result["status"] == "selected":
            self.assertGreaterEqual(result["max_context_tokens"], 100000)

    def test_register_custom_model(self):
        profile = ModelProfile(
            "custom-1", "Custom", 0.005, 100, 0.99, 16000,
            ["code", "custom_task"],
        )
        mid = self.msm.register_model(profile)
        self.assertEqual(mid, "custom-1")
        result = self.msm.select_model("custom_task")
        self.assertEqual(result["model_id"], "custom-1")

    def test_list_models_returns_defaults(self):
        models = self.msm.list_models()
        self.assertGreaterEqual(len(models), 6)

    def test_selection_history_recorded(self):
        self.msm.select_model("code")
        self.msm.select_model("analysis")
        history = self.msm.get_selection_history()
        self.assertEqual(len(history), 2)


# ===================================================================
# 2. Prompt Optimization Pipeline Tests
# ===================================================================

class TestPromptOptimizationPipeline(unittest.TestCase):
    """Tests for template selection, context injection, few-shot, token budget."""

    def setUp(self):
        self.pop = PromptOptimizationPipeline(default_token_budget=4096)
        self.pop.register_template(PromptTemplate(
            template_id="tmpl-summarise",
            name="Summarise",
            task_types=["summarisation"],
            template_text="Summarise the following text: {text}",
            variables=["text"],
            few_shot_examples=[
                {"input": "Long article about AI", "output": "AI is advancing rapidly."},
                {"input": "Recipe for cake", "output": "Mix, bake, enjoy."},
            ],
            priority=10,
        ))

    def test_optimise_prompt_basic(self):
        result = self.pop.optimise_prompt(
            "summarisation", {"text": "Hello world"},
        )
        self.assertEqual(result["status"], "optimised")
        self.assertIn("Hello world", result["prompt"])

    def test_optimise_prompt_no_template(self):
        result = self.pop.optimise_prompt("unknown_task", {})
        self.assertEqual(result["status"], "no_template")

    def test_optimise_prompt_context_injection(self):
        result = self.pop.optimise_prompt(
            "summarisation", {"text": "data"},
            context={"domain": "finance"},
        )
        self.assertTrue(result["context_injected"])
        self.assertIn("finance", result["prompt"])

    def test_optimise_prompt_few_shot(self):
        result = self.pop.optimise_prompt(
            "summarisation", {"text": "data"}, max_few_shot=1,
        )
        self.assertEqual(result["few_shot_count"], 1)

    def test_optimise_prompt_token_budget_trimming(self):
        result = self.pop.optimise_prompt(
            "summarisation", {"text": "x" * 50000}, token_budget=100,
        )
        self.assertTrue(result["trimmed"])
        self.assertLessEqual(result["estimated_tokens"], 110)  # allow rounding

    def test_list_templates(self):
        templates = self.pop.list_templates()
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["template_id"], "tmpl-summarise")

    def test_optimisation_log(self):
        self.pop.optimise_prompt("summarisation", {"text": "a"})
        log = self.pop.get_optimisation_log()
        self.assertEqual(len(log), 1)


# ===================================================================
# 3. Context-Aware Routing Rules Tests
# ===================================================================

class TestContextAwareRouter(unittest.TestCase):
    """Tests for context-aware routing decisions."""

    def setUp(self):
        self.car = ContextAwareRouter()

    def test_default_route_is_deterministic(self):
        result = self.car.route("math", {})
        self.assertEqual(result["route_type"], "deterministic")
        self.assertEqual(result["status"], "routed")

    def test_rule_based_routing(self):
        self.car.register_rule(RoutingRule(
            rule_id="r1", name="High complexity", condition_field="complexity",
            condition_value="high", route_type="llm", priority=10,
        ))
        result = self.car.route("analysis", {"complexity": "high"})
        self.assertEqual(result["route_type"], "llm")

    def test_user_preference_routing(self):
        self.car.set_user_preference("u1", {"preferred_route_analysis": "hybrid"})
        result = self.car.route("analysis", {}, user_id="u1")
        self.assertEqual(result["route_type"], "hybrid")

    def test_success_pattern_routing(self):
        for _ in range(5):
            self.car.record_success("analysis:llm", 0.9)
        result = self.car.route("analysis", {})
        self.assertEqual(result["route_type"], "llm")

    def test_conversation_history_heuristic(self):
        sid = "sess-1"
        for i in range(6):
            self.car.record_conversation_turn(sid, "user", f"turn {i}")
        result = self.car.route("general", {}, session_id=sid)
        self.assertEqual(result["route_type"], "llm")

    def test_get_conversation_history(self):
        self.car.record_conversation_turn("s1", "user", "hi")
        self.car.record_conversation_turn("s1", "assistant", "hello")
        history = self.car.get_conversation_history("s1")
        self.assertEqual(len(history), 2)

    def test_get_success_stats(self):
        self.car.record_success("k1", 0.8)
        self.car.record_success("k1", 0.6)
        stats = self.car.get_success_stats("k1")
        self.assertEqual(stats["samples"], 2)
        self.assertAlmostEqual(stats["average_score"], 0.7)

    def test_routing_log(self):
        self.car.route("task", {})
        log = self.car.get_routing_log()
        self.assertEqual(len(log), 1)


# ===================================================================
# 4. Hybrid Execution Mode Tests
# ===================================================================

class TestHybridExecutionEngine(unittest.TestCase):
    """Tests for hybrid task splitting and parallel execution."""

    def setUp(self):
        self.hee = HybridExecutionEngine()

    def test_create_plan(self):
        specs = [
            SubtaskSpec("s1", "validate", "deterministic"),
            SubtaskSpec("s2", "reason", "llm", depends_on=["s1"]),
        ]
        plan = self.hee.create_plan("t1", specs)
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["subtask_count"], 2)
        self.assertEqual(plan["deterministic_count"], 1)
        self.assertEqual(plan["llm_count"], 1)

    def test_execute_plan_with_stubs(self):
        specs = [SubtaskSpec("s1", "val", "deterministic")]
        plan = self.hee.create_plan("t2", specs)
        result = self.hee.execute_plan(plan["plan_id"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("s1", result["subtask_results"])

    def test_execute_plan_not_found(self):
        result = self.hee.execute_plan("nonexistent")
        self.assertEqual(result["status"], "not_found")

    def test_execute_plan_with_custom_fns(self):
        specs = [SubtaskSpec("s1", "calc", "deterministic")]
        plan = self.hee.create_plan("t3", specs)
        custom = lambda s: {"output": 42, "execution_type": "deterministic"}
        result = self.hee.execute_plan(plan["plan_id"], deterministic_fn=custom)
        self.assertEqual(
            result["subtask_results"]["s1"]["result"]["output"], 42,
        )

    def test_split_task_with_data_and_query(self):
        specs = self.hee.split_task({"data": [1, 2], "query": "sum?"})
        self.assertEqual(len(specs), 2)
        types = [s.execution_type for s in specs]
        self.assertIn("deterministic", types)
        self.assertIn("llm", types)

    def test_split_task_default(self):
        specs = self.hee.split_task({"foo": "bar"})
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].execution_type, "deterministic")

    def test_get_plan(self):
        specs = [SubtaskSpec("s1", "a", "deterministic")]
        plan = self.hee.create_plan("t4", specs)
        fetched = self.hee.get_plan(plan["plan_id"])
        self.assertEqual(fetched["task_id"], "t4")

    def test_get_result_not_found(self):
        result = self.hee.get_result("nope")
        self.assertEqual(result["status"], "not_found")


# ===================================================================
# 5. Routing Parity Validator Tests
# ===================================================================

class TestRoutingParityValidator(unittest.TestCase):
    """Tests for verifying deterministic/LLM result equivalence."""

    def setUp(self):
        self.rpv = RoutingParityValidator(tolerance=0.05)

    def test_validate_identical_results(self):
        det = {"answer": 42, "label": "ok"}
        llm = {"answer": 42, "label": "ok"}
        report = self.rpv.validate(det, llm)
        self.assertTrue(report["is_parity"])
        self.assertEqual(report["status"], "pass")

    def test_validate_mismatched_results(self):
        det = {"answer": 42}
        llm = {"answer": 99}
        report = self.rpv.validate(det, llm)
        self.assertFalse(report["is_parity"])
        self.assertEqual(report["status"], "fail")

    def test_validate_numeric_tolerance(self):
        det = {"value": 1.0}
        llm = {"value": 1.04}
        report = self.rpv.validate(det, llm)
        self.assertTrue(report["is_parity"])

    def test_validate_exceeds_tolerance(self):
        det = {"value": 1.0}
        llm = {"value": 1.1}
        report = self.rpv.validate(det, llm)
        self.assertFalse(report["is_parity"])

    def test_validate_specific_fields(self):
        det = {"a": 1, "b": 2}
        llm = {"a": 1, "b": 999}
        report = self.rpv.validate(det, llm, fields_to_compare=["a"])
        self.assertTrue(report["is_parity"])
        self.assertEqual(report["fields_checked"], 1)

    def test_bulk_validate(self):
        pairs = [
            ({"x": 1}, {"x": 1}),
            ({"x": 1}, {"x": 2}),
        ]
        report = self.rpv.bulk_validate(pairs)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["failed"], 1)
        self.assertFalse(report["overall_parity"])

    def test_compute_digest_deterministic(self):
        data = {"key": "value", "num": 42}
        d1 = self.rpv.compute_digest(data)
        d2 = self.rpv.compute_digest(data)
        self.assertEqual(d1, d2)
        self.assertEqual(len(d1), 64)  # SHA-256 hex

    def test_validation_log(self):
        self.rpv.validate({"a": 1}, {"a": 1})
        log = self.rpv.get_validation_log()
        self.assertEqual(len(log), 1)


# ===================================================================
# 6. Facade + Thread Safety
# ===================================================================

class TestLLMRoutingCompletenessFacade(unittest.TestCase):
    """Tests for the unified facade and cross-subsystem integration."""

    def test_get_status(self):
        lrc = LLMRoutingCompleteness()
        status = lrc.get_status()
        self.assertEqual(status["completeness"], "100%")
        self.assertEqual(status["status"], "active")
        self.assertIn("model_selection_matrix", status["subsystems"])

    def test_thread_safety_model_selection(self):
        msm = ModelSelectionMatrix()
        errors = []

        def worker():
            try:
                for _ in range(20):
                    msm.select_model("code")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)

    def test_end_to_end_flow(self):
        """Full pipeline: select model → optimise prompt → route → execute → validate."""
        lrc = LLMRoutingCompleteness()

        # 1. Model selection
        model = lrc.model_selector.select_model("code")
        self.assertEqual(model["status"], "selected")

        # 2. Prompt optimisation
        lrc.prompt_pipeline.register_template(PromptTemplate(
            "t1", "Code", ["code"], "Write code: {spec}", ["spec"],
        ))
        prompt = lrc.prompt_pipeline.optimise_prompt("code", {"spec": "hello"})
        self.assertEqual(prompt["status"], "optimised")

        # 3. Context-aware routing
        route = lrc.context_router.route("code", {})
        self.assertIn(route["route_type"], ("deterministic", "llm", "hybrid"))

        # 4. Hybrid execution
        specs = lrc.hybrid_engine.split_task({"data": [1], "query": "sum"})
        plan = lrc.hybrid_engine.create_plan("e2e", specs)
        exec_result = lrc.hybrid_engine.execute_plan(plan["plan_id"])
        self.assertEqual(exec_result["status"], "completed")

        # 5. Parity validation
        det = {"answer": 1}
        llm = {"answer": 1}
        val = lrc.parity_validator.validate(det, llm)
        self.assertTrue(val["is_parity"])


if __name__ == "__main__":
    unittest.main()

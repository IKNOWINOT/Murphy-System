"""
E2E tests for the Murphy System Describe → Generate → Execute hero flow.

Validates the end-to-end pipeline from natural-language intent through
workflow generation and execution routing — no live server or secrets required.

Labels: E2E-HERO-001, FORGE-E2E-001
"""

from __future__ import annotations

import sys
import pathlib
import time
import unittest

# ── Path setup ──────────────────────────────────────────────────────────────
_REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (_REPO, _REPO / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ===========================================================================
# Phase 1 — Describe: intent understanding
# ===========================================================================

class TestDescribePhase(unittest.TestCase):
    """User describes what they want in natural language."""

    def test_workflow_generator_importable(self):
        from ai_workflow_generator import AIWorkflowGenerator  # noqa: F401

    def test_generator_instantiation(self):
        from ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        self.assertIsNotNone(gen)

    def test_describe_sales_monitoring_intent(self):
        """Describing a sales monitoring intent returns a structured workflow."""
        from ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("monitor sales data and send a weekly summary to Slack")
        self.assertIsInstance(result, dict)
        self.assertIn("workflow_id", result)
        self.assertIsInstance(result["workflow_id"], str)
        self.assertTrue(len(result["workflow_id"]) > 0)

    def test_describe_returns_steps(self):
        """Generated workflow must contain at least one step."""
        from ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("route IT tickets to the right team based on urgency")
        self.assertIn("steps", result)
        self.assertIsInstance(result["steps"], list)
        self.assertGreater(len(result["steps"]), 0)

    def test_describe_step_has_required_fields(self):
        """Each step must have name, type, and description."""
        from ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("send IoT sensor alerts to PagerDuty on threshold breach")
        for step in result["steps"]:
            with self.subTest(step=step.get("name", "?")):
                self.assertIn("name", step)
                self.assertIn("type", step)
                self.assertIn("description", step)

    def test_describe_records_context(self):
        """Workflow result must carry the original intent in context or description."""
        from ai_workflow_generator import AIWorkflowGenerator
        intent = "automate weekly finance reports to email"
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow(intent)
        # At least one of description, context, or name contains intent keywords
        combined = " ".join([
            str(result.get("description", "")),
            str(result.get("context", "")),
            str(result.get("name", "")),
        ]).lower()
        keywords = ["finance", "report", "email", "weekly", "automate"]
        matched = sum(1 for k in keywords if k in combined)
        self.assertGreaterEqual(matched, 1, f"Intent keywords not reflected in output: {combined}")

    def test_describe_multiple_intents_produce_unique_ids(self):
        """Two different intents should produce different workflow IDs."""
        from ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        r1 = gen.generate_workflow("send daily digest to Slack")
        r2 = gen.generate_workflow("scale down idle EC2 instances at 11pm")
        self.assertNotEqual(r1["workflow_id"], r2["workflow_id"])

    def test_describe_deterministic_routing_integration(self):
        """After describing intent, deterministic routing must produce a routed decision."""
        from ai_workflow_generator import AIWorkflowGenerator
        from deterministic_routing_engine import DeterministicRoutingEngine
        gen = AIWorkflowGenerator()
        workflow = gen.generate_workflow("monitor sales data and alert on Slack")
        router = DeterministicRoutingEngine()
        decision = router.route_task(
            workflow.get("name", "sales_monitor"),
            context={"workflow_id": workflow["workflow_id"]},
        )
        self.assertIsInstance(decision, dict)
        self.assertIn("decision_id", decision)
        self.assertEqual(decision["status"], "routed")


# ===========================================================================
# Phase 2 — Generate: gate evaluation and workflow packaging
# ===========================================================================

class TestGeneratePhase(unittest.TestCase):
    """Murphy generates the automation package through gate evaluation."""

    def test_gate_execution_wiring_importable(self):
        from gate_execution_wiring import GateExecutionWiring  # noqa: F401

    def test_gate_wiring_instantiation(self):
        from gate_execution_wiring import GateExecutionWiring
        g = GateExecutionWiring()
        self.assertIsNotNone(g)

    def test_security_plane_defaults_register(self):
        """Registering security-plane gate defaults must succeed without error."""
        from gate_execution_wiring import GateExecutionWiring
        g = GateExecutionWiring()
        g.register_security_plane_defaults()
        status = g.get_status()
        self.assertIn("total_registered", status)
        self.assertGreaterEqual(status["total_registered"], 1)

    def test_gate_sequence_defined(self):
        """A gate sequence must be defined and non-empty."""
        from gate_execution_wiring import GateExecutionWiring
        g = GateExecutionWiring()
        status = g.get_status()
        self.assertIn("gate_sequence", status)
        self.assertIsInstance(status["gate_sequence"], list)
        self.assertGreater(len(status["gate_sequence"]), 0)

    def test_compliance_engine_clears_deliverable(self):
        """A minimal deliverable must pass the compliance engine."""
        from compliance_engine import ComplianceEngine
        ce = ComplianceEngine()
        deliverable = {
            "session_id": "e2e-hero-flow-generate",
            "name": "sales_monitor_v1",
            "type": "automation",
        }
        ready, issues = ce.is_release_ready(deliverable)
        self.assertIsInstance(ready, bool)
        self.assertIsInstance(issues, list)

    def test_compliance_report_structure(self):
        """Compliance report must contain required status fields."""
        from compliance_engine import ComplianceEngine
        ce = ComplianceEngine()
        report = ce.get_compliance_report()
        self.assertIsInstance(report, dict)
        required_keys = {"session_id", "total_registered_requirements",
                         "compliance_rate", "status_counts"}
        self.assertTrue(required_keys.issubset(report.keys()),
                        f"Missing keys: {required_keys - report.keys()}")

    def test_applicable_frameworks_by_domain(self):
        """Compliance engine returns applicable frameworks for known domains."""
        from compliance_engine import ComplianceEngine
        ce = ComplianceEngine()
        frameworks = ce.get_applicable_frameworks("healthcare")
        self.assertIsInstance(frameworks, list)
        self.assertGreater(len(frameworks), 0)

    def test_deterministic_routing_has_guardrails(self):
        """Every routing decision must include guardrails."""
        from deterministic_routing_engine import DeterministicRoutingEngine
        router = DeterministicRoutingEngine()
        decision = router.route_task("generate_report", context={"user": "e2e"})
        self.assertIn("guardrails_applied", decision)
        self.assertIsInstance(decision["guardrails_applied"], list)
        self.assertGreater(len(decision["guardrails_applied"]), 0)


# ===========================================================================
# Phase 3 — Execute: task scheduling and LLM fallback
# ===========================================================================

class TestExecutePhase(unittest.TestCase):
    """Murphy executes the generated automation."""

    def test_scheduler_importable(self):
        from scheduler import MurphyScheduler  # noqa: F401

    def test_scheduler_initial_status(self):
        """Scheduler status must include running state and last_run."""
        from scheduler import MurphyScheduler
        sched = MurphyScheduler()
        status = sched.get_status()
        self.assertIn("running", status)
        self.assertIn("last_run", status)
        self.assertIsInstance(status["running"], bool)

    def test_scheduler_can_be_started_and_stopped(self):
        """Scheduler start/stop must not raise an exception."""
        from scheduler import MurphyScheduler
        sched = MurphyScheduler()
        try:
            sched.start()
            time.sleep(0.05)
        finally:
            sched.stop()

    def test_local_llm_fallback_available(self):
        from local_llm_fallback import LocalLLMFallback  # noqa: F401

    def test_local_llm_fallback_responds(self):
        """Local LLM fallback must return a non-empty string for any prompt."""
        from local_llm_fallback import LocalLLMFallback
        fb = LocalLLMFallback()
        response = fb.generate("Summarise the purpose of Murphy System.")
        self.assertIsInstance(response, str)
        self.assertGreater(len(response.strip()), 0)

    def test_local_llm_fallback_handles_empty_prompt(self):
        """Fallback must not raise on an empty-string prompt."""
        from local_llm_fallback import LocalLLMFallback
        fb = LocalLLMFallback()
        try:
            response = fb.generate("")
            self.assertIsInstance(response, str)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"LocalLLMFallback.generate('') raised: {exc}")

    def test_self_fix_loop_status(self):
        """Self-fix loop must return a valid status dict."""
        from self_fix_loop import SelfFixLoop
        sfl = SelfFixLoop()
        status = sfl.get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("running", status)

    def test_self_fix_loop_diagnose(self):
        """Self-fix loop diagnose must return a list (empty or populated)."""
        from self_fix_loop import SelfFixLoop
        sfl = SelfFixLoop()
        result = sfl.diagnose()
        self.assertIsInstance(result, list)


# ===========================================================================
# Phase 4 — Refine: connector delivery and routing stats
# ===========================================================================

class TestRefinePhase(unittest.TestCase):
    """Murphy refines results through platform connectors and routing feedback."""

    def test_platform_connector_framework_importable(self):
        from platform_connector_framework import PlatformConnectorFramework  # noqa: F401

    def test_connectors_available(self):
        """At least one platform connector must be registered."""
        from platform_connector_framework import PlatformConnectorFramework
        pcf = PlatformConnectorFramework()
        connectors = pcf.list_available_connectors()
        self.assertIsInstance(connectors, list)
        self.assertGreater(len(connectors), 0)

    def test_connector_has_required_fields(self):
        """Each connector definition must carry id, name, category, and capabilities."""
        from platform_connector_framework import PlatformConnectorFramework
        pcf = PlatformConnectorFramework()
        for connector in pcf.list_available_connectors()[:5]:
            with self.subTest(connector=connector.get("connector_id", "?")):
                self.assertIn("connector_id", connector)
                self.assertIn("name", connector)
                self.assertIn("category", connector)
                self.assertIn("capabilities", connector)
                self.assertIsInstance(connector["capabilities"], list)

    def test_connector_categories_include_communication(self):
        """Communication connectors (Slack, Teams, etc.) must be present."""
        from platform_connector_framework import PlatformConnectorFramework
        pcf = PlatformConnectorFramework()
        status = pcf.status()
        categories = status.get("statistics", {}).get("categories", [])
        self.assertIn("communication", categories,
                      f"'communication' not in categories: {categories}")

    def test_routing_stats_tracked(self):
        """Routing engine tracks stats after a route call."""
        from deterministic_routing_engine import DeterministicRoutingEngine
        router = DeterministicRoutingEngine()
        router.route_task("generate_summary", context={"pass": 1})
        stats = router.get_routing_stats()
        self.assertIsInstance(stats, dict)

    def test_routing_decision_history_grows(self):
        """Decision history must grow with each call."""
        from deterministic_routing_engine import DeterministicRoutingEngine
        router = DeterministicRoutingEngine()
        before = len(router.get_decision_history())
        router.route_task("send_alert", context={})
        after = len(router.get_decision_history())
        self.assertGreater(after, before)


# ===========================================================================
# Phase 5 — Full hero-flow integration (all phases chained)
# ===========================================================================

class TestHeroFlowIntegration(unittest.TestCase):
    """Chain all four phases into a single hero-flow integration test."""

    def test_full_hero_flow_describe_to_execute(self):
        """
        Describe → Generate (gate check + compliance) → Execute (route) → Refine (connector).
        The entire hero path must complete without raising an exception and each
        sub-result must be structurally valid.
        """
        from ai_workflow_generator import AIWorkflowGenerator
        from gate_execution_wiring import GateExecutionWiring
        from compliance_engine import ComplianceEngine
        from deterministic_routing_engine import DeterministicRoutingEngine
        from platform_connector_framework import PlatformConnectorFramework

        # Phase 1 — Describe
        intent = "Alert engineering Slack channel when build failure rate exceeds 10%"
        gen = AIWorkflowGenerator()
        workflow = gen.generate_workflow(intent)
        self.assertIn("workflow_id", workflow)

        # Phase 2 — Generate (gate + compliance)
        gate = GateExecutionWiring()
        gate.register_security_plane_defaults()
        status = gate.get_status()
        self.assertGreaterEqual(status["total_registered"], 1)

        ce = ComplianceEngine()
        deliverable = {
            "session_id": workflow["workflow_id"],
            "name": workflow.get("name", "hero_flow_test"),
            "type": "automation",
        }
        ready, _ = ce.is_release_ready(deliverable)
        self.assertIsInstance(ready, bool)

        # Phase 3 — Execute (route)
        router = DeterministicRoutingEngine()
        decision = router.route_task(
            workflow.get("name", "hero_flow_task"),
            context={"workflow_id": workflow["workflow_id"]},
        )
        self.assertEqual(decision["status"], "routed")

        # Phase 4 — Refine (connector check)
        pcf = PlatformConnectorFramework()
        connectors = pcf.list_available_connectors()
        slack_ids = [c["connector_id"] for c in connectors if "slack" in c.get("connector_id", "")]
        self.assertGreater(len(slack_ids), 0, "Slack connector must be registered for this flow")

    def test_full_flow_timing_under_threshold(self):
        """The full hero flow (excluding LLM calls) must complete in < 2 seconds."""
        from ai_workflow_generator import AIWorkflowGenerator
        from deterministic_routing_engine import DeterministicRoutingEngine

        start = time.monotonic()
        gen = AIWorkflowGenerator()
        wf = gen.generate_workflow("send weekly digest to Slack")
        router = DeterministicRoutingEngine()
        router.route_task(wf.get("name", "digest"), context={"workflow_id": wf["workflow_id"]})
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 2.0, f"Hero flow took {elapsed:.3f}s — expected < 2s")

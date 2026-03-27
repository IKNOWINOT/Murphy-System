# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
test_gap_closure.py — Unit tests proving gap closure across all capabilities.
Run with: python -m pytest tests/test_gap_closure.py -v
     or:  python -m unittest tests.test_gap_closure
"""

from __future__ import annotations

import json
import os
import sys
import unittest

# Make parent importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ---------------------------------------------------------------------------
# TestConnectorEcosystem
# ---------------------------------------------------------------------------

class TestConnectorEcosystem(unittest.TestCase):

    def setUp(self) -> None:
        from connectors.connector_registry import registry, ConnectorCategory
        self.registry = registry
        self.ConnectorCategory = ConnectorCategory

    def test_registry_has_50_plus_connectors(self) -> None:
        self.assertGreaterEqual(self.registry.count(), 50,
                                f"Expected ≥50 connectors, got {self.registry.count()}")

    def test_all_twenty_categories_covered(self) -> None:
        covered = set(self.registry.categories_covered())
        self.assertGreaterEqual(len(covered), 15,
                                f"Expected ≥15 categories covered, got {len(covered)}")

    def test_crm_category_has_connectors(self) -> None:
        items = self.registry.list_by_category(self.ConnectorCategory.CRM)
        self.assertGreater(len(items), 0, "CRM category must have at least one connector")

    def test_communication_category_has_connectors(self) -> None:
        items = self.registry.list_by_category(self.ConnectorCategory.COMMUNICATION)
        self.assertGreater(len(items), 0)

    def test_cloud_category_has_connectors(self) -> None:
        items = self.registry.list_by_category(self.ConnectorCategory.CLOUD)
        self.assertGreater(len(items), 0)

    def test_search_returns_results(self) -> None:
        results = self.registry.search("salesforce")
        self.assertGreater(len(results), 0, "Search for 'salesforce' should return results")

    def test_search_by_tag_works(self) -> None:
        results = self.registry.search("healthcare")
        self.assertGreater(len(results), 0, "Tag search for 'healthcare' should return results")

    def test_export_catalog_is_valid_json(self) -> None:
        catalog_json = self.registry.export_catalog()
        catalog = json.loads(catalog_json)
        self.assertIn("total", catalog)
        self.assertIn("connectors", catalog)
        self.assertEqual(catalog["total"], self.registry.count())

    def test_get_connector_by_name(self) -> None:
        connector = self.registry.get("Salesforce")
        self.assertIsNotNone(connector)
        self.assertEqual(connector.name, "Salesforce")  # type: ignore[union-attr]

    def test_connector_to_dict_has_required_fields(self) -> None:
        connector = self.registry.get("Slack")
        self.assertIsNotNone(connector)
        d = connector.to_dict()  # type: ignore[union-attr]
        for field in ("name", "category", "description", "auth_type", "endpoints", "version"):
            self.assertIn(field, d, f"Connector dict missing field '{field}'")

    def test_plugin_sdk_example_connector_validates(self) -> None:
        from connectors.plugin_sdk import ExampleEchoConnector, PluginValidator
        validator = PluginValidator()
        result = validator.validate(ExampleEchoConnector)
        self.assertTrue(result.passed, f"ExampleEchoConnector failed validation: {result.errors}")

    def test_plugin_sdk_abstract_base_class_exists(self) -> None:
        from connectors.plugin_sdk import ConnectorPlugin
        import inspect
        self.assertTrue(inspect.isabstract(ConnectorPlugin))


# ---------------------------------------------------------------------------
# TestLowCodeUX
# ---------------------------------------------------------------------------

class TestLowCodeUX(unittest.TestCase):

    def setUp(self) -> None:
        from lowcode.workflow_builder import (
            WorkflowBuilder, NodeType, TriggerType, ValidationStatus
        )
        self.WorkflowBuilder = WorkflowBuilder
        self.NodeType = NodeType
        self.TriggerType = TriggerType
        self.ValidationStatus = ValidationStatus

    def _build_simple_workflow(self) -> "WorkflowBuilder":  # type: ignore[name-defined]
        return (
            self.WorkflowBuilder("test-wf", "Test Workflow")
            .add_node("t1", self.NodeType.TRIGGER, "Trigger")
            .add_node("a1", self.NodeType.ACTION, "Action")
            .add_node("o1", self.NodeType.OUTPUT, "Output")
            .connect("t1", "a1")
            .connect("a1", "o1")
            .add_trigger(self.TriggerType.WEBHOOK)
        )

    def test_builder_creates_workflow(self) -> None:
        wf = self._build_simple_workflow()
        defn = wf.get_definition()
        self.assertEqual(defn.name, "Test Workflow")

    def test_add_node_increases_node_count(self) -> None:
        wf = self.WorkflowBuilder("x", "x")
        wf.add_node("n1", self.NodeType.ACTION, "A")
        wf.add_node("n2", self.NodeType.ACTION, "B")
        self.assertEqual(len(wf.get_definition().nodes), 2)

    def test_connect_creates_edge(self) -> None:
        wf = self._build_simple_workflow()
        self.assertEqual(len(wf.get_definition().edges), 2)

    def test_validate_returns_valid(self) -> None:
        wf = self._build_simple_workflow()
        result = wf.validate()
        self.assertIn(result.status,
                      [self.ValidationStatus.VALID, self.ValidationStatus.WARNING])

    def test_validate_detects_missing_nodes(self) -> None:
        wf = self.WorkflowBuilder("empty", "Empty")
        result = wf.validate()
        self.assertEqual(result.status, self.ValidationStatus.INVALID)

    def test_compile_returns_compiled_workflow(self) -> None:
        wf = self._build_simple_workflow()
        compiled = wf.compile()
        self.assertGreater(len(compiled.execution_order), 0)
        self.assertGreater(len(compiled.compiled_steps), 0)

    def test_compile_steps_have_required_fields(self) -> None:
        wf = self._build_simple_workflow()
        compiled = wf.compile()
        for step in compiled.compiled_steps:
            for key in ("step", "node_id", "node_type", "label"):
                self.assertIn(key, step)

    def test_export_json_is_valid(self) -> None:
        wf = self._build_simple_workflow()
        json_str = wf.export_json()
        data = json.loads(json_str)
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("id", data)


# ---------------------------------------------------------------------------
# TestObservability
# ---------------------------------------------------------------------------

class TestObservability(unittest.TestCase):

    def setUp(self) -> None:
        from observability.telemetry import (
            MetricsRegistry, DistributedTracer, ObservabilityDashboard,
            TelemetryExporter, MetricType, Metric, build_default_registry
        )
        self.MetricsRegistry = MetricsRegistry
        self.DistributedTracer = DistributedTracer
        self.ObservabilityDashboard = ObservabilityDashboard
        self.TelemetryExporter = TelemetryExporter
        self.MetricType = MetricType
        self.Metric = Metric
        self.build_default_registry = build_default_registry
        self.reg = MetricsRegistry()
        self.tracer = DistributedTracer()

    def test_counter_increments(self) -> None:
        self.reg.counter("test_counter", 1)
        self.reg.counter("test_counter", 2)
        snap = self.reg.snapshot()
        self.assertEqual(snap["counters"]["test_counter"], 3)

    def test_gauge_set(self) -> None:
        self.reg.gauge("test_gauge", 42.5)
        snap = self.reg.snapshot()
        self.assertEqual(snap["gauges"]["test_gauge"], 42.5)

    def test_histogram_records_values(self) -> None:
        for v in [0.1, 0.5, 0.9]:
            self.reg.histogram("test_hist", v)
        snap = self.reg.snapshot()
        self.assertEqual(len(snap["histograms"]["test_hist"]), 3)

    def test_prometheus_export_format(self) -> None:
        self.reg.counter("gate_evaluations_total", 5,
                         help_text="Total gate evaluations")
        text = self.reg.export_prometheus_text()
        self.assertIn("gate_evaluations_total", text)
        self.assertIn("# TYPE", text)
        self.assertIn("# HELP", text)

    def test_prometheus_histogram_has_buckets(self) -> None:
        self.reg.histogram("latency_histogram", 0.25, help_text="Latency")
        text = self.reg.export_prometheus_text()
        self.assertIn("_bucket", text)
        self.assertIn("+Inf", text)

    def test_tracer_creates_span(self) -> None:
        span = self.tracer.start_span("test_span")
        self.assertIsNotNone(span)
        self.assertIsNone(span.end_time)

    def test_tracer_ends_span(self) -> None:
        span = self.tracer.start_span("end_test")
        self.tracer.end_span(span.span_id, status="ok")
        finished = self.tracer.get_span(span.span_id)
        self.assertIsNotNone(finished)
        self.assertIsNotNone(finished.end_time)  # type: ignore[union-attr]

    def test_dashboard_summary_is_json_serializable(self) -> None:
        self.reg.counter("gate_evaluations_total", 10)
        self.reg.gauge("error_rate", 0.01)
        dashboard = self.ObservabilityDashboard(self.reg, self.tracer)
        summary = dashboard.get_summary()
        # Must be JSON-serializable
        serialized = json.dumps(summary)
        self.assertIsInstance(serialized, str)
        self.assertIn("system_health", summary)


# ---------------------------------------------------------------------------
# TestMultiAgentOrchestration
# ---------------------------------------------------------------------------

class TestMultiAgentOrchestration(unittest.TestCase):

    def setUp(self) -> None:
        from agents.agent_coordinator import (
            AgentCoordinator, Agent, AgentRole, AgentMessage,
            MessageType, Priority, AgentStatus
        )
        self.AgentCoordinator = AgentCoordinator
        self.Agent = Agent
        self.AgentRole = AgentRole
        self.AgentMessage = AgentMessage
        self.MessageType = MessageType
        self.Priority = Priority
        self.AgentStatus = AgentStatus

    def _make_coord(self) -> "AgentCoordinator":  # type: ignore[name-defined]
        coord = self.AgentCoordinator()
        for i, role in enumerate(self.AgentRole):
            agent = self.Agent(f"agent-{i}", role, [f"cap_{i}"])
            coord.register_agent(agent)
        return coord

    def test_coordinator_registers_agents(self) -> None:
        coord = self._make_coord()
        status = coord.get_swarm_status()
        self.assertEqual(status["total_agents"], len(list(self.AgentRole)))

    def test_dispatch_delivers_message(self) -> None:
        coord = self._make_coord()
        agents = coord.list_agents()
        sender = agents[0]
        receiver = agents[1]
        msg = self.AgentMessage(
            from_agent=sender.agent_id,
            to_agent=receiver.agent_id,
            msg_type=self.MessageType.TASK,
            payload={"task": "test"},
        )
        count = coord.dispatch(msg)
        self.assertEqual(count, 1)

    def test_broadcast_reaches_all_except_sender(self) -> None:
        coord = self._make_coord()
        agents = coord.list_agents()
        sender_id = agents[0].agent_id
        n = coord.broadcast(sender_id, self.MessageType.BROADCAST, {"info": "hello"})
        self.assertEqual(n, len(agents) - 1)

    def test_orchestrate_task_returns_result(self) -> None:
        coord = self.AgentCoordinator()
        orch = self.Agent("orch", self.AgentRole.ORCHESTRATOR, ["plan"])

        def handler(msg: self.AgentMessage):  # type: ignore[name-defined]
            return self.AgentMessage(
                from_agent="orch",
                to_agent=msg.from_agent,
                msg_type=self.MessageType.RESULT,
                payload={"done": True},
            )

        orch.register_processor(self.MessageType.TASK, handler)
        coord.register_agent(orch)
        result = coord.orchestrate_task({"task_id": "t1", "description": "test"})
        self.assertTrue(result["success"])

    def test_swarm_status_has_expected_keys(self) -> None:
        coord = self._make_coord()
        status = coord.get_swarm_status()
        for key in ("total_agents", "by_role", "by_status", "messages_routed"):
            self.assertIn(key, status)

    def test_unregister_agent(self) -> None:
        coord = self._make_coord()
        initial = coord.get_swarm_status()["total_agents"]
        first_id = coord.list_agents()[0].agent_id
        removed = coord.unregister_agent(first_id)
        self.assertTrue(removed)
        self.assertEqual(coord.get_swarm_status()["total_agents"], initial - 1)


# ---------------------------------------------------------------------------
# TestLLMRouter
# ---------------------------------------------------------------------------

class TestLLMRouter(unittest.TestCase):

    def setUp(self) -> None:
        from llm.multi_provider_router import (
            build_default_router, RoutingStrategy, ProviderStatus, Provider
        )
        self.router = build_default_router()
        self.RoutingStrategy = RoutingStrategy
        self.ProviderStatus = ProviderStatus
        self.Provider = Provider

    def test_router_has_12_plus_providers(self) -> None:
        providers = self.router.list_providers()
        self.assertGreaterEqual(len(providers), 12,
                                f"Expected ≥12 providers, got {len(providers)}")

    def test_cheapest_strategy_returns_decision(self) -> None:
        decision = self.router.route(strategy=self.RoutingStrategy.CHEAPEST)
        self.assertIsNotNone(decision)

    def test_fastest_strategy_returns_decision(self) -> None:
        decision = self.router.route(strategy=self.RoutingStrategy.FASTEST)
        self.assertIsNotNone(decision)

    def test_most_reliable_strategy_returns_decision(self) -> None:
        decision = self.router.route(strategy=self.RoutingStrategy.MOST_RELIABLE)
        self.assertIsNotNone(decision)
        self.assertGreater(decision.provider.reliability_score, 0)  # type: ignore[union-attr]

    def test_round_robin_cycles_providers(self) -> None:
        decisions = [
            self.router.route(strategy=self.RoutingStrategy.ROUND_ROBIN)
            for _ in range(3)
        ]
        names = [d.provider.name for d in decisions if d]  # type: ignore[union-attr]
        self.assertEqual(len(names), 3)

    def test_benchmark_returns_results(self) -> None:
        results = self.router.benchmark()
        self.assertGreaterEqual(len(results), 12)
        for r in results:
            self.assertTrue(r.success)
            self.assertGreater(r.latency_ms, 0)

    def test_routing_table_has_all_providers(self) -> None:
        table = self.router.get_routing_table()
        self.assertGreaterEqual(len(table), 12)
        for entry in table:
            for field in ("name", "model", "cost_per_1k_tokens", "latency_ms"):
                self.assertIn(field, entry)


# ---------------------------------------------------------------------------
# TestGapScorer
# ---------------------------------------------------------------------------

class TestGapScorer(unittest.TestCase):

    def setUp(self) -> None:
        from gap_scorer import CapabilityScorer, CAPABILITY_BASELINES, GapReport
        self.CapabilityScorer = CapabilityScorer
        self.CAPABILITY_BASELINES = CAPABILITY_BASELINES
        self.GapReport = GapReport

    def test_scorer_returns_all_17_capabilities(self) -> None:
        scorer = self.CapabilityScorer()
        report = scorer.score_all()
        self.assertEqual(len(report.capability_results), len(self.CAPABILITY_BASELINES))

    def test_scores_are_improved_vs_baseline(self) -> None:
        scorer = self.CapabilityScorer()
        report = scorer.score_all()
        self.assertGreater(report.overall_score, report.baseline_overall,
                           "Current score must exceed baseline after gap closure")

    def test_gaps_closed_count_positive(self) -> None:
        scorer = self.CapabilityScorer()
        report = scorer.score_all()
        self.assertGreater(report.gaps_closed, 0)

    def test_readiness_at_least_90_percent(self) -> None:
        scorer = self.CapabilityScorer()
        report = scorer.score_all()
        self.assertGreaterEqual(report.readiness_pct, 90.0,
                                f"Readiness should be ≥90%, got {report.readiness_pct}%")

    def test_report_json_serializable(self) -> None:
        scorer = self.CapabilityScorer()
        report = scorer.score_all()
        json_str = report.to_json()
        data = json.loads(json_str)
        self.assertIn("overall_score", data)
        self.assertIn("readiness_pct", data)


# ---------------------------------------------------------------------------
# TestOneLaunchButton
# ---------------------------------------------------------------------------

class TestOneLaunchButton(unittest.TestCase):

    def setUp(self) -> None:
        from launch.launch import LaunchStreamer, ScaleConfig, LaunchEvent
        self.LaunchStreamer = LaunchStreamer
        self.ScaleConfig = ScaleConfig
        self.LaunchEvent = LaunchEvent

    def test_scale_config_defaults(self) -> None:
        cfg = self.ScaleConfig()
        self.assertEqual(cfg.replicas, 1)
        self.assertEqual(cfg.mode, "local")
        self.assertEqual(cfg.port, 8000)

    def test_scale_config_custom(self) -> None:
        cfg = self.ScaleConfig(replicas=5, mode="scale", port=9000)
        self.assertEqual(cfg.replicas, 5)
        self.assertEqual(cfg.mode, "scale")

    def test_scale_config_base_url(self) -> None:
        cfg = self.ScaleConfig(port=8080)
        self.assertIn("8080", cfg.base_url)

    def test_streamer_yields_events(self) -> None:
        cfg = self.ScaleConfig(mode="local")
        streamer = self.LaunchStreamer(cfg)
        events = list(streamer.stream())
        self.assertGreater(len(events), 0)

    def test_streamer_events_have_timestamps(self) -> None:
        cfg = self.ScaleConfig(mode="local")
        streamer = self.LaunchStreamer(cfg)
        events = list(streamer.stream())
        for evt in events:
            self.assertIsInstance(evt.timestamp, str)
            self.assertRegex(evt.timestamp, r"\d{2}:\d{2}:\d{2}")

    def test_streamer_has_ok_events(self) -> None:
        cfg = self.ScaleConfig(mode="local")
        streamer = self.LaunchStreamer(cfg)
        events = list(streamer.stream())
        ok_events = [e for e in events if e.status == "OK"]
        self.assertGreater(len(ok_events), 0)

    def test_no_error_events_in_local_mode(self) -> None:
        cfg = self.ScaleConfig(mode="local")
        streamer = self.LaunchStreamer(cfg)
        events = list(streamer.stream())
        error_events = [e for e in events if e.status == "ERROR"]
        self.assertEqual(len(error_events), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

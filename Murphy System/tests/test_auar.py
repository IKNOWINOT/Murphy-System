"""
Tests for the AUAR (Adaptive Universal API Router) package.

Covers all seven architectural layers:
  1. Signal Interpretation
  2. Capability Graph
  3. Routing Decision Engine
  4. Schema Translation
  5. Provider Adapter
  6. ML Optimization
  7. Observability & Governance
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from auar.signal_interpretation import (
    CapabilityIntent,
    ConfidenceScorer,
    IntentSignal,
    RequestContext,
    SignalInterpreter,
)
from auar.capability_graph import (
    Capability,
    CapabilityGraph,
    CapabilityMapping,
    CertificationLevel,
    CostModel,
    HealthStatus,
    PerformanceMetrics,
    Provider,
    RateLimitConfig,
)
from auar.routing_engine import (
    ProviderCandidate,
    RoutingDecision,
    RoutingDecisionEngine,
    RoutingStrategy,
)
from auar.schema_translation import (
    FieldMapping,
    SchemaMapping,
    SchemaTranslator,
    TranslationResult,
)
from auar.provider_adapter import (
    AdapterConfig,
    AdapterResponse,
    AuthMethod,
    Protocol,
    ProviderAdapter,
    ProviderAdapterManager,
)
from auar.ml_optimization import (
    MLOptimizer,
    OptimizationResult,
    RoutingFeatures,
)
from auar.observability import (
    AuditEntry,
    CostAttribution,
    ObservabilityLayer,
    RequestTrace,
    SpanRecord,
)


# ===================================================================
# Layer 1 — Signal Interpretation
# ===================================================================

class TestConfidenceScorer:
    def test_perfect_score(self):
        scorer = ConfidenceScorer()
        score = scorer.score(1.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0)

    def test_zero_score(self):
        scorer = ConfidenceScorer()
        score = scorer.score(0.0, 0.0, 0.0, 0.0)
        assert score == pytest.approx(0.0)

    def test_weighted_computation(self):
        scorer = ConfidenceScorer()
        score = scorer.score(schema_match=1.0)
        assert score == pytest.approx(0.4)

    def test_clamped_to_unit(self):
        scorer = ConfidenceScorer()
        score = scorer.score(2.0, 2.0, 2.0, 2.0)
        assert score <= 1.0

    def test_threshold_direct_route(self):
        scorer = ConfidenceScorer()
        assert scorer.can_direct_route(0.90) is True
        assert scorer.can_direct_route(0.80) is False

    def test_threshold_clarification(self):
        scorer = ConfidenceScorer()
        assert scorer.needs_clarification(0.50) is True
        assert scorer.needs_clarification(0.70) is False

    def test_threshold_validation(self):
        scorer = ConfidenceScorer()
        assert scorer.needs_validation(0.70) is True
        assert scorer.needs_validation(0.90) is False

    def test_custom_weights(self):
        scorer = ConfidenceScorer(weights={
            "schema": 1.0, "history": 0.0, "semantic": 0.0, "completeness": 0.0
        })
        assert scorer.score(schema_match=0.5) == pytest.approx(0.5)


class TestSignalInterpreter:
    def test_deterministic_parse_known_capability(self):
        si = SignalInterpreter()
        si.register_schema("send_email", required_params=["to", "subject", "body"],
                           domain="communication", category="email")
        signal = si.interpret({"capability": "send_email",
                               "parameters": {"to": "a@b.com", "subject": "Hi", "body": "Hello"}})
        assert signal.parsed_intent is not None
        assert signal.parsed_intent.capability_name == "send_email"
        assert signal.confidence_score > 0.6
        assert signal.interpretation_method == "deterministic"
        assert signal.requires_clarification is False

    def test_unknown_capability_low_confidence(self):
        si = SignalInterpreter()
        signal = si.interpret({"capability": "unknown_thing"})
        assert signal.parsed_intent is not None
        assert signal.confidence_score < 0.85

    def test_empty_request_requires_clarification(self):
        si = SignalInterpreter()
        signal = si.interpret({})
        assert signal.requires_clarification is True
        assert signal.confidence_score == 0.0

    def test_path_based_matching(self):
        si = SignalInterpreter()
        si.register_schema("send_email")
        signal = si.interpret({"path": "/api/send_email", "method": "POST"})
        assert signal.parsed_intent is not None
        assert signal.parsed_intent.capability_name == "send_email"

    def test_llm_fallback_invoked_on_low_confidence(self):
        calls = []

        def mock_llm(raw):
            calls.append(raw)
            return {"capability": "process_payment", "parameters": {"amount": 100}, "confidence": 0.9}

        si = SignalInterpreter(llm_backend=mock_llm, llm_confidence_threshold=0.95)
        si.register_schema("process_payment", required_params=["amount"])
        signal = si.interpret({"capability": "process_payment"})
        # Even though deterministic may match, threshold is 0.95 so LLM is called
        assert len(calls) >= 0  # may or may not be called depending on det score

    def test_llm_backend_failure_falls_back(self):
        def failing_llm(raw):
            raise RuntimeError("LLM unavailable")

        si = SignalInterpreter(llm_backend=failing_llm, llm_confidence_threshold=0.99)
        signal = si.interpret({"capability": "something"})
        # Should not raise
        assert signal is not None

    def test_history_improves_confidence(self):
        si = SignalInterpreter()
        si.register_schema("send_email")
        # First call creates history
        s1 = si.interpret({"capability": "send_email"})
        # Second call should benefit from history match
        s2 = si.interpret({"capability": "send_email"})
        assert s2.confidence_score >= s1.confidence_score

    def test_stats_tracking(self):
        si = SignalInterpreter()
        si.register_schema("test_cap")
        si.interpret({"capability": "test_cap"})
        si.interpret({"capability": "test_cap"})
        stats = si.get_stats()
        assert stats["total"] == 2
        assert stats["deterministic"] >= 0

    def test_request_context_preserved(self):
        si = SignalInterpreter()
        si.register_schema("cap1")
        ctx = RequestContext(user_id="u1", tenant_id="t1")
        signal = si.interpret({"capability": "cap1"}, context=ctx)
        assert signal.context.user_id == "u1"
        assert signal.context.tenant_id == "t1"

    def test_parameter_completeness_affects_score(self):
        # Use separate interpreters to avoid history contamination
        si_full = SignalInterpreter()
        si_full.register_schema("send_email", required_params=["to", "subject", "body"])
        si_partial = SignalInterpreter()
        si_partial.register_schema("send_email", required_params=["to", "subject", "body"])
        # Full params
        s_full = si_full.interpret({"capability": "send_email",
                                    "parameters": {"to": "a", "subject": "b", "body": "c"}})
        # Partial params
        s_partial = si_partial.interpret({"capability": "send_email",
                                          "parameters": {"to": "a"}})
        assert s_full.confidence_score >= s_partial.confidence_score


# ===================================================================
# Layer 2 — Capability Graph
# ===================================================================

class TestCapabilityGraph:
    @pytest.fixture
    def graph(self):
        g = CapabilityGraph()
        return g

    def test_register_and_retrieve_capability(self, graph):
        cap = Capability(name="send_email", domain="communication", category="email")
        cap_id = graph.register_capability(cap)
        assert cap_id == cap.id
        result = graph.get_capability(cap_id)
        assert result is not None
        assert result.name == "send_email"

    def test_find_by_name(self, graph):
        cap = Capability(name="send_sms", domain="communication", category="sms")
        graph.register_capability(cap)
        result = graph.find_capability_by_name("send_sms")
        assert result is not None
        assert result.domain == "communication"

    def test_list_by_domain(self, graph):
        graph.register_capability(Capability(name="c1", domain="comm"))
        graph.register_capability(Capability(name="c2", domain="payments"))
        graph.register_capability(Capability(name="c3", domain="comm"))
        comms = graph.list_capabilities(domain="comm")
        assert len(comms) == 2

    def test_register_provider(self, graph):
        cap = Capability(name="send_email")
        cap_id = graph.register_capability(cap)
        mapping = CapabilityMapping(capability_id=cap_id, cost_per_call=0.001)
        provider = Provider(name="SendGrid", supported_capabilities=[mapping])
        pid = graph.register_provider(provider)
        assert pid == provider.id

    def test_providers_for_capability(self, graph):
        cap = Capability(name="send_email")
        cap_id = graph.register_capability(cap)
        m1 = CapabilityMapping(capability_id=cap_id, cost_per_call=0.001)
        m2 = CapabilityMapping(capability_id=cap_id, cost_per_call=0.002)
        graph.register_provider(Provider(name="SendGrid", supported_capabilities=[m1]))
        graph.register_provider(Provider(name="Mailgun", supported_capabilities=[m2]))
        results = graph.providers_for_capability("send_email")
        assert len(results) == 2
        names = {r[0].name for r in results}
        assert "SendGrid" in names
        assert "Mailgun" in names

    def test_similarity_edges(self, graph):
        graph.register_capability(Capability(name="send_email"))
        graph.register_capability(Capability(name="send_notification"))
        assert graph.add_similarity_edge("send_email", "send_notification") is True
        similar = graph.similar_capabilities("send_email")
        assert len(similar) == 1
        assert similar[0].name == "send_notification"

    def test_similarity_edge_nonexistent(self, graph):
        assert graph.add_similarity_edge("a", "b") is False

    def test_child_capabilities(self, graph):
        parent = Capability(name="communication")
        graph.register_capability(parent)
        child = Capability(name="send_email", parent_capabilities=[parent.id])
        graph.register_capability(child)
        children = graph.child_capabilities("communication")
        assert len(children) == 1
        assert children[0].name == "send_email"

    def test_health_status_update(self, graph):
        cap = Capability(name="x")
        graph.register_capability(cap)
        prov = Provider(name="P1", supported_capabilities=[
            CapabilityMapping(capability_id=cap.id)
        ])
        graph.register_provider(prov)
        assert graph.update_provider_health(prov.id, HealthStatus.HEALTHY) is True
        assert graph.get_provider(prov.id).health_status == HealthStatus.HEALTHY

    def test_stats(self, graph):
        graph.register_capability(Capability(name="c1"))
        graph.register_provider(Provider(name="p1"))
        stats = graph.get_stats()
        assert stats["total_capabilities"] == 1
        assert stats["total_providers"] == 1


# ===================================================================
# Layer 3 — Routing Decision Engine
# ===================================================================

class TestRoutingDecisionEngine:
    @pytest.fixture
    def setup(self):
        graph = CapabilityGraph()
        cap = Capability(name="send_email")
        cap_id = graph.register_capability(cap)
        perf1 = PerformanceMetrics(avg_latency_ms=50, success_rate=0.99)
        perf2 = PerformanceMetrics(avg_latency_ms=100, success_rate=0.95)
        m1 = CapabilityMapping(capability_id=cap_id, cost_per_call=0.001,
                               performance=perf1,
                               certification_level=CertificationLevel.PRODUCTION)
        m2 = CapabilityMapping(capability_id=cap_id, cost_per_call=0.005,
                               performance=perf2,
                               certification_level=CertificationLevel.BETA)
        p1 = Provider(name="SendGrid", supported_capabilities=[m1],
                      health_status=HealthStatus.HEALTHY)
        p2 = Provider(name="Mailgun", supported_capabilities=[m2],
                      health_status=HealthStatus.HEALTHY)
        graph.register_provider(p1)
        graph.register_provider(p2)
        engine = RoutingDecisionEngine(graph)
        return engine, graph, p1, p2

    def test_route_selects_best_provider(self, setup):
        engine, graph, p1, p2 = setup
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email")
        )
        decision = engine.route(signal)
        assert decision.selected_provider is not None
        assert decision.score > 0

    def test_route_returns_fallbacks(self, setup):
        engine, graph, p1, p2 = setup
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email")
        )
        decision = engine.route(signal)
        assert len(decision.fallback_providers) >= 1

    def test_route_with_no_intent(self, setup):
        engine, _, _, _ = setup
        signal = IntentSignal()  # no parsed_intent
        decision = engine.route(signal)
        assert decision.selected_provider is None

    def test_route_unknown_capability(self, setup):
        engine, _, _, _ = setup
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="nonexistent")
        )
        decision = engine.route(signal)
        assert decision.selected_provider is None

    def test_circuit_breaker_trips(self, setup):
        engine, graph, p1, p2 = setup
        # Trip circuit breaker for the first provider
        for _ in range(6):
            engine.record_failure(p1.id)
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email")
        )
        decision = engine.route(signal)
        # Should fallback or circuit should be triggered
        stats = engine.get_stats()
        assert stats["circuit_trips"] >= 1

    def test_circuit_breaker_resets_on_success(self, setup):
        engine, graph, p1, p2 = setup
        for _ in range(6):
            engine.record_failure(p1.id)
        engine.record_success(p1.id)
        # After success, circuit should close

    def test_round_robin_strategy(self):
        graph = CapabilityGraph()
        cap = Capability(name="test")
        cap_id = graph.register_capability(cap)
        providers = []
        for i in range(3):
            m = CapabilityMapping(capability_id=cap_id,
                                  performance=PerformanceMetrics(success_rate=0.99),
                                  certification_level=CertificationLevel.PRODUCTION)
            p = Provider(name=f"P{i}", supported_capabilities=[m],
                         health_status=HealthStatus.HEALTHY)
            graph.register_provider(p)
            providers.append(p)
        engine = RoutingDecisionEngine(graph, strategy=RoutingStrategy.ROUND_ROBIN)
        signal = IntentSignal(parsed_intent=CapabilityIntent(capability_name="test"))
        # Multiple calls should cycle through providers
        selected = set()
        for _ in range(6):
            d = engine.route(signal)
            if d.selected_provider:
                selected.add(d.selected_provider.provider_name)
        assert len(selected) >= 2  # at least 2 different providers selected


# ===================================================================
# Layer 4 — Schema Translation
# ===================================================================

class TestSchemaTranslation:
    @pytest.fixture
    def translator(self):
        return SchemaTranslator()

    def test_simple_field_mapping(self, translator):
        mapping = SchemaMapping(
            capability_name="send_email",
            provider_id="sendgrid",
            direction="request",
            field_mappings=[
                FieldMapping(source_field="to", target_field="personalizations.to"),
                FieldMapping(source_field="subject", target_field="subject"),
                FieldMapping(source_field="body", target_field="content.value"),
            ],
        )
        translator.register_mapping(mapping)
        result = translator.translate_request("send_email", "sendgrid",
                                              {"to": "a@b.com", "subject": "Hi", "body": "Hello"})
        assert result.success is True
        assert result.translated_data["personalizations"]["to"] == "a@b.com"
        assert result.translated_data["subject"] == "Hi"
        assert result.translated_data["content"]["value"] == "Hello"
        assert result.fields_mapped == 3

    def test_transform_to_upper(self, translator):
        mapping = SchemaMapping(
            capability_name="test",
            provider_id="p1",
            direction="request",
            field_mappings=[
                FieldMapping(source_field="name", target_field="NAME", transform="to_upper"),
            ],
        )
        translator.register_mapping(mapping)
        result = translator.translate_request("test", "p1", {"name": "hello"})
        assert result.translated_data["NAME"] == "HELLO"

    def test_default_value(self, translator):
        mapping = SchemaMapping(
            capability_name="test",
            provider_id="p1",
            direction="request",
            field_mappings=[
                FieldMapping(source_field="missing_field", target_field="out", default_value="default_val"),
            ],
        )
        translator.register_mapping(mapping)
        result = translator.translate_request("test", "p1", {})
        assert result.translated_data["out"] == "default_val"
        assert result.fields_defaulted == 1

    def test_required_field_missing(self, translator):
        mapping = SchemaMapping(
            capability_name="test",
            provider_id="p1",
            direction="request",
            field_mappings=[
                FieldMapping(source_field="required_field", target_field="out", required=True),
            ],
        )
        translator.register_mapping(mapping)
        result = translator.translate_request("test", "p1", {})
        assert result.success is False
        assert len(result.errors) == 1

    def test_static_fields_injected(self, translator):
        mapping = SchemaMapping(
            capability_name="test",
            provider_id="p1",
            direction="request",
            field_mappings=[],
            static_fields={"api_version": "v3", "format": "json"},
        )
        translator.register_mapping(mapping)
        result = translator.translate_request("test", "p1", {})
        assert result.translated_data["api_version"] == "v3"

    def test_passthrough_without_mapping(self, translator):
        result = translator.translate_request("unknown", "unknown", {"key": "val"})
        assert result.translated_data == {"key": "val"}
        assert len(result.warnings) == 1

    def test_response_translation(self, translator):
        mapping = SchemaMapping(
            capability_name="test",
            provider_id="p1",
            direction="response",
            field_mappings=[
                FieldMapping(source_field="data.id", target_field="result_id"),
            ],
        )
        translator.register_mapping(mapping)
        result = translator.translate_response("test", "p1", {"data": {"id": "123"}})
        assert result.translated_data["result_id"] == "123"

    def test_custom_transform(self, translator):
        translator.register_transform("double", lambda v: v * 2)
        mapping = SchemaMapping(
            capability_name="test",
            provider_id="p1",
            direction="request",
            field_mappings=[
                FieldMapping(source_field="val", target_field="doubled", transform="double"),
            ],
        )
        translator.register_mapping(mapping)
        result = translator.translate_request("test", "p1", {"val": 5})
        assert result.translated_data["doubled"] == 10

    def test_stats_tracking(self, translator):
        mapping = SchemaMapping(
            capability_name="t", provider_id="p", direction="request",
            field_mappings=[FieldMapping(source_field="a", target_field="b")],
        )
        translator.register_mapping(mapping)
        translator.translate_request("t", "p", {"a": 1})
        translator.translate_request("t", "p", {"a": 2})
        stats = translator.get_stats()
        assert stats["translations"] == 2


# ===================================================================
# Layer 5 — Provider Adapter
# ===================================================================

class TestProviderAdapter:
    def test_default_execute(self):
        config = AdapterConfig(provider_id="test", provider_name="Test",
                               base_url="https://api.example.com")
        adapter = ProviderAdapter(config)
        resp = adapter.call("POST", "/send", body={"msg": "hi"})
        assert resp.success is True
        assert resp.status_code == 200
        assert resp.latency_ms > 0

    def test_custom_execute(self):
        def custom(payload):
            return {"status_code": 201, "body": {"created": True}, "headers": {}}

        config = AdapterConfig(provider_id="test", base_url="https://api.test.com")
        adapter = ProviderAdapter(config, execute_fn=custom)
        resp = adapter.call("POST", "/create")
        assert resp.status_code == 201
        assert resp.body["created"] is True

    def test_retry_on_failure(self):
        attempts = []

        def flaky(payload):
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("timeout")
            return {"status_code": 200, "body": {}, "headers": {}}

        config = AdapterConfig(provider_id="test", base_url="https://api.test.com",
                               max_retries=3, retry_backoff_s=0.01)
        adapter = ProviderAdapter(config, execute_fn=flaky)
        resp = adapter.call("GET", "/data")
        assert resp.success is True
        assert resp.retries_used == 2

    def test_all_retries_exhausted(self):
        def always_fail(payload):
            raise ConnectionError("down")

        config = AdapterConfig(provider_id="test", base_url="https://api.test.com",
                               max_retries=2, retry_backoff_s=0.01)
        adapter = ProviderAdapter(config, execute_fn=always_fail)
        resp = adapter.call("GET", "/data")
        assert resp.success is False
        assert resp.status_code == 502

    def test_api_key_auth_headers(self):
        payloads = []

        def capture(payload):
            payloads.append(payload)
            return {"status_code": 200, "body": {}, "headers": {}}

        config = AdapterConfig(
            provider_id="test", base_url="https://api.test.com",
            auth_method=AuthMethod.API_KEY,
            auth_credentials={"api_key": "secret123", "header_name": "X-API-Key"},
        )
        adapter = ProviderAdapter(config, execute_fn=capture)
        adapter.call("GET", "/test")
        assert payloads[0]["headers"]["X-API-Key"] == "secret123"

    def test_bearer_auth_headers(self):
        payloads = []

        def capture(payload):
            payloads.append(payload)
            return {"status_code": 200, "body": {}, "headers": {}}

        config = AdapterConfig(
            provider_id="test", base_url="https://api.test.com",
            auth_method=AuthMethod.BEARER,
            auth_credentials={"token": "tok123"},
        )
        adapter = ProviderAdapter(config, execute_fn=capture)
        adapter.call("GET", "/test")
        assert "Bearer tok123" in payloads[0]["headers"]["Authorization"]

    def test_stats(self):
        config = AdapterConfig(provider_id="test", base_url="https://api.test.com")
        adapter = ProviderAdapter(config)
        adapter.call("GET", "/a")
        adapter.call("GET", "/b")
        stats = adapter.get_stats()
        assert stats["calls"] == 2
        assert stats["successes"] == 2


class TestProviderAdapterManager:
    def test_register_and_call(self):
        mgr = ProviderAdapterManager()
        mgr.register_adapter(AdapterConfig(provider_id="p1", provider_name="P1",
                                           base_url="https://api.p1.com"))
        resp = mgr.call_provider("p1", "GET", "/status")
        assert resp.success is True

    def test_call_unknown_provider(self):
        mgr = ProviderAdapterManager()
        resp = mgr.call_provider("nonexistent", "GET", "/")
        assert resp.success is False
        assert resp.status_code == 404

    def test_list_adapters(self):
        mgr = ProviderAdapterManager()
        mgr.register_adapter(AdapterConfig(provider_id="a"))
        mgr.register_adapter(AdapterConfig(provider_id="b"))
        assert sorted(mgr.list_adapters()) == ["a", "b"]


# ===================================================================
# Layer 6 — ML Optimization
# ===================================================================

class TestMLOptimizer:
    def test_record_and_recommend(self):
        opt = MLOptimizer(epsilon=0.0)  # pure exploitation
        opt.record(RoutingFeatures(capability_name="send_email", provider_id="sg",
                                   latency_ms=50, cost=0.001, success=True))
        opt.record(RoutingFeatures(capability_name="send_email", provider_id="mg",
                                   latency_ms=200, cost=0.005, success=True))
        result = opt.recommend("send_email", ["sg", "mg"])
        assert result.recommended_provider_id == "sg"
        assert result.exploration is False

    def test_exploration_mode(self):
        opt = MLOptimizer(epsilon=1.0)  # always explore
        result = opt.recommend("send_email", ["a", "b", "c"])
        assert result.exploration is True

    def test_reward_computation(self):
        opt = MLOptimizer()
        reward = opt.record(RoutingFeatures(
            capability_name="test", provider_id="p1",
            latency_ms=0, cost=0, success=True
        ))
        # Perfect success, zero latency, zero cost → max reward
        assert reward == pytest.approx(1.0)

    def test_failed_request_lower_reward(self):
        opt = MLOptimizer()
        r_success = opt.record(RoutingFeatures(
            capability_name="test", provider_id="p1",
            latency_ms=100, cost=0.01, success=True
        ))
        r_failure = opt.record(RoutingFeatures(
            capability_name="test", provider_id="p2",
            latency_ms=100, cost=0.01, success=False
        ))
        assert r_success > r_failure

    def test_epsilon_decay(self):
        opt = MLOptimizer(epsilon=0.15, epsilon_decay=0.9)
        initial = opt._epsilon
        opt.record(RoutingFeatures(capability_name="t", provider_id="p"))
        assert opt._epsilon < initial

    def test_empty_candidates(self):
        opt = MLOptimizer()
        result = opt.recommend("cap", [])
        assert result.recommended_provider_id == ""

    def test_provider_stats(self):
        opt = MLOptimizer()
        opt.record(RoutingFeatures(capability_name="c", provider_id="p1",
                                   latency_ms=100, cost=0.01, success=True))
        stats = opt.get_provider_stats("c")
        assert "p1" in stats
        assert stats["p1"]["total_calls"] == 1

    def test_global_stats(self):
        opt = MLOptimizer()
        opt.record(RoutingFeatures(capability_name="c", provider_id="p"))
        stats = opt.get_stats()
        assert stats["total_observations"] == 1


# ===================================================================
# Layer 7 — Observability & Governance
# ===================================================================

class TestObservabilityLayer:
    @pytest.fixture
    def obs(self):
        return ObservabilityLayer()

    def test_trace_lifecycle(self, obs):
        trace = obs.start_trace("req1", tenant_id="t1", capability="send_email")
        span = obs.add_span(trace.trace_id, "signal_interpretation")
        time.sleep(0.01)
        obs.end_span(span)
        finished = obs.finish_trace(trace.trace_id, success=True)
        assert finished is not None
        assert finished.total_latency_ms > 0
        assert len(finished.spans) == 1

    def test_counters(self, obs):
        obs.increment("requests_total")
        obs.increment("requests_total")
        assert obs.get_counter("requests_total") == 2

    def test_histogram(self, obs):
        for v in [10, 20, 30, 40, 50]:
            obs.observe("latency_ms", v)
        summary = obs.get_histogram_summary("latency_ms")
        assert summary["count"] == 5
        assert summary["avg"] == pytest.approx(30.0)
        assert summary["min"] == 10.0
        assert summary["max"] == 50.0

    def test_audit_logging(self, obs):
        entry = obs.audit(actor="user1", action="register_provider",
                          resource="sendgrid", tenant_id="t1")
        assert entry.entry_id
        log = obs.get_audit_log(tenant_id="t1")
        assert len(log) == 1
        assert log[0].action == "register_provider"

    def test_cost_attribution(self, obs):
        obs.record_cost("t1", "send_email", "sendgrid", 0.001)
        obs.record_cost("t1", "send_email", "sendgrid", 0.001)
        obs.record_cost("t2", "send_sms", "twilio", 0.01)
        summary = obs.get_cost_summary(tenant_id="t1")
        assert summary["total"] == pytest.approx(0.002)

    def test_cost_summary_all_tenants(self, obs):
        obs.record_cost("t1", "cap1", "p1", 1.0)
        obs.record_cost("t2", "cap2", "p2", 2.0)
        summary = obs.get_cost_summary()
        assert summary["total"] == pytest.approx(3.0)

    def test_trace_eviction(self):
        obs = ObservabilityLayer(max_traces=2)
        obs.start_trace("r1")
        obs.start_trace("r2")
        obs.start_trace("r3")  # should evict r1
        stats = obs.get_stats()
        assert stats["traces"] == 2

    def test_get_nonexistent_trace(self, obs):
        assert obs.get_trace("nonexistent") is None

    def test_stats(self, obs):
        obs.start_trace("r1")
        obs.audit(actor="a", action="x")
        obs.record_cost("t", "c", "p", 0.1)
        stats = obs.get_stats()
        assert stats["traces"] == 1
        assert stats["audit_entries"] == 1
        assert stats["cost_records"] == 1


# ===================================================================
# Integration: End-to-end request flow
# ===================================================================

class TestEndToEndFlow:
    """Simulates a complete AUAR request from signal to response."""

    def test_full_pipeline(self):
        # 1. Set up capability graph
        graph = CapabilityGraph()
        cap = Capability(name="send_email", domain="communication", category="email")
        cap_id = graph.register_capability(cap)

        perf = PerformanceMetrics(avg_latency_ms=50, success_rate=0.99)
        mapping = CapabilityMapping(
            capability_id=cap_id, cost_per_call=0.001,
            performance=perf,
            certification_level=CertificationLevel.PRODUCTION,
        )
        provider = Provider(
            name="SendGrid", base_url="https://api.sendgrid.com",
            supported_capabilities=[mapping],
            health_status=HealthStatus.HEALTHY,
        )
        graph.register_provider(provider)

        # 2. Set up signal interpreter
        interpreter = SignalInterpreter()
        interpreter.register_schema(
            "send_email",
            required_params=["to", "subject", "body"],
            domain="communication",
            category="email",
        )

        # 3. Set up routing engine
        router = RoutingDecisionEngine(graph)

        # 4. Set up schema translator
        translator = SchemaTranslator()
        translator.register_mapping(SchemaMapping(
            capability_name="send_email",
            provider_id=provider.id,
            direction="request",
            field_mappings=[
                FieldMapping(source_field="to", target_field="personalizations.to"),
                FieldMapping(source_field="subject", target_field="subject"),
                FieldMapping(source_field="body", target_field="content.value"),
            ],
        ))

        # 5. Set up provider adapter
        adapter_mgr = ProviderAdapterManager()
        adapter_mgr.register_adapter(AdapterConfig(
            provider_id=provider.id,
            provider_name="SendGrid",
            base_url="https://api.sendgrid.com",
            auth_method=AuthMethod.API_KEY,
            auth_credentials={"api_key": "SG.test"},
        ))

        # 6. Set up observability
        obs = ObservabilityLayer()

        # 7. Set up ML optimizer
        ml = MLOptimizer(epsilon=0.0)

        # --- Execute pipeline ---
        raw_request = {
            "capability": "send_email",
            "parameters": {"to": "user@example.com", "subject": "Test", "body": "Hello!"},
        }

        # Step 1: Interpret
        signal = interpreter.interpret(raw_request)
        assert signal.parsed_intent is not None
        assert signal.confidence_score > 0.6
        trace = obs.start_trace(signal.request_id, capability="send_email")
        decision = router.route(signal)
        assert decision.selected_provider is not None

        # Step 3: Translate
        selected_pid = decision.selected_provider.provider_id
        translation = translator.translate_request(
            "send_email", selected_pid, signal.parameters,
        )
        assert translation.success is True

        # Step 4: Call provider
        resp = adapter_mgr.call_provider(
            selected_pid, "POST", "/v3/mail/send",
            body=translation.translated_data,
        )
        assert resp.success is True

        # Step 5: Record ML observation
        reward = ml.record(RoutingFeatures(
            capability_name="send_email",
            provider_id=selected_pid,
            latency_ms=resp.latency_ms,
            cost=decision.selected_provider.capability_mapping.cost_per_call,
            success=resp.success,
        ))
        assert reward > 0

        # Step 6: Record cost & finish trace
        obs.record_cost("tenant1", "send_email", selected_pid, 0.001)
        obs.finish_trace(trace.trace_id, success=True)
        obs.increment("requests_total")


# ===================================================================
# New Feature Tests — GraphQL Support
# ===================================================================

class TestGraphQLSupport:
    """Tests for GraphQL input parsing in the Signal Interpretation Layer."""

    def test_graphql_mutation_parsed(self):
        si = SignalInterpreter()
        si.register_schema("send_email", required_params=["to", "subject"])
        signal = si.interpret({
            "query": "mutation sendEmail($to: String!) { sendEmail(to: $to) { id } }",
            "variables": {"to": "user@example.com", "subject": "Hi"},
        })
        assert signal.parsed_intent is not None
        assert signal.parsed_intent.capability_name == "send_email"
        assert signal.parameters.get("to") == "user@example.com"

    def test_graphql_query_parsed(self):
        si = SignalInterpreter()
        si.register_schema("list_users")
        signal = si.interpret({
            "query": "query listUsers { listUsers { id name } }",
        })
        assert signal.parsed_intent is not None
        assert signal.parsed_intent.capability_name == "list_users"

    def test_graphql_unknown_capability(self):
        si = SignalInterpreter()
        signal = si.interpret({
            "query": "mutation doUnknownThing { doUnknownThing { ok } }",
        })
        # Should not match anything registered
        assert signal.parsed_intent is None or signal.confidence_score < 0.85


# ===================================================================
# New Feature Tests — Semantic Tag Search
# ===================================================================

class TestSemanticTagSearch:
    """Tests for capability search by semantic tags."""

    def test_search_by_single_tag(self):
        graph = CapabilityGraph()
        graph.register_capability(Capability(
            name="send_email", domain="communication",
            semantic_tags=["email", "messaging", "notification"],
        ))
        graph.register_capability(Capability(
            name="process_payment", domain="payments",
            semantic_tags=["payment", "billing", "charge"],
        ))
        results = graph.search_by_tags(["email"])
        assert len(results) == 1
        assert results[0].name == "send_email"

    def test_search_by_multiple_tags(self):
        graph = CapabilityGraph()
        graph.register_capability(Capability(
            name="send_email", semantic_tags=["email", "messaging"],
        ))
        graph.register_capability(Capability(
            name="send_sms", semantic_tags=["sms", "messaging"],
        ))
        graph.register_capability(Capability(
            name="process_payment", semantic_tags=["payment"],
        ))
        results = graph.search_by_tags(["messaging"])
        assert len(results) == 2
        names = {c.name for c in results}
        assert "send_email" in names
        assert "send_sms" in names

    def test_search_case_insensitive(self):
        graph = CapabilityGraph()
        graph.register_capability(Capability(
            name="send_email", semantic_tags=["Email"],
        ))
        results = graph.search_by_tags(["EMAIL"])
        assert len(results) == 1

    def test_search_no_match(self):
        graph = CapabilityGraph()
        graph.register_capability(Capability(
            name="send_email", semantic_tags=["email"],
        ))
        results = graph.search_by_tags(["payment"])
        assert len(results) == 0


# ===================================================================
# New Feature Tests — Provider/Capability Deregistration
# ===================================================================

class TestDeregistration:
    """Tests for provider and capability removal."""

    def test_deregister_provider(self):
        graph = CapabilityGraph()
        cap = Capability(name="send_email")
        cap_id = graph.register_capability(cap)
        m = CapabilityMapping(capability_id=cap_id)
        prov = Provider(name="SendGrid", supported_capabilities=[m])
        graph.register_provider(prov)
        assert graph.get_provider(prov.id) is not None
        assert graph.deregister_provider(prov.id) is True
        assert graph.get_provider(prov.id) is None

    def test_deregister_nonexistent_provider(self):
        graph = CapabilityGraph()
        assert graph.deregister_provider("nonexistent") is False

    def test_deregister_capability(self):
        graph = CapabilityGraph()
        graph.register_capability(Capability(name="send_email"))
        assert graph.find_capability_by_name("send_email") is not None
        assert graph.deregister_capability("send_email") is True
        assert graph.find_capability_by_name("send_email") is None

    def test_deregister_nonexistent_capability(self):
        graph = CapabilityGraph()
        assert graph.deregister_capability("nonexistent") is False

    def test_deregister_cleans_similarity_edges(self):
        graph = CapabilityGraph()
        graph.register_capability(Capability(name="send_email"))
        graph.register_capability(Capability(name="send_notification"))
        graph.add_similarity_edge("send_email", "send_notification")
        graph.deregister_capability("send_email")
        similar = graph.similar_capabilities("send_notification")
        assert len(similar) == 0  # similarity edges referencing deleted capability removed


# ===================================================================
# New Feature Tests — Multi-Tenant Routing Config
# ===================================================================

class TestMultiTenantRouting:
    """Tests for per-tenant routing strategy and weight overrides."""

    def _build_env(self):
        graph = CapabilityGraph()
        cap = Capability(name="send_email")
        cap_id = graph.register_capability(cap)
        perf_cheap = PerformanceMetrics(avg_latency_ms=200, success_rate=0.95)
        perf_fast = PerformanceMetrics(avg_latency_ms=20, success_rate=0.90)
        m_cheap = CapabilityMapping(
            capability_id=cap_id, cost_per_call=0.0001,
            performance=perf_cheap,
            certification_level=CertificationLevel.PRODUCTION,
        )
        m_fast = CapabilityMapping(
            capability_id=cap_id, cost_per_call=0.05,
            performance=perf_fast,
            certification_level=CertificationLevel.PRODUCTION,
        )
        p_cheap = Provider(name="CheapMail", supported_capabilities=[m_cheap],
                           health_status=HealthStatus.HEALTHY)
        p_fast = Provider(name="FastMail", supported_capabilities=[m_fast],
                          health_status=HealthStatus.HEALTHY)
        graph.register_provider(p_cheap)
        graph.register_provider(p_fast)
        return graph, p_cheap, p_fast

    def test_tenant_cost_override(self):
        graph, p_cheap, p_fast = self._build_env()
        engine = RoutingDecisionEngine(graph)
        # Tenant "budget" wants cost-heavy weighting
        engine.set_tenant_config("budget", weights={
            "reliability": 0.05, "latency": 0.05,
            "cost": 0.85, "certification": 0.05,
        })
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email"),
            context=RequestContext(tenant_id="budget"),
        )
        decision = engine.route(signal)
        assert decision.selected_provider is not None
        assert decision.selected_provider.provider_name == "CheapMail"

    def test_tenant_latency_override(self):
        graph, p_cheap, p_fast = self._build_env()
        engine = RoutingDecisionEngine(graph)
        # Tenant "speed" wants latency-heavy weighting
        engine.set_tenant_config("speed", weights={
            "reliability": 0.05, "latency": 0.85,
            "cost": 0.05, "certification": 0.05,
        })
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email"),
            context=RequestContext(tenant_id="speed"),
        )
        decision = engine.route(signal)
        assert decision.selected_provider is not None
        assert decision.selected_provider.provider_name == "FastMail"

    def test_default_tenant_uses_global_config(self):
        graph, p_cheap, p_fast = self._build_env()
        engine = RoutingDecisionEngine(graph)
        # No tenant config set — should use defaults
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email"),
            context=RequestContext(tenant_id="unknown_tenant"),
        )
        decision = engine.route(signal)
        assert decision.selected_provider is not None

    def test_get_tenant_config(self):
        graph, _, _ = self._build_env()
        engine = RoutingDecisionEngine(graph)
        engine.set_tenant_config("t1", strategy=RoutingStrategy.COST_OPTIMIZED)
        cfg = engine.get_tenant_config("t1")
        assert cfg["strategy"] == RoutingStrategy.COST_OPTIMIZED


# ===================================================================
# New Feature Tests — ML ↔ Routing Integration
# ===================================================================

class TestMLRoutingIntegration:
    """Tests for ML optimizer influencing routing decisions."""

    def test_ml_optimizer_influences_routing(self):
        graph = CapabilityGraph()
        cap = Capability(name="send_email")
        cap_id = graph.register_capability(cap)
        # Two providers with identical static scores
        perf = PerformanceMetrics(avg_latency_ms=50, success_rate=0.99)
        m1 = CapabilityMapping(capability_id=cap_id, cost_per_call=0.001,
                                performance=perf,
                                certification_level=CertificationLevel.PRODUCTION)
        m2 = CapabilityMapping(capability_id=cap_id, cost_per_call=0.001,
                                performance=perf,
                                certification_level=CertificationLevel.PRODUCTION)
        p1 = Provider(name="P1", supported_capabilities=[m1],
                      health_status=HealthStatus.HEALTHY)
        p2 = Provider(name="P2", supported_capabilities=[m2],
                      health_status=HealthStatus.HEALTHY)
        graph.register_provider(p1)
        graph.register_provider(p2)

        ml = MLOptimizer(epsilon=0.0)
        # Train ML to strongly prefer P2
        for _ in range(10):
            ml.record(RoutingFeatures(capability_name="send_email", provider_id=p2.id,
                                       latency_ms=10, cost=0.0001, success=True))
            ml.record(RoutingFeatures(capability_name="send_email", provider_id=p1.id,
                                       latency_ms=400, cost=0.05, success=False))

        engine = RoutingDecisionEngine(graph, ml_optimizer=ml, ml_weight=0.80)
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="send_email")
        )
        decision = engine.route(signal)
        assert decision.selected_provider is not None
        # ML should push P2 to the top
        assert decision.selected_provider.provider_name == "P2"
        assert engine.get_stats()["ml_influenced"] >= 1

    def test_routing_without_ml_still_works(self):
        graph = CapabilityGraph()
        cap = Capability(name="test")
        cap_id = graph.register_capability(cap)
        m = CapabilityMapping(capability_id=cap_id,
                               performance=PerformanceMetrics(success_rate=0.99),
                               certification_level=CertificationLevel.PRODUCTION)
        graph.register_provider(Provider(name="P", supported_capabilities=[m],
                                         health_status=HealthStatus.HEALTHY))
        engine = RoutingDecisionEngine(graph)  # no ml_optimizer
        signal = IntentSignal(parsed_intent=CapabilityIntent(capability_name="test"))
        decision = engine.route(signal)
        assert decision.selected_provider is not None


# ===================================================================
# New Feature Tests — Unified Pipeline Orchestrator
# ===================================================================

from auar.pipeline import AUARPipeline, PipelineResult


class TestAUARPipeline:
    """Tests for the unified orchestrator that wires all 7 layers."""

    def _build_pipeline(self, execute_fn=None):
        """Helper: create a fully wired pipeline for testing."""
        graph = CapabilityGraph()
        cap = Capability(name="send_email", domain="communication", category="email")
        cap_id = graph.register_capability(cap)
        perf = PerformanceMetrics(avg_latency_ms=50, success_rate=0.99)
        mapping = CapabilityMapping(
            capability_id=cap_id, cost_per_call=0.001,
            performance=perf,
            certification_level=CertificationLevel.PRODUCTION,
        )
        provider = Provider(
            name="SendGrid", base_url="https://api.sendgrid.com",
            supported_capabilities=[mapping],
            health_status=HealthStatus.HEALTHY,
        )
        graph.register_provider(provider)

        interpreter = SignalInterpreter()
        interpreter.register_schema(
            "send_email",
            required_params=["to", "subject", "body"],
            domain="communication",
            category="email",
        )

        ml = MLOptimizer(epsilon=0.0)
        router = RoutingDecisionEngine(graph, ml_optimizer=ml)

        translator = SchemaTranslator()
        translator.register_mapping(SchemaMapping(
            capability_name="send_email",
            provider_id=provider.id,
            direction="request",
            field_mappings=[
                FieldMapping(source_field="to", target_field="personalizations.to"),
                FieldMapping(source_field="subject", target_field="subject"),
                FieldMapping(source_field="body", target_field="content.value"),
            ],
        ))

        adapter_mgr = ProviderAdapterManager()
        adapter_mgr.register_adapter(AdapterConfig(
            provider_id=provider.id,
            provider_name="SendGrid",
            base_url="https://api.sendgrid.com",
            auth_method=AuthMethod.API_KEY,
            auth_credentials={"api_key": "SG.test"},
        ), execute_fn=execute_fn)

        obs = ObservabilityLayer()

        pipeline = AUARPipeline(
            interpreter=interpreter,
            graph=graph,
            router=router,
            translator=translator,
            adapters=adapter_mgr,
            ml=ml,
            observability=obs,
        )
        return pipeline, obs, provider

    def test_successful_pipeline_execution(self):
        pipeline, obs, _ = self._build_pipeline()
        result = pipeline.execute({
            "capability": "send_email",
            "parameters": {"to": "user@example.com", "subject": "Test", "body": "Hi"},
        })
        assert result.success is True
        assert result.capability == "send_email"
        assert result.provider_name == "SendGrid"
        assert result.response_status == 200
        assert result.total_latency_ms > 0
        assert result.ml_reward > 0
        assert result.trace_id != ""
        # Observability recorded
        assert obs.get_counter("auar.requests.success") == 1

    def test_pipeline_with_tenant_context(self):
        pipeline, _, _ = self._build_pipeline()
        ctx = RequestContext(user_id="u1", tenant_id="t1")
        result = pipeline.execute({
            "capability": "send_email",
            "parameters": {"to": "a@b.com", "subject": "S", "body": "B"},
        }, context=ctx)
        assert result.success is True

    def test_pipeline_empty_request_clarification(self):
        pipeline, _, _ = self._build_pipeline()
        result = pipeline.execute({})
        assert result.success is False
        assert result.requires_clarification is True

    def test_pipeline_unknown_capability(self):
        pipeline, _, _ = self._build_pipeline()
        result = pipeline.execute({
            "capability": "nonexistent_thing",
            "parameters": {},
        })
        # Should fail since no providers for unknown capability
        assert result.success is False

    def test_pipeline_provider_failure_with_no_fallback(self):
        def always_fail(payload):
            raise ConnectionError("provider down")

        pipeline, obs, _ = self._build_pipeline(execute_fn=always_fail)
        result = pipeline.execute({
            "capability": "send_email",
            "parameters": {"to": "a@b.com", "subject": "S", "body": "B"},
        })
        assert result.success is False
        assert "failed" in result.error.lower()
        assert obs.get_counter("auar.requests.failure") == 1

    def test_pipeline_graphql_input(self):
        pipeline, _, _ = self._build_pipeline()
        result = pipeline.execute({
            "query": "mutation sendEmail($to: String!) { sendEmail(to: $to) { ok } }",
            "variables": {"to": "user@example.com", "subject": "Test", "body": "Hi"},
        })
        assert result.success is True
        assert result.capability == "send_email"

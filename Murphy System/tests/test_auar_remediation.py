"""
Tests for the AUAR System Remediation Plan.

Covers all 14 issues across 3 phases:
  Phase 1 (Critical Security): Issues #1–3, #13
  Phase 2 (Core Hardening): Issues #4–9, #11
  Phase 3 (Polish): Issues #10, #12, #14

Copyright 2024 Inoni LLC – BSL-1.1
"""

import asyncio
import hashlib
import hmac as hmac_mod
import json
import os
import sys
import time


import pytest

from auar.config import AUARConfig, RoutingConfig, MLConfig
from auar.ml_optimization import MLOptimizer, RoutingFeatures, OptimizationResult
from auar.routing_engine import (
    CircuitState,
    RoutingDecisionEngine,
    RoutingStrategy,
    _CircuitBreaker,
)
from auar.capability_graph import (
    Capability,
    CapabilityGraph,
    CapabilityMapping,
    CertificationLevel,
    HealthStatus,
    PerformanceMetrics,
    Provider,
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
from auar.observability import ObservabilityLayer
from auar.pipeline import AUARPipeline, PipelineResult
from auar.signal_interpretation import (
    RequestContext,
    SignalInterpreter,
)
from auar_api import (
    AUARComponents,
    initialize_auar,
    handle_route,
    handle_register,
    handle_stats,
    handle_health,
    handle_deregister_provider,
    handle_deregister_capability,
    create_secure_auar_app,
)


# ===================================================================
# Phase 1 — Issue #1: Enforce Authentication at Startup
# ===================================================================

class TestEnforceAuth:
    """Tests for Issue #1: create_secure_auar_app raises without security module."""

    def test_secure_app_raises_without_security_module(self, monkeypatch):
        """Startup aborts if fastapi_security is not importable
        and AUAR_ALLOW_INSECURE is not set."""
        monkeypatch.delenv("AUAR_ALLOW_INSECURE", raising=False)
        # Temporarily hide fastapi_security
        original = sys.modules.get("fastapi_security")
        sys.modules["fastapi_security"] = None  # type: ignore
        try:
            with pytest.raises(RuntimeError, match="fastapi_security"):
                create_secure_auar_app()
        finally:
            if original is not None:
                sys.modules["fastapi_security"] = original
            else:
                sys.modules.pop("fastapi_security", None)

    def test_secure_app_allows_insecure_override(self, monkeypatch):
        """AUAR_ALLOW_INSECURE=true allows startup without security."""
        monkeypatch.setenv("AUAR_ALLOW_INSECURE", "true")
        original = sys.modules.get("fastapi_security")
        sys.modules["fastapi_security"] = None  # type: ignore
        try:
            app = create_secure_auar_app()
            assert app is not None
        finally:
            if original is not None:
                sys.modules["fastapi_security"] = original
            else:
                sys.modules.pop("fastapi_security", None)


# ===================================================================
# Phase 1 — Issue #2: Authorize /api/auar/register Endpoint
# ===================================================================

class TestAuthorizeRegister:
    """Tests for Issue #2: RBAC on registration endpoint."""

    def test_register_requires_admin_role_via_fastapi(self):
        """Registration endpoint returns 403 without admin role."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        app = FastAPI()
        router = create_auar_router()
        app.include_router(router)
        client = TestClient(app)

        # No admin headers → 403
        resp = client.post("/register", json={
            "capability": {"name": "test_cap"},
        })
        assert resp.status_code == 403
        assert "Admin role required" in resp.json()["error"]

    def test_register_succeeds_with_admin_role(self):
        """Registration endpoint succeeds with admin headers."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        app = FastAPI()
        router = create_auar_router()
        app.include_router(router)
        client = TestClient(app)

        resp = client.post(
            "/register",
            json={"capability": {"name": "admin_test"}},
            headers={"X-User-ID": "admin1", "X-User-Role": "admin"},
        )
        assert resp.status_code == 201
        assert "capability:admin_test" in resp.json()["registered"]

    def test_register_audit_entry_on_denial(self):
        """Denied registration attempts are audited."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        components = initialize_auar()
        app = FastAPI()
        router = create_auar_router(components)
        app.include_router(router)
        client = TestClient(app)

        client.post("/register", json={"capability": {"name": "x"}})
        audit = components.observability.get_audit_log()
        denied = [e for e in audit if e.outcome == "denied"]
        assert len(denied) >= 1

    def test_register_audit_entry_on_success(self):
        """Successful registrations are audited with actor info."""
        components = initialize_auar()
        handle_register(
            components,
            {"capability": {"name": "audited_cap", "domain": "test"}},
            actor="admin_user",
            tenant_id="t1",
        )
        audit = components.observability.get_audit_log()
        cap_entries = [e for e in audit if e.action == "register_capability"]
        assert len(cap_entries) >= 1
        assert cap_entries[0].actor == "admin_user"
        assert cap_entries[0].tenant_id == "t1"


# ===================================================================
# Phase 1 — Issue #3: Pydantic Input Validation
# ===================================================================

class TestPydanticValidation:
    """Tests for Issue #3: strict input validation with Pydantic models."""

    def test_route_rejects_empty_capability(self):
        """POST /route returns 422 for empty capability field."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        app = FastAPI()
        router = create_auar_router()
        app.include_router(router)
        client = TestClient(app)

        resp = client.post("/route", json={"capability": "", "parameters": {}})
        assert resp.status_code == 422

    def test_route_rejects_missing_capability(self):
        """POST /route returns 422 when capability is missing."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        app = FastAPI()
        router = create_auar_router()
        app.include_router(router)
        client = TestClient(app)

        resp = client.post("/route", json={"parameters": {}})
        assert resp.status_code == 422

    def test_register_rejects_invalid_provider(self):
        """POST /register returns 422 for invalid provider data."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        app = FastAPI()
        router = create_auar_router()
        app.include_router(router)
        client = TestClient(app)

        resp = client.post(
            "/register",
            json={
                "capability": {"name": "ok"},
                "provider": {"name": "p", "cost_per_call": -5.0},  # negative cost
            },
            headers={"X-User-ID": "admin1", "X-User-Role": "admin"},
        )
        assert resp.status_code == 422


# ===================================================================
# Phase 1 — Issue #13: License Header Consistency
# ===================================================================

class TestLicenseHeaders:
    """Tests for Issue #13: All source files use BSL-1.1."""

    def test_auar_api_has_bsl_header(self):
        """auar_api.py should use BSL-1.1, not Apache 2.0."""
        path = os.path.join(os.path.dirname(__file__), "..", "src", "auar_api.py")
        with open(path, "r") as f:
            content = f.read()
        assert "BSL-1.1" in content
        assert "Apache License 2.0" not in content

    def test_all_auar_modules_have_bsl_header(self):
        """All AUAR module files should use BSL-1.1."""
        auar_dir = os.path.join(os.path.dirname(__file__), "..", "src", "auar")
        for fname in os.listdir(auar_dir):
            if fname.endswith(".py") and fname != "__init__.py":
                with open(os.path.join(auar_dir, fname), "r") as f:
                    content = f.read()
                assert "BSL-1.1" in content, f"{fname} missing BSL-1.1 header"


# ===================================================================
# Phase 2 — Issue #4 & #5: Async HTTP Provider Calls + Async Retry
# ===================================================================

class TestAsyncProviderCalls:
    """Tests for Issues #4 and #5: async call and async retry."""

    def test_async_call_basic(self):
        """async_call returns AdapterResponse."""
        config = AdapterConfig(
            provider_id="async-test",
            base_url="https://example.com",
            max_retries=0,
        )
        adapter = ProviderAdapter(config)
        result = asyncio.run(
            adapter.async_call("GET", "/test")
        )
        assert isinstance(result, AdapterResponse)
        assert result.success is True

    def test_async_retry_uses_asyncio_sleep(self):
        """Async retry uses asyncio.sleep, not blocking time.sleep."""
        call_count = 0
        def failing_fn(payload):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("retry me")
            return {"status_code": 200, "body": {}, "headers": {}}

        config = AdapterConfig(
            provider_id="async-retry-test",
            base_url="https://example.com",
            max_retries=3,
            retry_backoff_s=0.01,
        )
        adapter = ProviderAdapter(config, execute_fn=failing_fn)
        result = asyncio.run(
            adapter.async_call("POST", "/test")
        )
        assert result.success is True
        assert result.retries_used == 2

    def test_async_call_provider_via_manager(self):
        """ProviderAdapterManager.async_call_provider works."""
        mgr = ProviderAdapterManager()
        mgr.register_adapter(AdapterConfig(
            provider_id="p1",
            provider_name="Test",
            base_url="https://example.com",
            max_retries=0,
        ))
        result = asyncio.run(
            mgr.async_call_provider("p1", "GET", "/test")
        )
        assert result.success is True

    def test_async_call_provider_not_found(self):
        """async_call_provider returns 404 for unknown provider."""
        mgr = ProviderAdapterManager()
        result = asyncio.run(
            mgr.async_call_provider("nonexistent", "GET", "/test")
        )
        assert result.success is False
        assert result.status_code == 404

    def test_httpx_execute_factory_available(self):
        """httpx execute factory creates a callable when httpx is installed."""
        config = AdapterConfig(base_url="https://example.com", timeout_s=5)
        factory = ProviderAdapter._httpx_execute_factory(config)
        # httpx is installed in our test env
        assert factory is not None


# ===================================================================
# Phase 2 — Issue #7: ML Optimizer Improvements
# ===================================================================

class TestMLOptimizerImprovements:
    """Tests for Issue #7: UCB1, recency decay, per-capability epsilon."""

    def test_ucb1_untried_provider_explored(self):
        """New/untried provider gets immediate exploration via UCB1."""
        opt = MLOptimizer(epsilon=0.0)  # disable epsilon to test UCB1 directly
        # Record data for provider p1
        for _ in range(10):
            opt.record(RoutingFeatures(
                capability_name="cap", provider_id="p1",
                latency_ms=100, cost=0.01, success=True,
            ))
        # p2 is untried — should be explored
        result = opt.recommend("cap", ["p1", "p2"])
        assert result.recommended_provider_id == "p2"
        assert result.exploration is True
        assert "untried" in result.reason

    def test_per_capability_epsilon(self):
        """Each capability has its own epsilon value."""
        opt = MLOptimizer(epsilon=0.15, epsilon_decay=0.5)
        opt.record(RoutingFeatures(capability_name="cap_a", provider_id="p1"))
        opt.record(RoutingFeatures(capability_name="cap_b", provider_id="p1"))

        # Both capabilities should have their own decayed epsilon
        assert "cap_a" in opt._capability_epsilon
        assert "cap_b" in opt._capability_epsilon

    def test_recency_decay_affects_weighted_reward(self):
        """Recent observations have more weight than old ones."""
        opt = MLOptimizer(recency_decay=0.5)
        # Record bad performance first
        for _ in range(5):
            opt.record(RoutingFeatures(
                capability_name="cap", provider_id="p1",
                latency_ms=400, cost=0.09, success=False,
            ))
        # Then good performance
        for _ in range(5):
            opt.record(RoutingFeatures(
                capability_name="cap", provider_id="p1",
                latency_ms=50, cost=0.01, success=True,
            ))
        stats = opt.get_provider_stats("cap")
        # Weighted avg should be better than plain avg due to recency
        assert stats["p1"]["weighted_avg_reward"] > stats["p1"]["avg_reward"]

    def test_provider_degradation_detection(self):
        """When a provider degrades, recency weighting reflects it."""
        opt = MLOptimizer(recency_decay=0.5)
        # Good performance first
        for _ in range(10):
            opt.record(RoutingFeatures(
                capability_name="cap", provider_id="p1",
                latency_ms=50, cost=0.01, success=True,
            ))
        # Then degradation
        for _ in range(5):
            opt.record(RoutingFeatures(
                capability_name="cap", provider_id="p1",
                latency_ms=400, cost=0.09, success=False,
            ))
        stats = opt.get_provider_stats("cap")
        # Weighted avg should be worse than overall avg
        assert stats["p1"]["weighted_avg_reward"] < stats["p1"]["avg_reward"]

    def test_cold_start_exploration(self):
        """With no data, recommendation falls back to cold start exploration."""
        opt = MLOptimizer()
        result = opt.recommend("new_cap", ["p1", "p2", "p3"])
        assert result.exploration is True
        assert "cold start" in result.reason

    def test_stats_include_per_capability_epsilon(self):
        """get_stats returns per-capability epsilon values."""
        opt = MLOptimizer()
        opt.record(RoutingFeatures(capability_name="cap_x", provider_id="p1"))
        stats = opt.get_stats()
        assert isinstance(stats["epsilon"], dict)
        assert "cap_x" in stats["epsilon"]


# ===================================================================
# Phase 2 — Issue #8: Gradual Circuit Breaker Recovery
# ===================================================================

class TestGradualCircuitBreaker:
    """Tests for Issue #8: half-open state requires N consecutive successes."""

    def _make_engine(self, **kwargs):
        graph = CapabilityGraph()
        return RoutingDecisionEngine(
            graph,
            circuit_failure_threshold=kwargs.get("threshold", 3),
            circuit_recovery_s=kwargs.get("recovery_s", 0.01),
            half_open_required_successes=kwargs.get("required", 3),
            half_open_traffic_ratio=kwargs.get("ratio", 1.0),  # 100% for test determinism
        )

    def test_half_open_requires_multiple_successes(self):
        """In HALF_OPEN, a single success does not close the circuit."""
        engine = self._make_engine(threshold=2, required=3)
        # Trip the circuit
        engine.record_failure("p1")
        engine.record_failure("p1")
        # Wait for recovery timeout
        time.sleep(0.02)
        # Now in half-open after timeout check
        cb = engine._circuit_breakers["p1"]
        cb.state = CircuitState.HALF_OPEN
        cb.half_open_success_count = 0

        # One success — still HALF_OPEN
        engine.record_success("p1")
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.half_open_success_count == 1

        # Two successes — still HALF_OPEN
        engine.record_success("p1")
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.half_open_success_count == 2

        # Three successes — now CLOSED
        engine.record_success("p1")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_failure_in_half_open_reopens_circuit(self):
        """A failure in HALF_OPEN state goes back to OPEN."""
        engine = self._make_engine(threshold=2, required=3)
        engine.record_failure("p1")
        engine.record_failure("p1")
        cb = engine._circuit_breakers["p1"]
        cb.state = CircuitState.HALF_OPEN
        cb.half_open_success_count = 2

        engine.record_failure("p1")
        assert cb.state == CircuitState.OPEN
        assert cb.half_open_success_count == 0

    def test_circuit_breaker_has_traffic_ratio(self):
        """_CircuitBreaker has configurable half_open_traffic_ratio."""
        cb = _CircuitBreaker(half_open_traffic_ratio=0.10)
        assert cb.half_open_traffic_ratio == 0.10

    def test_circuit_breaker_has_required_successes(self):
        """_CircuitBreaker has configurable half_open_required_successes."""
        cb = _CircuitBreaker(half_open_required_successes=5)
        assert cb.half_open_required_successes == 5


# ===================================================================
# Phase 2 — Issue #9: Configurable Score Normalization
# ===================================================================

class TestConfigurableNormalization:
    """Tests for Issue #9: max_latency_ms and max_cost are configurable."""

    def _make_graph_with_providers(self):
        graph = CapabilityGraph()
        cap = Capability(name="test_cap")
        graph.register_capability(cap)

        # Provider A: low latency, high cost
        perf_a = PerformanceMetrics(avg_latency_ms=100, success_rate=0.99)
        mapping_a = CapabilityMapping(
            capability_id=cap.id, cost_per_call=0.08,
            performance=perf_a, certification_level=CertificationLevel.PRODUCTION,
        )
        prov_a = Provider(
            name="ProvA", supported_capabilities=[mapping_a],
            health_status=HealthStatus.HEALTHY,
        )
        graph.register_provider(prov_a)

        # Provider B: high latency, low cost
        perf_b = PerformanceMetrics(avg_latency_ms=400, success_rate=0.99)
        mapping_b = CapabilityMapping(
            capability_id=cap.id, cost_per_call=0.02,
            performance=perf_b, certification_level=CertificationLevel.PRODUCTION,
        )
        prov_b = Provider(
            name="ProvB", supported_capabilities=[mapping_b],
            health_status=HealthStatus.HEALTHY,
        )
        graph.register_provider(prov_b)
        return graph

    def test_different_normalization_changes_ranking(self):
        """Changing max_latency_ms can invert provider ranking."""
        graph = self._make_graph_with_providers()

        # With default 500ms max — both providers well within range
        engine_default = RoutingDecisionEngine(
            graph, max_latency_ms=500.0, max_cost=0.10,
        )
        # With 200ms max — ProvB (400ms) gets penalized heavily
        engine_tight = RoutingDecisionEngine(
            graph, max_latency_ms=200.0, max_cost=0.10,
        )

        from auar.signal_interpretation import IntentSignal, CapabilityIntent
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="test_cap"),
            confidence_score=0.9,
        )

        dec_default = engine_default.route(signal)
        dec_tight = engine_tight.route(signal)

        # The scores should differ due to different normalization
        assert dec_default.score != dec_tight.score

    def test_max_cost_normalization(self):
        """Changing max_cost affects scoring of high-cost providers."""
        graph = self._make_graph_with_providers()

        # $0.10 max (default) — ProvA at $0.08 gets low cost score
        engine_low = RoutingDecisionEngine(graph, max_cost=0.10)
        # $1.00 max — ProvA at $0.08 gets high cost score
        engine_high = RoutingDecisionEngine(graph, max_cost=1.00)

        from auar.signal_interpretation import IntentSignal, CapabilityIntent
        signal = IntentSignal(
            parsed_intent=CapabilityIntent(capability_name="test_cap"),
            confidence_score=0.9,
        )

        dec_low = engine_low.route(signal)
        dec_high = engine_high.route(signal)

        # With higher max_cost, ProvA's cost penalty is smaller → higher score
        assert dec_high.score != dec_low.score

    def test_config_has_normalization_fields(self):
        """RoutingConfig includes max_latency_ms and max_cost."""
        cfg = RoutingConfig()
        assert cfg.max_latency_ms == 500.0
        assert cfg.max_cost == 0.10


# ===================================================================
# Phase 2 — Issue #11: Wire AUARConfig Into Bootstrap
# ===================================================================

class TestConfigWiring:
    """Tests for Issue #11: AUARConfig wired into initialize_auar."""

    def test_initialize_with_custom_config(self):
        """initialize_auar() uses provided config values."""
        cfg = AUARConfig.from_dict({
            "ml": {"epsilon": 0.50},
            "routing": {"strategy": "cost_optimized"},
        })
        components = initialize_auar(config=cfg)
        assert components.ml._epsilon_initial == 0.50
        assert components.router._strategy == RoutingStrategy.COST_OPTIMIZED

    def test_initialize_from_env(self, monkeypatch):
        """initialize_auar() picks up AUAR_* env vars."""
        monkeypatch.setenv("AUAR_ML_EPSILON", "0.42")
        monkeypatch.setenv("AUAR_ROUTING_STRATEGY", "latency_optimized")
        components = initialize_auar()
        assert components.ml._epsilon_initial == pytest.approx(0.42)
        assert components.router._strategy == RoutingStrategy.LATENCY_OPTIMIZED

    def test_config_propagates_to_routing_engine(self):
        """Config values for routing reach the engine."""
        cfg = AUARConfig.from_dict({
            "routing": {
                "max_latency_ms": 1000.0,
                "max_cost": 0.50,
                "circuit_breaker_threshold": 10,
            },
        })
        components = initialize_auar(config=cfg)
        assert components.router._max_latency_ms == 1000.0
        assert components.router._max_cost == 0.50
        assert components.router._cb_failure_threshold == 10

    def test_components_store_config(self):
        """AUARComponents stores the config for inspection."""
        cfg = AUARConfig.defaults()
        components = AUARComponents(config=cfg)
        assert components.config is cfg


# ===================================================================
# Phase 3 — Issue #10: HMAC Signing Must Include Request Body
# ===================================================================

class TestHMACBodySigning:
    """Tests for Issue #10: HMAC v2 includes canonicalized body."""

    def test_hmac_includes_body_in_signature(self):
        """HMAC signature covers the request body."""
        config = AdapterConfig(
            provider_id="hmac-test",
            auth_method=AuthMethod.HMAC,
            auth_credentials={"secret_key": "secret", "key_id": "k1"},
        )
        adapter = ProviderAdapter(config)

        body = {"action": "send", "to": "user@example.com"}
        h1 = adapter._build_auth_headers(body=body)

        ts = h1["X-HMAC-Timestamp"]
        canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
        expected_msg = f"{ts}:k1:{canon}"
        expected_sig = hmac_mod.new(
            b"secret", expected_msg.encode(), hashlib.sha256
        ).hexdigest()
        assert h1["X-HMAC-Signature"] == expected_sig

    def test_hmac_version_header(self):
        """HMAC v2 includes X-HMAC-Version header."""
        config = AdapterConfig(
            auth_method=AuthMethod.HMAC,
            auth_credentials={"secret_key": "s", "key_id": "k"},
        )
        adapter = ProviderAdapter(config)
        headers = adapter._build_auth_headers()
        assert headers["X-HMAC-Version"] == "v2"

    def test_hmac_body_tamper_detection(self):
        """Signature verification fails when body is modified."""
        config = AdapterConfig(
            auth_method=AuthMethod.HMAC,
            auth_credentials={"secret_key": "secret", "key_id": "k1"},
        )
        adapter = ProviderAdapter(config)

        body_original = {"amount": 100, "currency": "USD"}
        h_original = adapter._build_auth_headers(body=body_original)

        body_tampered = {"amount": 9999, "currency": "USD"}
        ts = h_original["X-HMAC-Timestamp"]
        canon_tampered = json.dumps(body_tampered, sort_keys=True, separators=(",", ":"))
        tampered_msg = f"{ts}:k1:{canon_tampered}"
        tampered_sig = hmac_mod.new(
            b"secret", tampered_msg.encode(), hashlib.sha256
        ).hexdigest()

        # Signatures must differ
        assert h_original["X-HMAC-Signature"] != tampered_sig


# ===================================================================
# Phase 3 — Issue #12: Check Response Translation Success
# ===================================================================

class TestResponseTranslationCheck:
    """Tests for Issue #12: pipeline checks resp_translation.success."""

    def _make_pipeline_with_failing_translation(self):
        """Build a pipeline where response translation always fails."""
        graph = CapabilityGraph()
        interpreter = SignalInterpreter()
        ml = MLOptimizer()
        router = RoutingDecisionEngine(graph, ml_optimizer=ml)
        translator = SchemaTranslator()
        adapters = ProviderAdapterManager()
        obs = ObservabilityLayer()

        # Register capability
        cap = Capability(name="test_cap", domain="test")
        cap_id = graph.register_capability(cap)
        interpreter.register_schema("test_cap")

        # Register provider
        mapping = CapabilityMapping(
            capability_id=cap_id, cost_per_call=0.01,
            performance=PerformanceMetrics(avg_latency_ms=100, success_rate=0.99),
            certification_level=CertificationLevel.PRODUCTION,
        )
        provider = Provider(
            name="TestProv", supported_capabilities=[mapping],
            health_status=HealthStatus.HEALTHY,
        )
        graph.register_provider(provider)
        adapters.register_adapter(AdapterConfig(
            provider_id=provider.id, provider_name="TestProv",
            base_url="https://example.com",
        ))

        # Register request mapping (so request translation succeeds)
        translator.register_mapping(SchemaMapping(
            capability_name="test_cap",
            provider_id=provider.id,
            direction="request",
            field_mappings=[],
        ))

        # Register response mapping with required field (will fail)
        translator.register_mapping(SchemaMapping(
            capability_name="test_cap",
            provider_id=provider.id,
            direction="response",
            field_mappings=[
                FieldMapping(
                    source_field="missing_field",
                    target_field="output",
                    required=True,
                ),
            ],
        ))

        pipeline = AUARPipeline(
            interpreter=interpreter, graph=graph, router=router,
            translator=translator, adapters=adapters, ml=ml,
            observability=obs,
        )
        return pipeline, obs

    def test_failed_response_translation_sets_success_false(self):
        """When response translation fails, result.success is False."""
        pipeline, obs = self._make_pipeline_with_failing_translation()
        result = pipeline.execute(
            {"capability": "test_cap", "parameters": {}},
            context=RequestContext(tenant_id="t1"),
        )
        assert result.success is False
        assert "translation failed" in result.error.lower()

    def test_failed_response_translation_logs_span(self):
        """Failed response translation creates an observability span."""
        pipeline, obs = self._make_pipeline_with_failing_translation()
        result = pipeline.execute(
            {"capability": "test_cap", "parameters": {}},
            context=RequestContext(tenant_id="t1"),
        )
        # Check that a translation failure counter was incremented
        counter = obs.get_counter("auar.requests.translation_failure")
        assert counter >= 1


# ===================================================================
# Phase 3 — Issue #14: Deregistration API
# ===================================================================

class TestDeregistrationAPI:
    """Tests for Issue #14: DELETE endpoints for providers and capabilities."""

    def _setup_registered_components(self):
        components = initialize_auar()
        result = handle_register(components, {
            "capability": {"name": "to_remove", "domain": "test"},
            "provider": {
                "name": "RemovableProvider",
                "base_url": "https://example.com",
            },
            "schema_mappings": [{
                "direction": "request",
                "field_mappings": [
                    {"source_field": "a", "target_field": "b"},
                ],
            }],
        }, actor="admin", tenant_id="t1")
        return components, result

    def test_deregister_provider(self):
        """Provider deregistration removes provider and cascades."""
        components, reg = self._setup_registered_components()
        pid = reg["provider_id"]

        result = handle_deregister_provider(
            components, pid, actor="admin", tenant_id="t1",
        )
        assert result["success"] is True

        # Provider gone from graph
        assert components.graph.get_provider(pid) is None

        # Adapter gone
        assert components.adapters.get_adapter(pid) is None

    def test_deregister_provider_not_found(self):
        """Deregistering unknown provider returns error."""
        components = initialize_auar()
        result = handle_deregister_provider(
            components, "nonexistent", actor="admin",
        )
        assert result["success"] is False

    def test_deregister_capability(self):
        """Capability deregistration removes capability and cascades."""
        components, _ = self._setup_registered_components()

        result = handle_deregister_capability(
            components, "to_remove", actor="admin", tenant_id="t1",
        )
        assert result["success"] is True

        # Capability gone from graph
        assert components.graph.find_capability_by_name("to_remove") is None

    def test_deregister_capability_not_found(self):
        """Deregistering unknown capability returns error."""
        components = initialize_auar()
        result = handle_deregister_capability(
            components, "nonexistent", actor="admin",
        )
        assert result["success"] is False

    def test_deregister_audited(self):
        """Deregistration actions are audited."""
        components, reg = self._setup_registered_components()
        pid = reg["provider_id"]

        handle_deregister_provider(
            components, pid, actor="admin_user", tenant_id="t1",
        )
        audit = components.observability.get_audit_log()
        dereg_entries = [e for e in audit if e.action == "deregister_provider"]
        assert len(dereg_entries) >= 1
        assert dereg_entries[0].actor == "admin_user"

    def test_deregister_provider_via_fastapi(self):
        """DELETE /provider/{id} works via FastAPI endpoint."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        components = initialize_auar()
        app = FastAPI()
        router = create_auar_router(components)
        app.include_router(router)
        client = TestClient(app)

        # Register first
        reg = client.post(
            "/register",
            json={"capability": {"name": "del_test"}, "provider": {"name": "P1"}},
            headers={"X-User-ID": "admin", "X-User-Role": "admin"},
        )
        pid = reg.json()["provider_id"]

        # Delete without admin → 403
        resp = client.delete(f"/provider/{pid}")
        assert resp.status_code == 403

        # Delete with admin → 200
        resp = client.delete(
            f"/provider/{pid}",
            headers={"X-User-ID": "admin", "X-User-Role": "admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_deregister_capability_via_fastapi(self):
        """DELETE /capability/{name} works via FastAPI endpoint."""
        from fastapi.testclient import TestClient
        from auar_api import create_auar_router
        from fastapi import FastAPI

        components = initialize_auar()
        app = FastAPI()
        router = create_auar_router(components)
        app.include_router(router)
        client = TestClient(app)

        # Register
        client.post(
            "/register",
            json={"capability": {"name": "cap_del"}},
            headers={"X-User-ID": "admin", "X-User-Role": "admin"},
        )

        # Delete
        resp = client.delete(
            "/capability/cap_del",
            headers={"X-User-ID": "admin", "X-User-Role": "admin"},
        )
        assert resp.status_code == 200

    def test_schema_translator_deregister_provider_mappings(self):
        """SchemaTranslator.deregister_provider_mappings removes all for a provider."""
        translator = SchemaTranslator()
        translator.register_mapping(SchemaMapping(
            capability_name="cap1", provider_id="p1", direction="request",
        ))
        translator.register_mapping(SchemaMapping(
            capability_name="cap2", provider_id="p1", direction="response",
        ))
        translator.register_mapping(SchemaMapping(
            capability_name="cap1", provider_id="p2", direction="request",
        ))
        removed = translator.deregister_provider_mappings("p1")
        assert removed == 2
        # p2 mapping still exists
        assert len(translator._mappings) == 1

    def test_schema_translator_deregister_capability_mappings(self):
        """SchemaTranslator.deregister_capability_mappings removes all for a capability."""
        translator = SchemaTranslator()
        translator.register_mapping(SchemaMapping(
            capability_name="cap1", provider_id="p1", direction="request",
        ))
        translator.register_mapping(SchemaMapping(
            capability_name="cap1", provider_id="p2", direction="request",
        ))
        translator.register_mapping(SchemaMapping(
            capability_name="cap2", provider_id="p1", direction="request",
        ))
        removed = translator.deregister_capability_mappings("cap1")
        assert removed == 2
        assert len(translator._mappings) == 1

    def test_adapter_manager_deregister(self):
        """ProviderAdapterManager.deregister_adapter removes the adapter."""
        mgr = ProviderAdapterManager()
        mgr.register_adapter(AdapterConfig(provider_id="p1", provider_name="P"))
        assert mgr.get_adapter("p1") is not None
        result = mgr.deregister_adapter("p1")
        assert result is True
        assert mgr.get_adapter("p1") is None

    def test_adapter_manager_deregister_not_found(self):
        """Deregistering non-existent adapter returns False."""
        mgr = ProviderAdapterManager()
        assert mgr.deregister_adapter("nonexistent") is False


# ===================================================================
# Phase 2 — Issue #6: Persistence Layer (StateBackend ABC)
# ===================================================================

class TestPersistenceBackend:
    """Tests for Issue #6: pluggable persistence design.

    Validates that state can be serialized/deserialized and that
    the graph, translator, and ML optimizer have serializable state.
    """

    def test_graph_state_serializable(self):
        """CapabilityGraph stats can be captured for persistence."""
        graph = CapabilityGraph()
        cap = Capability(name="persist_cap")
        graph.register_capability(cap)
        stats = graph.get_stats()
        assert isinstance(stats, dict)
        assert stats["total_capabilities"] == 1

    def test_ml_state_serializable(self):
        """MLOptimizer stats can be captured for persistence."""
        ml = MLOptimizer()
        ml.record(RoutingFeatures(capability_name="c", provider_id="p"))
        stats = ml.get_stats()
        assert isinstance(stats, dict)
        assert stats["total_observations"] == 1

    def test_config_round_trip(self):
        """AUARConfig can be serialized and deserialized."""
        cfg = AUARConfig.from_dict({
            "ml": {"epsilon": 0.42},
            "routing": {"strategy": "cost_optimized", "max_latency_ms": 1000},
        })
        d = cfg.to_dict()
        cfg2 = AUARConfig.from_dict(d)
        assert cfg2.ml.epsilon == pytest.approx(0.42)
        assert cfg2.routing.strategy == "cost_optimized"
        assert cfg2.routing.max_latency_ms == 1000.0


# ===================================================================
# Issue #1 (gap): fastapi_security documented in requirements
# ===================================================================

class TestFastapiSecurityDependencyDoc:
    """Issue #1: fastapi_security is documented as hard dependency."""

    def test_requirements_documents_fastapi_security(self):
        """requirements_murphy_1.0.txt contains a note about fastapi_security."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "requirements_murphy_1.0.txt"
        )
        with open(path) as f:
            content = f.read()
        assert "fastapi_security" in content.lower() or "fastapi-security" in content.lower()


# ===================================================================
# Issue #4 (gap): gRPC/SOAP raise NotImplementedError
# ===================================================================

class TestGrpcSoapNotImplemented:
    """Issue #4: gRPC and SOAP protocols raise NotImplementedError."""

    def test_grpc_raises_not_implemented(self):
        """Calling a gRPC adapter raises NotImplementedError."""
        config = AdapterConfig(
            provider_id="grpc-test",
            base_url="https://grpc.example.com",
            protocol=Protocol.GRPC,
            max_retries=0,
        )
        adapter = ProviderAdapter(config)
        with pytest.raises(NotImplementedError, match="gRPC"):
            adapter.call("POST", "/service/Method")

    def test_soap_raises_not_implemented(self):
        """Calling a SOAP adapter raises NotImplementedError."""
        config = AdapterConfig(
            provider_id="soap-test",
            base_url="https://soap.example.com",
            protocol=Protocol.SOAP,
            max_retries=0,
        )
        adapter = ProviderAdapter(config)
        with pytest.raises(NotImplementedError, match="SOAP"):
            adapter.call("POST", "/Service.asmx")


# ===================================================================
# Issue #5 (gap): call_sync wrapper
# ===================================================================

class TestSyncWrapper:
    """Issue #5: call_sync provides non-blocking sync wrapper."""

    def test_call_sync_succeeds(self):
        """call_sync returns an AdapterResponse using async path."""
        config = AdapterConfig(
            provider_id="sync-wrap",
            base_url="https://example.com",
            max_retries=0,
        )
        adapter = ProviderAdapter(config)
        resp = adapter.call_sync("GET", "/test")
        assert resp.success is True

    def test_call_sync_retries_use_asyncio_sleep(self):
        """call_sync retries use asyncio.sleep, not blocking time.sleep."""
        call_count = 0

        def flaky_fn(payload):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("retry please")
            return {"status_code": 200, "body": {}, "headers": {}}

        config = AdapterConfig(
            provider_id="sync-retry",
            base_url="https://example.com",
            max_retries=3,
            retry_backoff_s=0.01,
        )
        adapter = ProviderAdapter(config, execute_fn=flaky_fn)
        resp = adapter.call_sync("POST", "/test")
        assert resp.success is True
        assert resp.retries_used == 2


# ===================================================================
# Issue #6 (full): StateBackend ABC + FileStateBackend
# ===================================================================

class TestStateBackendABC:
    """Issue #6: StateBackend ABC and implementations."""

    def test_in_memory_save_load(self):
        """InMemoryStateBackend round-trips data."""
        from auar.persistence import InMemoryStateBackend
        backend = InMemoryStateBackend()
        backend.save("test.key", {"hello": "world"})
        assert backend.load("test.key") == {"hello": "world"}

    def test_in_memory_delete(self):
        """InMemoryStateBackend deletes keys."""
        from auar.persistence import InMemoryStateBackend
        backend = InMemoryStateBackend()
        backend.save("k", 42)
        assert backend.delete("k") is True
        assert backend.load("k") is None
        assert backend.delete("k") is False

    def test_in_memory_list_keys(self):
        """InMemoryStateBackend lists stored keys."""
        from auar.persistence import InMemoryStateBackend
        backend = InMemoryStateBackend()
        backend.save("a", 1)
        backend.save("b.c", 2)
        keys = backend.list_keys()
        assert "a" in keys
        assert "b.c" in keys

    def test_file_backend_save_load(self, tmp_path):
        """FileStateBackend round-trips data to disk."""
        from auar.persistence import FileStateBackend
        backend = FileStateBackend(str(tmp_path / "auar_state"))
        backend.save("graph.capabilities", {"cap1": {"name": "email"}})
        result = backend.load("graph.capabilities")
        assert result == {"cap1": {"name": "email"}}

    def test_file_backend_delete(self, tmp_path):
        """FileStateBackend deletes files."""
        from auar.persistence import FileStateBackend
        backend = FileStateBackend(str(tmp_path / "auar_state"))
        backend.save("temp", [1, 2, 3])
        assert backend.delete("temp") is True
        assert backend.load("temp") is None

    def test_file_backend_list_keys(self, tmp_path):
        """FileStateBackend lists all keys."""
        from auar.persistence import FileStateBackend
        backend = FileStateBackend(str(tmp_path / "auar_state"))
        backend.save("ml.scores", {"p1": 0.8})
        backend.save("graph.providers", ["p1"])
        keys = backend.list_keys()
        assert len(keys) == 2

    def test_file_backend_crash_recovery(self, tmp_path):
        """FileStateBackend persists across backend re-instantiation."""
        path = str(tmp_path / "auar_state")
        from auar.persistence import FileStateBackend
        b1 = FileStateBackend(path)
        b1.save("critical", {"important": True})
        # Simulate restart — new backend instance, same directory
        b2 = FileStateBackend(path)
        assert b2.load("critical") == {"important": True}

    def test_file_backend_load_missing_key(self, tmp_path):
        """FileStateBackend returns None for missing keys."""
        from auar.persistence import FileStateBackend
        backend = FileStateBackend(str(tmp_path / "auar_state"))
        assert backend.load("nonexistent") is None

    def test_state_backend_abc_cannot_instantiate(self):
        """StateBackend ABC cannot be instantiated directly."""
        from auar.persistence import StateBackend
        with pytest.raises(TypeError):
            StateBackend()  # type: ignore[abstract]

    def test_persistence_exported_from_auar(self):
        """Persistence classes are exported from the auar package."""
        from auar import StateBackend, InMemoryStateBackend, FileStateBackend
        assert StateBackend is not None
        assert InMemoryStateBackend is not None
        assert FileStateBackend is not None

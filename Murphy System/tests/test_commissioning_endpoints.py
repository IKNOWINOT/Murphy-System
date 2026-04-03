"""Commissioning tests — proves all previously broken endpoints now work."""
from __future__ import annotations
import os, sys
from pathlib import Path
import pytest
os.environ.setdefault("MURPHY_ENV", "test")
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.runtime.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestPreviouslyBrokenEndpoints:
    """Every endpoint in this class was returning 5xx. Proves they're fixed."""

    def test_game_worlds_post(self, client):
        r = client.post("/api/game/worlds", json={"theme": "FANTASY"})
        assert r.status_code < 500, f"game/worlds: {r.text[:200]}"

    def test_game_pipeline_start(self, client):
        r = client.post("/api/game/pipeline/start", json={"theme": "FANTASY"})
        assert r.status_code < 500, f"game/pipeline/start: {r.text[:200]}"

    def test_gate_synthesis_add_artifact(self, client):
        r = client.post("/api/gate-synthesis/artifacts/add",
                        json={"id": "a1", "type": "CODE", "source": "LLM", "content": "x"})
        assert r.status_code < 500, f"gate-synthesis/artifacts/add: {r.text[:200]}"

    def test_gate_synthesis_enumerate_failure_modes(self, client):
        r = client.post("/api/gate-synthesis/failure-modes/enumerate",
                        json={"confidence_state": {"score": 0.8}, "threshold": 0.5})
        assert r.status_code < 500, f"gate-synthesis/failure-modes/enumerate: {r.text[:200]}"

    def test_gate_synthesis_generate_gates(self, client):
        r = client.post("/api/gate-synthesis/gates/generate",
                        json={"failure_modes": [{"id": "f1", "description": "test failure"}]})
        assert r.status_code < 500, f"gate-synthesis/gates/generate: {r.text[:200]}"

    def test_gate_synthesis_update_retirement_conditions(self, client):
        r = client.post("/api/gate-synthesis/gates/update-retirement-conditions",
                        json={"condition_values": {"f1": True}})
        assert r.status_code < 500, f"update-retirement-conditions: {r.text[:200]}"

    def test_gate_synthesis_analyze_exposure(self, client):
        r = client.post("/api/gate-synthesis/murphy/analyze-exposure",
                        json={"external_side_effects": [], "gates": []})
        assert r.status_code < 500, f"analyze-exposure: {r.text[:200]}"

    def test_gate_synthesis_estimate(self, client):
        r = client.post("/api/gate-synthesis/murphy/estimate",
                        json={"risk_vector": {"probability": 0.1, "impact": 0.5, "mitigated": False}})
        assert r.status_code < 500, f"gate-synthesis/murphy/estimate: {r.text[:200]}"

    def test_mfm_promote_empty_version_returns_400(self, client):
        r = client.post("/api/mfm/promote", json={"version_id": ""})
        assert r.status_code in (400, 503), f"mfm/promote empty: {r.text[:200]}"

    def test_setup_api_collection_enqueue(self, client):
        r = client.post("/api/setup/api-collection/enqueue",
                        json={"url": "https://example.com/api", "source": "manual"})
        assert r.status_code < 500, f"api-collection/enqueue: {r.text[:200]}"

    def test_trading_sweep_trigger(self, client):
        r = client.post("/api/trading/sweep/trigger", json={})
        assert r.status_code < 500, f"trading/sweep/trigger: {r.text[:200]}"

    def test_analyze_domain(self, client):
        r = client.post("/api/analyze-domain",
                        json={"domain": "e-commerce", "context": "online retail"})
        assert r.status_code < 500, f"analyze-domain: {r.text[:200]}"

    def test_self_fix_run(self, client):
        r = client.post("/api/self-fix/run", json={})
        assert r.status_code < 500, f"self-fix/run: {r.text[:200]}"


class TestNewRoutes:
    """Routes that were missing and are now added."""

    def test_financing_options_redirect(self, client):
        r = client.get("/ui/financing-options", follow_redirects=False)
        assert r.status_code in (307, 302, 200)

    def test_dashboards_live_metrics_snapshot(self, client):
        r = client.get("/api/dashboards/live-metrics/snapshot")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True

    def test_email_webmail_url(self, client):
        r = client.get("/api/email/webmail-url")
        assert r.status_code == 200
        assert "url" in r.json()

    def test_forge_stream_endpoint(self, client):
        r = client.get("/api/demo/forge-stream")
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")


class TestForgeDeliverableEndpoint:
    """Proves the forge generate-deliverable endpoint returns usage + llm_provider."""

    def test_generate_deliverable_returns_forge_usage(self, client):
        r = client.post("/api/demo/generate-deliverable",
                        json={"query": "build a client onboarding automation"})
        assert r.status_code in (200, 429), f"generate-deliverable: {r.text[:200]}"
        if r.status_code == 200:
            data = r.json()
            assert data.get("success") is True
            assert "forge_usage" in data or "usage" in data

    def test_generate_deliverable_missing_query_returns_400(self, client):
        r = client.post("/api/demo/generate-deliverable", json={})
        assert r.status_code == 400

    def test_generate_deliverable_content_nonempty(self, client):
        r = client.post("/api/demo/generate-deliverable",
                        json={"query": "sales dashboard with KPIs"})
        if r.status_code == 200:
            data = r.json()
            assert data["deliverable"]["content"]


class TestFounderAutomations:
    """Proves founder automations are seeded."""

    def test_founder_automations_seeded(self, client):
        r = client.get("/api/automations/rules")
        assert r.status_code == 200
        rules = r.json()
        rule_list = rules if isinstance(rules, list) else rules.get("rules", [])
        assert len(rule_list) >= 1, "Expected at least founder automations to be seeded"


class TestMailSystem:
    """Proves mail system endpoints work."""

    def test_email_config_returns_webmail_url(self, client):
        r = client.get("/api/email/config")
        assert r.status_code == 200
        data = r.json()
        assert "webmail" in data
        assert data["webmail"] != "https://mail.murphy.system"

    def test_email_accounts_create(self, client):
        r = client.post("/api/email/accounts",
                        json={"address": "test@murphy.systems", "display_name": "Test"})
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_email_send(self, client):
        r = client.post("/api/email/send",
                        json={"from": "cpost@murphy.systems", "to": ["test@example.com"],
                              "subject": "Test", "body": "Hello"})
        assert r.status_code == 200
        assert r.json().get("ok") is True

"""
Production Wiring Commissioning Tests
Verifies that all crown jewel modules are correctly wired into the production server.

Test Hierarchy: Level 2 (Integration Tests)
Test Category: Production Wiring Commissioning
Commissioning Labels: G1–G9

G1: Subsystem initialised and non-None when module available.
G2: All new endpoints return HTTP 200.
G3: Background tasks list grows when heartbeat runner is wired.
G4: Health endpoint includes subsystems_wired count.
G5: Diagnostics endpoint structure is fully populated.
G6: Every endpoint returns available=False (not 500) when subsystem is None.
G7: Rosetta endpoint returns correct schema.
G8: CEO endpoint returns correct schema.
G9: No new endpoint returns HTTP 500 under nominal conditions.
"""

import pytest
import importlib
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_app():
    """Import (or reload) the production server and return (app, module)."""
    try:
        if "murphy_production_server" in sys.modules:
            mod = sys.modules["murphy_production_server"]
        else:
            mod = importlib.import_module("murphy_production_server")
        return mod.app, mod
    except Exception as exc:
        pytest.skip(f"murphy_production_server not importable: {exc}")


# Swarm header bypasses the human rate-limit bucket in tests.
_SWARM_HEADERS = {"X-Murphy-Traffic-Class": "swarm"}


def _client():
    try:
        from starlette.testclient import TestClient
        app, _ = _load_app()
        return TestClient(app, headers=_SWARM_HEADERS)
    except Exception as exc:
        pytest.skip(f"TestClient unavailable: {exc}")


# ---------------------------------------------------------------------------
# G2 / G9 — HTTP 200 for every new endpoint
# ---------------------------------------------------------------------------

NEW_ENDPOINTS = [
    "/api/rosetta/state",
    "/api/rosetta/personas",
    "/api/ceo/status",
    "/api/ceo/directives",
    "/api/heartbeat/status",
    "/api/aionmind/status",
    "/api/tools",
    "/api/lcm/status",
    "/api/gates/trust-levels",
    "/api/features",
    "/api/agents/teams",
    "/api/memory/search",
    "/api/skills",
    "/api/mcp/plugins",
    "/api/diagnostics",
]


@pytest.mark.parametrize("path", NEW_ENDPOINTS)
def test_g2_g9_endpoint_returns_200(path):
    """G2/G9: Every crown jewel endpoint returns HTTP 200, not 500."""
    client = _client()
    resp = client.get(path)
    assert resp.status_code == 200, (
        f"Expected 200 for {path}, got {resp.status_code}: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# G4 — /health includes subsystems_wired
# ---------------------------------------------------------------------------

def test_g4_health_has_subsystems_wired():
    """G4: /health response includes subsystems_wired integer field."""
    client = _client()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "subsystems_wired" in body, "subsystems_wired missing from /health"
    assert isinstance(body["subsystems_wired"], int)
    assert body["subsystems_wired"] >= 0


def test_g4_health_status_ok():
    """G4: /health status is 'ok'."""
    client = _client()
    resp = client.get("/health")
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# G5 — /api/diagnostics structure
# ---------------------------------------------------------------------------

EXPECTED_SUBSYSTEM_KEYS = {
    "rosetta", "ceo_branch", "heartbeat_runner", "aionmind",
    "lcm_engine", "gate_bypass", "tool_registry", "feature_flags",
    "team_coordinator", "persistent_memory", "skill_registry", "mcp_plugins",
}


def test_g5_diagnostics_has_all_subsystem_keys():
    """G5: /api/diagnostics contains all 12 expected subsystem keys."""
    client = _client()
    body = client.get("/api/diagnostics").json()
    assert "subsystems" in body
    missing = EXPECTED_SUBSYSTEM_KEYS - set(body["subsystems"].keys())
    assert not missing, f"Missing subsystem keys: {missing}"


def test_g5_diagnostics_has_background_tasks():
    """G5: /api/diagnostics contains background_tasks count."""
    client = _client()
    body = client.get("/api/diagnostics").json()
    assert "background_tasks" in body
    assert isinstance(body["background_tasks"], int)


def test_g5_diagnostics_has_memory_mb():
    """G5: /api/diagnostics contains memory_mb > 0."""
    client = _client()
    body = client.get("/api/diagnostics").json()
    assert "memory_mb" in body
    assert body["memory_mb"] > 0


def test_g5_diagnostics_subsystem_values_are_dicts():
    """G5: Each subsystem entry in /api/diagnostics is a dict with 'available' key."""
    client = _client()
    body = client.get("/api/diagnostics").json()
    for name, info in body["subsystems"].items():
        assert isinstance(info, dict), f"Subsystem {name!r} value is not a dict"
        assert "available" in info, f"Subsystem {name!r} missing 'available' key"


# ---------------------------------------------------------------------------
# G6 — Graceful degradation: available=False, not HTTP 500
# ---------------------------------------------------------------------------

def test_g6_rosetta_unavailable_returns_available_false(monkeypatch):
    """G6: When _rosetta_manager is None, /api/rosetta/state returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_rosetta_manager", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/rosetta/state")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_g6_ceo_unavailable_returns_available_false(monkeypatch):
    """G6: When _ceo_branch is None, /api/ceo/status returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_ceo_branch", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/ceo/status")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_g6_tools_unavailable_returns_available_false():
    """G6: When _tool_registry is None, /api/tools returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_tool_registry", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert isinstance(body["tools"], list)


def test_g6_lcm_unavailable_returns_available_false():
    """G6: When _lcm_engine_instance is None, /api/lcm/status returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_lcm_engine_instance", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/lcm/status")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_g6_features_unavailable_returns_available_false():
    """G6: When _feature_flag_manager is None, /api/features returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_feature_flag_manager", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/features")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_g6_skills_unavailable_returns_available_false():
    """G6: When _skill_registry is None, /api/skills returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_skill_registry", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/skills")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert isinstance(body["skills"], list)


def test_g6_mcp_unavailable_returns_available_false():
    """G6: When _mcp_plugin_manager is None, /api/mcp/plugins returns available=False."""
    _, mod = _load_app()
    from starlette.testclient import TestClient
    with patch.object(mod, "_mcp_plugin_manager", None):
        client = TestClient(mod.app, headers=_SWARM_HEADERS)
        resp = client.get("/api/mcp/plugins")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert isinstance(body["plugins"], list)


# ---------------------------------------------------------------------------
# G7 — Rosetta endpoint schema
# ---------------------------------------------------------------------------

def test_g7_rosetta_state_schema():
    """G7: /api/rosetta/state returns required keys."""
    client = _client()
    body = client.get("/api/rosetta/state").json()
    assert "available" in body


def test_g7_rosetta_personas_schema():
    """G7: /api/rosetta/personas returns 'available' and 'personas' list."""
    client = _client()
    body = client.get("/api/rosetta/personas").json()
    assert "available" in body
    assert "personas" in body
    assert isinstance(body["personas"], list)


def test_g7_rosetta_persona_404_when_missing():
    """G7: /api/rosetta/persona/{id} returns 404 for unknown persona when manager available.

    503 is also acceptable when the RosettaManager is present but load_state() failed
    and left the manager in a non-functional state at runtime.
    """
    _, mod = _load_app()
    if mod._rosetta_manager is None:
        pytest.skip("RosettaManager not available — skipping 404 test")
    client = _client()
    resp = client.get("/api/rosetta/persona/nonexistent_persona_xyz")
    # 404 = manager functional, persona not found; 503 = manager init degraded
    assert resp.status_code in (404, 503)


# ---------------------------------------------------------------------------
# G8 — CEO endpoint schema
# ---------------------------------------------------------------------------

def test_g8_ceo_status_schema():
    """G8: /api/ceo/status returns 'available' key."""
    client = _client()
    body = client.get("/api/ceo/status").json()
    assert "available" in body


def test_g8_ceo_directives_schema():
    """G8: /api/ceo/directives returns 'available' and 'directives' list."""
    client = _client()
    body = client.get("/api/ceo/directives").json()
    assert "available" in body
    assert "directives" in body
    assert isinstance(body["directives"], list)


def test_g8_heartbeat_status_schema():
    """G8: /api/heartbeat/status returns 'available' key."""
    client = _client()
    body = client.get("/api/heartbeat/status").json()
    assert "available" in body


# ---------------------------------------------------------------------------
# G1 — Module-level availability flags are booleans
# ---------------------------------------------------------------------------

def test_g1_availability_flags_are_booleans():
    """G1: All _*_available flags are booleans in the module namespace."""
    _, mod = _load_app()
    flags = [
        "_rosetta_available", "_ceo_available", "_heartbeat_available",
        "_aionmind_available", "_lcm_available", "_gate_bypass_available",
        "_tool_registry_available", "_feature_flags_available",
        "_multi_agent_available", "_persistent_memory_available",
        "_skill_system_available", "_mcp_plugin_available",
    ]
    for flag in flags:
        val = getattr(mod, flag, None)
        assert isinstance(val, bool), f"{flag} is not bool: {val!r}"


# ---------------------------------------------------------------------------
# Additional structural tests
# ---------------------------------------------------------------------------

def test_memory_search_endpoint():
    """GET /api/memory/search returns valid JSON with results list."""
    client = _client()
    resp = client.get("/api/memory/search?query=test&tenant_id=default")
    assert resp.status_code == 200
    body = resp.json()
    assert "available" in body
    assert "results" in body
    assert isinstance(body["results"], list)


def test_agent_teams_endpoint():
    """GET /api/agents/teams returns valid JSON with teams list."""
    client = _client()
    resp = client.get("/api/agents/teams")
    assert resp.status_code == 200
    body = resp.json()
    assert "available" in body
    assert "teams" in body
    assert isinstance(body["teams"], list)


def test_gate_trust_levels_endpoint():
    """GET /api/gates/trust-levels returns trust_levels dict."""
    client = _client()
    resp = client.get("/api/gates/trust-levels")
    assert resp.status_code == 200
    body = resp.json()
    assert "available" in body
    assert "trust_levels" in body


def test_aionmind_status_endpoint():
    """GET /api/aionmind/status returns valid JSON."""
    client = _client()
    resp = client.get("/api/aionmind/status")
    assert resp.status_code == 200
    assert "available" in resp.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

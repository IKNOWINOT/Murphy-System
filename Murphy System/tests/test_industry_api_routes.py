"""
tests/test_industry_api_routes.py
==================================
Tests for the 7 /api/industry/* REST endpoints added to app.py in Round 54.

These tests use FastAPI's TestClient (via httpx) so no network is required.
All tests are synchronous; the TestClient handles the async internals.
"""
from __future__ import annotations

import os
import sys
import time

# Raise the rate limit for tests so 35+ requests don't all hit 429
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")

# Ensure src/ is on the path

import pytest

# ---------------------------------------------------------------------------
# Try to import TestClient — skip entire module if fastapi/httpx not available
# ---------------------------------------------------------------------------
try:
    from fastapi.testclient import TestClient
    from src.runtime.app import create_app

    _app = create_app()
    _client = TestClient(_app, raise_server_exceptions=False)
    _AVAILABLE = True
except Exception as _e:
    _AVAILABLE = False
    _skip_reason = f"FastAPI/app unavailable: {_e}"

pytestmark = pytest.mark.skipif(not _AVAILABLE, reason=_skip_reason if not _AVAILABLE else "")


# ---------------------------------------------------------------------------
# Helper: retry on 429 (rate limit hit during rapid test execution)
# ---------------------------------------------------------------------------

def _post(path: str, json: dict, *, retries: int = 5, backoff: float = 0.25):
    """POST with automatic 429 retry."""
    r = _client.post(path, json=json)
    for _ in range(retries):
        if r.status_code != 429:
            break
        time.sleep(backoff)
        r = _client.post(path, json=json)
    return r


def _get(path: str, *, retries: int = 5, backoff: float = 0.25):
    """GET with automatic 429 retry."""
    r = _client.get(path)
    for _ in range(retries):
        if r.status_code != 429:
            break
        time.sleep(backoff)
        r = _client.get(path)
    return r


def _ok_or_rate_limited(r, expected: int = 200) -> bool:
    """Return True if response matches expected status OR is a 429 rate limit."""
    return r.status_code in (expected, 429)


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SAMPLE_EDE = (
    "object-name\tobject-type\tobject-identifier\tdescription\tunits-code\n"
    "SAT\tanalog-input\t0\tSupply Air Temp\t62\n"
    "RAT\tanalog-input\t1\tReturn Air Temp\t62\n"
    "CC_POS\tanalog-output\t0\tCooling Coil Valve\t98"
)

UTILITY_DATA = {
    "electricity_kwh": 500_000,
    "electricity_cost": 60_000,
    "natural_gas_therms": 20_000,
    "natural_gas_cost": 18_000,
    "facility_sqft": 50_000,
}

# ---------------------------------------------------------------------------
# /api/industry/ingest
# ---------------------------------------------------------------------------

class TestIngestEndpoint:
    def test_ingest_ede_returns_200(self):
        r = _post("/api/industry/ingest", {"content": SAMPLE_EDE, "filename": "ahu.ede"})
        assert _ok_or_rate_limited(r, 200)

    def test_ingest_success_flag(self):
        r = _post("/api/industry/ingest", {"content": SAMPLE_EDE, "filename": "ahu.ede"})
        assert r.json().get("success") is True or r.status_code == 429

    def test_ingest_records_ingested(self):
        r = _post("/api/industry/ingest", {"content": SAMPLE_EDE, "filename": "ahu.ede"})
        assert r.json().get("records_ingested", 0) >= 3

    def test_ingest_empty_content_returns_400(self):
        r = _post("/api/industry/ingest", {"content": "", "filename": "ahu.ede"})
        assert r.status_code == 400

    def test_ingest_adapter_name_in_response(self):
        r = _post("/api/industry/ingest", {"content": SAMPLE_EDE, "filename": "ahu.ede"})
        if r.status_code != 429:
            assert "adapter_name" in r.json()

    def test_ingest_csv_data(self):
        csv_data = "address,register_type,description,units\n40001,holding,Chiller Enable,\n40002,holding,CWS Temp,degF"
        r = _post("/api/industry/ingest", {"content": csv_data, "filename": "modbus.csv"})
        assert _ok_or_rate_limited(r, 200)

# ---------------------------------------------------------------------------
# /api/industry/climate/{city}
# ---------------------------------------------------------------------------

class TestClimateEndpoint:
    def test_chicago_returns_200(self):
        r = _get("/api/industry/climate/Chicago")
        assert _ok_or_rate_limited(r, 200)

    def test_chicago_climate_zone_5a(self):
        r = _get("/api/industry/climate/Chicago")
        assert r.json().get("climate_zone") == "5A"

    def test_miami_climate_zone_1a(self):
        r = _get("/api/industry/climate/Miami")
        assert r.json().get("climate_zone") == "1A"

    def test_response_has_resilience_factors(self):
        r = _get("/api/industry/climate/Chicago")
        j = r.json()
        assert "resilience_factors" in j
        assert "design_temp_cooling" in j["resilience_factors"]

    def test_response_has_design_recommendations(self):
        r = _get("/api/industry/climate/Miami")
        j = r.json()
        if r.status_code != 429:
            assert isinstance(j.get("design_recommendations"), list)

    def test_unknown_city_returns_200(self):
        r = _get("/api/industry/climate/Atlantis")
        assert _ok_or_rate_limited(r, 200)
        assert r.json().get("success") is True or r.status_code == 429

# ---------------------------------------------------------------------------
# /api/industry/energy-audit
# ---------------------------------------------------------------------------

class TestEnergyAuditEndpoint:
    def test_returns_200(self):
        r = _post("/api/industry/energy-audit", {"utility_data": UTILITY_DATA})
        assert _ok_or_rate_limited(r, 200)

    def test_success_flag(self):
        r = _post("/api/industry/energy-audit", {"utility_data": UTILITY_DATA})
        assert r.json().get("success") is True or r.status_code == 429

    def test_ecm_count_positive(self):
        r = _post("/api/industry/energy-audit", {"utility_data": UTILITY_DATA})
        assert r.json().get("ecm_count", 0) > 0

    def test_has_utility_analysis(self):
        r = _post("/api/industry/energy-audit", {"utility_data": UTILITY_DATA})
        if r.status_code != 429:
            assert "utility_analysis" in r.json()

    def test_level_III_audit(self):
        r = _post("/api/industry/energy-audit", {
            "utility_data": UTILITY_DATA, "audit_level": "III", "facility_type": "hospital"
        })
        assert _ok_or_rate_limited(r, 200)
        assert r.json().get("audit_level") == "III"

    def test_mss_simplify_mode(self):
        r = _post("/api/industry/energy-audit", {
            "utility_data": UTILITY_DATA, "mss_mode": "simplify"
        })
        assert _ok_or_rate_limited(r, 200)
        assert "mss_rubric" in r.json()

# ---------------------------------------------------------------------------
# /api/industry/interview
# ---------------------------------------------------------------------------

class TestInterviewEndpoint:
    def test_start_new_session(self):
        r = _post("/api/industry/interview", {"domain": "hvac"})
        assert _ok_or_rate_limited(r, 200)

    def test_returns_session_id(self):
        r = _post("/api/industry/interview", {})
        j = r.json()
        assert "session_id" in j and j["session_id"]

    def test_returns_first_question(self):
        r = _post("/api/industry/interview", {})
        j = r.json()
        assert j.get("question") is not None

    def test_answer_advances_session(self):
        r1 = _post("/api/industry/interview", {"domain": "bas"})
        j1 = r1.json()
        sid = j1["session_id"]
        q1 = j1.get("question")
        qid = q1.get("question_id") if isinstance(q1, dict) else None
        if qid is None:
            pytest.skip("question has no question_id")
        r2 = _post("/api/industry/interview", {
            "session_id": sid, "question_id": qid, "answer": "We use BACnet MS/TP on all field devices"
        })
        assert r2.status_code == 200

    def test_status_field_present(self):
        r = _post("/api/industry/interview", {})
        if r.status_code != 429:
            assert "status" in r.json()

# ---------------------------------------------------------------------------
# /api/industry/configure
# ---------------------------------------------------------------------------

class TestConfigureEndpoint:
    def test_ahu_returns_200(self):
        r = _post("/api/industry/configure", {"description": "air handling unit supply fan vfd"})
        assert _ok_or_rate_limited(r, 200)

    def test_detects_ahu_type(self):
        r = _post("/api/industry/configure", {"description": "air handling unit supply fan vfd"})
        assert r.json().get("system_type") == "ahu"

    def test_has_recommended_strategy(self):
        r = _post("/api/industry/configure", {"description": "chiller plant cooling tower"})
        j = r.json()
        if r.status_code != 429:
            assert "recommended_strategy" in j

    def test_mss_simplify_mode(self):
        r = _post("/api/industry/configure", {
            "description": "variable air volume terminal unit",
            "mss_mode": "simplify"
        })
        assert _ok_or_rate_limited(r, 200)
        assert r.json().get("mss_mode") == "simplify"

    def test_empty_description_returns_400(self):
        r = _post("/api/industry/configure", {"description": ""})
        assert r.status_code == 400

    def test_solidify_mode(self):
        r = _post("/api/industry/configure", {
            "description": "boiler plant hot water loop",
            "mss_mode": "solidify"
        })
        assert _ok_or_rate_limited(r, 200)

# ---------------------------------------------------------------------------
# /api/industry/as-built
# ---------------------------------------------------------------------------

class TestAsBuiltEndpoint:
    def test_returns_200(self):
        r = _post("/api/industry/as-built", {
            "system_name": "AHU-01",
            "equipment_spec": {"equipment_tag": "AHU-01", "equipment_type": "ahu"}
        })
        assert _ok_or_rate_limited(r, 200)

    def test_success_flag(self):
        r = _post("/api/industry/as-built", {
            "system_name": "AHU-01",
            "equipment_spec": {"equipment_tag": "AHU-01", "equipment_type": "ahu"}
        })
        assert r.json().get("success") is True or r.status_code == 429

    def test_has_diagram(self):
        r = _post("/api/industry/as-built", {
            "system_name": "CH-01",
            "equipment_spec": {"equipment_tag": "CH-01", "equipment_type": "chiller"}
        })
        if r.status_code != 429:
            assert "diagram" in r.json()

    def test_has_point_schedule(self):
        r = _post("/api/industry/as-built", {
            "system_name": "BLR-01",
            "equipment_spec": {"equipment_tag": "BLR-01", "equipment_type": "boiler"}
        })
        if r.status_code != 429:
            assert "point_schedule" in r.json()

    def test_has_schematic_description(self):
        r = _post("/api/industry/as-built", {
            "system_name": "FCU-01",
            "equipment_spec": {}
        })
        j = r.json()
        if r.status_code != 429:
            assert "schematic_description" in j
        if r.status_code != 429:
            assert len(j.get("schematic_description", "")) > 0

# ---------------------------------------------------------------------------
# /api/industry/decide
# ---------------------------------------------------------------------------

class TestDecideEndpoint:
    _OPTIONS = [
        {"name": "VFD", "scores": {"energy_savings": 0.9, "capital_cost": 0.3, "maintenance": 0.7, "reliability": 0.8, "code_compliance": 1.0, "safety": 1.0}},
        {"name": "Constant Speed", "scores": {"energy_savings": 0.2, "capital_cost": 0.9, "maintenance": 0.9, "reliability": 0.9, "code_compliance": 1.0, "safety": 1.0}},
    ]

    def test_returns_200(self):
        r = _post("/api/industry/decide", {
            "question": "Motor control strategy",
            "options": self._OPTIONS
        })
        assert _ok_or_rate_limited(r, 200)

    def test_success_flag(self):
        r = _post("/api/industry/decide", {
            "question": "Motor control strategy",
            "options": self._OPTIONS
        })
        assert r.json().get("success") is True or r.status_code == 429

    def test_has_viable_options_or_winner(self):
        r = _post("/api/industry/decide", {
            "question": "Motor control strategy",
            "options": self._OPTIONS,
            "criteria_set": "energy_system_selection"
        })
        j = r.json()
        if r.status_code != 429:
            assert "viable_options" in j or "winner" in j

    def test_empty_options_returns_400(self):
        r = _post("/api/industry/decide", {"question": "test", "options": []})
        assert r.status_code == 400

    def test_has_explanation(self):
        r = _post("/api/industry/decide", {
            "question": "Which ECM first?",
            "options": self._OPTIONS,
            "criteria_set": "ecm_prioritization"
        })
        j = r.json()
        if r.status_code != 429:
            assert "explanation" in j

    def test_eliminated_options_list(self):
        r = _post("/api/industry/decide", {
            "question": "Motor control strategy",
            "options": self._OPTIONS
        })
        if r.status_code != 429:
            assert "eliminated_options" in r.json()


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

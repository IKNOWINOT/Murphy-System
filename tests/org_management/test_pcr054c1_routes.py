"""PCR-054c.1 — Engagement Loop HTTP routes regression suite."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.engagement_routes import register_engagement_routes


@pytest.fixture
def client(tmp_path):
    """Per-test app with isolated SQLite + browse paths."""
    app = FastAPI()
    db_path = str(tmp_path / "engagement_folders.db")
    browse_root = str(tmp_path / "engagements")
    status = register_engagement_routes(app, db_path=db_path, browse_root=browse_root)
    assert status["ok"] and status["registered"]
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────


class TestRegistration:
    def test_registration_is_idempotent(self, tmp_path):
        app = FastAPI()
        db = str(tmp_path / "db.sqlite"); br = str(tmp_path / "br")
        s1 = register_engagement_routes(app, db_path=db, browse_root=br)
        s2 = register_engagement_routes(app, db_path=db, browse_root=br)
        assert s1["ok"] and s2["ok"]
        assert s2.get("note", "").startswith("already registered")

    def test_four_routes_registered(self, tmp_path):
        app = FastAPI()
        s = register_engagement_routes(
            app,
            db_path=str(tmp_path / "db.sqlite"),
            browse_root=str(tmp_path / "br"),
        )
        assert len(s["routes_added"]) == 5  # PCR-054d: outreach added


# ─────────────────────────────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────────────────────────────


class TestCreateEndpoint:
    def test_create_returns_drafting_folder(self, client):
        r = client.post("/api/org/engagement/create", json={
            "tenant_id": "t1", "role_id": "cpa_main",
            "artifact_type": "tax_return",
            "artifact_content": "draft body",
            "license_type_required": "CPA",
            "jurisdiction_required": "US-CA",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["engagement"]["state"] == "drafting"
        assert body["engagement"]["engagement_id"].startswith("eng_")
        assert body["engagement"]["license_type_required"] == "CPA"
        assert body["engagement"]["browse_path"]  # path string present

    def test_create_minimal_body_works(self, client):
        r = client.post("/api/org/engagement/create", json={
            "tenant_id": "t1", "role_id": "r1",
            "artifact_type": "tax_return",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_create_missing_required_returns_422(self, client):
        r = client.post("/api/org/engagement/create", json={
            "tenant_id": "t1",  # missing role_id and artifact_type
        })
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# Transition
# ─────────────────────────────────────────────────────────────────────


def _make(client, **overrides):
    body = {"tenant_id": "t1", "role_id": "r1", "artifact_type": "tax_return"}
    body.update(overrides)
    r = client.post("/api/org/engagement/create", json=body)
    assert r.status_code == 200
    return r.json()["engagement"]["engagement_id"]


class TestTransitionEndpoint:
    def test_happy_path_to_finalized(self, client):
        eid = _make(client)
        for s in ["outreach_queued", "awaiting_attestation",
                  "validating_attestation", "finalized"]:
            r = client.post(
                f"/api/org/engagement/{eid}/transition",
                json={"to_state": s, "reason": f"test-> {s}"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["engagement"]["state"] == s

    def test_illegal_skip_returns_409(self, client):
        eid = _make(client)
        # cannot go drafting -> finalized directly
        r = client.post(
            f"/api/org/engagement/{eid}/transition",
            json={"to_state": "finalized"},
        )
        assert r.status_code == 409
        assert r.json()["ok"] is False
        assert "not allowed" in r.json()["error"]

    def test_unknown_state_returns_400(self, client):
        eid = _make(client)
        r = client.post(
            f"/api/org/engagement/{eid}/transition",
            json={"to_state": "nonsense"},
        )
        assert r.status_code == 400

    def test_transition_with_update_fields(self, client):
        eid = _make(client)
        r = client.post(
            f"/api/org/engagement/{eid}/transition",
            json={
                "to_state": "outreach_queued",
                "update_fields": {
                    "practitioner_email": "cpa@example.com",
                    "rate_quote_usd": 950.0,
                },
            },
        )
        assert r.status_code == 200
        eng = r.json()["engagement"]
        assert eng["practitioner_email"] == "cpa@example.com"
        assert eng["rate_quote_usd"] == 950.0


# ─────────────────────────────────────────────────────────────────────
# Get + list
# ─────────────────────────────────────────────────────────────────────


class TestGetEndpoint:
    def test_get_returns_summary_events_attestations(self, client):
        eid = _make(client)
        r = client.get(f"/api/org/engagement/{eid}")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["engagement"]["engagement_id"] == eid
        assert isinstance(body["events"], list)
        assert isinstance(body["attestations"], list)
        # at least the initial "drafting" transition event
        assert any(e["event_type"] == "transition" for e in body["events"])

    def test_get_unknown_returns_404(self, client):
        r = client.get("/api/org/engagement/eng_does_not_exist")
        assert r.status_code == 404


class TestListEndpoint:
    def test_list_empty(self, client):
        r = client.get("/api/org/engagements")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["count"] == 0
        assert body["engagements"] == []

    def test_list_after_create(self, client):
        _make(client, tenant_id="t1")
        _make(client, tenant_id="t2")
        r = client.get("/api/org/engagements")
        assert r.json()["count"] == 2

    def test_list_filtered_by_tenant(self, client):
        _make(client, tenant_id="t1")
        _make(client, tenant_id="t2")
        r = client.get("/api/org/engagements?tenant_id=t1")
        body = r.json()
        assert body["count"] == 1
        assert body["engagements"][0]["tenant_id"] == "t1"

    def test_list_filtered_by_state(self, client):
        eid = _make(client)
        client.post(f"/api/org/engagement/{eid}/transition",
                    json={"to_state": "outreach_queued"})
        _make(client)  # leave one in DRAFTING

        r1 = client.get("/api/org/engagements?state=drafting")
        r2 = client.get("/api/org/engagements?state=outreach_queued")
        assert r1.json()["count"] == 1
        assert r2.json()["count"] == 1

    def test_list_bad_state_returns_400(self, client):
        r = client.get("/api/org/engagements?state=nonsense")
        assert r.status_code == 400

"""
Integration tests for ROI Calendar endpoints in murphy_production_server.py:
  - GET  /api/roi-calendar/events
  - POST /api/roi-calendar/events
  - PATCH /api/roi-calendar/events/{event_id}
  - GET  /api/roi-calendar/summary
  - GET  /api/roi-calendar/export
  - GET  /ui/roi-calendar

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

try:
    from murphy_production_server import app as _prod_app, _roi_calendar_store

    _PROD_APP_AVAILABLE = True
except Exception:
    _PROD_APP_AVAILABLE = False
    _prod_app = None  # type: ignore[assignment]
    _roi_calendar_store = []  # type: ignore[assignment]


@pytest.fixture()
def client():
    if not _PROD_APP_AVAILABLE:
        pytest.skip("murphy_production_server not importable")
    _roi_calendar_store.clear()
    return TestClient(_prod_app)


# ── GET /api/roi-calendar/events ─────────────────────────────────────


class TestROICalendarEvents:

    def test_events_empty_on_start(self, client) -> None:
        resp = client.get("/api/roi-calendar/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["events"] == []
        assert body["total"] == 0

    def test_create_event(self, client) -> None:
        resp = client.post(
            "/api/roi-calendar/events",
            json={
                "title": "Invoice Automation",
                "human_cost_estimate": 500.0,
                "human_time_estimate_hours": 10,
                "start": "2026-04-01T09:00:00",
                "end": "2026-04-01T17:00:00",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["ok"] is True
        ev = body["event"]
        assert ev["title"] == "Invoice Automation"
        assert ev["event_id"].startswith("roi-")
        assert ev["human_cost_estimate"] == 500.0
        assert ev["status"] == "pending"
        assert ev["progress_pct"] == 0
        assert ev["agent_compute_cost"] == 0.0
        assert ev["roi"] == 0.0

    def test_create_event_appears_in_list(self, client) -> None:
        client.post(
            "/api/roi-calendar/events",
            json={"title": "Task A", "human_cost_estimate": 100},
        )
        client.post(
            "/api/roi-calendar/events",
            json={"title": "Task B", "human_cost_estimate": 200},
        )
        resp = client.get("/api/roi-calendar/events")
        body = resp.json()
        assert body["total"] == 2
        titles = [e["title"] for e in body["events"]]
        assert "Task A" in titles
        assert "Task B" in titles

    def test_create_event_defaults(self, client) -> None:
        resp = client.post("/api/roi-calendar/events", json={})
        assert resp.status_code == 201
        ev = resp.json()["event"]
        assert ev["title"] == "Untitled Task"
        assert ev["human_cost_estimate"] == 0.0
        assert ev["human_time_estimate_hours"] == 8.0


# ── PATCH /api/roi-calendar/events/{event_id} ───────────────────────


class TestROICalendarUpdate:

    def _create(self, client, **kwargs):
        defaults = {"title": "Test Task", "human_cost_estimate": 1000.0}
        defaults.update(kwargs)
        resp = client.post("/api/roi-calendar/events", json=defaults)
        return resp.json()["event"]

    def test_update_status(self, client) -> None:
        ev = self._create(client)
        resp = client.patch(
            f"/api/roi-calendar/events/{ev['event_id']}",
            json={"status": "running", "progress_pct": 25},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["event"]["status"] == "running"
        assert body["event"]["progress_pct"] == 25

    def test_update_agent_cost_recalculates_roi(self, client) -> None:
        ev = self._create(client, human_cost_estimate=1000)
        resp = client.patch(
            f"/api/roi-calendar/events/{ev['event_id']}",
            json={"agent_compute_cost": 50.0, "overhead_cost": 10.0},
        )
        body = resp.json()
        assert body["event"]["roi"] == 940.0  # 1000 - 50 - 10

    def test_update_not_found(self, client) -> None:
        resp = client.patch(
            "/api/roi-calendar/events/nonexistent",
            json={"status": "running"},
        )
        assert resp.status_code == 404
        assert resp.json()["ok"] is False

    def test_hitl_review_adds_cost(self, client) -> None:
        ev = self._create(client, human_cost_estimate=1000)
        resp = client.patch(
            f"/api/roi-calendar/events/{ev['event_id']}",
            json={
                "hitl_review": {
                    "decision": "change_requested",
                    "notes": "Need revisions",
                    "cost_delta": 25.0,
                }
            },
        )
        body = resp.json()
        assert len(body["event"]["hitl_reviews"]) == 1
        assert body["event"]["agent_compute_cost"] == 25.0
        assert len(body["event"]["cost_adjustments"]) == 1

    def test_qc_failure_adds_cost(self, client) -> None:
        ev = self._create(client, human_cost_estimate=1000)
        # First set some agent cost
        client.patch(
            f"/api/roi-calendar/events/{ev['event_id']}",
            json={"agent_compute_cost": 100.0},
        )
        # Now fail QC
        resp = client.patch(
            f"/api/roi-calendar/events/{ev['event_id']}",
            json={"qc_result": {"passed": False, "reason": "formatting", "retry_cost": 15.0}},
        )
        body = resp.json()
        assert body["event"]["qc_failures"] == 1
        assert body["event"]["agent_compute_cost"] == 115.0  # 100 + 15

    def test_qc_pass(self, client) -> None:
        ev = self._create(client)
        resp = client.patch(
            f"/api/roi-calendar/events/{ev['event_id']}",
            json={"qc_result": {"passed": True}},
        )
        body = resp.json()
        assert body["event"]["qc_passes"] == 1
        assert body["event"]["qc_failures"] == 0


# ── GET /api/roi-calendar/summary ────────────────────────────────────


class TestROICalendarSummary:

    def test_summary_empty(self, client) -> None:
        resp = client.get("/api/roi-calendar/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["total_tasks"] == 0
        assert body["roi_pct"] == 0

    def test_summary_with_events(self, client) -> None:
        client.post(
            "/api/roi-calendar/events",
            json={"title": "A", "human_cost_estimate": 500},
        )
        client.post(
            "/api/roi-calendar/events",
            json={"title": "B", "human_cost_estimate": 300},
        )
        # Update one to running with agent cost
        events = client.get("/api/roi-calendar/events").json()["events"]
        eid = events[0]["event_id"]
        client.patch(
            f"/api/roi-calendar/events/{eid}",
            json={"status": "running", "agent_compute_cost": 20.0},
        )

        resp = client.get("/api/roi-calendar/summary")
        body = resp.json()
        assert body["total_tasks"] == 2
        assert body["total_human_cost_estimate"] == 800.0
        assert body["total_agent_cost"] == 20.0
        assert body["total_roi"] == 780.0
        assert body["active_tasks"] == 1
        assert body["roi_pct"] == 97.5  # (780/800)*100


# ── GET /api/roi-calendar/export ─────────────────────────────────────


class TestROICalendarExport:

    def test_export_json(self, client) -> None:
        client.post(
            "/api/roi-calendar/events",
            json={"title": "Export Test", "human_cost_estimate": 100},
        )
        resp = client.get("/api/roi-calendar/export?fmt=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        assert "roi-calendar.json" in resp.headers.get("content-disposition", "")
        body = resp.json()
        assert body["ok"] is True
        assert len(body["events"]) == 1

    def test_export_csv(self, client) -> None:
        client.post(
            "/api/roi-calendar/events",
            json={"title": "CSV Test", "human_cost_estimate": 200},
        )
        resp = client.get("/api/roi-calendar/export?fmt=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "roi-calendar.csv" in resp.headers.get("content-disposition", "")
        content = resp.text
        assert "event_id" in content
        assert "CSV Test" in content


# ── GET /ui/roi-calendar ─────────────────────────────────────────────


class TestROICalendarUI:

    def test_ui_route_serves_html(self, client) -> None:
        resp = client.get("/ui/roi-calendar")
        assert resp.status_code == 200
        text = resp.text
        assert "ROI Calendar" in text or "roi" in text.lower()

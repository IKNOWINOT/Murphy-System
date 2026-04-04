"""End-to-end commissioning test for Murphy System.

Tests the complete user journey including the three fixes from this PR:
  - ROI Calendar with real random data, agent colors, checklists
  - Onboarding chat always returning 'response' and 'message' fields
  - Forge download visibility and error handling
  - All stub endpoints (meetings, market quote, demo spec)
  - LLM fallback chain debug endpoint
  - MurphyLibrarianChat integration in landing page

Run with: pytest tests/test_e2e_commissioning.py -v --override-ini="addopts="

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient
from src.runtime.app import create_app

_app = create_app()
_client = TestClient(_app)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: System Health
# ─────────────────────────────────────────────────────────────────────────────

class TestSystemHealth(unittest.TestCase):
    """Verify the system starts and self-reports healthy."""

    def test_health_ok(self):
        r = _client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(
            d.get("healthy") or d.get("ok") or d.get("status") in ("ok", "healthy"),
            f"Bad health response: {d}"
        )

    def test_llm_debug_chain(self):
        """onboard layer must always be available (no API key required)."""
        r = _client.get("/api/llm/debug")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d.get("ok"))
        chain = d.get("fallback_chain", [])
        onboard = next((c for c in chain if c["provider"] == "onboard"), None)
        self.assertIsNotNone(onboard, "onboard layer missing from chain")
        self.assertTrue(onboard["available"])
        self.assertIn("active_provider", d)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Onboarding Chat (Issue 2 fix)
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingChat(unittest.TestCase):
    """mfgc-chat must always return 'response' + 'message' fields."""

    SESSION = "commission-test-session"

    def _chat(self, msg):
        r = _client.post("/api/onboarding/mfgc-chat",
                         json={"session_id": self.SESSION, "message": msg})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_response_field_always_present(self):
        d = self._chat("hello")
        self.assertIn("response", d, f"'response' missing: {list(d.keys())}")
        self.assertIn("message", d, f"'message' missing: {list(d.keys())}")

    def test_no_connection_fallback(self):
        """Must NOT show 'having trouble connecting' for normal messages."""
        d = self._chat("I need invoice processing automation")
        reply = d.get("response", "")
        self.assertNotIn("having trouble connecting", reply.lower(),
                         f"Got broken fallback: {reply!r}")

    def test_deterministic_fallback_invoice(self):
        """Invoice keyword gets a contextual response."""
        d = self._chat("invoice billing payment processing")
        reply = d.get("response", "")
        self.assertGreater(len(reply), 30, f"Reply too short: {reply!r}")

    def test_all_required_fields(self):
        d = self._chat("logistics company, Salesforce CRM")
        for f in ("success", "response", "message", "gate_satisfaction",
                  "confidence", "ready_for_plan"):
            self.assertIn(f, d, f"Field '{f}' missing from response")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: ROI Calendar (Issue 1 fix)
# ─────────────────────────────────────────────────────────────────────────────

class TestROICalendar(unittest.TestCase):
    """ROI Calendar must return real random data with agents and checklists."""

    @classmethod
    def setUpClass(cls):
        r = _client.get("/api/roi-calendar/events")
        cls._events = r.json().get("events", [])

    def test_minimum_events(self):
        self.assertGreaterEqual(len(self._events), 10,
                                f"Got {len(self._events)} events, need ≥10")

    def test_agents_are_colored_objects(self):
        for ev in self._events:
            agents = ev.get("agents", [])
            if agents:
                a = agents[0]
                self.assertIsInstance(a, dict)
                self.assertIn("name", a)
                self.assertIn("color", a)
                self.assertTrue(a["color"].startswith("#"), f"Bad color: {a['color']}")
                return
        self.fail("No events have agents")

    def test_checklists_with_agents(self):
        for ev in self._events:
            cl = ev.get("checklist", [])
            if cl:
                item = cl[0]
                self.assertIn("step", item)
                self.assertIn("agent", item)
                self.assertIn("status", item)
                self.assertIn(item["status"], ("pending", "running", "complete"))
                return
        self.fail("No events have a checklist")

    def test_industry_hourly_rates(self):
        for ev in self._events:
            if ev.get("hourly_rate"):
                r = float(ev["hourly_rate"])
                self.assertGreaterEqual(r, 35)
                self.assertLessEqual(r, 150)
                return
        self.fail("No events have hourly_rate")

    def test_roi_summary_positive(self):
        r = _client.get("/api/roi-calendar/summary")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertGreater(d.get("total_human_cost_estimate", 0), 0)

    def test_export_json(self):
        r = _client.get("/api/roi-calendar/export?fmt=json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("events", r.json())

    def test_export_csv(self):
        r = _client.get("/api/roi-calendar/export?fmt=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("event_id", r.text)

    def test_create_event(self):
        r = _client.post("/api/roi-calendar/events", json={
            "title": "Commission Test", "human_cost_estimate": 500,
            "human_time_estimate_hours": 4,
            "start": "2026-03-27T09:00:00Z", "end": "2026-03-27T11:00:00Z"
        })
        self.assertIn(r.status_code, (200, 201))
        self.assertTrue(r.json().get("ok"))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: Forge Download (Issue 3 fix)
# ─────────────────────────────────────────────────────────────────────────────

class TestForgeDeliverable(unittest.TestCase):
    """Forge must return downloadable content or a clear error — never silent."""

    def test_generates_or_rate_limits(self):
        r = _client.post("/api/demo/generate-deliverable",
                         json={"query": "invoice processing automation workflow"})
        self.assertIn(r.status_code, (200, 429),
                      f"Unexpected {r.status_code}: {r.text[:100]}")

    def test_empty_query_returns_400(self):
        r = _client.post("/api/demo/generate-deliverable", json={})
        self.assertEqual(r.status_code, 400)

    def test_success_response_has_downloadable_content(self):
        r = _client.post("/api/demo/generate-deliverable",
                         json={"query": "compliance audit automation"})
        if r.status_code == 429:
            return  # Rate limited — skip
        d = r.json()
        if d.get("success"):
            self.assertIn("content", d.get("deliverable", {}))
            self.assertIn("filename", d.get("deliverable", {}))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: Previously-Missing Stub Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestStubEndpoints(unittest.TestCase):
    """All three missing endpoints now return 200 OK with proper data."""

    def test_demo_spec(self):
        r = _client.get("/api/demo/spec/invoice-workflow")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

    def test_market_quote(self):
        r = _client.get("/api/market/quote/MSFT")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d.get("ok"))
        price = d.get("price") or d.get("quote", {}).get("price")
        self.assertIsNotNone(price)

    def test_meetings_lifecycle(self):
        r1 = _client.post("/api/meetings/start", json={"title": "Standup"})
        self.assertEqual(r1.status_code, 200)
        sid = r1.json().get("session_id")
        self.assertIsNotNone(sid)

        r2 = _client.get(f"/api/meetings/{sid}/transcript")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json().get("ok"))

        r3 = _client.get(f"/api/meetings/{sid}/suggestions")
        self.assertEqual(r3.status_code, 200)
        sug = r3.json()
        self.assertTrue(sug.get("ok"))
        self.assertIsInstance(sug.get("suggestions"), list)
        self.assertGreater(len(sug["suggestions"]), 0)

        r4 = _client.post(f"/api/meetings/{sid}/end", json={})
        self.assertEqual(r4.status_code, 200)
        self.assertTrue(r4.json().get("ok"))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6: Librarian / MurphyLibrarianChat
# ─────────────────────────────────────────────────────────────────────────────

class TestLibrarian(unittest.TestCase):

    def test_ask_returns_reply(self):
        r = _client.post("/api/librarian/ask",
                         json={"message": "What automations does Murphy support?"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        reply = d.get("response") or d.get("reply_text") or d.get("answer")
        self.assertIsNotNone(reply)
        self.assertGreater(len(reply), 20)

    def test_query_field_accepted(self):
        """MurphyLibrarianChat uses 'query' field — must be accepted."""
        r = _client.post("/api/librarian/ask", json={"query": "show me ROI data"})
        self.assertEqual(r.status_code, 200)

    def test_never_500(self):
        for msg in ["", "!@#$", "x" * 500]:
            r = _client.post("/api/librarian/ask", json={"message": msg})
            self.assertNotEqual(r.status_code, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7: HTML UI — error banner + murphy-components.js present
# ─────────────────────────────────────────────────────────────────────────────

class TestUIPages(unittest.TestCase):

    _MURPHY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _read_html(self, fname):
        with open(os.path.join(self._MURPHY_DIR, fname), encoding="utf-8") as f:
            return f.read()

    def test_landing_has_murphy_components(self):
        r = _client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("murphy-components.js", r.text)

    def test_landing_has_librarian_chat(self):
        r = _client.get("/")
        self.assertIn("MurphyLibrarianChat", r.text)

    def test_roi_calendar_has_error_banner(self):
        """Check file directly — /ui/roi-calendar requires auth."""
        content = self._read_html("roi_calendar.html")
        self.assertIn("murphy-error-banner", content)
        self.assertIn("showMurphyError", content)

    def test_onboarding_has_error_banner(self):
        """Check file directly — /ui/onboarding requires auth."""
        content = self._read_html("onboarding_wizard.html")
        self.assertIn("murphy-error-banner", content)
        self.assertIn("showMurphyError", content)

    def test_dashboard_serves(self):
        r = _client.get("/ui/dashboard")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)

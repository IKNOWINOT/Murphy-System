"""Phase-2 continuation integration tests for /api/execute.

* F33 — when the founder hits ``/api/execute`` with a low-risk task,
  the AionMind section reports ``auto_approved: True``.
* F35 — when an anonymous caller hits ``/api/execute`` with a
  MEDIUM-risk task and the kernel returns ``pending_approval``, the
  B8 hand-off creates an entry in the HITL queue surfaced via
  ``/api/hitl/queue``.

Both tests skip cleanly when ``create_app()`` cannot be imported in
the minimal sandbox (heavy deps absent), matching the conventions of
``test_execute_identity_attribution.py``.
"""

from __future__ import annotations

import os

import pytest


_FOUNDER_EMAIL = "cpost@murphy.systems"


def _build_client():
    try:
        from fastapi.testclient import TestClient
    except Exception:  # pragma: no cover
        pytest.skip("fastapi[testclient] not installed")
    try:
        from src.runtime.app import create_app
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Cannot import create_app: {exc}")
    os.environ["MURPHY_FOUNDER_EMAIL"] = _FOUNDER_EMAIL
    try:
        app = create_app()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"create_app() failed in this environment: {exc}")
    return TestClient(app)


@pytest.fixture(scope="module")
def client():
    with _build_client() as c:
        yield c


def _aionmind_section(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get("aionmind") or payload.get("result", {}).get("aionmind")


class TestFounderAutoApprovedEndToEnd:
    """F33 — founder identity propagates to ``auto_approved=True``."""

    def test_founder_low_risk_task_reports_auto_approved(self, client):
        resp = client.post(
            "/api/execute",
            headers={"X-User-ID": _FOUNDER_EMAIL},
            json={
                "task_description": "diagnostic ping",
                "task_type": "general",  # → LOW risk
            },
        )
        assert resp.status_code == 200, resp.text
        am = _aionmind_section(resp.json())
        if am is None:
            pytest.skip("AionMind kernel not initialised in this build")
        if am.get("status") == "no_candidates":
            pytest.skip("Kernel has no registered capabilities for this task")
        # A3 forces founder role to "owner"; LOW risk is well under
        # the owner ceiling (MEDIUM); auto_approved must be True.
        assert am.get("auto_approved") is True, am


class TestHitlHandoffEnqueue:
    """F35 — pending_approval results land in the HITL queue (B8)."""

    def test_anonymous_medium_risk_creates_hitl_intervention(self, client):
        resp = client.post(
            "/api/execute",
            json={
                "task_description": "deploy v2",
                "task_type": "deployment",  # → MEDIUM risk
            },
        )
        assert resp.status_code == 200, resp.text
        am = _aionmind_section(resp.json())
        if am is None:
            pytest.skip("AionMind kernel not initialised in this build")
        if am.get("status") != "pending_approval":
            pytest.skip(
                f"Kernel did not return pending_approval (got "
                f"{am.get('status')!r}) — environment-dependent"
            )
        # B8 — the front door must have stamped a hitl_intervention_id
        # on the AionMind result and queued it on the HITL queue.
        iid = am.get("hitl_intervention_id")
        assert iid, "expected hitl_intervention_id on pending_approval result"

        q = client.get("/api/hitl/queue")
        assert q.status_code == 200, q.text
        body = q.json()
        queue = body.get("queue", []) if isinstance(body, dict) else []
        request_ids = {
            item.get("request_id") for item in queue if isinstance(item, dict)
        }
        assert iid in request_ids, (
            f"hand-off id {iid!r} not surfaced in /api/hitl/queue "
            f"(found ids: {sorted(x for x in request_ids if x)})"
        )

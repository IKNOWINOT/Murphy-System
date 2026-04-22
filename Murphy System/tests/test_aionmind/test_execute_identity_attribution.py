"""Phase-1 integration tests for the AionMind front-door wiring.

These tests assert the contract from the plan:
- anonymous request to ``/api/execute`` no longer silently auto-approves;
- a request authenticated as the founder is attributed to that email
  in the AionMind audit trail (no more ``api_auto`` placeholder).

The tests skip cleanly when the optional FastAPI test stack is not
available so the broader suite continues to pass on minimal installs.
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
    # Force the founder email to a known value so seeding is deterministic.
    os.environ["MURPHY_FOUNDER_EMAIL"] = _FOUNDER_EMAIL
    try:
        app = create_app()
    except Exception as exc:  # pragma: no cover - heavy deps absent
        pytest.skip(f"create_app() failed in this environment: {exc}")
    return TestClient(app)


@pytest.fixture(scope="module")
def client():
    with _build_client() as c:
        yield c


def _aionmind_section(payload):
    """Pull the AionMind sub-result out of /api/execute's response."""
    if not isinstance(payload, dict):
        return None
    return payload.get("aionmind") or payload.get("result", {}).get("aionmind")


class TestExecuteIdentityAttribution:
    def test_anonymous_medium_risk_is_not_auto_approved(self, client):
        """Anonymous callers must not silently auto-approve MEDIUM tasks.

        Previously ``/api/execute`` hardcoded ``auto_approve=True`` and
        ``approver="api_auto"``.  The Phase-1 policy gates that behind
        an authenticated owner/admin.  Anonymous traffic must now end
        up with status ``pending_approval`` (or fall through to the
        legacy path with no auto-approved AionMind execution).
        """
        resp = client.post(
            "/api/execute",
            json={
                "task_description": "deploy v2",
                "task_type": "deployment",  # → RiskLevel.MEDIUM in the kernel
            },
        )
        # Endpoint should still return 200 — what matters is the
        # AionMind section did not auto-approve a MEDIUM-risk action
        # for an anonymous caller.
        assert resp.status_code == 200, resp.text
        body = resp.json()
        am = _aionmind_section(body)
        if am is None:
            # Kernel was not present in this build; nothing to assert.
            pytest.skip("AionMind kernel not initialised in this build")
        # Either no candidates (legacy fallback) OR pending approval —
        # but never an executed-by-api_auto state.
        assert am.get("status") != "completed" or am.get("graph", {}).get(
            "approved_by"
        ) != "api_auto"
        if am.get("status") == "pending_approval":
            assert am.get("graph", {}).get("approved") is not True

    def test_founder_request_is_attributed_to_real_email(self, client):
        """Founder header → AionMind sees ``cpost@murphy.systems``.

        Sends ``X-User-ID: cpost@murphy.systems`` (the legacy header
        the RBAC dependency consumes).  The Phase-1 ``_resolve_caller``
        helper resolves that to the founder account so the kernel
        records the real email — not ``api_auto``.
        """
        resp = client.post(
            "/api/execute",
            headers={"X-User-ID": _FOUNDER_EMAIL},
            json={
                "task_description": "diagnostic ping",
                "task_type": "general",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        am = _aionmind_section(body)
        if am is None:
            pytest.skip("AionMind kernel not initialised in this build")
        if am.get("status") == "no_candidates":
            pytest.skip("Kernel has no registered capabilities for this task")
        # The plan's exit criterion: audit trail attributed to cpost.
        audit = am.get("audit_trail") or []
        actors = {
            entry.get("details", {}).get("actor")
            for entry in audit
            if isinstance(entry, dict)
        }
        # api_auto must not appear; the real email should.
        assert "api_auto" not in actors
        if actors and actors != {None}:
            assert _FOUNDER_EMAIL in actors

"""Tests for PSM-003 / PSM-004 — operator-approved launch endpoint + console.

Test profile (one case per status code + invariant):

  401: missing header, wrong token (constant-time compare path).
  422: malformed JSON, schema-invalid body.
  409: RSC veto (records VETOED entry).
  503: orchestrator missing (records FAILED entry); RSC source missing.
  500: orchestrator raises (records FAILED entry).
  202: happy path — REQUESTED + APPROVED + LAUNCHED entries written, in order.
  Console GET 200 with form + table.
  Token unconfigured → 401 even with any header.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform_self_modification import (
    OPERATOR_HEADER,
    OPERATOR_TOKEN_ENV,
    build_router,
)
from src.platform_self_modification.ledger import (
    LedgerEntryKind,
    SelfEditLedger,
)
from src.recursive_stability_controller.lyapunov_monitor import LyapunovMonitor


TOKEN = "test-operator-token-do-not-use-in-prod"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubOrchestrator:
    """Minimum surface the endpoint requires: ``start_cycle(gap_analysis)``."""

    def __init__(self, *, raise_on_start: bool = False):
        self._raise = raise_on_start
        self.calls = []

    def start_cycle(self, gap_analysis=None):
        self.calls.append(gap_analysis)
        if self._raise:
            raise RuntimeError("synthetic orchestrator failure")

        class _Cycle:
            cycle_id = "cycle-stub-0001"

        return _Cycle()


@pytest.fixture(autouse=True)
def _set_token(monkeypatch):
    monkeypatch.setenv(OPERATOR_TOKEN_ENV, TOKEN)
    yield


def _build_app(
    *,
    orchestrator=None,
    lyap_source=None,
    ledger_path,
):
    app = FastAPI()
    app.include_router(
        build_router(
            get_orchestrator=lambda: orchestrator,
            get_lyapunov_source=lambda: lyap_source,
            ledger_path=str(ledger_path),
        )
    )
    return app, SelfEditLedger(ledger_path)


def _stable_monitor() -> LyapunovMonitor:
    m = LyapunovMonitor()
    m.update(recursion_energy=1.0, timestamp=1.0, cycle_id=1)
    m.update(recursion_energy=0.5, timestamp=2.0, cycle_id=2)
    return m


def _unstable_monitor() -> LyapunovMonitor:
    m = LyapunovMonitor()
    m.update(recursion_energy=1.0, timestamp=1.0, cycle_id=1)
    m.update(recursion_energy=2.0, timestamp=2.0, cycle_id=2)
    m.update(recursion_energy=3.0, timestamp=3.0, cycle_id=3)
    return m


def _good_body():
    return {
        "proposal_id": "prop-abc-123",
        "operator_id": "op-corey",
        "justification": "auto-tests for PSM-003",
    }


# ---------------------------------------------------------------------------
# 401 — auth
# ---------------------------------------------------------------------------


def test_401_when_header_missing(tmp_path):
    app, ledger = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch", json=_good_body()
    )
    assert r.status_code == 401
    assert r.json()["error"] == "missing_or_invalid_operator_token"
    # No partial state — REQUESTED was never recorded for an unauth call.
    assert ledger.read_all() == []


def test_401_when_header_wrong(tmp_path):
    app, ledger = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: "wrong"},
    )
    assert r.status_code == 401
    assert ledger.read_all() == []


def test_401_when_token_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv(OPERATOR_TOKEN_ENV, raising=False)
    app, _ = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 422 — bad input
# ---------------------------------------------------------------------------


def test_422_on_missing_field(tmp_path):
    app, _ = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json={"proposal_id": "p"},  # missing operator_id, justification
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_422_on_garbage_json(tmp_path):
    app, _ = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        content=b"not json at all",
        headers={
            OPERATOR_HEADER: TOKEN,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 409 — RSC veto (with mandatory ledger entry)
# ---------------------------------------------------------------------------


def test_409_on_rsc_veto_records_vetoed_entry(tmp_path):
    app, ledger = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_unstable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "rsc_veto"
    assert body["reason"] in {"consecutive_violations", "lyapunov_unstable"}
    assert isinstance(body["ledger_seq"], int)

    kinds = [e.kind for e in ledger.read_all()]
    assert kinds == ["REQUESTED", "VETOED"]
    ok, err = ledger.verify_chain()
    assert ok, err


# ---------------------------------------------------------------------------
# 503 — RSC source / orchestrator missing
# ---------------------------------------------------------------------------


def test_503_when_lyap_source_missing(tmp_path):
    app, ledger = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=None,
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 503
    assert r.json()["error"] == "rsc_unavailable"
    kinds = [e.kind for e in ledger.read_all()]
    assert kinds == ["REQUESTED", "VETOED"]


def test_503_when_orchestrator_missing(tmp_path):
    app, ledger = _build_app(
        orchestrator=None,
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 503
    assert r.json()["error"] == "orchestrator_unavailable"
    kinds = [e.kind for e in ledger.read_all()]
    assert kinds == ["REQUESTED", "FAILED"]


# ---------------------------------------------------------------------------
# 500 — orchestrator raises (with FAILED entry, not silent)
# ---------------------------------------------------------------------------


def test_500_when_orchestrator_raises_records_failed(tmp_path):
    app, ledger = _build_app(
        orchestrator=_StubOrchestrator(raise_on_start=True),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 500
    assert r.json()["error"] == "orchestrator_error"
    kinds = [e.kind for e in ledger.read_all()]
    assert kinds == ["REQUESTED", "APPROVED", "FAILED"]
    ok, err = ledger.verify_chain()
    assert ok, err


# ---------------------------------------------------------------------------
# 202 — happy path
# ---------------------------------------------------------------------------


def test_202_happy_path_writes_full_chain(tmp_path):
    orch = _StubOrchestrator()
    app, ledger = _build_app(
        orchestrator=orch,
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["ok"] is True
    assert body["cycle_id"] == "cycle-stub-0001"
    assert body["proposal_id"] == "prop-abc-123"
    assert isinstance(body["ledger_seq"], int)

    # Orchestrator was called with full provenance.
    assert orch.calls and orch.calls[0]["proposal_id"] == "prop-abc-123"
    assert orch.calls[0]["source"] == "platform_self_modification"

    kinds = [e.kind for e in ledger.read_all()]
    assert kinds == ["REQUESTED", "APPROVED", "LAUNCHED"]
    ok, err = ledger.verify_chain()
    assert ok, err


# ---------------------------------------------------------------------------
# GET /ledger
# ---------------------------------------------------------------------------


def test_ledger_endpoint_returns_recent_entries(tmp_path):
    orch = _StubOrchestrator()
    app, _ = _build_app(
        orchestrator=orch,
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    client = TestClient(app)
    client.post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )
    r = client.get("/api/platform/self-modification/ledger")
    assert r.status_code == 200
    body = r.json()
    assert body["chain_verified"] is True
    assert body["count"] == 3
    assert [e["kind"] for e in body["entries"]] == ["REQUESTED", "APPROVED", "LAUNCHED"]


# ---------------------------------------------------------------------------
# PSM-004 — console
# ---------------------------------------------------------------------------


def test_console_renders_form_and_recent_entries(tmp_path):
    orch = _StubOrchestrator()
    app, _ = _build_app(
        orchestrator=orch,
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    client = TestClient(app)
    client.post(
        "/api/platform/self-modification/launch",
        json=_good_body(),
        headers={OPERATOR_HEADER: TOKEN},
    )

    r = client.get("/api/platform/self-modification/console")
    assert r.status_code == 200
    html = r.text
    assert '<form method="post" action="/api/platform/self-modification/launch"' in html
    assert "prop-abc-123" in html
    assert "LAUNCHED" in html
    assert OPERATOR_HEADER in html
    assert "Operator token" in html


def test_console_warns_when_lyap_missing(tmp_path):
    app, _ = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=None,
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).get("/api/platform/self-modification/console")
    assert r.status_code == 200
    assert "RSC/Lyapunov source not wired" in r.text


def test_console_warns_when_token_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv(OPERATOR_TOKEN_ENV, raising=False)
    app, _ = _build_app(
        orchestrator=_StubOrchestrator(),
        lyap_source=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl",
    )
    r = TestClient(app).get("/api/platform/self-modification/console")
    assert r.status_code == 200
    assert "NOT CONFIGURED" in r.text

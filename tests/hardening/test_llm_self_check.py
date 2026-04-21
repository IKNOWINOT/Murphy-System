# Copyright 2020 Inoni LLC — BSL 1.1
"""
Tests for src/llm_self_check.py — label LLM-SELFCHECK-001.

Uses a stub provider (no real network) to walk every status branch:
  ok / degraded(onboard fallback with key) / schema_failure /
  verification_failed / config_error / unavailable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

import pytest

from src.llm_self_check import SelfCheckResult, _validate_schema, run_self_check


# ---------------------------------------------------------------------------
# Stub provider — mimics MurphyLLMProvider.complete()'s shape.
# ---------------------------------------------------------------------------

@dataclass
class _StubResult:
    success: bool
    content: str
    provider: str
    model: str = "stub-model"


class _StubLLM:
    """Returns scripted responses in order so tests can drive each branch."""

    def __init__(self, scripted: List[_StubResult]) -> None:
        self._scripted = list(scripted)
        self.calls: List[str] = []

    def complete(self, prompt, *, system="", model_hint="chat",
                 temperature=0.7, max_tokens=300):
        self.calls.append(prompt)
        if not self._scripted:
            raise RuntimeError("stub exhausted")
        return self._scripted.pop(0)


def _good_payload() -> str:
    return json.dumps({
        "name": "Daily summary email",
        "description": "Send a recap of the prior day's metrics every morning at 9am.",
        "steps": ["pull metrics", "format report", "send email"],
    })


def _verifier_yes() -> str:
    return json.dumps({"valid": True})


def _verifier_no() -> str:
    return json.dumps({"valid": False, "reason": "missing fields"})


# ---------------------------------------------------------------------------
# Schema validator — direct unit tests
# ---------------------------------------------------------------------------

def test_schema_accepts_well_formed():
    assert _validate_schema(json.loads(_good_payload())) == []


def test_schema_rejects_missing_steps():
    bad = {"name": "x", "description": "long enough description here", "steps": []}
    assert "'steps' must be a non-empty array" in _validate_schema(bad)


def test_schema_rejects_non_object():
    assert _validate_schema("hello") == ["top-level value is str, expected object"]


def test_schema_rejects_short_description():
    bad = {"name": "x", "description": "short", "steps": ["a"]}
    violations = _validate_schema(bad)
    assert any("description" in v for v in violations)


# ---------------------------------------------------------------------------
# run_self_check — happy path
# ---------------------------------------------------------------------------

def test_ok_when_deepinfra_answers_and_verifier_agrees(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    stub = _StubLLM([
        _StubResult(True, _good_payload(), "deepinfra"),
        _StubResult(True, _verifier_yes(), "deepinfra"),
    ])
    result = run_self_check(lambda: stub)
    assert result.status == "ok"
    assert result.provider == "deepinfra"
    assert result.verified is True
    assert result.retry_count == 0
    assert result.error_category is None
    assert result.generated_payload is not None
    assert result.correlation_id  # non-empty UUID hex


# ---------------------------------------------------------------------------
# THE key signal the user asked for: provider=onboard while a key is set
# ---------------------------------------------------------------------------

def test_degraded_when_onboard_used_but_api_key_set(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "sk-fake")
    stub = _StubLLM([
        _StubResult(True, _good_payload(), "onboard"),
        _StubResult(True, _verifier_yes(), "onboard"),
    ])
    result = run_self_check(lambda: stub)
    assert result.status == "degraded"
    assert result.provider == "onboard"
    assert result.error_category == "network"
    assert "API key is configured" in (result.last_error or "")


def test_ok_when_onboard_used_and_no_key_set(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    stub = _StubLLM([
        _StubResult(True, _good_payload(), "onboard"),
        _StubResult(True, _verifier_yes(), "onboard"),
    ])
    result = run_self_check(lambda: stub)
    # No keys configured → onboard is the legitimate provider, not degraded.
    assert result.status == "ok"
    assert result.provider == "onboard"


# ---------------------------------------------------------------------------
# Retry-with-reinforcement on schema failure (best-practices §2)
# ---------------------------------------------------------------------------

def test_retry_recovers_from_initial_malformed_json(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    stub = _StubLLM([
        _StubResult(True, "this is not json at all", "deepinfra"),
        _StubResult(True, _good_payload(), "deepinfra"),
        _StubResult(True, _verifier_yes(), "deepinfra"),
    ])
    result = run_self_check(lambda: stub)
    assert result.status == "ok"
    assert result.retry_count == 1


def test_schema_failure_after_retry(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    stub = _StubLLM([
        _StubResult(True, "still garbage", "deepinfra"),
        _StubResult(True, "still garbage round 2", "deepinfra"),
    ])
    result = run_self_check(lambda: stub)
    assert result.status == "schema_failure"
    assert result.error_category == "schema"
    assert result.retry_count == 1
    assert result.verified is False


# ---------------------------------------------------------------------------
# Verification failure — generation valid but verifier disagrees
# ---------------------------------------------------------------------------

def test_verification_failed_when_verifier_says_no(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    stub = _StubLLM([
        _StubResult(True, _good_payload(), "deepinfra"),
        _StubResult(True, _verifier_no(), "deepinfra"),
    ])
    result = run_self_check(lambda: stub)
    assert result.status == "verification_failed"
    assert result.verified is False
    assert result.error_category == "content"
    assert result.generated_payload is not None
    assert result.verifier_payload == {"valid": False, "reason": "missing fields"}


# ---------------------------------------------------------------------------
# Failure / boundary conditions — module must NEVER raise
# ---------------------------------------------------------------------------

def test_unavailable_when_get_llm_is_none():
    result = run_self_check(None)
    assert result.status == "unavailable"
    assert result.provider is None
    assert result.error_category == "config"


def test_config_error_when_get_llm_raises():
    def boom():
        raise RuntimeError("import failed")
    result = run_self_check(boom)
    assert result.status == "config_error"
    assert result.error_category == "config"
    assert "import failed" in (result.last_error or "")


def test_degraded_when_provider_raises_network_error(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)

    class _Boom:
        def complete(self, *a, **kw):
            raise ConnectionError("Connection refused to api.deepinfra.com")

    result = run_self_check(lambda: _Boom())
    assert result.status == "degraded"
    assert result.error_category == "network"
    assert "Connection refused" in (result.last_error or "")


def test_result_to_dict_is_json_serialisable():
    r = SelfCheckResult(
        status="ok", provider="deepinfra", model="m", latency_ms=1,
        retry_count=0, verified=True, correlation_id="cid",
    )
    payload = r.to_dict()
    # Must round-trip through json without TypeError.
    assert json.loads(json.dumps(payload))["status"] == "ok"

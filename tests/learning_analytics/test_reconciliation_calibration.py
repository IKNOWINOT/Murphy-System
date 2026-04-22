"""
Calibration regression tests — encode the lessons from the eval-harness
sweep so future changes to the standards catalog cannot silently
re-introduce the gaps we already fixed.

Each test is named for the calibration scenario it locks in.
"""

from __future__ import annotations

from src.reconciliation import (
    Deliverable,
    DeliverableType,
    IntentExtractor,
    OutputEvaluator,
    Request,
)
from src.reconciliation.evaluators.text import check_text_substance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evaluate(text: str, dtype: DeliverableType, content, metadata=None):
    req = Request(text=text, deliverable_type=dtype)
    intent = IntentExtractor().extract(req)[0]
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=dtype,
        content=content,
        metadata=metadata or {},
    )
    return OutputEvaluator().score(dlv, intent)


# ---------------------------------------------------------------------------
# Type-aware substance check (text + structured payloads)
# ---------------------------------------------------------------------------


def test_substance_check_passes_long_string() -> None:
    ok, score, _ = check_text_substance("This is a substantive sentence with enough content.")
    assert ok and score == 1.0


def test_substance_check_rejects_single_token_string() -> None:
    ok, _, detail = check_text_substance("ok")
    assert not ok
    assert "too short" in detail


def test_substance_check_rejects_whitespace_only() -> None:
    ok, _, _ = check_text_substance("   \n\t")
    assert not ok


def test_substance_check_handles_dict_content() -> None:
    ok, _, detail = check_text_substance({"a": 1, "b": 2})
    assert ok
    assert "dict" in detail


def test_substance_check_rejects_empty_dict() -> None:
    ok, _, detail = check_text_substance({})
    assert not ok
    assert "empty" in detail


def test_substance_check_rejects_none() -> None:
    ok, _, _ = check_text_substance(None)
    assert not ok


# ---------------------------------------------------------------------------
# Generic text — single-token outputs must fail (was a calibration gap)
# ---------------------------------------------------------------------------


def test_generic_text_single_token_is_flagged() -> None:
    score = _evaluate("Summarise the incident", DeliverableType.GENERIC_TEXT, "ok")
    assert not score.acceptable
    assert any("too short" in d.summary or "substantive" in d.summary.lower()
               for d in score.diagnoses)


def test_generic_text_two_words_below_floor_is_flagged() -> None:
    score = _evaluate("Summarise the incident", DeliverableType.GENERIC_TEXT, "ok done")
    # 7 chars < 12 char floor → still flagged.
    assert not score.acceptable


def test_generic_text_substantive_passes() -> None:
    score = _evaluate(
        "Summarise the incident",
        DeliverableType.GENERIC_TEXT,
        "Auth service returned 500s for twelve minutes due to a stale signing key.",
    )
    assert score.acceptable


# ---------------------------------------------------------------------------
# Bare except — must hard-fail under above-average code (was a calibration gap)
# ---------------------------------------------------------------------------


def test_bare_except_hard_fails_python_code() -> None:
    code = (
        '"""mod."""\n'
        'import json\n\n\n'
        'def load(path):\n'
        '    """Load."""\n'
        '    try:\n'
        '        with open(path) as f:\n'
        '            return json.load(f)\n'
        '    except:\n'
        '        return None\n'
    )
    score = _evaluate("Write a JSON loader", DeliverableType.CODE, code)
    assert not score.hard_pass
    assert any("CODE-004" in d.summary or "bare 'except:'" in d.summary.lower()
               for d in score.diagnoses)


def test_specific_except_does_not_trigger_code_004() -> None:
    code = (
        '"""mod."""\n'
        'import json\n\n\n'
        'def load(path):\n'
        '    """Load."""\n'
        '    try:\n'
        '        with open(path) as f:\n'
        '            return json.load(f)\n'
        '    except (OSError, json.JSONDecodeError):\n'
        '        return None\n'
    )
    score = _evaluate("Write a JSON loader", DeliverableType.CODE, code)
    assert score.acceptable
    assert not any("CODE-004" in d.summary for d in score.diagnoses)


# ---------------------------------------------------------------------------
# Structured-payload evaluators (JSON_PAYLOAD, DEPLOYMENT_RESULT) — were
# previously falling through to the text evaluator and rejecting dicts
# ---------------------------------------------------------------------------


def test_json_payload_dict_input_passes() -> None:
    score = _evaluate(
        "Build the response",
        DeliverableType.JSON_PAYLOAD,
        {"status": "ok", "data": [1, 2, 3]},
    )
    assert score.acceptable


def test_json_payload_empty_dict_is_flagged() -> None:
    score = _evaluate("Build the response", DeliverableType.JSON_PAYLOAD, {})
    assert not score.hard_pass


def test_json_payload_invalid_string_is_flagged() -> None:
    score = _evaluate(
        "Build the response",
        DeliverableType.JSON_PAYLOAD,
        '{"trailing": 1,}',
    )
    assert not score.hard_pass


def test_deployment_result_healthy_passes() -> None:
    score = _evaluate(
        "Deploy to staging",
        DeliverableType.DEPLOYMENT_RESULT,
        {"health": {"status": "ok"}, "url": "https://staging"},
    )
    assert score.acceptable


def test_deployment_result_unhealthy_is_flagged() -> None:
    score = _evaluate(
        "Deploy to staging",
        DeliverableType.DEPLOYMENT_RESULT,
        {"health": {"status": "down"}},
    )
    assert not score.hard_pass


def test_deployment_result_missing_health_is_flagged() -> None:
    score = _evaluate(
        "Deploy to staging",
        DeliverableType.DEPLOYMENT_RESULT,
        {"url": "https://staging"},
    )
    assert not score.hard_pass


# ---------------------------------------------------------------------------
# Above-average defaults — tests that lock in the strict-not-mediocre bar
# ---------------------------------------------------------------------------


def test_bash_without_strict_mode_is_below_above_average_bar() -> None:
    """A bash script without `set -euo pipefail` must not clear the
    above-average acceptance bar even though it has a shebang."""
    score = _evaluate(
        "Write a backup script",
        DeliverableType.SHELL_SCRIPT,
        "#!/bin/bash\n\necho backing up\ntar czf backup.tgz /data\n",
    )
    assert not score.acceptable


def test_document_without_h1_is_below_above_average_bar() -> None:
    """A document without a top-level heading must not clear the
    above-average acceptance bar."""
    score = _evaluate(
        "Write a quickstart",
        DeliverableType.DOCUMENT,
        "Just install the package and run it. It works out of the box.\n" * 5,
    )
    assert not score.acceptable


def test_plan_without_enumerated_steps_is_below_above_average_bar() -> None:
    score = _evaluate(
        "Plan the rollout",
        DeliverableType.PLAN,
        "# Rollout\n\nWe will roll this out gradually starting with internal users.\n",
    )
    assert not score.acceptable

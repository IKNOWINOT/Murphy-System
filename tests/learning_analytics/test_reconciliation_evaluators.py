"""
Tests for the per-deliverable-type evaluators and the top-level
:class:`OutputEvaluator`.  Each evaluator covers a distinct deliverable
type — code, config/shell, document, mailbox provisioning, generic
text — to enforce that the subsystem is genuinely deliverable-type-agnostic.
"""

from __future__ import annotations

from src.reconciliation import (
    Deliverable,
    DeliverableType,
    IntentExtractor,
    OutputEvaluator,
    Request,
)
from src.reconciliation.evaluators import (
    EvaluationContext,
    get_evaluator,
    list_evaluators,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _intent_for(req_text: str, dtype: DeliverableType):
    req = Request(text=req_text, deliverable_type=dtype)
    return req, IntentExtractor().extract(req)[0]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_covers_all_seeded_deliverable_types() -> None:
    registered = set(list_evaluators().keys())
    for dtype in (
        DeliverableType.CODE,
        DeliverableType.CONFIG_FILE,
        DeliverableType.SHELL_SCRIPT,
        DeliverableType.DOCUMENT,
        DeliverableType.PLAN,
        DeliverableType.DASHBOARD,
        DeliverableType.MAILBOX_PROVISIONING,
        DeliverableType.GENERIC_TEXT,
        DeliverableType.OTHER,
        DeliverableType.WORKFLOW,
    ):
        assert dtype in registered, f"missing evaluator for {dtype}"


def test_get_evaluator_falls_back_for_unregistered_type() -> None:
    # JSON_PAYLOAD has no dedicated evaluator — must fall back, never raise.
    ev = get_evaluator(DeliverableType.JSON_PAYLOAD)
    assert ev is not None


# ---------------------------------------------------------------------------
# CODE
# ---------------------------------------------------------------------------


def test_code_evaluator_passes_clean_python() -> None:
    req, intent = _intent_for("Write a clean function", DeliverableType.CODE)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.CODE,
        content='"""mod."""\n\ndef add(a, b):\n    """sum"""\n    return a + b\n',
    )
    score = OutputEvaluator().score(dlv, intent)
    assert score.hard_pass
    assert score.soft_score >= 0.85


def test_code_evaluator_reports_syntax_error_as_blocker() -> None:
    req, intent = _intent_for("Write a function", DeliverableType.CODE)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.CODE,
        content="def broken(:\n",
    )
    score = OutputEvaluator().score(dlv, intent)
    assert not score.hard_pass
    assert any("syntax" in d.summary.lower() or "CODE-003" in d.summary for d in score.diagnoses)


def test_code_evaluator_flags_bare_except_and_missing_docstring() -> None:
    req, intent = _intent_for("Write a function", DeliverableType.CODE)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.CODE,
        content=(
            'def public_no_doc():\n'
            '    try:\n'
            '        x = 1\n'
            '    except:\n'
            '        pass\n'
        ),
    )
    score = OutputEvaluator().score(dlv, intent)
    summaries = " | ".join(d.summary for d in score.diagnoses)
    assert "Bare 'except:'" in summaries
    assert "lacks a docstring" in summaries


# ---------------------------------------------------------------------------
# CONFIG / SHELL
# ---------------------------------------------------------------------------


def test_config_evaluator_blocks_plaintext_secret() -> None:
    req, intent = _intent_for("Write a config file", DeliverableType.CONFIG_FILE)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.CONFIG_FILE,
        content="# header comment\npassword: SuperSecretValue123\n",
    )
    score = OutputEvaluator().score(dlv, intent)
    assert not score.hard_pass
    assert any("CONFIG-001" in d.summary for d in score.diagnoses)


def test_shell_script_evaluator_requires_shebang() -> None:
    req, intent = _intent_for("Write a shell script", DeliverableType.SHELL_SCRIPT)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.SHELL_SCRIPT,
        content="echo hi\n",
    )
    score = OutputEvaluator().score(dlv, intent)
    # Shebang is hard-required.
    assert not score.hard_pass


def test_shell_script_evaluator_passes_strict_mode_script() -> None:
    req, intent = _intent_for("Write a shell script", DeliverableType.SHELL_SCRIPT)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.SHELL_SCRIPT,
        content="#!/usr/bin/env bash\nset -euo pipefail\necho hi\n",
    )
    score = OutputEvaluator().score(dlv, intent)
    assert score.hard_pass


def test_config_evaluator_reports_bad_yaml_when_pyyaml_available() -> None:
    pytest_yaml = __import__("importlib").util.find_spec("yaml")
    if pytest_yaml is None:  # pragma: no cover — exercised only when pyyaml is present
        return
    req, intent = _intent_for("Write a yaml config", DeliverableType.CONFIG_FILE)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.CONFIG_FILE,
        content="# header\nfoo: [unterminated\n",
        metadata={"extension": ".yaml"},
    )
    score = OutputEvaluator().score(dlv, intent)
    assert any("YAML failed to parse" in d.summary for d in score.diagnoses)


# ---------------------------------------------------------------------------
# DOCUMENT
# ---------------------------------------------------------------------------


def test_document_evaluator_reports_heading_jump() -> None:
    req, intent = _intent_for("Write a doc", DeliverableType.DOCUMENT)
    body = "# Title\n\nbody text " * 12 + "\n\n### Skipped H2\n\nmore body\n"
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.DOCUMENT,
        content=body,
    )
    score = OutputEvaluator().score(dlv, intent)
    assert any("Heading depth jumps" in d.summary for d in score.diagnoses)


def test_document_evaluator_passes_well_structured_doc() -> None:
    req, intent = _intent_for("Write a doc", DeliverableType.DOCUMENT)
    body = (
        "# Title\n\n"
        + "This is a substantive document body that exceeds the minimum length.\n\n"
        + "## Section\n\n"
        + "More content goes here to satisfy the substance floor.\n"
    )
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.DOCUMENT,
        content=body,
    )
    score = OutputEvaluator().score(dlv, intent)
    assert score.hard_pass


# ---------------------------------------------------------------------------
# MAILBOX PROVISIONING (non-code deliverable)
# ---------------------------------------------------------------------------


def test_mailbox_evaluator_passes_clean_provisioning() -> None:
    req, intent = _intent_for(
        "Provision team mailboxes",
        DeliverableType.MAILBOX_PROVISIONING,
    )
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
        content={
            "accounts": [
                {"email": "a@x", "password": "p1", "status": "created"},
                {"email": "b@x", "password": "p2", "status": "existed"},
            ],
        },
    )
    score = OutputEvaluator().score(dlv, intent)
    assert score.hard_pass


def test_mailbox_evaluator_blocks_when_password_missing() -> None:
    req, intent = _intent_for(
        "Provision team mailboxes",
        DeliverableType.MAILBOX_PROVISIONING,
    )
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
        content={
            "accounts": [
                {"email": "a@x", "password": None, "status": "existed"},
            ],
        },
    )
    score = OutputEvaluator().score(dlv, intent)
    assert not score.hard_pass
    assert any("no recorded password" in d.summary for d in score.diagnoses)


def test_mailbox_evaluator_reports_per_account_failure() -> None:
    req, intent = _intent_for(
        "Provision team mailboxes",
        DeliverableType.MAILBOX_PROVISIONING,
    )
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
        content={
            "accounts": [
                {"email": "a@x", "password": "p", "status": "created"},
                {"email": "b@x", "status": "failed", "error": "domain unknown"},
            ],
        },
    )
    score = OutputEvaluator().score(dlv, intent)
    assert not score.hard_pass
    assert any("failed for b@x" in d.summary for d in score.diagnoses)


# ---------------------------------------------------------------------------
# Generic text + LLM-judge integration via context
# ---------------------------------------------------------------------------


def test_generic_text_evaluator_blocks_empty_content() -> None:
    req, intent = _intent_for("Write something", DeliverableType.GENERIC_TEXT)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.GENERIC_TEXT,
        content="",
    )
    score = OutputEvaluator().score(dlv, intent)
    assert not score.hard_pass


def test_llm_judge_score_is_clamped_and_used() -> None:
    """When a judge is configured, its score participates in aggregation."""

    captured: list[str] = []

    def judge(rubric: str, content):  # noqa: ARG001
        captured.append(rubric)
        return (1.5, "exceeds")  # deliberately out of range — must be clamped

    req, intent = _intent_for("Write something useful", DeliverableType.GENERIC_TEXT)
    dlv = Deliverable(
        request_id=req.id,
        deliverable_type=DeliverableType.GENERIC_TEXT,
        content="hello world, this is a useful sentence",
    )
    ev = OutputEvaluator(EvaluationContext(llm_judge=judge))
    score = ev.score(dlv, intent)
    assert captured, "judge was not invoked"
    # All criterion scores must remain in [0, 1].
    assert all(0.0 <= r.score <= 1.0 for r in score.per_criterion)

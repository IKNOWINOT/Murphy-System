"""
Tests for the standards catalog — registration, lookup, callable
checks, and the declarative ``evaluate_check`` primitive.
"""

from __future__ import annotations

import pytest

from src.reconciliation import DeliverableType, Standard, default_catalog
from src.reconciliation.standards import (
    StandardsCatalog,
    check_deployment_healthy,
    check_json_parses,
    check_mailbox_no_hard_failures,
    check_mailbox_passwords_recorded,
    check_python_syntax,
    evaluate_check,
    register_standard,
    resolve_callable_check,
)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def test_default_catalog_seeds_multiple_deliverable_types() -> None:
    cat = default_catalog()
    types_seen = {std.deliverable_type for std in cat.all()}
    # Must cover non-code deliverables as well as code.
    assert DeliverableType.CODE in types_seen
    assert DeliverableType.DOCUMENT in types_seen
    assert DeliverableType.MAILBOX_PROVISIONING in types_seen
    assert DeliverableType.SHELL_SCRIPT in types_seen


def test_register_and_lookup_custom_standard() -> None:
    cat = StandardsCatalog()
    s = Standard(
        id="TEST-001",
        deliverable_type=DeliverableType.PLAN,
        title="t",
        rationale="r",
        check={"kind": "regex", "pattern": "x"},
    )
    cat.register(s)
    assert cat.get("TEST-001") is s
    assert cat.for_type(DeliverableType.PLAN) == [s]


def test_for_type_filters_by_tags() -> None:
    cat = StandardsCatalog()
    cat.register(Standard(id="A", deliverable_type=DeliverableType.CODE,
                          title="a", rationale="r", check={"kind": "regex", "pattern": "x"},
                          tags=("hygiene",)))
    cat.register(Standard(id="B", deliverable_type=DeliverableType.CODE,
                          title="b", rationale="r", check={"kind": "regex", "pattern": "x"},
                          tags=("security",)))
    matched = cat.for_type(DeliverableType.CODE, tags={"security"})
    assert [s.id for s in matched] == ["B"]


def test_register_standard_module_level_helper() -> None:
    s = Standard(
        id="MODLEVEL-001",
        deliverable_type=DeliverableType.OTHER,
        title="t",
        rationale="r",
        check={"kind": "regex", "pattern": "x"},
    )
    register_standard(s)
    assert default_catalog().get("MODLEVEL-001") is s


# ---------------------------------------------------------------------------
# evaluate_check primitives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec, content, expected_ok",
    [
        ({"kind": "regex", "pattern": r"hello"}, "hello world", True),
        ({"kind": "regex", "pattern": r"^foo$"}, "bar", False),
        ({"kind": "regex_absent", "pattern": r"TODO"}, "all done", True),
        ({"kind": "regex_absent", "pattern": r"TODO"}, "TODO: fix", False),
        ({"kind": "min_length", "value": 5}, "hello world", True),
        ({"kind": "min_length", "value": 50}, "short", False),
        ({"kind": "max_length", "value": 5}, "ok", True),
        ({"kind": "max_length", "value": 3}, "way too long", False),
    ],
)
def test_evaluate_check_basic_kinds(spec: dict, content, expected_ok: bool) -> None:
    ok, score, _ = evaluate_check(spec, content)
    assert ok is expected_ok
    if expected_ok:
        assert 0.0 <= score <= 1.0


def test_evaluate_check_unknown_kind_skips_softly() -> None:
    ok, score, detail = evaluate_check({"kind": "what_is_this"}, "x")
    assert ok is True
    assert score == 1.0
    assert "skipped" in detail


def test_evaluate_check_invalid_regex_returns_failure() -> None:
    ok, score, detail = evaluate_check({"kind": "regex", "pattern": "([unclosed"}, "x")
    assert ok is False
    assert "invalid regex" in detail


# ---------------------------------------------------------------------------
# Callable checks
# ---------------------------------------------------------------------------


def test_check_python_syntax_pass_and_fail() -> None:
    assert check_python_syntax("def f(): return 1")[0] is True
    assert check_python_syntax("def f(:")[0] is False
    assert check_python_syntax(123)[0] is False


def test_check_json_parses() -> None:
    assert check_json_parses('{"a": 1}')[0] is True
    assert check_json_parses({"a": 1})[0] is True
    assert check_json_parses("not json")[0] is False
    assert check_json_parses(42)[0] is False


def test_check_mailbox_passwords_recorded() -> None:
    ok, score, _ = check_mailbox_passwords_recorded(
        {"accounts": [{"email": "a", "password": "p"}, {"email": "b", "password": "q"}]}
    )
    assert ok and score == 1.0

    ok, score, detail = check_mailbox_passwords_recorded(
        {"accounts": [{"email": "a", "password": None}, {"email": "b", "password": "q"}]}
    )
    assert not ok and 0 < score < 1
    assert "missing password" in detail


def test_check_mailbox_no_hard_failures() -> None:
    ok, _, _ = check_mailbox_no_hard_failures(
        {"accounts": [{"email": "a", "status": "created"}]}
    )
    assert ok
    ok, _, detail = check_mailbox_no_hard_failures(
        {"accounts": [{"email": "a", "status": "failed", "error": "boom"}]}
    )
    assert not ok and "failed" in detail


def test_check_deployment_healthy() -> None:
    assert check_deployment_healthy({"health": {"status": "ok"}})[0]
    assert check_deployment_healthy({"health": "healthy"})[0]
    assert not check_deployment_healthy({"health": "down"})[0]
    assert not check_deployment_healthy({})[0]


def test_resolve_callable_check_known_and_unknown() -> None:
    assert resolve_callable_check(
        "src.reconciliation.standards:check_python_syntax"
    ) is check_python_syntax
    assert resolve_callable_check("not_a_module:nope") is None
    assert resolve_callable_check("nofunc") is None


def test_evaluate_check_callable_dispatches_to_registry() -> None:
    spec = {"kind": "callable", "fn": "src.reconciliation.standards:check_python_syntax"}
    ok, _, _ = evaluate_check(spec, "x = 1")
    assert ok is True
    ok, _, _ = evaluate_check(spec, "def f(:")
    assert ok is False


def test_standard_to_criterion_round_trip() -> None:
    s = Standard(
        id="X-001",
        deliverable_type=DeliverableType.CODE,
        title="t",
        rationale="r",
        check={"kind": "regex", "pattern": "x"},
        weight=2.0,
        hard=True,
    )
    crit = s.to_criterion()
    assert crit.weight == 2.0
    assert crit.hard is True
    assert crit.check_spec["standard_id"] == "X-001"

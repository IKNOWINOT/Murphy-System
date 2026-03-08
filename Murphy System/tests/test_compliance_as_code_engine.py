# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for compliance_as_code_engine — CCE-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable CCERecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from compliance_as_code_engine import (  # noqa: E402
    CheckResult,
    ComplianceAsCodeEngine,
    ComplianceReport,
    ComplianceRule,
    ComplianceScan,
    ComplianceStatus,
    Framework,
    RemediationAction,
    RuleSeverity,
    RuleStatus,
    create_compliance_api,
    gate_cce_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class CCERecord:
    """One CCE check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[CCERecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        CCERecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Helpers ---------------------------------------------------------------


def _make_engine() -> ComplianceAsCodeEngine:
    return ComplianceAsCodeEngine(max_rules=500, max_executions=500)


def _add_rule(
    eng: ComplianceAsCodeEngine,
    name: str = "enc-check",
    expression: str = "encryption_enabled == True",
    framework: str = "soc2",
    severity: str = "high",
) -> ComplianceRule:
    return eng.create_rule(
        name=name,
        description=f"Test rule: {name}",
        framework=framework,
        severity=severity,
        expression=expression,
        remediation=f"Fix {name}",
    )


# ==========================================================================
# Tests
# ==========================================================================


class TestRuleCRUD:
    """Rule creation, retrieval, update, deletion."""

    def test_create_rule(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        record(
            "CCE-001", "create_rule returns ComplianceRule",
            True, isinstance(rule, ComplianceRule),
            cause="create_rule called",
            effect="ComplianceRule returned",
            lesson="Factory must return typed rule",
        )
        assert rule.name == "enc-check"

    def test_create_rule_defaults(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, "test-rule")
        record(
            "CCE-002", "rule has active status by default",
            "active", rule.status,
            cause="no status specified",
            effect="defaults to active",
            lesson="New rules start active",
        )

    def test_create_rule_enum_framework(self) -> None:
        eng = _make_engine()
        rule = eng.create_rule(
            "gdpr-check", "GDPR test", Framework.gdpr, "high",
            "consent_obtained == True", "Obtain consent",
        )
        record(
            "CCE-003", "enum Framework coerced to string",
            "gdpr", rule.framework,
            cause="Framework enum passed",
            effect="stored as string",
            lesson="Enum coercion must work",
        )

    def test_get_rule(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        got = eng.get_rule(rule.id)
        record(
            "CCE-004", "get_rule returns correct rule",
            rule.id, got.id if got else None,
            cause="get by ID",
            effect="same rule returned",
            lesson="Lookup must work",
        )

    def test_get_rule_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_rule("nonexistent")
        record(
            "CCE-005", "get_rule returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing rules return None",
        )

    def test_list_rules(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1", framework="soc2")
        _add_rule(eng, "r2", framework="gdpr")
        _add_rule(eng, "r3", framework="soc2")
        rules = eng.list_rules(framework="soc2")
        record(
            "CCE-006", "list_rules filters by framework",
            2, len(rules),
            cause="2 soc2 rules, 1 gdpr",
            effect="2 returned for soc2",
            lesson="Framework filter must work",
        )

    def test_list_rules_severity(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1", severity="high")
        _add_rule(eng, "r2", severity="low")
        rules = eng.list_rules(severity="high")
        record(
            "CCE-007", "list_rules filters by severity",
            1, len(rules),
            cause="1 high rule",
            effect="1 returned",
            lesson="Severity filter must work",
        )

    def test_list_rules_limit(self) -> None:
        eng = _make_engine()
        for i in range(20):
            _add_rule(eng, f"r{i}")
        rules = eng.list_rules(limit=5)
        record(
            "CCE-008", "list_rules respects limit",
            5, len(rules),
            cause="20 rules, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_update_rule_status(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        updated = eng.update_rule(rule.id, status="disabled")
        record(
            "CCE-009", "update_rule changes status",
            "disabled", updated.status if updated else None,
            cause="status changed to disabled",
            effect="status updated",
            lesson="Status updates must persist",
        )

    def test_update_rule_expression(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        updated = eng.update_rule(rule.id, expression="key_length >= 256")
        record(
            "CCE-010", "update_rule changes expression",
            "key_length >= 256", updated.expression if updated else None,
            cause="expression changed",
            effect="expression updated",
            lesson="Expression updates must persist",
        )

    def test_update_rule_missing(self) -> None:
        eng = _make_engine()
        result = eng.update_rule("missing")
        record(
            "CCE-011", "update_rule returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing rules cannot be updated",
        )

    def test_delete_rule(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        ok = eng.delete_rule(rule.id)
        record(
            "CCE-012", "delete_rule returns True",
            True, ok,
            cause="valid rule deleted",
            effect="True returned",
            lesson="Delete must succeed for existing rules",
        )
        assert eng.get_rule(rule.id) is None

    def test_delete_rule_missing(self) -> None:
        eng = _make_engine()
        ok = eng.delete_rule("nonexistent")
        record(
            "CCE-013", "delete_rule returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Delete of missing returns False",
        )

    def test_rule_id_unique(self) -> None:
        eng = _make_engine()
        r1 = _add_rule(eng, "r1")
        r2 = _add_rule(eng, "r2")
        record(
            "CCE-014", "rule IDs are unique",
            True, r1.id != r2.id,
            cause="two rules created",
            effect="different IDs",
            lesson="UUID generation must be unique",
        )

    def test_rule_serialization(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        d = rule.to_dict()
        record(
            "CCE-015", "to_dict has all fields",
            True, "id" in d and "name" in d and "expression" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_list_rules_status_filter(self) -> None:
        eng = _make_engine()
        r1 = _add_rule(eng, "r1")
        r2 = _add_rule(eng, "r2")
        eng.update_rule(r2.id, status="disabled")
        rules = eng.list_rules(status="active")
        record(
            "CCE-016", "list_rules filters by status",
            1, len(rules),
            cause="1 active, 1 disabled",
            effect="1 returned",
            lesson="Status filter must work",
        )


class TestRuleChecking:
    """Individual rule evaluation."""

    def test_check_rule_pass(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="encryption_enabled == True")
        check = eng.check_rule(rule.id, {"encryption_enabled": True})
        record(
            "CCE-017", "rule check passes when expression is True",
            "pass", check.result,
            cause="encryption_enabled=True",
            effect="result=pass",
            lesson="True expression must pass",
        )

    def test_check_rule_fail(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="encryption_enabled == True")
        check = eng.check_rule(rule.id, {"encryption_enabled": False})
        record(
            "CCE-018", "rule check fails when expression is False",
            "fail", check.result,
            cause="encryption_enabled=False",
            effect="result=fail",
            lesson="False expression must fail",
        )

    def test_check_rule_error(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="undefined_var == True")
        check = eng.check_rule(rule.id, {})
        record(
            "CCE-019", "rule check errors on missing variable",
            "error", check.result,
            cause="undefined_var not in context",
            effect="result=error",
            lesson="Missing vars must error gracefully",
        )

    def test_check_rule_missing_rule(self) -> None:
        eng = _make_engine()
        check = eng.check_rule("nonexistent", {})
        record(
            "CCE-020", "check missing rule returns error",
            "error", check.result,
            cause="invalid rule_id",
            effect="result=error",
            lesson="Missing rules must error gracefully",
        )

    def test_check_rule_comparison(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="key_length >= 256")
        check = eng.check_rule(rule.id, {"key_length": 512})
        record(
            "CCE-021", "comparison expression works",
            "pass", check.result,
            cause="key_length=512 >= 256",
            effect="result=pass",
            lesson="Numeric comparisons must work",
        )

    def test_check_rule_boolean_and(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="a == True and b == True")
        check = eng.check_rule(rule.id, {"a": True, "b": True})
        record(
            "CCE-022", "boolean AND expression works",
            "pass", check.result,
            cause="a=True and b=True",
            effect="result=pass",
            lesson="Boolean AND must work",
        )

    def test_check_rule_boolean_and_fail(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="a == True and b == True")
        check = eng.check_rule(rule.id, {"a": True, "b": False})
        record(
            "CCE-023", "boolean AND fails when one is False",
            "fail", check.result,
            cause="a=True and b=False",
            effect="result=fail",
            lesson="Partial AND must fail",
        )

    def test_check_rule_or(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="audit_log == True or monitoring == True")
        check = eng.check_rule(rule.id, {"audit_log": False, "monitoring": True})
        record(
            "CCE-024", "boolean OR expression works",
            "pass", check.result,
            cause="monitoring=True (OR)",
            effect="result=pass",
            lesson="Boolean OR must work",
        )

    def test_check_rule_records_duration(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        check = eng.check_rule(rule.id, {"encryption_enabled": True})
        record(
            "CCE-025", "check records execution duration",
            True, check.duration_ms >= 0,
            cause="check executed",
            effect="duration recorded",
            lesson="Duration tracking is required",
        )

    def test_check_rule_string_comparison(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression='region == "us-east-1"')
        check = eng.check_rule(rule.id, {"region": "us-east-1"})
        record(
            "CCE-026", "string comparison works",
            "pass", check.result,
            cause="region matches",
            effect="result=pass",
            lesson="String comparisons must work",
        )


class TestScanning:
    """Compliance scan execution."""

    def test_run_scan_all_pass(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "enc", "encryption_enabled == True")
        _add_rule(eng, "auth", "auth_enabled == True")
        scan = eng.run_scan("Q1 Audit", context={
            "encryption_enabled": True, "auth_enabled": True,
        })
        record(
            "CCE-027", "scan with all passing = compliant",
            "compliant", scan.status,
            cause="all rules pass",
            effect="status=compliant",
            lesson="All-pass scan must be compliant",
        )
        assert scan.rules_passed == 2
        assert scan.rules_failed == 0

    def test_run_scan_some_fail(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "enc", "encryption_enabled == True")
        _add_rule(eng, "auth", "auth_enabled == True")
        scan = eng.run_scan("Q1 Audit", context={
            "encryption_enabled": True, "auth_enabled": False,
        })
        record(
            "CCE-028", "scan with mixed results = partial",
            "partial", scan.status,
            cause="1 pass, 1 fail",
            effect="status=partial",
            lesson="Mixed pass/fail = partial compliance",
        )

    def test_run_scan_framework_filter(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "soc2-enc", framework="soc2")
        _add_rule(eng, "gdpr-consent", expression="consent == True", framework="gdpr")
        scan = eng.run_scan("SOC2 Check", framework_filter="soc2", context={
            "encryption_enabled": True, "consent": True,
        })
        record(
            "CCE-029", "scan filters by framework",
            1, scan.rules_checked,
            cause="1 soc2 rule, 1 gdpr (filtered out)",
            effect="1 checked",
            lesson="Framework filter must work in scans",
        )

    def test_run_scan_empty(self) -> None:
        eng = _make_engine()
        scan = eng.run_scan("Empty Scan", context={})
        record(
            "CCE-030", "scan with no rules = unknown",
            "unknown", scan.status,
            cause="no rules defined",
            effect="status=unknown",
            lesson="Empty scans have unknown compliance",
        )

    def test_get_scan(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1")
        scan = eng.run_scan("test", context={"encryption_enabled": True})
        got = eng.get_scan(scan.id)
        record(
            "CCE-031", "get_scan retrieves correct scan",
            scan.id, got.id if got else None,
            cause="get by ID",
            effect="same scan returned",
            lesson="Scan lookup must work",
        )

    def test_get_scan_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_scan("nonexistent")
        record(
            "CCE-032", "get_scan returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing scans return None",
        )

    def test_list_scans(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1")
        eng.run_scan("s1", context={"encryption_enabled": True})
        eng.run_scan("s2", context={"encryption_enabled": True})
        scans = eng.list_scans()
        record(
            "CCE-033", "list_scans returns all scans",
            2, len(scans),
            cause="2 scans run",
            effect="2 returned",
            lesson="List must return all",
        )

    def test_list_scans_limit(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1")
        for i in range(10):
            eng.run_scan(f"s{i}", context={"encryption_enabled": True})
        scans = eng.list_scans(limit=3)
        record(
            "CCE-034", "list_scans respects limit",
            3, len(scans),
            cause="10 scans, limit=3",
            effect="3 returned",
            lesson="Limit must be respected",
        )

    def test_scan_with_error(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "bad", expression="missing_var == True")
        scan = eng.run_scan("Error Scan", context={})
        record(
            "CCE-035", "scan with errors records error count",
            True, scan.rules_errored >= 1,
            cause="rule references missing var",
            effect="error counted",
            lesson="Errors must be counted in scan",
        )


class TestReports:
    """Report generation."""

    def test_generate_report(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "enc", "encryption_enabled == True")
        scan = eng.run_scan("Q1", context={"encryption_enabled": True})
        report = eng.generate_report(scan.id)
        record(
            "CCE-036", "generate_report returns ComplianceReport",
            True, isinstance(report, ComplianceReport),
            cause="generate_report called",
            effect="ComplianceReport returned",
            lesson="Report generation must work",
        )
        assert report.compliance_pct == 100.0

    def test_report_missing_scan(self) -> None:
        eng = _make_engine()
        report = eng.generate_report("nonexistent")
        record(
            "CCE-037", "report for missing scan returns None",
            True, report is None,
            cause="invalid scan_id",
            effect="None returned",
            lesson="Missing scans cannot generate reports",
        )

    def test_report_with_failures(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "enc", "encryption_enabled == True")
        _add_rule(eng, "auth", "auth_enabled == True")
        scan = eng.run_scan("Q1", context={
            "encryption_enabled": True, "auth_enabled": False,
        })
        report = eng.generate_report(scan.id)
        record(
            "CCE-038", "report reflects failure count",
            1, report.failed if report else -1,
            cause="1 rule failed",
            effect="failed=1",
            lesson="Report must accurately reflect failures",
        )
        assert report.compliance_pct == 50.0

    def test_report_serialization(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1")
        scan = eng.run_scan("Q1", context={"encryption_enabled": True})
        report = eng.generate_report(scan.id)
        d = report.to_dict()
        record(
            "CCE-039", "report to_dict has all fields",
            True, "compliance_pct" in d and "findings" in d,
            cause="to_dict called",
            effect="dict complete",
            lesson="Report serialization complete",
        )


class TestRemediations:
    """Remediation action tracking."""

    def test_create_remediation(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        scan = eng.run_scan("s1", context={"encryption_enabled": False})
        rem = eng.create_remediation(rule.id, scan.id, "Enable encryption", "high", "ops-team")
        record(
            "CCE-040", "create_remediation returns RemediationAction",
            True, isinstance(rem, RemediationAction),
            cause="create_remediation called",
            effect="RemediationAction returned",
            lesson="Remediation factory must work",
        )
        assert rem.completed is False

    def test_list_remediations(self) -> None:
        eng = _make_engine()
        r1 = _add_rule(eng, "r1")
        r2 = _add_rule(eng, "r2")
        scan = eng.run_scan("s1", context={"encryption_enabled": False})
        eng.create_remediation(r1.id, scan.id, "Fix r1")
        eng.create_remediation(r2.id, scan.id, "Fix r2")
        rems = eng.list_remediations()
        record(
            "CCE-041", "list_remediations returns all",
            2, len(rems),
            cause="2 remediations created",
            effect="2 returned",
            lesson="List must return all remediations",
        )

    def test_list_remediations_filter_rule(self) -> None:
        eng = _make_engine()
        r1 = _add_rule(eng, "r1")
        r2 = _add_rule(eng, "r2")
        scan = eng.run_scan("s1", context={"encryption_enabled": False})
        eng.create_remediation(r1.id, scan.id, "Fix r1")
        eng.create_remediation(r2.id, scan.id, "Fix r2")
        rems = eng.list_remediations(rule_id=r1.id)
        record(
            "CCE-042", "list_remediations filters by rule_id",
            1, len(rems),
            cause="1 remediation for r1",
            effect="1 returned",
            lesson="Rule filter must work",
        )

    def test_complete_remediation(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        scan = eng.run_scan("s1", context={"encryption_enabled": False})
        rem = eng.create_remediation(rule.id, scan.id, "Fix it")
        completed = eng.complete_remediation(rem.id)
        record(
            "CCE-043", "complete_remediation marks as done",
            True, completed.completed if completed else False,
            cause="complete_remediation called",
            effect="completed=True",
            lesson="Completion must persist",
        )

    def test_complete_remediation_missing(self) -> None:
        eng = _make_engine()
        result = eng.complete_remediation("missing")
        record(
            "CCE-044", "complete missing remediation returns None",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing remediations return None",
        )

    def test_list_remediations_completed_filter(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng)
        scan = eng.run_scan("s1", context={"encryption_enabled": False})
        rem1 = eng.create_remediation(rule.id, scan.id, "Fix 1")
        eng.create_remediation(rule.id, scan.id, "Fix 2")
        eng.complete_remediation(rem1.id)
        rems = eng.list_remediations(completed=True)
        record(
            "CCE-045", "list_remediations filters by completed",
            1, len(rems),
            cause="1 completed, 1 pending",
            effect="1 returned",
            lesson="Completed filter must work",
        )


class TestComplianceSummary:
    """Compliance summary aggregation."""

    def test_summary_basic(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1", framework="soc2")
        _add_rule(eng, "r2", framework="soc2")
        eng.run_scan("s1", context={"encryption_enabled": True})
        summary = eng.get_compliance_summary()
        record(
            "CCE-046", "summary returns dict",
            True, isinstance(summary, dict),
            cause="get_compliance_summary called",
            effect="dict returned",
            lesson="Summary must return dict",
        )
        assert "total_rules" in summary

    def test_summary_framework_filter(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1", framework="soc2")
        _add_rule(eng, "r2", framework="gdpr")
        summary = eng.get_compliance_summary(framework="soc2")
        record(
            "CCE-047", "summary filters by framework",
            True, summary.get("framework") in ("soc2", "all"),
            cause="framework=soc2 filter",
            effect="filtered summary",
            lesson="Framework filter must work for summary",
        )

    def test_summary_empty(self) -> None:
        eng = _make_engine()
        summary = eng.get_compliance_summary()
        record(
            "CCE-048", "summary handles empty state",
            0, summary.get("total_rules"),
            cause="no rules",
            effect="total_rules=0",
            lesson="Empty state must work",
        )


class TestExportAndClear:
    """State export and clear."""

    def test_export_state(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1")
        state = eng.export_state()
        record(
            "CCE-049", "export_state returns dict",
            True, isinstance(state, dict),
            cause="export_state called",
            effect="dict returned",
            lesson="Export must return plain dict",
        )
        assert "rules" in state
        assert "exported_at" in state

    def test_export_has_all_keys(self) -> None:
        eng = _make_engine()
        state = eng.export_state()
        expected_keys = {"rules", "executions", "scans", "remediations", "exported_at"}
        record(
            "CCE-050", "export has all expected keys",
            expected_keys, set(state.keys()),
            cause="export_state called",
            effect="all keys present",
            lesson="Export must be comprehensive",
        )

    def test_clear(self) -> None:
        eng = _make_engine()
        _add_rule(eng, "r1")
        eng.clear()
        rules = eng.list_rules()
        record(
            "CCE-051", "clear removes all state",
            0, len(rules),
            cause="clear called",
            effect="no rules remain",
            lesson="Clear must remove all data",
        )


class TestWingmanValidation:
    """Wingman pair validation."""

    def test_wingman_match(self) -> None:
        result = validate_wingman_pair(["a", "b", "c"], ["a", "b", "c"])
        record(
            "CCE-052", "matching pair passes",
            True, result["passed"],
            cause="storyline matches actuals",
            effect="validation passes",
            lesson="Matching pairs must pass",
        )

    def test_wingman_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "x"])
        record(
            "CCE-053", "mismatching pair fails",
            False, result["passed"],
            cause="actuals differ",
            effect="validation fails",
            lesson="Mismatches must be caught",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "CCE-054", "empty storyline fails",
            False, result["passed"],
            cause="empty storyline",
            effect="validation fails",
            lesson="Empty inputs must be rejected",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "CCE-055", "empty actuals fails",
            False, result["passed"],
            cause="empty actuals",
            effect="validation fails",
            lesson="Empty inputs must be rejected",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "CCE-056", "length mismatch fails",
            False, result["passed"],
            cause="different lengths",
            effect="validation fails",
            lesson="Length mismatches must be caught",
        )

    def test_wingman_pair_count(self) -> None:
        result = validate_wingman_pair(["x", "y", "z"], ["x", "y", "z"])
        record(
            "CCE-057", "pair_count in response",
            3, result.get("pair_count"),
            cause="3 pairs validated",
            effect="pair_count=3",
            lesson="Response must include pair_count",
        )


class TestSandboxGate:
    """Causality Sandbox gating."""

    def test_sandbox_pass(self) -> None:
        result = gate_cce_in_sandbox({"framework": "gdpr"})
        record(
            "CCE-058", "sandbox gate passes with framework",
            True, result["passed"],
            cause="framework key present",
            effect="gate passes",
            lesson="Valid context must pass gate",
        )

    def test_sandbox_missing_framework(self) -> None:
        result = gate_cce_in_sandbox({})
        record(
            "CCE-059", "sandbox gate fails without framework",
            False, result["passed"],
            cause="no framework key",
            effect="gate fails",
            lesson="Missing required keys must fail gate",
        )

    def test_sandbox_empty_framework(self) -> None:
        result = gate_cce_in_sandbox({"framework": ""})
        record(
            "CCE-060", "sandbox gate fails with empty framework",
            False, result["passed"],
            cause="empty framework string",
            effect="gate fails",
            lesson="Empty values must fail gate",
        )

    def test_sandbox_returns_framework(self) -> None:
        result = gate_cce_in_sandbox({"framework": "hipaa"})
        record(
            "CCE-061", "sandbox gate returns framework",
            "hipaa", result.get("framework"),
            cause="framework=hipaa passed",
            effect="framework in response",
            lesson="Response must echo framework",
        )


class TestFlaskAPI:
    """Flask Blueprint API endpoints."""

    def _make_app(self):
        try:
            from flask import Flask
        except ImportError:
            return None, None
        eng = _make_engine()
        app = Flask(__name__)
        app.config["TESTING"] = True
        bp = create_compliance_api(eng)
        app.register_blueprint(bp)
        return app, eng

    def test_api_create_rule(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-062", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/cce/rules", json={
                "name": "enc-check", "description": "Encryption required",
                "framework": "soc2", "severity": "high",
                "expression": "encryption_enabled == True",
                "remediation": "Enable encryption",
            })
        record(
            "CCE-062", "POST /cce/rules returns 201",
            201, resp.status_code,
            cause="valid rule data",
            effect="201 created",
            lesson="Rule creation must return 201",
        )

    def test_api_list_rules(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-063", "Flask not installed — skip", True, True)
            return
        _add_rule(eng, "r1")
        with app.test_client() as c:
            resp = c.get("/api/cce/rules")
        record(
            "CCE-063", "GET /cce/rules returns 200",
            200, resp.status_code,
            cause="rules exist",
            effect="200 OK",
            lesson="List must return 200",
        )

    def test_api_get_rule(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-064", "Flask not installed — skip", True, True)
            return
        rule = _add_rule(eng, "r1")
        with app.test_client() as c:
            resp = c.get(f"/api/cce/rules/{rule.id}")
        record(
            "CCE-064", "GET /cce/rules/<id> returns 200",
            200, resp.status_code,
            cause="valid rule ID",
            effect="200 OK",
            lesson="Get by ID must return 200",
        )

    def test_api_get_rule_404(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-065", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/cce/rules/nonexistent")
        record(
            "CCE-065", "GET /cce/rules/<missing> returns 404",
            404, resp.status_code,
            cause="invalid rule ID",
            effect="404 Not Found",
            lesson="Missing rule must return 404",
        )

    def test_api_check_rule(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-066", "Flask not installed — skip", True, True)
            return
        rule = _add_rule(eng)
        with app.test_client() as c:
            resp = c.post(f"/api/cce/check/{rule.id}", json={
                "context": {"encryption_enabled": True},
            })
        record(
            "CCE-066", "POST /cce/check/<id> returns 200",
            200, resp.status_code,
            cause="valid check request",
            effect="200 OK",
            lesson="Check must return 200",
        )

    def test_api_run_scan(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-067", "Flask not installed — skip", True, True)
            return
        _add_rule(eng)
        with app.test_client() as c:
            resp = c.post("/api/cce/scan", json={
                "name": "Q1 Audit",
                "context": {"encryption_enabled": True},
            })
        record(
            "CCE-067", "POST /cce/scan returns 201",
            201, resp.status_code,
            cause="valid scan request",
            effect="201 Created",
            lesson="Scan creation must return 201",
        )

    def test_api_get_scan(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-068", "Flask not installed — skip", True, True)
            return
        _add_rule(eng)
        scan = eng.run_scan("test", context={"encryption_enabled": True})
        with app.test_client() as c:
            resp = c.get(f"/api/cce/scans/{scan.id}")
        record(
            "CCE-068", "GET /cce/scans/<id> returns 200",
            200, resp.status_code,
            cause="valid scan ID",
            effect="200 OK",
            lesson="Get scan must return 200",
        )

    def test_api_list_scans(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-069", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/cce/scans")
        record(
            "CCE-069", "GET /cce/scans returns 200",
            200, resp.status_code,
            cause="scans endpoint called",
            effect="200 OK",
            lesson="List scans must return 200",
        )

    def test_api_generate_report(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-070", "Flask not installed — skip", True, True)
            return
        _add_rule(eng)
        scan = eng.run_scan("test", context={"encryption_enabled": True})
        with app.test_client() as c:
            resp = c.get(f"/api/cce/scans/{scan.id}/report")
        record(
            "CCE-070", "GET /cce/scans/<id>/report returns 200",
            200, resp.status_code,
            cause="valid scan for report",
            effect="200 OK",
            lesson="Report must return 200",
        )

    def test_api_create_remediation(self) -> None:
        app, eng = self._make_app()
        if app is None:
            record("CCE-071", "Flask not installed — skip", True, True)
            return
        rule = _add_rule(eng)
        scan = eng.run_scan("test", context={"encryption_enabled": False})
        with app.test_client() as c:
            resp = c.post("/api/cce/remediations", json={
                "rule_id": rule.id, "scan_id": scan.id,
                "description": "Enable encryption",
            })
        record(
            "CCE-071", "POST /cce/remediations returns 201",
            201, resp.status_code,
            cause="valid remediation data",
            effect="201 created",
            lesson="Remediation creation must return 201",
        )

    def test_api_list_remediations(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-072", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/cce/remediations")
        record(
            "CCE-072", "GET /cce/remediations returns 200",
            200, resp.status_code,
            cause="remediations endpoint called",
            effect="200 OK",
            lesson="List remediations must return 200",
        )

    def test_api_summary(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-073", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/cce/summary")
        record(
            "CCE-073", "GET /cce/summary returns 200",
            200, resp.status_code,
            cause="summary endpoint called",
            effect="200 OK",
            lesson="Summary must return 200",
        )

    def test_api_export(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-074", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/cce/export")
        record(
            "CCE-074", "POST /cce/export returns 200",
            200, resp.status_code,
            cause="export endpoint called",
            effect="200 OK",
            lesson="Export must return 200",
        )

    def test_api_health(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-075", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/cce/health")
        data = resp.get_json()
        record(
            "CCE-075", "GET /cce/health returns module CCE-001",
            "CCE-001", data.get("module"),
            cause="health endpoint called",
            effect="module=CCE-001",
            lesson="Health must identify the module",
        )

    def test_api_missing_name(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("CCE-076", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/cce/rules", json={})
        record(
            "CCE-076", "POST /cce/rules without name returns 400",
            400, resp.status_code,
            cause="missing name field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )


class TestConcurrency:
    """Thread-safety tests."""

    def test_concurrent_rule_creation(self) -> None:
        eng = _make_engine()
        errors: List[str] = []

        def create_batch(prefix: str) -> None:
            try:
                for i in range(50):
                    _add_rule(eng, f"{prefix}-{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=create_batch, args=(f"t{t}",))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        rules = eng.list_rules(limit=500)
        record(
            "CCE-077", "concurrent rule creation is thread-safe",
            True, len(rules) == 200 and not errors,
            cause="4 threads × 50 rules",
            effect="200 rules, no errors",
            lesson="Rule creation must be thread-safe",
        )

    def test_concurrent_scan(self) -> None:
        eng = _make_engine()
        for i in range(10):
            _add_rule(eng, f"r{i}")
        errors: List[str] = []

        def scan_batch(tid: int) -> None:
            try:
                for i in range(5):
                    eng.run_scan(f"t{tid}-s{i}", context={"encryption_enabled": True})
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=scan_batch, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        scans = eng.list_scans(limit=100)
        record(
            "CCE-078", "concurrent scanning is thread-safe",
            True, len(scans) == 20 and not errors,
            cause="4 threads × 5 scans",
            effect="20 scans, no errors",
            lesson="Scanning must be thread-safe",
        )


class TestEdgeCases:
    """Edge cases and boundary values."""

    def test_complex_expression(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="password_min_length >= 12 and mfa_enabled == True")
        check = eng.check_rule(rule.id, {"password_min_length": 16, "mfa_enabled": True})
        record(
            "CCE-079", "complex multi-condition expression",
            "pass", check.result,
            cause="both conditions met",
            effect="result=pass",
            lesson="Complex expressions must work",
        )

    def test_not_expression(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="not allow_anonymous")
        check = eng.check_rule(rule.id, {"allow_anonymous": False})
        record(
            "CCE-080", "NOT expression works",
            "pass", check.result,
            cause="not False = True",
            effect="result=pass",
            lesson="NOT operator must work",
        )

    def test_numeric_boundary(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="timeout >= 30")
        check = eng.check_rule(rule.id, {"timeout": 30})
        record(
            "CCE-081", "boundary value (exactly equal)",
            "pass", check.result,
            cause="timeout=30 >= 30",
            effect="result=pass",
            lesson="Boundary values must be handled correctly",
        )

    def test_numeric_just_below(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="timeout >= 30")
        check = eng.check_rule(rule.id, {"timeout": 29})
        record(
            "CCE-082", "just below boundary fails",
            "fail", check.result,
            cause="timeout=29 < 30",
            effect="result=fail",
            lesson="Just-below boundary must fail",
        )

    def test_special_chars_in_name(self) -> None:
        eng = _make_engine()
        rule = eng.create_rule(
            "SOC2 / PCI-DSS @ 2026",
            "Combined check", "soc2", "high",
            "True", "No action needed",
        )
        record(
            "CCE-083", "special characters in name",
            "SOC2 / PCI-DSS @ 2026", rule.name,
            cause="special chars in name",
            effect="stored as-is",
            lesson="Names must accept arbitrary strings",
        )

    def test_disabled_rule_skipped_in_scan(self) -> None:
        eng = _make_engine()
        r1 = _add_rule(eng, "active-rule")
        r2 = _add_rule(eng, "disabled-rule")
        eng.update_rule(r2.id, status="disabled")
        scan = eng.run_scan("test", context={"encryption_enabled": True})
        record(
            "CCE-084", "disabled rules skipped in scan",
            1, scan.rules_checked,
            cause="1 active, 1 disabled",
            effect="only 1 checked",
            lesson="Disabled rules must be skipped",
        )

    def test_in_operator(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression='"admin" in roles')
        check = eng.check_rule(rule.id, {"roles": ["admin", "user"]})
        record(
            "CCE-085", "in operator works with lists",
            "pass", check.result,
            cause="admin in roles list",
            effect="result=pass",
            lesson="in operator must work",
        )

    def test_always_true_expression(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="True")
        check = eng.check_rule(rule.id, {})
        record(
            "CCE-086", "literal True always passes",
            "pass", check.result,
            cause="expression is True",
            effect="result=pass",
            lesson="Literal booleans must work",
        )

    def test_always_false_expression(self) -> None:
        eng = _make_engine()
        rule = _add_rule(eng, expression="False")
        check = eng.check_rule(rule.id, {})
        record(
            "CCE-087", "literal False always fails",
            "fail", check.result,
            cause="expression is False",
            effect="result=fail",
            lesson="Literal booleans must work",
        )

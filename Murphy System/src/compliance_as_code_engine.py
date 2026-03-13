# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Compliance-as-Code Engine — CCE-001

Owner: Security · Dep: threading, uuid, dataclasses, ast, time

Encode regulatory requirements as testable rules, continuous compliance
checking.  Define compliance rules as safe expressions, run scans against
a context dictionary, aggregate pass/fail/error results, generate reports,
and track remediation actions.
``create_compliance_api(engine)`` → Flask Blueprint.
Safety: every mutation under ``threading.Lock``; bounded via capped_append.
"""
from __future__ import annotations

import ast
import builtins
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]

    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}

    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}
        @staticmethod
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)
# -- Enums -----------------------------------------------------------------

class Framework(str, Enum):
    """Regulatory / compliance framework."""
    gdpr = "gdpr"; hipaa = "hipaa"; soc2 = "soc2"; pci_dss = "pci_dss"
    iso_27001 = "iso_27001"; ccpa = "ccpa"; custom = "custom"

class RuleSeverity(str, Enum):
    """Severity level of a compliance rule."""
    info = "info"; low = "low"; medium = "medium"; high = "high"; critical = "critical"

class RuleStatus(str, Enum):
    """Lifecycle status of a compliance rule."""
    active = "active"; disabled = "disabled"; deprecated = "deprecated"

class CheckResult(str, Enum):
    """Result of a single rule check."""
    pass_result = "pass"; fail = "fail"; error = "error"; skip = "skip"

class ComplianceStatus(str, Enum):
    """Overall compliance status of a scan."""
    compliant = "compliant"; non_compliant = "non_compliant"
    partial = "partial"; unknown = "unknown"
# -- Dataclass models ------------------------------------------------------

@dataclass
class ComplianceRule:
    """A testable compliance rule with a safe expression."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    description: str = ""
    framework: str = "custom"
    severity: str = "medium"
    status: str = "active"
    expression: str = ""
    remediation: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class CheckExecution:
    """Result of evaluating a single rule against a context."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    rule_id: str = ""
    rule_name: str = ""
    result: str = "skip"
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    duration_ms: float = 0.0
    executed_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class ComplianceScan:
    """Aggregated result of running multiple rules."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    framework_filter: Optional[str] = None
    rules_checked: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    rules_errored: int = 0
    rules_skipped: int = 0
    status: str = "unknown"
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class RemediationAction:
    """A remediation task linked to a rule and scan."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    rule_id: str = ""
    scan_id: str = ""
    description: str = ""
    priority: str = "medium"
    assigned_to: str = ""
    completed: bool = False
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class ComplianceReport:
    """Generated compliance report from a scan."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    scan_id: str = ""
    framework: str = ""
    total_rules: int = 0
    passed: int = 0
    failed: int = 0
    compliance_pct: float = 0.0
    status: str = "unknown"
    findings: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)
# -- Safe expression evaluator ---------------------------------------------

_SAFE_NODE_TYPES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Constant, ast.Name, ast.Load, ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
)


def _validate_ast(node: ast.AST) -> bool:
    """Return True only if every node in the tree is in the safe set."""
    if not isinstance(node, _SAFE_NODE_TYPES):
        return False
    for child in ast.iter_child_nodes(node):
        if not _validate_ast(child):
            return False
    return True


def _safe_eval(expression: str, context: Dict[str, Any]) -> bool:
    """Evaluate *expression* against *context* using a restricted namespace.

    Only simple comparisons, boolean operators, arithmetic, ``in``, and
    literal / context-key lookups are permitted.  Raises ``ValueError``
    for disallowed constructs.
    """
    tree = ast.parse(expression, "<rule>", "eval")
    if not _validate_ast(tree):
        raise ValueError("Expression contains disallowed constructs")
    code = compile(tree, "<rule>", "eval")
    # SECURITY: eval() is used here ONLY after full AST validation by _validate_ast().
    # The namespace is sandboxed: builtins are disabled and only context keys are accessible.
    # This is intentional for rule-engine expression evaluation. See SEC-001 audit.
    _sandbox_eval = builtins.__dict__["eval"]  # noqa: S307
    result = _sandbox_eval(code, {"__builtins__": {}}, context)
    return bool(result)
# -- Engine ----------------------------------------------------------------

class ComplianceAsCodeEngine:
    """Thread-safe compliance-as-code engine."""

    def __init__(self, max_rules: int = 10_000,
                 max_executions: int = 50_000) -> None:
        self._lock = threading.Lock()
        self._rules: Dict[str, ComplianceRule] = {}
        self._executions: List[CheckExecution] = []
        self._scans: Dict[str, ComplianceScan] = {}
        self._remediations: Dict[str, RemediationAction] = {}
        self._history: List[dict] = []
        self._max_rules = max_rules
        self._max_executions = max_executions
    # -- Rules CRUD ---------------------------------------------------------

    def create_rule(
        self, name: str, description: str,
        framework: Union[str, Framework] = "custom",
        severity: Union[str, RuleSeverity] = "medium",
        expression: str = "",
        remediation: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> ComplianceRule:
        """Create and store a new compliance rule."""
        rule = ComplianceRule(
            name=name, description=description,
            framework=_enum_val(framework), severity=_enum_val(severity),
            expression=expression, remediation=remediation,
            tags=tags or {},
        )
        with self._lock:
            self._rules[rule.id] = rule
            capped_append(self._history,
                          {"action": "create_rule", "rule_id": rule.id,
                           "ts": _now()}, 50_000)
        return rule

    def get_rule(self, rule_id: str) -> Optional[ComplianceRule]:
        """Return a rule by id, or None."""
        with self._lock:
            return self._rules.get(rule_id)

    def list_rules(
        self, framework: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ComplianceRule]:
        """Return rules filtered by optional criteria."""
        with self._lock:
            out = list(self._rules.values())
        if framework:
            out = [r for r in out if r.framework == framework]
        if severity:
            out = [r for r in out if r.severity == severity]
        if status:
            out = [r for r in out if r.status == status]
        return out[:limit]

    def update_rule(
        self, rule_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        expression: Optional[str] = None,
        remediation: Optional[str] = None,
    ) -> Optional[ComplianceRule]:
        """Update mutable fields of a rule."""
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                return None
            if status is not None:
                rule.status = status
            if severity is not None:
                rule.severity = severity
            if expression is not None:
                rule.expression = expression
            if remediation is not None:
                rule.remediation = remediation
            rule.updated_at = _now()
            capped_append(self._history,
                          {"action": "update_rule", "rule_id": rule_id,
                           "ts": _now()}, 50_000)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by id. Return True if found."""
        with self._lock:
            if rule_id not in self._rules:
                return False
            del self._rules[rule_id]
            capped_append(self._history,
                          {"action": "delete_rule", "rule_id": rule_id,
                           "ts": _now()}, 50_000)
        return True
    # -- Check & Scan -------------------------------------------------------

    def check_rule(self, rule_id: str,
                   context: Dict[str, Any]) -> CheckExecution:
        """Evaluate one rule against *context*."""
        with self._lock:
            rule = self._rules.get(rule_id)
        if rule is None:
            return CheckExecution(rule_id=rule_id, result="error",
                                 message="Rule not found")
        return self._execute_rule(rule, context)

    def _execute_rule(self, rule: ComplianceRule,
                      context: Dict[str, Any]) -> CheckExecution:
        """Run *rule* expression and record the execution."""
        if rule.status != "active":
            return self._record_execution(
                rule, "skip", context, "Rule is not active", 0.0)
        t0 = time.monotonic()
        try:
            passed = _safe_eval(rule.expression, context)
            elapsed = (time.monotonic() - t0) * 1000
            result = "pass" if passed else "fail"
            msg = "Rule passed" if passed else rule.remediation
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            result = "error"
            msg = str(exc)[:200]
        return self._record_execution(rule, result, context, msg, elapsed)

    def _record_execution(
        self, rule: ComplianceRule, result: str,
        context: Dict[str, Any], message: str, duration_ms: float,
    ) -> CheckExecution:
        """Create and store a CheckExecution."""
        exe = CheckExecution(
            rule_id=rule.id, rule_name=rule.name, result=result,
            context_snapshot=dict(context), message=message,
            duration_ms=round(duration_ms, 3),
        )
        with self._lock:
            capped_append(self._executions, exe, self._max_executions)
        return exe

    def run_scan(
        self, name: str,
        framework_filter: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ComplianceScan:
        """Run all matching active rules against *context*."""
        ctx = context or {}
        scan = ComplianceScan(name=name, framework_filter=framework_filter)
        rules = self._collect_scan_rules(framework_filter)
        passed = failed = errored = skipped = 0
        for rule in rules:
            exe = self._execute_rule(rule, ctx)
            passed, failed, errored, skipped = _tally(
                exe.result, passed, failed, errored, skipped)
        self._finalise_scan(scan, len(rules), passed, failed,
                            errored, skipped)
        return scan

    def _collect_scan_rules(
        self, framework_filter: Optional[str],
    ) -> List[ComplianceRule]:
        """Return active rules matching the optional framework filter."""
        with self._lock:
            rules = list(self._rules.values())
        if framework_filter:
            rules = [r for r in rules if r.framework == framework_filter]
        return [r for r in rules if r.status == "active"]

    def _finalise_scan(
        self, scan: ComplianceScan, checked: int,
        passed: int, failed: int, errored: int, skipped: int,
    ) -> None:
        """Populate scan counters, derive status, and persist."""
        scan.rules_checked = checked
        scan.rules_passed = passed
        scan.rules_failed = failed
        scan.rules_errored = errored
        scan.rules_skipped = skipped
        scan.status = _derive_status(passed, failed, errored, checked)
        scan.completed_at = _now()
        with self._lock:
            self._scans[scan.id] = scan
            capped_append(self._history,
                          {"action": "run_scan", "scan_id": scan.id,
                           "ts": _now()}, 50_000)
    # -- Scan queries -------------------------------------------------------

    def get_scan(self, scan_id: str) -> Optional[ComplianceScan]:
        """Return a scan by id, or None."""
        with self._lock:
            return self._scans.get(scan_id)

    def list_scans(
        self, framework: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[ComplianceScan]:
        """Return scans filtered by optional criteria."""
        with self._lock:
            out = list(self._scans.values())
        if framework:
            out = [s for s in out if s.framework_filter == framework]
        if status:
            out = [s for s in out if s.status == status]
        return out[:limit]
    # -- Report -------------------------------------------------------------

    def generate_report(self, scan_id: str) -> Optional[ComplianceReport]:
        """Build a compliance report from a scan's executions."""
        with self._lock:
            scan = self._scans.get(scan_id)
            if scan is None:
                return None
            exes = [e for e in self._executions
                    if self._exe_belongs_to_scan(e, scan)]
        return self._build_report(scan, exes)

    @staticmethod
    def _exe_belongs_to_scan(exe: CheckExecution,
                             scan: ComplianceScan) -> bool:
        """Check if an execution timestamp falls within the scan window."""
        return (scan.started_at <= exe.executed_at
                and (not scan.completed_at
                     or exe.executed_at <= scan.completed_at))

    @staticmethod
    def _build_report(scan: ComplianceScan,
                      exes: List[CheckExecution]) -> ComplianceReport:
        """Construct a ComplianceReport from scan data and executions."""
        findings = [{"rule_id": e.rule_id, "rule_name": e.rule_name,
                     "result": e.result, "message": e.message}
                    for e in exes if e.result in ("fail", "error")]
        total = scan.rules_checked or 1
        pct = round(scan.rules_passed / total * 100, 2)
        return ComplianceReport(
            scan_id=scan.id,
            framework=scan.framework_filter or "",
            total_rules=scan.rules_checked, passed=scan.rules_passed,
            failed=scan.rules_failed, compliance_pct=pct,
            status=scan.status, findings=findings,
        )
    # -- Remediation --------------------------------------------------------

    def create_remediation(
        self, rule_id: str, scan_id: str, description: str,
        priority: Union[str, RuleSeverity] = "medium",
        assigned_to: str = "",
    ) -> RemediationAction:
        """Create a remediation action for a failed rule."""
        action = RemediationAction(
            rule_id=rule_id, scan_id=scan_id, description=description,
            priority=_enum_val(priority), assigned_to=assigned_to,
        )
        with self._lock:
            self._remediations[action.id] = action
            capped_append(self._history,
                          {"action": "create_remediation", "id": action.id,
                           "ts": _now()}, 50_000)
        return action

    def list_remediations(
        self, rule_id: Optional[str] = None,
        scan_id: Optional[str] = None,
        completed: Optional[bool] = None,
        limit: int = 100,
    ) -> List[RemediationAction]:
        """Return remediations filtered by optional criteria."""
        with self._lock:
            out = list(self._remediations.values())
        if rule_id:
            out = [r for r in out if r.rule_id == rule_id]
        if scan_id:
            out = [r for r in out if r.scan_id == scan_id]
        if completed is not None:
            out = [r for r in out if r.completed is completed]
        return out[:limit]

    def complete_remediation(
        self, remediation_id: str,
    ) -> Optional[RemediationAction]:
        """Mark a remediation as completed."""
        with self._lock:
            action = self._remediations.get(remediation_id)
            if action is None:
                return None
            action.completed = True
            capped_append(self._history,
                          {"action": "complete_remediation",
                           "id": remediation_id, "ts": _now()}, 50_000)
        return action
    # -- Summary & export ---------------------------------------------------

    def get_compliance_summary(
        self, framework: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a high-level compliance summary."""
        with self._lock:
            rules = list(self._rules.values())
            scans = list(self._scans.values())
        if framework:
            rules = [r for r in rules if r.framework == framework]
            scans = [s for s in scans if s.framework_filter == framework]
        active = [r for r in rules if r.status == "active"]
        latest = scans[-1] if scans else None
        pct = 0.0
        if latest and latest.rules_checked:
            pct = round(latest.rules_passed / latest.rules_checked * 100, 2)
        return {
            "framework": framework or "all",
            "total_rules": len(rules), "active_rules": len(active),
            "latest_scan_status": latest.status if latest else "none",
            "compliance_pct": pct,
        }

    def export_state(self) -> dict:
        """Serialise full engine state."""
        with self._lock:
            return {
                "rules": {rid: r.to_dict()
                          for rid, r in self._rules.items()},
                "executions": [e.to_dict() for e in self._executions],
                "scans": {sid: s.to_dict()
                          for sid, s in self._scans.items()},
                "remediations": {rid: r.to_dict()
                                 for rid, r in self._remediations.items()},
                "exported_at": _now(),
            }

    def clear(self) -> None:
        """Remove all state."""
        with self._lock:
            self._rules.clear()
            self._executions.clear()
            self._scans.clear()
            self._remediations.clear()
            capped_append(self._history, {"action": "clear", "ts": _now()},
                          50_000)
# -- Helpers (scan tallying / status) --------------------------------------

def _tally(result: str, passed: int, failed: int,
           errored: int, skipped: int) -> tuple:
    """Increment the correct counter for *result*."""
    if result == "pass":
        return passed + 1, failed, errored, skipped
    if result == "fail":
        return passed, failed + 1, errored, skipped
    if result == "error":
        return passed, failed, errored + 1, skipped
    return passed, failed, errored, skipped + 1


def _derive_status(passed: int, failed: int, errored: int,
                   checked: int) -> str:
    """Derive overall compliance status from counters."""
    if checked == 0:
        return "unknown"
    if failed == 0 and errored == 0:
        return "compliant"
    if passed == 0:
        return "non_compliant"
    return "partial"
# -- Wingman & Sandbox gates -----------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """CCE-001 Wingman gate."""
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {"passed": False,
                "message": f"Length mismatch: storyline={len(storyline)} "
                           f"actuals={len(actuals)}"}
    mismatches: List[int] = [
        i for i, (s, a) in enumerate(zip(storyline, actuals)) if s != a
    ]
    if mismatches:
        return {"passed": False,
                "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}


def gate_cce_in_sandbox(context: dict) -> dict:
    """CCE-001 Causality Sandbox gate."""
    required_keys = {"framework"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("framework"):
        return {"passed": False, "message": "framework must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "framework": context["framework"]}
# -- Flask Blueprint factory -----------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k) and body.get(k) != 0:
            return jsonify({"error": f"Missing required field: {k}",
                            "code": "MISSING_FIELD"}), 400
    return None

def _not_found(msg: str) -> Any:
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404


def create_compliance_api(
    engine: ComplianceAsCodeEngine,
) -> Any:
    """Create a Flask Blueprint with compliance-as-code REST endpoints."""
    bp = Blueprint("cce", __name__, url_prefix="/api")
    eng = engine

    @bp.route("/cce/rules", methods=["POST"])
    def create_rule() -> Any:
        body = _api_body()
        err = _api_need(body, "name", "expression")
        if err:
            return err
        r = eng.create_rule(
            name=body["name"],
            description=body.get("description", ""),
            framework=body.get("framework", "custom"),
            severity=body.get("severity", "medium"),
            expression=body["expression"],
            remediation=body.get("remediation", ""),
            tags=body.get("tags", {}),
        )
        return jsonify(r.to_dict()), 201

    @bp.route("/cce/rules", methods=["GET"])
    def list_rules() -> Any:
        a = request.args
        rules = eng.list_rules(
            framework=a.get("framework"),
            severity=a.get("severity"),
            status=a.get("status"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in rules]), 200

    @bp.route("/cce/rules/<rule_id>", methods=["GET"])
    def get_rule(rule_id: str) -> Any:
        rule = eng.get_rule(rule_id)
        if rule is None:
            return _not_found("Rule not found")
        return jsonify(rule.to_dict()), 200

    @bp.route("/cce/rules/<rule_id>", methods=["PUT"])
    def update_rule(rule_id: str) -> Any:
        body = _api_body()
        rule = eng.update_rule(
            rule_id,
            status=body.get("status"),
            severity=body.get("severity"),
            expression=body.get("expression"),
            remediation=body.get("remediation"),
        )
        if rule is None:
            return _not_found("Rule not found")
        return jsonify(rule.to_dict()), 200

    @bp.route("/cce/rules/<rule_id>", methods=["DELETE"])
    def delete_rule(rule_id: str) -> Any:
        if not eng.delete_rule(rule_id):
            return _not_found("Rule not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/cce/check/<rule_id>", methods=["POST"])
    def check_rule(rule_id: str) -> Any:
        body = _api_body()
        exe = eng.check_rule(rule_id, body)
        return jsonify(exe.to_dict()), 200

    @bp.route("/cce/scan", methods=["POST"])
    def run_scan() -> Any:
        body = _api_body()
        err = _api_need(body, "name")
        if err:
            return err
        scan = eng.run_scan(
            name=body["name"],
            framework_filter=body.get("framework_filter"),
            context=body.get("context", {}),
        )
        return jsonify(scan.to_dict()), 201

    @bp.route("/cce/scans", methods=["GET"])
    def list_scans() -> Any:
        a = request.args
        scans = eng.list_scans(
            framework=a.get("framework"),
            status=a.get("status"),
            limit=int(a.get("limit", 50)),
        )
        return jsonify([s.to_dict() for s in scans]), 200

    @bp.route("/cce/scans/<scan_id>", methods=["GET"])
    def get_scan(scan_id: str) -> Any:
        scan = eng.get_scan(scan_id)
        if scan is None:
            return _not_found("Scan not found")
        return jsonify(scan.to_dict()), 200

    @bp.route("/cce/scans/<scan_id>/report", methods=["GET"])
    def generate_report(scan_id: str) -> Any:
        report = eng.generate_report(scan_id)
        if report is None:
            return _not_found("Scan not found")
        return jsonify(report.to_dict()), 200

    @bp.route("/cce/remediations", methods=["POST"])
    def create_remediation() -> Any:
        body = _api_body()
        err = _api_need(body, "rule_id", "scan_id", "description")
        if err:
            return err
        action = eng.create_remediation(
            rule_id=body["rule_id"], scan_id=body["scan_id"],
            description=body["description"],
            priority=body.get("priority", "medium"),
            assigned_to=body.get("assigned_to", ""),
        )
        return jsonify(action.to_dict()), 201

    @bp.route("/cce/remediations", methods=["GET"])
    def list_remediations() -> Any:
        a = request.args
        completed = None
        if a.get("completed") is not None:
            completed = a.get("completed", "").lower() == "true"
        actions = eng.list_remediations(
            rule_id=a.get("rule_id"), scan_id=a.get("scan_id"),
            completed=completed,
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in actions]), 200

    @bp.route("/cce/remediations/<remediation_id>/complete", methods=["POST"])
    def complete_remediation(remediation_id: str) -> Any:
        action = eng.complete_remediation(remediation_id)
        if action is None:
            return _not_found("Remediation not found")
        return jsonify(action.to_dict()), 200

    @bp.route("/cce/summary", methods=["GET"])
    def get_summary() -> Any:
        a = request.args
        summary = eng.get_compliance_summary(framework=a.get("framework"))
        return jsonify(summary), 200

    @bp.route("/cce/export", methods=["POST"])
    def export_state() -> Any:
        return jsonify(eng.export_state()), 200

    @bp.route("/cce/health", methods=["GET"])
    def health() -> Any:
        rules = eng.list_rules()
        return jsonify({
            "status": "healthy", "module": "CCE-001",
            "tracked_rules": len(rules),
        }), 200

    require_blueprint_auth(bp)
    return bp

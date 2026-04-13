# production_commissioning_validator.py
# Design Label: COMMISSION-VAL-001
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: Business Source License 1.1 (BSL 1.1)
#
# Programmatic enforcement of the COMMISSIONING_CHECKLIST.md questions
# as automated static-analysis checks for production modules.

"""
Production Commissioning Validator

Part of the Murphy System.
"""

from __future__ import annotations

import ast
import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class CommissioningQuestion(Enum):
    """The 10 commissioning questions from COMMISSIONING_CHECKLIST.md."""

    Q1 = "Does the module do what it was designed to do?"
    Q2 = (
        "What exactly is the module supposed to do, knowing that this "
        "may change as design decisions evolve?"
    )
    Q3 = "What conditions are possible based on the module?"
    Q4 = (
        "Does the test profile actually reflect the full range of "
        "capabilities and possible conditions?"
    )
    Q5 = "What is the expected result at all points of operation?"
    Q6 = "What is the actual result?"
    Q7 = (
        "If there are still problems, how do we restart the process "
        "from the symptoms and work back through validation again?"
    )
    Q8 = (
        "Has all ancillary code and documentation been updated to "
        "reflect the changes made, including as-builts?"
    )
    Q9 = "Has hardening been applied?"
    Q10 = "Has the module been commissioned again after those steps?"


@dataclass
class CheckResult:
    """Result of a single commissioning-question check.

    Attributes:
        question: The commissioning question that was evaluated.
        passed: Whether the check passed.
        evidence: Human-readable evidence string.
        severity: One of P0 through P4.
        details: Arbitrary key/value details for tooling.
    """

    question: CommissioningQuestion
    passed: bool
    evidence: str
    severity: str
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_severities = {"P0", "P1", "P2", "P3", "P4"}
        if self.severity not in valid_severities:
            raise ValueError(
                f"severity must be one of {valid_severities}, got {self.severity!r}"
            )


@dataclass
class ModuleCommissionReport:
    """Full commissioning report for a single module.

    Attributes:
        module_name: Short name of the module.
        module_path: Filesystem path to the module file.
        results: Ordered list of check results (Q1-Q10).
        commissioned_by: Name/handle of the person commissioning.
        commissioned_at: ISO 8601 timestamp of the commissioning run.
        overall_pass: True only when every check passed.
    """

    module_name: str
    module_path: str
    results: List[CheckResult]
    commissioned_by: str
    commissioned_at: str
    overall_pass: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_parse_lock = threading.Lock()


def _parse_module(module_path: str) -> ast.Module:
    """Thread-safe AST parse of a Python file."""
    with _parse_lock:
        source = Path(module_path).read_text(encoding="utf-8")
        return ast.parse(source, filename=module_path)


def _get_test_path(module_path: str, test_dir: str) -> Path:
    """Derive the expected test file path for a given module."""
    module_name = Path(module_path).stem
    return Path(test_dir) / f"test_{module_name}.py"


def _count_functions_and_classes(tree: ast.Module) -> List[ast.AST]:
    """Return top-level public functions and classes in *tree*."""
    return [
        node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    ]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class ProductionCommissioningValidator:
    """Automated enforcement of the 10 commissioning-checklist questions.

    All analysis is performed via the ``ast`` module (no ``exec`` / ``eval``).
    Every public method is thread-safe.
    """

    # -- Q1 ------------------------------------------------------------------

    def check_q1_functionality(self, module_path: str) -> CheckResult:
        """Q1 – Does the module do what it was designed to do?

        Checks whether the module can be parsed (importable) and has a
        module-level docstring.
        """
        logger.info("Q1: checking functionality for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}
        try:
            tree = _parse_module(module_path)
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q1,
                passed=False,
                evidence=f"SyntaxError – module cannot be imported: {exc}",
                severity="P0",
                details={**details, "error": str(exc)},
            )

        has_docstring = (
            isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, (ast.Constant,))
            and isinstance(tree.body[0].value.value, str)
            if tree.body
            else False
        )
        details["has_docstring"] = has_docstring

        if has_docstring:
            return CheckResult(
                question=CommissioningQuestion.Q1,
                passed=True,
                evidence="Module parses successfully and has a module docstring.",
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q1,
            passed=False,
            evidence="Module parses but lacks a module-level docstring.",
            severity="P2",
            details=details,
        )

    # -- Q2 ------------------------------------------------------------------

    def check_q2_purpose(self, module_path: str) -> CheckResult:
        """Q2 – What exactly is the module supposed to do?

        Checks if the module has a top-level docstring that describes its
        purpose (minimum 10 characters).
        """
        logger.info("Q2: checking purpose docstring for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}
        try:
            tree = _parse_module(module_path)
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q2,
                passed=False,
                evidence=f"Cannot parse module: {exc}",
                severity="P0",
                details={**details, "error": str(exc)},
            )

        docstring = ast.get_docstring(tree) or ""
        details["docstring_length"] = len(docstring)

        if len(docstring) >= 10:
            return CheckResult(
                question=CommissioningQuestion.Q2,
                passed=True,
                evidence=f"Module docstring found ({len(docstring)} chars).",
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q2,
            passed=False,
            evidence="Module docstring missing or too short (< 10 chars).",
            severity="P1",
            details=details,
        )

    # -- Q3 ------------------------------------------------------------------

    def check_q3_conditions(self, module_path: str) -> CheckResult:
        """Q3 – What conditions are possible based on the module?

        Checks if try/except blocks exist, indicating the developer has
        considered error/edge-case conditions.
        """
        logger.info("Q3: checking error-condition handling for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}
        try:
            tree = _parse_module(module_path)
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q3,
                passed=False,
                evidence=f"Cannot parse module: {exc}",
                severity="P0",
                details={**details, "error": str(exc)},
            )

        try_count = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.Try)
        )
        details["try_except_count"] = try_count

        if try_count > 0:
            return CheckResult(
                question=CommissioningQuestion.Q3,
                passed=True,
                evidence=f"Found {try_count} try/except block(s).",
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q3,
            passed=False,
            evidence="No try/except blocks found – edge-case handling may be missing.",
            severity="P2",
            details=details,
        )

    # -- Q4 ------------------------------------------------------------------

    def check_q4_test_coverage(
        self, module_path: str, test_dir: str
    ) -> CheckResult:
        """Q4 – Does the test profile reflect the full range of capabilities?

        Checks that a corresponding test file exists and contains at least
        one ``test_`` function or ``Test`` class.
        """
        logger.info("Q4: checking test coverage for %s", module_path)
        test_file = _get_test_path(module_path, test_dir)
        details: Dict[str, Any] = {
            "module_path": module_path,
            "expected_test_file": str(test_file),
        }

        if not test_file.exists():
            return CheckResult(
                question=CommissioningQuestion.Q4,
                passed=False,
                evidence=f"Test file not found: {test_file}",
                severity="P1",
                details=details,
            )

        try:
            tree = _parse_module(str(test_file))
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q4,
                passed=False,
                evidence=f"Test file has syntax errors: {exc}",
                severity="P1",
                details={**details, "error": str(exc)},
            )

        test_items = [
            node
            for node in ast.walk(tree)
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
            )
            or (isinstance(node, ast.ClassDef) and node.name.startswith("Test"))
        ]
        details["test_item_count"] = len(test_items)

        if test_items:
            return CheckResult(
                question=CommissioningQuestion.Q4,
                passed=True,
                evidence=f"Found {len(test_items)} test item(s) in {test_file.name}.",
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q4,
            passed=False,
            evidence="Test file exists but contains no test functions or classes.",
            severity="P2",
            details=details,
        )

    # -- Q5 ------------------------------------------------------------------

    def check_q5_expected_results(
        self, module_path: str, test_dir: str
    ) -> CheckResult:
        """Q5 – What is the expected result at all points of operation?

        Checks that the test file uses ``assert`` statements, which encode
        the expected results.
        """
        logger.info("Q5: checking expected-result assertions for %s", module_path)
        test_file = _get_test_path(module_path, test_dir)
        details: Dict[str, Any] = {
            "module_path": module_path,
            "expected_test_file": str(test_file),
        }

        if not test_file.exists():
            return CheckResult(
                question=CommissioningQuestion.Q5,
                passed=False,
                evidence=f"Test file not found: {test_file}",
                severity="P1",
                details=details,
            )

        try:
            tree = _parse_module(str(test_file))
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q5,
                passed=False,
                evidence=f"Test file has syntax errors: {exc}",
                severity="P1",
                details={**details, "error": str(exc)},
            )

        assert_count = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.Assert)
        )
        details["assert_count"] = assert_count

        if assert_count > 0:
            return CheckResult(
                question=CommissioningQuestion.Q5,
                passed=True,
                evidence=f"Found {assert_count} assert statement(s) in tests.",
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q5,
            passed=False,
            evidence="No assert statements found – expected results not encoded.",
            severity="P2",
            details=details,
        )

    # -- Q6 ------------------------------------------------------------------

    def check_q6_actual_results(
        self, module_path: str, test_dir: str
    ) -> CheckResult:
        """Q6 – What is the actual result?

        Runs ``pytest --collect-only`` to verify tests are discoverable
        without executing them.
        """
        logger.info("Q6: verifying test discoverability for %s", module_path)
        test_file = _get_test_path(module_path, test_dir)
        details: Dict[str, Any] = {
            "module_path": module_path,
            "expected_test_file": str(test_file),
        }

        if not test_file.exists():
            return CheckResult(
                question=CommissioningQuestion.Q6,
                passed=False,
                evidence=f"Test file not found: {test_file}",
                severity="P1",
                details=details,
            )

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--collect-only", "-q", str(test_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            details["returncode"] = result.returncode
            details["stdout"] = result.stdout[:500]
            details["stderr"] = result.stderr[:500]

            if result.returncode == 0:
                return CheckResult(
                    question=CommissioningQuestion.Q6,
                    passed=True,
                    evidence="pytest --collect-only succeeded; tests are discoverable.",
                    severity="P4",
                    details=details,
                )
            return CheckResult(
                question=CommissioningQuestion.Q6,
                passed=False,
                evidence=(
                    f"pytest --collect-only failed (rc={result.returncode}). "
                    f"stderr: {result.stderr[:200]}"
                ),
                severity="P1",
                details=details,
            )
        except FileNotFoundError:
            return CheckResult(
                question=CommissioningQuestion.Q6,
                passed=False,
                evidence="pytest not found on PATH – cannot verify test discovery.",
                severity="P2",
                details=details,
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                question=CommissioningQuestion.Q6,
                passed=False,
                evidence="pytest --collect-only timed out after 60 s.",
                severity="P1",
                details=details,
            )

    # -- Q7 ------------------------------------------------------------------

    def check_q7_restart_procedure(self, module_path: str) -> CheckResult:
        """Q7 – If problems remain, how do we restart from symptoms?

        Checks for error-recovery patterns: try/except blocks that include
        logging calls (indicating structured recovery/diagnostic paths).
        """
        logger.info("Q7: checking restart/recovery patterns for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}
        try:
            tree = _parse_module(module_path)
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q7,
                passed=False,
                evidence=f"Cannot parse module: {exc}",
                severity="P0",
                details={**details, "error": str(exc)},
            )

        logging_names = {"logger", "logging", "log"}
        recovery_count = 0

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                for child in ast.walk(handler):
                    if isinstance(child, ast.Attribute) and isinstance(
                        child.value, ast.Name
                    ):
                        if child.value.id in logging_names:
                            recovery_count += 1
                            break
                    if isinstance(child, ast.Call) and isinstance(
                        child.func, ast.Attribute
                    ):
                        if (
                            isinstance(child.func.value, ast.Name)
                            and child.func.value.id in logging_names
                        ):
                            recovery_count += 1
                            break

        details["recovery_pattern_count"] = recovery_count

        if recovery_count > 0:
            return CheckResult(
                question=CommissioningQuestion.Q7,
                passed=True,
                evidence=(
                    f"Found {recovery_count} except handler(s) with logging "
                    f"(error-recovery patterns)."
                ),
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q7,
            passed=False,
            evidence=(
                "No except handlers with logging found – "
                "restart/recovery traceability is missing."
            ),
            severity="P2",
            details=details,
        )

    # -- Q8 ------------------------------------------------------------------

    def check_q8_documentation(self, module_path: str) -> CheckResult:
        """Q8 – Has all ancillary code and documentation been updated?

        Checks that every public function and class has a docstring.
        """
        logger.info("Q8: checking public-API docstrings for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}
        try:
            tree = _parse_module(module_path)
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q8,
                passed=False,
                evidence=f"Cannot parse module: {exc}",
                severity="P0",
                details={**details, "error": str(exc)},
            )

        public_nodes = _count_functions_and_classes(tree)
        missing: List[str] = []
        for node in public_nodes:
            if not ast.get_docstring(node):
                missing.append(node.name)

        details["public_count"] = len(public_nodes)
        details["missing_docstrings"] = missing

        if not missing:
            return CheckResult(
                question=CommissioningQuestion.Q8,
                passed=True,
                evidence=(
                    f"All {len(public_nodes)} public function(s)/class(es) "
                    f"have docstrings."
                ),
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q8,
            passed=False,
            evidence=(
                f"{len(missing)} public item(s) lack docstrings: "
                f"{', '.join(missing)}"
            ),
            severity="P3",
            details=details,
        )

    # -- Q9 ------------------------------------------------------------------

    def check_q9_hardening(self, module_path: str) -> CheckResult:
        """Q9 – Has hardening been applied?

        Checks for:
        - Input validation (``isinstance``, ``raise ValueError/TypeError``)
        - Type hints on function signatures
        - Error-code patterns (``MODULE-ERR-`` string literals)
        - Logging usage
        """
        logger.info("Q9: checking hardening for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}
        try:
            tree = _parse_module(module_path)
        except SyntaxError as exc:
            return CheckResult(
                question=CommissioningQuestion.Q9,
                passed=False,
                evidence=f"Cannot parse module: {exc}",
                severity="P0",
                details={**details, "error": str(exc)},
            )

        source = Path(module_path).read_text(encoding="utf-8")

        # --- input validation ---
        has_isinstance = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            for node in ast.walk(tree)
        )
        has_raise_validation = any(
            isinstance(node, ast.Raise)
            and node.exc is not None
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id in {"ValueError", "TypeError"}
            for node in ast.walk(tree)
        )

        # --- type hints ---
        funcs = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        annotated_funcs = sum(
            1
            for f in funcs
            if f.returns is not None
            or any(a.annotation is not None for a in f.args.args)
        )
        type_hint_ratio = annotated_funcs / max(len(funcs), 1)

        # --- error codes ---
        has_error_codes = "MODULE-ERR-" in source

        # --- logging ---
        has_logging = any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"logger", "logging", "log"}
            for node in ast.walk(tree)
        )

        checks_passed = {
            "input_validation": has_isinstance or has_raise_validation,
            "type_hints": type_hint_ratio >= 0.5,
            "error_codes": has_error_codes,
            "logging": has_logging,
        }
        details["hardening_checks"] = checks_passed
        details["type_hint_ratio"] = round(type_hint_ratio, 2)
        passed_count = sum(checks_passed.values())

        if passed_count >= 3:
            return CheckResult(
                question=CommissioningQuestion.Q9,
                passed=True,
                evidence=(
                    f"Hardening adequate: {passed_count}/4 checks passed "
                    f"({', '.join(k for k, v in checks_passed.items() if v)})."
                ),
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q9,
            passed=False,
            evidence=(
                f"Hardening insufficient: only {passed_count}/4 checks passed. "
                f"Missing: {', '.join(k for k, v in checks_passed.items() if not v)}."
            ),
            severity="P2",
            details=details,
        )

    # -- Q10 -----------------------------------------------------------------

    def check_q10_recommissioned(self, module_path: str, test_dir: str = "") -> CheckResult:
        """Q10 – Has the module been re-commissioned after changes?

        Compares the module's last-modification time against its test file's
        last-modification time.  If the test file was modified at the same
        time or later, the module is considered re-commissioned.
        """
        logger.info("Q10: checking re-commission status for %s", module_path)
        details: Dict[str, Any] = {"module_path": module_path}

        if not os.path.exists(module_path):
            return CheckResult(
                question=CommissioningQuestion.Q10,
                passed=False,
                evidence=f"Module file not found: {module_path}",
                severity="P0",
                details=details,
            )

        test_file = _get_test_path(module_path, test_dir) if test_dir else None

        if test_file is None or not test_file.exists():
            return CheckResult(
                question=CommissioningQuestion.Q10,
                passed=False,
                evidence="Cannot verify re-commission: no test file found.",
                severity="P2",
                details=details,
            )

        mod_mtime = os.path.getmtime(module_path)
        test_mtime = os.path.getmtime(str(test_file))
        details["module_mtime"] = mod_mtime
        details["test_mtime"] = test_mtime

        if test_mtime >= mod_mtime:
            return CheckResult(
                question=CommissioningQuestion.Q10,
                passed=True,
                evidence=(
                    "Test file modified at or after module – "
                    "re-commissioning evidence present."
                ),
                severity="P4",
                details=details,
            )
        return CheckResult(
            question=CommissioningQuestion.Q10,
            passed=False,
            evidence=(
                "Module was modified after its test file – "
                "re-commissioning may be needed."
            ),
            severity="P3",
            details=details,
        )

    # -- Aggregate -----------------------------------------------------------

    def commission_module(
        self,
        module_path: str,
        test_dir: str,
        commissioned_by: str,
    ) -> ModuleCommissionReport:
        """Run all 10 commissioning checks and return a full report.

        Args:
            module_path: Path to the Python module under validation.
            test_dir: Directory containing the module's test files.
            commissioned_by: Name or handle of the person commissioning.

        Returns:
            A ``ModuleCommissionReport`` with every check result.
        """
        logger.info(
            "Commissioning module %s (by %s)", module_path, commissioned_by
        )

        results: List[CheckResult] = [
            self.check_q1_functionality(module_path),
            self.check_q2_purpose(module_path),
            self.check_q3_conditions(module_path),
            self.check_q4_test_coverage(module_path, test_dir),
            self.check_q5_expected_results(module_path, test_dir),
            self.check_q6_actual_results(module_path, test_dir),
            self.check_q7_restart_procedure(module_path),
            self.check_q8_documentation(module_path),
            self.check_q9_hardening(module_path),
            self.check_q10_recommissioned(module_path, test_dir),
        ]

        overall_pass = all(r.passed for r in results)
        now_iso = datetime.now(timezone.utc).isoformat()

        report = ModuleCommissionReport(
            module_name=Path(module_path).stem,
            module_path=module_path,
            results=results,
            commissioned_by=commissioned_by,
            commissioned_at=now_iso,
            overall_pass=overall_pass,
        )
        logger.info(
            "Commission complete for %s – overall_pass=%s",
            module_path,
            overall_pass,
        )
        return report

    # -- Markdown report -----------------------------------------------------

    @staticmethod
    def generate_report_markdown(report: ModuleCommissionReport) -> str:
        """Produce a Markdown commissioning report from *report*.

        Args:
            report: A completed ``ModuleCommissionReport``.

        Returns:
            A Markdown-formatted string suitable for embedding in a PR
            description or documentation.
        """
        status = "✅ PASSED" if report.overall_pass else "❌ FAILED"
        lines: List[str] = [
            f"# Commissioning Report – {report.module_name}",
            "",
            f"**File:** `{report.module_path}`  ",
            f"**Commissioned by:** {report.commissioned_by}  ",
            f"**Date:** {report.commissioned_at}  ",
            f"**Overall:** {status}",
            "",
            "## Results",
            "",
            "| # | Question | Passed | Severity | Evidence |",
            "|---|----------|--------|----------|----------|",
        ]

        for idx, result in enumerate(report.results, start=1):
            icon = "✅" if result.passed else "❌"
            question_short = result.question.value
            if len(question_short) > 60:
                question_short = question_short[:57] + "..."
            lines.append(
                f"| Q{idx} | {question_short} | {icon} | "
                f"{result.severity} | {result.evidence} |"
            )

        lines.extend(
            [
                "",
                "## Severity Legend",
                "",
                "| Level | Meaning |",
                "|-------|---------|",
                "| P0 | Blocker – module does not function at all |",
                "| P1 | Critical – core functionality broken or missing |",
                "| P2 | Major – important feature incomplete or unreliable |",
                "| P3 | Minor – edge case or polish issue |",
                "| P4 | Cosmetic – documentation or naming only |",
                "",
                "---",
                f"*Design Label: COMMISSION-VAL-001*",
            ]
        )

        return "\n".join(lines)

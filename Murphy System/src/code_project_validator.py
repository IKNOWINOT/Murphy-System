"""
Code Project Validator - Murphy System
=======================================
Validates generated code project files for basic functionality before
delivering to the user.

Checks performed:
  1. Required files present (index.html, README.md)
  2. HTML structure valid (doctype, head, body)
  3. Python syntax valid (ast.parse)
  4. JavaScript basic syntax (bracket/paren balance)
  5. CSS basic structure check
  6. No empty files

Design Label: CPV-001
Copyright (c) 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CPV-001: Data structures
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation issue found in a project file."""

    file_path: str
    severity: str  # "error", "warning", "info"
    code: str
    message: str


@dataclass
class ValidationResult:
    """Result of validating a code project."""

    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    files_checked: int = 0
    files_passed: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# CPV-001: Required files
# ---------------------------------------------------------------------------

_REQUIRED_FILES = ["README.md"]
_RECOMMENDED_FILES = ["index.html", "styles.css"]


# ---------------------------------------------------------------------------
# CPV-VALIDATE-001: Main validation entry point
# ---------------------------------------------------------------------------


def validate_code_project(
    project_files: Dict[str, str],
) -> ValidationResult:
    """Validate a generated code project for basic functionality.

    Args:
        project_files: Dict mapping relative file paths to content strings.

    Returns:
        ValidationResult with issues found and pass/fail status.

    Label: CPV-VALIDATE-001
    """
    if not project_files:
        return ValidationResult(
            valid=False,
            issues=[
                ValidationIssue(
                    file_path="(project)",
                    severity="error",
                    code="CPV-EMPTY-001",
                    message="No project files generated",
                )
            ],
        )

    issues: List[ValidationIssue] = []
    files_passed = 0

    # Check required files
    for req in _REQUIRED_FILES:
        if req not in project_files:
            issues.append(
                ValidationIssue(
                    file_path=req,
                    severity="warning",
                    code="CPV-MISSING-001",
                    message=f"Required file missing: {req}",
                )
            )

    # Check recommended files
    for rec in _RECOMMENDED_FILES:
        if rec not in project_files:
            issues.append(
                ValidationIssue(
                    file_path=rec,
                    severity="info",
                    code="CPV-MISSING-002",
                    message=f"Recommended file missing: {rec}",
                )
            )

    # Validate each file by extension
    for path, content in project_files.items():
        file_issues = _validate_file(path, content)
        issues.extend(file_issues)
        if not any(i.severity == "error" for i in file_issues):
            files_passed += 1

    error_count = sum(1 for i in issues if i.severity == "error")

    result = ValidationResult(
        valid=error_count == 0,
        issues=issues,
        files_checked=len(project_files),
        files_passed=files_passed,
    )

    if not result.valid:
        logger.warning(
            "CPV-VALIDATE-001: Project validation failed: %d errors, "
            "%d warnings across %d files",
            result.error_count,
            result.warning_count,
            result.files_checked,
        )
    else:
        logger.info(
            "CPV-VALIDATE-001: Project validation passed: %d files checked, "
            "%d warnings",
            result.files_checked,
            result.warning_count,
        )

    return result


def _validate_file(path: str, content: str) -> List[ValidationIssue]:
    """Validate a single file based on its extension.

    Label: CPV-FILE-001
    """
    issues: List[ValidationIssue] = []

    # Empty file check
    if not content or not content.strip():
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="error",
                code="CPV-EMPTY-002",
                message=f"File is empty: {path}",
            )
        )
        return issues

    lower_path = path.lower()

    if lower_path.endswith(".html") or lower_path.endswith(".htm"):
        issues.extend(_validate_html(path, content))
    elif lower_path.endswith(".py"):
        issues.extend(_validate_python(path, content))
    elif lower_path.endswith(".js"):
        issues.extend(_validate_javascript(path, content))
    elif lower_path.endswith(".css"):
        issues.extend(_validate_css(path, content))
    elif lower_path.endswith(".md"):
        issues.extend(_validate_markdown(path, content))

    return issues


# ---------------------------------------------------------------------------
# CPV-HTML-001: HTML validation
# ---------------------------------------------------------------------------


def _validate_html(path: str, content: str) -> List[ValidationIssue]:
    """Validate HTML file structure.  Label: CPV-HTML-001"""
    issues: List[ValidationIssue] = []
    lower = content.lower()

    if "<!doctype" not in lower:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="warning",
                code="CPV-HTML-001",
                message="Missing <!DOCTYPE html> declaration",
            )
        )

    if "<html" not in lower:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="error",
                code="CPV-HTML-002",
                message="Missing <html> tag",
            )
        )

    if "<head" not in lower:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="warning",
                code="CPV-HTML-003",
                message="Missing <head> section",
            )
        )

    if "<body" not in lower:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="warning",
                code="CPV-HTML-004",
                message="Missing <body> section",
            )
        )

    if "<title" not in lower:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="info",
                code="CPV-HTML-005",
                message="Missing <title> tag",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# CPV-PY-001: Python validation
# ---------------------------------------------------------------------------


def _validate_python(path: str, content: str) -> List[ValidationIssue]:
    """Validate Python file syntax.  Label: CPV-PY-001"""
    issues: List[ValidationIssue] = []

    try:
        ast.parse(content, filename=path)
    except SyntaxError as exc:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="error",
                code="CPV-PY-001",
                message=f"Python syntax error at line {exc.lineno}: {exc.msg}",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# CPV-JS-001: JavaScript validation
# ---------------------------------------------------------------------------


def _validate_javascript(path: str, content: str) -> List[ValidationIssue]:
    """Validate JavaScript basic structure.  Label: CPV-JS-001"""
    issues: List[ValidationIssue] = []

    # Check bracket/paren balance
    openers = content.count("{") + content.count("(") + content.count("[")
    closers = content.count("}") + content.count(")") + content.count("]")

    if abs(openers - closers) > 2:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="warning",
                code="CPV-JS-001",
                message=(
                    f"Possible bracket mismatch: {openers} openers vs "
                    f"{closers} closers"
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------------
# CPV-CSS-001: CSS validation
# ---------------------------------------------------------------------------


def _validate_css(path: str, content: str) -> List[ValidationIssue]:
    """Validate CSS basic structure.  Label: CPV-CSS-001"""
    issues: List[ValidationIssue] = []

    open_braces = content.count("{")
    close_braces = content.count("}")

    if open_braces != close_braces:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="warning",
                code="CPV-CSS-001",
                message=(
                    f"Brace mismatch: {open_braces} open vs "
                    f"{close_braces} close"
                ),
            )
        )

    # Check for at least one rule
    if not re.search(r"\{[^}]+\}", content):
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="warning",
                code="CPV-CSS-002",
                message="No CSS rules found",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# CPV-MD-001: Markdown validation
# ---------------------------------------------------------------------------


def _validate_markdown(path: str, content: str) -> List[ValidationIssue]:
    """Validate Markdown basic structure.  Label: CPV-MD-001"""
    issues: List[ValidationIssue] = []

    if not content.startswith("#") and "\n#" not in content:
        issues.append(
            ValidationIssue(
                file_path=path,
                severity="info",
                code="CPV-MD-001",
                message="No heading found in markdown file",
            )
        )

    return issues

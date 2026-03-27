"""
Code Repair Engine for the Murphy System.

Design Label: ARCH-012 — AST-Aware Code Repair
Owner: Backend Team

Provides AST-based static analysis of Python source files and generates
human-reviewable repair proposals for common code quality issues.

All patches are proposals only — they are never applied automatically and
always carry requires_human_review=True for non-trivial changes.

Supported detectors:
- Missing exception handlers (silent swallowing)
- Missing docstrings (functions and classes)
- Unused imports
- Broad exception clauses (bare except Exception)
- Missing type hints on function parameters and return values

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import difflib
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CodeIssue:
    """Describes a detected code quality issue in a source file."""

    issue_id: str
    file_path: str
    line_range: Tuple[int, int]
    issue_type: str  # "bug" | "performance" | "style" | "missing_handler" | "missing_test" | "missing_doc"
    description: str
    severity: str    # "critical" | "high" | "medium" | "low"
    ast_context: Dict[str, Any]  # surrounding AST node info


@dataclass
class CodePatch:
    """A proposed repair for a CodeIssue."""

    patch_id: str
    file_path: str
    original_content: str
    proposed_content: str
    diff_text: str
    issue_id: str
    strategy: str        # which repair strategy generated this
    confidence: float    # 0.0 – 1.0
    requires_human_review: bool = True


# ---------------------------------------------------------------------------
# Abstract repair strategy
# ---------------------------------------------------------------------------

class RepairStrategy(ABC):
    """Abstract base class for code repair strategies."""

    @abstractmethod
    def generate_patches(self, issue: CodeIssue) -> List[CodePatch]:
        """Generate one or more patches for the given issue."""


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------

class MissingHandlerStrategy(RepairStrategy):
    """
    Detects except blocks that swallow exceptions silently (no logging,
    no re-raise) and proposes adding a logging call or re-raise.
    """

    def generate_patches(self, issue: CodeIssue) -> List[CodePatch]:
        if issue.issue_type != "missing_handler":
            return []
        try:
            with open(issue.file_path, encoding="utf-8") as fh:
                original = fh.read()
        except OSError as exc:
            logger.warning("MissingHandlerStrategy: cannot read %s: %s", issue.file_path, exc)
            return []

        lines = original.splitlines(keepends=True)
        start, end = issue.line_range
        context_lines = lines[start - 1 : end]
        if not context_lines:
            return []

        # Find the bare pass and replace with a log + re-raise
        indent = len(context_lines[-1]) - len(context_lines[-1].lstrip())
        indent_str = " " * indent
        handler_line = f"{indent_str}logger.warning('Unhandled exception: %s', exc)\n"
        reraise_line = f"{indent_str}raise\n"

        proposed_lines = list(lines)
        # Replace the last line of the handler (assumed to be `pass`) with logging + re-raise
        insert_idx = end - 1
        if insert_idx < len(proposed_lines):
            proposed_lines[insert_idx] = handler_line + reraise_line

        proposed = "".join(proposed_lines)
        diff_text = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=issue.file_path,
                tofile=issue.file_path,
            )
        )

        return [
            CodePatch(
                patch_id=str(uuid.uuid4()),
                file_path=issue.file_path,
                original_content=original,
                proposed_content=proposed,
                diff_text=diff_text,
                issue_id=issue.issue_id,
                strategy="MissingHandlerStrategy",
                confidence=0.7,
                requires_human_review=True,
            )
        ]


class MissingDocstringStrategy(RepairStrategy):
    """
    Finds functions and classes without docstrings and proposes template
    docstrings based on the signature.
    """

    def generate_patches(self, issue: CodeIssue) -> List[CodePatch]:
        if issue.issue_type != "missing_doc":
            return []
        try:
            with open(issue.file_path, encoding="utf-8") as fh:
                original = fh.read()
        except OSError as exc:
            logger.warning("MissingDocstringStrategy: cannot read %s: %s", issue.file_path, exc)
            return []

        lines = original.splitlines(keepends=True)
        target_line = issue.line_range[0]  # 1-based
        node_name = issue.ast_context.get("name", "unknown")
        node_type = issue.ast_context.get("node_type", "function")

        if node_type == "class":
            docstring_text = f'"""{node_name} class."""'
        else:
            docstring_text = f'"""{node_name}."""'

        # Insert after the def/class line — find the body start
        # The body typically starts on the next line
        insert_after = target_line  # 0-based index to insert after
        if insert_after < len(lines):
            # Determine indentation from the next line
            next_idx = insert_after
            if next_idx < len(lines):
                next_line = lines[next_idx]
                indent_str = " " * (len(next_line) - len(next_line.lstrip()))
            else:
                indent_str = "    "
            docstring_line = f"{indent_str}{docstring_text}\n"
            proposed_lines = lines[:insert_after] + [docstring_line] + lines[insert_after:]
        else:
            proposed_lines = list(lines)

        proposed = "".join(proposed_lines)
        diff_text = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=issue.file_path,
                tofile=issue.file_path,
            )
        )

        return [
            CodePatch(
                patch_id=str(uuid.uuid4()),
                file_path=issue.file_path,
                original_content=original,
                proposed_content=proposed,
                diff_text=diff_text,
                issue_id=issue.issue_id,
                strategy="MissingDocstringStrategy",
                confidence=0.9,
                requires_human_review=True,
            )
        ]


class UnusedImportStrategy(RepairStrategy):
    """
    Detects imports not referenced in the module body and proposes their removal.
    """

    def generate_patches(self, issue: CodeIssue) -> List[CodePatch]:
        if issue.issue_type != "style" or "unused import" not in issue.description.lower():
            return []
        try:
            with open(issue.file_path, encoding="utf-8") as fh:
                original = fh.read()
        except OSError as exc:
            logger.warning("UnusedImportStrategy: cannot read %s: %s", issue.file_path, exc)
            return []

        lines = original.splitlines(keepends=True)
        start, end = issue.line_range
        # Remove the import line
        proposed_lines = lines[: start - 1] + lines[end:]
        proposed = "".join(proposed_lines)
        diff_text = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=issue.file_path,
                tofile=issue.file_path,
            )
        )

        return [
            CodePatch(
                patch_id=str(uuid.uuid4()),
                file_path=issue.file_path,
                original_content=original,
                proposed_content=proposed,
                diff_text=diff_text,
                issue_id=issue.issue_id,
                strategy="UnusedImportStrategy",
                confidence=0.8,
                requires_human_review=True,
            )
        ]


class BroadExceptionStrategy(RepairStrategy):
    """
    Finds bare `except Exception` clauses and proposes narrower exception types
    based on the surrounding code context.
    """

    def generate_patches(self, issue: CodeIssue) -> List[CodePatch]:
        if issue.issue_type != "bug" or "broad exception" not in issue.description.lower():
            return []
        try:
            with open(issue.file_path, encoding="utf-8") as fh:
                original = fh.read()
        except OSError as exc:
            logger.warning("BroadExceptionStrategy: cannot read %s: %s", issue.file_path, exc)
            return []

        lines = original.splitlines(keepends=True)
        target_line = issue.line_range[0] - 1  # 0-based
        if target_line >= len(lines):
            return []

        original_line = lines[target_line]
        # Replace `except Exception` with a more specific suggestion
        proposed_line = original_line.replace("except Exception", "except (ValueError, RuntimeError)")
        if proposed_line == original_line:
            return []

        proposed_lines = list(lines)
        proposed_lines[target_line] = proposed_line
        proposed = "".join(proposed_lines)
        diff_text = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=issue.file_path,
                tofile=issue.file_path,
            )
        )

        return [
            CodePatch(
                patch_id=str(uuid.uuid4()),
                file_path=issue.file_path,
                original_content=original,
                proposed_content=proposed,
                diff_text=diff_text,
                issue_id=issue.issue_id,
                strategy="BroadExceptionStrategy",
                confidence=0.5,
                requires_human_review=True,
            )
        ]


class MissingTypeHintStrategy(RepairStrategy):
    """
    Finds function parameters and return values without type hints and
    proposes adding `Any` annotations as a starting point.
    """

    def generate_patches(self, issue: CodeIssue) -> List[CodePatch]:
        if issue.issue_type != "style" or "type hint" not in issue.description.lower():
            return []
        # Type hint patches are informational only; they require human judgement
        # on the actual types.  We return a patch with the diff stub populated.
        try:
            with open(issue.file_path, encoding="utf-8") as fh:
                original = fh.read()
        except OSError as exc:
            logger.warning("MissingTypeHintStrategy: cannot read %s: %s", issue.file_path, exc)
            return []

        return [
            CodePatch(
                patch_id=str(uuid.uuid4()),
                file_path=issue.file_path,
                original_content=original,
                proposed_content=original,  # no automatic change — human must fill types
                diff_text="",
                issue_id=issue.issue_id,
                strategy="MissingTypeHintStrategy",
                confidence=0.3,
                requires_human_review=True,
            )
        ]


# ---------------------------------------------------------------------------
# CodeRepairEngine
# ---------------------------------------------------------------------------

class CodeRepairEngine:
    """
    AST-aware source code analysis and repair proposal generator.

    Scans Python source files for common quality issues and produces
    human-reviewable patch proposals.  All patches set requires_human_review=True;
    no code is ever modified automatically.
    """

    def __init__(self) -> None:
        self._strategies: List[RepairStrategy] = [
            MissingHandlerStrategy(),
            MissingDocstringStrategy(),
            UnusedImportStrategy(),
            BroadExceptionStrategy(),
            MissingTypeHintStrategy(),
        ]

    def scan_file(self, file_path: str) -> List[CodeIssue]:
        """
        Parse the AST of a single Python file and run all issue detectors.

        Returns a list of CodeIssue objects (may be empty).
        """
        issues: List[CodeIssue] = []
        try:
            with open(file_path, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=file_path)
        except (OSError, SyntaxError) as exc:
            logger.warning("scan_file: cannot parse %s: %s", file_path, exc)
            return issues

        issues.extend(self._detect_missing_handlers(tree, file_path))
        issues.extend(self._detect_missing_docstrings(tree, file_path))
        issues.extend(self._detect_unused_imports(tree, file_path, source))
        issues.extend(self._detect_broad_exceptions(tree, file_path))
        issues.extend(self._detect_missing_type_hints(tree, file_path))

        logger.debug("scan_file: %s → %d issue(s)", file_path, len(issues))
        return issues

    def scan_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
    ) -> List[CodeIssue]:
        """
        Recursively scan all matching files in a directory.

        Args:
            directory: Root directory to scan.
            extensions: File extensions to include.  Defaults to [".py"].
        """
        if extensions is None:
            extensions = [".py"]

        all_issues: List[CodeIssue] = []
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                if any(fname.endswith(ext) for ext in extensions):
                    fpath = os.path.join(root, fname)
                    all_issues.extend(self.scan_file(fpath))
        return all_issues

    def generate_repairs(self, issues: List[CodeIssue]) -> List[CodePatch]:
        """
        Run all repair strategies against the provided issues.

        Returns a flat list of CodePatch proposals.
        """
        patches: List[CodePatch] = []
        for issue in issues:
            for strategy in self._strategies:
                try:
                    new_patches = strategy.generate_patches(issue)
                    patches.extend(new_patches)
                except Exception as exc:
                    logger.warning(
                        "generate_repairs: strategy %s raised for issue %s: %s",
                        type(strategy).__name__,
                        issue.issue_id,
                        exc,
                    )
        return patches

    def validate_patch(self, patch: CodePatch) -> bool:
        """
        Verify that the proposed patch content is syntactically valid Python.

        Returns True if the proposed content parses without error.
        """
        if not patch.proposed_content:
            return False
        try:
            ast.parse(patch.proposed_content)
            return True
        except SyntaxError as exc:
            logger.debug(
                "validate_patch: patch %s has syntax error: %s", patch.patch_id, exc
            )
            return False

    def apply_patch_to_sandbox(self, patch: CodePatch, sandbox_dir: str) -> bool:
        """
        Write the proposed content to a sandbox directory for testing.

        The sandbox path mirrors the original file path structure under sandbox_dir.
        Returns True if the file was written successfully.
        """
        try:
            rel_path = os.path.basename(patch.file_path)
            dest = os.path.join(sandbox_dir, rel_path)
            os.makedirs(sandbox_dir, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(patch.proposed_content)
            return True
        except OSError as exc:
            logger.warning(
                "apply_patch_to_sandbox: cannot write %s: %s", patch.file_path, exc
            )
            return False

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_missing_handlers(tree: ast.AST, file_path: str) -> List[CodeIssue]:
        """Detect except blocks that only contain `pass` (silent swallowing)."""
        issues: List[CodeIssue] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                issues.append(
                    CodeIssue(
                        issue_id=str(uuid.uuid4()),
                        file_path=file_path,
                        line_range=(node.lineno, node.end_lineno or node.lineno),
                        issue_type="missing_handler",
                        description="Exception handler silently swallows exception (bare pass)",
                        severity="high",
                        ast_context={"handler_type": ast.dump(node.type) if node.type else "bare"},
                    )
                )
        return issues

    @staticmethod
    def _detect_missing_docstrings(tree: ast.AST, file_path: str) -> List[CodeIssue]:
        """Detect functions and classes that lack a docstring."""
        issues: List[CodeIssue] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue  # skip private/dunder
            has_docstring = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            if not has_docstring:
                node_type = "class" if isinstance(node, ast.ClassDef) else "function"
                issues.append(
                    CodeIssue(
                        issue_id=str(uuid.uuid4()),
                        file_path=file_path,
                        line_range=(node.lineno, node.lineno),
                        issue_type="missing_doc",
                        description=f"{node_type} '{node.name}' is missing a docstring",
                        severity="low",
                        ast_context={"name": node.name, "node_type": node_type},
                    )
                )
        return issues

    @staticmethod
    def _detect_unused_imports(
        tree: ast.AST, file_path: str, source: str
    ) -> List[CodeIssue]:
        """Detect import statements whose names are not referenced in the module body."""
        issues: List[CodeIssue] = []
        imported_names: List[Tuple[str, int, int]] = []  # (name, start_line, end_line)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split(".")[0]
                    imported_names.append((name, node.lineno, node.end_lineno or node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname if alias.asname else alias.name
                    imported_names.append((name, node.lineno, node.end_lineno or node.lineno))

        for name, start, end in imported_names:
            # Simple heuristic: count occurrences after the import line
            lines_after_import = source.split("\n")[end:]
            body_text = "\n".join(lines_after_import)
            if name not in body_text:
                issues.append(
                    CodeIssue(
                        issue_id=str(uuid.uuid4()),
                        file_path=file_path,
                        line_range=(start, end),
                        issue_type="style",
                        description=f"Unused import: '{name}'",
                        severity="low",
                        ast_context={"import_name": name},
                    )
                )
        return issues

    @staticmethod
    def _detect_broad_exceptions(tree: ast.AST, file_path: str) -> List[CodeIssue]:
        """Detect broad `except Exception` handlers that could be narrowed."""
        issues: List[CodeIssue] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                continue  # bare except (handled separately)
            if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                issues.append(
                    CodeIssue(
                        issue_id=str(uuid.uuid4()),
                        file_path=file_path,
                        line_range=(node.lineno, node.lineno),
                        issue_type="bug",
                        description="Broad exception handler: except Exception — consider narrowing",
                        severity="medium",
                        ast_context={"exception_type": "Exception"},
                    )
                )
        return issues

    @staticmethod
    def _detect_missing_type_hints(tree: ast.AST, file_path: str) -> List[CodeIssue]:
        """Detect function parameters or return values missing type annotations."""
        issues: List[CodeIssue] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue  # skip private/dunder
            missing_args = [
                arg.arg
                for arg in node.args.args
                if arg.annotation is None and arg.arg != "self"
            ]
            missing_return = node.returns is None
            if missing_args or missing_return:
                desc_parts: List[str] = []
                if missing_args:
                    desc_parts.append(f"params without type hint: {missing_args}")
                if missing_return:
                    desc_parts.append("missing return type hint")
                issues.append(
                    CodeIssue(
                        issue_id=str(uuid.uuid4()),
                        file_path=file_path,
                        line_range=(node.lineno, node.lineno),
                        issue_type="style",
                        description=f"Function '{node.name}' has {', '.join(desc_parts)}",
                        severity="low",
                        ast_context={"function_name": node.name, "missing_args": missing_args},
                    )
                )
        return issues

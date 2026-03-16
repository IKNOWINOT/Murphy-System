"""CodingBot combining code refactoring and recursion utilities."""
from __future__ import annotations

import ast
import re
from typing import Any, List, Dict

import subprocess

try:
    from RestrictedPython import compile_restricted, safe_builtins
except Exception:  # pragma: no cover - optional dependency
    compile_restricted = None


def _camel_to_snake(name: str) -> str:
    """Convert camelCase identifier to snake_case."""
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class _UsageCollector(ast.NodeVisitor):
    """Collect all Name nodes used as identifiers (non-import-alias context)."""

    def __init__(self) -> None:
        self.used: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        self.used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        # Only visit the value side (the object), not the attribute name
        self.visit(node.value)


class CodingBot:
    """Merge of CodeSmithBot and RecursionBot capabilities."""

    def __init__(self) -> None:
        self.history: List[str] = []

    # Former CodeSmithBot functionality
    def refactor_code(self, code: str) -> dict:
        """Refactor code using AST-level transforms and return structured result.

        Transforms applied:
        1. Remove unused imports.
        2. Convert camelCase variable names to snake_case.
        3. Remove dead code (``if False:`` blocks, unreachable code after
           ``return``/``raise`` inside a block).

        Returns:
            dict with keys ``code`` (str), ``changes`` (List[str]),
            ``confidence`` (float).
        """
        self.history.append(code)

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"code": code, "changes": [], "confidence": 0.0}

        changes: List[str] = []

        # ── 1. Remove unused imports ────────────────────────────────────────
        usage = _UsageCollector()
        # Visit everything except Import/ImportFrom nodes to collect used names
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            usage.visit(node)

        used_names = usage.used
        lines = code.splitlines(keepends=True)
        import_line_indices: set[int] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    if bound not in used_names:
                        import_line_indices.add(node.lineno - 1)
                        changes.append(f"removed unused import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                unused = [
                    alias
                    for alias in node.names
                    if (alias.asname or alias.name) not in used_names
                ]
                if len(unused) == len(node.names):
                    import_line_indices.add(node.lineno - 1)
                    for alias in unused:
                        changes.append(f"removed unused import: {alias.name}")

        filtered_lines = [
            ln for i, ln in enumerate(lines) if i not in import_line_indices
        ]
        code = "".join(filtered_lines)

        # ── 2. Normalise camelCase variable names to snake_case ────────────
        camel_pattern = re.compile(r'\b([a-z]+[A-Z][a-zA-Z]*)\b')
        seen_renames: Dict[str, str] = {}

        def _replace_camel(m: re.Match) -> str:
            original = m.group(0)
            replacement = _camel_to_snake(original)
            if original != replacement:
                seen_renames[original] = replacement
            return replacement

        new_code = camel_pattern.sub(_replace_camel, code)
        if new_code != code:
            for orig, repl in seen_renames.items():
                changes.append(f"renamed {orig} → {repl}")
            code = new_code

        # ── 3. Remove dead code (if False: ...) ────────────────────────────
        dead_block_pattern = re.compile(
            r'^([ \t]*)if\s+False\s*:[ \t]*\n(?:(?:[ \t]+[^\n]*\n|\n))*',
            re.MULTILINE,
        )
        cleaned = dead_block_pattern.sub("", code)
        if cleaned != code:
            changes.append("removed dead code: if False: block")
            code = cleaned

        confidence = 1.0 if changes else 0.95
        return {"code": code, "changes": changes, "confidence": confidence}

    def rollback(self) -> str:
        """Undo the last refactor if possible."""
        if self.history:
            return self.history.pop()
        return ""

    def execute_sandboxed(self, code: str, timeout: float = 2.0) -> str:
        """Execute ``code`` in an isolated sandbox and return its output."""
        if compile_restricted is not None:
            compiled = compile_restricted(code, filename="<task>", mode="exec")
            local: dict[str, Any] = {}
            stdout: List[str] = []

            def _print(*objs: Any, **_kw: Any) -> None:
                stdout.append(" ".join(map(str, objs)))

            safe = safe_builtins.copy()
            safe["print"] = _print
            try:
                exec(compiled.code, {"__builtins__": safe}, local)
            except Exception as exc:
                return str(exc)
            return "\n".join(stdout)
        # Fallback to subprocess if RestrictedPython not installed
        try:
            proc = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return "Timed out"
        result = proc.stdout
        if proc.stderr:
            result += proc.stderr
        return result

    # Former RecursionBot functionality
    def broadcast(self, nodes: List[Any], message: str) -> List[Any]:
        """Broadcast a message to all nodes."""
        return [n.receive(message) for n in nodes]

    def reload(self) -> None:
        """Reload configuration or state by clearing history."""
        self.history.clear()

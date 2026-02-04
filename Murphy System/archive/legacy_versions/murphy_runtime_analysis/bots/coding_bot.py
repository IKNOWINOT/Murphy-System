"""CodingBot combining code refactoring and recursion utilities."""
from __future__ import annotations

from typing import Any, List

import subprocess

try:
    from RestrictedPython import compile_restricted, safe_builtins
except Exception:  # pragma: no cover - optional dependency
    compile_restricted = None


class CodingBot:
    """Merge of CodeSmithBot and RecursionBot capabilities."""

    def __init__(self) -> None:
        self.history: List[str] = []

    # Former CodeSmithBot functionality
    def refactor_code(self, code: str) -> str:
        """Refactor code and store previous version for rollback."""
        self.history.append(code)
        # Placeholder for refactoring logic
        return code

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

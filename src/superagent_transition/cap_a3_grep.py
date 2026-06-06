"""Cap A.3 — grep.

Search file contents with regex. Uses GNU grep -rnE under the hood
(ripgrep would be faster but is not installed; behavior identical).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._path_guard import is_allowed, canonicalize, allowed_roots

MAX_MATCHES = 500
MAX_TIMEOUT_S = 30
LINE_TRUNCATE = 500


def grep(
    pattern: str,
    path: str,
    *,
    include_glob: Optional[str] = None,
    max_matches: int = MAX_MATCHES,
    case_insensitive: bool = False,
    timeout_s: int = MAX_TIMEOUT_S,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "pattern": pattern, "path": path,
        "matches": [], "match_count": 0, "truncated": False,
        "error": None,
    }
    try:
        if not pattern:
            out["error"] = "empty pattern"; return out
        if not path:
            out["error"] = "empty path"; return out
        if not is_allowed(path):
            out["error"] = f"path not under allowed roots: {allowed_roots()}"
            return out
        try:
            re.compile(pattern)
        except re.error as e:
            out["error"] = f"invalid regex: {e}"; return out

        canon = canonicalize(path)
        cmd = ["grep", "-rnE", "--binary-files=without-match"]
        if case_insensitive:
            cmd.append("-i")
        if include_glob:
            cmd.append(f"--include={include_glob}")
        cmd.extend([pattern, canon])

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout_s, errors="replace",
        )
        # grep exits 1 = no matches (not an error), 0 = matches, 2+ = real error
        if result.returncode > 1:
            out["error"] = f"grep error (rc={result.returncode}): {result.stderr.strip()[:200]}"
            return out

        matches = []
        for line in result.stdout.splitlines():
            if ":" not in line:
                continue
            # GNU grep format: path:lineno:content
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            file_path, lineno_str, content = parts
            try:
                lineno = int(lineno_str)
            except ValueError:
                continue
            if len(content) > LINE_TRUNCATE:
                content = content[:LINE_TRUNCATE] + "...[truncated]"
            matches.append({"file": file_path, "line": lineno, "content": content})
            if len(matches) >= max_matches:
                out["truncated"] = True
                break

        out["matches"] = matches
        out["match_count"] = len(matches)
        out["ok"] = True
        return out
    except subprocess.TimeoutExpired:
        out["error"] = f"grep timed out after {timeout_s}s"
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out


def execute_grep(**kwargs) -> Dict[str, Any]:
    return grep(
        pattern=kwargs.get("pattern", ""),
        path=kwargs.get("path", ""),
        include_glob=kwargs.get("include_glob") or kwargs.get("include"),
        max_matches=kwargs.get("max_matches", MAX_MATCHES),
        case_insensitive=kwargs.get("case_insensitive", False),
        timeout_s=kwargs.get("timeout_s", MAX_TIMEOUT_S),
    )

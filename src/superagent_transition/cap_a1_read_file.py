"""Cap A.1 — read_file. (R15: now uses shared _path_guard)"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Optional
from ._path_guard import is_allowed, canonicalize, allowed_roots

MAX_BYTES = 2 * 1024 * 1024
MAX_LINES_RETURNED = 5000


def read_file(file_path: str, max_lines: Optional[int] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "path": file_path, "size_bytes": 0,
        "lines_returned": 0, "truncated": False,
        "content": "", "error": None,
    }
    try:
        if not file_path:
            out["error"] = "empty path"; return out
        if not is_allowed(file_path):
            out["error"] = f"path not under allowed roots: {allowed_roots()}"
            return out
        canon = canonicalize(file_path)
        out["path"] = canon
        if not os.path.exists(canon):
            out["error"] = "file does not exist"; return out
        if not os.path.isfile(canon):
            out["error"] = "path is not a regular file"; return out
        size = os.path.getsize(canon)
        out["size_bytes"] = size
        if size > MAX_BYTES:
            out["error"] = f"file too large: {size} bytes > {MAX_BYTES} max"
            return out
        with open(canon, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        limit = max_lines if max_lines is not None else MAX_LINES_RETURNED
        lines = text.splitlines(keepends=True)
        if len(lines) > limit:
            text = "".join(lines[:limit])
            out["truncated"] = True
            out["lines_returned"] = limit
        else:
            out["lines_returned"] = len(lines)
        out["content"] = text
        out["ok"] = True
        return out
    except PermissionError as e:
        out["error"] = f"permission denied: {e}"; return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_read_file(**kwargs) -> Dict[str, Any]:
    path = kwargs.get("file_path") or kwargs.get("path") or kwargs.get("text", "")
    return read_file(path, max_lines=kwargs.get("max_lines"))

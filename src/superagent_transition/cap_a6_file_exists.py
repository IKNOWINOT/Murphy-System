"""Cap A.6 — file_exists."""
from __future__ import annotations
import os, stat
from typing import Any, Dict
from ._path_guard import is_allowed, canonicalize, allowed_roots


def file_exists(path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "path": path, "exists": False, "kind": None,
        "size_bytes": None, "error": None,
    }
    try:
        if not path:
            out["error"] = "empty path"; return out
        if not is_allowed(path):
            out["error"] = f"path not under allowed roots: {allowed_roots()}"
            return out
        canon = canonicalize(path)
        out["path"] = canon
        if not os.path.lexists(canon):
            out["exists"] = False
            out["ok"] = True
            return out
        st = os.lstat(canon)
        if stat.S_ISDIR(st.st_mode):
            out["kind"] = "dir"
        elif stat.S_ISLNK(st.st_mode):
            out["kind"] = "link"
        elif stat.S_ISREG(st.st_mode):
            out["kind"] = "file"
            out["size_bytes"] = st.st_size
        else:
            out["kind"] = "other"
        out["exists"] = True
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_file_exists(**kwargs) -> Dict[str, Any]:
    return file_exists(kwargs.get("path", "") or kwargs.get("file_path", ""))

"""Cap A.5 — list_directory."""
from __future__ import annotations
import os, stat
from pathlib import Path
from typing import Any, Dict, Optional
from ._path_guard import is_allowed, canonicalize, allowed_roots

MAX_ENTRIES = 1000


def list_directory(path: str, *, show_hidden: bool = False,
                   max_entries: int = MAX_ENTRIES) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "path": path, "entries": [],
        "entry_count": 0, "truncated": False, "error": None,
    }
    try:
        if not path:
            out["error"] = "empty path"; return out
        if not is_allowed(path):
            out["error"] = f"path not under allowed roots: {allowed_roots()}"
            return out
        canon = canonicalize(path)
        out["path"] = canon
        if not os.path.exists(canon):
            out["error"] = "path does not exist"; return out
        if not os.path.isdir(canon):
            out["error"] = "path is not a directory"; return out

        entries = []
        for name in sorted(os.listdir(canon)):
            if not show_hidden and name.startswith("."):
                continue
            full = os.path.join(canon, name)
            try:
                st = os.lstat(full)
                kind = (
                    "dir" if stat.S_ISDIR(st.st_mode) else
                    "link" if stat.S_ISLNK(st.st_mode) else
                    "file" if stat.S_ISREG(st.st_mode) else
                    "other"
                )
                entries.append({
                    "name": name, "kind": kind,
                    "size_bytes": st.st_size if kind == "file" else None,
                    "mode": oct(st.st_mode & 0o777),
                })
            except OSError as e:
                entries.append({"name": name, "kind": "error", "error": str(e)})
            if len(entries) >= max_entries:
                out["truncated"] = True
                break
        out["entries"] = entries
        out["entry_count"] = len(entries)
        out["ok"] = True
        return out
    except PermissionError as e:
        out["error"] = f"permission denied: {e}"; return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_list_directory(**kwargs) -> Dict[str, Any]:
    return list_directory(
        path=kwargs.get("path", ""),
        show_hidden=kwargs.get("show_hidden", False),
        max_entries=kwargs.get("max_entries", MAX_ENTRIES),
    )

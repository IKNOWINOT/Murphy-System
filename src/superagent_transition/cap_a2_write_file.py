"""Cap A.2 — write_file.

Murphy's second migrated superagent capability. Creates or overwrites
a text file with atomic write (write-temp-then-rename), root allowlist,
dangerous-extension blocklist, size guard, and SHA-256 checksum return.

Status: A.2 NEW → EXISTS (post-R15)
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from ._path_guard import check_write_safe, canonicalize

MAX_WRITE_BYTES = 5 * 1024 * 1024  # 5 MB hard cap on writes


def write_file(
    file_path: str,
    content: str,
    *,
    mode: int = 0o644,
    owner: Optional[str] = None,
    create_dirs: bool = False,
) -> Dict[str, Any]:
    """Atomically write content to file_path.

    Returns:
        {
          "ok": bool,
          "path": str,           # canonical path written
          "size_bytes": int,
          "sha256": str,         # of written content
          "created": bool,       # True if file didn't exist before
          "error": str | None,
        }
    """
    out: Dict[str, Any] = {
        "ok": False, "path": file_path, "size_bytes": 0,
        "sha256": "", "created": False, "error": None,
    }
    try:
        ok, err = check_write_safe(file_path)
        if not ok:
            out["error"] = err
            return out

        if content is None:
            content = ""
        if not isinstance(content, str):
            out["error"] = f"content must be str, got {type(content).__name__}"
            return out

        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            out["error"] = (f"content too large: {len(encoded)} bytes > "
                            f"{MAX_WRITE_BYTES} max")
            return out

        canon = canonicalize(file_path)
        out["path"] = canon

        parent = os.path.dirname(canon)
        if not os.path.isdir(parent):
            if create_dirs:
                os.makedirs(parent, mode=0o755, exist_ok=True)
            else:
                out["error"] = f"parent directory does not exist: {parent}"
                return out

        existed_before = os.path.exists(canon)
        out["created"] = not existed_before

        # Atomic write: temp file in same dir then rename
        fd, tmp_path = tempfile.mkstemp(
            prefix=".superagent_write_", dir=parent,
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(encoded)
            os.chmod(tmp_path, mode)
            if owner:
                import pwd
                try:
                    uid = pwd.getpwnam(owner).pw_uid
                    gid = pwd.getpwnam(owner).pw_gid
                    os.chown(tmp_path, uid, gid)
                except (KeyError, PermissionError) as e:
                    # Non-fatal — log via error field but still write
                    out["chown_warning"] = f"chown {owner} failed: {e}"
            os.rename(tmp_path, canon)
            tmp_path = None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        sha = hashlib.sha256(encoded).hexdigest()
        out["size_bytes"] = len(encoded)
        out["sha256"] = sha
        out["ok"] = True
        return out
    except PermissionError as e:
        out["error"] = f"permission denied: {e}"
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out


def execute_write_file(**kwargs) -> Dict[str, Any]:
    """Adapter for SkillManager.register_tool_executor."""
    path = kwargs.get("file_path") or kwargs.get("path") or ""
    content = kwargs.get("content", "")
    return write_file(
        path,
        content,
        mode=kwargs.get("mode", 0o644),
        owner=kwargs.get("owner"),
        create_dirs=kwargs.get("create_dirs", False),
    )

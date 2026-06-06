"""Shared filesystem safety primitives for superagent transition caps.

Used by A.1 (read_file), A.2 (write_file), A.5 (list_directory),
A.6 (file_exists), and any future filesystem-touching cap.

Two layers:
  1. Root allowlist — paths must canonicalize under an allowed root
  2. Dangerous extension blocklist (write-only) — refuse .bat/.vbs/.hta
     and friends per Base44 platform file-safety rule

Both layers are operator-overridable via env vars so deployments can
narrow or widen as policy requires.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

DEFAULT_ROOTS = [
    "/opt/Murphy-System",
    "/var/lib/murphy-production",
    "/etc/murphy-production",
    "/tmp",
    "/var/log/murphy",
]

# Match Base44's blocked extensions list verbatim (file-safety rule).
DANGEROUS_EXTS = {
    ".bat", ".cmd", ".com", ".exe", ".hta", ".jar", ".js", ".jse",
    ".lnk", ".msi", ".pif", ".ps1", ".reg", ".scr", ".vbs", ".vbe",
    ".wsf", ".wsh",
}


def allowed_roots() -> list:
    """Return current allowlist. Overridable via SUPERAGENT_FS_ROOTS env."""
    env = os.getenv("SUPERAGENT_FS_ROOTS") or os.getenv("SUPERAGENT_READ_FILE_ROOTS")
    if env:
        return [r.strip() for r in env.split(":") if r.strip()]
    return list(DEFAULT_ROOTS)


def is_allowed(path: str) -> bool:
    """Path canonicalizes under an allowed root prefix."""
    try:
        canon = Path(path).resolve()
    except Exception:
        return False
    s = str(canon)
    for root in allowed_roots():
        try:
            root_canon = str(Path(root).resolve())
            if s == root_canon or s.startswith(root_canon + os.sep):
                return True
        except Exception:
            continue
    return False


def dangerous_extensions() -> set:
    """Operator can extend via SUPERAGENT_DANGEROUS_EXTS (colon-separated)."""
    s = set(DANGEROUS_EXTS)
    env = os.getenv("SUPERAGENT_DANGEROUS_EXTS")
    if env:
        for ext in env.split(":"):
            ext = ext.strip().lower()
            if ext and not ext.startswith("."):
                ext = "." + ext
            if ext:
                s.add(ext)
    return s


def check_write_safe(path: str) -> Tuple[bool, str]:
    """Returns (ok, error_msg). Used by all write-style caps."""
    if not path:
        return False, "empty path"
    if not is_allowed(path):
        return False, f"path not under allowed roots: {allowed_roots()}"
    ext = Path(path).suffix.lower()
    if ext in dangerous_extensions():
        return False, (f"dangerous extension blocked: {ext} "
                       f"(Base44 file-safety rule)")
    return True, ""


def canonicalize(path: str) -> str:
    return str(Path(path).resolve())

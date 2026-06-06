"""Cap A.7 — upload_file (public CDN-ish URL).

Implementation:
  - Copy source file into /opt/Murphy-System/static/uploads/<uuid>/<basename>
  - Nginx already serves /static/ → file becomes
    https://murphy.systems/static/uploads/<uuid>/<basename>
  - Reuses _path_guard for SOURCE allowlist + dangerous-ext blocklist
  - SHA-256 returned for integrity verification by caller
  - 25 MB hard cap (matches Base44 superagent surface)

This is the "host it ourselves" minimal pattern. Future cap (R-future)
can swap in real CDN / S3 without changing the public surface.
"""
from __future__ import annotations
import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict
from ._path_guard import is_allowed, canonicalize, dangerous_extensions

PUBLIC_HOST = "https://murphy.systems"
UPLOAD_ROOT = "/opt/Murphy-System/static/uploads"
PUBLIC_PREFIX = "/static/uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB matches Base44 cap


def upload_file(file_path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "source": file_path, "file_url": None,
        "size_bytes": 0, "sha256": "", "error": None,
    }
    try:
        if not file_path:
            out["error"] = "empty path"; return out
        if not is_allowed(file_path):
            out["error"] = "source path not under allowed roots"
            return out
        canon = canonicalize(file_path)
        if not os.path.exists(canon):
            out["error"] = "source file does not exist"; return out
        if not os.path.isfile(canon):
            out["error"] = "source is not a regular file"; return out
        # Block dangerous extensions on upload
        ext = Path(canon).suffix.lower()
        if ext in dangerous_extensions():
            out["error"] = f"dangerous extension blocked on upload: {ext}"
            return out
        size = os.path.getsize(canon)
        if size > MAX_UPLOAD_BYTES:
            out["error"] = f"file too large: {size} > {MAX_UPLOAD_BYTES}"
            return out

        # Generate unique upload dir + preserve original basename
        upload_id = uuid.uuid4().hex[:16]
        basename = Path(canon).name
        # Sanitize basename (no slashes — they shouldn't appear but be safe)
        basename = basename.replace("/", "_").replace("\\", "_")
        target_dir = os.path.join(UPLOAD_ROOT, upload_id)
        os.makedirs(target_dir, exist_ok=True)
        os.chmod(target_dir, 0o755)
        target_path = os.path.join(target_dir, basename)
        shutil.copy2(canon, target_path)
        os.chmod(target_path, 0o644)

        # Compute SHA of what we copied (integrity verification)
        h = hashlib.sha256()
        with open(target_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        sha = h.hexdigest()

        public_url = f"{PUBLIC_HOST}{PUBLIC_PREFIX}/{upload_id}/{basename}"

        out["file_url"] = public_url
        out["size_bytes"] = size
        out["sha256"] = sha
        out["upload_id"] = upload_id
        out["ok"] = True
        return out
    except PermissionError as e:
        out["error"] = f"permission denied: {e}"; return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_upload_file(**kwargs) -> Dict[str, Any]:
    return upload_file(kwargs.get("file_path", "") or kwargs.get("path", ""))

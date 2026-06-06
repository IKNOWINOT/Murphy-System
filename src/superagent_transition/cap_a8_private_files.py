"""Cap A.8 — upload_private_file + create_file_signed_url.

Architecture:
  - Private uploads land in /var/lib/murphy-production/private_uploads/<uuid>/
    OUTSIDE the web root. Nginx cannot path-guess to them.
  - create_file_signed_url generates HMAC-signed URLs:
      https://murphy.systems/api/files/<uuid>/<basename>?exp=<ts>&sig=<hmac>
  - Verification happens in the FastAPI handler (added in r615 spawn svc).
  - HMAC over canonical string: f"{file_uri}|{exp}"
  - Signing key: SUPERAGENT_FILE_SIGNING_KEY env var (separate from founder)
  - Default expiry 300s, max 86400s (24h)
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from ._path_guard import is_allowed, canonicalize, dangerous_extensions

PRIVATE_ROOT = "/var/lib/murphy-production/private_uploads"
SIGN_KEY_ENV = "SUPERAGENT_FILE_SIGNING_KEY"
PUBLIC_HOST = "https://murphy.systems"
SIGNED_URL_PATH = "/api/files"
DEFAULT_EXPIRY_S = 300
MAX_EXPIRY_S = 86400
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _signing_key() -> bytes:
    k = os.environ.get(SIGN_KEY_ENV, "")
    if not k:
        # Fall back to reading the secrets file directly (env may not be in
        # process if called outside service)
        try:
            with open("/etc/murphy-production/secrets.env") as f:
                for line in f:
                    if line.startswith(f"{SIGN_KEY_ENV}="):
                        k = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not k:
        raise RuntimeError(f"{SIGN_KEY_ENV} not set")
    return k.encode("utf-8")


def upload_private_file(file_path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "source": file_path, "file_uri": None,
        "size_bytes": 0, "sha256": "", "error": None,
    }
    try:
        if not file_path:
            out["error"] = "empty path"; return out
        if not is_allowed(file_path):
            out["error"] = "source not under allowed roots"; return out
        canon = canonicalize(file_path)
        if not os.path.exists(canon):
            out["error"] = "source does not exist"; return out
        if not os.path.isfile(canon):
            out["error"] = "source is not a regular file"; return out
        ext = Path(canon).suffix.lower()
        if ext in dangerous_extensions():
            out["error"] = f"dangerous extension blocked: {ext}"; return out
        size = os.path.getsize(canon)
        if size > MAX_UPLOAD_BYTES:
            out["error"] = f"file too large: {size}"; return out

        upload_id = uuid.uuid4().hex[:16]
        basename = Path(canon).name.replace("/", "_").replace("\\", "_")
        target_dir = os.path.join(PRIVATE_ROOT, upload_id)
        os.makedirs(target_dir, exist_ok=True)
        os.chmod(target_dir, 0o750)
        target_path = os.path.join(target_dir, basename)
        shutil.copy2(canon, target_path)
        os.chmod(target_path, 0o640)

        h = hashlib.sha256()
        with open(target_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)

        file_uri = f"private://{upload_id}/{basename}"
        out["file_uri"] = file_uri
        out["upload_id"] = upload_id
        out["basename"] = basename
        out["size_bytes"] = size
        out["sha256"] = h.hexdigest()
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def create_file_signed_url(file_uri: str, expires_in: int = DEFAULT_EXPIRY_S) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "file_uri": file_uri, "signed_url": None,
        "expires_at": None, "error": None,
    }
    try:
        if not file_uri or not file_uri.startswith("private://"):
            out["error"] = "file_uri must start with private://"; return out
        # Parse uri
        rest = file_uri[len("private://"):]
        if "/" not in rest:
            out["error"] = "malformed file_uri"; return out
        upload_id, basename = rest.split("/", 1)
        if not upload_id or not basename:
            out["error"] = "malformed file_uri"; return out
        # Verify file exists (don't sign URLs for missing files)
        fs_path = os.path.join(PRIVATE_ROOT, upload_id, basename)
        if not os.path.exists(fs_path):
            out["error"] = "file does not exist for this uri"; return out

        expires_in = min(max(1, int(expires_in)), MAX_EXPIRY_S)
        exp = int(time.time()) + expires_in
        # Canonical signing string
        canonical = f"{file_uri}|{exp}"
        sig = hmac.new(_signing_key(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signed_url = (
            f"{PUBLIC_HOST}{SIGNED_URL_PATH}/{upload_id}/{basename}"
            f"?exp={exp}&sig={sig}"
        )
        out["signed_url"] = signed_url
        out["expires_at"] = exp
        out["expires_in"] = expires_in
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def verify_signed_request(upload_id: str, basename: str, exp: int, sig: str) -> Dict[str, Any]:
    """Server-side verifier used by the FastAPI handler."""
    try:
        now = int(time.time())
        if now > int(exp):
            return {"ok": False, "error": "expired"}
        file_uri = f"private://{upload_id}/{basename}"
        canonical = f"{file_uri}|{exp}"
        expected = hmac.new(_signing_key(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return {"ok": False, "error": "bad signature"}
        fs_path = os.path.join(PRIVATE_ROOT, upload_id, basename)
        if not os.path.exists(fs_path):
            return {"ok": False, "error": "file gone"}
        return {"ok": True, "fs_path": fs_path}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def execute_upload_private_file(**kwargs) -> Dict[str, Any]:
    return upload_private_file(kwargs.get("file_path", "") or kwargs.get("path", ""))


def execute_create_file_signed_url(**kwargs) -> Dict[str, Any]:
    return create_file_signed_url(
        file_uri=kwargs.get("file_uri", ""),
        expires_in=int(kwargs.get("expires_in", DEFAULT_EXPIRY_S)),
    )

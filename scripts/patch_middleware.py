#!/usr/bin/env python3
"""
Murphy System — Patch _APIKeyMiddleware to accept murphy_session cookies.

Run this on the Hetzner server:
  python3 /tmp/patch_middleware.py

It patches src/runtime/app.py in-place, replacing the _APIKeyMiddleware.dispatch
method so that a valid murphy_session cookie bypasses the X-API-Key requirement.
"""

import re
import os
import shutil
from pathlib import Path

APP_PY = Path("/opt/Murphy-System/src/runtime/app.py")

if not APP_PY.exists():
    print(f"ERROR: {APP_PY} not found")
    exit(1)

# Backup first
backup = APP_PY.with_suffix(".py.bak")
shutil.copy2(APP_PY, backup)
print(f"Backup: {backup}")

content = APP_PY.read_text()

OLD = '''        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if path.startswith("/api/"):
                is_exempt = (
                    path in self.EXEMPT_PATHS
                    or any(path.startswith(pfx) for pfx in self.EXEMPT_PREFIXES)
                )
                if not is_exempt:
                    expected_key = os.environ.get("MURPHY_API_KEY", "") or os.environ.get("MURPHY_API_KEYS", "")
                    if expected_key:
                        # Starlette normalises header names to lowercase (RFC 7230);
                        # use lowercase "x-api-key" here to match that behaviour.
                        api_key = request.headers.get("x-api-key", "")
                        if api_key != expected_key:
                            return JSONResponse(
                                {"success": False, "error": {"code": "AUTH_REQUIRED", "message": "Valid X-API-Key header required"}},
                                status_code=401,
                            )
            return await call_next(request)'''

NEW = '''        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if path.startswith("/api/"):
                is_exempt = (
                    path in self.EXEMPT_PATHS
                    or any(path.startswith(pfx) for pfx in self.EXEMPT_PREFIXES)
                )
                if not is_exempt:
                    expected_key = os.environ.get("MURPHY_API_KEY", "") or os.environ.get("MURPHY_API_KEYS", "")
                    if expected_key:
                        # 1. Valid murphy_session cookie — user is logged in via browser
                        session_cookie = request.cookies.get("murphy_session", "")
                        if session_cookie:
                            try:
                                with _session_lock:
                                    if session_cookie in _session_store:
                                        return await call_next(request)
                            except Exception:
                                pass
                        # 2. Authorization: Bearer <session_token> — JS clients
                        auth_header = request.headers.get("authorization", "")
                        if auth_header.lower().startswith("bearer "):
                            bearer = auth_header[7:].strip()
                            try:
                                with _session_lock:
                                    if bearer in _session_store:
                                        return await call_next(request)
                            except Exception:
                                pass
                        # 3. X-API-Key header — server-to-server / external clients
                        api_key = request.headers.get("x-api-key", "")
                        if api_key != expected_key:
                            return JSONResponse(
                                {"success": False, "error": {"code": "AUTH_REQUIRED", "message": "Authentication required"}},
                                status_code=401,
                            )
            return await call_next(request)'''

if OLD not in content:
    print("ERROR: Target block not found — file may have changed. Aborting.")
    exit(1)

patched = content.replace(OLD, NEW, 1)
APP_PY.write_text(patched)
print("Patched successfully.")
print("Run: systemctl restart murphy-production")

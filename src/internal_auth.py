"""
PATCH-OPT-3 — Murphy Internal Service Auth
============================================

WHAT THIS IS:
  Shared-secret authentication for inter-service calls. When murphy-edge
  needs to talk to murphy-core, it sends X-Internal-Token. murphy-core
  validates that token before processing. This stops anyone bypassing the
  edge and hitting core/ops/robotics directly.

WHY IT EXISTS:
  Modular split means 6 processes listen on 6 ports. Each port could in
  theory be probed by an attacker (only edge faces the internet, but
  defense-in-depth says every service should authenticate every caller).
  Also lets internal services skip the heavy OIDC bearer check — they
  trust the edge's identity work and just need to know "this is a peer".

HOW IT FITS:
  - Secret stored at /etc/murphy-production/.internal_secret (mode 0440)
  - Generated once at first boot if missing
  - Every cross-service request carries X-Internal-Token: <secret>
  - require_internal() decorator on FastAPI routes that should ONLY be
    callable from another Murphy service (never from public)
  - call_internal(service_url, path, ...) is the client-side helper

KEY CONCEPTS:
  - Shared secret: 32 random bytes, hex-encoded, mode 0440 root:murphy
  - Constant-time compare (hmac.compare_digest) to prevent timing attacks
  - Optional caller identification via X-Internal-Service header for audit

ENDPOINTS / PUBLIC SURFACE:
  - require_internal() — FastAPI dependency, raises 401 if header missing/wrong
  - call_internal(service, path, method, ...) — async helper using httpx
  - rotate_secret() — admin function to regenerate (requires all services
    to restart, so used carefully)

DEPENDENCIES:
  - fastapi (for HTTPException + Depends)
  - httpx (for client-side calls between services)
  - hmac (stdlib) for constant-time comparison

VAULT SECRETS USED:
  Not used. This is the bootstrap secret BEFORE the vault is reachable
  (the vault itself runs in ops service and needs internal auth to be
  callable from edge). Stored as a flat file instead.

EVENT SPINE EMISSIONS:
  - 'internal_auth.failed' with caller_ip + path when validation fails
  - 'internal_auth.secret_rotated' on rotate

KNOWN LIMITS:
  - Single shared secret, no per-service tokens (PATCH-OPT-7 will fix)
  - Rotation requires coordinated restart of all 6 services

LAST UPDATED: 2026-05-24 by Murphy
"""
from __future__ import annotations

import os, hmac, secrets, logging, time
from typing import Optional, Dict, Any

log = logging.getLogger("murphy.internal_auth")

SECRET_PATH = "/etc/murphy-production/.internal_secret"
HEADER_TOKEN = "X-Internal-Token"
HEADER_SERVICE = "X-Internal-Service"


# ── Secret bootstrap ────────────────────────────────────────────────────────
def _load_or_create_secret() -> str:
    """Return hex secret. Creates one (32 bytes) if file missing."""
    if os.path.exists(SECRET_PATH):
        try:
            with open(SECRET_PATH) as f:
                s = f.read().strip()
            if len(s) >= 32:
                return s
            log.warning("internal secret file too short, regenerating")
        except Exception as e:
            log.error("failed reading %s: %s", SECRET_PATH, e)

    # Generate
    secret = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(SECRET_PATH), exist_ok=True)
        # Write with restrictive permissions atomically
        tmp = SECRET_PATH + ".tmp"
        with open(tmp, "w") as f:
            f.write(secret)
        os.chmod(tmp, 0o440)
        # Try to set group to murphy if possible
        try:
            import grp
            gid = grp.getgrnam("murphy").gr_gid
            os.chown(tmp, 0, gid)
        except (KeyError, PermissionError):
            pass
        os.replace(tmp, SECRET_PATH)
        log.info("internal_auth secret generated at %s", SECRET_PATH)
    except Exception as e:
        log.error("failed writing %s: %s — falling back to in-memory", SECRET_PATH, e)
    return secret


_SECRET: Optional[str] = None


def get_secret() -> str:
    global _SECRET
    if _SECRET is None:
        _SECRET = _load_or_create_secret()
    return _SECRET


# ── Server-side validation ──────────────────────────────────────────────────
def validate_token(provided: Optional[str]) -> bool:
    """Constant-time comparison of provided token vs known secret."""
    if not provided:
        return False
    expected = get_secret()
    try:
        return hmac.compare_digest(provided.strip(), expected)
    except Exception:
        return False


# ── FastAPI dependency ──────────────────────────────────────────────────────
async def require_internal(request) -> Dict[str, Any]:
    """
    FastAPI dependency. Use as:

        @app.get("/api/core/internal/something")
        async def something(_=Depends(require_internal)):
            ...
    """
    from fastapi import HTTPException

    token = request.headers.get(HEADER_TOKEN)
    caller = request.headers.get(HEADER_SERVICE, "unknown")

    if not validate_token(token):
        # Try to emit to event spine if reachable (don't block on it)
        try:
            from event_spine import emit  # type: ignore
            emit("internal_auth.failed", {
                "caller_ip": request.client.host if request.client else "?",
                "caller_service": caller,
                "path": str(request.url.path),
                "ts": time.time(),
            })
        except Exception:
            pass
        raise HTTPException(
            status_code=401,
            detail={"error": "internal_auth_failed",
                    "hint": f"Set {HEADER_TOKEN} header"}
        )

    return {"internal": True, "caller_service": caller}


# ── Client-side helper ──────────────────────────────────────────────────────
async def call_internal(
    base_url: str,
    path: str,
    method: str = "GET",
    *,
    caller_service: str = "unknown",
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
) -> Any:
    """
    Make an authenticated internal request to another Murphy service.

    Example:
        result = await call_internal(
            "http://127.0.0.1:8003", "/api/vault/get",
            method="POST", json={"key_name": "stripe_test"},
            caller_service="edge"
        )
    """
    import httpx

    h = dict(headers or {})
    h[HEADER_TOKEN] = get_secret()
    h[HEADER_SERVICE] = caller_service

    url = base_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method.upper() == "GET":
            resp = await client.get(url, params=params, headers=h)
        elif method.upper() == "POST":
            resp = await client.post(url, json=json, params=params, headers=h)
        elif method.upper() == "PUT":
            resp = await client.put(url, json=json, params=params, headers=h)
        elif method.upper() == "DELETE":
            resp = await client.delete(url, params=params, headers=h)
        else:
            raise ValueError(f"unsupported method: {method}")

    return resp


# ── Service URL registry (where each module lives) ──────────────────────────
SERVICE_URLS = {
    "edge":       "http://127.0.0.1:8000",
    "core":       "http://127.0.0.1:8010",   # legacy monolith, renamed
    "business":   "http://127.0.0.1:8002",
    "ops":        "http://127.0.0.1:8003",
    "robotics":   "http://127.0.0.1:8004",
    "stream":     "http://127.0.0.1:8005",
}


def url_for(service: str) -> str:
    """Return base URL for a named Murphy service."""
    if service not in SERVICE_URLS:
        raise ValueError(f"unknown service: {service}")
    return SERVICE_URLS[service]


# ── Routes (mounted into every service for self-test) ──────────────────────
def init_internal_auth_routes(app, service_name: str):
    """Wire /api/internal/* — diagnostic + ping endpoints."""
    from fastapi import Depends, Request
    from fastapi.responses import JSONResponse

    @app.get("/api/internal/ping")
    async def internal_ping(_=Depends(require_internal), request: Request = None):
        return {
            "ok": True,
            "service": service_name,
            "ts": time.time(),
            "caller": request.headers.get(HEADER_SERVICE, "?") if request else "?",
        }

    @app.get("/api/internal/health")
    async def internal_health():
        """PUBLIC — used by nginx + local healthchecks. No auth."""
        return {"ok": True, "service": service_name,
                "secret_loaded": bool(get_secret()),
                "ts": time.time()}

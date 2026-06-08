"""
BLOCK-A.5.1 — Murphy Audit Middleware
=====================================

WHAT THIS IS:
  A Starlette BaseHTTPMiddleware that writes one row to murphy_audit.events
  per HTTP request. Captures actor identity (from auth_middleware's
  request.state stamping), route, method, status code, latency, tenant
  context, and optional prompt-hash for state-changing routes.

WHY IT EXISTS:
  The 22,034 rows currently in murphy_audit.events are all system-level
  (audit_trail_start on service boot). No HTTP-request-level visibility
  exists. When something like BLOCK-X.2's lying-activity bug happens, we
  have no record of which request triggered the CRM write — making
  forensics painful and bug-class detection impossible.

HOW IT FITS:
  Composes AFTER modular_auth.ModularAuthMiddleware (which stamps
  request.state.actor_kind, tier, department, account_id). This audit
  middleware reads those attrs and writes them along with response data
  to murphy_audit.events. Survives auth failures (logs them with status=403/401).

KEY CONCEPTS:
  - Async write to murphy_audit.events with hash-chain (matches existing
    schema's prev_event_hash + event_hash columns)
  - EXEMPT paths (static, /api/swarm/bus, /api/pulse — high-frequency
    polling routes that would flood the log)
  - Body sampling for state-changing routes (POST/PUT/PATCH/DELETE) —
    SHA-256 hash of first 2KB of body goes to prompt_hash, never raw body
  - Failure-safe: audit write errors NEVER block the request

ENDPOINTS / PUBLIC SURFACE:
  - register_audit_middleware(app: FastAPI, service_name: str) -> None
  - install_audit_middleware (legacy alias)

DEPENDENCIES:
  - sqlite3 (stdlib)
  - starlette.middleware.base.BaseHTTPMiddleware
  - hashlib (stdlib)
  - Existing /var/lib/murphy-production/murphy_audit.db with `events` table

VAULT SECRETS USED: none

EVENT SPINE EMISSIONS: none (writes to murphy_audit.events table directly,
  not to the event bus — audit should not depend on the event bus to
  guarantee delivery)

KNOWN LIMITS:
  - SQLite synchronous write per request adds ~0.5-2ms latency
  - At >100 req/s sustained, consider batched async writer
  - prev_event_hash uses last seen by THIS process; on restart, chain
    re-anchors from latest DB row — accept this as restart boundary

LAST UPDATED: 2026-05-25 by Murphy (BLOCK-A.5.1)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("murphy.audit_middleware")

# ── Configuration ──────────────────────────────────────────────────────────────

AUDIT_DB_PATH = os.environ.get(
    "MURPHY_AUDIT_DB",
    "/var/lib/murphy-production/murphy_audit.db",
)

# High-frequency polling routes — skip to avoid log flooding.
# Match patterns: prefix-startswith (path.startswith(p) for p in EXEMPT_PREFIXES)
# BLOCK-A.5.4 (2026-05-26): expanded list (per swarm-designed brief)
EXEMPT_PREFIXES = (
    "/static",
    "/favicon",
    "/assets",
    "/api/swarm/bus/feed",       # 1s polling - SSE feed
    "/api/pulse/current",        # 60s polling but very chatty
    "/api/health",
    "/healthz",
    "/livez",
    "/readyz",
    "/api/version",
    "/docs",                     # FastAPI auto-docs
    "/redoc",                    # FastAPI auto-docs (alt)
    "/openapi.json",             # OpenAPI spec
    "/ws",                       # WebSocket upgrades
    "/api/ws",                   # WebSocket upgrades (alt)
)

# BLOCK-A.5.4 (2026-05-26): paths that MUST be audited regardless of EXEMPT match.
# These override EXEMPT_PREFIXES — money, approvals, secrets are always logged.
ALWAYS_AUDIT_PREFIXES = (
    "/api/billing/",             # all payments
    "/api/checkout",             # checkout creation
    "/api/portal",               # billing portal
    "/api/webhooks/stripe",      # stripe events
    "/api/webhooks/nowpayments", # crypto events
    "/api/hitl/",                # human-in-loop approvals
    "/api/platform/self-modification/",  # PSM patches (ledger-critical)
    "/api/secret/",              # vault access
    "/api/admin/",               # admin actions
    "/api/auth/",                # auth events
    "/api/intake",               # client intake
    "/api/financial/",           # financial actions
    "/api/grants/",              # grant operations (money-adjacent)
)

# Methods that mutate state — capture body hash
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Cap body sampling to avoid memory blowups
BODY_SAMPLE_LIMIT = 2048  # bytes

# BLOCK-A.5.2: tenant context — match existing convention from app.py:10714
TENANT_HEADER = "X-Tenant-ID"
DEFAULT_TENANT_ID = "default"

# In-process last-event-hash for chain (re-anchors from DB on first call)
_LAST_HASH: dict[str, Optional[str]] = {}
_HASH_LOCK = asyncio.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_exempt(path: str) -> bool:
    """Return True if path matches an exempt prefix — no audit row written.

    BLOCK-A.5.4: ALWAYS_AUDIT_PREFIXES overrides EXEMPT_PREFIXES. Even if a
    path happens to match an exempt rule, it is still audited if it touches
    money, approvals, secrets, or admin actions.
    """
    if any(path.startswith(p) for p in ALWAYS_AUDIT_PREFIXES):
        return False
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_body_hash(body_bytes: bytes) -> Optional[str]:
    """Hash up to BODY_SAMPLE_LIMIT bytes of body. Returns None for empty."""
    if not body_bytes:
        return None
    sample = body_bytes[:BODY_SAMPLE_LIMIT]
    return _sha256_hex(sample)


def _connect() -> sqlite3.Connection:
    """Open audit DB with WAL + 2s timeout to handle concurrent writers."""
    conn = sqlite3.connect(AUDIT_DB_PATH, timeout=2, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=2000")
    except sqlite3.Error:
        pass  # PRAGMA failures don't break audit
    return conn


def _fetch_last_hash(service_name: str) -> Optional[str]:
    """Find the most recent event_hash to anchor the chain."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT event_hash FROM events "
                "WHERE event_hash IS NOT NULL "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row[0] if row and row[0] else None
    except sqlite3.Error as e:
        logger.warning("audit: chain re-anchor failed for %s: %s", service_name, e)
        return None


async def _next_hash(service_name: str, payload: str) -> Tuple[Optional[str], str]:
    """Return (prev_hash, this_hash) atomically per service."""
    async with _HASH_LOCK:
        prev = _LAST_HASH.get(service_name)
        if prev is None:
            prev = _fetch_last_hash(service_name)
            _LAST_HASH[service_name] = prev
        chain_input = (prev or "GENESIS").encode() + b"|" + payload.encode()
        this_hash = _sha256_hex(chain_input)
        _LAST_HASH[service_name] = this_hash
        return prev, this_hash


def _summarize_request(
    request: Request,
    body_hash: Optional[str],
) -> str:
    """Build a short, indexable input_summary string."""
    parts = [request.method, str(request.url.path)]
    qs = request.url.query
    if qs:
        # truncate query string to avoid blowing up the index
        parts.append(f"?{qs[:200]}")
    if body_hash:
        parts.append(f"body_sha={body_hash[:16]}")
    return " ".join(parts)


def _summarize_response(status_code: int, latency_ms: int, response_size: int) -> str:
    return f"status={status_code} latency_ms={latency_ms} bytes={response_size}"


# ── The middleware ─────────────────────────────────────────────────────────────

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Writes one row to murphy_audit.events per non-exempt request.

    Args:
        app: ASGI app to wrap
        service_name: Identifier for which monolith/edge/ops/robotics emitted
            the event (e.g. "monolith", "robotics"). Stored in metadata.
    """

    def __init__(self, app, service_name: str = "unknown"):
        super().__init__(app)
        self.service_name = service_name
        logger.info("AuditMiddleware initialized for service=%s db=%s",
                    service_name, AUDIT_DB_PATH)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"

        # Skip the high-frequency polling routes
        if _is_exempt(path):
            return await call_next(request)

        # BLOCK-A.5.2: stamp tenant_id on request.state if upstream auth
        # didn't set it. Matches the X-Tenant-ID convention used by app.py
        # (line 10714) and 7+ other call sites. Default to "default".
        if not getattr(request.state, "tenant_id", None):
            request.state.tenant_id = (
                request.headers.get(TENANT_HEADER)
                or request.headers.get(TENANT_HEADER.lower())
                or DEFAULT_TENANT_ID
            )

        # Capture body for mutating requests so we can hash it.
        # IMPORTANT: must replace the receive callable so downstream gets the same body.
        body_hash: Optional[str] = None
        if request.method.upper() in MUTATING_METHODS:
            try:
                body_bytes = await request.body()
                body_hash = _safe_body_hash(body_bytes)
                # Re-inject body for downstream handler
                async def _receive():
                    return {"type": "http.request", "body": body_bytes, "more_body": False}
                request._receive = _receive  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("audit: body capture failed for %s %s: %s",
                             request.method, path, e)

        # Time the downstream handler
        t_start = time.perf_counter()
        status_code = 500
        response: Optional[Response] = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Even on handler failure, we audit the attempt
            status_code = 500
            logger.error("audit: downstream raised for %s %s: %s",
                         request.method, path, e)
            # Don't swallow — re-raise after we audit (in finally)
            try:
                await self._write_event(
                    request=request,
                    status_code=status_code,
                    latency_ms=int((time.perf_counter() - t_start) * 1000),
                    response_size=0,
                    body_hash=body_hash,
                    extra_status="error",
                    extra_meta={"exception": type(e).__name__},
                )
            except Exception:
                pass
            raise

        # Successful (in HTTP sense) path: write the audit row.
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        response_size = 0
        try:
            cl = response.headers.get("content-length")
            response_size = int(cl) if cl else 0
        except (TypeError, ValueError):
            response_size = 0

        try:
            await self._write_event(
                request=request,
                status_code=status_code,
                latency_ms=latency_ms,
                response_size=response_size,
                body_hash=body_hash,
            )
        except Exception as e:
            # Audit failures NEVER block the request
            logger.warning("audit: write failed for %s %s: %s",
                           request.method, path, e)

        return response

    async def _write_event(
        self,
        request: Request,
        status_code: int,
        latency_ms: int,
        response_size: int,
        body_hash: Optional[str],
        extra_status: Optional[str] = None,
        extra_meta: Optional[dict] = None,
    ) -> None:
        """Write one event row. Best-effort — never raises."""
        ts = datetime.now(timezone.utc).isoformat()

        # Pull actor info from request.state (stamped by ModularAuthMiddleware)
        state = request.state
        actor = getattr(state, "actor_account_id", None) or "anonymous"
        actor_kind = getattr(state, "actor_kind", "anonymous")
        tier = getattr(state, "tier", None)
        department = getattr(state, "department", None)
        tenant_id = getattr(state, "tenant_id", None)

        # Status-code-based audit status field
        if extra_status:
            audit_status = extra_status
        elif status_code >= 500:
            audit_status = "error"
        elif status_code >= 400:
            audit_status = "denied"
        else:
            audit_status = "ok"

        # Determine action verb
        method = request.method.upper()
        path = request.url.path
        action = f"{method} {path}"

        input_summary = _summarize_request(request, body_hash)
        output_summary = _summarize_response(status_code, latency_ms, response_size)
        # === PCR-025 BEGIN provenance side-write ===
        try:
            from src.provenance_writer import write_from_request as _pcr025_pw
            _pcr025_pw(
                path=path,
                method=method,
                status_code=status_code,
                latency_ms=latency_ms,
                actor=actor,
                body_hash=body_hash,
                response_size=response_size,
            )
        except Exception as _pcr025_e:
            logger.debug("provenance side-write failed: %s", _pcr025_e)
        # === PCR-025 END provenance side-write ===


        # Build metadata JSON
        meta = {
            "service": self.service_name,
            "tier": tier,
            "department": department,
            "actor_kind": actor_kind,
            "latency_ms": latency_ms,
            "status_code": status_code,
            "response_size": response_size,
        }
        if extra_meta:
            meta.update(extra_meta)

        # Client IP
        client_host = request.client.host if request.client else None
        # Honor X-Forwarded-For if behind nginx
        xff = request.headers.get("x-forwarded-for")
        if xff:
            client_host = xff.split(",")[0].strip()

        # Session id (cookie or header — best-effort)
        session_id = request.cookies.get("session_id") or request.headers.get("x-session-id")

        # Compute hash chain over the canonical payload
        canonical = "|".join([
            ts, actor, actor_kind, action,
            audit_status, str(status_code), str(latency_ms),
            tenant_id or "", body_hash or "",
        ])
        prev_hash, this_hash = await _next_hash(self.service_name, canonical)

        # Insert (run in default executor since sqlite3 is sync)
        def _insert():
            with _connect() as conn:
                conn.execute(
                    """
                    INSERT INTO events
                        (ts, actor, actor_type, action,
                         resource_type, resource_id,
                         input_summary, output_summary, status, metadata,
                         ip_address, session_id, tenant_id, prompt_hash,
                         prev_event_hash, event_hash)
                    VALUES (?,?,?,?, ?,?, ?,?,?,?, ?,?,?,?, ?,?)
                    """,
                    (
                        ts, actor, actor_kind, action,
                        "http_request", None,
                        input_summary, output_summary, audit_status, json.dumps(meta),
                        client_host, session_id, tenant_id, body_hash,
                        prev_hash, this_hash,
                    ),
                )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _insert)


# ── Registration helpers ───────────────────────────────────────────────────────

def register_audit_middleware(app, service_name: str = "monolith") -> None:
    """
    Mount AuditMiddleware on a FastAPI app.

    Call this AFTER auth middleware registration so we see the actor info
    that auth middleware stamps onto request.state.

    Order in Starlette: middleware added later runs FIRST on the request
    (and LAST on the response). So we want audit added AFTER auth →
    auth runs first → stamps request.state → audit runs second → reads it.
    """
    app.add_middleware(AuditMiddleware, service_name=service_name)
    logger.info("audit_middleware: registered for service=%s", service_name)
    # === PCR-025 BEGIN provenance writer init ===
    try:
        from src import provenance_writer  # noqa: F401
        logger.info("audit_middleware: provenance_writer loaded (PCR-025)")
    except Exception as _e:
        logger.warning("audit_middleware: provenance_writer load failed: %s", _e)
    # === PCR-025 END provenance writer init ===



# Legacy alias
install_audit_middleware = register_audit_middleware


# ── Self-test (run as `python audit_middleware.py`) ────────────────────────────

if __name__ == "__main__":
    # Smoke test: write a synthetic event directly
    logging.basicConfig(level=logging.INFO)
    print(f"Audit DB: {AUDIT_DB_PATH}")
    print(f"DB exists: {os.path.exists(AUDIT_DB_PATH)}")

    with _connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"Events before: {before}")

    # Synthesize an insert via the chain helper
    async def _test():
        prev, this = await _next_hash("self_test", "test|payload")
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO events
                    (ts, actor, actor_type, action,
                     resource_type, input_summary, output_summary, status,
                     metadata, prev_event_hash, event_hash)
                VALUES (?,?,?,?, ?,?,?,?, ?, ?,?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    "self_test", "test", "GET /self_test",
                    "http_request", "GET /self_test", "status=200 latency_ms=1 bytes=0",
                    "ok",
                    json.dumps({"service": "self_test"}),
                    prev, this,
                ),
            )
        return this

    result = asyncio.run(_test())
    print(f"Wrote chain hash: {result[:16]}...")

    with _connect() as conn:
        after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"Events after:  {after}  (+{after - before})")
    print("✅ Self-test passed" if after == before + 1 else "❌ Self-test FAILED")

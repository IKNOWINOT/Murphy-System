"""
Murphy System — Authentication & Security Middleware (DEF-014, DEF-015, ADR-0012)

Provides:
  - APIKeyMiddleware: Legacy X-API-Key middleware (kept for back-compat).
  - OIDCAuthMiddleware: ADR-0012 Release-N middleware — OIDC primary,
    session-cookie secondary, deprecated X-API-Key fallback gated by
    an env-var + route-allowlist.  Stamps ``request.state.actor_user_sub``
    and ``request.state.actor_kind`` for audit attribution.
  - SecurityHeadersMiddleware: Adds standard security headers.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import fnmatch
import hmac
import logging
import sqlite3 as _sqlite3_audit
from datetime import datetime as _dt_audit, timezone as _tz_audit
import os
import threading
from typing import Dict, List, Optional, Set, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("murphy.auth")

# ── Exempt paths that never require authentication ─────────────────────────
_DEFAULT_EXEMPT: Set[str] = {
    "/health",
    "/api/health",
    "/api/readiness",
    "/api/status/public",
    "/api/self/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/",
    "/trippingpenguins",
    "/penguins",
    "/voteforsteve2028",
    "/steve2028merch",
    "/stevewiki",
}

_EXEMPT_PREFIXES = (
    "/static",
    "/murphy-static",
    "/ui/",
    "/api/ui/",
    "/api/auth/",
    "/api/demo",
    "/api/manga",
    "/api/v1/",          # PATCH-065a: public API
    "/oauth/",           # PATCH-065b: OAuth AS
    "/.well-known/",     # PATCH-065b: OIDC discovery
    "/api/connectors/",  # PATCH-065c: connector agent
    "/api/connectors",
        "/api/connectors",
    "/api/v1/auth/",
    # PATCH-049a: billing endpoints — webhooks public (signature-verified),
    # checkout + plans public (user supplies account_id in body)
    "/api/billing/webhooks/",
    "/api/billing/plans",
    "/api/billing/currencies",
    "/api/billing/checkout",
    # PATCH-097: Foundation modules — conduct, ledger, front-of-line
    "/api/conduct/",
    "/api/conduct",
    "/api/ledger/",
    "/api/ledger",
    "/api/frontline/",
    "/api/frontline",
    # PATCH-097b: Self-modification + evaluation
    "/api/self/evaluate",
    "/api/self/patch",
    "/api/self/backups",
    "/api/self/restore",
    "/api/self/vision",
    # PATCH-098: RROM monitoring
    "/api/rrom/",
    "/api/rrom",
    # PATCH-099: PCC
    "/api/pcc/",
    "/api/pcc",
    # PATCH-103: World State Engine (public read-only)
    "/api/world/",
    "/api/world",
    # PATCH-102: Hardware telemetry (public read-only)
    "/api/hardware/",
    "/api/hardware",
    # PATCH-100: CIDP (public stats only)
    "/api/cidp/stats",
    "/api/cidp/stats/",
    # PATCH-111a: Shield Wall — all /api/shield/* routes are public (north star, status, team)
    "/api/shield/",
    "/api/shield",
    # PATCH-111a: LCM — /api/lcm/process is auth-gated but signal/history are internal
    "/api/lcm/",
    "/api/lcm",
    # PATCH-112-117: Swarm Rosetta — public read endpoints
    "/api/rosetta/",
    "/api/rosetta",
    "/api/signals/",
    "/api/signals",
    "/api/workflows/",
    "/api/workflows",
    "/api/workflow/",
    "/api/workflow",
    "/api/exec/",
    "/api/exec",
    "/api/prodops/",
    "/api/prodops",
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce API key authentication on all non-exempt routes.

    Supports three authentication methods:
      1. X-API-Key header
      2. Authorization: Bearer <key>
      3. ?api_key=<key> query parameter

    Environment-aware:
      - Development mode (MURPHY_ENV != production/staging): allows requests
        when MURPHY_AUTH_ENABLED is not explicitly "true"
      - Production/staging: requires valid API key unless MURPHY_AUTH_ENABLED=false
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path.rstrip("/") or "/"
        method = request.method.upper()

        # Always allow OPTIONS (CORS preflight)
        if method == "OPTIONS":
            return await call_next(request)

        # Check exempt paths
        if path in _DEFAULT_EXEMPT:
            return await call_next(request)
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Check user-defined exempt paths
        extra_exempt = os.environ.get("MURPHY_AUTH_EXEMPT", "")
        if extra_exempt:
            for ep in extra_exempt.split(","):
                ep = ep.strip()
                if ep and path.startswith(ep):
                    return await call_next(request)

        # Check if auth is enabled
        env_mode = os.environ.get("MURPHY_ENV", "development").lower()
        auth_enabled = os.environ.get("MURPHY_AUTH_ENABLED", "").lower()

        if env_mode in ("production", "staging"):
            # Production: auth enabled by default unless explicitly disabled
            if auth_enabled == "false":
                return await call_next(request)
        else:
            # Development: auth disabled by default unless explicitly enabled
            if auth_enabled != "true":
                return await call_next(request)

        # Get the expected API key
        expected_key = os.environ.get("MURPHY_API_KEY", "")
        if not expected_key:
            logger.warning(
                "MURPHY_API_KEY not set but auth is enabled — blocking request to %s",
                path,
            )
            return JSONResponse(
                {"error": "Server misconfiguration: API key not set"},
                status_code=500,
            )

        # Extract key from request
        provided_key = _extract_api_key(request)
        if not provided_key:
            return JSONResponse(
                {"error": "Authentication required", "detail": "Provide API key via X-API-Key header, Authorization: Bearer, or ?api_key= query param"},
                status_code=401,
            )

        # Constant-time comparison
        if not hmac.compare_digest(provided_key, expected_key):
            logger.warning("Invalid API key attempt on %s", path)
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=403,
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to all responses (DEF-015)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS only in production
        env_mode = os.environ.get("MURPHY_ENV", "development").lower()
        if env_mode in ("production", "staging"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from multiple sources."""
    # 1. X-API-Key header
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if key:
        return key

    # 2. Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    # 3. Query parameter
    key = request.query_params.get("api_key")
    if key:
        return key

    return None


# ════════════════════════════════════════════════════════════════════════════
# ADR-0012 Release N — OIDC primary auth + deprecated API-key fallback
# ════════════════════════════════════════════════════════════════════════════
#
# Authentication order (per ADR §"Authentication order"):
#   1. ``Authorization: Bearer <jwt>``  → OIDC verifier → claims
#   2. ``Cookie: murphy_sid=<sid>``     → server-side session lookup
#   3. ``X-API-Key`` (deprecated)       → only when the env var is on
#                                          AND the route matches the
#                                          legacy machine-to-machine
#                                          allowlist.
#
# Every accepted API-key request emits a ``DeprecationWarning``-flavoured
# log line plus a Prometheus-shaped counter so we can watch the residual
# usage drop to zero before flipping the default in Release N+1.


# Default machine-to-machine allowlist — matches the ADR's example.
# Operators can extend it via ``MURPHY_API_KEY_ROUTES``
# (comma-separated fnmatch patterns).
_DEFAULT_API_KEY_ROUTES: Tuple[str, ...] = ("/api/v1/internal/*",)


class _ApiKeyDeprecationCounter:
    """Thread-safe per-route counter of accepted API-key requests.

    Exposed via ``snapshot()`` for tests and (eventually) the
    ``/api/aionmind/metrics`` surface.  The counter name matches the
    ADR's spec: ``murphy_api_key_requests_total{route="..."}``.
    """

    metric_name = "murphy_api_key_requests_total"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {}

    def increment(self, route: str) -> None:
        with self._lock:
            self._counts[route] = self._counts.get(route, 0) + 1

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


# Module-global counter — one per process.  Tests reset via
# ``api_key_deprecation_counter.reset()``.
api_key_deprecation_counter = _ApiKeyDeprecationCounter()


class _SessionStore:
    """Tiny in-memory ``murphy_sid`` → ``{sub, tenant, kind}`` store.

    Production deployments swap this for a Redis-backed store via
    ``OIDCAuthMiddleware.session_store=`` injection.  The interface is
    intentionally narrow (``get`` only) so any backend that satisfies
    it works.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, str]] = {}

    def get(self, sid: str) -> Optional[Dict[str, str]]:
        with self._lock:
            v = self._sessions.get(sid)
            return dict(v) if v else None

    def put(self, sid: str, claims: Dict[str, str]) -> None:
        with self._lock:
            self._sessions[sid] = dict(claims)

    def revoke(self, sid: str) -> None:
        with self._lock:
            self._sessions.pop(sid, None)


# Module-global default session store (in-memory).  ``OIDCAuthMiddleware``
# accepts a different store at construction.
default_session_store = _SessionStore()


def _api_key_allowed(path: str, patterns: Tuple[str, ...]) -> bool:
    """Return True when *path* matches any of the legacy m2m
    allowlist patterns (fnmatch style)."""
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _allowlist_from_env() -> Tuple[str, ...]:
    raw = os.environ.get("MURPHY_API_KEY_ROUTES", "").strip()
    if not raw:
        return _DEFAULT_API_KEY_ROUTES
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else _DEFAULT_API_KEY_ROUTES


class OIDCAuthMiddleware(BaseHTTPMiddleware):
    """ADR-0012 Release N — OIDC primary, API-key fallback.

    The middleware is configured entirely via environment variables so
    deployments don't grow new code-level config knobs (CLAUDE.md §2):

    * ``MURPHY_OIDC_ISSUER``         — required to enable JWT path
    * ``MURPHY_OIDC_CLIENT_ID``      — required to enable JWT path
    * ``MURPHY_OIDC_TENANT_CLAIM``   — optional, defaults to ``"tenant"``
    * ``MURPHY_API_KEY``             — current shared API key (legacy)
    * ``MURPHY_ALLOW_API_KEY``       — ``"true"`` (Release-N default)
                                       to keep accepting the legacy
                                       header.  Release N+1 flips this
                                       to ``"false"``.
    * ``MURPHY_API_KEY_ROUTES``      — comma-separated fnmatch patterns
                                       restricting which routes accept
                                       the deprecated header (default:
                                       ``/api/v1/internal/*``).
    * ``MURPHY_AUTH_ENFORCED``       — ``"true"`` to reject unauthenticated
                                       requests; defaults to ``"false"`` in
                                       development to preserve the existing
                                       permissive-when-unset behaviour.

    The middleware never short-circuits ``/api/auth/*``, ``/api/demo/*``,
    ``/api/health``, ``/api/system/*``, or any of the back-compat exempt
    prefixes inherited from the inline middleware it replaces.
    """

    # Inline-middleware behaviour we MUST preserve so the existing
    # /api/auth/login flow keeps working:
    EXEMPT_PATHS: Set[str] = {
        "/api/automation/prefight/status",   # PATCH-177: engine availability — public
        "/api/health",
        "/api/info",
        "/api/manifest",
        "/api/readiness",
        "/api/status/public",
        "/api/self/health",    # PATCH-066c: self health public
        "/api/capabilities/registry",  # PATCH-174: API registry public
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/",
        # PATCH-142b: demo page public endpoints (no auth required)
        "/api/roi-calendar/summary",
        "/api/roi-calendar/events",
        "/api/ambient/stats",
        "/api/ambient/settings",
        "/api/forge/list",
        "/api/forge/status",
        "/api/swarm/mind/status",
        "/api/corpus/stats",
        "/api/compliance/report",
        "/api/compliance/toggles",
        "/api/compliance/recommended",
        "/api/compliance/scan",
        "/api/shield/status",
        "/api/shield/north-star",
        "/api/wallet/balances",
        "/api/wallet/addresses",
        "/api/wallet/transactions",
        # PATCH-158: CRM/Boards/Time-tracking public read
        "/api/crm/deals",
        "/api/crm/contacts",
        "/api/crm/activities",
        "/api/crm/pipelines",
        "/api/boards",
        "/api/time-tracking/",
        "/api/portfolio/",
        "/api/workdocs",
        "/api/time-tracking/report",
        "/api/time-tracking/timer/active",
        "/api/matrix/chat",
        "/api/matrix/chat/rooms",
        "/api/comms",
        "/api/portfolio/summary",
        "/api/trading/paper/status",
        "/api/trading/paper/performance",
        "/api/trading/paper/positions",
        "/api/trading/paper/strategies",
        "/api/trading/paper/trades",
        "/api/trading/emergency/status",
        "/api/trading/risk/assessment",
        "/api/trading/risk/costs",
        "/api/collaboration/feed",
        "/api/workdocs",
        "/api/crypto/status",
    }
    EXEMPT_PREFIXES: Tuple[str, ...] = (
        "/static",
        "/murphy-static",
        "/ui/",
        "/api/ui/",
        "/api/auth/",
        "/api/v1/auth/",
        "/api/demo",
        "/api/manga",
        "/api/demo/",
        "/api/time-tracking/",
        "/api/portfolio/",
        "/api/trading/paper/",
        "/api/trading/risk/",
        "/api/trading/emergency/",
        "/api/trading/graduation/",
        "/api/trading/audit/",
        "/api/workdocs",
        "/api/collaboration/",
        "/api/comms/",
        "/api/matrix/chat",
        "/api/system/",
        # PATCH-098: RROM monitoring (public)
        "/api/rrom/",
        "/api/rrom",
        # PATCH-099: PCC (public)
        "/api/pcc/",
        "/api/pcc",
        # PATCH-103c: Teacher loop status (public read-only)
        "/api/teacher/status",
        # PATCH-103: World State Engine (public read-only)
        "/api/world/",
        "/api/world",
        # PATCH-102: Hardware telemetry (public read-only)
        "/api/hardware/",
        "/api/hardware",
        # PATCH-100: CIDP stats (public read-only)
        "/api/cidp/stats",
        "/api/cidp/stats/",
        # PATCH-048: /api/account/* and /api/admin/* use murphy_session
        # cookie auth inside app.py (_get_account_from_session).
        # OIDCAuthMiddleware only knows murphy_sid — exempt these so they
        # reach the inner auth logic rather than being blocked here.
        "/api/account/",
        "/api/account",
        "/api/admin/",
        "/api/admin",
        # PATCH-072: Ambient AI + Management AI — session-cookie auth inside routers
        "/api/ambient/",

    "/api/shield/",  # PATCH-093c: Shield Wall — public status endpoint
        # PATCH-160c: Read-only internal monitoring endpoints — GET only, no state mutation
        # Mind cycle reads these to build its self-model; must stay accessible
        "/api/swarm/mind/status",       # public status
        "/api/visual/snapshot/",      # PATCH-161: public screenshot serving (GET)
        "/api/visual/snapshots",      # PATCH-161: snapshot list (GET)

        "/api/swarm/status",            # swarm health — read-only
        "/api/swarm/scheduler",         # scheduler status — read-only
        "/api/swarm/patterns",          # pattern registry — read-only
        "/api/swarm/critic/modes",      # critic failure modes list — read-only
        "/api/rosetta/status",          # rosetta status — read-only
        "/api/rosetta/soul",            # soul constitution — read-only
        "/api/confidence/status",       # confidence score — read-only
        "/api/self-fix/status",         # self-fix status — read-only
        "/api/repair/proposals",        # repair proposals — read-only
        "/api/gate-synthesis/health",   # gate health — read-only
        "/api/self/code-gen/status",    # code-gen status — read-only
        "/api/corpus/stats",            # corpus stats — read-only
        "/api/swarm/corpus/stats",      # alias
        "/api/signals/latest",          # latest signals — read-only
        # Workflows/automation: session-auth enforced inside handlers
        "/api/automation/loop/",
        "/api/workflows/",

        "/api/ambient",
        "/api/mgmt/",
        "/api/mgmt",
        "/api/lcm/",
        "/api/lcm",
        "/api/convergence/",
        "/api/convergence",
        # PATCH-049a: payment webhooks public (signature-verified by provider)
        # checkout + plans public (user supplies account_id in body)
        "/api/billing/webhooks/",
        "/api/billing/plans",
        "/api/billing/currencies",
        "/api/billing/checkout",
        # PATCH-065: Public API, OAuth AS, Connector Agent
        "/api/v1/",
        "/oauth/",
        "/.well-known/",
        "/api/connectors/",
        # PATCH-097: Foundation modules — public commissioning gate endpoints
        "/api/conduct/",
        "/api/conduct",
        "/api/ledger/",
        "/api/ledger",
        "/api/frontline/",
        "/api/frontline",
        "/api/self/patch",
        "/api/self/vision",   # PATCH-163: vision loop — has own bearer check
        # PATCH-098: RROM monitoring
        "/api/rrom/",
        "/api/rrom",
        # PATCH-099: PCC
        "/api/pcc/",
        "/api/pcc",
    )


    _AUDIT_DB = "/var/lib/murphy-production/murphy_audit.db"

    @staticmethod
    def _write_audit_event(
        event_type: str,
        actor: str = "",
        resource: str = "",
        action: str = "",
        outcome: str = "success",
        details: str = "",
        ip: str = "",
        session_id: str = "",
    ) -> None:
        """Write a single audit event to the persistent audit log (PATCH-155)."""
        try:
            ts = _dt_audit.now(_tz_audit.utc).isoformat()
            with _sqlite3_audit.connect(OIDCAuthMiddleware._AUDIT_DB, timeout=3) as conn:
                conn.execute(
                    "INSERT INTO audit_log (ts, event_type, actor, resource, action, outcome, details, ip, session_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (ts, event_type, actor, resource, action, outcome, details, ip, session_id),
                )
                conn.commit()
        except Exception:
            pass  # Never block a request on audit failure


    def __init__(
        self,
        app,
        *,
        verifier=None,
        session_store: Optional[_SessionStore] = None,
        counter: Optional[_ApiKeyDeprecationCounter] = None,
    ) -> None:
        super().__init__(app)
        self._verifier = verifier  # may be lazily built on first request
        self._verifier_built = verifier is not None
        self._verifier_error: Optional[str] = None
        self._session_store = session_store or default_session_store
        self._counter = counter or api_key_deprecation_counter

    # ── exemption helpers ─────────────────────────────────────────────
    def _is_exempt(self, path: str) -> bool:
        if path in self.EXEMPT_PATHS:
            return True
        for pfx in self.EXEMPT_PREFIXES:
            if path.startswith(pfx):
                return True
        return False

    def _get_verifier(self):
        """Lazily construct the OIDC verifier from env vars on first use."""
        if self._verifier_built:
            return self._verifier
        self._verifier_built = True
        issuer = os.environ.get("MURPHY_OIDC_ISSUER", "").strip()
        audience = os.environ.get("MURPHY_OIDC_CLIENT_ID", "").strip()
        tenant_claim = os.environ.get("MURPHY_OIDC_TENANT_CLAIM", "tenant").strip() or "tenant"
        if not issuer or not audience:
            return None
        try:
            from oidc_verifier import OIDCVerifier
        except Exception:
            try:
                from .oidc_verifier import OIDCVerifier  # type: ignore
            except Exception as exc:
                logger.warning(
                    "OIDC verifier import failed (%s) — falling back to API-key only",
                    exc,
                )
                self._verifier_error = str(exc)
                return None
        try:
            self._verifier = OIDCVerifier(
                issuer=issuer,
                audience=audience,
                tenant_claim=tenant_claim,
            )
            logger.info(
                "OIDC verifier configured (issuer=%s, audience=%s, tenant_claim=%s)",
                issuer, audience, tenant_claim,
            )
        except Exception as exc:
            logger.warning(
                "OIDC verifier construction failed (%s) — falling back to API-key only",
                exc,
            )
            self._verifier_error = str(exc)
            self._verifier = None
        return self._verifier

    # ── main dispatch ─────────────────────────────────────────────────
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()

        # CORS preflight always passes.
        if method == "OPTIONS":
            return await call_next(request)

        # Public surface (auth endpoints, UI, demo, health, etc.) is
        # always exempt — same set the inline middleware honoured.
        if self._is_exempt(path):
            return await call_next(request)

        # Only enforce on /api/* (back-compat with the old inline mount).
        if not path.startswith("/api/"):
            return await call_next(request)

        enforced = os.environ.get("MURPHY_AUTH_ENFORCED", "").strip().lower() == "true"
        # Back-compat: setting MURPHY_API_KEY (or MURPHY_API_KEYS) used
        # to implicitly enforce auth on /api/*.  Preserve that so a
        # deployment upgrading to Release N doesn't suddenly become
        # wide-open.  An operator who wants the new permissive default
        # must explicitly unset MURPHY_API_KEY.
        if not enforced and (
            os.environ.get("MURPHY_API_KEY", "").strip()
            or os.environ.get("MURPHY_API_KEYS", "").strip()
        ):
            enforced = True

        # ── Path 1: Bearer JWT (OIDC) or Session Token ─────────────
        # PATCH-152e: Bearer can be either an OIDC JWT OR a murphy
        # session token (urlsafe_b64, issued by /api/auth/login).
        # Try OIDC first; on failure fall through to session validation
        # instead of hard-rejecting — this unblocks browser clients
        # that send the session_token as Authorization: Bearer.
        bearer = _extract_bearer(request)
        verifier = self._get_verifier()
        if bearer:
            oidc_ok = False
            if verifier is not None:
                try:
                    claims = verifier.verify(bearer)
                    request.state.actor_user_sub = claims.sub
                    request.state.actor_tenant = claims.tenant
                    request.state.actor_kind = "oidc"
                    oidc_ok = True
                    return await call_next(request)
                except Exception as exc:
                    err_name = type(exc).__name__
                    if err_name == "OIDCDiscoveryError":
                        logger.error("OIDC discovery / JWKS failure: %s", exc)
                        return JSONResponse(
                            {"error": "Identity provider unavailable",
                             "code": "OIDC_DISCOVERY_FAILED"},
                            status_code=503,
                        )
                    # Not an OIDC JWT — fall through to session check
                    logger.debug(
                        "Bearer not a valid OIDC token on %s — trying session store",
                        path,
                    )

            if not oidc_ok:
                # PATCH-152e: try bearer as a murphy session token
                try:
                    from src.fastapi_security import _session_validator as _sv
                    if _sv is not None and _sv(bearer):
                        # Resolve account details from session store
                        _account_id = ""
                        _tenant_id = "default"
                        try:
                            from src.runtime.app import _session_store, _session_lock
                            with _session_lock:
                                _account_id = _session_store.get(bearer, "")
                        except Exception:
                            pass
                        request.state.actor_user_sub = _account_id or "session_user"
                        request.state.actor_tenant = _tenant_id
                        request.state.actor_kind = "session_bearer"
                        request.state.actor_account_id = _account_id
                        logger.debug(
                            "Session-bearer auth accepted for account %s on %s",
                            _account_id, path,
                        )
                        return await call_next(request)
                except Exception as _se:
                    logger.debug("Session-bearer check error: %s", _se)

        # ── Path 2: server-side session cookie ───────────────────────
        # PATCH-060-auth: accept both murphy_sid (OIDC store) and
        # murphy_session (app.py login store) so the standard login
        # flow authenticates all /api/* routes.
        sid = (
            request.cookies.get("murphy_sid", "")
            or request.cookies.get("murphy_session", "")
        )
        if sid:
            sess = self._session_store.get(sid)
            if sess:
                request.state.actor_user_sub = sess.get("sub", "")
                request.state.actor_tenant = sess.get("tenant", "")
                request.state.actor_kind = "session"
                return await call_next(request)
            # Fallback: validate against the app-level session store
            # (populated by /api/auth/login using murphy_session cookie).
            try:
                from src.fastapi_security import _session_validator as _app_sv
                if _app_sv is not None and _app_sv(sid):
                    request.state.actor_user_sub = "murphy_session_user"
                    request.state.actor_tenant = "default"
                    request.state.actor_kind = "session"
                    return await call_next(request)
            except Exception:
                pass

        # ── Path 1.5: session token via Authorization: Bearer ────────
        # PATCH-152e: catches urlsafe session tokens that _extract_bearer
        # rejects (not a 3-segment JWT). Checked BEFORE the API-key
        # fallback so the value isn't treated as a legacy key.
        raw_bearer = _extract_raw_bearer(request)
        if raw_bearer:
            try:
                from src.fastapi_security import _session_validator as _sv_15
                if _sv_15 is not None and _sv_15(raw_bearer):
                    _acct_15 = ""
                    try:
                        from src.runtime.app import _session_store as _ss_15, _session_lock as _sl_15
                        with _sl_15:
                            _acct_15 = _ss_15.get(raw_bearer, "")
                    except Exception:
                        pass
                    request.state.actor_user_sub = _acct_15 or "session_bearer_user"
                    request.state.actor_tenant = "default"
                    request.state.actor_kind = "session_bearer"
                    request.state.actor_account_id = _acct_15
                    logger.debug(
                        "PATCH-152e: session-bearer accepted for account=%s on %s",
                        _acct_15, path,
                    )
                    return await call_next(request)
            except Exception as _e15:
                logger.debug("PATCH-152e: session-bearer check failed: %s", _e15)

        # ── Path 3: deprecated API-key fallback ──────────────────────
        api_key = _extract_api_key(request)
        expected_key = (
            os.environ.get("MURPHY_API_KEY", "")
            or os.environ.get("MURPHY_API_KEYS", "")
        )
        allow_api_key = (
            os.environ.get("MURPHY_ALLOW_API_KEY", "true").strip().lower() == "true"
        )
        allowlist = _allowlist_from_env()
        if api_key and expected_key:
            if not allow_api_key:
                logger.info(
                    "API-key auth attempt rejected (MURPHY_ALLOW_API_KEY=false) on %s",
                    path,
                )
                return JSONResponse(
                    {"error": "API key authentication is disabled",
                     "code": "API_KEY_DEPRECATED"},
                    status_code=401,
                )
            if not _api_key_allowed(path, allowlist):
                logger.info(
                    "API-key auth attempt on non-allowlisted route %s (allowlist=%s)",
                    path, allowlist,
                )
                return JSONResponse(
                    {"error": "API key not accepted on this route",
                     "code": "API_KEY_ROUTE_DENIED"},
                    status_code=401,
                )
            if not hmac.compare_digest(api_key, expected_key):
                logger.warning("Invalid API key on %s", path)
                return JSONResponse(
                    {"error": "Invalid API key",
                     "code": "AUTH_REQUIRED"},
                    status_code=401,
                )
            # Accepted — emit the deprecation signal.
            self._counter.increment(path)
            logger.warning(
                "DEPRECATED: X-API-Key accepted on %s — migrate to OIDC "
                "(ADR-0012 Release N+1 disables this path by default)",
                path,
            )
            # PATCH-152d: resolve account_id from correct SQLite path
            _api_acct_id = ""
            try:
                import sqlite3 as _sq_mw
                _founder_email = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")
                # DB lives in service WorkingDirectory (/opt/Murphy-System/murphy.db)
                _db_mw = _sq_mw.connect("/opt/Murphy-System/murphy.db", timeout=2)
                _row_mw = _db_mw.execute(
                    "SELECT account_id FROM user_accounts WHERE email=? LIMIT 1",
                    (_founder_email,)
                ).fetchone()
                _db_mw.close()
                if _row_mw:
                    _api_acct_id = _row_mw[0]
            except Exception:
                pass
            request.state.actor_user_sub = _api_acct_id or ""
            request.state.actor_tenant = "founder" if _api_acct_id else ""
            request.state.actor_kind = "api_key"
            request.state.actor_account_id = _api_acct_id
            return await call_next(request)

        # ── No credentials presented ──────────────────────────────────
        if not enforced:
            # Permissive dev mode — preserve the legacy "no key set ⇒
            # let it through" behaviour the inline middleware had.
            request.state.actor_user_sub = ""
            request.state.actor_tenant = ""
            request.state.actor_kind = "anonymous"
            return await call_next(request)
        return JSONResponse(
            {"error": "Authentication required",
             "code": "AUTH_REQUIRED",
             "detail": "Provide an OIDC bearer token, session cookie, or "
                       "(legacy) X-API-Key header on an allowlisted route"},
            status_code=401,
        )


def _extract_bearer(request: Request) -> Optional[str]:
    """Return the JWT from ``Authorization: Bearer <jwt>`` if present.

    Distinct from ``_extract_api_key``: that helper returns the raw
    bearer value as an *API key*; this one is used to feed the OIDC
    verifier.  We treat a value that isn't 3 dot-separated segments as
    "not a JWT" so the API-key fallback can still pick it up.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    candidate = auth[7:].strip()
    if candidate.count(".") == 2 and len(candidate) > 20:
        return candidate
    return None


def _extract_raw_bearer(request: Request) -> Optional[str]:
    """Return the raw bearer value regardless of whether it looks like a JWT.
    Used by PATCH-152e to validate session tokens sent as Authorization: Bearer.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth[7:].strip() or None
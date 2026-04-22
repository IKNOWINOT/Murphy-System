"""OIDC JWT verifier with JWKS caching — ADR-0012 Release N.

This module implements the JWT validation path that ``auth_middleware``
uses as its primary trust signal.  It deliberately exposes a small,
stateless surface so the middleware can call it inside
``dispatch`` without holding any locks.

Per ADR-0012 §"Provider configuration":

* OIDC discovery is automatic via ``/.well-known/openid-configuration``.
* JWKS is cached for **1 h** with a **5 m grace window**; on ``kid``
  miss the verifier refreshes immediately and retries **once**.
* Failure to refresh after one retry is a hard error — the middleware
  surfaces it as 503, never silently falls back to the API key.

Per ADR-0012 §"Authentication order" the JWT is validated for ``iss``,
``aud``, ``exp``, ``nbf``, and ``iat`` skew.  ``sub`` is exposed as
the user identity; a configurable ``tenant`` claim is exposed for
multi-tenant deployments (defaults to the literal claim name
``"tenant"`` — the ADR allows callers to configure it).

Dependencies (already pinned in ``requirements.txt``):

* ``pyjwt>=2.8`` — JWS verification.
* ``cryptography>=41`` — RS256/RS384/RS512/ES256/ES384/ES512 keys.

The module degrades cleanly when those libs are absent: ``OIDCVerifier``
construction raises ``OIDCConfigError`` so the middleware falls back to
its legacy API-key path with a clear error message logged once at
warning level.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("murphy.oidc")

# ── Public exception hierarchy ──────────────────────────────────────────────


class OIDCError(Exception):
    """Base class for every OIDC verifier error."""


class OIDCConfigError(OIDCError):
    """Verifier could not be constructed (missing deps / config)."""


class OIDCDiscoveryError(OIDCError):
    """OIDC discovery / JWKS fetch failed (HTTP / parse / TLS)."""


class OIDCTokenError(OIDCError):
    """A specific token failed verification.  ``reason`` is one of:
    ``malformed``, ``expired``, ``not_yet_valid``, ``wrong_issuer``,
    ``wrong_audience``, ``unknown_kid``, ``bad_signature``,
    ``missing_claim``, ``unsupported_algorithm``.
    """

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


# ── Verifier ───────────────────────────────────────────────────────────────


@dataclass
class VerifiedClaims:
    """Result of a successful JWT verification.

    The middleware uses ``sub`` to populate
    ``request.state.actor_user_sub`` and ``tenant`` for the audit
    attribution column described in ADR-0012 §Consequences.
    """

    sub: str
    tenant: str
    issuer: str
    audience: str
    expires_at: float
    raw: Dict[str, Any] = field(default_factory=dict)


# JWKS-cache TTL constants from the ADR (centralised so tests can
# monkey-patch them deterministically without poking at module
# internals).
JWKS_TTL_SECONDS = 60 * 60        # 1 h
JWKS_GRACE_SECONDS = 5 * 60       # 5 m grace window
DISCOVERY_TTL_SECONDS = 60 * 60   # 1 h, refreshed lazily

# Algorithms we accept.  HS256 (shared-secret) is intentionally
# excluded — this verifier exists specifically to remove shared
# secrets from the trust path.
_ALLOWED_ALGS: Tuple[str, ...] = (
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
)


class OIDCVerifier:
    """Stateless-as-possible OIDC JWT verifier with JWKS caching.

    Construction is cheap; each ``verify`` call grabs a cache snapshot
    under a short-held lock then performs JWT decode outside the lock.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        tenant_claim: str = "tenant",
        leeway_seconds: int = 30,
        http_get: Optional[Callable[[str, Dict[str, str]], Tuple[int, Dict[str, Any]]]] = None,
    ) -> None:
        if not issuer:
            raise OIDCConfigError("OIDC issuer is required")
        if not audience:
            raise OIDCConfigError("OIDC audience (client_id) is required")
        # Importing here so a deployment without the security extras
        # only fails when it actually tries to construct a verifier.
        try:
            import jwt as _jwt  # noqa: F401  (probe import only)
        except Exception as exc:  # pragma: no cover - covered by smoke test
            raise OIDCConfigError(
                "PyJWT is required for OIDC verification"
            ) from exc

        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._tenant_claim = tenant_claim
        self._leeway = int(leeway_seconds)
        self._http_get = http_get or _default_http_get

        self._lock = threading.Lock()
        # Discovery cache: (fetched_at, document)
        self._discovery: Optional[Tuple[float, Dict[str, Any]]] = None
        # JWKS cache: (fetched_at, {kid: jwk_dict})
        self._jwks: Optional[Tuple[float, Dict[str, Dict[str, Any]]]] = None

    # ── Public API ────────────────────────────────────────────────────────

    def verify(self, token: str, *, now: Optional[float] = None) -> VerifiedClaims:
        """Verify *token* and return its claims.

        Raises :class:`OIDCTokenError` for token-specific failures and
        :class:`OIDCDiscoveryError` for transport-level failures.  The
        latter MUST be surfaced as 503 by the middleware (per the
        ADR's "no silent fallback" rule).
        """
        if not token or token.count(".") != 2:
            raise OIDCTokenError("malformed", "JWT must have 3 segments")

        # Peek at the unverified header so we can reject unsupported
        # algorithms (notably HS256) BEFORE the JWKS round-trip.  This
        # closes the "shared-secret token slips through" gap that
        # would otherwise depend on the JWK's stored ``alg`` field.
        header_alg = self._unverified_alg(token)
        if header_alg and header_alg not in _ALLOWED_ALGS:
            raise OIDCTokenError(
                "unsupported_algorithm", f"alg {header_alg!r} not allowed"
            )

        kid = self._unverified_kid(token)
        jwk = self._jwk_for_kid(kid)
        if jwk is None:
            # ADR: refresh once on kid miss, then retry.
            self._refresh_jwks(force=True)
            jwk = self._jwk_for_kid(kid)
            if jwk is None:
                raise OIDCTokenError("unknown_kid", f"kid {kid!r} not in JWKS")

        try:
            import jwt as _jwt
            from jwt import PyJWKClient  # noqa: F401  (used indirectly via algorithms)
            from jwt.algorithms import RSAAlgorithm, ECAlgorithm
        except Exception as exc:  # pragma: no cover
            raise OIDCConfigError("PyJWT not available at verify time") from exc

        alg = jwk.get("alg") or self._unverified_alg(token)
        if alg not in _ALLOWED_ALGS:
            raise OIDCTokenError("unsupported_algorithm", f"alg {alg!r} not allowed")

        # Build a public key from the JWK for the algorithm family.
        try:
            if alg.startswith("RS") or alg.startswith("PS"):
                public_key = RSAAlgorithm.from_jwk(jwk)
            elif alg.startswith("ES"):
                public_key = ECAlgorithm.from_jwk(jwk)
            else:  # pragma: no cover - guarded above
                raise OIDCTokenError("unsupported_algorithm", alg)
        except OIDCTokenError:
            raise
        except Exception as exc:
            raise OIDCTokenError("bad_signature", f"could not load JWK: {exc}") from exc

        try:
            claims = _jwt.decode(
                token,
                public_key,
                algorithms=[alg],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except _jwt.ExpiredSignatureError as exc:
            raise OIDCTokenError("expired", str(exc)) from exc
        except _jwt.ImmatureSignatureError as exc:
            raise OIDCTokenError("not_yet_valid", str(exc)) from exc
        except _jwt.InvalidIssuerError as exc:
            raise OIDCTokenError("wrong_issuer", str(exc)) from exc
        except _jwt.InvalidAudienceError as exc:
            raise OIDCTokenError("wrong_audience", str(exc)) from exc
        except _jwt.MissingRequiredClaimError as exc:
            raise OIDCTokenError("missing_claim", str(exc)) from exc
        except _jwt.InvalidSignatureError as exc:
            raise OIDCTokenError("bad_signature", str(exc)) from exc
        except _jwt.InvalidTokenError as exc:
            raise OIDCTokenError("malformed", str(exc)) from exc

        sub = str(claims.get("sub") or "")
        if not sub:  # pragma: no cover - require=["sub"] catches this first
            raise OIDCTokenError("missing_claim", "sub")
        tenant = str(claims.get(self._tenant_claim) or "")
        # ``iat`` skew is enforced by PyJWT via ``leeway``; nothing to do here.
        _ = now  # reserved for tests that want a deterministic clock
        return VerifiedClaims(
            sub=sub,
            tenant=tenant,
            issuer=str(claims.get("iss") or ""),
            audience=str(claims.get("aud") or ""),
            expires_at=float(claims.get("exp") or 0.0),
            raw=dict(claims),
        )

    def jwks_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Test-friendly accessor for the current JWKS cache."""
        with self._lock:
            return dict((self._jwks or (0.0, {}))[1])

    # ── Internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _unverified_header(token: str) -> Dict[str, Any]:
        try:
            import jwt as _jwt
            return _jwt.get_unverified_header(token)
        except Exception as exc:
            raise OIDCTokenError("malformed", f"bad header: {exc}") from exc

    def _unverified_kid(self, token: str) -> str:
        kid = self._unverified_header(token).get("kid", "")
        return str(kid)

    def _unverified_alg(self, token: str) -> str:
        alg = self._unverified_header(token).get("alg", "")
        return str(alg)

    def _jwk_for_kid(self, kid: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cache = self._jwks
        if cache is None or _expired(cache[0], JWKS_TTL_SECONDS, JWKS_GRACE_SECONDS):
            try:
                self._refresh_jwks(force=False)
            except OIDCDiscoveryError:
                if cache is None:
                    raise
                # Within grace window — keep serving the stale cache.
                logger.warning("JWKS refresh failed; serving cache within grace window")
            with self._lock:
                cache = self._jwks
        if cache is None:
            return None
        if not kid:
            # If the token has no kid AND the JWKS has exactly one key,
            # fall back to that key (single-key providers are common).
            keys = cache[1]
            if len(keys) == 1:
                return next(iter(keys.values()))
            return None
        return cache[1].get(kid)

    def _refresh_jwks(self, *, force: bool) -> None:
        """Re-fetch the JWKS document.  Holds the lock for I/O — fine,
        we want at-most-one concurrent refresh."""
        with self._lock:
            if not force and self._jwks is not None and not _expired(
                self._jwks[0], JWKS_TTL_SECONDS, 0
            ):
                return
            disc = self._discovery_locked()
            jwks_uri = str(disc.get("jwks_uri") or "")
            if not jwks_uri:
                raise OIDCDiscoveryError("discovery document has no jwks_uri")
            try:
                status, body = self._http_get(jwks_uri, {"Accept": "application/json"})
            except Exception as exc:
                raise OIDCDiscoveryError(f"JWKS fetch failed: {exc}") from exc
            if status != 200 or not isinstance(body, dict):
                raise OIDCDiscoveryError(
                    f"JWKS fetch returned status={status} body_type={type(body).__name__}"
                )
            keys = body.get("keys") or []
            indexed: Dict[str, Dict[str, Any]] = {}
            for k in keys:
                if not isinstance(k, dict):
                    continue
                kid = str(k.get("kid") or "")
                # Allow keys without kid by indexing them under the
                # empty string — _jwk_for_kid handles single-key
                # providers.
                indexed[kid] = k
            self._jwks = (time.time(), indexed)

    def _discovery_locked(self) -> Dict[str, Any]:
        """Return the discovery document, refreshing if stale.  Caller
        already holds ``self._lock``."""
        if self._discovery is not None and not _expired(
            self._discovery[0], DISCOVERY_TTL_SECONDS, 0
        ):
            return self._discovery[1]
        url = self._issuer + "/.well-known/openid-configuration"
        try:
            status, body = self._http_get(url, {"Accept": "application/json"})
        except Exception as exc:
            raise OIDCDiscoveryError(f"discovery fetch failed: {exc}") from exc
        if status != 200 or not isinstance(body, dict):
            raise OIDCDiscoveryError(
                f"discovery fetch returned status={status} body_type={type(body).__name__}"
            )
        # Minimal contract — ADR requires jwks_uri; issuer must match.
        doc_iss = str(body.get("issuer") or "").rstrip("/")
        if doc_iss and doc_iss != self._issuer:
            raise OIDCDiscoveryError(
                f"discovery issuer mismatch: expected {self._issuer!r}, got {doc_iss!r}"
            )
        self._discovery = (time.time(), body)
        return body


# ── Helpers ────────────────────────────────────────────────────────────────


def _expired(fetched_at: float, ttl: int, grace: int) -> bool:
    return time.time() > fetched_at + ttl + grace


def _default_http_get(url: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    """Minimal blocking HTTP GET using stdlib so the verifier has zero
    extra runtime deps.  Tests inject their own callable.

    Returns ``(status_code, parsed_json_body)``.  TLS verification is
    delegated to the system trust store via ``urllib.request``; the
    ADR's threat model explicitly names "JWKS spoofing if TLS
    validation is disabled" as a residual risk we accept as long as
    callers do not subvert the system trust store.
    """
    import json as _json
    from urllib.request import Request, urlopen

    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=10) as resp:  # noqa: S310 - URL is operator-supplied OIDC issuer
        body_bytes = resp.read()
        try:
            body = _json.loads(body_bytes.decode("utf-8"))
        except Exception:
            body = {}
        return (resp.status, body)

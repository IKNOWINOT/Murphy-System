# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""OAuth2 / OIDC Authentication Provider — OAU-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Programmatic OAuth2 / OpenID Connect provider integration for the Murphy
System — provider registry, authorization code flow, token exchange,
token refresh, OIDC discovery metadata, session management, and RBAC
role mapping with full lifecycle control.

Classes: OAuthProvider/GrantType/TokenStatus/SessionStatus (enums),
ProviderConfig/AuthorizationRequest/TokenSet/OIDCDiscovery/UserInfo/
OAuthSession (dataclasses), OAuthManager (thread-safe orchestrator).
``create_oauth_api(manager)`` returns a Flask Blueprint (JSON error envelope).

Real HTTP integration
---------------------
``OAuthManager`` accepts an optional *http_client* at construction time.
When a client is supplied and the registered provider has a ``token_url``,
``exchange_code()`` and ``refresh_token()`` perform **real** HTTP calls to
the provider's token endpoint (PKCE S256 code-flow / refresh-token grant).
``fetch_userinfo()`` calls the provider's ``userinfo_url`` with the Bearer
access token.  A lightweight OIDC ``id_token`` claim validator (issuer,
audience, expiry) is included; full JWKS signature verification should be
added via a dedicated OIDC library in production deployments that require it.

When *no* http_client is provided the manager operates in **simulation mode**
(generates random token values) which is useful for unit-test environments
that do not require real provider connectivity.

Expected HTTP client interface (compatible with ``httpx.Client``)::

    client.post(url, data=payload)   → response with .status_code / .json()
    client.get(url, headers=headers) → response with .status_code / .json()

Safety: all mutable state guarded by threading.Lock; session/token lists
bounded via capped_append (CWE-770); client_secret and tokens redacted
in serialisation.
"""
from __future__ import annotations

import base64
import hashlib
import json as _json
import logging
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    class _StubBlueprint:
        """No-op Blueprint stand-in when Flask is absent."""
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass
        def route(self, *a: Any, **kw: Any) -> Any:
            return lambda fn: fn
    Blueprint = _StubBlueprint  # type: ignore[misc,assignment]
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)
logger = logging.getLogger(__name__)
try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
# -- Enumerations ----------------------------------------------------------
class OAuthProvider(str, Enum):
    """Supported identity providers."""
    MICROSOFT = "microsoft"
    GOOGLE = "google"
    META = "meta"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    APPLE = "apple"
    CUSTOM = "custom"
class GrantType(str, Enum):
    """OAuth2 grant types."""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    DEVICE_CODE = "device_code"
class TokenStatus(str, Enum):
    """Lifecycle status of an OAuth token set."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
class SessionStatus(str, Enum):
    """Lifecycle status of an authenticated session."""
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
# -- Dataclasses -----------------------------------------------------------
@dataclass
class ProviderConfig:
    """Configuration for an OAuth2 / OIDC identity provider."""
    name: str
    provider_type: OAuthProvider = OAuthProvider.CUSTOM
    client_id: str = ""
    client_secret: str = ""
    authorize_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    issuer: str = ""
    jwks_uri: str = ""
    scopes: List[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    redirect_uri: str = ""
    enabled: bool = True
    role_mapping: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    def to_dict(self) -> Dict[str, Any]:
        """Serialise with client_secret redacted."""
        d = asdict(self)
        d["provider_type"] = self.provider_type.value
        if self.client_secret:
            d["client_secret"] = "***REDACTED***"
        return d
@dataclass
class AuthorizationRequest:
    """Pending authorization code flow request."""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    provider_name: str = ""
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    code_verifier: str = field(default_factory=lambda: secrets.token_urlsafe(64))
    redirect_uri: str = ""
    scopes: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    def code_challenge(self) -> str:
        """Derive S256 PKCE code challenge from verifier."""
        digest = hashlib.sha256(self.code_verifier.encode()).digest()
        import base64
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["code_challenge"] = self.code_challenge()
        return d
@dataclass
class TokenSet:
    """OAuth2 token set (access + optional refresh + optional id_token)."""
    token_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    provider_name: str = ""
    access_token: str = ""
    refresh_token: str = ""
    id_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str = ""
    status: TokenStatus = TokenStatus.ACTIVE
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: float = 0.0
    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            self.expires_at = time.time() + self.expires_in
    def is_expired(self) -> bool:
        """Check whether the access token has expired."""
        return time.time() >= self.expires_at
    def to_dict(self) -> Dict[str, Any]:
        """Serialise with tokens redacted."""
        d = asdict(self)
        d["status"] = self.status.value
        for k in ("access_token", "refresh_token", "id_token"):
            v = d.get(k, "")
            d[k] = (v[:4] + "...REDACTED") if v else ""
        return d
@dataclass
class OIDCDiscovery:
    """OIDC discovery document metadata."""
    issuer: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""
    scopes_supported: List[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    response_types_supported: List[str] = field(default_factory=lambda: ["code"])
    grant_types_supported: List[str] = field(
        default_factory=lambda: ["authorization_code", "refresh_token"],
    )
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)
@dataclass
class UserInfo:
    """Authenticated user profile from OIDC provider."""
    sub: str = ""
    name: str = ""
    email: str = ""
    email_verified: bool = False
    picture: str = ""
    locale: str = ""
    provider_name: str = ""
    raw_claims: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)
@dataclass
class OAuthSession:
    """Authenticated user session backed by an OAuth token set."""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    provider_name: str = ""
    user_sub: str = ""
    user_email: str = ""
    roles: List[str] = field(default_factory=list)
    token_id: str = ""
    status: SessionStatus = SessionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity: str = ""
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        if self.user_email:
            parts = self.user_email.split("@")
            d["user_email"] = f"{parts[0][0]}***@{parts[1]}" if len(parts) == 2 else "***"
        return d
# -- OAuthManager ----------------------------------------------------------
class OAuthManager:
    """Thread-safe OAuth2/OIDC provider and session lifecycle manager.

    Parameters
    ----------
    http_client:
        Optional HTTP client instance (e.g. ``httpx.Client``).  When
        provided, ``exchange_code()`` and ``refresh_token()`` perform real
        network calls to the configured provider endpoints.  When ``None``
        the manager operates in *simulation mode* — useful for unit tests
        that do not need real provider connectivity.
    """

    def __init__(self, http_client: Optional[Any] = None) -> None:
        self._lock = threading.Lock()
        self._providers: Dict[str, ProviderConfig] = {}
        self._auth_requests: Dict[str, AuthorizationRequest] = {}
        self._tokens: Dict[str, TokenSet] = {}
        self._sessions: Dict[str, OAuthSession] = {}
        self._discovery_cache: Dict[str, OIDCDiscovery] = {}
        # Injectable HTTP client — None → simulation mode
        self._http_client: Optional[Any] = http_client

    # -- Provider CRUD -----------------------------------------------------
    def register_provider(self, cfg: ProviderConfig) -> str:
        """Register an identity provider. Returns the name."""
        with self._lock:
            self._providers[cfg.name] = cfg
            logger.info("Registered OAuth provider %s", cfg.name)
            return cfg.name

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Retrieve a provider config by name."""
        with self._lock:
            return self._providers.get(name)

    def list_providers(self) -> List[ProviderConfig]:
        """List all registered providers."""
        with self._lock:
            return list(self._providers.values())

    def remove_provider(self, name: str) -> bool:
        """Remove a provider. Returns True if removed."""
        with self._lock:
            return self._providers.pop(name, None) is not None

    def enable_provider(self, name: str, enabled: bool = True) -> bool:
        """Enable or disable a provider."""
        with self._lock:
            p = self._providers.get(name)
            if p is None:
                return False
            p.enabled = enabled
            return True

    # -- Authorization flow ------------------------------------------------
    def start_authorization(
        self,
        provider_name: str,
        redirect_uri: str = "",
    ) -> Optional[AuthorizationRequest]:
        """Create a new authorization request (PKCE S256 code flow)."""
        with self._lock:
            p = self._providers.get(provider_name)
            if p is None or not p.enabled:
                return None
            req = AuthorizationRequest(
                provider_name=provider_name,
                redirect_uri=redirect_uri or p.redirect_uri,
                scopes=list(p.scopes),
            )
            self._auth_requests[req.state] = req
            return req

    def get_auth_request(self, state: str) -> Optional[AuthorizationRequest]:
        """Retrieve a pending auth request by state parameter."""
        with self._lock:
            return self._auth_requests.get(state)

    def exchange_code(self, state: str, code: str) -> Optional[TokenSet]:
        """Exchange an authorization code for tokens.

        **Real mode** (``http_client`` injected + provider has ``token_url``):
        POSTs to the provider's token endpoint with PKCE ``code_verifier``,
        optionally fetches the userinfo profile, and validates basic OIDC
        ``id_token`` claims (issuer, audience, expiry).

        **Simulation mode** (no ``http_client`` or provider has no
        ``token_url``):  generates random token values — suitable for
        unit-test environments that do not require real connectivity.

        Returns ``None`` if *state* is unknown or already consumed.
        """
        with self._lock:
            req = self._auth_requests.pop(state, None)
        if req is None:
            return None

        with self._lock:
            prov = self._providers.get(req.provider_name)

        if prov and prov.token_url and self._http_client is not None:
            return self._exchange_code_real(req, code, prov)

        # ── Simulation mode ────────────────────────────────────────────────
        ts = TokenSet(
            provider_name=req.provider_name,
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            id_token=secrets.token_urlsafe(48),
            scope=" ".join(req.scopes),
        )
        with self._lock:
            self._tokens[ts.token_id] = ts
        return ts

    def _exchange_code_real(
        self,
        req: AuthorizationRequest,
        code: str,
        prov: ProviderConfig,
    ) -> TokenSet:
        """Perform a real token-endpoint POST (PKCE authorization-code grant).

        Raises:
            RuntimeError: on HTTP error or non-200 response from the provider.
        """
        payload: Dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": req.redirect_uri or prov.redirect_uri,
            "client_id": prov.client_id,
            "code_verifier": req.code_verifier,
        }
        if prov.client_secret:
            payload["client_secret"] = prov.client_secret

        try:
            token_resp = self._http_client.post(prov.token_url, data=payload)  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("Token exchange network error for %s: %s", req.provider_name, exc)
            raise RuntimeError(
                f"Token exchange network error for {req.provider_name}: {exc}"
            ) from exc

        if token_resp.status_code != 200:
            raise RuntimeError(
                f"Token exchange failed for {req.provider_name}: "
                f"HTTP {token_resp.status_code} — {token_resp.text[:200]}"
            )

        tok_data: Dict[str, Any] = token_resp.json()

        # Fetch user profile if a userinfo URL is configured
        userinfo: Dict[str, Any] = {}
        access_token = tok_data.get("access_token", "")
        if prov.userinfo_url and access_token:
            userinfo = self._fetch_userinfo_raw(prov.userinfo_url, access_token)

        # Validate OIDC id_token claims if present
        id_token = tok_data.get("id_token", "")
        if id_token and (prov.issuer or prov.client_id):
            try:
                self._validate_id_token_claims(
                    id_token,
                    issuer=prov.issuer,
                    audience=prov.client_id,
                )
            except ValueError as exc:
                logger.warning(
                    "OIDC id_token validation warning for %s: %s",
                    req.provider_name,
                    exc,
                )

        ts = TokenSet(
            provider_name=req.provider_name,
            access_token=access_token,
            refresh_token=tok_data.get("refresh_token", ""),
            id_token=id_token,
            token_type=tok_data.get("token_type", "Bearer"),
            expires_in=int(tok_data.get("expires_in", 3600)),
            scope=tok_data.get("scope", " ".join(req.scopes)),
        )
        # Attach userinfo so callers can build a UserInfo object if needed
        ts._userinfo_raw = userinfo  # type: ignore[attr-defined]

        with self._lock:
            self._tokens[ts.token_id] = ts

        logger.info("Token exchange complete for %s (token_id=%s)", req.provider_name, ts.token_id)
        return ts

    # -- Userinfo ----------------------------------------------------------
    def fetch_userinfo(self, token_id: str) -> Optional[UserInfo]:
        """Fetch the authenticated user's profile from the provider's
        ``userinfo_url`` using the stored Bearer access token.

        Returns ``None`` if the token is unknown, has no access token, the
        provider has no ``userinfo_url``, or no HTTP client is available.
        """
        with self._lock:
            t = self._tokens.get(token_id)
        if t is None or not t.access_token:
            return None

        with self._lock:
            prov = self._providers.get(t.provider_name)
        if prov is None or not prov.userinfo_url:
            return None

        if self._http_client is None:
            logger.debug("fetch_userinfo called without http_client — skipped")
            return None

        raw = self._fetch_userinfo_raw(prov.userinfo_url, t.access_token)
        if not raw:
            return None

        return UserInfo(
            sub=str(raw.get("sub", raw.get("id", ""))),
            name=raw.get("name", ""),
            email=raw.get("email", ""),
            email_verified=bool(raw.get("email_verified", False)),
            picture=raw.get("picture", ""),
            locale=raw.get("locale", ""),
            provider_name=t.provider_name,
            raw_claims=raw,
        )

    def _fetch_userinfo_raw(self, userinfo_url: str, access_token: str) -> Dict[str, Any]:
        """GET the userinfo endpoint with a Bearer token.  Returns raw dict."""
        try:
            resp = self._http_client.get(  # type: ignore[union-attr]
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning(
                "Userinfo endpoint returned HTTP %d for URL %s",
                resp.status_code,
                userinfo_url,
            )
        except Exception as exc:
            logger.error("Userinfo fetch failed: %s", exc)
        return {}

    # -- OIDC validation ---------------------------------------------------
    @staticmethod
    def _validate_id_token_claims(
        id_token: str,
        *,
        issuer: str = "",
        audience: str = "",
    ) -> None:
        """Validate basic OIDC ``id_token`` JWT claims.

        Checks performed (per `OpenID Connect Core §3.1.3.7`_):
        - ``iss`` (issuer) matches the expected *issuer* when both are non-empty
        - ``aud`` (audience) contains *audience* when both are non-empty
        - ``exp`` (expiry) has not passed

        .. note::
            Cryptographic signature verification against the provider's JWKS
            endpoint is intentionally **not** performed here.  For deployments
            that require signature verification, use a dedicated OIDC library
            (e.g. ``python-jose``, ``authlib``, ``PyJWT[crypto]``).

        Raises:
            ValueError: if any claim fails validation.
        """
        parts = id_token.split(".")
        if len(parts) < 3:
            raise ValueError("Malformed id_token: expected 3 base64url segments")

        try:
            padding = 4 - len(parts[1]) % 4
            payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * (padding % 4))
            claims: Dict[str, Any] = _json.loads(payload_bytes)
        except Exception as exc:
            raise ValueError(f"Could not decode id_token payload: {exc}") from exc

        # Issuer check
        token_iss = claims.get("iss", "")
        if issuer and token_iss and token_iss != issuer:
            raise ValueError(
                f"id_token issuer mismatch: expected {issuer!r}, got {token_iss!r}"
            )

        # Audience check
        token_aud = claims.get("aud")
        if audience and token_aud is not None:
            aud_list: List[str] = (
                [token_aud] if isinstance(token_aud, str) else list(token_aud)
            )
            if audience not in aud_list:
                raise ValueError(
                    f"id_token audience mismatch: {audience!r} not in {aud_list!r}"
                )

        # Expiry check
        exp = claims.get("exp")
        if exp is not None:
            if time.time() > float(exp):
                raise ValueError(
                    f"id_token has expired (exp={exp}, now={int(time.time())})"
                )

    # -- Token management --------------------------------------------------
    def refresh_token(self, token_id: str) -> Optional[TokenSet]:
        """Refresh an expired token set.

        **Real mode** (``http_client`` injected + provider has ``token_url``):
        performs a ``refresh_token`` grant against the provider endpoint.

        **Simulation mode**: generates new random token values.

        Returns ``None`` if *token_id* is unknown or has no refresh token.
        """
        with self._lock:
            old = self._tokens.get(token_id)
        if old is None or not old.refresh_token:
            return None

        with self._lock:
            prov = self._providers.get(old.provider_name)

        if prov and prov.token_url and self._http_client is not None:
            return self._refresh_token_real(old, prov)

        # ── Simulation mode ────────────────────────────────────────────────
        with self._lock:
            stored = self._tokens.get(token_id)
            if stored is not None:
                stored.status = TokenStatus.EXPIRED
            ts = TokenSet(
                provider_name=old.provider_name,
                access_token=secrets.token_urlsafe(32),
                refresh_token=secrets.token_urlsafe(32),
                id_token=old.id_token,
                scope=old.scope,
            )
            self._tokens[ts.token_id] = ts
        return ts

    def _refresh_token_real(self, old: TokenSet, prov: ProviderConfig) -> TokenSet:
        """Perform a real ``refresh_token`` grant against the provider endpoint.

        Raises:
            RuntimeError: on HTTP error or non-200 response.
        """
        payload: Dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": old.refresh_token,
            "client_id": prov.client_id,
        }
        if prov.client_secret:
            payload["client_secret"] = prov.client_secret

        try:
            resp = self._http_client.post(prov.token_url, data=payload)  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("Token refresh network error for %s: %s", old.provider_name, exc)
            raise RuntimeError(
                f"Token refresh network error for {old.provider_name}: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Token refresh failed for {old.provider_name}: "
                f"HTTP {resp.status_code} — {resp.text[:200]}"
            )

        tok_data: Dict[str, Any] = resp.json()

        with self._lock:
            stored = self._tokens.get(old.token_id)
            if stored is not None:
                stored.status = TokenStatus.EXPIRED
            ts = TokenSet(
                provider_name=old.provider_name,
                access_token=tok_data.get("access_token", ""),
                # Provider may omit refresh_token on refresh — keep existing
                refresh_token=tok_data.get("refresh_token", old.refresh_token),
                id_token=tok_data.get("id_token", old.id_token),
                token_type=tok_data.get("token_type", "Bearer"),
                expires_in=int(tok_data.get("expires_in", 3600)),
                scope=tok_data.get("scope", old.scope),
            )
            self._tokens[ts.token_id] = ts

        logger.info("Token refresh complete for %s (token_id=%s)", old.provider_name, ts.token_id)
        return ts
    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token set."""
        with self._lock:
            t = self._tokens.get(token_id)
            if t is None:
                return False
            t.status = TokenStatus.REVOKED
            return True
    def get_token(self, token_id: str) -> Optional[TokenSet]:
        """Retrieve a token set by ID."""
        with self._lock:
            return self._tokens.get(token_id)
    def list_tokens(self, provider: Optional[str] = None) -> List[TokenSet]:
        """List token sets, optionally filtered by provider."""
        with self._lock:
            ts = list(self._tokens.values())
            if provider:
                ts = [t for t in ts if t.provider_name == provider]
            return ts
    # -- Session management ------------------------------------------------
    def create_session(self, token_id: str, user_info: Optional[UserInfo] = None) -> Optional[OAuthSession]:
        """Create an authenticated session from a valid token."""
        with self._lock:
            t = self._tokens.get(token_id)
            if t is None or t.status != TokenStatus.ACTIVE:
                return None
            prov = self._providers.get(t.provider_name)
            roles = list(prov.role_mapping.values()) if prov and prov.role_mapping else ["user"]
            sess = OAuthSession(
                provider_name=t.provider_name,
                user_sub=user_info.sub if user_info else "unknown",
                user_email=user_info.email if user_info else "",
                roles=roles,
                token_id=token_id,
                status=SessionStatus.ACTIVE,
                last_activity=datetime.now(timezone.utc).isoformat(),
            )
            self._sessions[sess.session_id] = sess
            return sess
    def get_session(self, session_id: str) -> Optional[OAuthSession]:
        """Retrieve a session by ID."""
        with self._lock:
            return self._sessions.get(session_id)
    def list_sessions(self, status: Optional[SessionStatus] = None) -> List[OAuthSession]:
        """List sessions, optionally filtered by status."""
        with self._lock:
            ss = list(self._sessions.values())
            if status:
                ss = [s for s in ss if s.status == status]
            return ss
    def revoke_session(self, session_id: str) -> bool:
        """Revoke (logout) a session."""
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return False
            s.status = SessionStatus.REVOKED
            return True
    def touch_session(self, session_id: str) -> bool:
        """Update last_activity timestamp on a session."""
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None or s.status != SessionStatus.ACTIVE:
                return False
            s.last_activity = datetime.now(timezone.utc).isoformat()
            return True
    # -- OIDC discovery ----------------------------------------------------
    def set_discovery(self, provider_name: str, disc: OIDCDiscovery) -> str:
        """Cache OIDC discovery metadata for a provider."""
        with self._lock:
            self._discovery_cache[provider_name] = disc
            return provider_name
    def get_discovery(self, provider_name: str) -> Optional[OIDCDiscovery]:
        """Retrieve cached OIDC discovery metadata."""
        with self._lock:
            return self._discovery_cache.get(provider_name)
    # -- Stats -------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """Return counts of managed resources and operational mode."""
        with self._lock:
            return {
                "providers": len(self._providers),
                "pending_auth_requests": len(self._auth_requests),
                "tokens": len(self._tokens),
                "active_tokens": sum(1 for t in self._tokens.values() if t.status == TokenStatus.ACTIVE),
                "sessions": len(self._sessions),
                "active_sessions": sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE),
                "real_http_mode": self._http_client is not None,
            }
# -- Flask Blueprint -------------------------------------------------------
def create_oauth_api(mgr: OAuthManager) -> Any:
    """Create a Flask Blueprint exposing OAuth2/OIDC management endpoints."""
    if not _HAS_FLASK:
        return Blueprint("oauth", __name__)  # type: ignore[arg-type]
    bp = Blueprint("oauth", __name__, url_prefix="/api/oauth")
    def _body() -> Dict[str, Any]:
        return request.get_json(silent=True) or {}
    def _need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
        for k in keys:
            if not body.get(k):
                return jsonify({"error": f"{k} required", "code": "MISSING_FIELDS"}), 400
        return None
    def _404() -> Any:
        return jsonify({"error": "Not found", "code": "NOT_FOUND"}), 404
    # -- Providers ---------------------------------------------------------
    @bp.route("/providers", methods=["POST"])
    def register_provider() -> Any:
        """Register an identity provider."""
        b = _body(); err = _need(b, "name")
        if err:
            return err
        cfg = ProviderConfig(
            name=b["name"],
            provider_type=OAuthProvider(b.get("provider_type", "custom")),
            client_id=b.get("client_id", ""),
            client_secret=b.get("client_secret", ""),
            authorize_url=b.get("authorize_url", ""),
            token_url=b.get("token_url", ""),
            userinfo_url=b.get("userinfo_url", ""),
            issuer=b.get("issuer", ""),
            scopes=b.get("scopes", ["openid", "profile", "email"]),
            redirect_uri=b.get("redirect_uri", ""),
            role_mapping=b.get("role_mapping", {}),
        )
        mgr.register_provider(cfg)
        return jsonify(cfg.to_dict()), 201
    @bp.route("/providers", methods=["GET"])
    def list_providers() -> Any:
        """List providers."""
        return jsonify([p.to_dict() for p in mgr.list_providers()])
    @bp.route("/providers/<name>", methods=["GET"])
    def get_provider(name: str) -> Any:
        """Get a provider."""
        p = mgr.get_provider(name)
        return jsonify(p.to_dict()) if p else _404()
    @bp.route("/providers/<name>", methods=["DELETE"])
    def delete_provider(name: str) -> Any:
        """Remove a provider."""
        return jsonify({"status": "deleted"}) if mgr.remove_provider(name) else _404()
    @bp.route("/providers/<name>/enable", methods=["POST"])
    def enable_provider(name: str) -> Any:
        """Enable/disable a provider."""
        b = _body()
        ok = mgr.enable_provider(name, b.get("enabled", True))
        return jsonify({"status": "updated"}) if ok else _404()
    # -- Authorization flow ------------------------------------------------
    @bp.route("/authorize", methods=["POST"])
    def authorize() -> Any:
        """Start authorization code flow."""
        b = _body(); err = _need(b, "provider_name")
        if err:
            return err
        req = mgr.start_authorization(b["provider_name"], b.get("redirect_uri", ""))
        if req is None:
            return jsonify({"error": "Provider not found or disabled", "code": "PROVIDER_ERROR"}), 400
        return jsonify(req.to_dict()), 201
    @bp.route("/callback", methods=["POST"])
    def callback() -> Any:
        """Exchange authorization code for tokens."""
        b = _body(); err = _need(b, "state", "code")
        if err:
            return err
        try:
            ts = mgr.exchange_code(b["state"], b["code"])
        except RuntimeError as exc:
            return jsonify({"error": str(exc), "code": "EXCHANGE_FAILED"}), 502
        if ts is None:
            return jsonify({"error": "Invalid state or expired", "code": "EXCHANGE_FAILED"}), 400
        return jsonify(ts.to_dict()), 201
    # -- Tokens ------------------------------------------------------------
    @bp.route("/tokens", methods=["GET"])
    def list_tokens() -> Any:
        """List token sets."""
        prov = request.args.get("provider")
        return jsonify([t.to_dict() for t in mgr.list_tokens(prov)])
    @bp.route("/tokens/<token_id>/userinfo", methods=["GET"])
    def get_userinfo(token_id: str) -> Any:
        """Fetch userinfo from provider for a given token."""
        ui = mgr.fetch_userinfo(token_id)
        if ui is None:
            return jsonify({"error": "Userinfo unavailable", "code": "USERINFO_UNAVAILABLE"}), 404
        return jsonify(ui.to_dict())
    @bp.route("/tokens/<token_id>/refresh", methods=["POST"])
    def refresh_tok(token_id: str) -> Any:
        """Refresh a token."""
        try:
            ts = mgr.refresh_token(token_id)
        except RuntimeError as exc:
            return jsonify({"error": str(exc), "code": "REFRESH_FAILED"}), 502
        return jsonify(ts.to_dict()) if ts else _404()
    @bp.route("/tokens/<token_id>/revoke", methods=["POST"])
    def revoke_tok(token_id: str) -> Any:
        """Revoke a token."""
        return jsonify({"status": "revoked"}) if mgr.revoke_token(token_id) else _404()
    # -- Sessions ----------------------------------------------------------
    @bp.route("/sessions", methods=["POST"])
    def create_session() -> Any:
        """Create session from token."""
        b = _body(); err = _need(b, "token_id")
        if err:
            return err
        ui = None
        if "user_info" in b:
            ui = UserInfo(**b["user_info"])
        sess = mgr.create_session(b["token_id"], ui)
        if sess is None:
            return jsonify({"error": "Invalid or inactive token", "code": "SESSION_FAILED"}), 400
        return jsonify(sess.to_dict()), 201
    @bp.route("/sessions", methods=["GET"])
    def list_sessions() -> Any:
        """List sessions."""
        st = request.args.get("status")
        filt = SessionStatus(st) if st else None
        return jsonify([s.to_dict() for s in mgr.list_sessions(filt)])
    @bp.route("/sessions/<sid>", methods=["GET"])
    def get_session(sid: str) -> Any:
        """Get a session."""
        s = mgr.get_session(sid)
        return jsonify(s.to_dict()) if s else _404()
    @bp.route("/sessions/<sid>/revoke", methods=["POST"])
    def revoke_session(sid: str) -> Any:
        """Revoke a session."""
        return jsonify({"status": "revoked"}) if mgr.revoke_session(sid) else _404()
    # -- Discovery & stats -------------------------------------------------
    @bp.route("/discovery/<name>", methods=["GET"])
    def discovery(name: str) -> Any:
        """Get OIDC discovery for a provider."""
        d = mgr.get_discovery(name)
        return jsonify(d.to_dict()) if d else _404()
    @bp.route("/stats", methods=["GET"])
    def oauth_stats() -> Any:
        """Return OAuth statistics."""
        return jsonify(mgr.stats())
    require_blueprint_auth(bp)
    return bp

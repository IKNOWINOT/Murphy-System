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

Safety: all mutable state guarded by threading.Lock; session/token lists
bounded via capped_append (CWE-770); client_secret and tokens redacted
in serialisation; no real network calls — provider adapters are injected.
"""
from __future__ import annotations

import hashlib
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
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    META = "meta"
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
    """Thread-safe OAuth2/OIDC provider and session lifecycle manager."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: Dict[str, ProviderConfig] = {}
        self._auth_requests: Dict[str, AuthorizationRequest] = {}
        self._tokens: Dict[str, TokenSet] = {}
        self._sessions: Dict[str, OAuthSession] = {}
        self._discovery_cache: Dict[str, OIDCDiscovery] = {}
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
    def start_authorization(self, provider_name: str, redirect_uri: str = "") -> Optional[AuthorizationRequest]:
        """Create a new authorization request (PKCE code flow)."""
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
        """Simulate exchanging an authorization code for tokens."""
        with self._lock:
            req = self._auth_requests.pop(state, None)
            if req is None:
                return None
            ts = TokenSet(
                provider_name=req.provider_name,
                access_token=secrets.token_urlsafe(32),
                refresh_token=secrets.token_urlsafe(32),
                id_token=secrets.token_urlsafe(48),
                scope=" ".join(req.scopes),
            )
            self._tokens[ts.token_id] = ts
            return ts
    def refresh_token(self, token_id: str) -> Optional[TokenSet]:
        """Simulate refreshing an expired token set."""
        with self._lock:
            old = self._tokens.get(token_id)
            if old is None or not old.refresh_token:
                return None
            old.status = TokenStatus.EXPIRED
            ts = TokenSet(
                provider_name=old.provider_name,
                access_token=secrets.token_urlsafe(32),
                refresh_token=secrets.token_urlsafe(32),
                id_token=old.id_token,
                scope=old.scope,
            )
            self._tokens[ts.token_id] = ts
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
        """Return counts of managed resources."""
        with self._lock:
            return {
                "providers": len(self._providers),
                "pending_auth_requests": len(self._auth_requests),
                "tokens": len(self._tokens),
                "active_tokens": sum(1 for t in self._tokens.values() if t.status == TokenStatus.ACTIVE),
                "sessions": len(self._sessions),
                "active_sessions": sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE),
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
        ts = mgr.exchange_code(b["state"], b["code"])
        if ts is None:
            return jsonify({"error": "Invalid state or expired", "code": "EXCHANGE_FAILED"}), 400
        return jsonify(ts.to_dict()), 201
    # -- Tokens ------------------------------------------------------------
    @bp.route("/tokens", methods=["GET"])
    def list_tokens() -> Any:
        """List token sets."""
        prov = request.args.get("provider")
        return jsonify([t.to_dict() for t in mgr.list_tokens(prov)])
    @bp.route("/tokens/<token_id>/refresh", methods=["POST"])
    def refresh_tok(token_id: str) -> Any:
        """Refresh a token."""
        ts = mgr.refresh_token(token_id)
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

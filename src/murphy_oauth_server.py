# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post · License: BSL 1.1
"""
murphy_oauth_server.py — PATCH-065b
Murphy OAuth 2.0 / OIDC Authorization Server

Murphy becomes an OAuth 2.0 Authorization Server (AS) so external apps
can request delegated access to a user's Murphy instance.

Flows supported:
  - Authorization Code + PKCE (RFC 7636) — browser-based apps
  - Client Credentials — server-to-server / machine-to-machine
  - Token introspection (RFC 7662)
  - Token revocation (RFC 7009)
  - OIDC Discovery (/.well-known/openid-configuration)
  - JWKS endpoint (/.well-known/jwks.json) — HS256 for now, RS256 roadmap

Token format: signed JWT (HS256 using MURPHY_JWT_SECRET)

Design: MOS-001
Thread-safe: Yes
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOKEN_EXPIRY_ACCESS  = 3600          # 1 hour
TOKEN_EXPIRY_REFRESH = 86400 * 30   # 30 days
AUTH_CODE_EXPIRY     = 600           # 10 minutes
ISSUER               = "https://murphy.systems"
SUPPORTED_SCOPES     = [
    "openid", "profile", "email",
    "forge:read", "forge:write",
    "agents:read", "agents:write",
    "mail:read", "mail:write",
    "calendar:read", "calendar:write",
    "connectors:*", "admin:*",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GrantType(str, Enum):
    AUTH_CODE    = "authorization_code"
    CLIENT_CREDS = "client_credentials"
    REFRESH      = "refresh_token"


class ClientType(str, Enum):
    PUBLIC       = "public"       # browser / mobile — no secret
    CONFIDENTIAL = "confidential" # server-side — has secret


# ---------------------------------------------------------------------------
# Minimal JWT (HS256) — no external deps
# ---------------------------------------------------------------------------

class _JWT:
    """Minimal HS256 JWT implementation (no external library needed)."""

    @staticmethod
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _b64url_decode(s: str) -> bytes:
        pad = 4 - len(s) % 4
        return base64.urlsafe_b64decode(s + "=" * pad)

    @classmethod
    def encode(cls, payload: Dict, secret: str) -> str:
        header  = cls._b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body    = cls._b64url(json.dumps(payload).encode())
        msg     = f"{header}.{body}".encode()
        sig     = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
        return f"{header}.{body}.{cls._b64url(sig)}"

    @classmethod
    def decode(cls, token: str, secret: str) -> Optional[Dict]:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            msg      = f"{parts[0]}.{parts[1]}".encode()
            expected = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
            sig      = cls._b64url_decode(parts[2])
            if not hmac.compare_digest(expected, sig):
                return None
            return json.loads(cls._b64url_decode(parts[1]))
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class OAuthClient:
    client_id:     str
    client_secret: str    # empty for public clients
    name:          str
    client_type:   ClientType
    redirect_uris: List[str]
    allowed_scopes: List[str]
    grant_types:   List[GrantType]
    owner_id:      str
    created_at:    float = field(default_factory=time.time)
    active:        bool  = True
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def verify_secret(self, provided: str) -> bool:
        if self.client_type == ClientType.PUBLIC:
            return True   # public clients don't use secrets
        return hmac.compare_digest(self.client_secret, provided)

    def redirect_allowed(self, uri: str) -> bool:
        return uri in self.redirect_uris

    def scope_allowed(self, requested: List[str]) -> List[str]:
        return [s for s in requested if s in self.allowed_scopes or "admin:*" in self.allowed_scopes]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id":     self.client_id,
            "name":          self.name,
            "client_type":   self.client_type.value,
            "redirect_uris": self.redirect_uris,
            "allowed_scopes": self.allowed_scopes,
            "grant_types":   [g.value for g in self.grant_types],
            "owner_id":      self.owner_id,
            "created_at":    self.created_at,
            "active":        self.active,
        }


@dataclass
class AuthorizationCode:
    code:          str
    client_id:     str
    user_id:       str
    scopes:        List[str]
    redirect_uri:  str
    code_challenge: Optional[str]  # PKCE S256 hash
    expires_at:    float
    used:          bool = False

    def is_valid(self) -> bool:
        return not self.used and time.time() < self.expires_at

    def verify_pkce(self, verifier: str) -> bool:
        if not self.code_challenge:
            return True   # PKCE not required (legacy)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return hmac.compare_digest(self.code_challenge, challenge)


@dataclass
class TokenRecord:
    jti:        str
    subject:    str
    client_id:  str
    scopes:     List[str]
    token_type: str       # "access" | "refresh"
    expires_at: float
    revoked:    bool = False

    def is_valid(self) -> bool:
        return not self.revoked and time.time() < self.expires_at


# ---------------------------------------------------------------------------
# Client Registry
# ---------------------------------------------------------------------------

class ClientRegistry:
    """Thread-safe store of registered OAuth clients."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._clients: Dict[str, OAuthClient] = {}
        self._lock = threading.RLock()
        self._persist_path = persist_path
        if persist_path:
            self._load()

    def register(
        self,
        name: str,
        client_type: ClientType,
        redirect_uris: List[str],
        allowed_scopes: List[str],
        grant_types: List[GrantType],
        owner_id: str,
        metadata: Optional[Dict] = None,
    ) -> OAuthClient:
        client_id = "mcl_" + secrets.token_urlsafe(16)
        client_secret = secrets.token_urlsafe(32) if client_type == ClientType.CONFIDENTIAL else ""
        client = OAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            name=name,
            client_type=client_type,
            redirect_uris=redirect_uris,
            allowed_scopes=allowed_scopes,
            grant_types=grant_types,
            owner_id=owner_id,
            metadata=metadata or {},
        )
        with self._lock:
            self._clients[client_id] = client
        self._save()
        return client

    def get(self, client_id: str) -> Optional[OAuthClient]:
        with self._lock:
            return self._clients.get(client_id)

    def list_by_owner(self, owner_id: str) -> List[OAuthClient]:
        with self._lock:
            return [c for c in self._clients.values() if c.owner_id == owner_id]

    def deactivate(self, client_id: str) -> bool:
        with self._lock:
            c = self._clients.get(client_id)
            if not c:
                return False
            c.active = False
        self._save()
        return True

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            data = {cid: {
                "client_secret": c.client_secret, "name": c.name,
                "client_type": c.client_type.value,
                "redirect_uris": c.redirect_uris, "allowed_scopes": c.allowed_scopes,
                "grant_types": [g.value for g in c.grant_types],
                "owner_id": c.owner_id, "created_at": c.created_at,
                "active": c.active, "metadata": c.metadata,
            } for cid, c in self._clients.items()}
            tmp = self._persist_path + ".tmp"
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._persist_path)
        except Exception as exc:
            logger.error("ClientRegistry._save: %s", exc)

    def _load(self) -> None:
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path) as f:
                data = json.load(f)
            for cid, d in data.items():
                self._clients[cid] = OAuthClient(
                    client_id=cid,
                    client_secret=d["client_secret"],
                    name=d["name"],
                    client_type=ClientType(d["client_type"]),
                    redirect_uris=d["redirect_uris"],
                    allowed_scopes=d["allowed_scopes"],
                    grant_types=[GrantType(g) for g in d["grant_types"]],
                    owner_id=d["owner_id"],
                    created_at=d["created_at"],
                    active=d.get("active", True),
                    metadata=d.get("metadata", {}),
                )
            logger.info("ClientRegistry loaded %d clients", len(self._clients))
        except Exception as exc:
            logger.error("ClientRegistry._load: %s", exc)


# ---------------------------------------------------------------------------
# Token Store
# ---------------------------------------------------------------------------

class TokenStore:
    """Tracks issued tokens for introspection and revocation."""

    def __init__(self) -> None:
        self._tokens: Dict[str, TokenRecord] = {}
        self._lock   = threading.RLock()

    def record(self, rec: TokenRecord) -> None:
        with self._lock:
            self._tokens[rec.jti] = rec

    def get(self, jti: str) -> Optional[TokenRecord]:
        with self._lock:
            return self._tokens.get(jti)

    def revoke(self, jti: str) -> bool:
        with self._lock:
            rec = self._tokens.get(jti)
            if not rec:
                return False
            rec.revoked = True
            return True

    def revoke_for_client(self, client_id: str) -> int:
        count = 0
        with self._lock:
            for rec in self._tokens.values():
                if rec.client_id == client_id and not rec.revoked:
                    rec.revoked = True
                    count += 1
        return count

    def cleanup(self) -> int:
        """Remove expired tokens. Call periodically."""
        now = time.time()
        with self._lock:
            before = len(self._tokens)
            self._tokens = {jti: r for jti, r in self._tokens.items() if r.expires_at > now}
            return before - len(self._tokens)


# ---------------------------------------------------------------------------
# Authorization Server
# ---------------------------------------------------------------------------

class MurphyAuthorizationServer:
    """
    Murphy's OAuth 2.0 / OIDC Authorization Server.
    Singleton — instantiate once at startup.
    """

    _instance: Optional["MurphyAuthorizationServer"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MurphyAuthorizationServer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        persist_dir = os.environ.get("MURPHY_PERSISTENCE_DIR", "/var/lib/murphy-production")
        self._secret  = os.environ.get("MURPHY_JWT_SECRET", secrets.token_hex(32))
        self.clients  = ClientRegistry(persist_path=os.path.join(persist_dir, "oauth_clients.json"))
        self.tokens   = TokenStore()
        self._codes:  Dict[str, AuthorizationCode] = {}
        self._codes_lock = threading.RLock()
        logger.info("MurphyAuthorizationServer initialised (MOS-001)")

    # ── Authorization Code flow ─────────────────────────────────────────────

    def create_auth_code(
        self,
        client_id: str,
        user_id: str,
        scopes: List[str],
        redirect_uri: str,
        code_challenge: Optional[str],
    ) -> Optional[str]:
        client = self.clients.get(client_id)
        if not client or not client.active:
            return None
        if not client.redirect_allowed(redirect_uri):
            return None
        granted_scopes = client.scope_allowed(scopes)

        code = secrets.token_urlsafe(32)
        rec  = AuthorizationCode(
            code=code, client_id=client_id, user_id=user_id,
            scopes=granted_scopes, redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            expires_at=time.time() + AUTH_CODE_EXPIRY,
        )
        with self._codes_lock:
            self._codes[code] = rec
        return code

    def exchange_auth_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: Optional[str],
    ) -> Tuple[bool, Optional[Dict], str]:
        with self._codes_lock:
            rec = self._codes.get(code)
        if not rec:
            return False, None, "invalid_grant"
        if not rec.is_valid():
            return False, None, "code_expired"
        if rec.client_id != client_id:
            return False, None, "client_mismatch"
        if rec.redirect_uri != redirect_uri:
            return False, None, "redirect_mismatch"
        if rec.code_challenge and not rec.verify_pkce(code_verifier or ""):
            return False, None, "pkce_failed"

        rec.used = True  # single-use
        tokens = self._mint_tokens(rec.user_id, client_id, rec.scopes)
        return True, tokens, "ok"

    # ── Client Credentials flow ─────────────────────────────────────────────

    def client_credentials(
        self, client_id: str, client_secret: str, scopes: List[str]
    ) -> Tuple[bool, Optional[Dict], str]:
        client = self.clients.get(client_id)
        if not client or not client.active:
            return False, None, "invalid_client"
        if GrantType.CLIENT_CREDS not in client.grant_types:
            return False, None, "grant_type_not_allowed"
        if not client.verify_secret(client_secret):
            return False, None, "invalid_client_secret"
        granted = client.scope_allowed(scopes)
        tokens  = self._mint_tokens(f"client:{client_id}", client_id, granted, refresh=False)
        return True, tokens, "ok"

    # ── Refresh Token flow ──────────────────────────────────────────────────

    def refresh(self, refresh_token: str, client_id: str) -> Tuple[bool, Optional[Dict], str]:
        payload = _JWT.decode(refresh_token, self._secret)
        if not payload:
            return False, None, "invalid_token"
        if payload.get("type") != "refresh":
            return False, None, "not_refresh_token"
        if payload.get("client_id") != client_id:
            return False, None, "client_mismatch"
        jti = payload.get("jti", "")
        rec = self.tokens.get(jti)
        if not rec or not rec.is_valid():
            return False, None, "token_revoked_or_expired"

        self.tokens.revoke(jti)  # rotate refresh token
        tokens = self._mint_tokens(payload["sub"], client_id, payload.get("scopes", []))
        return True, tokens, "ok"

    # ── Introspection ────────────────────────────────────────────────────────

    def introspect(self, token: str) -> Dict[str, Any]:
        payload = _JWT.decode(token, self._secret)
        if not payload:
            return {"active": False}
        jti = payload.get("jti", "")
        rec = self.tokens.get(jti)
        if not rec or not rec.is_valid():
            return {"active": False}
        return {
            "active":    True,
            "sub":       payload.get("sub"),
            "client_id": payload.get("client_id"),
            "scope":     " ".join(payload.get("scopes", [])),
            "exp":       payload.get("exp"),
            "iat":       payload.get("iat"),
            "iss":       ISSUER,
            "jti":       jti,
        }

    # ── Revocation ───────────────────────────────────────────────────────────

    def revoke_token(self, token: str) -> bool:
        payload = _JWT.decode(token, self._secret)
        if not payload:
            return False
        return self.tokens.revoke(payload.get("jti", ""))

    # ── OIDC Discovery ───────────────────────────────────────────────────────

    def discovery_doc(self) -> Dict[str, Any]:
        return {
            "issuer":                                ISSUER,
            "authorization_endpoint":                f"{ISSUER}/oauth/authorize",
            "token_endpoint":                        f"{ISSUER}/oauth/token",
            "introspection_endpoint":                f"{ISSUER}/oauth/introspect",
            "revocation_endpoint":                   f"{ISSUER}/oauth/revoke",
            "jwks_uri":                              f"{ISSUER}/.well-known/jwks.json",
            "userinfo_endpoint":                     f"{ISSUER}/oauth/userinfo",
            "response_types_supported":              ["code"],
            "grant_types_supported":                 ["authorization_code", "client_credentials", "refresh_token"],
            "scopes_supported":                      SUPPORTED_SCOPES,
            "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
            "code_challenge_methods_supported":      ["S256"],
            "subject_types_supported":               ["public"],
            "id_token_signing_alg_values_supported": ["HS256"],
        }

    # ── Internal token minting ───────────────────────────────────────────────

    def _mint_tokens(
        self,
        subject: str,
        client_id: str,
        scopes: List[str],
        refresh: bool = True,
    ) -> Dict[str, Any]:
        now = int(time.time())
        access_jti  = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())

        access_payload = {
            "iss":       ISSUER,
            "sub":       subject,
            "client_id": client_id,
            "scopes":    scopes,
            "type":      "access",
            "jti":       access_jti,
            "iat":       now,
            "exp":       now + TOKEN_EXPIRY_ACCESS,
        }
        access_token = _JWT.encode(access_payload, self._secret)
        self.tokens.record(TokenRecord(
            jti=access_jti, subject=subject, client_id=client_id,
            scopes=scopes, token_type="access",
            expires_at=now + TOKEN_EXPIRY_ACCESS,
        ))

        result: Dict[str, Any] = {
            "access_token": access_token,
            "token_type":   "Bearer",
            "expires_in":   TOKEN_EXPIRY_ACCESS,
            "scope":        " ".join(scopes),
        }

        if refresh:
            refresh_payload = {
                "iss":       ISSUER,
                "sub":       subject,
                "client_id": client_id,
                "scopes":    scopes,
                "type":      "refresh",
                "jti":       refresh_jti,
                "iat":       now,
                "exp":       now + TOKEN_EXPIRY_REFRESH,
            }
            result["refresh_token"] = _JWT.encode(refresh_payload, self._secret)
            self.tokens.record(TokenRecord(
                jti=refresh_jti, subject=subject, client_id=client_id,
                scopes=scopes, token_type="refresh",
                expires_at=now + TOKEN_EXPIRY_REFRESH,
            ))

            if "openid" in scopes:
                id_payload = {**access_payload, "type": "id_token", "email": f"{subject}@murphy.systems"}
                result["id_token"] = _JWT.encode(id_payload, self._secret)

        return result

    def validate_bearer(self, token: str) -> Optional[Dict]:
        """Validate a Bearer token from an incoming request. Returns payload or None."""
        payload = _JWT.decode(token, self._secret)
        if not payload:
            return None
        if payload.get("type") != "access":
            return None
        jti = payload.get("jti", "")
        rec = self.tokens.get(jti)
        if not rec or not rec.is_valid():
            return None
        return payload


# ---------------------------------------------------------------------------
# Route factory (called from app.py)
# ---------------------------------------------------------------------------

def create_oauth_server_routes(app) -> None:
    """Register /oauth/* and /.well-known/* routes on the FastAPI app."""
    from urllib.parse import urlencode
    try:
        from fastapi import Request
    except ImportError:
        from starlette.requests import Request
    from starlette.responses import JSONResponse, RedirectResponse, HTMLResponse

    server = MurphyAuthorizationServer()

    def _err(code: str, desc: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"error": code, "error_description": desc}, status_code=status)

    # ── OIDC Discovery ───────────────────────────────────────────────────────

    @app.get("/.well-known/openid-configuration")
    async def oidc_discovery():
        return JSONResponse(server.discovery_doc())

    @app.get("/.well-known/jwks.json")
    async def jwks():
        # HS256 — no public key to expose. Return empty keyset.
        # RS256 migration: populate here with RSA public key.
        return JSONResponse({"keys": []})

    # ── Client Registration ──────────────────────────────────────────────────

    @app.post("/oauth/clients")
    async def register_client(request: Request):
        session_user = getattr(request.state, "user", None)
        if not session_user:
            return _err("unauthorized", "Login required to register OAuth clients", 401)
        body = await request.json()
        client_type = ClientType(body.get("client_type", "confidential"))
        grant_types = [GrantType(g) for g in body.get("grant_types", ["authorization_code"])]
        client = server.clients.register(
            name=body.get("name", "Unnamed App"),
            client_type=client_type,
            redirect_uris=body.get("redirect_uris", []),
            allowed_scopes=body.get("scopes", ["openid", "profile"]),
            grant_types=grant_types,
            owner_id=session_user.get("user_id", "unknown"),
            metadata=body.get("metadata", {}),
        )
        result = client.to_dict()
        if client_type == ClientType.CONFIDENTIAL:
            result["client_secret"] = client.client_secret  # shown once
        return JSONResponse(result, status_code=201)

    @app.get("/oauth/clients")
    async def list_clients(request: Request):
        session_user = getattr(request.state, "user", None)
        if not session_user:
            return _err("unauthorized", "Login required", 401)
        clients = server.clients.list_by_owner(session_user.get("user_id", ""))
        return JSONResponse({"clients": [c.to_dict() for c in clients]})

    @app.delete("/oauth/clients/{client_id}")
    async def deactivate_client(request: Request, client_id: str):
        session_user = getattr(request.state, "user", None)
        if not session_user:
            return _err("unauthorized", "Login required", 401)
        ok = server.clients.deactivate(client_id)
        return JSONResponse({"deactivated": ok})

    # ── Authorization Endpoint ───────────────────────────────────────────────

    @app.get("/oauth/authorize")
    async def authorize(request: Request):
        p = request.query_params
        client_id     = p.get("client_id", "")
        redirect_uri  = p.get("redirect_uri", "")
        scope         = p.get("scope", "openid")
        state         = p.get("state", "")
        code_challenge = p.get("code_challenge")
        response_type = p.get("response_type", "code")

        if response_type != "code":
            return _err("unsupported_response_type", "Only 'code' is supported")

        client = server.clients.get(client_id)
        if not client:
            return _err("invalid_client", "Unknown client_id")
        if not client.redirect_allowed(redirect_uri):
            return _err("invalid_redirect_uri", "redirect_uri not registered")

        # Render consent page
        scope_list = scope.split()
        scope_html = "".join(f"<li>{s}</li>" for s in scope_list)
        html = f"""<!DOCTYPE html><html><head>
        <title>Murphy Authorization</title>
        <style>body{{font-family:system-ui;max-width:400px;margin:80px auto;padding:20px;background:#0f0f14;color:#e2e8f0}}
        .card{{background:#1a1a2e;border-radius:12px;padding:30px;border:1px solid #2d2d4e}}
        h2{{color:#7c3aed;margin:0 0 8px}}
        .app{{color:#a78bfa;font-weight:600;font-size:1.1em}}
        ul{{color:#94a3b8;margin:16px 0}}
        .btns{{display:flex;gap:12px;margin-top:24px}}
        button{{flex:1;padding:12px;border-radius:8px;border:none;cursor:pointer;font-size:1em;font-weight:600}}
        .allow{{background:#7c3aed;color:#fff}}
        .deny{{background:#374151;color:#e2e8f0}}
        </style></head><body>
        <div class="card">
          <h2>Murphy System</h2>
          <p>The app <span class="app">{client.name}</span> is requesting access to your Murphy instance.</p>
          <p><strong>Requested permissions:</strong></p>
          <ul>{scope_html}</ul>
          <form method="POST" action="/oauth/authorize/confirm">
            <input type="hidden" name="client_id"      value="{client_id}"/>
            <input type="hidden" name="redirect_uri"   value="{redirect_uri}"/>
            <input type="hidden" name="scope"          value="{scope}"/>
            <input type="hidden" name="state"          value="{state}"/>
            <input type="hidden" name="code_challenge" value="{code_challenge or ''}"/>
            <div class="btns">
              <button type="submit" name="decision" value="allow"  class="allow">Allow</button>
              <button type="submit" name="decision" value="deny"   class="deny">Deny</button>
            </div>
          </form>
        </div></body></html>"""
        return HTMLResponse(html)

    @app.post("/oauth/authorize/confirm")
    async def authorize_confirm(request: Request):
        session_user = getattr(request.state, "user", None)
        if not session_user:
            # Redirect to login, preserving original query
            return RedirectResponse("/ui/login?next=/oauth/authorize", status_code=302)

        form = await request.form()
        decision      = form.get("decision", "deny")
        client_id     = form.get("client_id", "")
        redirect_uri  = form.get("redirect_uri", "")
        scope         = form.get("scope", "openid")
        state         = form.get("state", "")
        code_challenge = form.get("code_challenge") or None

        if decision != "allow":
            params = urlencode({"error": "access_denied", "state": state})
            return RedirectResponse(f"{redirect_uri}?{params}", status_code=302)

        user_id = session_user.get("user_id", "unknown")
        code = server.create_auth_code(
            client_id=client_id,
            user_id=user_id,
            scopes=scope.split(),
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
        )
        if not code:
            return _err("server_error", "Could not issue authorization code")

        params = urlencode({"code": code, "state": state})
        return RedirectResponse(f"{redirect_uri}?{params}", status_code=302)

    # ── Token Endpoint ───────────────────────────────────────────────────────

    @app.post("/oauth/token")
    async def token_endpoint(request: Request):
        ct = request.headers.get("content-type", "")
        if "json" in ct:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)

        grant_type = body.get("grant_type", "")

        if grant_type == GrantType.AUTH_CODE:
            ok, tokens, reason = server.exchange_auth_code(
                code=body.get("code", ""),
                client_id=body.get("client_id", ""),
                redirect_uri=body.get("redirect_uri", ""),
                code_verifier=body.get("code_verifier"),
            )
            if not ok:
                return _err("invalid_grant", reason)
            return JSONResponse(tokens)

        elif grant_type == GrantType.CLIENT_CREDS:
            ok, tokens, reason = server.client_credentials(
                client_id=body.get("client_id", ""),
                client_secret=body.get("client_secret", ""),
                scopes=body.get("scope", "").split(),
            )
            if not ok:
                return _err("invalid_client", reason)
            return JSONResponse(tokens)

        elif grant_type == GrantType.REFRESH:
            ok, tokens, reason = server.refresh(
                refresh_token=body.get("refresh_token", ""),
                client_id=body.get("client_id", ""),
            )
            if not ok:
                return _err("invalid_grant", reason)
            return JSONResponse(tokens)

        return _err("unsupported_grant_type", f"Unsupported: {grant_type}")

    # ── Introspection ────────────────────────────────────────────────────────

    @app.post("/oauth/introspect")
    async def introspect(request: Request):
        form = await request.form()
        token = form.get("token", "")
        return JSONResponse(server.introspect(token))

    # ── Revocation ───────────────────────────────────────────────────────────

    @app.post("/oauth/revoke")
    async def revoke(request: Request):
        form = await request.form()
        token = form.get("token", "")
        server.revoke_token(token)
        return JSONResponse({})   # always 200 per RFC 7009

    # ── UserInfo ─────────────────────────────────────────────────────────────

    @app.get("/oauth/userinfo")
    async def userinfo(request: Request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _err("invalid_token", "Bearer token required", 401)
        token   = auth[7:]
        payload = server.validate_bearer(token)
        if not payload:
            return _err("invalid_token", "Token invalid or expired", 401)
        return JSONResponse({
            "sub":   payload["sub"],
            "iss":   ISSUER,
            "scope": " ".join(payload.get("scopes", [])),
        })

    logger.info("PATCH-065b: OAuth server routes registered (/oauth/*, /.well-known/*)")

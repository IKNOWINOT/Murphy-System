"""
OAuth Provider Registry
========================

Manages OAuth provider configurations and sign-up/sign-in flows for
Microsoft, Google, Meta, and extensible custom providers.

Each provider is registered with its OAuth endpoints, client credentials,
scopes, and profile-mapping function.  The registry handles:
- Authorization URL generation with PKCE + state
- Token exchange (authorization code → access + refresh tokens)
- Profile normalization across providers
- Token refresh lifecycle

Design Label: ACCT-002
Owner: Platform Engineering

Note: In a production deployment, the actual HTTP calls to OAuth endpoints
require a running server with callback URLs.  This module provides the
orchestration logic and can be used with any HTTP client.
"""

import hashlib
import logging
import os
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from account_management.models import OAuthProvider, OAuthToken

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_TTL_SECONDS = 600  # 10 minutes
_MAX_PROVIDERS = 50


# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------


@dataclass
class OAuthProviderConfig:
    """Configuration for a single OAuth provider."""
    provider: OAuthProvider
    client_id: str = ""
    client_secret_encrypted: str = ""
    authorize_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    scopes: List[str] = field(default_factory=list)
    redirect_uri: str = ""
    enabled: bool = True
    profile_mapper: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "authorize_url": self.authorize_url,
            "token_url": self.token_url,
            "userinfo_url": self.userinfo_url,
            "scopes": self.scopes,
            "redirect_uri": self.redirect_uri,
            "enabled": self.enabled,
            "has_client_id": bool(self.client_id),
            "has_client_secret": bool(self.client_secret_encrypted),
        }


@dataclass
class PendingAuthState:
    """Tracks a pending OAuth authorization flow."""
    state: str
    provider: OAuthProvider
    code_verifier: str  # PKCE
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_expired(self) -> bool:
        try:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.now(timezone.utc) - created).total_seconds() > _STATE_TTL_SECONDS
        except (ValueError, TypeError):
            return True


# ---------------------------------------------------------------------------
# Default Profile Mappers
# ---------------------------------------------------------------------------


def _microsoft_profile_mapper(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Microsoft Graph /me response."""
    return {
        "email": raw.get("mail") or raw.get("userPrincipalName", ""),
        "display_name": raw.get("displayName", ""),
        "given_name": raw.get("givenName", ""),
        "family_name": raw.get("surname", ""),
        "provider_user_id": raw.get("id", ""),
    }


def _google_profile_mapper(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Google userinfo response."""
    return {
        "email": raw.get("email", ""),
        "display_name": raw.get("name", ""),
        "given_name": raw.get("given_name", ""),
        "family_name": raw.get("family_name", ""),
        "provider_user_id": raw.get("sub", ""),
        "picture": raw.get("picture", ""),
    }


def _meta_profile_mapper(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Meta /me response."""
    return {
        "email": raw.get("email", ""),
        "display_name": raw.get("name", ""),
        "given_name": raw.get("first_name", ""),
        "family_name": raw.get("last_name", ""),
        "provider_user_id": raw.get("id", ""),
    }


def _linkedin_profile_mapper(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a LinkedIn userinfo (OIDC) response."""
    return {
        "email": raw.get("email", ""),
        "display_name": raw.get("name", ""),
        "given_name": raw.get("given_name", ""),
        "family_name": raw.get("family_name", ""),
        "provider_user_id": raw.get("sub", ""),
        "picture": raw.get("picture", ""),
    }


def _apple_profile_mapper(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an Apple Sign In token/userinfo response."""
    name_obj = raw.get("name") or {}
    given = name_obj.get("firstName", "") if isinstance(name_obj, dict) else ""
    family = name_obj.get("lastName", "") if isinstance(name_obj, dict) else ""
    display = f"{given} {family}".strip() or raw.get("email", "")
    return {
        "email": raw.get("email", ""),
        "display_name": display,
        "given_name": given,
        "family_name": family,
        "provider_user_id": raw.get("sub", ""),
    }


# ---------------------------------------------------------------------------
# Default Provider Configurations
# ---------------------------------------------------------------------------


def _default_providers() -> Dict[str, OAuthProviderConfig]:
    """Pre-configured OAuth providers (credentials loaded from env)."""
    return {
        OAuthProvider.MICROSOFT.value: OAuthProviderConfig(
            provider=OAuthProvider.MICROSOFT,
            client_id=os.environ.get("MURPHY_OAUTH_MICROSOFT_CLIENT_ID", ""),
            client_secret_encrypted=os.environ.get("MURPHY_OAUTH_MICROSOFT_SECRET", ""),
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            userinfo_url="https://graph.microsoft.com/v1.0/me",
            scopes=["openid", "profile", "email", "User.Read"],
            redirect_uri=os.environ.get(
                "MURPHY_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback"
            ),
            profile_mapper=_microsoft_profile_mapper,
        ),
        OAuthProvider.GOOGLE.value: OAuthProviderConfig(
            provider=OAuthProvider.GOOGLE,
            client_id=os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID", ""),
            client_secret_encrypted=os.environ.get("MURPHY_OAUTH_GOOGLE_SECRET", ""),
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scopes=["openid", "profile", "email"],
            redirect_uri=os.environ.get(
                "MURPHY_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback"
            ),
            profile_mapper=_google_profile_mapper,
        ),
        OAuthProvider.META.value: OAuthProviderConfig(
            provider=OAuthProvider.META,
            client_id=os.environ.get("MURPHY_OAUTH_META_CLIENT_ID", ""),
            client_secret_encrypted=os.environ.get("MURPHY_OAUTH_META_SECRET", ""),
            authorize_url="https://www.facebook.com/v18.0/dialog/oauth",
            token_url="https://graph.facebook.com/v18.0/oauth/access_token",
            userinfo_url="https://graph.facebook.com/v18.0/me?fields=id,name,email,first_name,last_name",
            scopes=["email", "public_profile"],
            redirect_uri=os.environ.get(
                "MURPHY_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback"
            ),
            profile_mapper=_meta_profile_mapper,
        ),
        OAuthProvider.LINKEDIN.value: OAuthProviderConfig(
            provider=OAuthProvider.LINKEDIN,
            client_id=os.environ.get("MURPHY_OAUTH_LINKEDIN_CLIENT_ID", ""),
            client_secret_encrypted=os.environ.get("MURPHY_OAUTH_LINKEDIN_SECRET", ""),
            authorize_url="https://www.linkedin.com/oauth/v2/authorization",
            token_url="https://www.linkedin.com/oauth/v2/accessToken",
            userinfo_url="https://api.linkedin.com/v2/userinfo",
            scopes=["openid", "profile", "email"],
            redirect_uri=os.environ.get(
                "MURPHY_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback"
            ),
            profile_mapper=_linkedin_profile_mapper,
        ),
        OAuthProvider.APPLE.value: OAuthProviderConfig(
            provider=OAuthProvider.APPLE,
            client_id=os.environ.get("MURPHY_OAUTH_APPLE_CLIENT_ID", ""),
            client_secret_encrypted=os.environ.get("MURPHY_OAUTH_APPLE_SECRET", ""),
            authorize_url="https://appleid.apple.com/auth/authorize",
            token_url="https://appleid.apple.com/auth/token",
            userinfo_url="",
            scopes=["name", "email"],
            redirect_uri=os.environ.get(
                "MURPHY_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback"
            ),
            profile_mapper=_apple_profile_mapper,
        ),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class OAuthProviderRegistry:
    """Central registry for OAuth providers.

    Usage::

        registry = OAuthProviderRegistry()
        url, state = registry.begin_auth_flow(OAuthProvider.GOOGLE)
        # redirect user to url ...
        token = registry.complete_auth_flow(state, authorization_code)
    """

    def __init__(self, providers: Optional[Dict[str, OAuthProviderConfig]] = None) -> None:
        self._lock = threading.Lock()
        self._providers: Dict[str, OAuthProviderConfig] = (
            providers if providers is not None else _default_providers()
        )
        self._pending_states: Dict[str, PendingAuthState] = {}

    # -- Provider management ------------------------------------------------

    def register_provider(self, config: OAuthProviderConfig) -> bool:
        """Register or update an OAuth provider configuration."""
        with self._lock:
            if len(self._providers) >= _MAX_PROVIDERS and config.provider.value not in self._providers:
                return False
            self._providers[config.provider.value] = config
            return True

    def get_provider(self, provider: OAuthProvider) -> Optional[OAuthProviderConfig]:
        """Get the configuration for a provider."""
        with self._lock:
            return self._providers.get(provider.value)

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all registered providers (safe dict form)."""
        with self._lock:
            return [cfg.to_dict() for cfg in self._providers.values()]

    def list_enabled_providers(self) -> List[str]:
        """Return provider names that are enabled and have client IDs."""
        with self._lock:
            return [
                name for name, cfg in self._providers.items()
                if cfg.enabled and cfg.client_id
            ]

    def disable_provider(self, provider: OAuthProvider) -> bool:
        with self._lock:
            cfg = self._providers.get(provider.value)
            if cfg:
                cfg.enabled = False
                return True
            return False

    def enable_provider(self, provider: OAuthProvider) -> bool:
        with self._lock:
            cfg = self._providers.get(provider.value)
            if cfg:
                cfg.enabled = True
                return True
            return False

    # -- PKCE helpers -------------------------------------------------------

    @staticmethod
    def _generate_pkce() -> Tuple[str, str]:
        """Generate a PKCE code_verifier and code_challenge."""
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        import base64
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    # -- Auth flow ----------------------------------------------------------

    def begin_auth_flow(self, provider: OAuthProvider) -> Tuple[str, str]:
        """Start an OAuth authorization flow.

        Returns:
            (authorize_url, state) — redirect the user to authorize_url.
            The state token is used to complete the flow later.

        Raises:
            ValueError: if provider is not registered or not enabled.
        """
        with self._lock:
            cfg = self._providers.get(provider.value)
        if cfg is None:
            raise ValueError(f"Unknown provider: {provider.value}")
        if not cfg.enabled:
            raise ValueError(f"Provider {provider.value} is disabled")
        if not cfg.client_id:
            raise ValueError(
                f"Provider {provider.value} has no client_id configured "
                "(set MURPHY_OAUTH_{PROVIDER}_CLIENT_ID)"
            )

        state = secrets.token_urlsafe(32)
        verifier, challenge = self._generate_pkce()

        pending = PendingAuthState(
            state=state,
            provider=provider,
            code_verifier=verifier,
        )

        with self._lock:
            self._cleanup_expired_states()
            self._pending_states[state] = pending

        # Build authorize URL
        params = {
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "response_type": "code",
            "scope": " ".join(cfg.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{cfg.authorize_url}?{query}"

        logger.info("OAuth flow started for %s (state=%s...)", provider.value, state[:8])
        return url, state

    def complete_auth_flow(
        self,
        state: str,
        authorization_code: str,
        *,
        token_response: Optional[Dict[str, Any]] = None,
        profile_response: Optional[Dict[str, Any]] = None,
    ) -> OAuthToken:
        """Complete an OAuth flow after user authorization.

        When ``token_response`` is *not* provided (i.e., a real production
        flow), this method makes an actual HTTP POST to ``cfg.token_url`` to
        exchange the authorization code for tokens, then fetches the user
        profile from ``cfg.userinfo_url``.

        For testability, callers may pass ``token_response`` and
        ``profile_response`` directly to bypass the HTTP calls.

        Raises:
            ValueError: if the state is invalid/expired.
            RuntimeError: if the HTTP token exchange fails.
        """
        with self._lock:
            pending = self._pending_states.pop(state, None)
        if pending is None:
            raise ValueError("Invalid or expired OAuth state")
        if pending.is_expired():
            raise ValueError("OAuth state has expired")

        with self._lock:
            cfg = self._providers.get(pending.provider.value)
        if cfg is None:
            raise ValueError(f"Provider {pending.provider.value} no longer registered")

        if token_response is None:
            # ── Real HTTP token exchange ────────────────────────────────
            tok_resp, profile_resp = self._exchange_code_for_token(
                cfg=cfg,
                authorization_code=authorization_code,
                code_verifier=pending.code_verifier,
            )
        else:
            # ── Test / injected path ────────────────────────────────────
            tok_resp = token_response
            profile_resp = profile_response or {}

        # Normalize profile
        profile = {}
        if cfg.profile_mapper and profile_resp:
            profile = cfg.profile_mapper(profile_resp)

        expires_at = None
        if "expires_in" in tok_resp:
            try:
                expires_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=int(tok_resp["expires_in"]))
                ).isoformat()
            except (ValueError, TypeError) as exc:
                logger.debug("Could not parse expires_in: %s", exc)

        token = OAuthToken(
            provider=pending.provider,
            access_token=tok_resp.get("access_token", authorization_code),
            refresh_token=tok_resp.get("refresh_token"),
            token_type=tok_resp.get("token_type", "Bearer"),
            expires_at=expires_at,
            scopes=tok_resp.get("scope", "").split() if isinstance(tok_resp.get("scope"), str) else [],
            raw_profile=profile,
        )
        logger.info("OAuth flow completed for %s", pending.provider.value)
        return token

    def _exchange_code_for_token(
        self,
        cfg: "OAuthProviderConfig",
        authorization_code: str,
        code_verifier: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Exchange an authorization code for tokens via HTTP POST, then
        fetch the user profile.

        Returns
        -------
        (tok_resp, profile_resp)
        """
        try:
            import httpx
        except ImportError:
            raise RuntimeError(
                "httpx is required for real OAuth token exchange. "
                "Install it with: pip install httpx"
            )

        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": cfg.redirect_uri,
            "client_id": cfg.client_id,
            "code_verifier": code_verifier,
        }
        if cfg.client_secret_encrypted:
            payload["client_secret"] = cfg.client_secret_encrypted

        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(cfg.token_url, data=payload)
            if token_resp.status_code != 200:
                raise RuntimeError(
                    f"Token exchange failed: HTTP {token_resp.status_code} — {token_resp.text[:200]}"
                )
            tok_resp = token_resp.json()

            # Fetch user profile if a userinfo URL is configured
            profile_resp: Dict[str, Any] = {}
            if cfg.userinfo_url and tok_resp.get("access_token"):
                info_resp = client.get(
                    cfg.userinfo_url,
                    headers={"Authorization": f"Bearer {tok_resp['access_token']}"},
                )
                if info_resp.status_code == 200:
                    profile_resp = info_resp.json()
                else:
                    logger.warning(
                        "Userinfo request returned HTTP %d for %s",
                        info_resp.status_code,
                        cfg.provider.value,
                    )

        return tok_resp, profile_resp

    def get_pending_state(self, state: str) -> Optional[PendingAuthState]:
        """Look up a pending auth state (for testing/debugging)."""
        with self._lock:
            return self._pending_states.get(state)

    def _cleanup_expired_states(self) -> int:
        """Remove expired pending states.  Returns count removed."""
        expired = [s for s, p in self._pending_states.items() if p.is_expired()]
        for s in expired:
            del self._pending_states[s]
        return len(expired)

    def get_status(self) -> Dict[str, Any]:
        """System status summary."""
        with self._lock:
            return {
                "total_providers": len(self._providers),
                "enabled_providers": sum(
                    1 for c in self._providers.values() if c.enabled
                ),
                "configured_providers": sum(
                    1 for c in self._providers.values() if c.client_id
                ),
                "pending_auth_flows": len(self._pending_states),
            }

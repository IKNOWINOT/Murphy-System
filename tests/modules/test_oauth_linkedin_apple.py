"""
Tests for LinkedIn and Apple OAuth provider additions.

Covers:
  - OAuthProvider enum has LINKEDIN and APPLE
  - Profile mappers for LinkedIn and Apple normalize correctly
  - Default provider registry includes LinkedIn and Apple
  - Authorization URL generation works for both providers
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from account_management.models import OAuthProvider
from account_management.oauth_provider_registry import (
    OAuthProviderRegistry,
    OAuthProviderConfig,
    _linkedin_profile_mapper,
    _apple_profile_mapper,
    _default_providers,
)


# ---------------------------------------------------------------------------
# OAuthProvider enum
# ---------------------------------------------------------------------------

class TestOAuthProviderEnum:
    def test_linkedin_in_enum(self):
        assert OAuthProvider.LINKEDIN == "linkedin"

    def test_apple_in_enum(self):
        assert OAuthProvider.APPLE == "apple"

    def test_linkedin_value(self):
        assert OAuthProvider.LINKEDIN.value == "linkedin"

    def test_apple_value(self):
        assert OAuthProvider.APPLE.value == "apple"

    def test_existing_providers_unchanged(self):
        assert OAuthProvider.GOOGLE == "google"
        assert OAuthProvider.META == "meta"
        assert OAuthProvider.GITHUB == "github"
        assert OAuthProvider.MICROSOFT == "microsoft"


# ---------------------------------------------------------------------------
# LinkedIn profile mapper
# ---------------------------------------------------------------------------

class TestLinkedInProfileMapper:
    def test_maps_standard_oidc_fields(self):
        raw = {
            "sub": "linkedin-user-123",
            "name": "Alice Smith",
            "given_name": "Alice",
            "family_name": "Smith",
            "email": "alice@example.com",
            "picture": "https://media.licdn.com/photo.jpg",
        }
        result = _linkedin_profile_mapper(raw)
        assert result["provider_user_id"] == "linkedin-user-123"
        assert result["display_name"] == "Alice Smith"
        assert result["given_name"] == "Alice"
        assert result["family_name"] == "Smith"
        assert result["email"] == "alice@example.com"
        assert result["picture"] == "https://media.licdn.com/photo.jpg"

    def test_empty_response_returns_empty_strings(self):
        result = _linkedin_profile_mapper({})
        assert result["email"] == ""
        assert result["display_name"] == ""
        assert result["given_name"] == ""
        assert result["family_name"] == ""
        assert result["provider_user_id"] == ""

    def test_partial_response(self):
        result = _linkedin_profile_mapper({"email": "bob@example.com", "sub": "123"})
        assert result["email"] == "bob@example.com"
        assert result["provider_user_id"] == "123"
        assert result["display_name"] == ""


# ---------------------------------------------------------------------------
# Apple profile mapper
# ---------------------------------------------------------------------------

class TestAppleProfileMapper:
    def test_maps_sub_and_email(self):
        raw = {
            "sub": "apple-user-456",
            "email": "user@privaterelay.appleid.com",
            "name": {"firstName": "Bob", "lastName": "Jones"},
        }
        result = _apple_profile_mapper(raw)
        assert result["provider_user_id"] == "apple-user-456"
        assert result["email"] == "user@privaterelay.appleid.com"
        assert result["given_name"] == "Bob"
        assert result["family_name"] == "Jones"
        assert result["display_name"] == "Bob Jones"

    def test_display_name_falls_back_to_email(self):
        raw = {"sub": "abc", "email": "anon@example.com"}
        result = _apple_profile_mapper(raw)
        assert result["display_name"] == "anon@example.com"

    def test_empty_response(self):
        result = _apple_profile_mapper({})
        assert result["email"] == ""
        assert result["provider_user_id"] == ""

    def test_name_dict_not_present(self):
        raw = {"sub": "xyz", "email": "test@example.com"}
        result = _apple_profile_mapper(raw)
        assert result["given_name"] == ""
        assert result["family_name"] == ""

    def test_name_only_first_name(self):
        raw = {"sub": "xyz", "email": "t@e.com", "name": {"firstName": "Jane"}}
        result = _apple_profile_mapper(raw)
        assert result["given_name"] == "Jane"
        assert result["family_name"] == ""
        assert result["display_name"] == "Jane"


# ---------------------------------------------------------------------------
# Default providers registry includes LinkedIn and Apple
# ---------------------------------------------------------------------------

class TestDefaultProviders:
    def test_linkedin_in_defaults(self):
        providers = _default_providers()
        assert "linkedin" in providers

    def test_apple_in_defaults(self):
        providers = _default_providers()
        assert "apple" in providers

    def test_linkedin_urls(self):
        providers = _default_providers()
        cfg = providers["linkedin"]
        assert cfg.authorize_url == "https://www.linkedin.com/oauth/v2/authorization"
        assert cfg.token_url == "https://www.linkedin.com/oauth/v2/accessToken"
        assert cfg.userinfo_url == "https://api.linkedin.com/v2/userinfo"
        assert "openid" in cfg.scopes
        assert "profile" in cfg.scopes
        assert "email" in cfg.scopes

    def test_apple_urls(self):
        providers = _default_providers()
        cfg = providers["apple"]
        assert cfg.authorize_url == "https://appleid.apple.com/auth/authorize"
        assert cfg.token_url == "https://appleid.apple.com/auth/token"
        assert "name" in cfg.scopes
        assert "email" in cfg.scopes

    def test_linkedin_profile_mapper_set(self):
        providers = _default_providers()
        cfg = providers["linkedin"]
        assert cfg.profile_mapper is not None
        assert callable(cfg.profile_mapper)

    def test_apple_profile_mapper_set(self):
        providers = _default_providers()
        cfg = providers["apple"]
        assert cfg.profile_mapper is not None
        assert callable(cfg.profile_mapper)

    def test_linkedin_provider_enum_matches(self):
        providers = _default_providers()
        cfg = providers["linkedin"]
        assert cfg.provider == OAuthProvider.LINKEDIN

    def test_apple_provider_enum_matches(self):
        providers = _default_providers()
        cfg = providers["apple"]
        assert cfg.provider == OAuthProvider.APPLE


# ---------------------------------------------------------------------------
# Registry: authorization URL generation
# ---------------------------------------------------------------------------

class TestRegistryAuthFlows:
    def test_registry_has_linkedin(self):
        registry = OAuthProviderRegistry()
        cfg = registry.get_provider(OAuthProvider.LINKEDIN)
        assert cfg is not None
        assert cfg.provider == OAuthProvider.LINKEDIN

    def test_registry_has_apple(self):
        registry = OAuthProviderRegistry()
        cfg = registry.get_provider(OAuthProvider.APPLE)
        assert cfg is not None
        assert cfg.provider == OAuthProvider.APPLE

    def test_linkedin_begin_auth_flow_returns_url_and_state(self):
        registry = OAuthProviderRegistry()
        # Provide a fake client_id so the URL can be constructed
        cfg = registry.get_provider(OAuthProvider.LINKEDIN)
        cfg.client_id = "fake-linkedin-client-id"
        url, state = registry.begin_auth_flow(OAuthProvider.LINKEDIN)
        assert "linkedin.com" in url
        assert len(state) > 0
        assert "client_id=fake-linkedin-client-id" in url

    def test_apple_begin_auth_flow_returns_url_and_state(self):
        registry = OAuthProviderRegistry()
        cfg = registry.get_provider(OAuthProvider.APPLE)
        cfg.client_id = "fake-apple-client-id"
        url, state = registry.begin_auth_flow(OAuthProvider.APPLE)
        assert "appleid.apple.com" in url
        assert len(state) > 0

    def test_state_contains_code_challenge(self):
        """PKCE: the auth URL must contain code_challenge."""
        registry = OAuthProviderRegistry()
        cfg = registry.get_provider(OAuthProvider.LINKEDIN)
        cfg.client_id = "cli"
        url, _ = registry.begin_auth_flow(OAuthProvider.LINKEDIN)
        assert "code_challenge" in url

    def test_list_providers_includes_linkedin_and_apple(self):
        registry = OAuthProviderRegistry()
        providers = registry.list_providers()
        provider_names = [p["provider"] for p in providers]
        assert "linkedin" in provider_names
        assert "apple" in provider_names

    def test_register_custom_linkedin_config(self):
        registry = OAuthProviderRegistry()
        custom = OAuthProviderConfig(
            provider=OAuthProvider.LINKEDIN,
            client_id="custom-id",
            authorize_url="https://www.linkedin.com/oauth/v2/authorization",
            token_url="https://www.linkedin.com/oauth/v2/accessToken",
            scopes=["openid", "profile", "email"],
        )
        result = registry.register_provider(custom)
        assert result is True
        cfg = registry.get_provider(OAuthProvider.LINKEDIN)
        assert cfg.client_id == "custom-id"

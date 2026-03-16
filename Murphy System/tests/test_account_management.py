"""
Tests for Account Management & OAuth Integration System
=========================================================

Validates:
- Data models (AccountRecord, OAuthToken, StoredCredential, ConsentRecord)
- OAuth Provider Registry (Microsoft, Google, Meta, custom)
- Credential Vault (encrypt, decrypt, verify, rotate, remove)
- Account Manager (create, OAuth signup, link/unlink, credentials, consent)
- Consent-based credential import flow
- Auto-ticketing for missing integrations
- Audit log completeness
- Thread safety
- Edge cases and error handling

Design Labels: TEST-ACCT-001, TEST-ACCT-002, TEST-ACCT-003
Owner: QA Team
"""

import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from account_management.models import (
    AccountEvent,
    AccountEventType,
    AccountRecord,
    AccountStatus,
    ConsentRecord,
    ConsentStatus,
    OAuthProvider,
    OAuthToken,
    StoredCredential,
)
from account_management.credential_vault import (
    CredentialVault,
    _encrypt,
    _decrypt,
    _hash_prefix,
)
from account_management.oauth_provider_registry import (
    OAuthProviderConfig,
    OAuthProviderRegistry,
    PendingAuthState,
    _google_profile_mapper,
    _meta_profile_mapper,
    _microsoft_profile_mapper,
)
from account_management.account_manager import (
    AccountManager,
    KNOWN_INTEGRATION_SERVICES,
)


# ===================================================================
# Class 1: Data Model Tests
# ===================================================================


class TestOAuthProvider:
    """Validate OAuthProvider enum values."""

    def test_microsoft_value(self):
        assert OAuthProvider.MICROSOFT.value == "microsoft"

    def test_google_value(self):
        assert OAuthProvider.GOOGLE.value == "google"

    def test_meta_value(self):
        assert OAuthProvider.META.value == "meta"

    def test_github_value(self):
        assert OAuthProvider.GITHUB.value == "github"

    def test_custom_value(self):
        assert OAuthProvider.CUSTOM.value == "custom"


class TestAccountStatus:
    """Validate AccountStatus enum values."""

    def test_all_statuses_defined(self):
        expected = {"pending", "active", "suspended", "deactivated"}
        actual = {s.value for s in AccountStatus}
        assert actual == expected


class TestConsentStatus:
    """Validate ConsentStatus enum values."""

    def test_all_statuses_defined(self):
        expected = {"pending", "granted", "denied", "revoked"}
        actual = {s.value for s in ConsentStatus}
        assert actual == expected


class TestAccountEventType:
    """Validate AccountEventType enum values."""

    def test_has_core_events(self):
        core = [
            "account_created", "oauth_linked", "oauth_unlinked",
            "password_set", "password_changed",
            "credential_stored", "credential_rotated", "credential_removed",
            "consent_requested", "consent_granted", "consent_denied", "consent_revoked",
            "status_changed", "missing_integration_ticket",
            "login", "logout",
        ]
        actual_values = {e.value for e in AccountEventType}
        for c in core:
            assert c in actual_values, f"Missing event type: {c}"


class TestOAuthToken:
    """Validate OAuthToken model."""

    def test_token_creation(self):
        token = OAuthToken(
            provider=OAuthProvider.GOOGLE,
            access_token="access-123",
            refresh_token="refresh-456",
        )
        assert token.provider == OAuthProvider.GOOGLE
        assert token.access_token == "access-123"
        assert token.refresh_token == "refresh-456"
        assert token.token_type == "Bearer"

    def test_token_not_expired_when_no_expiry(self):
        token = OAuthToken(provider=OAuthProvider.GOOGLE, access_token="x")
        assert token.is_expired() is False

    def test_token_expired_when_past(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        token = OAuthToken(
            provider=OAuthProvider.GOOGLE, access_token="x", expires_at=past
        )
        assert token.is_expired() is True

    def test_token_not_expired_when_future(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        token = OAuthToken(
            provider=OAuthProvider.GOOGLE, access_token="x", expires_at=future
        )
        assert token.is_expired() is False

    def test_to_dict_never_contains_access_token(self):
        token = OAuthToken(
            provider=OAuthProvider.GOOGLE,
            access_token="secret-access-token",
            refresh_token="secret-refresh-token",
        )
        d = token.to_dict()
        assert "access_token" not in d
        assert "refresh_token" not in d
        assert d["has_refresh_token"] is True
        assert d["provider"] == "google"


class TestStoredCredential:
    """Validate StoredCredential model."""

    def test_creation_with_defaults(self):
        cred = StoredCredential()
        assert cred.credential_id.startswith("cred-")
        assert cred.rotation_count == 0

    def test_to_dict_excludes_encrypted_value(self):
        cred = StoredCredential(encrypted_value="ENCRYPTED_DATA_HERE")
        d = cred.to_dict()
        assert "encrypted_value" not in d
        assert "credential_id" in d


class TestConsentRecord:
    """Validate ConsentRecord model."""

    def test_creation_defaults(self):
        consent = ConsentRecord(
            account_id="acct-1",
            services_requested=["github", "slack"],
        )
        assert consent.consent_id.startswith("consent-")
        assert consent.status == ConsentStatus.PENDING
        assert len(consent.services_requested) == 2

    def test_to_dict_has_all_fields(self):
        consent = ConsentRecord(account_id="acct-1", services_requested=["x"])
        d = consent.to_dict()
        assert "consent_id" in d
        assert "status" in d
        assert d["status"] == "pending"


class TestAccountRecord:
    """Validate AccountRecord model."""

    def test_creation_defaults(self):
        account = AccountRecord(display_name="Test User")
        assert account.account_id.startswith("acct-")
        assert account.status == AccountStatus.PENDING
        assert len(account.events) == 0

    def test_emit_appends_event(self):
        account = AccountRecord(display_name="Test")
        evt = account._emit("test_event", "test detail")
        assert len(account.events) == 1
        assert account.events[0].event_type == "test_event"
        assert account.events[0].account_id == account.account_id

    def test_to_dict_structure(self):
        account = AccountRecord(display_name="Test User", email="test@example.com")
        d = account.to_dict()
        assert d["display_name"] == "Test User"
        assert d["email"] == "test@example.com"
        assert d["status"] == "pending"
        assert "event_count" in d
        assert "stored_credentials" in d
        assert "oauth_providers" in d


class TestAccountEvent:
    """Validate AccountEvent model."""

    def test_creation_defaults(self):
        evt = AccountEvent(account_id="acct-1", event_type="test")
        assert evt.event_id.startswith("evt-")
        assert evt.timestamp

    def test_to_dict(self):
        evt = AccountEvent(
            account_id="acct-1",
            event_type="test",
            detail="details",
            metadata={"key": "val"},
        )
        d = evt.to_dict()
        assert d["event_type"] == "test"
        assert d["detail"] == "details"
        assert d["metadata"]["key"] == "val"


# ===================================================================
# Class 2: Profile Mapper Tests
# ===================================================================


class TestProfileMappers:
    """Validate OAuth profile normalization functions."""

    def test_microsoft_mapper(self):
        raw = {
            "id": "ms-123",
            "displayName": "John Doe",
            "mail": "john@example.com",
            "givenName": "John",
            "surname": "Doe",
        }
        result = _microsoft_profile_mapper(raw)
        assert result["email"] == "john@example.com"
        assert result["display_name"] == "John Doe"
        assert result["provider_user_id"] == "ms-123"

    def test_microsoft_mapper_fallback_email(self):
        raw = {"userPrincipalName": "john@corp.com", "id": "1"}
        result = _microsoft_profile_mapper(raw)
        assert result["email"] == "john@corp.com"

    def test_google_mapper(self):
        raw = {
            "sub": "goog-456",
            "name": "Jane Smith",
            "email": "jane@gmail.com",
            "given_name": "Jane",
            "family_name": "Smith",
            "picture": "https://example.com/pic.jpg",
        }
        result = _google_profile_mapper(raw)
        assert result["email"] == "jane@gmail.com"
        assert result["display_name"] == "Jane Smith"
        assert result["picture"] == "https://example.com/pic.jpg"

    def test_meta_mapper(self):
        raw = {
            "id": "meta-789",
            "name": "Bob Builder",
            "email": "bob@example.com",
            "first_name": "Bob",
            "last_name": "Builder",
        }
        result = _meta_profile_mapper(raw)
        assert result["email"] == "bob@example.com"
        assert result["given_name"] == "Bob"
        assert result["family_name"] == "Builder"

    def test_mapper_with_empty_dict(self):
        for mapper in [_microsoft_profile_mapper, _google_profile_mapper, _meta_profile_mapper]:
            result = mapper({})
            assert isinstance(result, dict)
            assert "email" in result


# ===================================================================
# Class 3: OAuth Provider Registry Tests
# ===================================================================


class TestOAuthProviderRegistry:
    """Validate the OAuth provider registry."""

    @pytest.fixture
    def registry(self):
        return OAuthProviderRegistry()

    def test_default_providers_loaded(self, registry):
        providers = registry.list_providers()
        names = [p["provider"] for p in providers]
        assert "microsoft" in names
        assert "google" in names
        assert "meta" in names

    def test_register_custom_provider(self, registry):
        cfg = OAuthProviderConfig(
            provider=OAuthProvider.CUSTOM,
            client_id="custom-id",
            authorize_url="https://custom.auth/authorize",
            token_url="https://custom.auth/token",
            userinfo_url="https://custom.auth/userinfo",
        )
        assert registry.register_provider(cfg) is True
        found = registry.get_provider(OAuthProvider.CUSTOM)
        assert found is not None
        assert found.client_id == "custom-id"

    def test_disable_enable_provider(self, registry):
        assert registry.disable_provider(OAuthProvider.GOOGLE) is True
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        assert cfg.enabled is False
        assert registry.enable_provider(OAuthProvider.GOOGLE) is True
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        assert cfg.enabled is True

    def test_disable_unknown_provider(self, registry):
        assert registry.disable_provider(OAuthProvider.CUSTOM) is False

    def test_begin_auth_flow_requires_client_id(self, registry):
        # Default providers have no client_id (env vars not set)
        with pytest.raises(ValueError, match="no client_id"):
            registry.begin_auth_flow(OAuthProvider.GOOGLE)

    def test_begin_auth_flow_with_client_id(self, registry):
        # Configure a client_id
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        cfg.client_id = "test-client-id"
        registry.register_provider(cfg)

        url, state = registry.begin_auth_flow(OAuthProvider.GOOGLE)
        assert "accounts.google.com" in url
        assert "test-client-id" in url
        assert "state=" in url
        assert len(state) > 10

    def test_begin_auth_flow_disabled_provider(self, registry):
        registry.disable_provider(OAuthProvider.GOOGLE)
        with pytest.raises(ValueError, match="disabled"):
            registry.begin_auth_flow(OAuthProvider.GOOGLE)

    def test_begin_auth_flow_unknown_provider(self, registry):
        with pytest.raises(ValueError, match="Unknown"):
            registry.begin_auth_flow(OAuthProvider.CUSTOM)

    def test_complete_auth_flow_success(self, registry):
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        cfg.client_id = "test-id"
        registry.register_provider(cfg)

        _, state = registry.begin_auth_flow(OAuthProvider.GOOGLE)

        token = registry.complete_auth_flow(
            state, "auth-code-123",
            token_response={
                "access_token": "at-abc",
                "refresh_token": "rt-def",
                "expires_in": 3600,
                "scope": "openid profile email",
            },
            profile_response={
                "sub": "goog-user-1",
                "name": "Test User",
                "email": "test@gmail.com",
            },
        )
        assert token.provider == OAuthProvider.GOOGLE
        assert token.access_token == "at-abc"
        assert token.refresh_token == "rt-def"
        assert token.raw_profile["email"] == "test@gmail.com"
        assert token.is_expired() is False

    def test_complete_auth_flow_invalid_state(self, registry):
        with pytest.raises(ValueError, match="Invalid or expired"):
            registry.complete_auth_flow("bogus-state", "code")

    def test_complete_auth_flow_state_consumed(self, registry):
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        cfg.client_id = "test-id"
        registry.register_provider(cfg)
        _, state = registry.begin_auth_flow(OAuthProvider.GOOGLE)

        # First complete works
        registry.complete_auth_flow(state, "code-1")
        # Second fails (state consumed)
        with pytest.raises(ValueError, match="Invalid or expired"):
            registry.complete_auth_flow(state, "code-2")

    def test_pkce_generates_valid_values(self):
        verifier, challenge = OAuthProviderRegistry._generate_pkce()
        assert len(verifier) > 40
        assert len(challenge) > 20
        # They should be different
        assert verifier != challenge

    def test_list_enabled_providers(self, registry):
        # None have client_ids by default
        assert len(registry.list_enabled_providers()) == 0

        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        cfg.client_id = "my-id"
        registry.register_provider(cfg)
        enabled = registry.list_enabled_providers()
        assert "google" in enabled

    def test_get_status(self, registry):
        status = registry.get_status()
        assert status["total_providers"] == 3
        assert status["enabled_providers"] == 3
        assert status["configured_providers"] == 0
        assert status["pending_auth_flows"] == 0


# ===================================================================
# Class 4: Credential Vault Tests
# ===================================================================


class TestCredentialVault:
    """Validate the encrypted credential vault."""

    @pytest.fixture
    def vault(self):
        return CredentialVault(master_key="test-master-key-for-testing")

    def test_store_and_retrieve(self, vault):
        cid = vault.store_credential("acct-1", "github", "password", "my-secret")
        assert cid.startswith("cred-")
        plain = vault.retrieve_credential(cid)
        assert plain == "my-secret"

    def test_verify_correct_password(self, vault):
        cid = vault.store_credential("acct-1", "slack", "api_key", "xoxb-123")
        assert vault.verify_credential(cid, "xoxb-123") is True

    def test_verify_wrong_password(self, vault):
        cid = vault.store_credential("acct-1", "slack", "api_key", "xoxb-123")
        assert vault.verify_credential(cid, "wrong-key") is False

    def test_verify_nonexistent_credential(self, vault):
        assert vault.verify_credential("cred-nonexistent", "any") is False

    def test_rotate_credential(self, vault):
        cid = vault.store_credential("acct-1", "github", "password", "old-pass")
        success = vault.rotate_credential(cid, "new-pass")
        assert success is True
        assert vault.verify_credential(cid, "new-pass") is True
        assert vault.verify_credential(cid, "old-pass") is False
        plain = vault.retrieve_credential(cid)
        assert plain == "new-pass"

    def test_rotate_tracks_count(self, vault):
        cid = vault.store_credential("acct-1", "svc", "password", "p1")
        vault.rotate_credential(cid, "p2")
        vault.rotate_credential(cid, "p3")
        meta = vault.get_credential_metadata(cid)
        assert meta["rotation_count"] == 2
        assert meta["last_rotated_at"] is not None

    def test_rotate_nonexistent(self, vault):
        assert vault.rotate_credential("cred-nonexistent", "new") is False

    def test_remove_credential(self, vault):
        cid = vault.store_credential("acct-1", "github", "password", "pass")
        assert vault.remove_credential(cid) is True
        assert vault.retrieve_credential(cid) is None
        assert vault.remove_credential(cid) is False

    def test_list_credentials_for_account(self, vault):
        vault.store_credential("acct-1", "github", "password", "pass1")
        vault.store_credential("acct-1", "slack", "api_key", "pass2")
        vault.store_credential("acct-2", "jira", "password", "pass3")

        acct1_creds = vault.list_credentials_for_account("acct-1")
        assert len(acct1_creds) == 2
        services = [c["service_name"] for c in acct1_creds]
        assert "github" in services
        assert "slack" in services

    def test_list_all_services(self, vault):
        vault.store_credential("acct-1", "github", "password", "p1")
        vault.store_credential("acct-1", "slack", "api_key", "p2")
        services = vault.list_all_services()
        assert "github" in services
        assert "slack" in services

    def test_empty_credential_rejected(self, vault):
        with pytest.raises(ValueError, match="cannot be empty"):
            vault.store_credential("acct-1", "svc", "password", "")

    def test_overlong_credential_rejected(self, vault):
        with pytest.raises(ValueError, match="max length"):
            vault.store_credential("acct-1", "svc", "password", "x" * 5000)

    def test_empty_rotation_rejected(self, vault):
        cid = vault.store_credential("acct-1", "svc", "password", "pass")
        with pytest.raises(ValueError, match="cannot be empty"):
            vault.rotate_credential(cid, "")

    def test_get_credential_metadata_safe(self, vault):
        cid = vault.store_credential("acct-1", "github", "password", "secret")
        meta = vault.get_credential_metadata(cid)
        assert "encrypted_value" not in meta
        assert meta["service_name"] == "github"
        assert meta["credential_type"] == "password"

    def test_get_status(self, vault):
        vault.store_credential("acct-1", "github", "password", "p")
        status = vault.get_status()
        assert status["total_credentials"] == 1
        assert status["total_accounts"] == 1
        assert "github" in status["services"]


class TestEncryptionHelpers:
    """Validate encryption/decryption helpers."""

    def test_encrypt_decrypt_roundtrip(self):
        key = "my-test-key"
        plain = "Hello, World!"
        encrypted = _encrypt(plain, key)
        assert encrypted != plain
        decrypted = _decrypt(encrypted, key)
        assert decrypted == plain

    def test_hash_prefix_consistent(self):
        h1 = _hash_prefix("test-value")
        h2 = _hash_prefix("test-value")
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_prefix_differs_for_different_values(self):
        h1 = _hash_prefix("value-a")
        h2 = _hash_prefix("value-b")
        assert h1 != h2


class TestCredentialVaultThreadSafety:
    """Validate thread-safe credential operations."""

    def test_concurrent_stores(self):
        vault = CredentialVault(master_key="thread-test-key")
        errors = []

        def store_cred(i):
            try:
                vault.store_credential(f"acct-{i}", f"svc-{i}", "password", f"pass-{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=store_cred, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        status = vault.get_status()
        assert status["total_credentials"] == 20


# ===================================================================
# Class 5: Account Manager Tests
# ===================================================================


class TestAccountManagerCreation:
    """Validate account creation flows."""

    @pytest.fixture
    def mgr(self):
        return AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )

    def test_create_account(self, mgr):
        account = mgr.create_account("Test User", email="test@example.com")
        assert account.account_id.startswith("acct-")
        assert account.display_name == "Test User"
        assert account.email == "test@example.com"
        assert account.status == AccountStatus.ACTIVE

    def test_create_account_emits_event(self, mgr):
        account = mgr.create_account("Test User")
        assert len(account.events) == 1
        assert account.events[0].event_type == AccountEventType.CREATED.value

    def test_get_account(self, mgr):
        account = mgr.create_account("Test")
        retrieved = mgr.get_account(account.account_id)
        assert retrieved is not None
        assert retrieved["display_name"] == "Test"

    def test_get_nonexistent_account(self, mgr):
        assert mgr.get_account("acct-nonexistent") is None

    def test_list_accounts(self, mgr):
        mgr.create_account("User 1")
        mgr.create_account("User 2")
        accounts = mgr.list_accounts()
        assert len(accounts) == 2

    def test_list_accounts_by_status(self, mgr):
        a1 = mgr.create_account("User 1")
        mgr.create_account("User 2")
        mgr.update_account_status(a1.account_id, AccountStatus.SUSPENDED)
        active = mgr.list_accounts(status=AccountStatus.ACTIVE)
        assert len(active) == 1

    def test_update_account_status(self, mgr):
        account = mgr.create_account("Test")
        assert mgr.update_account_status(account.account_id, AccountStatus.SUSPENDED)
        updated = mgr.get_account(account.account_id)
        assert updated["status"] == "suspended"

    def test_update_status_emits_event(self, mgr):
        account = mgr.create_account("Test")
        mgr.update_account_status(account.account_id, AccountStatus.DEACTIVATED)
        events = mgr.get_account_events(account.account_id)
        status_events = [e for e in events if e["event_type"] == "status_changed"]
        assert len(status_events) == 1

    def test_update_status_nonexistent(self, mgr):
        assert mgr.update_account_status("acct-fake", AccountStatus.ACTIVE) is False


class TestAccountManagerOAuth:
    """Validate OAuth signup and linking flows."""

    @pytest.fixture
    def mgr(self):
        registry = OAuthProviderRegistry()
        # Configure Google with a test client_id
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        cfg.client_id = "test-google-client-id"
        registry.register_provider(cfg)

        # Configure Microsoft
        ms_cfg = registry.get_provider(OAuthProvider.MICROSOFT)
        ms_cfg.client_id = "test-ms-client-id"
        registry.register_provider(ms_cfg)

        return AccountManager(
            oauth_registry=registry,
            credential_vault=CredentialVault(master_key="test-key"),
        )

    def test_oauth_signup_creates_account(self, mgr):
        url, state = mgr.begin_oauth_signup(OAuthProvider.GOOGLE)
        assert "accounts.google.com" in url

        account = mgr.complete_oauth_signup(
            state, "auth-code-123",
            token_response={"access_token": "at-1", "refresh_token": "rt-1"},
            profile_response={"sub": "g-1", "name": "Google User", "email": "guser@gmail.com"},
        )
        assert account.status == AccountStatus.ACTIVE
        assert "google" in account.oauth_providers
        assert account.display_name == "Google User"
        assert account.email == "guser@gmail.com"

    def test_oauth_signup_emits_events(self, mgr):
        _, state = mgr.begin_oauth_signup(OAuthProvider.GOOGLE)
        account = mgr.complete_oauth_signup(
            state, "code",
            profile_response={"name": "X", "email": "x@x.com"},
        )
        event_types = [e.event_type for e in account.events]
        assert AccountEventType.CREATED.value in event_types
        assert AccountEventType.OAUTH_LINKED.value in event_types

    def test_oauth_link_to_existing_account(self, mgr):
        # Create account first
        account = mgr.create_account("Existing User")
        assert "microsoft" not in account.oauth_providers

        # Link Microsoft
        url, state = mgr.begin_oauth_signup(
            OAuthProvider.MICROSOFT,
            existing_account_id=account.account_id,
        )
        assert "login.microsoftonline.com" in url

        updated = mgr.complete_oauth_signup(
            state, "ms-code",
            token_response={"access_token": "ms-at"},
            profile_response={"id": "ms-1", "displayName": "MS User", "mail": "ms@corp.com"},
        )
        assert updated.account_id == account.account_id
        assert "microsoft" in updated.oauth_providers

    def test_unlink_oauth(self, mgr):
        _, state = mgr.begin_oauth_signup(OAuthProvider.GOOGLE)
        account = mgr.complete_oauth_signup(
            state, "code",
            profile_response={"name": "Y"},
        )
        assert mgr.unlink_oauth(account.account_id, OAuthProvider.GOOGLE) is True
        assert "google" not in account.oauth_providers

    def test_unlink_nonexistent_provider(self, mgr):
        account = mgr.create_account("Test")
        assert mgr.unlink_oauth(account.account_id, OAuthProvider.META) is False

    def test_unlink_nonexistent_account(self, mgr):
        assert mgr.unlink_oauth("acct-fake", OAuthProvider.GOOGLE) is False


class TestAccountManagerCredentials:
    """Validate credential storage through account manager."""

    @pytest.fixture
    def mgr(self):
        return AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )

    def test_store_credential(self, mgr):
        account = mgr.create_account("Test")
        cred_id = mgr.store_credential(
            account.account_id, "github", "password", "gh-token-123"
        )
        assert cred_id.startswith("cred-")
        assert cred_id in account.stored_credentials

    def test_store_credential_emits_event(self, mgr):
        account = mgr.create_account("Test")
        mgr.store_credential(account.account_id, "github", "password", "token")
        cred_events = [
            e for e in account.events
            if e.event_type == AccountEventType.CREDENTIAL_STORED.value
        ]
        assert len(cred_events) == 1

    def test_rotate_credential(self, mgr):
        account = mgr.create_account("Test")
        cred_id = mgr.store_credential(
            account.account_id, "github", "password", "old-pass"
        )
        assert mgr.rotate_credential(account.account_id, cred_id, "new-pass")
        rotation_events = [
            e for e in account.events
            if e.event_type == AccountEventType.CREDENTIAL_ROTATED.value
        ]
        assert len(rotation_events) == 1

    def test_remove_credential(self, mgr):
        account = mgr.create_account("Test")
        cred_id = mgr.store_credential(account.account_id, "svc", "password", "p")
        assert mgr.remove_credential(account.account_id, cred_id) is True
        assert cred_id not in account.stored_credentials

    def test_store_credential_nonexistent_account(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.store_credential("acct-fake", "svc", "password", "p")

    def test_rotate_nonexistent_account(self, mgr):
        assert mgr.rotate_credential("acct-fake", "cred-fake", "new") is False

    def test_remove_nonexistent_account(self, mgr):
        assert mgr.remove_credential("acct-fake", "cred-fake") is False


# ===================================================================
# Class 6: Consent-Based Credential Import Tests
# ===================================================================


class TestConsentFlow:
    """Validate the consent-based credential import flow."""

    @pytest.fixture
    def mgr(self):
        return AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )

    def test_request_consent(self, mgr):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github", "slack", "jira"]
        )
        assert consent.status == ConsentStatus.PENDING
        assert len(consent.services_requested) == 3

    def test_grant_consent_all_services(self, mgr):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github", "slack"]
        )
        updated = mgr.respond_to_consent(consent.consent_id, grant=True)
        assert updated.status == ConsentStatus.GRANTED
        assert updated.services_granted == ["github", "slack"]
        assert updated.services_denied == []

    def test_grant_consent_partial(self, mgr):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github", "slack", "custom_crm"]
        )
        updated = mgr.respond_to_consent(
            consent.consent_id,
            grant=True,
            granted_services=["github", "slack"],
            denied_services=["custom_crm"],
        )
        assert updated.services_granted == ["github", "slack"]
        assert updated.services_denied == ["custom_crm"]

    def test_deny_consent(self, mgr):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github"]
        )
        updated = mgr.respond_to_consent(consent.consent_id, grant=False)
        assert updated.status == ConsentStatus.DENIED
        assert updated.services_denied == ["github"]

    def test_revoke_consent(self, mgr):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=True)
        revoked = mgr.revoke_consent(consent.consent_id)
        assert revoked.status == ConsentStatus.REVOKED

    def test_consent_emits_events(self, mgr):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=True)
        event_types = [e.event_type for e in account.events]
        assert AccountEventType.CONSENT_REQUESTED.value in event_types
        assert AccountEventType.CONSENT_GRANTED.value in event_types

    def test_respond_to_nonexistent_consent(self, mgr):
        assert mgr.respond_to_consent("consent-fake", grant=True) is None

    def test_revoke_nonexistent_consent(self, mgr):
        assert mgr.revoke_consent("consent-fake") is None

    def test_consent_for_nonexistent_account(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.request_credential_import("acct-fake", ["github"])


# ===================================================================
# Class 7: Missing Integration Ticketing Tests
# ===================================================================


class TestMissingIntegrationTicketing:
    """Validate auto-ticketing for missing integrations."""

    @pytest.fixture
    def mock_ticketing(self):
        mock = MagicMock()
        mock.create_ticket.return_value = MagicMock(ticket_id="TKT-12345")
        return mock

    @pytest.fixture
    def mgr(self, mock_ticketing):
        return AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
            ticketing_adapter=mock_ticketing,
        )

    def test_known_services_do_not_trigger_tickets(self, mgr, mock_ticketing):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github", "slack", "aws"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=True)
        mock_ticketing.create_ticket.assert_not_called()

    def test_unknown_services_trigger_tickets(self, mgr, mock_ticketing):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["github", "custom_erp", "my_special_tool"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=True)
        assert mock_ticketing.create_ticket.call_count == 2

    def test_ticket_contains_service_name(self, mgr, mock_ticketing):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["obscure_platform"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=True)
        call_args = mock_ticketing.create_ticket.call_args
        assert "obscure_platform" in call_args.kwargs.get("title", call_args[1].get("title", ""))

    def test_ticket_event_logged(self, mgr, mock_ticketing):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["unknown_tool"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=True)
        ticket_events = [
            e for e in account.events
            if e.event_type == AccountEventType.MISSING_INTEGRATION_TICKET.value
        ]
        assert len(ticket_events) == 1

    def test_no_tickets_when_consent_denied(self, mgr, mock_ticketing):
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["unknown_tool"]
        )
        mgr.respond_to_consent(consent.consent_id, grant=False)
        mock_ticketing.create_ticket.assert_not_called()

    def test_mock_ticket_without_adapter(self):
        mgr = AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
            # No ticketing adapter
        )
        account = mgr.create_account("Test")
        consent = mgr.request_credential_import(
            account.account_id, ["custom_platform"]
        )
        updated = mgr.respond_to_consent(consent.consent_id, grant=True)
        # Should still succeed with mock ticket IDs
        assert updated.status == ConsentStatus.GRANTED


class TestIntegrationCoverage:
    """Validate integration coverage checking."""

    @pytest.fixture
    def mgr(self):
        return AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )

    def test_all_known_services_covered(self, mgr):
        result = mgr.check_integration_coverage(["github", "slack", "aws"])
        assert result["coverage_pct"] == 100.0
        assert len(result["missing"]) == 0

    def test_mixed_coverage(self, mgr):
        result = mgr.check_integration_coverage(["github", "custom_erp"])
        assert result["coverage_pct"] == 50.0
        assert "github" in result["covered"]
        assert "custom_erp" in result["missing"]

    def test_empty_services(self, mgr):
        result = mgr.check_integration_coverage([])
        assert result["coverage_pct"] == 0.0

    def test_known_integration_list_is_substantial(self):
        assert len(KNOWN_INTEGRATION_SERVICES) >= 30


# ===================================================================
# Class 8: Audit Log Tests
# ===================================================================


class TestAuditLog:
    """Validate complete audit trail for account operations."""

    @pytest.fixture
    def mgr(self):
        registry = OAuthProviderRegistry()
        cfg = registry.get_provider(OAuthProvider.GOOGLE)
        cfg.client_id = "test-id"
        registry.register_provider(cfg)
        return AccountManager(
            oauth_registry=registry,
            credential_vault=CredentialVault(master_key="test-key"),
        )

    def test_full_lifecycle_audit(self, mgr):
        """Test that every operation produces an audit event."""
        # Create account
        account = mgr.create_account("Audit Test")

        # Store credential
        cred_id = mgr.store_credential(
            account.account_id, "github", "password", "pass1"
        )

        # Rotate credential
        mgr.rotate_credential(account.account_id, cred_id, "pass2")

        # Request consent
        consent = mgr.request_credential_import(
            account.account_id, ["github"]
        )

        # Grant consent
        mgr.respond_to_consent(consent.consent_id, grant=True)

        # Revoke consent
        mgr.revoke_consent(consent.consent_id)

        # Remove credential
        mgr.remove_credential(account.account_id, cred_id)

        # Change status
        mgr.update_account_status(account.account_id, AccountStatus.SUSPENDED)

        events = mgr.get_account_events(account.account_id)
        event_types = [e["event_type"] for e in events]

        assert AccountEventType.CREATED.value in event_types
        assert AccountEventType.CREDENTIAL_STORED.value in event_types
        assert AccountEventType.CREDENTIAL_ROTATED.value in event_types
        assert AccountEventType.CONSENT_REQUESTED.value in event_types
        assert AccountEventType.CONSENT_GRANTED.value in event_types
        assert AccountEventType.CONSENT_REVOKED.value in event_types
        assert AccountEventType.CREDENTIAL_REMOVED.value in event_types
        assert AccountEventType.STATUS_CHANGED.value in event_types

    def test_events_have_timestamps(self, mgr):
        account = mgr.create_account("Test")
        events = mgr.get_account_events(account.account_id)
        for e in events:
            assert "timestamp" in e
            # Should be ISO format
            datetime.fromisoformat(e["timestamp"])

    def test_events_have_account_id(self, mgr):
        account = mgr.create_account("Test")
        for e in account.events:
            assert e.account_id == account.account_id


# ===================================================================
# Class 9: Account Manager Status Tests
# ===================================================================


class TestAccountManagerStatus:
    """Validate the get_status aggregation."""

    def test_status_empty(self):
        mgr = AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )
        status = mgr.get_status()
        assert status["total_accounts"] == 0
        assert "oauth_registry" in status
        assert "credential_vault" in status
        assert status["known_integrations"] >= 30

    def test_status_after_operations(self):
        mgr = AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )
        mgr.create_account("User 1")
        mgr.create_account("User 2")
        status = mgr.get_status()
        assert status["total_accounts"] == 2
        assert status["by_status"]["active"] == 2


# ===================================================================
# Class 10: Thread Safety Tests
# ===================================================================


class TestAccountManagerThreadSafety:
    """Validate thread-safe account operations."""

    def test_concurrent_account_creation(self):
        mgr = AccountManager(
            credential_vault=CredentialVault(master_key="test-key"),
        )
        errors = []

        def create(i):
            try:
                mgr.create_account(f"User-{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert mgr.get_status()["total_accounts"] == 20

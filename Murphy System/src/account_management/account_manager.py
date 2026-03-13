"""
Account Manager
=================

Top-level orchestrator for account lifecycle:
- Create accounts via OAuth sign-up or direct creation
- Link/unlink OAuth providers (Microsoft, Google, Meta)
- Store and manage passwords with API-key-style encryption
- Consent-based credential import flow
- Auto-ticket missing integrations to the ticketing adapter
- Full audit log for every account mutation

Integrates with:
- OAuthProviderRegistry — OAuth flows
- CredentialVault — encrypted credential storage
- TicketingAdapter — self-ticketing for missing integrations
- EventBackbone — event publishing
- PersistenceManager — durable storage

Design Label: ACCT-001
Owner: Platform Engineering
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from account_management.credential_vault import CredentialVault
from account_management.models import (
    AccountEvent,
    AccountEventType,
    AccountRecord,
    AccountStatus,
    ConsentRecord,
    ConsentStatus,
    OAuthProvider,
    OAuthToken,
)
from account_management.oauth_provider_registry import OAuthProviderRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ACCOUNTS = 10_000

# Services Murphy has built-in integrations for
KNOWN_INTEGRATION_SERVICES = frozenset({
    "github", "gitlab", "bitbucket",
    "slack", "discord", "teams",
    "jira", "asana", "trello", "linear",
    "salesforce", "hubspot",
    "aws", "gcp", "azure",
    "stripe", "paypal",
    "google_workspace", "microsoft_365",
    "dropbox", "box",
    "notion", "confluence",
    "datadog", "pagerduty",
    "docker", "kubernetes",
    "openai", "groq", "anthropic",
    "facebook", "instagram", "twitter", "linkedin",
    "shopify", "woocommerce",
    "quickbooks", "xero",
    "twilio", "sendgrid", "mailchimp",
    "zoom", "google_meet",
    "mongodb", "postgresql", "redis",
})


# ---------------------------------------------------------------------------
# Account Manager
# ---------------------------------------------------------------------------


class AccountManager:
    """Full-lifecycle account management with OAuth, credential vault,
    consent-based import, and self-ticketing.

    Usage::

        mgr = AccountManager()

        # Create account via OAuth
        url, state = mgr.begin_oauth_signup(OAuthProvider.GOOGLE)
        account = mgr.complete_oauth_signup(state, code, token_resp, profile_resp)

        # Store a credential
        mgr.store_credential(account.account_id, "github", "password", "token123")

        # Consent-based import
        consent = mgr.request_credential_import(account.account_id, ["github", "slack", "notion"])
        mgr.respond_to_consent(consent.consent_id, grant=True)
    """

    def __init__(
        self,
        oauth_registry: Optional[OAuthProviderRegistry] = None,
        credential_vault: Optional[CredentialVault] = None,
        ticketing_adapter: Optional[Any] = None,
        persistence_manager: Optional[Any] = None,
        event_backbone: Optional[Any] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._oauth = oauth_registry or OAuthProviderRegistry()
        self._vault = credential_vault or CredentialVault()
        self._ticketing = ticketing_adapter
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._accounts: Dict[str, AccountRecord] = {}
        # Map: state → (account_id or None) for linking flows
        self._oauth_flow_account: Dict[str, Optional[str]] = {}

    # -- Account creation ---------------------------------------------------

    def create_account(
        self,
        display_name: str,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AccountRecord:
        """Create a new account directly (not via OAuth)."""
        with self._lock:
            if len(self._accounts) >= _MAX_ACCOUNTS:
                raise ValueError("Maximum account limit reached")

        account = AccountRecord(
            display_name=display_name,
            email=email,
            status=AccountStatus.ACTIVE,
            metadata=metadata or {},
        )
        account._emit(AccountEventType.CREATED.value, f"Account created for {display_name}")

        with self._lock:
            self._accounts[account.account_id] = account

        self._persist_account(account)
        self._publish_event(account, AccountEventType.CREATED.value)
        logger.info("Account created: %s (%s)", account.account_id, display_name)
        return account

    # -- OAuth sign-up / link -----------------------------------------------

    def begin_oauth_signup(
        self,
        provider: OAuthProvider,
        existing_account_id: Optional[str] = None,
    ) -> tuple:
        """Start an OAuth sign-up or link flow.

        Args:
            provider: Which OAuth provider to use.
            existing_account_id: If provided, links to an existing account
                instead of creating a new one.

        Returns:
            (authorize_url, state)
        """
        url, state = self._oauth.begin_auth_flow(provider)
        with self._lock:
            self._oauth_flow_account[state] = existing_account_id
        return url, state

    def complete_oauth_signup(
        self,
        state: str,
        authorization_code: str,
        token_response: Optional[Dict[str, Any]] = None,
        profile_response: Optional[Dict[str, Any]] = None,
    ) -> AccountRecord:
        """Complete an OAuth flow and create or update an account.

        Returns the AccountRecord (new or existing).
        """
        token = self._oauth.complete_auth_flow(
            state, authorization_code,
            token_response=token_response,
            profile_response=profile_response,
        )

        with self._lock:
            existing_account_id = self._oauth_flow_account.pop(state, None)

        if existing_account_id:
            return self._link_oauth_to_existing(existing_account_id, token)

        # Create new account from OAuth profile
        profile = token.raw_profile
        display_name = profile.get("display_name", "")
        email = profile.get("email")

        account = AccountRecord(
            display_name=display_name or f"user-{uuid.uuid4().hex[:6]}",
            email=email,
            status=AccountStatus.ACTIVE,
        )
        account.oauth_providers[token.provider.value] = token
        account._emit(
            AccountEventType.CREATED.value,
            f"Account created via {token.provider.value} OAuth",
        )
        account._emit(
            AccountEventType.OAUTH_LINKED.value,
            f"Linked {token.provider.value} provider",
            {"provider": token.provider.value},
        )

        with self._lock:
            self._accounts[account.account_id] = account

        self._persist_account(account)
        logger.info("OAuth signup complete: %s via %s", account.account_id, token.provider.value)
        return account

    def _link_oauth_to_existing(
        self, account_id: str, token: OAuthToken
    ) -> AccountRecord:
        """Link an OAuth token to an existing account."""
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        account.oauth_providers[token.provider.value] = token
        account._emit(
            AccountEventType.OAUTH_LINKED.value,
            f"Linked {token.provider.value} provider",
            {"provider": token.provider.value},
        )
        self._persist_account(account)
        return account

    def unlink_oauth(self, account_id: str, provider: OAuthProvider) -> bool:
        """Remove an OAuth provider from an account."""
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            return False
        if provider.value not in account.oauth_providers:
            return False
        del account.oauth_providers[provider.value]
        account._emit(
            AccountEventType.OAUTH_UNLINKED.value,
            f"Unlinked {provider.value} provider",
            {"provider": provider.value},
        )
        self._persist_account(account)
        return True

    # -- Credential management ----------------------------------------------

    def store_credential(
        self,
        account_id: str,
        service_name: str,
        credential_type: str,
        plaintext_value: str,
    ) -> str:
        """Store a credential for an account (API-key-style encryption).

        Returns the credential_id.
        """
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        cred_id = self._vault.store_credential(
            account_id, service_name, credential_type, plaintext_value
        )

        # Record in account
        meta = self._vault.get_credential_metadata(cred_id)
        if meta:
            from account_management.models import StoredCredential
            sc = StoredCredential(
                credential_id=cred_id,
                account_id=account_id,
                service_name=service_name,
                credential_type=credential_type,
                key_hash=meta.get("key_hash", ""),
            )
            account.stored_credentials[cred_id] = sc

        account._emit(
            AccountEventType.CREDENTIAL_STORED.value,
            f"Credential stored for {service_name}",
            {"credential_id": cred_id, "service_name": service_name},
        )
        self._persist_account(account)
        return cred_id

    def rotate_credential(
        self,
        account_id: str,
        credential_id: str,
        new_plaintext_value: str,
    ) -> bool:
        """Rotate (update) a credential and log the change."""
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            return False

        success = self._vault.rotate_credential(credential_id, new_plaintext_value)
        if success:
            account._emit(
                AccountEventType.CREDENTIAL_ROTATED.value,
                f"Credential {credential_id} rotated",
                {"credential_id": credential_id},
            )
            # Update stored credential metadata
            meta = self._vault.get_credential_metadata(credential_id)
            if meta and credential_id in account.stored_credentials:
                account.stored_credentials[credential_id].key_hash = meta.get("key_hash", "")
                account.stored_credentials[credential_id].rotation_count = meta.get("rotation_count", 0)
                account.stored_credentials[credential_id].last_rotated_at = meta.get("last_rotated_at")
                account.stored_credentials[credential_id].updated_at = meta.get("updated_at", "")
            self._persist_account(account)
        return success

    def remove_credential(self, account_id: str, credential_id: str) -> bool:
        """Remove a credential from the vault and account."""
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            return False

        success = self._vault.remove_credential(credential_id)
        if success:
            account.stored_credentials.pop(credential_id, None)
            account._emit(
                AccountEventType.CREDENTIAL_REMOVED.value,
                f"Credential {credential_id} removed",
                {"credential_id": credential_id},
            )
            self._persist_account(account)
        return success

    # -- Consent-based credential import ------------------------------------

    def request_credential_import(
        self,
        account_id: str,
        services: List[str],
    ) -> ConsentRecord:
        """Request consent to import credentials for a list of services.

        This is the "Do you agree with sharing all accounts and passwords?"
        flow.  The user is presented with the list of services and chooses
        which to grant or deny.

        Returns a ConsentRecord in PENDING status.
        """
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        consent = ConsentRecord(
            account_id=account_id,
            description=(
                "Murphy requests access to your credentials for the following "
                "services. You may grant or deny access to each service individually."
            ),
            services_requested=list(services),
        )
        account.consent_records.append(consent)
        account._emit(
            AccountEventType.CONSENT_REQUESTED.value,
            f"Credential import consent requested for {len(services)} services",
            {"services": services, "consent_id": consent.consent_id},
        )
        self._persist_account(account)
        return consent

    def respond_to_consent(
        self,
        consent_id: str,
        grant: bool,
        granted_services: Optional[List[str]] = None,
        denied_services: Optional[List[str]] = None,
    ) -> Optional[ConsentRecord]:
        """Respond to a consent request.

        If ``grant`` is True and ``granted_services`` is None, all requested
        services are granted.  Otherwise, provide explicit lists.

        Returns the updated ConsentRecord, or None if not found.
        """
        consent, account = self._find_consent(consent_id)
        if consent is None or account is None:
            return None

        consent.responded_at = datetime.now(timezone.utc).isoformat()

        if grant:
            consent.status = ConsentStatus.GRANTED
            consent.services_granted = (
                granted_services if granted_services is not None
                else list(consent.services_requested)
            )
            consent.services_denied = (
                denied_services if denied_services is not None else []
            )
            account._emit(
                AccountEventType.CONSENT_GRANTED.value,
                f"Consent granted for {len(consent.services_granted)} services",
                {
                    "consent_id": consent_id,
                    "granted": consent.services_granted,
                    "denied": consent.services_denied,
                },
            )
            # Auto-ticket any services Murphy doesn't have integrations for
            self._ticket_missing_integrations(account, consent.services_granted)
        else:
            consent.status = ConsentStatus.DENIED
            consent.services_denied = list(consent.services_requested)
            account._emit(
                AccountEventType.CONSENT_DENIED.value,
                "Consent denied for all services",
                {"consent_id": consent_id},
            )

        self._persist_account(account)
        return consent

    def revoke_consent(self, consent_id: str) -> Optional[ConsentRecord]:
        """Revoke a previously granted consent."""
        consent, account = self._find_consent(consent_id)
        if consent is None or account is None:
            return None
        consent.status = ConsentStatus.REVOKED
        consent.responded_at = datetime.now(timezone.utc).isoformat()
        account._emit(
            AccountEventType.CONSENT_REVOKED.value,
            f"Consent {consent_id} revoked",
            {"consent_id": consent_id},
        )
        self._persist_account(account)
        return consent

    # -- Missing integration ticketing --------------------------------------

    def _ticket_missing_integrations(
        self, account: AccountRecord, services: List[str]
    ) -> List[str]:
        """Check which services lack Murphy integrations and file tickets.

        Returns list of ticket IDs created.
        """
        missing = [s for s in services if s.lower() not in KNOWN_INTEGRATION_SERVICES]
        if not missing:
            return []

        ticket_ids = []
        for service in missing:
            ticket_id = self._create_missing_integration_ticket(account, service)
            if ticket_id:
                ticket_ids.append(ticket_id)
                account._emit(
                    AccountEventType.MISSING_INTEGRATION_TICKET.value,
                    f"Filed ticket to develop integration for '{service}'",
                    {"service": service, "ticket_id": ticket_id},
                )
        return ticket_ids

    def _create_missing_integration_ticket(
        self, account: AccountRecord, service: str
    ) -> Optional[str]:
        """Create a self-ticket for a missing integration."""
        if self._ticketing is None:
            logger.info(
                "Would file ticket for missing integration: %s (no ticketing adapter)",
                service,
            )
            return f"MOCK-TKT-{uuid.uuid4().hex[:8]}"

        try:
            ticket = self._ticketing.create_ticket(
                title=f"Develop integration for: {service}",
                description=(
                    f"Account {account.account_id} ({account.display_name}) "
                    f"requested credential import for '{service}', which is not "
                    f"in Murphy's known integration list. Please develop a "
                    f"connector for this service."
                ),
                ticket_type="integration_request",
                priority="medium",
                requester="account_manager",
                tags=["auto-generated", "missing-integration", service],
                metadata={
                    "account_id": account.account_id,
                    "service": service,
                },
            )
            return ticket.ticket_id if hasattr(ticket, "ticket_id") else str(ticket)
        except Exception as exc:
            logger.error("Failed to create ticket for %s: %s", service, exc)
            return None

    def check_integration_coverage(self, services: List[str]) -> Dict[str, Any]:
        """Check which services have Murphy integrations and which don't.

        Returns:
            {
                "covered": ["github", "slack"],
                "missing": ["custom_crm"],
                "coverage_pct": 66.7,
            }
        """
        covered = [s for s in services if s.lower() in KNOWN_INTEGRATION_SERVICES]
        missing = [s for s in services if s.lower() not in KNOWN_INTEGRATION_SERVICES]
        total = len(services) if services else 1
        return {
            "covered": covered,
            "missing": missing,
            "coverage_pct": round(len(covered) / total * 100, 1),
        }

    # -- Account queries ----------------------------------------------------

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account as safe dict (no secrets)."""
        with self._lock:
            account = self._accounts.get(account_id)
        return account.to_dict() if account else None

    def get_account_events(
        self, account_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get the audit log for an account."""
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            return []
        return [e.to_dict() for e in account.events[-limit:]]

    def list_accounts(
        self,
        status: Optional[AccountStatus] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List accounts, optionally filtered by status."""
        with self._lock:
            accounts = list(self._accounts.values())
        if status:
            accounts = [a for a in accounts if a.status == status]
        return [a.to_dict() for a in accounts[:limit]]

    def update_account_status(
        self, account_id: str, new_status: AccountStatus
    ) -> bool:
        """Change account status."""
        with self._lock:
            account = self._accounts.get(account_id)
        if account is None:
            return False
        old_status = account.status
        account.status = new_status
        account._emit(
            AccountEventType.STATUS_CHANGED.value,
            f"Status changed from {old_status.value} to {new_status.value}",
            {"old_status": old_status.value, "new_status": new_status.value},
        )
        self._persist_account(account)
        return True

    # -- Helpers ------------------------------------------------------------

    def _find_consent(self, consent_id: str):
        """Find a consent record across all accounts."""
        with self._lock:
            for account in self._accounts.values():
                for consent in account.consent_records:
                    if consent.consent_id == consent_id:
                        return consent, account
        return None, None

    def _persist_account(self, account: AccountRecord) -> None:
        """Persist account to durable storage if available."""
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=account.account_id,
                    document=account.to_dict(),
                )
            except Exception as exc:
                logger.debug("Account persistence skipped: %s", exc)

    def _publish_event(self, account: AccountRecord, event_type: str) -> None:
        """Publish account event to event backbone if available."""
        if self._backbone is not None:
            try:
                self._backbone.publish(
                    "account_management",
                    {
                        "event_type": event_type,
                        "account_id": account.account_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as exc:
                logger.debug("Event publish skipped: %s", exc)

    def get_status(self) -> Dict[str, Any]:
        """System status summary."""
        with self._lock:
            total = len(self._accounts)
            by_status = {}
            for a in self._accounts.values():
                by_status[a.status.value] = by_status.get(a.status.value, 0) + 1
        return {
            "total_accounts": total,
            "by_status": by_status,
            "oauth_registry": self._oauth.get_status(),
            "credential_vault": self._vault.get_status(),
            "known_integrations": len(KNOWN_INTEGRATION_SERVICES),
            "has_ticketing": self._ticketing is not None,
            "has_persistence": self._pm is not None,
            "has_event_backbone": self._backbone is not None,
        }

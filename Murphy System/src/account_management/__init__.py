"""
Account Management & OAuth Integration System
===============================================

Provides:
- OAuth sign-up/sign-in flows for Microsoft, Google, and Meta
- Secure credential storage with encryption (API-key-style treatment)
- Account creation with audit logging
- Consent-based credential import from local credential managers
- Auto-ticketing for missing integration providers
- Password lifecycle management with automatic change detection

Design Labels: ACCT-001, ACCT-002, ACCT-003
Owner: Platform Engineering
Phase: Account & Identity Integration

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from account_management.account_manager import AccountManager
from account_management.credential_vault import CredentialVault
from account_management.models import (
    AccountEvent,
    AccountRecord,
    AccountStatus,
    ConsentRecord,
    ConsentStatus,
    OAuthProvider,
    OAuthToken,
    StoredCredential,
)
from account_management.oauth_provider_registry import OAuthProviderRegistry

__all__ = [
    "OAuthProvider",
    "AccountStatus",
    "ConsentStatus",
    "AccountRecord",
    "OAuthToken",
    "StoredCredential",
    "ConsentRecord",
    "AccountEvent",
    "OAuthProviderRegistry",
    "CredentialVault",
    "AccountManager",
]

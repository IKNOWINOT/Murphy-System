# `src/account_management` — Account Management & OAuth Integration

OAuth sign-up/sign-in, secure credential storage, and account lifecycle management for the Murphy System.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The account management package handles the full identity lifecycle for Murphy users and tenants. It provides OAuth 2.0 flows for Microsoft, Google, Meta, GitHub, LinkedIn, and Apple, enabling users to sign up and sign in via external identity providers. Credentials are stored encrypted with audit logging on every access and mutation. Automatic change detection triggers notifications when stored credentials are rotated by upstream providers.

## Key Components

| Module | Purpose |
|--------|---------|
| `account_manager.py` | Core CRUD for account records, OAuth token exchange, and audit event emission |
| `credential_vault.py` | Encrypted credential storage with consent-gated import and lifecycle management |
| `models.py` | Pydantic models: `AccountRecord`, `OAuthToken`, `StoredCredential`, `ConsentRecord` |
| `oauth_provider_registry.py` | Registry of supported OAuth providers with auto-ticketing for missing ones |

## Usage

```python
from account_management import AccountManager, CredentialVault, OAuthProvider

manager = AccountManager()
vault = CredentialVault()

# Begin OAuth flow
account = manager.create_account(email="user@example.com", provider=OAuthProvider.GOOGLE)

# Store credential with user consent
vault.store(account.id, service="openai", api_key="sk-...", consent_granted=True)
```

## Configuration

| Variable | Description |
|----------|-------------|
| `OAUTH_MICROSOFT_CLIENT_ID` | Azure app client ID for Microsoft OAuth |
| `OAUTH_GOOGLE_CLIENT_ID` | Google Cloud client ID |
| `OAUTH_META_CLIENT_ID` | Meta / Facebook app ID |
| `CREDENTIAL_ENCRYPTION_KEY` | Symmetric key for credential vault encryption |

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# Account Management

The `account_management` package handles user and organisation accounts,
credential storage, and OAuth provider registration.

## Key Modules

| Module | Purpose |
|--------|---------|
| `account_manager.py` | `AccountManager` — CRUD for user and org accounts |
| `credential_vault.py` | Encrypted credential store with audit trail |
| `models.py` | `Account`, `Organisation`, `Credential` Pydantic models |
| `oauth_provider_registry.py` | Registers and resolves OAuth 2.0 providers |

## Usage

```python
from account_management.account_manager import AccountManager
mgr = AccountManager()
account = await mgr.create(email="alice@example.com", org_id="org-1")
```

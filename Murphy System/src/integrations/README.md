# Integrations

The `integrations` package provides pre-built connectors to popular
third-party services and databases used by the Murphy System.

## Key Modules

| Module | Purpose |
|--------|---------|
| `base_connector.py` | `BaseConnector` abstract class all connectors extend |
| `anthropic_connector.py` | Anthropic Claude API connector |
| `asana_connector.py` | Asana project management connector |
| `cloudflare_connector.py` | Cloudflare Workers and R2 connector |
| `database_connectors.py` | PostgreSQL, Redis, and SQLite connection helpers |

Additional connectors are organised in sub-modules for CRM, calendar,
email, payment, and other domains.

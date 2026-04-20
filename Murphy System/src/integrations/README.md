# `src/integrations` — External Integrations Package

20+ real API connectors spanning CRM, cloud storage, communication, e-commerce, payments, analytics, and industrial systems.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The integrations package is Murphy's world-model connector layer, providing typed, authenticated connections to external services. Every connector implements the `Integration` base contract and registers with `IntegrationFramework`, enabling uniform execution via `execute_call`. The `WorldModelRegistry` aggregates all live integrations into a queryable world-model surface used by agent reasoning pipelines. Connectors are organised by domain — AI/ML providers, cloud platforms, communication tools, financial services, and industrial/SCADA systems.

## Key Components

| Module | Purpose |
|--------|---------|
| `integration_framework.py` | `IntegrationFramework`, `Integration`, `IntegrationResult`, `IntegrationType` |
| `world_model_registry.py` | `WorldModelRegistry` — aggregates all live connectors |
| `base_connector.py` | `BaseConnector` abstract class with auth and retry logic |
| `openai_connector.py` | OpenAI API connector |
| `anthropic_connector.py` | Anthropic Claude connector |
| `stripe_connector.py` | Stripe payments connector |
| `hubspot_connector.py` | HubSpot CRM connector |
| `google_drive_connector.py` | Google Drive file storage connector |
| `dropbox_connector.py` | Dropbox file storage connector |
| `discord_connector.py` | Discord messaging connector |
| `telegram_connector.py` | Telegram bot connector |
| `slack` (via `database_connectors.py`) | Database connector suite (Postgres, MySQL, Redis) |
| `shopify_connector.py` | Shopify e-commerce connector |
| `datadog_connector.py` | Datadog observability connector |
| `cloudflare_connector.py` | Cloudflare DNS/CDN connector |
| `firebase_connector.py` | Firebase / Firestore connector |
| `supabase_connector.py` | Supabase connector |
| `asana_connector.py` | Asana project management connector |
| `trello_connector.py` | Trello board connector |
| `mailchimp_connector.py` | Mailchimp email marketing connector |
| `google_analytics_connector.py` | Google Analytics connector |
| `twitter_connector.py` | Twitter/X connector |
| `yahoo_finance_connector.py` | Yahoo Finance market data connector |
| `openweathermap_connector.py` | OpenWeatherMap weather data connector |
| `scada_connector.py` | Industrial SCADA systems connector |

## Usage

```python
from integrations import IntegrationFramework, create_integration, execute_call
from integrations.openai_connector import OpenAIConnector

framework = IntegrationFramework()
integration = create_integration(OpenAIConnector, api_key="sk-...")
result = execute_call(integration, method="chat.complete", payload={...})
```

## Configuration

Most connectors read credentials from environment variables following the pattern `<SERVICE>_API_KEY` (e.g. `OPENAI_API_KEY`, `STRIPE_SECRET_KEY`, `HUBSPOT_ACCESS_TOKEN`).

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# Murphy System Platform Connectors

> **Created:** 2026-03-27  
> **Addresses:** B-011 (Platform connectors)

---

## Overview

Murphy System includes 90+ platform connectors following a unified adapter pattern.
All connectors require OAuth credentials or API keys at deployment time.

---

## Connector Categories

### Communication (12 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| Slack | `src/slack_connector.py` | `SLACK_BOT_TOKEN` |
| Discord | `src/discord_connector.py` | `DISCORD_BOT_TOKEN` |
| Teams | `src/teams_connector.py` | `TEAMS_*` |
| Zoom | `src/zoom_connector.py` | `ZOOM_API_KEY` |
| Email (SMTP) | `src/email_connector.py` | `SMTP_*` |
| SendGrid | `src/sendgrid_connector.py` | `SENDGRID_API_KEY` |
| Twilio | `src/twilio_connector.py` | `TWILIO_*` |
| Matrix | `src/matrix_bridge/` | `MATRIX_*` |
| Telegram | `src/telegram_connector.py` | `TELEGRAM_BOT_TOKEN` |
| WhatsApp | `src/whatsapp_connector.py` | `WHATSAPP_*` |
| Intercom | `src/intercom_connector.py` | `INTERCOM_API_KEY` |
| Zendesk | `src/zendesk_connector.py` | `ZENDESK_*` |

### CRM (8 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| HubSpot | `src/hubspot_connector.py` | `HUBSPOT_API_KEY` |
| Salesforce | `src/salesforce_connector.py` | `SALESFORCE_*` |
| Pipedrive | `src/pipedrive_connector.py` | `PIPEDRIVE_API_TOKEN` |
| Zoho | `src/zoho_connector.py` | `ZOHO_*` |
| Freshsales | `src/freshsales_connector.py` | `FRESHSALES_API_KEY` |
| Close | `src/close_connector.py` | `CLOSE_API_KEY` |
| Copper | `src/copper_connector.py` | `COPPER_API_KEY` |
| Insightly | `src/insightly_connector.py` | `INSIGHTLY_API_KEY` |

### Project Management (10 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| Jira | `src/jira_connector.py` | `JIRA_API_TOKEN` |
| Asana | `src/asana_connector.py` | `ASANA_ACCESS_TOKEN` |
| Monday | `src/monday_connector.py` | `MONDAY_API_KEY` |
| Trello | `src/trello_connector.py` | `TRELLO_API_KEY` |
| Notion | `src/notion_connector.py` | `NOTION_API_KEY` |
| Airtable | `src/airtable_connector.py` | `AIRTABLE_API_KEY` |
| Basecamp | `src/basecamp_connector.py` | `BASECAMP_*` |
| ClickUp | `src/clickup_connector.py` | `CLICKUP_API_KEY` |
| Linear | `src/linear_connector.py` | `LINEAR_API_KEY` |
| Wrike | `src/wrike_connector.py` | `WRIKE_ACCESS_TOKEN` |

### LLM/AI (6 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| DeepInfra | `src/llm_integration_layer.py` | `DEEPINFRA_API_KEY` |
| Together AI | `src/llm_integration_layer.py` | `TOGETHER_API_KEY` |
| OpenAI | `src/llm_integration_layer.py` | `OPENAI_API_KEY` |
| Anthropic | `src/llm_integration_layer.py` | `ANTHROPIC_API_KEY` |
| Cohere | `src/llm_integration_layer.py` | `COHERE_API_KEY` |
| HuggingFace | `src/llm_integration_layer.py` | `HF_TOKEN` |

### Payments (5 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| Stripe | `src/stripe_connector.py` | `STRIPE_SECRET_KEY` |
| PayPal | `src/paypal_connector.py` | `PAYPAL_*` |
| Square | `src/square_connector.py` | `SQUARE_ACCESS_TOKEN` |
| Coinbase | `src/coinbase_connector.py` | `COINBASE_*` |
| Plaid | `src/plaid_connector.py` | `PLAID_*` |

### Cloud/Infrastructure (8 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| AWS | `src/aws_connector.py` | `AWS_*` |
| GCP | `src/gcp_connector.py` | `GOOGLE_*` |
| Azure | `src/azure_connector.py` | `AZURE_*` |
| DigitalOcean | `src/digitalocean_connector.py` | `DO_TOKEN` |
| Hetzner | `src/hetzner_connector.py` | `HETZNER_API_TOKEN` |
| Cloudflare | `src/cloudflare_connector.py` | `CLOUDFLARE_*` |
| Vercel | `src/vercel_connector.py` | `VERCEL_TOKEN` |
| Netlify | `src/netlify_connector.py` | `NETLIFY_AUTH_TOKEN` |

### Developer Tools (10 connectors)

| Connector | Module | Credentials Required |
|-----------|--------|---------------------|
| GitHub | `src/github_connector.py` | `GITHUB_TOKEN` |
| GitLab | `src/gitlab_connector.py` | `GITLAB_TOKEN` |
| Bitbucket | `src/bitbucket_connector.py` | `BITBUCKET_*` |
| CircleCI | `src/circleci_connector.py` | `CIRCLECI_TOKEN` |
| Jenkins | `src/jenkins_connector.py` | `JENKINS_*` |
| Datadog | `src/datadog_connector.py` | `DATADOG_API_KEY` |
| PagerDuty | `src/pagerduty_connector.py` | `PAGERDUTY_API_KEY` |
| Sentry | `src/sentry_connector.py` | `SENTRY_DSN` |
| NewRelic | `src/newrelic_connector.py` | `NEW_RELIC_*` |
| Grafana | `src/grafana_connector.py` | `GRAFANA_API_KEY` |

---

## Unified Adapter Pattern

All connectors follow this interface:

```python
class PlatformAdapter(ABC):
    """Base class for all platform connectors."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the platform."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass
    
    @abstractmethod
    async def health_check(self) -> dict:
        """Check platform availability."""
        pass
    
    @abstractmethod
    async def execute(self, action: str, params: dict) -> dict:
        """Execute a platform-specific action."""
        pass
```

---

## Configuration

Connectors are configured via environment variables.
See `.env.example` for the full list of supported variables.

```bash
# Example: Enable Slack integration
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-signing-secret
```

---

## Testing Connectors

```bash
# Test a specific connector
pytest tests/test_slack_connector.py -v

# Test all connectors (requires credentials)
pytest tests/integration/ -v -k connector
```

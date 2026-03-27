"""
Murphy Terminal — Configuration and Constants

Contains all configuration values, environment variables, and static mappings
used across the Murphy Terminal package.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import os
from typing import Dict, List

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Placeholder strings that appear in template .env files but are not real keys.
PLACEHOLDER_KEY_VALUES = frozenset({
    # Generic placeholders
    "your_groq_key_here", "your_openai_key_here",
    "your_key_here", "your-key-here", "change_me", "changeme", "xxx", "none",
    # .env.example placeholders — AI / LLM
    "your_groq_api_key_here", "sk-your_openai_key_here",
    "sk-ant-your_anthropic_key_here",
    # Communication
    "sg.your_sendgrid_key_here",
    "xoxb-your-slack-bot-token-here",
    "your_twilio_auth_token_here",
    "your_twilio_account_sid_here",
    # CRM / Sales
    "your_hubspot_api_key_here",
    "your_pipedrive_token_here",
    "your_salesforce_consumer_key_here",
    # Payments
    "sk_test_your_stripe_key_here",
    # Dev / Hosting
    "ghp_your_github_token_here",
    # Monitoring
    "your_datadog_api_key_here",
    "your_pagerduty_api_key_here",
    # Productivity
    "secret_your_notion_key_here",
    "your_jira_api_token_here",
    "your_asana_access_token_here",
    "your_monday_api_key_here",
    "your_airtable_api_key_here",
    # Cloud
    "your_aws_access_key_id_here",
    "your_aws_secret_access_key_here",
    # Video / Meetings
    "your_zoom_api_key_here",
    # Analytics / Data
    "your_google_analytics_api_key_here",
    "your_openweather_api_key_here",
    # Legacy
    "your_aristotle_api_key_here",
    "your_wulfrum_api_key_here",
})

DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.environ.get("MURPHY_API_URL", DEFAULT_API_URL)
RECONNECT_INTERVAL = 15  # seconds between auto-reconnect attempts
MAX_RECONNECT_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Module → Command mapping (used for audit / discoverability)
# ---------------------------------------------------------------------------

MODULE_COMMAND_MAP: Dict[str, List[str]] = {
    "billing": ["billing", "subscription", "tier", "pricing"],
    "librarian": ["librarian", "knowledge base", "search docs"],
    "hitl": ["hitl", "pending interventions", "hitl stats"],
    "execution": ["execute <task>", "run task", "launch"],
    "corrections": ["corrections", "correction stats"],
    "health_monitor": ["health", "alive", "ping"],
    "analytics_dashboard": ["status", "dashboard"],
    "onboarding": ["start interview", "onboard me", "setup", "begin"],
    "compliance_engine": ["compliance status"],
    "planning": ["plan", "execution plan", "two-plane"],
    "sales_automation": ["sales report"],
    "system_librarian": ["librarian", "knowledge base"],
    "integration_engine": ["integrations", "show integrations"],
    "api_setup": ["api keys", "get api keys", "set key <provider> <key>"],
    "command_system": ["help", "commands", "show modules"],
    "conversation_handler": ["chat (natural language)"],
}

# ---------------------------------------------------------------------------
# API Provider Links — direct signup URLs for third-party services
# ---------------------------------------------------------------------------

API_PROVIDER_LINKS: Dict[str, Dict[str, str]] = {
    "deepinfra": {
        "name": "DeepInfra",
        "url": "https://deepinfra.com/dash/api_keys",
        "env_var": "DEEPINFRA_API_KEY",
        "description": "LLM provider (fast inference for Llama, Mixtral, Qwen)",
    },
    "together": {
        "name": "Together AI",
        "url": "https://api.together.xyz/settings/api-keys",
        "env_var": "TOGETHER_API_KEY",
        "description": "LLM provider (open models, fine-tuning)",
    },
    "openai": {
        "name": "OpenAI",
        "url": "https://platform.openai.com/api-keys",
        "env_var": "OPENAI_API_KEY",
        "description": "LLM provider (GPT-4, GPT-3.5)",
    },
    "github": {
        "name": "GitHub",
        "url": "https://github.com/settings/tokens",
        "env_var": "GITHUB_TOKEN",
        "description": "Repository integration, CI/CD, issue tracking",
    },
    "slack": {
        "name": "Slack",
        "url": "https://api.slack.com/apps",
        "env_var": "SLACK_BOT_TOKEN",
        "description": "Team messaging and notifications",
    },
    "stripe": {
        "name": "Stripe",
        "url": "https://dashboard.stripe.com/apikeys",
        "env_var": "STRIPE_API_KEY",
        "description": "Payment processing and billing",
    },
    "sendgrid": {
        "name": "SendGrid",
        "url": "https://app.sendgrid.com/settings/api_keys",
        "env_var": "SENDGRID_API_KEY",
        "description": "Email delivery and marketing",
    },
    "twilio": {
        "name": "Twilio",
        "url": "https://www.twilio.com/console",
        "env_var": "TWILIO_AUTH_TOKEN",
        "description": "SMS, voice, and phone integrations",
    },
    "hubspot": {
        "name": "HubSpot",
        "url": "https://developers.hubspot.com/get-started",
        "env_var": "HUBSPOT_API_KEY",
        "description": "CRM, marketing, sales automation",
    },
    "salesforce": {
        "name": "Salesforce",
        "url": "https://developer.salesforce.com/signup",
        "env_var": "SALESFORCE_TOKEN",
        "description": "CRM and enterprise sales platform",
    },
    "shopify": {
        "name": "Shopify",
        "url": "https://partners.shopify.com/signup",
        "env_var": "SHOPIFY_API_KEY",
        "description": "E-commerce platform and store management",
    },
    "google": {
        "name": "Google Cloud / Workspace",
        "url": "https://console.cloud.google.com/apis/credentials",
        "env_var": "GOOGLE_API_KEY",
        "description": "Google Sheets, Gmail, Calendar, Cloud services",
    },
}

# ---------------------------------------------------------------------------
# Intent Detection Patterns
# ---------------------------------------------------------------------------

INTENT_PATTERNS = {
    "intent_status": [r"\bstatus\b", r"\bdashboard\b"],
    "intent_help": [r"\bhelp\b", r"\bcommands\b", r"\bshow modules\b"],
    "intent_api_keys": [r"\bapi keys?\b", r"\bget api keys?\b", r"\bshow keys?\b"],
    "intent_health": [r"\bhealth\b", r"\bping\b", r"\balive\b"],
    "intent_billing": [r"\bbilling\b", r"\bsubscription\b", r"\btier\b", r"\bpricing\b"],
    "intent_hitl": [r"\bhitl\b", r"\bpending interventions?\b"],
    "intent_onboarding": [r"\bstart interview\b", r"\bonboard\b", r"\bsetup\b", r"\bbegin\b"],
    "intent_compliance": [r"\bcompliance\b"],
    "intent_integrations": [r"\bintegrations?\b", r"\bshow integrations?\b"],
    "intent_set_key": [r"\bset key\b"],
    "intent_execute": [r"\bexecute\b", r"\brun task\b", r"\blaunch\b"],
    "intent_corrections": [r"\bcorrections?\b", r"\bcorrection stats?\b"],
    "intent_sales": [r"\bsales report\b"],
    "intent_planning": [r"\bplan\b", r"\bexecution plan\b"],
    "intent_librarian": [r"\blibrarian\b", r"\bknowledge base\b", r"\bsearch docs?\b"],
}

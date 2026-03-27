#!/usr/bin/env python3
"""
Murphy System — Interactive Natural Language Terminal UI

A conversational TUI (Terminal User Interface) for interacting with
Murphy System via natural language.  Start with:

    python murphy_terminal.py

Connects to the Murphy backend API at http://localhost:8000 (configurable
via MURPHY_API_URL environment variable).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
import uuid
import json
import re
import subprocess
import platform
from datetime import datetime
from typing import Optional

import requests
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Static,
    RichLog,
)

from src.env_manager import (
    read_env,
    write_env_key,
    reload_env,
    validate_api_key,
    strip_key_wrapping,
    get_env_path,
    API_KEY_FORMATS,
)

try:
    import pyperclip  # Optional clipboard support
except ImportError:
    pyperclip = None

try:
    import win32clipboard as _win32clipboard  # Optional: Windows clipboard fallback (pywin32)
except ImportError:
    _win32clipboard = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Placeholder strings that appear in template .env files but are not real keys.
_PLACEHOLDER_KEY_VALUES = frozenset({
    "your_deepinfra_key_here", "your_openai_key_here",
    # Placeholders used in .env.example
    "your_deepinfra_api_key_here", "sk-your_openai_key_here",
    "sk-ant-your_anthropic_key_here",
    "your_key_here", "your-key-here", "change_me",
    "changeme", "xxx", "none",
})

DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.environ.get("MURPHY_API_URL", DEFAULT_API_URL)
RECONNECT_INTERVAL = 15  # seconds between auto-reconnect attempts
MAX_RECONNECT_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Module → Command mapping (used for audit / discoverability)
# ---------------------------------------------------------------------------

MODULE_COMMAND_MAP: dict[str, list[str]] = {
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
# API Provider Links — direct signup URLs for third-party services.
#
# Each entry maps a service key to its display name, API key signup URL,
# environment variable name, and description.  Used by ``intent_api_keys``
# and ``DialogContext._infer_integrations`` to guide users to the exact
# page where they can obtain credentials needed by Murphy.
# ---------------------------------------------------------------------------

API_PROVIDER_LINKS: dict[str, dict[str, str]] = {
    "deepinfra": {
        "name": "DeepInfra",
        "url": "https://deepinfra.com",
        "env_var": "DEEPINFRA_API_KEY",
        "description": "LLM provider (fast inference for Llama, Mixtral, Gemma)",
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
# Backend API client
# ---------------------------------------------------------------------------


class MurphyAPIClient:
    """Thin wrapper around the Murphy System REST API."""

    def __init__(self, base_url: str = API_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.last_error: Optional[str] = None

    # -- helpers --

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _get(self, path: str) -> dict:
        resp = requests.get(self._url(path), timeout=self.timeout)
        resp.raise_for_status()
        self.last_error = None
        return resp.json()

    def _post(self, path: str, payload: dict) -> dict:
        resp = requests.post(
            self._url(path), json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        self.last_error = None
        return resp.json()

    def set_base_url(self, url: str) -> None:
        """Update the backend API URL at runtime."""
        self.base_url = url.rstrip("/")
        self.session_id = None
        self.last_error = None

    def test_connection(self) -> tuple[bool, str]:
        """Test connectivity to backend. Returns (ok, detail_message)."""
        try:
            data = self.health()
            status = data.get("status", "unknown")
            version = data.get("version", "n/a")
            return True, f"Healthy — status={status}, version={version}"
        except requests.ConnectionError:
            msg = f"Connection refused at {self.base_url}"
            self.last_error = msg
            return False, msg
        except requests.Timeout:
            msg = f"Timeout after {self.timeout}s reaching {self.base_url}"
            self.last_error = msg
            return False, msg
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            msg = f"HTTP {code} from {self.base_url}"
            self.last_error = msg
            return False, msg
        except Exception as exc:
            msg = f"Cannot reach {self.base_url}: {type(exc).__name__}"
            self.last_error = msg
            return False, msg

    # -- public API methods --

    def health(self) -> dict:
        return self._get("/api/health")

    def status(self) -> dict:
        return self._get("/api/status")

    def info(self) -> dict:
        return self._get("/api/info")

    def create_session(self, name: Optional[str] = None) -> dict:
        result = self._post("/api/sessions/create", {"name": name or "terminal"})
        self.session_id = result.get("session_id", self.session_id)
        return result

    def chat(self, message: str) -> dict:
        payload: dict = {"message": message}
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/chat", payload)

    def execute(self, task_description: str, task_type: str = "general", parameters: Optional[dict] = None) -> dict:
        payload: dict = {
            "task_description": task_description,
            "task_type": task_type,
        }
        if parameters:
            payload["parameters"] = parameters
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/execute", payload)

    def corrections_stats(self) -> dict:
        return self._get("/api/corrections/statistics")

    def hitl_pending(self) -> dict:
        return self._get("/api/hitl/interventions/pending")

    def hitl_stats(self) -> dict:
        return self._get("/api/hitl/statistics")

    def librarian_ask(self, message: str) -> dict:
        payload: dict = {"message": message}
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/librarian/ask", payload)

    def llm_status(self) -> dict:
        return self._get("/api/llm/status")

    def configure_llm(self, provider: str, api_key: str) -> dict:
        """Notify the backend to hot-reload LLM config with the new provider/key."""
        try:
            return self._post("/api/llm/configure", {"provider": provider, "api_key": api_key})
        except requests.RequestException:
            return {"success": False, "error": "backend not reachable"}

    def librarian_status(self) -> dict:
        return self._get("/api/librarian/status")

    def llm_test(self) -> dict:
        """Ask the backend to make a minimal test call to verify the LLM key."""
        try:
            return self._post("/api/llm/test", {})
        except requests.RequestException:
            return {"success": False, "error": "backend not reachable"}

    def llm_reload(self) -> dict:
        """Ask the backend to re-read .env and reinitialise LLM config."""
        try:
            return self._post("/api/llm/reload", {})
        except requests.RequestException:
            return {"success": False, "error": "backend not reachable"}

    def create_document(self, title: str, content: str, doc_type: str = "general") -> dict:
        """Create a living document for block-command workflows."""
        payload: dict = {"title": title, "content": content, "type": doc_type}
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/documents", payload)

    def magnify_document(self, doc_id: str, domain: str = "general") -> dict:
        """Expand domain depth of a living document to increase context coverage."""
        return self._post(f"/api/documents/{doc_id}/magnify", {"domain": domain})

    def simplify_document(self, doc_id: str) -> dict:
        """Reduce complexity of a living document to improve clarity."""
        return self._post(f"/api/documents/{doc_id}/simplify", {})

    def solidify_document(self, doc_id: str) -> dict:
        """Lock a document and trigger swarm task generation."""
        return self._post(f"/api/documents/{doc_id}/solidify", {})


# ---------------------------------------------------------------------------
# Dialog context — synthetic interview state tracking
# ---------------------------------------------------------------------------


class DialogContext:
    """Tracks conversation state for context-aware dialog flow.

    Maintains collected user data, the current interview step, feedback
    history, and previously asked questions so Murphy can advance the
    conversation intelligently and avoid repetition.
    """

    INTERVIEW_STEPS: list[dict] = [
        {"key": "name", "prompt": "What is your name or organisation?", "label": "Name / Org"},
        {"key": "business_goal", "prompt": "What is the primary business goal you'd like Murphy to help with? (e.g. increase sales, reduce costs, automate operations, improve compliance)", "label": "Business Goal"},
        {"key": "use_case", "prompt": "What is your primary use-case for Murphy? (e.g. onboarding, automation, monitoring)", "label": "Use-Case"},
        {"key": "platforms", "prompt": "What platforms or tools does your team use today? (e.g. email, Slack, GitHub, CRM, social media — or 'skip' if unsure)", "label": "Current Platforms"},
        {"key": "billing_tier", "prompt": "Which billing tier interests you? (free / starter / pro / enterprise, or 'all' to see details)", "label": "Billing Tier"},
        {"key": "integrations", "prompt": "Based on your answers, which integrations should Murphy set up? (e.g. GitHub, Slack, email — or 'auto' to let Murphy decide)", "label": "Integrations"},
        {"key": "confirm", "prompt": "Here's what I have so far — shall I proceed? (yes / no / edit)", "label": "Confirmation"},
    ]

    def __init__(self) -> None:
        self.collected: dict[str, str] = {}
        self.step_index: int = 0
        self.active: bool = False
        self.feedback_log: list[str] = []
        self.asked_questions: set[str] = set()

    # -- state queries --

    @property
    def current_step(self) -> Optional[dict]:
        if 0 <= self.step_index < len(self.INTERVIEW_STEPS):
            return self.INTERVIEW_STEPS[self.step_index]
        return None

    @property
    def progress_label(self) -> str:
        total = len(self.INTERVIEW_STEPS)
        current = min(self.step_index + 1, total)
        step = self.current_step
        label = step["label"] if step else "Complete"
        return f"Step {current}/{total}: {label}"

    @property
    def is_complete(self) -> bool:
        return self.step_index >= len(self.INTERVIEW_STEPS)

    def summary(self) -> str:
        if not self.collected:
            return "(no information collected yet)"
        lines = [f"  • {k}: {v}" for k, v in self.collected.items()]
        return "\n".join(lines)

    # -- mutation --

    def start(self) -> str:
        """Start or restart the interview, returning the first prompt."""
        self.step_index = 0
        self.active = True
        step = self.current_step
        if step:
            self.asked_questions.add(step["key"])
            return f"[bold cyan]{self.progress_label}[/bold cyan]\n{step['prompt']}"
        return "Interview has no steps configured."

    def advance(self, user_input: str) -> str:
        """Record user answer for the current step and return the next prompt."""
        step = self.current_step
        if step is None:
            self.active = False
            return self._complete_message()

        stripped = user_input.strip()
        normalised = stripped.lower()

        # Handle skip / back / review navigation
        if normalised == "skip":
            return self._skip()
        if normalised in ("back", "previous"):
            return self._go_back()
        if normalised in ("review", "show"):
            return f"[bold cyan]Collected so far:[/bold cyan]\n{self.summary()}\n\n{step['prompt']}"

        # Infer context from conversational responses
        inferred = self._infer_value(step["key"], normalised, stripped)
        self.collected[step["key"]] = inferred
        self.step_index += 1

        next_step = self.current_step
        if next_step is None:
            self.active = False
            return self._complete_message()

        self.asked_questions.add(next_step["key"])
        return (
            f"[dim]✓ Got it — recorded [bold]{step['label']}[/bold]: {inferred}[/dim]\n"
            f"[bold cyan]{self.progress_label}[/bold cyan]\n{next_step['prompt']}"
        )

    def record_feedback(self, text: str) -> None:
        self.feedback_log.append(text)

    # -- internal helpers --

    def _skip(self) -> str:
        step = self.current_step
        if step:
            self.collected[step["key"]] = "(skipped)"
        self.step_index += 1
        next_step = self.current_step
        if next_step is None:
            self.active = False
            return self._complete_message()
        self.asked_questions.add(next_step["key"])
        return f"[dim]Skipped.[/dim]\n[bold cyan]{self.progress_label}[/bold cyan]\n{next_step['prompt']}"

    def _go_back(self) -> str:
        if self.step_index > 0:
            self.step_index -= 1
        step = self.current_step
        if step:
            return f"[dim]Going back…[/dim]\n[bold cyan]{self.progress_label}[/bold cyan]\n{step['prompt']}"
        return "Already at the beginning."

    def _complete_message(self) -> str:
        msg = (
            "[bold green]✓ Interview complete![/bold green]\n"
            f"Here's what I collected:\n{self.summary()}\n\n"
        )
        # Infer and show recommended integrations from answers
        recs = self._infer_integrations()
        if recs:
            msg += "[bold cyan]Recommended integrations based on your answers:[/bold cyan]\n"
            for i, (svc_key, info) in enumerate(recs.items(), 1):
                msg += (
                    f"  {i}. [bold]{info['name']}[/bold] — {info['description']}\n"
                    f"     Get your key: [link={info['url']}]{info['url']}[/link]\n"
                    f"     Set: [green]{info['env_var']}[/green]\n"
                )
            msg += (
                "\n[bold cyan]What to do next:[/bold cyan]\n"
                "  1. Sign up for the API keys listed above (links provided)\n"
                "  2. Set keys right here: [green]set key deepinfra di_...[/green] (no restart needed)\n"
                "  3. Type [green]status[/green] to verify everything is connected\n"
                "  4. Type [green]execute <your first task>[/green] to start automating!\n\n"
            )
        else:
            msg += (
                "[bold cyan]What to do next:[/bold cyan]\n"
                "  1. Type [green]status[/green] to verify the system is ready\n"
                "  2. Type [green]execute <your first task>[/green] to start automating\n"
                "  3. Type [green]api keys[/green] if you need integration credentials\n\n"
            )
        msg += (
            "Type [green]confirm[/green] to proceed, [green]edit[/green] to change answers, "
            "or [green]restart[/green] to start over.\n"
            "Type [green]api keys[/green] to see all available API signup links."
        )
        return msg

    def _infer_integrations(self) -> dict[str, dict[str, str]]:
        """Analyze collected answers and return matching API_PROVIDER_LINKS entries.

        Uses three inference levels:
          1. **Keyword matching** — direct mentions of platforms
          2. **Workflow action mapping** — infers APIs from described actions
          3. **Business goal mapping** — infers APIs from high-level goals
        """
        combined = " ".join(str(v) for v in self.collected.values()).lower()

        # Level 1: Direct keyword matching
        keyword_map = {
            "email": ["sendgrid", "google"],
            "gmail": ["google"],
            "crm": ["hubspot", "salesforce"],
            "hubspot": ["hubspot"],
            "salesforce": ["salesforce"],
            "slack": ["slack"],
            "sms": ["twilio"],
            "phone": ["twilio"],
            "github": ["github"],
            "payment": ["stripe"],
            "stripe": ["stripe"],
            "shopify": ["shopify"],
            "e-commerce": ["shopify", "stripe"],
            "ecommerce": ["shopify", "stripe"],
            "sell": ["stripe", "shopify"],
            "sales": ["hubspot"],
            "marketing": ["sendgrid", "hubspot"],
            "google": ["google"],
            "sheets": ["google"],
            "jira": ["jira"],
            "notion": ["notion"],
        }

        # Level 2: Workflow action → API inference
        action_map = {
            "send email": ["sendgrid", "google"],
            "send notification": ["sendgrid", "slack"],
            "send message": ["slack", "twilio"],
            "notify team": ["slack", "sendgrid"],
            "post to channel": ["slack"],
            "create issue": ["github", "jira"],
            "open ticket": ["jira", "github"],
            "pull request": ["github"],
            "deploy": ["github"],
            "track leads": ["hubspot", "salesforce"],
            "lead scoring": ["hubspot", "salesforce"],
            "process payment": ["stripe"],
            "online store": ["shopify", "stripe"],
            "schedule meeting": ["google"],
            "social media": ["zapier"],
            "automate workflow": ["zapier"],
        }

        # Level 3: Business goal → API inference
        goal_map = {
            "increase sales": ["hubspot", "sendgrid", "stripe"],
            "grow revenue": ["hubspot", "sendgrid", "stripe"],
            "reduce costs": ["zapier", "google"],
            "automate operations": ["zapier", "slack", "github"],
            "customer support": ["hubspot", "slack", "sendgrid"],
            "devops": ["github", "slack", "jira"],
            "software development": ["github", "jira", "slack"],
            "team collaboration": ["slack", "notion", "google"],
            "lead generation": ["hubspot", "sendgrid"],
        }

        matched: dict[str, dict[str, str]] = {}

        def _add(pk: str) -> None:
            if pk not in matched and pk in API_PROVIDER_LINKS:
                matched[pk] = API_PROVIDER_LINKS[pk]

        for keyword, provider_keys in keyword_map.items():
            if keyword in combined:
                for pk in provider_keys:
                    _add(pk)

        for action, provider_keys in action_map.items():
            if action in combined:
                for pk in provider_keys:
                    _add(pk)

        for goal, provider_keys in goal_map.items():
            if goal in combined:
                for pk in provider_keys:
                    _add(pk)

        # Always recommend LLM if not configured
        if "deepinfra" not in matched:
            llm_provider = os.environ.get("MURPHY_LLM_PROVIDER", "").strip()
            if not llm_provider:
                matched["deepinfra"] = API_PROVIDER_LINKS["deepinfra"]
        return matched

    @staticmethod
    def _infer_value(key: str, text: str, original: str = "") -> str:
        """Infer a meaningful value from conversational input.

        ``text`` is the lowercased version used for matching;
        ``original`` is the user's input with original casing, used as the
        passthrough fallback.
        """
        # Handle vague / contextual answers
        if text in ("all", "all of them", "everything", "all tiers"):
            return "all"
        if text in ("not sure", "i don't know", "idk", "unsure", "no idea", "dunno"):
            return "(needs guidance)"
        if text in ("yes", "yep", "sure", "ok", "okay", "y"):
            return "yes"
        if text in ("no", "nope", "nah", "n"):
            return "no"
        if text in ("auto", "automatic", "let murphy decide", "you decide"):
            return "(auto-configure)"
        return original if original else text


# ---------------------------------------------------------------------------
# Intent detection — local keyword / regex based (no external model needed)
# ---------------------------------------------------------------------------

# Mapping of intent keywords → handler method names on the app.
INTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(health|alive|ping)\b", re.I), "intent_health"),
    (re.compile(r"^llm[_ ]?status\b", re.I), "intent_llm_status"),
    (re.compile(r"^librarian[_ ]?status\b", re.I), "intent_librarian_status"),
    (re.compile(r"^(api[_ ]?keys?|get[_ ]?api[_ ]?keys?)\b", re.I), "intent_api_keys"),
    (re.compile(r"\b(status|state|dashboard)\b", re.I), "intent_status"),
    (re.compile(r"\b(info|about|version)\b", re.I), "intent_info"),
    (re.compile(r"\b(help|commands|what can)\b", re.I), "intent_help"),
    (re.compile(r"\b(exit|quit|bye|close)\b", re.I), "intent_exit"),
    (re.compile(r"\b(corrections?|correction stats)\b", re.I), "intent_corrections"),
    (re.compile(r"\b(pending|interventions?|hitl)\b", re.I), "intent_hitl"),
    (re.compile(r"\b(execute|run task|launch)\b", re.I), "intent_execute"),
    (re.compile(r"^set[_ ]?key\b", re.I), "intent_set_key"),
    (re.compile(r"^set[_ ]?api\b", re.I), "intent_set_api"),
    (re.compile(r"^test[_ ]?api\b|^test[_ ]?connection\b", re.I), "intent_test_api"),
    (re.compile(r"^reconnect\b", re.I), "intent_reconnect"),
    (re.compile(r"^(start interview|onboard me|setup|begin)\b", re.I), "intent_start_interview"),
    (re.compile(r"^(skip)\b", re.I), "intent_skip"),
    (re.compile(r"^(back|previous)\b", re.I), "intent_back"),
    (re.compile(r"^(review|show collected)\b", re.I), "intent_review"),
    (re.compile(r"^(restart)\b", re.I), "intent_restart_interview"),
    (re.compile(r"^(confirm)\b", re.I), "intent_confirm"),
    (re.compile(r"\b(librarian|library|knowledge base)\b", re.I), "intent_librarian"),
    (re.compile(r"^(show modules|list modules|modules)\b", re.I), "intent_modules"),
    (re.compile(r"\b(billing|subscription|tier|pricing)\b", re.I), "intent_billing"),
    (re.compile(r"^(ui|user interface|show ui|ui links|open ui)\b", re.I), "intent_ui"),
    (re.compile(r"^(account|sign.?up|sign.?in|get started|account flow)\b", re.I), "intent_account"),
    (re.compile(r"\b(links|urls|dashboards)\b", re.I), "intent_links"),
    (re.compile(r"\b(plan|planning|two.?plane|execution plan)\b", re.I), "intent_plan"),
    (re.compile(r"^paste\b", re.I), "intent_paste"),
    (re.compile(r"^magnify\b", re.I), "intent_magnify"),
    (re.compile(r"^simplify\b", re.I), "intent_simplify"),
    (re.compile(r"^solidify\b", re.I), "intent_solidify"),
    # ── New feature toggles ──────────────────────────────────────────────
    (re.compile(r"^(/toggle[_ ]?test[_ ]?mode|test[_ ]?mode)\b", re.I), "intent_toggle_test_mode"),
    (re.compile(r"^(/toggle[_ ]?self[_ ]?learn|toggle[_ ]?self[_ ]?learn|self[_ ]?learn)\b", re.I), "intent_toggle_self_learning"),
    (re.compile(r"^(readiness|ready|scan|pre.?flight|check)\b", re.I), "intent_readiness_scan"),
]

# Patterns that indicate user frustration or feedback
FEEDBACK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(too complicated|confus|frustrat|annoying|broken|not working|doesn'?t work|useless)\b", re.I),
    re.compile(r"\b(feedback|suggestion|complaint|issue)\b", re.I),
    re.compile(r"\b(help me|i need help|stuck|lost)\b", re.I),
    re.compile(r"\bconfused\b", re.I),
]


def detect_feedback(message: str) -> bool:
    """Return True if the message contains frustration / feedback signals."""
    return any(p.search(message) for p in FEEDBACK_PATTERNS)


def detect_intent(message: str) -> Optional[str]:
    """Return the first matching intent handler name, or None."""
    for pattern, intent in INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return None


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

WELCOME_TEXT = """\
[bold cyan]╔══════════════════════════════════════════════════════════════╗
║              ☠  Murphy System Terminal  ☠                  ║
║                  Natural Language Interface                   ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]

[bold]Hello! I'm Murphy — your professional automation assistant.[/bold]
I help teams automate operations, onboard new users, manage integrations,
and run end-to-end workflows with minimal manual effort.

[bold cyan]🚀 Getting Started[/bold cyan]
  • [green]start interview[/green]  — guided onboarding (I'll learn about your needs first)
  • [green]account[/green]          — see the signup → verify → session → automation flow
  • [green]help[/green]             — see all available commands
  • [green]show modules[/green]    — list all system modules and their commands

[bold cyan]📡 Quick Commands[/bold cyan]
  • [green]health[/green] / [green]status[/green]  — check system health
  • [green]execute <task>[/green]   — run a task or workflow
  • [green]set key deepinfra <key>[/green] — configure your API key (no restart needed)
  • [green]librarian[/green]       — consult the knowledge base expert
  • [green]billing[/green]         — view billing and subscription info
  • [green]links[/green]           — show dashboard and UI links
  • [green]ui[/green]              — show role-based UI links

[bold cyan]🔗 Dashboard Links[/bold cyan]
  • Swagger API Docs : [link=http://localhost:8000/docs]http://localhost:8000/docs[/link]
  • System Dashboard : [link=http://localhost:8000/api/status]http://localhost:8000/api/status[/link]
  • Onboarding UI    : [link=http://localhost:8000/onboarding]http://localhost:8000/onboarding[/link]
  • Terminal (Web)   : [link=http://localhost:8000/terminal]http://localhost:8000/terminal[/link]

[dim]Type any question in natural language — Murphy will respond conversationally.[/dim]
[dim]Tip: Use right-click to paste, or type [green]paste[/green] to paste from clipboard.[/dim]
"""

DASHBOARD_LINKS: list[dict[str, str]] = [
    {"name": "Swagger API Docs", "url": "/docs"},
    {"name": "System Dashboard", "url": "/api/status"},
    {"name": "Onboarding UI", "url": "/onboarding"},
    {"name": "Terminal (Web)", "url": "/terminal"},
    {"name": "Health Check", "url": "/api/health"},
]

# ---------------------------------------------------------------------------
# Account lifecycle flow — the ordered stages a user goes through from
# discovering the system to having a fully configured automation account.
# ---------------------------------------------------------------------------

ACCOUNT_LIFECYCLE_FLOW: list[dict[str, str]] = [
    {
        "stage": "info",
        "name": "Info & Landing Page",
        "url": "/ui/landing",
        "api": "/api/info",
        "description": "Learn about Murphy System capabilities and features",
    },
    {
        "stage": "signup",
        "name": "Account Signup",
        "url": "/ui/onboarding",
        "api": "/api/onboarding/wizard/questions",
        "description": "Create an account through the onboarding wizard",
    },
    {
        "stage": "verify",
        "name": "Account Verification",
        "url": "/ui/onboarding",
        "api": "/api/onboarding/wizard/validate",
        "description": "Validate configuration and verify account setup",
    },
    {
        "stage": "session",
        "name": "Account Session",
        "url": "/ui/dashboard",
        "api": "/api/sessions/create",
        "description": "Start an authenticated session to access your account",
    },
    {
        "stage": "automation",
        "name": "Automation Management",
        "url": "/ui/terminal-integrated",
        "api": "/api/execute",
        "description": "Create, configure, and manage your automations",
    },
]

# ---------------------------------------------------------------------------
# Role-based UI links — maps each RBAC user type to the HTML interfaces
# that are appropriate for their access level.
# ---------------------------------------------------------------------------

USER_TYPE_UI_LINKS: dict[str, list[dict[str, str]]] = {
    "owner": [
        {"name": "Architect Terminal", "url": "/ui/terminal-architect", "file": "terminal_architect.html"},
        {"name": "Integrated Terminal", "url": "/ui/terminal-integrated", "file": "murphy_ui_integrated_terminal.html"},
        {"name": "Full Dashboard", "url": "/ui/dashboard", "file": "murphy_ui_integrated.html"},
        {"name": "Onboarding Wizard", "url": "/ui/onboarding", "file": "onboarding_wizard.html"},
        {"name": "Landing Page", "url": "/ui/landing", "file": "murphy_landing_page.html"},
    ],
    "admin": [
        {"name": "Architect Terminal", "url": "/ui/terminal-architect", "file": "terminal_architect.html"},
        {"name": "Integrated Terminal", "url": "/ui/terminal-integrated", "file": "murphy_ui_integrated_terminal.html"},
        {"name": "Full Dashboard", "url": "/ui/dashboard", "file": "murphy_ui_integrated.html"},
        {"name": "Onboarding Wizard", "url": "/ui/onboarding", "file": "onboarding_wizard.html"},
    ],
    "operator": [
        {"name": "Worker Terminal", "url": "/ui/terminal-worker", "file": "terminal_worker.html"},
        {"name": "Enhanced Terminal", "url": "/ui/terminal-enhanced", "file": "terminal_enhanced.html"},
        {"name": "Operator Terminal", "url": "/ui/terminal-operator", "file": "terminal_integrated.html"},
    ],
    "viewer": [
        {"name": "Landing Page", "url": "/ui/landing", "file": "murphy_landing_page.html"},
        {"name": "Enhanced Terminal", "url": "/ui/terminal-enhanced", "file": "terminal_enhanced.html"},
    ],
}


class StatusBar(Static):
    """Top-right status indicator."""

    connected = reactive(False)
    api_url = reactive("")
    llm_enabled = reactive(False)
    llm_warning = reactive(False)

    def render(self) -> str:
        if self.llm_enabled:
            llm = "[green]LLM: On ✓[/green]"
        elif self.llm_warning:
            llm = "[yellow]LLM: ⚠[/yellow]"
        else:
            llm = "[yellow]LLM: Off[/yellow]"
        if self.connected:
            return f"[bold green]● Connected[/bold green]  {llm}"
        return f"[bold red]● Disconnected[/bold red]  {llm}"


class MurphyInput(Input):
    """Input subclass that intercepts Ctrl+V at the widget level.

    On Windows, the ``Input`` widget can consume ``ctrl+v`` before the
    app-level binding fires.  Overriding ``on_key`` here ensures paste works
    regardless of platform.
    """

    def on_key(self, event: events.Key) -> None:
        """Intercept Ctrl+V and route it to the app-level paste action."""
        if event.key == "ctrl+v":
            app = self.app
            if hasattr(app, "action_paste_clipboard"):
                app.action_paste_clipboard()
            event.prevent_default()
            event.stop()

# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------


class MurphyTerminalApp(App):
    """Murphy System — Interactive Natural Language Terminal."""

    TITLE = "Murphy System Terminal"
    SUB_TITLE = f"API: {API_URL}"

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-area {
        height: 1fr;
    }
    #chat-log {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    #sidebar {
        width: 44;
        border: solid $accent;
        padding: 1;
        overflow-y: auto;
    }
    #input-area {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    #user-input {
        width: 1fr;
    }
    StatusBar {
        dock: right;
        width: auto;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+h", "show_help", "Help", show=True),
        Binding("ctrl+s", "show_status", "Status", show=True),
        Binding("ctrl+v", "paste_clipboard", "Paste", show=False, priority=True),
        Binding("shift+insert", "paste_clipboard", "Paste", show=False),
    ]

    def __init__(self, api_url: str = API_URL, **kwargs):
        super().__init__(**kwargs)
        self.client = MurphyAPIClient(base_url=api_url)
        self._session_created = False
        self.dialog = DialogContext()
        self._reconnect_attempts = 0
        self._reconnect_timer = None
        self._offline_mode = False
        self._awaiting_api_key = False
        self._current_doc_id: Optional[str] = None  # tracks the last created living document

    # -- compose --

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
            with Vertical(id="sidebar"):
                yield StatusBar()
                yield Static(
                    "[bold cyan]Navigation[/bold cyan]\n\n"
                    "[dim]Ctrl+H[/dim] Help\n"
                    "[dim]Ctrl+S[/dim] Status\n"
                    "[dim]Ctrl+Q[/dim] Quit\n"
                    "[dim]Ctrl+V[/dim] Paste\n\n"
                    "[bold cyan]Quick Commands[/bold cyan]\n\n"
                    "[dim]health[/dim]\n"
                    "[dim]status[/dim]\n"
                    "[dim]start interview[/dim]\n"
                    "[dim]show modules[/dim]\n"
                    "[dim]librarian[/dim]\n"
                    "[dim]api keys[/dim]\n"
                    "[dim]set key <prov> <key>[/dim]\n"
                    "[dim]billing[/dim]\n"
                    "[dim]links[/dim]\n"
                    "[dim]plan[/dim]\n"
                    "[dim]llm status[/dim]\n"
                    "[dim]librarian status[/dim]\n"
                    "[dim]set api <url>[/dim]\n"
                    "[dim]test connection[/dim]\n"
                    "[dim]reconnect[/dim]\n"
                    "[dim]help[/dim]\n"
                    "[dim]exit[/dim]\n",
                    id="sidebar-hints",
                )
        yield MurphyInput(placeholder="Type a message…", id="user-input")
        yield Footer()

    # -- lifecycle --

    def on_mount(self) -> None:
        chat = self.query_one("#chat-log", RichLog)
        chat.write(WELCOME_TEXT)
        self._update_status_url()
        self._check_connection()
        self._check_api_key_on_startup()

    # -- connection --

    def _update_status_url(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.api_url = self.client.base_url
        self.sub_title = f"API: {self.client.base_url}"

    def _check_connection(self) -> None:
        status_bar = self.query_one(StatusBar)
        ok, detail = self.client.test_connection()
        if ok:
            status_bar.connected = True
            self._reconnect_attempts = 0
            self._cancel_reconnect_timer()
            self._write_system(f"Connected to Murphy backend. ({detail})")
            self._ensure_session()
            self._check_llm_status()
        else:
            status_bar.connected = False
            self._write_system(
                f"[yellow]⚠ Cannot reach Murphy backend — {detail}[/yellow]\n"
                "[dim]Tip: Use [green]set api <url>[/green] to change the address, "
                "or [green]reconnect[/green] to retry.[/dim]"
            )
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Schedule an automatic reconnection attempt."""
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self._write_system(
                f"[yellow]Auto-reconnect stopped after {MAX_RECONNECT_ATTEMPTS} attempts. "
                "Type [green]reconnect[/green] to try again manually.[/yellow]"
            )
            return
        self._cancel_reconnect_timer()
        self._reconnect_timer = self.set_timer(
            RECONNECT_INTERVAL, self._auto_reconnect
        )

    def _cancel_reconnect_timer(self) -> None:
        if self._reconnect_timer is not None:
            self._reconnect_timer.stop()
            self._reconnect_timer = None

    def _auto_reconnect(self) -> None:
        status_bar = self.query_one(StatusBar)
        if status_bar.connected:
            return
        self._reconnect_attempts += 1
        self._write_system(
            f"[dim]Reconnecting… (attempt {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})[/dim]"
        )
        ok, detail = self.client.test_connection()
        if ok:
            status_bar.connected = True
            self._reconnect_attempts = 0
            self._write_system(f"[green]✓ Reconnected![/green] ({detail})")
            self._ensure_session()
        else:
            self._schedule_reconnect()

    def _ensure_session(self) -> None:
        if self._session_created:
            return
        try:
            result = self.client.create_session(name="terminal-ui")
            self._session_created = True
            sid = result.get("session_id", "unknown")
            self._write_system(f"Session created: [cyan]{sid}[/cyan]")
        except Exception:
            pass

    def _check_llm_status(self) -> None:
        """Query backend LLM status and update the status bar.

        Uses the ``/api/llm/test`` endpoint so the status bar reflects
        actual auth state, not merely whether an env var is set.

        States:
        - Off (``llm_enabled=False``, ``llm_warning=False``): no key configured.
        - ⚠  (``llm_enabled=False``, ``llm_warning=True``):  key set but auth failed.
        - On ✓ (``llm_enabled=True``, ``llm_warning=False``): key authenticates.
        """
        status_bar = self.query_one(StatusBar)
        try:
            data = self.client.llm_status()
            enabled = data.get("enabled", False)
            provider = data.get("provider") or "none"
            if enabled:
                # Verify the key actually authenticates
                test_result = self.client.llm_test()
                if test_result.get("success"):
                    status_bar.llm_enabled = True
                    status_bar.llm_warning = False
                    model = data.get("model") or "default"
                    self._write_system(f"LLM enabled — provider=[cyan]{provider}[/cyan] model=[cyan]{model}[/cyan]")
                else:
                    status_bar.llm_enabled = False
                    status_bar.llm_warning = True
                    error = test_result.get("error", "auth failed")
                    self._write_system(
                        f"[yellow]⚠️ LLM key saved but authentication failed ({error})[/yellow] — "
                        "running in deterministic mode. "
                        "Type [green]set key deepinfra <your-key>[/green] to update."
                    )
            else:
                status_bar.llm_enabled = False
                status_bar.llm_warning = False
                error = data.get("error", "not configured")
                self._write_system(
                    f"[yellow]LLM not configured ({error})[/yellow] — "
                    "running in deterministic mode. "
                    "Type [green]set key deepinfra <your-key>[/green] to enable."
                )
        except Exception:
            status_bar.llm_enabled = False
            status_bar.llm_warning = False

    @staticmethod
    def _is_real_key(value: Optional[str]) -> bool:
        """Return True if *value* looks like a real API key (not a placeholder)."""
        if not value:
            return False
        return value.strip().lower() not in _PLACEHOLDER_KEY_VALUES

    def _check_api_key_on_startup(self) -> None:
        """First-run gate: prompt for DeepInfra API key if not configured."""
        # Check environment first, then .env file
        env_path = get_env_path()
        env_vars = read_env(env_path)
        has_key = (
            self._is_real_key(os.environ.get("DEEPINFRA_API_KEY"))
            or self._is_real_key(env_vars.get("DEEPINFRA_API_KEY"))
        )
        if has_key:
            return  # Key exists — skip the gate

        self._awaiting_api_key = True
        self._write_murphy(
            "[bold yellow]⚠ No DeepInfra API key detected[/bold yellow]\n\n"
            "Murphy needs at least a DeepInfra API key for full AI features.\n\n"
            "[bold cyan]Get your free key:[/bold cyan]\n"
            "  → [link=https://deepinfra.com]https://deepinfra.com[/link]\n\n"
            "Then paste it here, or type:\n"
            "  [green]set key deepinfra di_yourKeyHere[/green]\n"
            "  [green]skip[/green] — continue in offline mode (limited functionality)\n"
        )

    def _handle_startup_key_input(self, message: str) -> None:
        """Handle user input during the first-run API key prompt."""
        stripped = message.strip()
        lower = stripped.lower()

        if lower == "skip":
            self._awaiting_api_key = False
            self._offline_mode = True
            self._write_murphy(
                "[yellow]Continuing in offline mode.[/yellow]\n"
                "[dim]AI features will be limited. "
                "Type [green]set key deepinfra <your-key>[/green] at any time to activate full capabilities.[/dim]"
            )
            return

        # Check if it looks like a bare key (starts with di_)
        bare = strip_key_wrapping(stripped)
        if bare.startswith("di_"):
            self._awaiting_api_key = False
            self._apply_api_key("deepinfra", bare)
            return

        # Check if it's a 'set key' command
        m = re.match(r"^set[_ ]?key\s+(\w+)\s+(\S+)", stripped, re.I)
        if m:
            self._awaiting_api_key = False
            self._apply_api_key(m.group(1).lower(), m.group(2))
            return

        # For any other input, dismiss the gate and process normally
        self._awaiting_api_key = False
        self._offline_mode = True
        self._process_message(message)

    # -- helpers --

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        """Return a short, human-readable error description.

        Strips verbose Python internals (urllib3 traces, object addresses)
        and returns a concise message suitable for display in the TUI.
        """
        if isinstance(exc, requests.ConnectionError):
            return "Connection refused — is the backend running?"
        if isinstance(exc, requests.Timeout):
            return "Request timed out"
        if isinstance(exc, requests.HTTPError):
            code = exc.response.status_code if exc.response is not None else "?"
            return f"HTTP error {code}"
        return type(exc).__name__

    def _write_user(self, text: str) -> None:
        chat = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        chat.write(f"[bold green][{ts}] You:[/bold green] {text}")

    def _write_murphy(self, text: str) -> None:
        chat = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        chat.write(f"[bold cyan][{ts}] Murphy:[/bold cyan] {text}")

    def _write_system(self, text: str) -> None:
        chat = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        chat.write(f"[dim][{ts}] system:[/dim] {text}")

    def _format_json(self, data: dict) -> str:
        """Pretty-format a dict for display."""
        try:
            return json.dumps(data, indent=2, default=str)
        except Exception:
            return str(data)

    def _update_sidebar_context(self) -> None:
        """Refresh sidebar hints based on current dialog state."""
        hints = self.query_one("#sidebar-hints", Static)
        if self.dialog.active:
            hints.update(
                f"[bold cyan]Interview[/bold cyan]\n"
                f"[dim]{self.dialog.progress_label}[/dim]\n\n"
                "[dim]skip[/dim]  — skip question\n"
                "[dim]back[/dim]  — previous question\n"
                "[dim]review[/dim] — see answers\n\n"
                "[bold cyan]Quick Commands[/bold cyan]\n\n"
                "[dim]help[/dim]\n"
                "[dim]exit[/dim]\n"
            )
        else:
            hints.update(
                "[bold cyan]Navigation[/bold cyan]\n\n"
                "[dim]Ctrl+H[/dim] Help\n"
                "[dim]Ctrl+S[/dim] Status\n"
                "[dim]Ctrl+Q[/dim] Quit\n"
                "[dim]Ctrl+V[/dim] Paste\n\n"
                "[bold cyan]Quick Commands[/bold cyan]\n\n"
                "[dim]health[/dim]\n"
                "[dim]status[/dim]\n"
                "[dim]start interview[/dim]\n"
                "[dim]show modules[/dim]\n"
                "[dim]librarian[/dim]\n"
                "[dim]api keys[/dim]\n"
                "[dim]set key <prov> <key>[/dim]\n"
                "[dim]billing[/dim]\n"
                "[dim]links[/dim]\n"
                "[dim]plan[/dim]\n"
                "[dim]llm status[/dim]\n"
                "[dim]librarian status[/dim]\n"
                "[dim]set api <url>[/dim]\n"
                "[dim]test connection[/dim]\n"
                "[dim]reconnect[/dim]\n"
                "[dim]help[/dim]\n"
                "[dim]exit[/dim]\n"
            )

    # -- input handling --

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        event.input.value = ""
        self._write_user(message)
        self._process_message(message)

    def _process_message(self, message: str) -> None:
        # Handle first-run API key prompt
        if self._awaiting_api_key:
            self._handle_startup_key_input(message)
            return

        # If an interview is active, route most input through dialog context
        if self.dialog.active:
            # Allow certain intents even during interview
            intent = detect_intent(message)
            if intent in ("intent_help", "intent_exit", "intent_health",
                          "intent_status", "intent_set_api", "intent_set_key",
                          "intent_test_api",
                          "intent_reconnect", "intent_links", "intent_ui", "intent_account", "intent_modules",
                          "intent_llm_status", "intent_librarian_status",
                          "intent_api_keys",
                          "intent_magnify", "intent_simplify", "intent_solidify"):
                handler = getattr(self, intent, None)
                if handler:
                    handler(message)
                    return
            # Route interview-navigation intents
            if intent in ("intent_skip", "intent_back", "intent_review",
                          "intent_restart_interview", "intent_confirm"):
                handler = getattr(self, intent, None)
                if handler:
                    handler(message)
                    return
            # Otherwise advance the interview with the user's answer
            response = self.dialog.advance(message)
            self._write_murphy(response)
            self._update_sidebar_context()
            return

        # Check for feedback / frustration first
        if detect_feedback(message):
            self._handle_feedback(message)
            return

        intent = detect_intent(message)
        if intent:
            handler = getattr(self, intent, None)
            if handler:
                handler(message)
                return
        # Default: route through /api/chat (same as web UIs)
        self._send_chat(message)

    # -- feedback handling --

    def _handle_feedback(self, message: str) -> None:
        self.dialog.record_feedback(message)
        self._write_murphy(
            "[bold yellow]📝 Feedback received[/bold yellow] — thank you for letting me know.\n"
            f'[dim]You said: "{message}"[/dim]\n\n'
            "Here's what I can do right now:\n"
            "  • [green]help[/green] — context-aware assistance\n"
            "  • [green]start interview[/green] — guided onboarding walkthrough\n"
            "  • [green]status[/green] — check system connectivity\n\n"
            "If you're stuck, try describing what you'd like to accomplish "
            "and I'll do my best to guide you."
        )

    # -- intent handlers --

    def intent_health(self, _msg: str) -> None:
        try:
            data = self.client.health()
            self._write_murphy(
                f"System is [bold green]{data.get('status', 'unknown')}[/bold green] "
                f"(version {data.get('version', 'n/a')})"
            )
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch health: {self._friendly_error(exc)}[/red]")

    def intent_status(self, _msg: str) -> None:
        try:
            data = self.client.status()
            self._write_murphy("System status:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch status: {self._friendly_error(exc)}[/red]")

    def intent_info(self, _msg: str) -> None:
        try:
            data = self.client.info()
            self._write_murphy("System info:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch info: {self._friendly_error(exc)}[/red]")

    def intent_help(self, _msg: str) -> None:
        # Context-aware help
        if self.dialog.active:
            step = self.dialog.current_step
            step_label = step["label"] if step else "unknown"
            self._write_murphy(
                f"[bold cyan]Contextual help[/bold cyan] — you are on [bold]{self.dialog.progress_label}[/bold]\n\n"
                f"I'm asking about: [green]{step_label}[/green]\n"
                "You can:\n"
                "  • Type your answer naturally (e.g. 'all tiers', 'not sure')\n"
                "  • [green]skip[/green] — move to the next question\n"
                "  • [green]back[/green] — revisit the previous question\n"
                "  • [green]review[/green] — see what you've entered so far\n"
                "  • [green]restart[/green] — start the interview over\n"
            )
            return

        self._write_murphy(
            "I can help with the following:\n\n"
            "[bold cyan]System[/bold cyan]\n"
            "  • [green]health[/green] — check backend health\n"
            "  • [green]status[/green] — view system status\n"
            "  • [green]info[/green] — system version & information\n"
            "  • [green]links[/green] — show dashboard and UI URLs\n"
            "  • [green]ui[/green] — show user-type specific UI links\n"
            "  • [green]account[/green] — account lifecycle (signup → verify → session → automation)\n"
            "  • [green]llm status[/green] — check LLM provider configuration\n"
            "  • [green]librarian status[/green] — check librarian health\n\n"
            "[bold cyan]Onboarding & Interview[/bold cyan]\n"
            "  • [green]start interview[/green] — guided onboarding dialog\n"
            "  • [green]billing[/green] — view billing tiers & subscription\n\n"
            "[bold cyan]Modules & Execution[/bold cyan]\n"
            "  • [green]execute <task>[/green] — run a task\n"
            "  • [green]show modules[/green] — list all modules and commands\n"
            "  • [green]librarian[/green] — consult knowledge-base expert\n"
            "  • [green]api keys[/green] — get API signup links for integrations\n"
            "  • [green]set key <provider> <key>[/green] — set an API key inline (e.g. [green]set key deepinfra di_...[/green])\n"
            "  • [green]plan[/green] — two-plane planning & execution overview\n"
            "  • [green]pending / hitl[/green] — pending interventions\n"
            "  • [green]corrections[/green] — correction statistics\n\n"
            "[bold cyan]Document Block Commands[/bold cyan]\n"
            "  • [green]magnify <topic>[/green] — create a document from a topic and expand its depth\n"
            "  • [green]simplify[/green] — reduce complexity of the current document\n"
            "  • [green]solidify[/green] — lock document and generate execution tasks\n"
            "  Workflow: [green]magnify <goal>[/green] → [green]simplify[/green] → [green]solidify[/green] → [green]execute plan[/green]\n\n"
            "[bold cyan]Connection[/bold cyan]\n"
            "  • [green]set api <url>[/green] — change backend address\n"
            "  • [green]test connection[/green] — verify backend reachability\n"
            "  • [green]reconnect[/green] — retry backend connection\n\n"
            "[bold cyan]Clipboard[/bold cyan]\n"
            "  • [green]Ctrl+V[/green] — paste clipboard into input\n"
            "  • [green]Shift+Insert[/green] — paste (terminal fallback)\n"
            "  • Right-click paste may also work depending on your terminal\n"
            "  • For long API keys, you can also edit the [green].env[/green] file directly\n\n"
            "Or type any natural language message — Murphy will respond conversationally.\n"
            "  • [green]exit[/green] — quit the terminal"
        )

    def intent_exit(self, _msg: str) -> None:
        self._write_murphy("Goodbye! ☠")
        self.exit()

    def intent_corrections(self, _msg: str) -> None:
        try:
            data = self.client.corrections_stats()
            self._write_murphy("Correction statistics:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch corrections: {self._friendly_error(exc)}[/red]")

    def intent_hitl(self, _msg: str) -> None:
        try:
            data = self.client.hitl_pending()
            self._write_murphy("Pending interventions:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch HITL data: {self._friendly_error(exc)}[/red]")

    def intent_execute(self, msg: str) -> None:
        # Strip the trigger word and send the rest as task description
        task_desc = re.sub(r"^(execute|run task|launch)\s*", "", msg, flags=re.I).strip()
        if not task_desc:
            self._write_murphy(
                "What task would you like to execute? "
                "Please describe it, e.g. [green]execute onboarding for site foo[/green]"
            )
            return
        try:
            data = self.client.execute(task_description=task_desc)
            self._write_murphy("Task result:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Execution failed: {self._friendly_error(exc)}[/red]")

    # -- API key management --

    def intent_set_key(self, msg: str) -> None:
        """Handle ``set key <provider> [<value>]`` command."""
        rest = re.sub(r"^set[_ ]?key\s*", "", msg, flags=re.I).strip()
        parts = rest.split(None, 1)

        if not parts:
            supported = ", ".join(sorted(API_KEY_FORMATS.keys()))
            self._write_murphy(
                "[bold cyan]🔑 Set API Key[/bold cyan]\n\n"
                f"Usage: [green]set key <provider> <key>[/green]\n"
                f"Supported providers: [green]{supported}[/green]\n\n"
                "Examples:\n"
                "  [green]set key deepinfra di_abc123...[/green]\n"
                "  [green]set key openai sk-abc123...[/green]\n"
                "  [green]set key anthropic sk-ant-abc123...[/green]"
            )
            return

        provider = parts[0].lower()
        key_value = parts[1] if len(parts) > 1 else None

        if provider not in API_KEY_FORMATS:
            supported = ", ".join(sorted(API_KEY_FORMATS.keys()))
            self._write_murphy(
                f"[red]Unknown provider '{provider}'.[/red]\n"
                f"Supported: [green]{supported}[/green]"
            )
            return

        if not key_value:
            self._write_murphy(
                f"Please provide your {provider} API key.\n"
                f"Usage: [green]set key {provider} <your-key>[/green]"
            )
            return

        self._apply_api_key(provider, strip_key_wrapping(key_value))

    def _apply_api_key(self, provider: str, key_value: str) -> None:
        """Validate, persist, and hot-reload an API key."""
        key_value = strip_key_wrapping(key_value)
        valid, message = validate_api_key(provider, key_value)
        if not valid:
            self._write_murphy(f"[red]✗ {message}[/red]")
            return

        fmt = API_KEY_FORMATS[provider]
        env_var = fmt["env_var"]

        # Persist to .env (both the API key and the provider selection)
        env_path = get_env_path()
        write_env_key(env_path, env_var, key_value)
        write_env_key(env_path, "MURPHY_LLM_PROVIDER", provider)

        # Hot-reload into current process
        os.environ[env_var] = key_value
        os.environ["MURPHY_LLM_PROVIDER"] = provider
        reload_env(env_path)

        # Notify the backend to hot-reload its LLM config
        configure_result = self.client.configure_llm(provider, key_value)
        if not configure_result.get("success", False):
            self._write_murphy(
                f"[red]✗ Backend configure failed: {configure_result.get('error', 'unknown error')}[/red]"
            )
            return

        self._write_murphy(
            f"[bold green]✓ {provider.capitalize()} API key saved![/bold green]\n"
            f"  Env var : [green]{env_var}[/green]\n"
            f"  .env    : [dim]{env_path}[/dim]"
        )

        # Verify the key actually authenticates with the provider
        test_result = self.client.llm_test()
        if test_result.get("success"):
            self._write_murphy(
                "[bold green]✓ Key verified — LLM is active and responding.[/bold green]\n"
                "[dim]The key is active immediately — no restart needed.[/dim]"
            )
        else:
            err = test_result.get("error", "unknown error")
            self._write_murphy(
                f"[yellow]⚠ Key saved but authentication failed: {err}[/yellow]\n"
                "[dim]Please verify your key at "
                "[link=https://deepinfra.com]https://deepinfra.com[/link][/dim]"
            )

        # Refresh the StatusBar — only mark LLM On if the test passed
        self._check_llm_status()

    # -- clipboard support --

    @staticmethod
    def _read_clipboard() -> Optional[str]:
        """Try to read text from the system clipboard."""
        # Try pyperclip first
        if pyperclip is not None:
            try:
                return pyperclip.paste()
            except Exception:
                pass

        # Platform-specific fallbacks
        system = platform.system()
        try:
            if system == "Linux":
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    return result.stdout
            elif system == "Darwin":
                result = subprocess.run(
                    ["pbpaste"], capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    return result.stdout
            elif system == "Windows":
                # Prefer win32clipboard (pywin32) — fast, in-process, and
                # avoids the subprocess conflicts with Textual's Input widget.
                if _win32clipboard is not None:
                    try:
                        _win32clipboard.OpenClipboard()
                        try:
                            text = _win32clipboard.GetClipboardData(_win32clipboard.CF_UNICODETEXT)
                            return text
                        finally:
                            _win32clipboard.CloseClipboard()
                    except Exception:
                        pass
                # Fallback: PowerShell
                result = subprocess.run(
                    ["powershell", "-command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    return result.stdout
        except Exception:
            pass

        return None

    def _insert_text_into_input(self, text: str) -> None:
        """Insert *text* into the command Input widget, using only the first line.

        API keys and short commands are always single-line.  Silently ignores
        errors so that clipboard/paste failures never crash the app.
        Whitespace and newlines are stripped so pasted keys are clean.
        """
        first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
        if first_line:
            try:
                input_widget = self.query_one("#user-input", MurphyInput)
                input_widget.insert_text_at_cursor(first_line)
            except Exception:
                pass

    def action_paste_clipboard(self) -> None:
        """Paste clipboard contents into the focused Input widget."""
        text = self._read_clipboard()
        if text:
            self._insert_text_into_input(text)
        else:
            self._write_system(
                "Paste not available. Try: Shift+Insert, or right-click in your "
                "terminal. You can also set keys via .env file directly."
            )

    def key_ctrl_v(self, event: events.Key) -> None:
        """Intercept Ctrl+V at the app level so paste works even when the
        Input widget would otherwise swallow the key on Windows."""
        self.action_paste_clipboard()
        event.prevent_default()
        event.stop()

    def on_paste(self, event: events.Paste) -> None:
        """Handle terminal bracketed-paste events (e.g. right-click paste in Windows Terminal).

        Routes the pasted text into the command input widget so users can
        paste API keys directly without relying on the system clipboard API.
        """
        if event.text:
            self._insert_text_into_input(event.text)
            event.stop()

    def intent_paste(self, _msg: str) -> None:
        """Text command: typing 'paste' reads clipboard and inserts its content.

        This is a keyboard-independent fallback that works on any platform
        where clipboard APIs may not be accessible via Ctrl+V.
        """
        text = self._read_clipboard()
        if text:
            self._insert_text_into_input(text)
            self._write_system("Clipboard contents pasted into input.")
        else:
            self._write_system(
                "Clipboard is empty or unavailable. "
                "Try right-click → paste in your terminal emulator."
            )

    # -- connectivity intents --

    def intent_set_api(self, msg: str) -> None:
        new_url = re.sub(r"^set[_ ]?api\s*", "", msg, flags=re.I).strip()
        if not new_url:
            self._write_murphy(
                f"Current backend URL: [cyan]{self.client.base_url}[/cyan]\n"
                "Usage: [green]set api http://host:port[/green]"
            )
            return
        self.client.set_base_url(new_url)
        self._session_created = False
        self._update_status_url()
        self._write_system(f"Backend URL changed to [cyan]{self.client.base_url}[/cyan]")
        self._check_connection()

    def intent_test_api(self, _msg: str) -> None:
        self._write_system(f"Testing connection to [cyan]{self.client.base_url}[/cyan]…")
        ok, detail = self.client.test_connection()
        status_bar = self.query_one(StatusBar)
        if ok:
            status_bar.connected = True
            self._write_murphy(f"[green]✓ Connection OK:[/green] {detail}")
        else:
            status_bar.connected = False
            self._write_murphy(f"[red]✗ Connection failed:[/red] {detail}")

    def intent_reconnect(self, _msg: str) -> None:
        self._reconnect_attempts = 0
        self._write_system("Attempting reconnection…")
        self._check_connection()
        # Re-read .env on the backend so any manual edits take effect
        reload_result = self.client.llm_reload()
        if reload_result.get("success"):
            self._write_system("Backend .env reloaded.")
        self._check_llm_status()

    # -- interview intents --

    def intent_start_interview(self, _msg: str) -> None:
        prompt = self.dialog.start()
        self._write_murphy(prompt)
        self._update_sidebar_context()

    def intent_skip(self, _msg: str) -> None:
        if not self.dialog.active:
            self._write_murphy("No interview in progress. Type [green]start interview[/green] to begin.")
            return
        response = self.dialog.advance("skip")
        self._write_murphy(response)
        self._update_sidebar_context()

    def intent_back(self, _msg: str) -> None:
        if not self.dialog.active:
            self._write_murphy("No interview in progress.")
            return
        response = self.dialog._go_back()
        self._write_murphy(response)
        self._update_sidebar_context()

    def intent_review(self, _msg: str) -> None:
        if not self.dialog.active and not self.dialog.collected:
            self._write_murphy("No interview data collected yet. Type [green]start interview[/green] to begin.")
            return
        self._write_murphy(
            f"[bold cyan]Collected information:[/bold cyan]\n{self.dialog.summary()}"
        )

    def intent_restart_interview(self, _msg: str) -> None:
        prompt = self.dialog.start()
        self._write_murphy(f"[dim]Restarting interview…[/dim]\n{prompt}")
        self._update_sidebar_context()

    def intent_confirm(self, _msg: str) -> None:
        if self.dialog.active:
            response = self.dialog.advance("yes")
            self._write_murphy(response)
            self._update_sidebar_context()
            return
        if self.dialog.collected:
            self._write_murphy(
                "[bold green]✓ Confirmed![/bold green] Your onboarding data has been recorded.\n"
                f"{self.dialog.summary()}"
            )
        else:
            self._write_murphy("Nothing to confirm. Type [green]start interview[/green] to begin.")

    # -- module exposure intents --

    def intent_librarian(self, msg: str) -> None:
        # Strip the trigger word to extract the actual question
        question = re.sub(r"^(librarian|library|knowledge base)\s*", "", msg, flags=re.I).strip()
        if not question:
            question = "What can you help me with?"
        self._send_librarian(question)

    def intent_llm_status(self, _msg: str) -> None:
        try:
            data = self.client.llm_status()
            enabled = data.get("enabled", False)
            provider = data.get("provider") or "none"
            model = data.get("model") or "n/a"
            healthy = data.get("healthy", False)
            error = data.get("error", "")
            if enabled:
                self._write_murphy(
                    f"[bold cyan]🤖 LLM Status[/bold cyan]\n\n"
                    f"  Provider : [green]{provider}[/green]\n"
                    f"  Model    : [green]{model}[/green]\n"
                    f"  Healthy  : {'[green]yes[/green]' if healthy else '[red]no[/red]'}"
                )
            else:
                self._write_murphy(
                    f"[bold yellow]🤖 LLM Status — Not Configured[/bold yellow]\n\n"
                    f"  Error: {error}\n\n"
                    "To enable LLM, set your API key right here:\n"
                    "  [green]set key deepinfra di_your_key_here[/green]\n\n"
                    "Get a free key: [link=https://deepinfra.com]https://deepinfra.com[/link]"
                )
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch LLM status: {self._friendly_error(exc)}[/red]")

    def intent_librarian_status(self, _msg: str) -> None:
        try:
            data = self.client.librarian_status()
            enabled = data.get("enabled", False)
            healthy = data.get("healthy", False)
            self._write_murphy(
                f"[bold cyan]📚 Librarian Status[/bold cyan]\n\n"
                f"  Enabled : {'[green]yes[/green]' if enabled else '[yellow]no[/yellow]'}\n"
                f"  Healthy : {'[green]yes[/green]' if healthy else '[yellow]no[/yellow]'}"
            )
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch librarian status: {self._friendly_error(exc)}[/red]")

    def intent_modules(self, _msg: str) -> None:
        lines = ["[bold cyan]📦 Murphy System — Module ↔ Command Map[/bold cyan]\n"]
        for module, cmds in MODULE_COMMAND_MAP.items():
            cmd_list = ", ".join(f"[green]{c}[/green]" for c in cmds)
            lines.append(f"  [bold]{module}[/bold]: {cmd_list}")
        lines.append(f"\n[dim]Total: {len(MODULE_COMMAND_MAP)} modules mapped to front-end commands.[/dim]")
        self._write_murphy("\n".join(lines))

    def intent_billing(self, _msg: str) -> None:
        self._write_murphy(
            "[bold cyan]💳 Billing & Subscription[/bold cyan]\n\n"
            "Available tiers:\n"
            "  • [green]Community[/green]  — Free, core modules, community support\n"
            "  • [green]Solo[/green]       — $99/mo, 3 automations, email support\n"
            "  • [green]Business[/green]   — $299/mo, unlimited automations, 10 users, all integrations\n"
            "  • [green]Professional[/green] — $599/mo, unlimited users, HITL graduation, white-label\n"
            "  • [green]Enterprise[/green] — Contact us, custom SLA, dedicated onboarding, full API\n\n"
            "To check your current tier or manage billing, use:\n"
            "  [green]execute billing status[/green]"
        )

    def intent_links(self, _msg: str) -> None:
        base = self.client.base_url
        lines = ["[bold cyan]🔗 Murphy Dashboard & UI Links[/bold cyan]\n"]
        for link in DASHBOARD_LINKS:
            full_url = f"{base}{link['url']}"
            lines.append(f"  • {link['name']}: [link={full_url}]{full_url}[/link]")
        lines.append("\n[dim]Tip: Click any link to open in your browser.[/dim]")
        lines.append("[dim]Type [green]ui[/green] to see role-based UI links.[/dim]")
        self._write_murphy("\n".join(lines))

    def intent_ui(self, _msg: str) -> None:
        """Show direct links to HTML user interfaces grouped by user type."""
        base = self.client.base_url
        lines = ["[bold cyan]🖥️  User Interface Links by Role[/bold cyan]\n"]
        for role, ui_links in USER_TYPE_UI_LINKS.items():
            lines.append(f"  [bold yellow]{role.upper()}[/bold yellow]")
            for link in ui_links:
                full_url = f"{base}{link['url']}"
                lines.append(f"    • {link['name']}: [link={full_url}]{full_url}[/link]")
            lines.append("")
        lines.append(
            "[dim]Each role has access to UI pages matching their permission level.\n"
            "Contact your admin to change roles.[/dim]"
        )
        self._write_murphy("\n".join(lines))

    def intent_plan(self, _msg: str) -> None:
        self._write_murphy(
            "[bold cyan]📋 Two-Plane Execution: Planning & Execution[/bold cyan]\n\n"
            "Murphy uses a two-plane model:\n"
            "  [bold]Planning Plane[/bold]  — Librarian reviews context, generates plan\n"
            "  [bold]Execution Plane[/bold] — Domain gates execute approved steps\n\n"
            "Workflow:\n"
            "  1. Describe your goal → Murphy drafts a plan\n"
            "  2. Review the plan (HITL approval)\n"
            "  3. Execute — Murphy runs each step with safety checks\n\n"
            "Try: [green]execute plan for <your goal>[/green]"
        )

    def intent_account(self, _msg: str) -> None:
        """Show the account lifecycle flow: info → signup → verify → session → automation."""
        base = self.client.base_url
        lines = ["[bold cyan]🔐 Account Lifecycle Flow[/bold cyan]\n"]
        for i, stage in enumerate(ACCOUNT_LIFECYCLE_FLOW, 1):
            ui_url = f"{base}{stage['url']}"
            api_url = f"{base}{stage['api']}"
            lines.append(
                f"  [bold yellow]{i}. {stage['name']}[/bold yellow] ({stage['stage']})\n"
                f"     {stage['description']}\n"
                f"     UI:  [link={ui_url}]{ui_url}[/link]\n"
                f"     API: [link={api_url}]{api_url}[/link]"
            )
        lines.append(
            "\n[bold cyan]Flow:[/bold cyan] "
            "[green]Info[/green] → [green]Signup[/green] → "
            "[green]Verify[/green] → [green]Session[/green] → "
            "[green]Automation[/green]\n\n"
            "[dim]Start with [green]start interview[/green] to begin the signup process.[/dim]\n\n"
            "[bold cyan]Required env vars for OAuth signup:[/bold cyan]\n"
            "  [green]MURPHY_OAUTH_GOOGLE_CLIENT_ID[/green]=your-google-client-id\n"
            "  [green]MURPHY_OAUTH_GOOGLE_SECRET[/green]=your-google-secret\n"
            "  [green]MURPHY_OAUTH_MICROSOFT_CLIENT_ID[/green]=your-ms-client-id\n"
            "  [green]MURPHY_OAUTH_META_CLIENT_ID[/green]=your-meta-client-id\n"
            "  [green]MURPHY_OAUTH_REDIRECT_URI[/green]=http://localhost:8000/api/auth/callback\n\n"
            "  Get Google credentials: "
            "[link=https://console.cloud.google.com/apis/credentials]https://console.cloud.google.com/[/link]\n"
            "  Get Microsoft credentials: "
            "[link=https://entra.microsoft.com/]https://entra.microsoft.com/[/link]\n"
            "  Get Meta credentials: "
            "[link=https://developers.facebook.com/apps/]https://developers.facebook.com/apps/[/link]"
        )
        self._write_murphy("\n".join(lines))

    def intent_toggle_test_mode(self, _msg: str) -> None:
        """Toggle test mode on/off, showing current status and limits."""
        try:
            result = self.client._post("/api/test-mode/toggle", {})
            active = result.get("active", False)
            if active:
                calls_rem = result.get("calls_remaining", "?")
                secs_rem = result.get("seconds_remaining", "?")
                keys = result.get("keys_count", 0)
                self._write_murphy(
                    "[bold green]🧪 Test Mode: ENABLED[/bold green]\n"
                    f"   Call limit   : [cyan]{result.get('max_calls', '?')}[/cyan] "
                    f"([cyan]{calls_rem}[/cyan] remaining)\n"
                    f"   Time limit   : [cyan]{result.get('max_seconds', '?')}s[/cyan] "
                    f"([cyan]{secs_rem:.0f}s[/cyan] remaining)\n"
                    f"   Test keys    : [cyan]{keys}[/cyan] key(s) loaded\n\n"
                    "[dim]💡 Best free key provider:[/dim]\n"
                    "   [bold]DeepInfra[/bold] — Free tier, generous limits, fast inference\n"
                    "   Signup: [link=https://deepinfra.com]https://deepinfra.com[/link]\n"
                    "   Then: [green]set key deepinfra di_your_key[/green]\n\n"
                    "[dim]Session ends automatically when call or time limit is reached.\n"
                    "Run [green]test mode[/green] again to disable.[/dim]"
                )
            else:
                calls_used = result.get("calls_used", 0)
                self._write_murphy(
                    "[bold yellow]🧪 Test Mode: DISABLED[/bold yellow]\n"
                    f"   Calls used in last session: [cyan]{calls_used}[/cyan]\n\n"
                    "[dim]Run [green]test mode[/green] to start a new session.[/dim]"
                )
        except Exception as exc:
            self._write_murphy(f"[red]✗ test mode toggle error: {self._friendly_error(exc)}[/red]")

    def intent_toggle_self_learning(self, _msg: str) -> None:
        """Toggle self-learning on/off."""
        try:
            result = self.client._post("/api/learning/toggle", {})
            enabled = result.get("self_learning_enabled", False)
            skipped = result.get("skipped_operations", 0)
            if enabled:
                self._write_murphy(
                    "[bold green]🧠 Self-Learning: ENABLED[/bold green]\n"
                    "   Training data will now be collected and stored to disk.\n"
                    f"   Operations skipped (while disabled): [cyan]{skipped:,}[/cyan]\n\n"
                    "[dim]Run [green]self learn[/green] to disable and stop disk writes.[/dim]"
                )
            else:
                self._write_murphy(
                    "[bold yellow]🧠 Self-Learning: DISABLED[/bold yellow]\n"
                    f"   Traces skipped: [cyan]{skipped:,}[/cyan] (no disk writes)\n\n"
                    "[dim]Disk writes are avoided while learning is off.\n"
                    "Run [green]self learn[/green] to enable when storage is available.[/dim]"
                )
        except Exception as exc:
            self._write_murphy(f"[red]✗ self-learning toggle error: {self._friendly_error(exc)}[/red]")

    def intent_readiness_scan(self, _msg: str) -> None:
        """Run the recursive readiness scanner and display a formatted report."""
        self._write_murphy("[dim]🔍 Running readiness scan…[/dim]")
        try:
            result = self.client._get("/api/readiness")
            ready = result.get("ready", False)
            score = result.get("score", "?")
            passed = result.get("passed", [])
            blockers = result.get("blockers", [])
            warnings_list = result.get("warnings", [])

            header = (
                "[bold green]✅ READY FOR DEPLOYMENT[/bold green]"
                if ready
                else "[bold red]❌ NOT READY[/bold red]"
            )
            lines = [f"{header}  —  {score}\n"]

            if blockers:
                lines.append("[bold red]BLOCKERS (must fix):[/bold red]")
                for b in blockers:
                    fix = f"\n     Fix: [green]{b['fix']}[/green]" if b.get("fix") else ""
                    lines.append(f"  ✗ [red]{b['check']}[/red] — {b.get('detail', '')}{fix}")

            if warnings_list:
                lines.append("\n[bold yellow]WARNINGS:[/bold yellow]")
                for w in warnings_list:
                    lines.append(f"  ⚠ [yellow]{w['check']}[/yellow] — {w.get('detail', '')}")

            if passed:
                lines.append(f"\n[bold green]PASSED ({len(passed)}):[/bold green]")
                lines.append("  " + ", ".join(f"[green]{p}[/green]" for p in passed[:15]))
                if len(passed) > 15:
                    lines.append(f"  … and {len(passed) - 15} more")

            strategy = result.get("api_key_strategy", {})
            if strategy:
                lines.append("\n[bold cyan]💡 Best bang-for-buck API key strategy:[/bold cyan]")
                for p in strategy.get("providers", []):
                    lines.append(
                        f"  {p['rank']}. [bold]{p['name']}[/bold] — {p.get('models','')}\n"
                        f"     {p.get('note','')}\n"
                        f"     [link={p['url']}]{p['url']}[/link]"
                    )

            self._write_murphy("\n".join(lines))
        except Exception as exc:
            self._write_murphy(f"[red]✗ readiness scan error: {self._friendly_error(exc)}[/red]")

    def intent_api_keys(self, _msg: str) -> None:
        """Show API provider signup links for all supported integrations."""
        lines = ["[bold cyan]🔑 API Keys & Signup Links[/bold cyan]\n"]
        for key, info in API_PROVIDER_LINKS.items():
            lines.append(
                f"  • [bold]{info['name']}[/bold] — {info['description']}\n"
                f"    Signup: [link={info['url']}]{info['url']}[/link]\n"
                f"    Env var: [green]{info['env_var']}[/green]"
            )
        lines.append(
            "\n[bold cyan]Quick Start (LLM):[/bold cyan]\n"
            "  1. Get a free DeepInfra key: [link=https://deepinfra.com]https://deepinfra.com[/link]\n"
            "  2. Set it right here in the terminal:\n"
            "     [green]set key deepinfra di_your_key_here[/green]\n"
            "  That's it! No restart needed.\n\n"
            "[dim]Tip: Run [green]start interview[/green] and Murphy will recommend "
            "exactly which API keys you need based on your answers.[/dim]"
        )
        self._write_murphy("\n".join(lines))

    # -- document block-command intents --

    def _require_doc(self) -> Optional[str]:
        """Return current doc_id or show a prompt to create one first."""
        if self._current_doc_id:
            return self._current_doc_id
        self._write_murphy(
            "[yellow]No active document.[/yellow] "
            "Create one first:\n"
            "  [green]magnify <topic>[/green] — start from a topic\n"
            "  [green]magnify my sales automation plan[/green]"
        )
        return None

    def intent_magnify(self, msg: str) -> None:
        """Magnify: expand domain depth of the current document (or create one from the prompt)."""
        topic = re.sub(r"^magnify\s*", "", msg, flags=re.I).strip()
        if not topic and self._current_doc_id:
            # Re-magnify existing document with no domain override
            topic = "general"
        if not topic:
            self._write_murphy(
                "Usage: [green]magnify <topic or goal>[/green]\n"
                "Example: [green]magnify automate our customer onboarding workflow[/green]"
            )
            return
        try:
            if not self._current_doc_id:
                # Create a new document from the topic, then magnify it
                doc_data = self.client.create_document(
                    title=topic[:80],
                    content=topic,
                    doc_type="plan",
                )
                if not doc_data.get("success"):
                    self._write_murphy(
                        f"[red]✗ Could not create document: {doc_data.get('error', 'unknown')}[/red]"
                    )
                    return
                self._current_doc_id = doc_data["doc_id"]
            result = self.client.magnify_document(self._current_doc_id, domain=topic[:40])
            conf = result.get("confidence", 0)
            depth = result.get("domain_depth", 0)
            self._write_murphy(
                f"[bold cyan]🔍 Magnified[/bold cyan] — doc [dim]{self._current_doc_id}[/dim]\n"
                f"  Confidence  : [cyan]{conf:.0%}[/cyan]\n"
                f"  Domain depth: [cyan]{depth}[/cyan]\n\n"
                "Run [green]simplify[/green] to reduce complexity, or "
                "[green]solidify[/green] to lock and generate tasks."
            )
        except Exception as exc:
            self._write_murphy(f"[red]✗ magnify error: {self._friendly_error(exc)}[/red]")

    def intent_simplify(self, msg: str) -> None:
        """Simplify: reduce complexity of the current document."""
        doc_id = self._require_doc()
        if not doc_id:
            return
        try:
            result = self.client.simplify_document(doc_id)
            conf = result.get("confidence", 0)
            depth = result.get("domain_depth", 0)
            self._write_murphy(
                f"[bold cyan]✂ Simplified[/bold cyan] — doc [dim]{doc_id}[/dim]\n"
                f"  Confidence  : [cyan]{conf:.0%}[/cyan]\n"
                f"  Domain depth: [cyan]{depth}[/cyan]\n\n"
                "Run [green]solidify[/green] to lock and generate tasks, or "
                "[green]magnify <topic>[/green] to expand again."
            )
        except Exception as exc:
            self._write_murphy(f"[red]✗ simplify error: {self._friendly_error(exc)}[/red]")

    def intent_solidify(self, msg: str) -> None:
        """Solidify: lock the current document and trigger swarm task generation."""
        doc_id = self._require_doc()
        if not doc_id:
            return
        try:
            result = self.client.solidify_document(doc_id)
            conf = result.get("confidence", 0)
            state = result.get("state", "SOLIDIFIED")
            tasks = result.get("generated_tasks", [])
            tasks_text = ""
            if tasks:
                task_lines = "\n".join(
                    f"  {i+1}. {t.get('description', t)}"
                    for i, t in enumerate(tasks[:10])
                )
                tasks_text = f"\n\n[bold]Generated tasks:[/bold]\n{task_lines}"
            self._write_murphy(
                f"[bold green]🔒 Solidified[/bold green] — doc [dim]{doc_id}[/dim] → state=[cyan]{state}[/cyan]\n"
                f"  Confidence: [cyan]{conf:.0%}[/cyan]"
                f"{tasks_text}"
                "\n\n[dim]Document is locked. Run [green]execute plan[/green] to start execution.[/dim]"
            )
            # Clear current doc so next magnify starts fresh
            self._current_doc_id = None
        except Exception as exc:
            self._write_murphy(f"[red]✗ solidify error: {self._friendly_error(exc)}[/red]")

    # -- chat fallback --

    @staticmethod
    def _extract_response(data: dict) -> str:
        """Extract the display-ready response text from an API result."""
        return str(
            data.get("reply_text")
            or data.get("response")
            or data.get("message")
            or json.dumps(data, indent=2, default=str)
        )

    def _send_librarian(self, message: str) -> None:
        """Route a message through the Librarian + LLM endpoint."""
        try:
            data = self.client.librarian_ask(message)
            mode = data.get("mode", "unknown")
            if mode == "llm_error":
                err_msg = data.get("llm_error", "unknown error")
                self._write_murphy(
                    f"[yellow]⚠ LLM call failed: {err_msg}[/yellow]\n"
                    "[dim]Your API key may be invalid. "
                    "Get a new key at [link=https://deepinfra.com]https://deepinfra.com[/link] "
                    "then run [green]set key deepinfra <your-key>[/green][/dim]"
                )
                return
            text = self._extract_response(data)
            suggested = data.get("suggested_commands", [])
            if suggested:
                text += "\n\n[dim]Suggested: " + ", ".join(f"[green]{c}[/green]" for c in suggested) + "[/dim]"
            if mode == "deterministic":
                text += "\n[dim](deterministic mode — type [green]set key deepinfra <your-key>[/green] to enable LLM)[/dim]"
            self._write_murphy(text)
        except Exception:
            # Fall back to /api/chat if /api/librarian/ask is unavailable
            self._send_chat(message)

    def _send_chat(self, message: str) -> None:
        try:
            data = self.client.chat(message)
            self._write_murphy(self._extract_response(data))
        except Exception as exc:
            self._write_murphy(
                f"[red]Chat error: {self._friendly_error(exc)}[/red]\n"
                "[dim]Tip: Is Murphy backend running? "
                f"Expected at {self.client.base_url}[/dim]"
            )

    # -- key bindings --

    def action_show_help(self) -> None:
        self.intent_help("")

    def action_show_status(self) -> None:
        self.intent_status("")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main():
    url = os.environ.get("MURPHY_API_URL", DEFAULT_API_URL)
    app = MurphyTerminalApp(api_url=url)
    app.run()


if __name__ == "__main__":
    main()

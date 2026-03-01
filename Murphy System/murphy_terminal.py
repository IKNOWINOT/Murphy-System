#!/usr/bin/env python3
"""
Murphy System — Interactive Natural Language Terminal UI

A conversational TUI (Terminal User Interface) for interacting with
Murphy System via natural language.  Start with:

    python murphy_terminal.py

Connects to the Murphy backend API at http://localhost:8000 (configurable
via MURPHY_API_URL environment variable).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: Apache License 2.0
"""

from __future__ import annotations

import os
import sys
import uuid
import json
import re
from datetime import datetime
from typing import Optional

import requests
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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
    "api_setup": ["api keys", "get api keys"],
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
    "groq": {
        "name": "Groq",
        "url": "https://console.groq.com/keys",
        "env_var": "GROQ_API_KEY",
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

    def librarian_status(self) -> dict:
        return self._get("/api/librarian/status")


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
            for svc_key, info in recs.items():
                msg += (
                    f"  • [bold]{info['name']}[/bold] — {info['description']}\n"
                    f"    Get your key: [link={info['url']}]{info['url']}[/link]\n"
                    f"    Set: [green]{info['env_var']}[/green]\n"
                )
            msg += "\n"
        msg += (
            "Type [green]confirm[/green] to proceed, [green]edit[/green] to change answers, "
            "or [green]restart[/green] to start over.\n"
            "Type [green]api keys[/green] to see all available API signup links."
        )
        return msg

    def _infer_integrations(self) -> dict[str, dict[str, str]]:
        """Analyze collected answers and return matching API_PROVIDER_LINKS entries."""
        combined = " ".join(str(v) for v in self.collected.values()).lower()
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
        }
        matched: dict[str, dict[str, str]] = {}
        for keyword, provider_keys in keyword_map.items():
            if keyword in combined:
                for pk in provider_keys:
                    if pk not in matched and pk in API_PROVIDER_LINKS:
                        matched[pk] = API_PROVIDER_LINKS[pk]
        # Always recommend LLM if not configured
        if "groq" not in matched:
            llm_provider = os.environ.get("MURPHY_LLM_PROVIDER", "").strip()
            if not llm_provider:
                matched["groq"] = API_PROVIDER_LINKS["groq"]
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
    (re.compile(r"\b(links|urls|dashboards|open ui)\b", re.I), "intent_links"),
    (re.compile(r"\b(plan|planning|two.?plane|execution plan)\b", re.I), "intent_plan"),
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
║              💀  Murphy System Terminal  💀                  ║
║                  Natural Language Interface                   ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]

[bold]Hello! I'm Murphy — your professional automation assistant.[/bold]
I help teams automate operations, onboard new users, manage integrations,
and run end-to-end workflows with minimal manual effort.

[bold cyan]🚀 Getting Started[/bold cyan]
  • [green]start interview[/green]  — guided onboarding (I'll learn about your needs first)
  • [green]help[/green]             — see all available commands
  • [green]show modules[/green]    — list all system modules and their commands

[bold cyan]📡 Quick Commands[/bold cyan]
  • [green]health[/green] / [green]status[/green]  — check system health
  • [green]execute <task>[/green]   — run a task or workflow
  • [green]librarian[/green]       — consult the knowledge base expert
  • [green]billing[/green]         — view billing and subscription info
  • [green]links[/green]           — show dashboard and UI links

[bold cyan]🔗 Dashboard Links[/bold cyan]
  • Swagger API Docs : [link=http://localhost:8000/docs]http://localhost:8000/docs[/link]
  • System Dashboard : [link=http://localhost:8000/api/status]http://localhost:8000/api/status[/link]
  • Onboarding UI    : [link=http://localhost:8000/onboarding]http://localhost:8000/onboarding[/link]
  • Terminal (Web)   : [link=http://localhost:8000/terminal]http://localhost:8000/terminal[/link]

[dim]Type any question in natural language — Murphy will respond conversationally.[/dim]
"""

DASHBOARD_LINKS: list[dict[str, str]] = [
    {"name": "Swagger API Docs", "url": "/docs"},
    {"name": "System Dashboard", "url": "/api/status"},
    {"name": "Onboarding UI", "url": "/onboarding"},
    {"name": "Terminal (Web)", "url": "/terminal"},
    {"name": "Health Check", "url": "/api/health"},
]


class StatusBar(Static):
    """Top-right status indicator."""

    connected = reactive(False)
    api_url = reactive("")
    llm_enabled = reactive(False)

    def render(self) -> str:
        llm = "[green]LLM: On[/green]" if self.llm_enabled else "[yellow]LLM: Off[/yellow]"
        if self.connected:
            return f"[bold green]● Connected[/bold green]  {llm}"
        return f"[bold red]● Disconnected[/bold red]  {llm}"


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
        width: 30;
        border: solid $accent;
        padding: 1;
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
    ]

    def __init__(self, api_url: str = API_URL, **kwargs):
        super().__init__(**kwargs)
        self.client = MurphyAPIClient(base_url=api_url)
        self._session_created = False
        self.dialog = DialogContext()
        self._reconnect_attempts = 0
        self._reconnect_timer = None

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
                    "[dim]Ctrl+Q[/dim] Quit\n\n"
                    "[bold cyan]Quick Commands[/bold cyan]\n\n"
                    "[dim]health[/dim]\n"
                    "[dim]status[/dim]\n"
                    "[dim]start interview[/dim]\n"
                    "[dim]show modules[/dim]\n"
                    "[dim]librarian[/dim]\n"
                    "[dim]api keys[/dim]\n"
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
        yield Input(placeholder="Type a message…", id="user-input")
        yield Footer()

    # -- lifecycle --

    def on_mount(self) -> None:
        chat = self.query_one("#chat-log", RichLog)
        chat.write(WELCOME_TEXT)
        self._update_status_url()
        self._check_connection()

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
        """Query backend LLM status and update the status bar."""
        status_bar = self.query_one(StatusBar)
        try:
            data = self.client.llm_status()
            enabled = data.get("enabled", False)
            status_bar.llm_enabled = enabled
            provider = data.get("provider") or "none"
            if enabled:
                model = data.get("model") or "default"
                self._write_system(f"LLM enabled — provider=[cyan]{provider}[/cyan] model=[cyan]{model}[/cyan]")
            else:
                error = data.get("error", "not configured")
                self._write_system(
                    f"[yellow]LLM not configured ({error})[/yellow] — "
                    "running in deterministic mode. "
                    "Set MURPHY_LLM_PROVIDER and API keys to enable."
                )
        except Exception:
            status_bar.llm_enabled = False

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
                "[dim]Ctrl+Q[/dim] Quit\n\n"
                "[bold cyan]Quick Commands[/bold cyan]\n\n"
                "[dim]health[/dim]\n"
                "[dim]status[/dim]\n"
                "[dim]start interview[/dim]\n"
                "[dim]show modules[/dim]\n"
                "[dim]librarian[/dim]\n"
                "[dim]api keys[/dim]\n"
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
        # If an interview is active, route most input through dialog context
        if self.dialog.active:
            # Allow certain intents even during interview
            intent = detect_intent(message)
            if intent in ("intent_help", "intent_exit", "intent_health",
                          "intent_status", "intent_set_api", "intent_test_api",
                          "intent_reconnect", "intent_links", "intent_modules",
                          "intent_llm_status", "intent_librarian_status",
                          "intent_api_keys"):
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
        # Default: route through Librarian + LLM
        self._send_librarian(message)

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
            "  • [green]plan[/green] — two-plane planning & execution overview\n"
            "  • [green]pending / hitl[/green] — pending interventions\n"
            "  • [green]corrections[/green] — correction statistics\n\n"
            "[bold cyan]Connection[/bold cyan]\n"
            "  • [green]set api <url>[/green] — change backend address\n"
            "  • [green]test connection[/green] — verify backend reachability\n"
            "  • [green]reconnect[/green] — retry backend connection\n\n"
            "Or type any natural language message — Murphy will respond conversationally.\n"
            "  • [green]exit[/green] — quit the terminal"
        )

    def intent_exit(self, _msg: str) -> None:
        self._write_murphy("Goodbye! 💀")
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
                    "To enable LLM, set these environment variables:\n"
                    "  [green]MURPHY_LLM_PROVIDER[/green] = groq\n"
                    "  [green]GROQ_API_KEY[/green] = <your key>\n"
                    "  [green]MURPHY_LLM_MODEL[/green] = llama3-8b-8192  (optional)"
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
            "  • [green]Free[/green]       — basic automation, community support\n"
            "  • [green]Starter[/green]    — 5 modules, email support\n"
            "  • [green]Pro[/green]        — all modules, priority support, HITL\n"
            "  • [green]Enterprise[/green] — custom SLA, dedicated onboarding, full API\n\n"
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
            "  1. Get a free Groq key: [link=https://console.groq.com/keys]https://console.groq.com/keys[/link]\n"
            "  2. Set environment variables:\n"
            "     [green]export MURPHY_LLM_PROVIDER=groq[/green]\n"
            "     [green]export GROQ_API_KEY=gsk_your_key_here[/green]\n"
            "  3. Restart Murphy\n\n"
            "[dim]Tip: Run [green]start interview[/green] and Murphy will recommend "
            "exactly which API keys you need based on your answers.[/dim]"
        )
        self._write_murphy("\n".join(lines))

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
            text = self._extract_response(data)
            mode = data.get("mode", "unknown")
            suggested = data.get("suggested_commands", [])
            if suggested:
                text += "\n\n[dim]Suggested: " + ", ".join(f"[green]{c}[/green]" for c in suggested) + "[/dim]"
            if mode == "deterministic":
                text += "\n[dim](deterministic mode — set MURPHY_LLM_PROVIDER to enable LLM)[/dim]"
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

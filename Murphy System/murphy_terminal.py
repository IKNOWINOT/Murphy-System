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

# ---------------------------------------------------------------------------
# Backend API client
# ---------------------------------------------------------------------------


class MurphyAPIClient:
    """Thin wrapper around the Murphy System REST API."""

    def __init__(self, base_url: str = API_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None

    # -- helpers --

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _get(self, path: str) -> dict:
        resp = requests.get(self._url(path), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> dict:
        resp = requests.post(
            self._url(path), json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

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


# ---------------------------------------------------------------------------
# Intent detection — local keyword / regex based (no external model needed)
# ---------------------------------------------------------------------------

# Mapping of intent keywords → handler method names on the app.
INTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(health|alive|ping)\b", re.I), "intent_health"),
    (re.compile(r"\b(status|state|dashboard)\b", re.I), "intent_status"),
    (re.compile(r"\b(info|about|version)\b", re.I), "intent_info"),
    (re.compile(r"\b(help|commands|what can)\b", re.I), "intent_help"),
    (re.compile(r"\b(exit|quit|bye|close)\b", re.I), "intent_exit"),
    (re.compile(r"\b(corrections?|correction stats)\b", re.I), "intent_corrections"),
    (re.compile(r"\b(pending|interventions?|hitl)\b", re.I), "intent_hitl"),
    (re.compile(r"\b(execute|run task|launch)\b", re.I), "intent_execute"),
]


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

[dim]Type a message to interact with Murphy.  Examples:[/dim]
  • [green]show health status[/green]
  • [green]show system status[/green]
  • [green]show system info[/green]
  • [green]execute onboarding for site foo[/green]
  • [green]show pending interventions[/green]
  • [green]help[/green]  /  [green]exit[/green]

[dim]Or type any question — Murphy will respond via natural language chat.[/dim]
"""


class StatusBar(Static):
    """Top-right status indicator."""

    connected = reactive(False)

    def render(self) -> str:
        if self.connected:
            return "[bold green]● Connected[/bold green]"
        return "[bold red]● Disconnected[/bold red]"


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
                    "[dim]info[/dim]\n"
                    "[dim]help[/dim]\n"
                    "[dim]exit[/dim]\n"
                )
        yield Input(placeholder="Type a message…", id="user-input")
        yield Footer()

    # -- lifecycle --

    def on_mount(self) -> None:
        chat = self.query_one("#chat-log", RichLog)
        chat.write(WELCOME_TEXT)
        self._check_connection()

    # -- connection --

    def _check_connection(self) -> None:
        status_bar = self.query_one(StatusBar)
        try:
            self.client.health()
            status_bar.connected = True
            self._write_system("Connected to Murphy backend.")
            self._ensure_session()
        except Exception:
            status_bar.connected = False
            self._write_system(
                "[yellow]⚠ Cannot reach Murphy backend at "
                f"{self.client.base_url}. "
                "Messages will be sent when connection is available.[/yellow]"
            )

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

    # -- helpers --

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

    # -- input handling --

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        event.input.value = ""
        self._write_user(message)
        self._process_message(message)

    def _process_message(self, message: str) -> None:
        intent = detect_intent(message)
        if intent:
            handler = getattr(self, intent, None)
            if handler:
                handler(message)
                return
        # Default: send as chat to backend
        self._send_chat(message)

    # -- intent handlers --

    def intent_health(self, _msg: str) -> None:
        try:
            data = self.client.health()
            self._write_murphy(
                f"System is [bold green]{data.get('status', 'unknown')}[/bold green] "
                f"(version {data.get('version', 'n/a')})"
            )
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch health: {exc}[/red]")

    def intent_status(self, _msg: str) -> None:
        try:
            data = self.client.status()
            self._write_murphy("System status:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch status: {exc}[/red]")

    def intent_info(self, _msg: str) -> None:
        try:
            data = self.client.info()
            self._write_murphy("System info:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch info: {exc}[/red]")

    def intent_help(self, _msg: str) -> None:
        self._write_murphy(
            "I can help with the following:\n"
            "  • [green]health[/green] — check backend health\n"
            "  • [green]status[/green] — view system status\n"
            "  • [green]info[/green] — system version & information\n"
            "  • [green]execute <task>[/green] — run a task\n"
            "  • [green]pending / hitl[/green] — pending interventions\n"
            "  • [green]corrections[/green] — correction statistics\n"
            "  • Or type any natural language message for chat\n"
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
            self._write_murphy(f"[red]Could not fetch corrections: {exc}[/red]")

    def intent_hitl(self, _msg: str) -> None:
        try:
            data = self.client.hitl_pending()
            self._write_murphy("Pending interventions:\n" + self._format_json(data))
        except Exception as exc:
            self._write_murphy(f"[red]Could not fetch HITL data: {exc}[/red]")

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
            self._write_murphy(f"[red]Execution failed: {exc}[/red]")

    # -- chat fallback --

    def _send_chat(self, message: str) -> None:
        try:
            data = self.client.chat(message)
            response = data.get("response") or data.get("message") or self._format_json(data)
            self._write_murphy(str(response))
        except Exception as exc:
            self._write_murphy(
                f"[red]Chat error: {exc}[/red]\n"
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

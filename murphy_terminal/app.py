"""
Murphy Terminal — Main Application

Textual-based TUI application for Murphy System interaction.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import os
import sys

# Add parent directory to path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Header, RichLog

from murphy_terminal.api_client import MurphyAPIClient
from murphy_terminal.dialog import DialogContext, detect_intent, detect_feedback
from murphy_terminal.widgets import StatusBar, MurphyInput
from murphy_terminal.config import API_URL, MODULE_COMMAND_MAP, API_PROVIDER_LINKS


class MurphyTerminalApp(App):
    """Murphy System Interactive Terminal Application."""

    TITLE = "Murphy Terminal"
    SUB_TITLE = "Natural Language System Interface"
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #status-bar {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    
    #chat-log {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    
    #input-area {
        height: 3;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+r", "reconnect", "Reconnect"),
        Binding("f1", "help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.api = MurphyAPIClient(base_url=API_URL)
        self.dialog = DialogContext()
        self.connected = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(api_url=API_URL, id="status-bar")
        with VerticalScroll(id="chat-container"):
            yield RichLog(id="chat-log", highlight=True, markup=True)
        yield MurphyInput(id="input", placeholder="Type a command or ask Murphy...")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on app mount."""
        self.log_message("Welcome to Murphy Terminal!", style="bold green")
        self.log_message("Type 'help' for available commands.", style="dim")
        self.log_message("")
        
        # Test connection
        await self.action_reconnect()

    def log_message(self, message: str, style: str = "") -> None:
        """Log a message to the chat area."""
        chat_log = self.query_one("#chat-log", RichLog)
        if style:
            chat_log.write(f"[{style}]{message}[/{style}]")
        else:
            chat_log.write(message)

    async def on_input_submitted(self, event) -> None:
        """Handle input submission."""
        message = event.value.strip()
        if not message:
            return

        input_widget = self.query_one("#input", MurphyInput)
        input_widget.add_to_history(message)
        input_widget.clear_input()

        self.log_message(f"[bold cyan]You:[/bold cyan] {message}")

        # Process the command
        await self.process_command(message)

    async def process_command(self, message: str) -> None:
        """Process user command or message."""
        message_lower = message.lower().strip()

        # Check if in interview mode
        if self.dialog.is_in_interview():
            response = self.dialog.process_response(message)
            self.log_message(f"[bold green]Murphy:[/bold green] {response}")
            return

        # Built-in commands
        if message_lower in ("help", "?", "commands"):
            self.show_help()
            return

        if message_lower in ("quit", "exit", "bye"):
            self.exit()
            return

        if message_lower == "clear":
            await self.action_clear()
            return

        if message_lower in ("status", "dashboard"):
            await self.show_status()
            return

        if message_lower in ("health", "ping"):
            await self.check_health()
            return

        if message_lower in ("start interview", "onboard", "setup", "begin"):
            response = self.dialog.start_interview()
            self.log_message(f"[bold green]Murphy:[/bold green] {response}")
            return

        if message_lower in ("api keys", "keys", "show keys"):
            self.show_api_keys()
            return

        # Detect intent
        intent = detect_intent(message)
        if intent:
            await self.handle_intent(intent, message)
            return

        # Default: send to chat API
        await self.send_chat(message)

    async def handle_intent(self, intent: str, message: str) -> None:
        """Handle detected intent."""
        if intent == "intent_status":
            await self.show_status()
        elif intent == "intent_help":
            self.show_help()
        elif intent == "intent_api_keys":
            self.show_api_keys()
        elif intent == "intent_health":
            await self.check_health()
        elif intent == "intent_onboarding":
            response = self.dialog.start_interview()
            self.log_message(f"[bold green]Murphy:[/bold green] {response}")
        else:
            await self.send_chat(message)

    async def send_chat(self, message: str) -> None:
        """Send message to Murphy chat API."""
        if not self.connected:
            self.log_message("[bold red]Not connected.[/bold red] Use Ctrl+R to reconnect.")
            return

        try:
            result = self.api.chat(message)
            response = result.get("response", result.get("message", str(result)))
            self.log_message(f"[bold green]Murphy:[/bold green] {response}")
        except Exception as exc:
            self.log_message(f"[bold red]Error:[/bold red] {exc}")

    async def show_status(self) -> None:
        """Show system status."""
        try:
            result = self.api.status()
            self.log_message("[bold]System Status:[/bold]")
            for key, value in result.items():
                self.log_message(f"  {key}: {value}")
        except Exception as exc:
            self.log_message(f"[bold red]Error getting status:[/bold red] {exc}")

    async def check_health(self) -> None:
        """Check backend health."""
        ok, msg = self.api.test_connection()
        if ok:
            self.log_message(f"[bold green]✓ {msg}[/bold green]")
        else:
            self.log_message(f"[bold red]✗ {msg}[/bold red]")

    def show_help(self) -> None:
        """Display help message."""
        help_text = """
[bold]Murphy Terminal Commands[/bold]

[cyan]Basic Commands:[/cyan]
  help, ?          Show this help
  status           Show system status
  health, ping     Check backend health
  clear            Clear the screen
  quit, exit       Exit terminal

[cyan]Interview & Setup:[/cyan]
  start interview  Begin onboarding interview
  api keys         Show API key configuration

[cyan]Modules:[/cyan]
"""
        self.log_message(help_text)
        for module, commands in MODULE_COMMAND_MAP.items():
            self.log_message(f"  {module}: {', '.join(commands)}")

    def show_api_keys(self) -> None:
        """Show API key configuration help."""
        self.log_message("[bold]API Key Configuration[/bold]\n")
        for key, info in API_PROVIDER_LINKS.items():
            self.log_message(f"[cyan]{info['name']}[/cyan]")
            self.log_message(f"  URL: {info['url']}")
            self.log_message(f"  Env: {info['env_var']}")
            self.log_message(f"  {info['description']}\n")

    async def action_clear(self) -> None:
        """Clear the chat log."""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()

    async def action_reconnect(self) -> None:
        """Attempt to reconnect to backend."""
        self.log_message("Connecting to Murphy backend...", style="dim")
        ok, msg = self.api.test_connection()
        
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.set_connected(ok)
        self.connected = ok

        if ok:
            self.log_message(f"[bold green]✓ Connected:[/bold green] {msg}")
            # Create session
            try:
                result = self.api.create_session("terminal")
                session_id = result.get("session_id", "")
                if session_id:
                    status_bar.set_session_id(session_id)
                    self.log_message(f"Session created: {session_id[:8]}...")
            except Exception:
                pass
        else:
            self.log_message(f"[bold red]✗ Connection failed:[/bold red] {msg}")

    def action_help(self) -> None:
        """Show help."""
        self.show_help()


def main() -> None:
    """Main entry point."""
    app = MurphyTerminalApp()
    app.run()


if __name__ == "__main__":
    main()

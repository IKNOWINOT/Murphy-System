"""
Murphy Terminal — Custom Widgets

StatusBar and MurphyInput widgets for the terminal UI.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

from textual.widgets import Static, Input


class StatusBar(Static):
    """Status bar widget showing connection and session state."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        connected: bool = False,
        session_id: str = "",
    ) -> None:
        super().__init__()
        self.api_url = api_url
        self.connected = connected
        self.session_id = session_id
        self._update_display()

    def _update_display(self) -> None:
        conn_status = "🟢 Connected" if self.connected else "🔴 Disconnected"
        session_info = f" | Session: {self.session_id[:8]}..." if self.session_id else ""
        self.update(f"{conn_status} | {self.api_url}{session_info}")

    def set_connected(self, connected: bool) -> None:
        self.connected = connected
        self._update_display()

    def set_session_id(self, session_id: str) -> None:
        self.session_id = session_id
        self._update_display()

    def set_api_url(self, api_url: str) -> None:
        self.api_url = api_url
        self._update_display()


class MurphyInput(Input):
    """Custom input widget with Murphy-specific behavior."""

    def __init__(
        self,
        placeholder: str = "Type a command or ask Murphy...",
        **kwargs
    ) -> None:
        super().__init__(placeholder=placeholder, **kwargs)
        self.history: list[str] = []
        self.history_index: int = -1

    def on_key(self, event) -> None:
        """Handle up/down arrow for history navigation."""
        if event.key == "up":
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.value = self.history[-(self.history_index + 1)]
            event.prevent_default()
        elif event.key == "down":
            if self.history_index > 0:
                self.history_index -= 1
                self.value = self.history[-(self.history_index + 1)]
            elif self.history_index == 0:
                self.history_index = -1
                self.value = ""
            event.prevent_default()

    def add_to_history(self, command: str) -> None:
        """Add a command to history."""
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.history_index = -1

    def clear_input(self) -> None:
        """Clear the input field and reset history index."""
        self.value = ""
        self.history_index = -1

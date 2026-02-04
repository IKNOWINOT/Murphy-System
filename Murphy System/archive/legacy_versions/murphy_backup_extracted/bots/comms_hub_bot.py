"""Vanta-governed communication hub consolidating user interfaces."""
from __future__ import annotations

from typing import Optional
import asyncio

from .matrix_client import MatrixClient
from .dashboard import run_dashboard as launch_dashboard
from .rest_api import run_api as launch_rest_api, register_bot
from .interactive_shell import BotShell


class CommsHubBot:
    """🗣 Governed by Vanta. Unified control over all I/O channels."""

    def __init__(self, homeserver: str = "http://localhost:8008", user: str = "@bot:localhost", password: str = "botpass") -> None:
        self.homeserver = homeserver
        self.user = user
        self.password = password
        self.matrix_client = MatrixClient(homeserver, user, password)

    async def start_matrix(self) -> None:
        await self.matrix_client.login()
        await self.matrix_client.client.sync_forever(timeout=30000)

    async def send_matrix_message(self, room: str, message: str, attachment: Optional[str] = None) -> None:
        await self.matrix_client.send_message(room, message)
        if attachment:
            await self.matrix_client.send_message(room, attachment)

    def start_dashboard(self, port: int = 8000) -> None:
        launch_dashboard(port=port)

    def start_rest_api(self, port: int = 8080) -> None:
        launch_rest_api(port=port)

    def start_shell(self) -> None:
        shell = BotShell()
        shell.cmdloop()

    def get_cognitive_signature(self) -> dict:
        return {
            "kiren": 0.10,
            "veritas": 0.10,
            "vallon": 0.10,
            "vanta": 0.70,
        }

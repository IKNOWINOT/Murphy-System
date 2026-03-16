"""Matrix chatbot interface (simplified)."""
from __future__ import annotations

import asyncio
from typing import Optional

from .matrix_client import MatrixClient

try:
    from nio import AsyncClient
except Exception:  # pragma: no cover
    AsyncClient = None  # type: ignore


class MatrixChatBot:
    """High level chatbot interface using :class:`MatrixClient`."""

    def __init__(self, homeserver: str, user: str, password: str) -> None:
        self.client = MatrixClient(homeserver, user, password)

    async def login(self) -> None:
        await self.client.login()

    async def send_message(self, room: str, message: str, attachment: Optional[str] = None) -> None:
        await self.client.send_message(room, message)
        if attachment:
            await self.client.send_message(room, attachment)

    async def listen(self) -> None:
        await self.client.client.sync_forever(timeout=30000)

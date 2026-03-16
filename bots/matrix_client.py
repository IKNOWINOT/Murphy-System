"""Persistent Matrix client leveraging matrix-nio."""
from __future__ import annotations

from typing import List, Optional
import base64
import json

from .crypto_utils import (
    encrypt_payload,
    decrypt_payload,
    sign_message,
    verify_signature,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .memory_manager_bot import MemoryManagerBot

try:
    from nio import AsyncClient
except Exception:  # pragma: no cover - optional dependency
    AsyncClient = None  # type: ignore


class MatrixClient:
    """Wrapper around :class:`AsyncClient` with optional encryption and signing."""

    def __init__(
        self,
        homeserver: str,
        user: str,
        password: str,
        *,
        enc_key: Optional[bytes] = None,
        signing_key: Optional[Ed25519PrivateKey] = None,
        verify_key: Optional[Ed25519PublicKey] = None,
    ) -> None:
        if AsyncClient is None:
            raise ImportError('matrix-nio is required for MatrixClient')
        self.client = AsyncClient(homeserver, user)
        self.password = password
        self.enc_key = enc_key
        self.signing_key = signing_key
        self.verify_key = verify_key

    async def login(self) -> None:
        """Log in to the homeserver."""
        await self.client.login(self.password)

    async def send_message(self, room_id: str, body: str) -> None:
        """Send a text message to a room with optional encryption and signing."""
        data: bytes = body.encode()
        if self.enc_key:
            data = encrypt_payload(self.enc_key, data)
        if self.signing_key:
            sig = sign_message(self.signing_key, data)
            payload = json.dumps({
                "body": base64.b64encode(data).decode(),
                "sig": base64.b64encode(sig).decode(),
            })
            await self.client.room_send(room_id, "m.room.message", {"msgtype": "m.text", "body": payload})
        else:
            await self.client.room_send(room_id, "m.room.message", {"msgtype": "m.text", "body": data.decode()})

    async def _parse_messages(self, res) -> List[str]:
        """Decode messages from a room_messages response."""
        messages: List[str] = []
        for event in res.chunk:
            if not hasattr(event, "body"):
                continue
            body = event.body
            try:
                payload = json.loads(body)
                data = base64.b64decode(payload["body"])
                sig = base64.b64decode(payload["sig"])
                if self.verify_key and verify_signature(self.verify_key, data, sig):
                    if self.enc_key:
                        data = decrypt_payload(self.enc_key, data)
                    messages.append(data.decode())
            except Exception:
                if self.enc_key:
                    try:
                        plain = decrypt_payload(self.enc_key, body.encode()).decode()
                        messages.append(plain)
                        continue
                    except Exception:
                        pass
                messages.append(body)
        return messages

    async def get_history(self, room_id: str, limit: int = 50, direction: str = "b") -> List[str]:
        """Return text bodies from room history, verifying signatures if set."""
        res = await self.client.room_messages(room_id, limit=limit, direction=direction)
        return await self._parse_messages(res)

    async def get_history_paginated(self, room_id: str, start_token: str | None = None, limit: int = 50) -> tuple[List[str], str | None]:
        """Retrieve a page of history and return messages plus end token."""
        res = await self.client.room_messages(room_id, start_token, limit=limit, direction="b")
        msgs = await self._parse_messages(res)
        return msgs, getattr(res, "end", None)

    async def archive_to_memory(self, room_id: str, memory_bot: MemoryManagerBot, limit: int = 50) -> None:
        """Fetch room history and store messages via ``MemoryManagerBot``."""
        token = None
        while True:
            messages, token = await self.get_history_paginated(room_id, start_token=token, limit=limit)
            for body in messages:
                memory_bot.add_memory(body)
            if not token:
                break

    async def close(self) -> None:
        await self.client.close()

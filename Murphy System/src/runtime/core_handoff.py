"""Legacy runtime handoff helpers for Murphy Core.

These helpers make it explicit how legacy /api/chat and /api/execute
should delegate into Murphy Core without maintaining a second orchestration path.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.runtime.murphy_core_bridge import create_bridge_app


class CoreHandoff:
    def __init__(self, prefer_core: bool = True) -> None:
        self.prefer_core = prefer_core
        self._app: FastAPI = create_bridge_app(prefer_core=prefer_core)
        self._client = TestClient(self._app)

    def handoff_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._client.post("/api/chat", json=payload)
        return {
            "status_code": response.status_code,
            "payload": response.json(),
            "delegated_to": "murphy_core" if self.prefer_core else "legacy_runtime",
        }

    def handoff_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._client.post("/api/execute", json=payload)
        return {
            "status_code": response.status_code,
            "payload": response.json(),
            "delegated_to": "murphy_core" if self.prefer_core else "legacy_runtime",
        }

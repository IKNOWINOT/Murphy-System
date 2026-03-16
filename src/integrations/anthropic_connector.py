"""
Anthropic Claude Integration — Murphy System World Model Connector.

Uses Anthropic API.
Required credentials: ANTHROPIC_API_KEY
Setup: https://console.anthropic.com/
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicConnector(BaseIntegrationConnector):
    """Anthropic Claude API connector."""

    INTEGRATION_NAME = "Anthropic Claude"
    BASE_URL = "https://api.anthropic.com/v1"
    CREDENTIAL_KEYS = ["ANTHROPIC_API_KEY"]
    REQUIRED_CREDENTIALS = ["ANTHROPIC_API_KEY"]
    FREE_TIER = False
    SETUP_URL = "https://console.anthropic.com/api-keys"
    DOCUMENTATION_URL = "https://docs.anthropic.com/en/api/getting-started"

    def _build_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._credentials.get("ANTHROPIC_API_KEY", ""),
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    # -- Messages --

    def message(
        self,
        content: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: float = 1.0,
    ) -> Dict[str, Any]:
        """Send a single user message and get a response."""
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        return self._post("/messages", json=payload)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: float = 1.0,
    ) -> Dict[str, Any]:
        """Multi-turn conversation."""
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        return self._post("/messages", json=payload)

    def count_tokens(self, messages: List[Dict[str, str]],
                     model: str = "claude-3-5-sonnet-20241022") -> Dict[str, Any]:
        return self._post("/messages/count_tokens", json={
            "model": model, "messages": messages})

    # -- Models --

    def list_models(self) -> Dict[str, Any]:
        return self._get("/models")

    # -- Batches (async message batches) --

    def create_batch(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._post("/messages/batches",
                          json={"requests": requests},
                          headers={"anthropic-beta": "message-batches-2024-09-24"})

    def get_batch(self, batch_id: str) -> Dict[str, Any]:
        return self._get(f"/messages/batches/{batch_id}",
                         headers={"anthropic-beta": "message-batches-2024-09-24"})

    def list_batches(self) -> Dict[str, Any]:
        return self._get("/messages/batches",
                         headers={"anthropic-beta": "message-batches-2024-09-24"})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.message("ping", max_tokens=16)
        result["integration"] = self.INTEGRATION_NAME
        return result

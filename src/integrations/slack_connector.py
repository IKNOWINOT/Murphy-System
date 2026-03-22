"""
Slack Integration — Murphy System World Model Connector.

Uses Slack Web API v2.
Required credentials: SLACK_BOT_TOKEN
Setup: https://api.slack.com/authentication/token-types#bot
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class SlackConnector(BaseIntegrationConnector):
    """Slack Web API connector (bot token)."""

    INTEGRATION_NAME = "Slack"
    BASE_URL = "https://slack.com/api"
    CREDENTIAL_KEYS = ["SLACK_BOT_TOKEN", "SLACK_WEBHOOK_URL"]
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = "https://api.slack.com/apps"
    DOCUMENTATION_URL = "https://api.slack.com/web"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("SLACK_BOT_TOKEN")
            or self._credentials.get("SLACK_WEBHOOK_URL")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("SLACK_BOT_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    # -- Messages --

    def send_message(self, channel: str, text: str,
                     blocks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Post a message to a Slack channel."""
        payload: Dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        return self._post("/chat.postMessage", json=payload)

    def send_webhook(self, text: str,
                     blocks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Send a message via incoming webhook (no token required)."""
        webhook_url = self._credentials.get("SLACK_WEBHOOK_URL", "")
        if not webhook_url:
            return self._not_configured("SLACK_WEBHOOK_URL not set")
        payload: Dict[str, Any] = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        import httpx
        try:
            r = httpx.post(webhook_url, json=payload, timeout=self._timeout)
            return {"success": r.status_code == 200, "status": r.status_code}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def upload_file(self, channels: str, filename: str,
                    content: str, title: str = "") -> Dict[str, Any]:
        """Upload a text file/snippet to a channel."""
        return self._post("/files.upload", json={
            "channels": channels, "filename": filename,
            "content": content, "title": title,
        })

    # -- Channels --

    def list_channels(self, limit: int = 200,
                      cursor: Optional[str] = None) -> Dict[str, Any]:
        """List public channels."""
        params: Dict[str, Any] = {"limit": min(limit, 200), "types": "public_channel"}
        if cursor:
            params["cursor"] = cursor
        return self._get("/conversations.list", params=params)

    def get_channel_history(self, channel: str,
                            limit: int = 100) -> Dict[str, Any]:
        """Retrieve messages from a channel."""
        return self._get("/conversations.history",
                         params={"channel": channel, "limit": min(limit, 100)})

    def create_channel(self, name: str, is_private: bool = False) -> Dict[str, Any]:
        """Create a new channel."""
        return self._post("/conversations.create",
                          json={"name": name, "is_private": is_private})

    # -- Users --

    def list_users(self, limit: int = 200) -> Dict[str, Any]:
        return self._get("/users.list", params={"limit": min(limit, 200)})

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        return self._get("/users.info", params={"user": user_id})

    def _not_configured(self, msg: str) -> Dict[str, Any]:
        return {"success": False, "configured": False, "error": msg}

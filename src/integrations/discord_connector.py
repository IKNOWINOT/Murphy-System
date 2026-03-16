"""
Discord Bot Integration — Murphy System World Model Connector.

Uses Discord REST API v10.
Required credentials: DISCORD_BOT_TOKEN
Setup: https://discord.com/developers/docs/intro
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class DiscordConnector(BaseIntegrationConnector):
    """Discord Bot API v10 connector."""

    INTEGRATION_NAME = "Discord"
    BASE_URL = "https://discord.com/api/v10"
    CREDENTIAL_KEYS = ["DISCORD_BOT_TOKEN", "DISCORD_WEBHOOK_URL"]
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = "https://discord.com/developers/applications"
    DOCUMENTATION_URL = "https://discord.com/developers/docs/reference"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("DISCORD_BOT_TOKEN")
            or self._credentials.get("DISCORD_WEBHOOK_URL")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("DISCORD_BOT_TOKEN", "")
        return {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

    # -- Messages --

    def send_message(self, channel_id: str, content: str,
                     embeds: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"content": content}
        if embeds:
            payload["embeds"] = embeds
        return self._post(f"/channels/{channel_id}/messages", json=payload)

    def send_webhook_message(self, content: str,
                             username: Optional[str] = None,
                             embeds: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Send via webhook URL — does not require bot token."""
        webhook_url = self._credentials.get("DISCORD_WEBHOOK_URL", "")
        if not webhook_url:
            return self.not_configured_response("send_webhook_message")
        payload: Dict[str, Any] = {"content": content}
        if username:
            payload["username"] = username
        if embeds:
            payload["embeds"] = embeds
        # Use base HTTP but with webhook URL
        orig_base = self.BASE_URL
        self.BASE_URL = webhook_url
        result = self._post("", json=payload)
        self.BASE_URL = orig_base
        return result

    def get_messages(self, channel_id: str, limit: int = 50,
                     before: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if before:
            params["before"] = before
        return self._get(f"/channels/{channel_id}/messages", params=params)

    def delete_message(self, channel_id: str, message_id: str) -> Dict[str, Any]:
        return self._delete(f"/channels/{channel_id}/messages/{message_id}")

    # -- Channels --

    def get_channel(self, channel_id: str) -> Dict[str, Any]:
        return self._get(f"/channels/{channel_id}")

    def list_guild_channels(self, guild_id: str) -> Dict[str, Any]:
        return self._get(f"/guilds/{guild_id}/channels")

    def create_channel(self, guild_id: str, name: str, channel_type: int = 0) -> Dict[str, Any]:
        return self._post(f"/guilds/{guild_id}/channels", json={"name": name, "type": channel_type})

    # -- Guild / Server --

    def get_guild(self, guild_id: str) -> Dict[str, Any]:
        return self._get(f"/guilds/{guild_id}")

    def list_guild_members(self, guild_id: str, limit: int = 100) -> Dict[str, Any]:
        return self._get(f"/guilds/{guild_id}/members", params={"limit": min(limit, 1000)})

    def get_bot_user(self) -> Dict[str, Any]:
        return self._get("/users/@me")

    def list_bot_guilds(self) -> Dict[str, Any]:
        return self._get("/users/@me/guilds")

    # -- Roles --

    def list_roles(self, guild_id: str) -> Dict[str, Any]:
        return self._get(f"/guilds/{guild_id}/roles")

    def add_role(self, guild_id: str, user_id: str, role_id: str) -> Dict[str, Any]:
        return self._http("PUT", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_bot_user()
        result["integration"] = self.INTEGRATION_NAME
        return result

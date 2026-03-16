"""
Telegram Bot Integration — Murphy System World Model Connector.

Uses Telegram Bot API.
Required credentials: TELEGRAM_BOT_TOKEN
Setup: https://core.telegram.org/bots#how-do-i-create-a-bot
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .base_connector import BaseIntegrationConnector


class TelegramConnector(BaseIntegrationConnector):
    """Telegram Bot API connector."""

    INTEGRATION_NAME = "Telegram"
    BASE_URL = ""  # dynamic — built from token
    CREDENTIAL_KEYS = ["TELEGRAM_BOT_TOKEN"]
    REQUIRED_CREDENTIALS = ["TELEGRAM_BOT_TOKEN"]
    FREE_TIER = True
    SETUP_URL = "https://t.me/BotFather"
    DOCUMENTATION_URL = "https://core.telegram.org/bots/api"

    def _api_url(self, method: str) -> str:
        token = self._credentials.get("TELEGRAM_BOT_TOKEN", "")
        return f"https://api.telegram.org/bot{token}/{method}"

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None,
              json: Optional[Any] = None) -> Dict[str, Any]:
        """Direct Telegram API call."""
        if not self.is_configured():
            return self.not_configured_response(method)

        url = self._api_url(method)
        import threading
        with self._lock:
            self._request_count += 1
        try:
            import httpx
            with httpx.Client(timeout=self._timeout) as client:
                if json is not None:
                    response = client.post(url, json=json)
                else:
                    response = client.get(url, params=params)
            try:
                data = response.json()
            except Exception as exc:
                data = response.text
            return {
                "success": response.is_success and data.get("ok", False) if isinstance(data, dict) else response.is_success,
                "configured": True,
                "simulated": False,
                "data": data,
                "status_code": response.status_code,
                "error": None,
            }
        except ImportError:
            return {"success": False, "configured": True, "simulated": False, "data": None,
                    "error": "httpx not installed; run: pip install httpx"}
        except Exception as exc:
            with self._lock:
                self._error_count += 1
            return {"success": False, "configured": True, "simulated": False, "data": None, "error": str(exc)}

    # -- Core methods --

    def get_me(self) -> Dict[str, Any]:
        return self._call("getMe")

    def send_message(self, chat_id: Union[str, int], text: str,
                     parse_mode: Optional[str] = None,
                     reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", json=payload)

    def send_photo(self, chat_id: Union[str, int], photo_url: str,
                   caption: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption
        return self._call("sendPhoto", json=payload)

    def send_document(self, chat_id: Union[str, int], document_url: str,
                      caption: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "document": document_url}
        if caption:
            payload["caption"] = caption
        return self._call("sendDocument", json=payload)

    def get_updates(self, offset: Optional[int] = None, limit: int = 100,
                    timeout: int = 0) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": min(limit, 100), "timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        return self._call("getUpdates", params=params)

    def set_webhook(self, url: str) -> Dict[str, Any]:
        return self._call("setWebhook", json={"url": url})

    def delete_webhook(self) -> Dict[str, Any]:
        return self._call("deleteWebhook")

    def get_webhook_info(self) -> Dict[str, Any]:
        return self._call("getWebhookInfo")

    def get_chat(self, chat_id: Union[str, int]) -> Dict[str, Any]:
        return self._call("getChat", params={"chat_id": chat_id})

    def get_chat_members_count(self, chat_id: Union[str, int]) -> Dict[str, Any]:
        return self._call("getChatMembersCount", params={"chat_id": chat_id})

    def pin_message(self, chat_id: Union[str, int], message_id: int) -> Dict[str, Any]:
        return self._call("pinChatMessage", json={"chat_id": chat_id, "message_id": message_id})

    def create_invite_link(self, chat_id: Union[str, int]) -> Dict[str, Any]:
        return self._call("createChatInviteLink", json={"chat_id": chat_id})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_me()
        result["integration"] = self.INTEGRATION_NAME
        return result

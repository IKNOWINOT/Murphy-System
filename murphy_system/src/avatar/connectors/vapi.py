"""Vapi voice AI call connector."""

import logging
from typing import Any, Dict, List, Union

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_UNAVAILABLE_RESPONSE: Dict[str, str] = {
    "status": "unavailable",
    "reason": "API key not configured",
}
_TIMEOUT = 5


class VapiConnector:
    """Vapi voice AI call connector."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.vapi.ai"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._available = bool(api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _check_requests(self) -> None:
        if requests is None:
            raise RuntimeError("The 'requests' library is required but not installed")

    def start_call(
        self, phone_number: str, assistant_id: str = "default"
    ) -> Dict[str, Any]:
        """Start a voice AI call. Returns call metadata."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not phone_number or not phone_number.strip():
            raise ValueError("phone_number must be a non-empty string")
        if not assistant_id or not assistant_id.strip():
            raise ValueError("assistant_id must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/call/phone"
        payload = {
            "phoneNumber": phone_number,
            "assistantId": assistant_id,
        }

        try:
            response = requests.post(
                url, json=payload, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Vapi authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Vapi rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            logger.info("Vapi call started: %s", data.get("id"))
            return {
                "call_id": data.get("id", ""),
                "status": data.get("status", "ringing"),
            }
        except requests.ConnectionError:
            logger.error("Vapi connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Vapi request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Vapi HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def end_call(self, call_id: str) -> Dict[str, Any]:
        """End an active call."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not call_id or not call_id.strip():
            raise ValueError("call_id must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/call/{call_id}/stop"

        try:
            response = requests.post(
                url, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Vapi authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Vapi rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            logger.info("Vapi call ended: %s", call_id)
            return {
                "call_id": data.get("id", call_id),
                "status": data.get("status", "ended"),
            }
        except requests.ConnectionError:
            logger.error("Vapi connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Vapi request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Vapi HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Get the status of a call."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not call_id or not call_id.strip():
            raise ValueError("call_id must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/call/{call_id}"

        try:
            response = requests.get(
                url, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Vapi authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Vapi rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            logger.info("Vapi call %s status: %s", call_id, data.get("status"))
            return {
                "call_id": data.get("id", call_id),
                "status": data.get("status", "unknown"),
            }
        except requests.ConnectionError:
            logger.error("Vapi connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Vapi request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Vapi HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def list_assistants(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """List available voice assistants."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        self._check_requests()

        url = f"{self._base_url}/assistant"

        try:
            response = requests.get(
                url, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Vapi authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Vapi rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            assistants = data if isinstance(data, list) else data.get("data", [])
            logger.info("Vapi returned %d assistants", len(assistants))
            return assistants
        except requests.ConnectionError:
            logger.error("Vapi connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Vapi request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Vapi HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "service": "vapi",
            "available": self._available,
            "base_url": self._base_url,
            "version": "v1",
        }
        if self._available and requests is not None:
            try:
                resp = requests.get(
                    f"{self._base_url}/assistant",
                    headers=self._headers(),
                    timeout=10,
                )
                status["connected"] = resp.status_code == 200
            except (requests.ConnectionError, requests.Timeout):
                status["connected"] = False
        else:
            status["connected"] = False
        return status

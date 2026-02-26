"""Vapi voice AI call connector (stub for testing)."""

from typing import Any, Dict, List


class VapiConnector:
    """Vapi voice AI call connector (stub for testing)."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.vapi.ai"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._available = bool(api_key)

    def start_call(self, phone_number: str, assistant_id: str = "default") -> Dict[str, str]:
        """Start a voice AI call. Returns call metadata."""
        if not self._available:
            return {"status": "unavailable"}
        return {"call_id": "stub", "status": "ringing"}

    def end_call(self, call_id: str) -> Dict[str, str]:
        """End an active call."""
        return {"call_id": call_id, "status": "ended"}

    def get_call_status(self, call_id: str) -> Dict[str, str]:
        """Get the status of a call."""
        return {"call_id": call_id, "status": "active"}

    def list_assistants(self) -> List[Dict[str, str]]:
        """List available voice assistants."""
        return [{"assistant_id": "default", "name": "Default Assistant"}]

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        return {
            "service": "vapi",
            "available": self._available,
            "base_url": self._base_url,
        }

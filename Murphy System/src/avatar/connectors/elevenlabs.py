"""ElevenLabs text-to-speech connector (stub for testing)."""

from typing import Any, Dict, List


class ElevenLabsConnector:
    """ElevenLabs text-to-speech connector (stub for testing)."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.elevenlabs.io/v1"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._available = bool(api_key)

    def synthesize(self, text: str, voice_id: str = "default") -> bytes:
        """Synthesize speech from text. Returns audio bytes."""
        if not self._available:
            return b""
        return b""

    def list_voices(self) -> List[Dict[str, str]]:
        """List available voices."""
        return [{"voice_id": "default", "name": "Default Voice"}]

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        return {
            "service": "elevenlabs",
            "available": self._available,
            "base_url": self._base_url,
        }

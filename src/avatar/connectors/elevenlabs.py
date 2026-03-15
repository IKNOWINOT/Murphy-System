"""ElevenLabs text-to-speech connector."""

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


class ElevenLabsConnector:
    """ElevenLabs text-to-speech connector."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.elevenlabs.io/v1"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._available = bool(api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "xi-api-key": self._api_key,
            "Accept": "application/json",
        }

    def _check_requests(self) -> None:
        if requests is None:
            raise RuntimeError("The 'requests' library is required but not installed")

    def synthesize(
        self, text: str, voice_id: str = "default"
    ) -> Union[bytes, Dict[str, str]]:
        """Synthesize speech from text. Returns audio bytes on success."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not text or not text.strip():
            raise ValueError("text must be a non-empty string")
        if not voice_id or not voice_id.strip():
            raise ValueError("voice_id must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/text-to-speech/{voice_id}"
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        payload = {"text": text}

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("ElevenLabs authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("ElevenLabs rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            logger.info("ElevenLabs synthesized %d bytes of audio", len(response.content))
            return response.content
        except requests.ConnectionError:
            logger.error("ElevenLabs connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("ElevenLabs request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("ElevenLabs HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def list_voices(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """List available voices."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        self._check_requests()

        url = f"{self._base_url}/voices"
        try:
            response = requests.get(
                url, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("ElevenLabs authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("ElevenLabs rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            voices = data.get("voices", [])
            logger.info("ElevenLabs returned %d voices", len(voices))
            return voices
        except requests.ConnectionError:
            logger.error("ElevenLabs connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("ElevenLabs request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("ElevenLabs HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "service": "elevenlabs",
            "available": self._available,
            "base_url": self._base_url,
            "version": "v1",
        }
        if self._available and requests is not None:
            try:
                resp = requests.get(
                    f"{self._base_url}/voices",
                    headers=self._headers(),
                    timeout=10,
                )
                status["connected"] = resp.status_code == 200
            except (requests.ConnectionError, requests.Timeout):
                status["connected"] = False
        else:
            status["connected"] = False
        return status

"""HeyGen video generation connector."""

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


class HeyGenConnector:
    """HeyGen video generation connector."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.heygen.com/v2"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._available = bool(api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _check_requests(self) -> None:
        if requests is None:
            raise RuntimeError("The 'requests' library is required but not installed")

    def create_video(
        self, script: str, avatar_id: str = "default"
    ) -> Dict[str, Any]:
        """Create a video from script. Returns video metadata."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not script or not script.strip():
            raise ValueError("script must be a non-empty string")
        if not avatar_id or not avatar_id.strip():
            raise ValueError("avatar_id must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/video/generate"
        payload = {
            "video_inputs": [
                {
                    "character": {"type": "avatar", "avatar_id": avatar_id},
                    "voice": {"type": "text", "input_text": script},
                }
            ],
        }

        try:
            response = requests.post(
                url, json=payload, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("HeyGen authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("HeyGen rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json().get("data", {})
            logger.info("HeyGen video creation started: %s", data.get("video_id"))
            return {
                "video_id": data.get("video_id", ""),
                "status": data.get("status", "processing"),
            }
        except requests.ConnectionError:
            logger.error("HeyGen connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("HeyGen request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("HeyGen HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def get_video_status(self, video_id: str) -> Dict[str, Any]:
        """Get the status of a video generation job."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not video_id or not video_id.strip():
            raise ValueError("video_id must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/video_status.get"
        params = {"video_id": video_id}

        try:
            response = requests.get(
                url, params=params, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("HeyGen authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("HeyGen rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json().get("data", {})
            logger.info("HeyGen video %s status: %s", video_id, data.get("status"))
            return {
                "video_id": data.get("video_id", video_id),
                "status": data.get("status", "unknown"),
            }
        except requests.ConnectionError:
            logger.error("HeyGen connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("HeyGen request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("HeyGen HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def list_avatars(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """List available HeyGen avatars."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        self._check_requests()

        url = f"{self._base_url}/avatars"
        try:
            response = requests.get(
                url, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("HeyGen authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("HeyGen rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json().get("data", {})
            avatars = data.get("avatars", [])
            logger.info("HeyGen returned %d avatars", len(avatars))
            return avatars
        except requests.ConnectionError:
            logger.error("HeyGen connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("HeyGen request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("HeyGen HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "service": "heygen",
            "available": self._available,
            "base_url": self._base_url,
            "version": "v2",
        }
        if self._available and requests is not None:
            try:
                resp = requests.get(
                    f"{self._base_url}/avatars",
                    headers=self._headers(),
                    timeout=10,
                )
                status["connected"] = resp.status_code == 200
            except (requests.ConnectionError, requests.Timeout):
                status["connected"] = False
        else:
            status["connected"] = False
        return status

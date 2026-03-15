"""Tavus personalized video connector."""

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


class TavusConnector:
    """Tavus personalized video connector."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.tavus.io/v2"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._available = bool(api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _check_requests(self) -> None:
        if requests is None:
            raise RuntimeError("The 'requests' library is required but not installed")

    def create_replica(self, name: str, training_data: str = "") -> Dict[str, Any]:
        """Create a video replica. Returns replica metadata."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not name or not name.strip():
            raise ValueError("name must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/replicas"
        payload: Dict[str, str] = {"replica_name": name}
        if training_data:
            payload["training_data"] = training_data

        try:
            response = requests.post(
                url, json=payload, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Tavus authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Tavus rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            logger.info("Tavus replica created: %s", data.get("replica_id"))
            return {
                "replica_id": data.get("replica_id", ""),
                "status": data.get("status", "training"),
            }
        except requests.ConnectionError:
            logger.error("Tavus connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Tavus request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Tavus HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def generate_video(
        self, replica_id: str, script: str
    ) -> Dict[str, Any]:
        """Generate a personalized video from a replica."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        if not replica_id or not replica_id.strip():
            raise ValueError("replica_id must be a non-empty string")
        if not script or not script.strip():
            raise ValueError("script must be a non-empty string")
        self._check_requests()

        url = f"{self._base_url}/videos"
        payload = {"replica_id": replica_id, "script": script}

        try:
            response = requests.post(
                url, json=payload, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Tavus authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Tavus rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            logger.info("Tavus video generation started: %s", data.get("video_id"))
            return {
                "video_id": data.get("video_id", ""),
                "status": data.get("status", "processing"),
            }
        except requests.ConnectionError:
            logger.error("Tavus connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Tavus request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Tavus HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    def list_replicas(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """List available replicas."""
        if not self._available:
            return _UNAVAILABLE_RESPONSE
        self._check_requests()

        url = f"{self._base_url}/replicas"
        try:
            response = requests.get(
                url, headers=self._headers(), timeout=_TIMEOUT
            )
            if response.status_code == 401:
                logger.error("Tavus authentication failed")
                return {"status": "error", "reason": "Authentication failed"}
            if response.status_code == 429:
                logger.warning("Tavus rate limit exceeded")
                return {"status": "error", "reason": "Rate limit exceeded"}
            response.raise_for_status()
            data = response.json()
            replicas = data if isinstance(data, list) else data.get("data", [])
            logger.info("Tavus returned %d replicas", len(replicas))
            return replicas
        except requests.ConnectionError:
            logger.error("Tavus connection error")
            return {"status": "error", "reason": "Connection error"}
        except requests.Timeout:
            logger.error("Tavus request timed out")
            return {"status": "error", "reason": "Request timed out"}
        except requests.HTTPError as exc:
            logger.error("Tavus HTTP error: %s", exc)
            return {"status": "error", "reason": f"HTTP error: {exc}"}

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "service": "tavus",
            "available": self._available,
            "base_url": self._base_url,
            "version": "v2",
        }
        if self._available and requests is not None:
            try:
                resp = requests.get(
                    f"{self._base_url}/replicas",
                    headers=self._headers(),
                    timeout=10,
                )
                status["connected"] = resp.status_code == 200
            except (requests.ConnectionError, requests.Timeout):
                status["connected"] = False
        else:
            status["connected"] = False
        return status

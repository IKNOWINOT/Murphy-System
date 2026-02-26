"""Tavus personalized video connector (stub for testing)."""

from typing import Any, Dict, List


class TavusConnector:
    """Tavus personalized video connector (stub for testing)."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.tavus.io/v2"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._available = bool(api_key)

    def create_replica(self, name: str, training_data: str = "") -> Dict[str, str]:
        """Create a video replica. Returns replica metadata."""
        if not self._available:
            return {"status": "unavailable"}
        return {"replica_id": "stub", "status": "training"}

    def generate_video(
        self, replica_id: str, script: str
    ) -> Dict[str, str]:
        """Generate a personalized video from a replica."""
        if not self._available:
            return {"status": "unavailable"}
        return {"video_id": "stub", "status": "processing"}

    def list_replicas(self) -> List[Dict[str, str]]:
        """List available replicas."""
        return [{"replica_id": "default", "name": "Default Replica"}]

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        return {
            "service": "tavus",
            "available": self._available,
            "base_url": self._base_url,
        }

"""HeyGen video generation connector (stub for testing)."""

from typing import Any, Dict, List


class HeyGenConnector:
    """HeyGen video generation connector (stub for testing)."""

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.heygen.com/v2"
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._available = bool(api_key)

    def create_video(
        self, script: str, avatar_id: str = "default"
    ) -> Dict[str, str]:
        """Create a video from script. Returns video metadata."""
        if not self._available:
            return {"status": "unavailable"}
        return {"video_id": "stub", "status": "processing"}

    def get_video_status(self, video_id: str) -> Dict[str, str]:
        """Get the status of a video generation job."""
        return {"video_id": video_id, "status": "completed"}

    def list_avatars(self) -> List[Dict[str, str]]:
        """List available HeyGen avatars."""
        return [{"avatar_id": "default", "name": "Default Avatar"}]

    @property
    def available(self) -> bool:
        return self._available

    def get_status(self) -> Dict[str, Any]:
        return {
            "service": "heygen",
            "available": self._available,
            "base_url": self._base_url,
        }

"""
Zoom Integration — Murphy System World Model Connector.

Uses Zoom REST API v2 (Server-to-Server OAuth).
Required credentials: ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET
                   or ZOOM_API_KEY (legacy JWT — deprecated Jan 2023)
Setup: https://marketplace.zoom.us/develop/create
"""
from __future__ import annotations

import base64
import time
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class ZoomConnector(BaseIntegrationConnector):
    """Zoom REST API v2 connector (Server-to-Server OAuth)."""

    INTEGRATION_NAME = "Zoom"
    BASE_URL = "https://api.zoom.us/v2"
    CREDENTIAL_KEYS = [
        "ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_API_KEY"
    ]
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = "https://marketplace.zoom.us/develop/create"
    DOCUMENTATION_URL = "https://developers.zoom.us/docs/api/"

    def __init__(self, credentials=None, **kwargs):
        super().__init__(credentials=credentials, **kwargs)
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

    def is_configured(self) -> bool:
        return bool(
            (self._credentials.get("ZOOM_ACCOUNT_ID")
             and self._credentials.get("ZOOM_CLIENT_ID")
             and self._credentials.get("ZOOM_CLIENT_SECRET"))
            or self._credentials.get("ZOOM_API_KEY")
        )

    def _get_access_token(self) -> Optional[str]:
        """Obtain Server-to-Server OAuth access token, caching until expiry."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        account_id = self._credentials.get("ZOOM_ACCOUNT_ID", "")
        client_id = self._credentials.get("ZOOM_CLIENT_ID", "")
        client_secret = self._credentials.get("ZOOM_CLIENT_SECRET", "")
        if not (account_id and client_id and client_secret):
            return None
        encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        import httpx
        try:
            r = httpx.post(
                "https://zoom.us/oauth/token",
                params={"grant_type": "account_credentials", "account_id": account_id},
                headers={"Authorization": f"Basic {encoded}"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            self._access_token = data.get("access_token")
            self._token_expiry = time.time() + data.get("expires_in", 3600)
            return self._access_token
        except Exception:
            return None

    def _build_headers(self) -> Dict[str, str]:
        token = self._get_access_token() or self._credentials.get("ZOOM_API_KEY", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -- Meetings --

    def list_meetings(self, user_id: str = "me",
                      meeting_type: str = "scheduled",
                      page_size: int = 30) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}/meetings",
                         params={"type": meeting_type,
                                 "page_size": min(page_size, 300)})

    def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/meetings/{meeting_id}")

    def create_meeting(self, topic: str, start_time: str,
                       duration: int = 60, agenda: str = "",
                       user_id: str = "me",
                       meeting_type: int = 2) -> Dict[str, Any]:
        """Create a scheduled meeting.

        meeting_type: 1=instant, 2=scheduled, 3=recurring_no_fixed_time, 8=recurring_fixed_time
        """
        return self._post(f"/users/{user_id}/meetings", json={
            "topic": topic,
            "type": meeting_type,
            "start_time": start_time,
            "duration": duration,
            "agenda": agenda,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "mute_upon_entry": True,
                "waiting_room": True,
                "auto_recording": "none",
            },
        })

    def update_meeting(self, meeting_id: str,
                       updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("PATCH", f"/meetings/{meeting_id}", json=updates)

    def delete_meeting(self, meeting_id: str) -> Dict[str, Any]:
        return self._http("DELETE", f"/meetings/{meeting_id}")

    def get_meeting_registrants(self, meeting_id: str,
                                page_size: int = 30) -> Dict[str, Any]:
        return self._get(f"/meetings/{meeting_id}/registrants",
                         params={"page_size": min(page_size, 300)})

    # -- Webinars --

    def list_webinars(self, user_id: str = "me",
                      page_size: int = 30) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}/webinars",
                         params={"page_size": min(page_size, 300)})

    # -- Reports --

    def get_meeting_report(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/report/meetings/{meeting_id}")

    def get_meeting_participants(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/report/meetings/{meeting_id}/participants")

    # -- Users --

    def get_user(self, user_id: str = "me") -> Dict[str, Any]:
        return self._get(f"/users/{user_id}")

    def list_users(self, page_size: int = 30) -> Dict[str, Any]:
        return self._get("/users", params={"page_size": min(page_size, 300)})

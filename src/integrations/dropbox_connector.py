"""
Dropbox Integration — Murphy System World Model Connector.

Uses Dropbox API v2.
Required credentials: DROPBOX_ACCESS_TOKEN
Setup: https://www.dropbox.com/developers/documentation/http/documentation
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class DropboxConnector(BaseIntegrationConnector):
    """Dropbox API v2 connector."""

    INTEGRATION_NAME = "Dropbox"
    BASE_URL = "https://api.dropboxapi.com/2"
    CREDENTIAL_KEYS = ["DROPBOX_ACCESS_TOKEN", "DROPBOX_REFRESH_TOKEN", "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET"]
    REQUIRED_CREDENTIALS = ["DROPBOX_ACCESS_TOKEN"]
    FREE_TIER = True
    SETUP_URL = "https://www.dropbox.com/developers/apps"
    DOCUMENTATION_URL = "https://www.dropbox.com/developers/documentation/http/documentation"

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("DROPBOX_ACCESS_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -- Files --

    def list_folder(self, path: str = "", recursive: bool = False,
                    limit: int = 100) -> Dict[str, Any]:
        return self._post("/files/list_folder", json={
            "path": path,
            "recursive": recursive,
            "limit": min(limit, 2000),
        })

    def get_metadata(self, path: str) -> Dict[str, Any]:
        return self._post("/files/get_metadata", json={"path": path})

    def create_folder(self, path: str, auto_rename: bool = False) -> Dict[str, Any]:
        return self._post("/files/create_folder_v2", json={
            "path": path,
            "autorename": auto_rename,
        })

    def delete_file(self, path: str) -> Dict[str, Any]:
        return self._post("/files/delete_v2", json={"path": path})

    def move_file(self, from_path: str, to_path: str, auto_rename: bool = False) -> Dict[str, Any]:
        return self._post("/files/move_v2", json={
            "from_path": from_path,
            "to_path": to_path,
            "autorename": auto_rename,
        })

    def copy_file(self, from_path: str, to_path: str) -> Dict[str, Any]:
        return self._post("/files/copy_v2", json={
            "from_path": from_path,
            "to_path": to_path,
        })

    def search_files(self, query: str, path: str = "", max_results: int = 20) -> Dict[str, Any]:
        return self._post("/files/search_v2", json={
            "query": query,
            "options": {"path": path, "max_results": min(max_results, 1000)},
        })

    def get_temporary_link(self, path: str) -> Dict[str, Any]:
        return self._post("/files/get_temporary_link", json={"path": path})

    # -- Sharing --

    def list_shared_links(self, path: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if path:
            body["path"] = path
        return self._post("/sharing/list_shared_links", json=body)

    def create_shared_link(self, path: str, requested_visibility: str = "public") -> Dict[str, Any]:
        return self._post("/sharing/create_shared_link_with_settings", json={
            "path": path,
            "settings": {"requested_visibility": requested_visibility},
        })

    # -- Account --

    def get_current_account(self) -> Dict[str, Any]:
        return self._post("/users/get_current_account")

    def get_space_usage(self) -> Dict[str, Any]:
        return self._post("/users/get_space_usage")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_current_account()
        result["integration"] = self.INTEGRATION_NAME
        return result

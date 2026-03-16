"""
Google Drive Integration — Murphy System World Model Connector.

Uses Google Drive API v3.
Required credentials: GOOGLE_DRIVE_ACCESS_TOKEN (or GOOGLE_SERVICE_ACCOUNT_JSON for service accounts)
Setup: https://developers.google.com/drive/api/guides/about-sdk
"""
from __future__ import annotations
import logging

import json
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class GoogleDriveConnector(BaseIntegrationConnector):
    """Google Drive API v3 connector."""

    INTEGRATION_NAME = "Google Drive"
    BASE_URL = "https://www.googleapis.com/drive/v3"
    CREDENTIAL_KEYS = ["GOOGLE_DRIVE_ACCESS_TOKEN", "GOOGLE_SERVICE_ACCOUNT_JSON"]
    FREE_TIER = True
    SETUP_URL = "https://developers.google.com/drive/api/guides/about-sdk"
    DOCUMENTATION_URL = "https://developers.google.com/drive/api/reference/rest/v3"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("GOOGLE_DRIVE_ACCESS_TOKEN")
            or self._credentials.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("GOOGLE_DRIVE_ACCESS_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -- Files --

    def list_files(self, page_size: int = 100, query: Optional[str] = None,
                   page_token: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "pageSize": min(page_size, 1000),
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size,webViewLink)",
        }
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token
        return self._get("/files", params=params)

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        return self._get(f"/files/{file_id}",
                         params={"fields": "id,name,mimeType,size,modifiedTime,webViewLink,parents"})

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]
        return self._post("/files", json=metadata)

    def copy_file(self, file_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if name:
            body["name"] = name
        return self._post(f"/files/{file_id}/copy", json=body)

    def delete_file(self, file_id: str) -> Dict[str, Any]:
        return self._delete(f"/files/{file_id}")

    def move_file(self, file_id: str, new_parent_id: str) -> Dict[str, Any]:
        # Get current parents first
        meta = self.get_file_metadata(file_id)
        parents = (meta.get("data") or {}).get("parents", [])
        remove_parents = ",".join(parents)
        return self._http(
            "PATCH",
            f"/files/{file_id}",
            params={"addParents": new_parent_id, "removeParents": remove_parents,
                    "fields": "id,parents"},
        )

    def search_files(self, query: str, page_size: int = 50) -> Dict[str, Any]:
        return self.list_files(page_size=page_size, query=query)

    # -- Sharing / Permissions --

    def list_permissions(self, file_id: str) -> Dict[str, Any]:
        return self._get(f"/files/{file_id}/permissions")

    def share_file(self, file_id: str, email: str, role: str = "reader") -> Dict[str, Any]:
        return self._post(f"/files/{file_id}/permissions", json={
            "type": "user",
            "role": role,
            "emailAddress": email,
        })

    def make_public(self, file_id: str) -> Dict[str, Any]:
        return self._post(f"/files/{file_id}/permissions", json={
            "type": "anyone",
            "role": "reader",
        })

    # -- About --

    def get_storage_quota(self) -> Dict[str, Any]:
        return self._get("/about", params={"fields": "storageQuota,user"})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/about", params={"fields": "user"})
        result["integration"] = self.INTEGRATION_NAME
        return result

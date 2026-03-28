"""
Notion Integration — Murphy System World Model Connector.

Uses Notion API v1.
Required credentials: NOTION_API_KEY (Integration token)
Setup: https://www.notion.so/my-integrations
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class NotionConnector(BaseIntegrationConnector):
    """Notion API v1 connector."""

    INTEGRATION_NAME = "Notion"
    BASE_URL = "https://api.notion.com/v1"
    CREDENTIAL_KEYS = ["NOTION_API_KEY", "NOTION_TOKEN"]
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = "https://www.notion.so/my-integrations"
    DOCUMENTATION_URL = "https://developers.notion.com/reference/intro"

    NOTION_VERSION = "2022-06-28"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("NOTION_API_KEY")
            or self._credentials.get("NOTION_TOKEN")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = (self._credentials.get("NOTION_API_KEY")
                 or self._credentials.get("NOTION_TOKEN", ""))
        return {
            "Authorization": f"Bearer {token}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # -- Databases --

    def list_databases(self) -> Dict[str, Any]:
        """Search for all databases the integration can access."""
        return self._post("/search", json={"filter": {"value": "database", "property": "object"}})

    def query_database(self, database_id: str,
                       filter_obj: Optional[Dict[str, Any]] = None,
                       sorts: Optional[List[Dict[str, Any]]] = None,
                       page_size: int = 100) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        return self._post(f"/databases/{database_id}/query", json=payload)

    def get_database(self, database_id: str) -> Dict[str, Any]:
        return self._get(f"/databases/{database_id}")

    def create_database(self, parent_page_id: str, title: str,
                        properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties or {"Name": {"title": {}}},
        }
        return self._post("/databases", json=payload)

    # -- Pages --

    def get_page(self, page_id: str) -> Dict[str, Any]:
        return self._get(f"/pages/{page_id}")

    def create_page(self, parent_id: str, title: str,
                    properties: Optional[Dict[str, Any]] = None,
                    children: Optional[List[Dict[str, Any]]] = None,
                    parent_type: str = "database_id") -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "parent": {parent_type: parent_id},
            "properties": properties or {
                "title": {"title": [{"text": {"content": title}}]}
            },
        }
        if children:
            payload["children"] = children
        return self._post("/pages", json=payload)

    def update_page(self, page_id: str,
                    properties: Dict[str, Any],
                    archived: bool = False) -> Dict[str, Any]:
        return self._http("PATCH", f"/pages/{page_id}",
                          json={"properties": properties, "archived": archived})

    # -- Blocks --

    def get_block_children(self, block_id: str,
                           page_size: int = 100) -> Dict[str, Any]:
        return self._get(f"/blocks/{block_id}/children",
                         params={"page_size": min(page_size, 100)})

    def append_block_children(self, block_id: str,
                              children: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._http("PATCH", f"/blocks/{block_id}/children",
                          json={"children": children})

    # -- Search --

    def search(self, query: str, filter_type: Optional[str] = None,
               page_size: int = 20) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "page_size": min(page_size, 100)}
        if filter_type:
            payload["filter"] = {"value": filter_type, "property": "object"}
        return self._post("/search", json=payload)

    # -- Users --

    def list_users(self) -> Dict[str, Any]:
        return self._get("/users")

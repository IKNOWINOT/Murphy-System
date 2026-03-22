"""
Monday.com Integration — Murphy System World Model Connector.

Uses Monday.com GraphQL API v2.
Required credentials: MONDAY_API_KEY
Setup: https://developer.monday.com/apps/docs/mondaycode
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class MondayConnector(BaseIntegrationConnector):
    """Monday.com GraphQL API connector."""

    INTEGRATION_NAME = "Monday.com"
    BASE_URL = "https://api.monday.com/v2"
    CREDENTIAL_KEYS = ["MONDAY_API_KEY"]
    REQUIRED_CREDENTIALS = ["MONDAY_API_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://developer.monday.com/apps/docs/mondaycode"
    DOCUMENTATION_URL = "https://developer.monday.com/api-reference/reference/about-the-api-reference"

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("MONDAY_API_KEY", "")
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": "2023-10",
        }

    def _graphql(self, query: str,
                 variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        return self._post("", json=payload)

    # -- Boards --

    def list_boards(self, limit: int = 25) -> Dict[str, Any]:
        query = f"""query {{
            boards(limit: {min(limit, 100)}) {{
                id name description state board_kind
                columns {{ id title type }}
                groups {{ id title color }}
            }}
        }}"""
        return self._graphql(query)

    def get_board(self, board_id: str) -> Dict[str, Any]:
        query = f"""query {{
            boards(ids: [{board_id}]) {{
                id name description state
                items_count
                columns {{ id title type }}
                groups {{ id title color }}
            }}
        }}"""
        return self._graphql(query)

    # -- Items --

    def list_items(self, board_id: str, limit: int = 50) -> Dict[str, Any]:
        query = f"""query {{
            boards(ids: [{board_id}]) {{
                items_page(limit: {min(limit, 500)}) {{
                    items {{
                        id name state
                        column_values {{ id text value }}
                        group {{ id title }}
                    }}
                }}
            }}
        }}"""
        return self._graphql(query)

    def create_item(self, board_id: str, group_id: str,
                    item_name: str,
                    column_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import json
        cv_str = json.dumps(json.dumps(column_values or {}))
        query = f"""mutation {{
            create_item(
                board_id: {board_id},
                group_id: "{group_id}",
                item_name: "{item_name}",
                column_values: {cv_str}
            ) {{
                id name
            }}
        }}"""
        return self._graphql(query)

    def update_item(self, board_id: str, item_id: str,
                    column_id: str, value: str) -> Dict[str, Any]:
        import json
        query = f"""mutation {{
            change_simple_column_value(
                board_id: {board_id},
                item_id: {item_id},
                column_id: "{column_id}",
                value: {json.dumps(value)}
            ) {{
                id
            }}
        }}"""
        return self._graphql(query)

    def delete_item(self, item_id: str) -> Dict[str, Any]:
        query = f"""mutation {{
            delete_item(item_id: {item_id}) {{
                id
            }}
        }}"""
        return self._graphql(query)

    # -- Updates (comments) --

    def create_update(self, item_id: str, body: str) -> Dict[str, Any]:
        query = f"""mutation {{
            create_update(
                item_id: {item_id},
                body: "{body}"
            ) {{
                id body
            }}
        }}"""
        return self._graphql(query)

    # -- Users --

    def get_me(self) -> Dict[str, Any]:
        query = """query { me { id name email } }"""
        return self._graphql(query)

"""
Trello Project Management Integration — Murphy System World Model Connector.

Uses Trello REST API v1.
Required credentials: TRELLO_API_KEY, TRELLO_TOKEN
Setup: https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class TrelloConnector(BaseIntegrationConnector):
    """Trello REST API connector."""

    INTEGRATION_NAME = "Trello"
    BASE_URL = "https://api.trello.com/1"
    CREDENTIAL_KEYS = ["TRELLO_API_KEY", "TRELLO_TOKEN"]
    REQUIRED_CREDENTIALS = ["TRELLO_API_KEY", "TRELLO_TOKEN"]
    FREE_TIER = True
    SETUP_URL = "https://trello.com/app-key"
    DOCUMENTATION_URL = "https://developer.atlassian.com/cloud/trello/rest/"

    def _auth_params(self) -> Dict[str, str]:
        return {
            "key": self._credentials.get("TRELLO_API_KEY", ""),
            "token": self._credentials.get("TRELLO_TOKEN", ""),
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        merged = {**self._auth_params(), **(params or {})}
        return super()._get(path, params=merged, headers=headers)

    def _post(self, path: str, json: Optional[Any] = None,
              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        # Trello wants auth as query params, not headers
        return self._http("POST", path, params=self._auth_params(), json=json, headers=headers)

    def _delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._http("DELETE", path, params=self._auth_params(), headers=headers)

    # -- Boards --

    def list_boards(self, member_id: str = "me") -> Dict[str, Any]:
        return self._get(f"/members/{member_id}/boards",
                         params={"fields": "id,name,desc,closed,url,shortUrl"})

    def get_board(self, board_id: str) -> Dict[str, Any]:
        return self._get(f"/boards/{board_id}")

    def create_board(self, name: str, desc: str = "",
                     default_lists: bool = True) -> Dict[str, Any]:
        return self._post("/boards", json={
            "name": name,
            "desc": desc,
            "defaultLists": default_lists,
        })

    def close_board(self, board_id: str) -> Dict[str, Any]:
        return self._http("PUT", f"/boards/{board_id}", params={**self._auth_params()},
                          json={"closed": True})

    # -- Lists --

    def list_lists(self, board_id: str) -> Dict[str, Any]:
        return self._get(f"/boards/{board_id}/lists")

    def create_list(self, board_id: str, name: str, pos: str = "bottom") -> Dict[str, Any]:
        return self._post("/lists", json={"idBoard": board_id, "name": name, "pos": pos})

    def archive_list(self, list_id: str) -> Dict[str, Any]:
        return self._http("PUT", f"/lists/{list_id}/closed", params=self._auth_params(),
                          json={"value": True})

    # -- Cards --

    def list_cards(self, list_id: str) -> Dict[str, Any]:
        return self._get(f"/lists/{list_id}/cards")

    def get_card(self, card_id: str) -> Dict[str, Any]:
        return self._get(f"/cards/{card_id}")

    def create_card(self, list_id: str, name: str, desc: str = "",
                    due: Optional[str] = None, pos: str = "bottom") -> Dict[str, Any]:
        payload: Dict[str, Any] = {"idList": list_id, "name": name, "desc": desc, "pos": pos}
        if due:
            payload["due"] = due
        return self._post("/cards", json=payload)

    def update_card(self, card_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("PUT", f"/cards/{card_id}", params=self._auth_params(), json=updates)

    def archive_card(self, card_id: str) -> Dict[str, Any]:
        return self.update_card(card_id, {"closed": True})

    def move_card(self, card_id: str, list_id: str) -> Dict[str, Any]:
        return self.update_card(card_id, {"idList": list_id})

    def add_comment(self, card_id: str, text: str) -> Dict[str, Any]:
        return self._post(f"/cards/{card_id}/actions/comments", json={"text": text})

    def assign_member(self, card_id: str, member_id: str) -> Dict[str, Any]:
        return self._http("POST", f"/cards/{card_id}/idMembers",
                          params=self._auth_params(), json={"value": member_id})

    def add_checklist(self, card_id: str, name: str) -> Dict[str, Any]:
        return self._post(f"/cards/{card_id}/checklists", json={"name": name})

    # -- Members --

    def get_member(self, member_id: str = "me") -> Dict[str, Any]:
        return self._get(f"/members/{member_id}")

    # -- Search --

    def search(self, query: str, model_types: str = "cards,boards") -> Dict[str, Any]:
        return self._get("/search", params={"query": query, "modelTypes": model_types})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_member()
        result["integration"] = self.INTEGRATION_NAME
        return result

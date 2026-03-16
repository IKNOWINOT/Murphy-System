"""
HubSpot CRM Integration — Murphy System World Model Connector.

Uses HubSpot API v3 (free tier).
Required credentials: HUBSPOT_API_KEY or HUBSPOT_ACCESS_TOKEN
Setup: https://developers.hubspot.com/docs/api/overview
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class HubSpotConnector(BaseIntegrationConnector):
    """HubSpot CRM connector (v3 API)."""

    INTEGRATION_NAME = "HubSpot"
    BASE_URL = "https://api.hubapi.com"
    CREDENTIAL_KEYS = ["HUBSPOT_API_KEY", "HUBSPOT_ACCESS_TOKEN"]
    REQUIRED_CREDENTIALS = []  # At least one of the above
    FREE_TIER = True
    SETUP_URL = "https://developers.hubspot.com/docs/api/overview"
    DOCUMENTATION_URL = "https://developers.hubspot.com/docs/api/crm/contacts"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("HUBSPOT_API_KEY")
            or self._credentials.get("HUBSPOT_ACCESS_TOKEN")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("HUBSPOT_ACCESS_TOKEN") or self._credentials.get("HUBSPOT_API_KEY", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -- Contacts --

    def list_contacts(self, limit: int = 100, after: Optional[str] = None) -> Dict[str, Any]:
        """List CRM contacts."""
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        return self._get("/crm/v3/objects/contacts", params=params)

    def get_contact(self, contact_id: str) -> Dict[str, Any]:
        return self._get(f"/crm/v3/objects/contacts/{contact_id}")

    def create_contact(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/crm/v3/objects/contacts", json={"properties": properties})

    def update_contact(self, contact_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._patch(f"/crm/v3/objects/contacts/{contact_id}", json={"properties": properties})

    def search_contacts(self, query: str, limit: int = 20) -> Dict[str, Any]:
        payload = {
            "query": query,
            "limit": min(limit, 100),
            "properties": ["firstname", "lastname", "email", "phone", "company"],
        }
        return self._post("/crm/v3/objects/contacts/search", json=payload)

    # -- Deals --

    def list_deals(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/crm/v3/objects/deals", params={"limit": min(limit, 100)})

    def create_deal(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/crm/v3/objects/deals", json={"properties": properties})

    # -- Companies --

    def list_companies(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/crm/v3/objects/companies", params={"limit": min(limit, 100)})

    def create_company(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/crm/v3/objects/companies", json={"properties": properties})

    # -- Pipelines --

    def list_pipelines(self, object_type: str = "deals") -> Dict[str, Any]:
        return self._get(f"/crm/v3/pipelines/{object_type}")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/crm/v3/objects/contacts", params={"limit": 1})
        result["integration"] = self.INTEGRATION_NAME
        return result

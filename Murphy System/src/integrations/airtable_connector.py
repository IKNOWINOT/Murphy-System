"""
Airtable Integration — Murphy System World Model Connector.

Uses Airtable REST API v0.
Required credentials: AIRTABLE_API_KEY or AIRTABLE_PERSONAL_ACCESS_TOKEN
Setup: https://airtable.com/create/tokens
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class AirtableConnector(BaseIntegrationConnector):
    """Airtable REST API connector."""

    INTEGRATION_NAME = "Airtable"
    BASE_URL = "https://api.airtable.com/v0"
    CREDENTIAL_KEYS = ["AIRTABLE_API_KEY", "AIRTABLE_PERSONAL_ACCESS_TOKEN"]
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = "https://airtable.com/create/tokens"
    DOCUMENTATION_URL = "https://airtable.com/developers/web/api/introduction"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("AIRTABLE_API_KEY")
            or self._credentials.get("AIRTABLE_PERSONAL_ACCESS_TOKEN")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = (self._credentials.get("AIRTABLE_PERSONAL_ACCESS_TOKEN")
                 or self._credentials.get("AIRTABLE_API_KEY", ""))
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -- Records --

    def list_records(self, base_id: str, table_name: str,
                     view: Optional[str] = None,
                     filter_formula: Optional[str] = None,
                     max_records: int = 100,
                     fields: Optional[List[str]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"maxRecords": min(max_records, 100)}
        if view:
            params["view"] = view
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if fields:
            params["fields[]"] = fields
        return self._get(f"/{base_id}/{table_name}", params=params)

    def get_record(self, base_id: str, table_name: str,
                   record_id: str) -> Dict[str, Any]:
        return self._get(f"/{base_id}/{table_name}/{record_id}")

    def create_records(self, base_id: str, table_name: str,
                       records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create up to 10 records at once."""
        return self._post(f"/{base_id}/{table_name}", json={
            "records": [{"fields": r} for r in records[:10]]
        })

    def update_record(self, base_id: str, table_name: str,
                      record_id: str,
                      fields: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record (PATCH — only specified fields changed)."""
        return self._http("PATCH", f"/{base_id}/{table_name}/{record_id}",
                          json={"fields": fields})

    def delete_record(self, base_id: str, table_name: str,
                      record_id: str) -> Dict[str, Any]:
        return self._http("DELETE", f"/{base_id}/{table_name}/{record_id}")

    # -- Bases --

    def list_bases(self) -> Dict[str, Any]:
        """List all bases the token has access to (Meta API)."""
        return self._get("/meta/bases",
                         base_url_override="https://api.airtable.com")

    def get_base_schema(self, base_id: str) -> Dict[str, Any]:
        return self._get(f"/meta/bases/{base_id}/tables",
                         base_url_override="https://api.airtable.com")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None,  # type: ignore[override]
             base_url_override: Optional[str] = None) -> Dict[str, Any]:
        """Override to support alternate base URLs for the Meta API."""
        if base_url_override:
            original = self.BASE_URL
            self.BASE_URL = base_url_override
            result = super()._get(path, params=params)
            self.BASE_URL = original
            return result
        return super()._get(path, params=params)

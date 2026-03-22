"""
SendGrid Integration — Murphy System World Model Connector.

Uses SendGrid Web API v3.
Required credentials: SENDGRID_API_KEY
Setup: https://app.sendgrid.com/settings/api_keys
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class SendGridConnector(BaseIntegrationConnector):
    """SendGrid Web API v3 connector."""

    INTEGRATION_NAME = "SendGrid"
    BASE_URL = "https://api.sendgrid.com/v3"
    CREDENTIAL_KEYS = ["SENDGRID_API_KEY"]
    REQUIRED_CREDENTIALS = ["SENDGRID_API_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://app.sendgrid.com/settings/api_keys"
    DOCUMENTATION_URL = "https://docs.sendgrid.com/api-reference/"

    def _build_headers(self) -> Dict[str, str]:
        api_key = self._credentials.get("SENDGRID_API_KEY", "")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # -- Mail --

    def send_email(self, to_email: str, to_name: str,
                   from_email: str, from_name: str,
                   subject: str, html_content: str,
                   text_content: str = "") -> Dict[str, Any]:
        """Send a transactional email."""
        return self._post("/mail/send", json={
            "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
            "from": {"email": from_email, "name": from_name},
            "subject": subject,
            "content": [
                *(([{"type": "text/plain", "value": text_content}]) if text_content else []),
                {"type": "text/html", "value": html_content},
            ],
        })

    def send_template_email(self, to_email: str,
                            from_email: str, template_id: str,
                            dynamic_template_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send an email using a Dynamic Template."""
        return self._post("/mail/send", json={
            "personalizations": [{
                "to": [{"email": to_email}],
                "dynamic_template_data": dynamic_template_data or {},
            }],
            "from": {"email": from_email},
            "template_id": template_id,
        })

    def send_bulk(self, recipients: List[Dict[str, str]],
                  from_email: str, from_name: str,
                  subject: str, html_content: str) -> Dict[str, Any]:
        """Send to multiple recipients (up to 1000 per request)."""
        return self._post("/mail/send", json={
            "personalizations": [{"to": recipients[:1000]}],
            "from": {"email": from_email, "name": from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_content}],
        })

    # -- Contacts --

    def list_contacts(self, page_size: int = 100) -> Dict[str, Any]:
        return self._post("/marketing/contacts/search", json={
            "query": "email LIKE '%'",
        })

    def upsert_contacts(self, contacts: List[Dict[str, Any]],
                        list_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"contacts": contacts[:30000]}
        if list_ids:
            payload["list_ids"] = list_ids
        return self._put("/marketing/contacts", json=payload)

    def delete_contacts(self, emails: List[str]) -> Dict[str, Any]:
        return self._delete(f"/marketing/contacts?emails={','.join(emails[:100])}")

    # -- Lists --

    def list_contact_lists(self) -> Dict[str, Any]:
        return self._get("/marketing/lists", params={"page_size": 100})

    def create_contact_list(self, name: str) -> Dict[str, Any]:
        return self._post("/marketing/lists", json={"name": name})

    # -- Stats --

    def get_stats(self, start_date: str, end_date: str,
                  aggregated_by: str = "day") -> Dict[str, Any]:
        return self._get("/stats", params={
            "start_date": start_date, "end_date": end_date,
            "aggregated_by": aggregated_by,
        })

    def _delete(self, path: str) -> Dict[str, Any]:
        return self._http("DELETE", path)

    def _put(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._http("PUT", path, json=json)

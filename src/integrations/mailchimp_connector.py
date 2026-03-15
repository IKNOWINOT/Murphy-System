"""
Mailchimp Email Marketing Integration — Murphy System World Model Connector.

Uses Mailchimp Marketing API v3.
Required credentials: MAILCHIMP_API_KEY (contains dc, e.g. key-us1)
Setup: https://mailchimp.com/developer/marketing/guides/quick-start/
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


def _extract_dc(api_key: str) -> str:
    """Extract the data centre suffix from a Mailchimp API key (e.g. 'us1')."""
    match = re.search(r"-([a-z0-9]+)$", api_key)
    return match.group(1) if match else "us1"


class MailchimpConnector(BaseIntegrationConnector):
    """Mailchimp Marketing API v3 connector."""

    INTEGRATION_NAME = "Mailchimp"
    BASE_URL = ""  # dynamic — determined by API key data centre
    CREDENTIAL_KEYS = ["MAILCHIMP_API_KEY"]
    REQUIRED_CREDENTIALS = ["MAILCHIMP_API_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://mailchimp.com/developer/marketing/guides/quick-start/"
    DOCUMENTATION_URL = "https://mailchimp.com/developer/marketing/api/"

    def _base_url(self) -> str:
        api_key = self._credentials.get("MAILCHIMP_API_KEY", "")
        dc = _extract_dc(api_key)
        return f"https://{dc}.api.mailchimp.com/3.0"

    def _build_headers(self) -> Dict[str, str]:
        import base64
        api_key = self._credentials.get("MAILCHIMP_API_KEY", "")
        encoded = base64.b64encode(f"anystring:{api_key}".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }

    def _http(self, method: str, path: str, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        # Override to use dynamic base_url
        self.BASE_URL = self._base_url()
        return super()._http(method, path, **kwargs)

    # -- Lists / Audiences --

    def list_audiences(self) -> Dict[str, Any]:
        return self._get("/lists")

    def create_audience(self, name: str, contact: Dict[str, Any], campaign_defaults: Dict[str, Any],
                        permission_reminder: str) -> Dict[str, Any]:
        return self._post("/lists", json={
            "name": name,
            "contact": contact,
            "campaign_defaults": campaign_defaults,
            "permission_reminder": permission_reminder,
            "email_type_option": True,
        })

    def get_audience(self, list_id: str) -> Dict[str, Any]:
        return self._get(f"/lists/{list_id}")

    # -- Members / Subscribers --

    def list_members(self, list_id: str, count: int = 100) -> Dict[str, Any]:
        return self._get(f"/lists/{list_id}/members", params={"count": min(count, 1000)})

    def add_member(self, list_id: str, email: str, status: str = "subscribed",
                   merge_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post(f"/lists/{list_id}/members", json={
            "email_address": email,
            "status": status,
            "merge_fields": merge_fields or {},
        })

    def update_member(self, list_id: str, email_hash: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._patch(f"/lists/{list_id}/members/{email_hash}", json=data)

    def remove_member(self, list_id: str, email_hash: str) -> Dict[str, Any]:
        return self._delete(f"/lists/{list_id}/members/{email_hash}")

    # -- Campaigns --

    def list_campaigns(self, count: int = 25) -> Dict[str, Any]:
        return self._get("/campaigns", params={"count": min(count, 1000)})

    def create_campaign(self, campaign_type: str, recipients: Dict[str, Any],
                        settings: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/campaigns", json={
            "type": campaign_type,
            "recipients": recipients,
            "settings": settings,
        })

    def send_campaign(self, campaign_id: str) -> Dict[str, Any]:
        return self._post(f"/campaigns/{campaign_id}/actions/send")

    def get_campaign_report(self, campaign_id: str) -> Dict[str, Any]:
        return self._get(f"/reports/{campaign_id}")

    # -- Tags --

    def list_tags(self, list_id: str) -> Dict[str, Any]:
        return self._get(f"/lists/{list_id}/tag-search")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/ping")
        result["integration"] = self.INTEGRATION_NAME
        return result

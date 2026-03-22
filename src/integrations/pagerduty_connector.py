"""
PagerDuty Integration — Murphy System World Model Connector.

Uses PagerDuty REST API v2.
Required credentials: PAGERDUTY_API_KEY
Setup: https://support.pagerduty.com/docs/api-access-keys
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class PagerDutyConnector(BaseIntegrationConnector):
    """PagerDuty REST API v2 connector."""

    INTEGRATION_NAME = "PagerDuty"
    BASE_URL = "https://api.pagerduty.com"
    CREDENTIAL_KEYS = ["PAGERDUTY_API_KEY", "PAGERDUTY_ROUTING_KEY"]
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = "https://support.pagerduty.com/docs/api-access-keys"
    DOCUMENTATION_URL = "https://developer.pagerduty.com/api-reference/"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("PAGERDUTY_API_KEY")
            or self._credentials.get("PAGERDUTY_ROUTING_KEY")
        )

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("PAGERDUTY_API_KEY", "")
        return {
            "Authorization": f"Token token={token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }

    # -- Incidents --

    def list_incidents(self, status: str = "triggered,acknowledged",
                       limit: int = 25) -> Dict[str, Any]:
        return self._get("/incidents",
                         params={"statuses[]": status.split(","),
                                 "limit": min(limit, 100)})

    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        return self._get(f"/incidents/{incident_id}")

    def create_incident(self, title: str, service_id: str,
                        urgency: str = "high",
                        details: str = "") -> Dict[str, Any]:
        return self._post("/incidents", json={
            "incident": {
                "type": "incident",
                "title": title,
                "service": {"id": service_id, "type": "service_reference"},
                "urgency": urgency,
                "body": {"type": "incident_body", "details": details},
            }
        })

    def acknowledge_incident(self, incident_id: str,
                             from_email: str) -> Dict[str, Any]:
        return self._http("PUT", f"/incidents/{incident_id}", json={
            "incident": {"type": "incident", "status": "acknowledged"}
        }, headers={"From": from_email})

    def resolve_incident(self, incident_id: str,
                         from_email: str) -> Dict[str, Any]:
        return self._http("PUT", f"/incidents/{incident_id}", json={
            "incident": {"type": "incident", "status": "resolved"}
        }, headers={"From": from_email})

    # -- Services --

    def list_services(self, limit: int = 25) -> Dict[str, Any]:
        return self._get("/services", params={"limit": min(limit, 100)})

    def get_service(self, service_id: str) -> Dict[str, Any]:
        return self._get(f"/services/{service_id}")

    # -- Alerts via Events v2 API --

    def trigger_alert(self, routing_key: str, summary: str,
                      severity: str = "error",
                      source: str = "murphy-system",
                      custom_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger an alert via the PagerDuty Events v2 API."""
        import httpx
        payload: Dict[str, Any] = {
            "routing_key": routing_key or self._credentials.get("PAGERDUTY_ROUTING_KEY", ""),
            "event_action": "trigger",
            "payload": {
                "summary": summary,
                "severity": severity,
                "source": source,
                "custom_details": custom_details or {},
            },
        }
        try:
            r = httpx.post("https://events.pagerduty.com/v2/enqueue",
                           json=payload, timeout=self._timeout)
            r.raise_for_status()
            return {"success": True, "data": r.json()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # -- On-call --

    def list_oncalls(self, limit: int = 25) -> Dict[str, Any]:
        return self._get("/oncalls", params={"limit": min(limit, 100)})

    def _http(self, method: str, path: str, headers: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        extra = dict(headers or {})
        return super()._http(method, path, **kwargs)

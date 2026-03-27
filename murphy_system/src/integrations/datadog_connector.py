"""
Datadog Monitoring Integration — Murphy System World Model Connector.

Uses Datadog API v1/v2.
Required credentials: DATADOG_API_KEY, DATADOG_APP_KEY
  (optional: DATADOG_SITE, default: datadoghq.com)
Setup: https://docs.datadoghq.com/api/latest/
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class DatadogConnector(BaseIntegrationConnector):
    """Datadog API connector."""

    INTEGRATION_NAME = "Datadog"
    BASE_URL = ""  # dynamic from DATADOG_SITE
    CREDENTIAL_KEYS = ["DATADOG_API_KEY", "DATADOG_APP_KEY", "DATADOG_SITE"]
    REQUIRED_CREDENTIALS = ["DATADOG_API_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://app.datadoghq.com/organization-settings/api-keys"
    DOCUMENTATION_URL = "https://docs.datadoghq.com/api/latest/"

    def _dd_base(self, version: str = "v1") -> str:
        site = self._credentials.get("DATADOG_SITE", "datadoghq.com")
        return f"https://api.{site}/api/{version}"

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "DD-API-KEY": self._credentials.get("DATADOG_API_KEY", ""),
            "Content-Type": "application/json",
        }
        app_key = self._credentials.get("DATADOG_APP_KEY", "")
        if app_key:
            headers["DD-APPLICATION-KEY"] = app_key
        return headers

    def _http(self, method: str, path: str, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        version = "v2" if "/v2/" in path else "v1"
        self.BASE_URL = self._dd_base(version)
        # Strip version prefix from path since it's now in BASE_URL
        path = path.replace("/v1/", "/").replace("/v2/", "/")
        return super()._http(method, path, **kwargs)

    # -- Metrics --

    def submit_metrics(self, series: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._http("POST", "/v1/series", json={"series": series})

    def query_metrics(self, query: str, from_ts: int, to_ts: int) -> Dict[str, Any]:
        return self._http("GET", "/v1/query",
                          params={"query": query, "from": from_ts, "to": to_ts})

    def list_active_metrics(self, host: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if host:
            params["host"] = host
        return self._http("GET", "/v1/metrics", params=params)

    # -- Events --

    def post_event(self, title: str, text: str, alert_type: str = "info",
                   tags: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"title": title, "text": text, "alert_type": alert_type}
        if tags:
            payload["tags"] = tags
        return self._http("POST", "/v1/events", json=payload)

    def get_events(self, start: int, end: int,
                   priority: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"start": start, "end": end}
        if priority:
            params["priority"] = priority
        return self._http("GET", "/v1/events", params=params)

    # -- Monitors --

    def list_monitors(self) -> Dict[str, Any]:
        return self._http("GET", "/v1/monitor")

    def get_monitor(self, monitor_id: int) -> Dict[str, Any]:
        return self._http("GET", f"/v1/monitor/{monitor_id}")

    def create_monitor(self, name: str, type_: str, query: str,
                       message: str = "", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": name, "type": type_, "query": query, "message": message}
        if tags:
            payload["tags"] = tags
        return self._http("POST", "/v1/monitor", json=payload)

    def mute_monitor(self, monitor_id: int) -> Dict[str, Any]:
        return self._http("POST", f"/v1/monitor/{monitor_id}/mute")

    def delete_monitor(self, monitor_id: int) -> Dict[str, Any]:
        return self._http("DELETE", f"/v1/monitor/{monitor_id}")

    # -- Dashboards --

    def list_dashboards(self) -> Dict[str, Any]:
        return self._http("GET", "/v1/dashboard")

    def get_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        return self._http("GET", f"/v1/dashboard/{dashboard_id}")

    # -- Hosts --

    def get_host_totals(self) -> Dict[str, Any]:
        return self._http("GET", "/v1/hosts/totals")

    def list_hosts(self, filter_str: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if filter_str:
            params["filter"] = filter_str
        return self._http("GET", "/v1/hosts", params=params)

    # -- Logs --

    def submit_logs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._http("POST", "/v2/logs", json=logs)

    def list_logs(self, query: str, from_ts: str, to_ts: str,
                  limit: int = 100) -> Dict[str, Any]:
        return self._http("POST", "/v2/logs/events/search", json={
            "filter": {"query": query, "from": from_ts, "to": to_ts},
            "page": {"limit": min(limit, 1000)},
        })

    # -- Incidents --

    def list_incidents(self) -> Dict[str, Any]:
        return self._http("GET", "/v2/incidents")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._http("GET", "/v1/validate")
        result["integration"] = self.INTEGRATION_NAME
        return result

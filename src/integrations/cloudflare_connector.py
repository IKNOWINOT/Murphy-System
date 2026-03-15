"""
Cloudflare DNS/CDN Integration — Murphy System World Model Connector.

Uses Cloudflare API v4.
Required credentials: CLOUDFLARE_API_TOKEN (or CLOUDFLARE_EMAIL + CLOUDFLARE_GLOBAL_API_KEY)
Setup: https://developers.cloudflare.com/api/tokens/create/
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class CloudflareConnector(BaseIntegrationConnector):
    """Cloudflare API v4 connector."""

    INTEGRATION_NAME = "Cloudflare"
    BASE_URL = "https://api.cloudflare.com/client/v4"
    CREDENTIAL_KEYS = [
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_EMAIL",
        "CLOUDFLARE_GLOBAL_API_KEY",
        "CLOUDFLARE_ZONE_ID",
        "CLOUDFLARE_ACCOUNT_ID",
    ]
    FREE_TIER = True
    SETUP_URL = "https://dash.cloudflare.com/profile/api-tokens"
    DOCUMENTATION_URL = "https://developers.cloudflare.com/api/"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("CLOUDFLARE_API_TOKEN")
            or (self._credentials.get("CLOUDFLARE_EMAIL")
                and self._credentials.get("CLOUDFLARE_GLOBAL_API_KEY"))
        )

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("CLOUDFLARE_API_TOKEN", "")
        if token:
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        email = self._credentials.get("CLOUDFLARE_EMAIL", "")
        api_key = self._credentials.get("CLOUDFLARE_GLOBAL_API_KEY", "")
        return {"X-Auth-Email": email, "X-Auth-Key": api_key,
                "Content-Type": "application/json"}

    def _zone_id(self) -> str:
        return self._credentials.get("CLOUDFLARE_ZONE_ID", "")

    def _account_id(self) -> str:
        return self._credentials.get("CLOUDFLARE_ACCOUNT_ID", "")

    # -- Zones --

    def list_zones(self, name: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if name:
            params["name"] = name
        return self._get("/zones", params=params)

    def get_zone(self, zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._get(f"/zones/{zid}")

    def purge_cache(self, zone_id: Optional[str] = None,
                    purge_everything: bool = False,
                    files: Optional[List[str]] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        payload: Dict[str, Any] = {}
        if purge_everything:
            payload["purge_everything"] = True
        elif files:
            payload["files"] = files
        return self._post(f"/zones/{zid}/purge_cache", json=payload)

    # -- DNS Records --

    def list_dns_records(self, zone_id: Optional[str] = None,
                         type_filter: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        params: Dict[str, Any] = {}
        if type_filter:
            params["type"] = type_filter
        return self._get(f"/zones/{zid}/dns_records", params=params)

    def create_dns_record(self, name: str, type_: str, content: str,
                          ttl: int = 1, proxied: bool = True,
                          zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._post(f"/zones/{zid}/dns_records", json={
            "name": name, "type": type_, "content": content,
            "ttl": ttl, "proxied": proxied})

    def update_dns_record(self, record_id: str, updates: Dict[str, Any],
                          zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._http("PATCH", f"/zones/{zid}/dns_records/{record_id}", json=updates)

    def delete_dns_record(self, record_id: str,
                          zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._delete(f"/zones/{zid}/dns_records/{record_id}")

    # -- Workers --

    def list_workers(self) -> Dict[str, Any]:
        account_id = self._account_id()
        return self._get(f"/accounts/{account_id}/workers/scripts")

    def deploy_worker(self, script_name: str, script_content: str) -> Dict[str, Any]:
        account_id = self._account_id()
        return self._http("PUT",
                          f"/accounts/{account_id}/workers/scripts/{script_name}",
                          json={"script": script_content})

    # -- Firewall Rules --

    def list_firewall_rules(self, zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._get(f"/zones/{zid}/firewall/rules")

    # -- Page Rules --

    def list_page_rules(self, zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._get(f"/zones/{zid}/pagerules")

    # -- R2 Storage --

    def list_r2_buckets(self) -> Dict[str, Any]:
        account_id = self._account_id()
        return self._get(f"/accounts/{account_id}/r2/buckets")

    # -- Analytics --

    def get_zone_analytics(self, zone_id: Optional[str] = None) -> Dict[str, Any]:
        zid = zone_id or self._zone_id()
        return self._get(f"/zones/{zid}/analytics/dashboard")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/user/tokens/verify")
        result["integration"] = self.INTEGRATION_NAME
        return result

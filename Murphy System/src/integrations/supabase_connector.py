"""
Supabase Integration — Murphy System World Model Connector.

Uses Supabase REST API (PostgREST + Auth + Storage).
Required credentials: SUPABASE_URL, SUPABASE_KEY (anon or service_role)
Setup: https://supabase.com/docs/guides/getting-started
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class SupabaseConnector(BaseIntegrationConnector):
    """Supabase REST API connector."""

    INTEGRATION_NAME = "Supabase"
    BASE_URL = ""  # dynamic from SUPABASE_URL
    CREDENTIAL_KEYS = ["SUPABASE_URL", "SUPABASE_KEY"]
    REQUIRED_CREDENTIALS = ["SUPABASE_URL", "SUPABASE_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://app.supabase.com"
    DOCUMENTATION_URL = "https://supabase.com/docs/reference/javascript/introduction"

    def _supabase_base(self) -> str:
        return self._credentials.get("SUPABASE_URL", "").rstrip("/")

    def _build_headers(self) -> Dict[str, str]:
        key = self._credentials.get("SUPABASE_KEY", "")
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _http(self, method: str, path: str, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        self.BASE_URL = self._supabase_base()
        return super()._http(method, path, **kwargs)

    # -- PostgREST (database) --

    def select(self, table: str, columns: str = "*",
               filters: Optional[Dict[str, Any]] = None,
               limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        params: Dict[str, Any] = {"select": columns, "limit": min(limit, 1000), "offset": offset}
        if filters:
            for col, val in filters.items():
                params[col] = f"eq.{val}"
        return self._get(f"/rest/v1/{table}", params=params)

    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/rest/v1/{table}", json=data)

    def upsert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("POST", f"/rest/v1/{table}", json=data,
                          headers={"Prefer": "resolution=merge-duplicates,return=representation"})

    def update(self, table: str, filters: Dict[str, Any],
               data: Dict[str, Any]) -> Dict[str, Any]:
        params = {col: f"eq.{val}" for col, val in filters.items()}
        return self._http("PATCH", f"/rest/v1/{table}", params=params, json=data)

    def delete(self, table: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        params = {col: f"eq.{val}" for col, val in filters.items()}
        return self._http("DELETE", f"/rest/v1/{table}", params=params)

    # -- Auth --

    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        return self._post("/auth/v1/signup", json={"email": email, "password": password})

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        return self._post("/auth/v1/token", json={"email": email, "password": password},
                          headers={"Content-Type": "application/json"})

    def get_user(self, access_token: str) -> Dict[str, Any]:
        return self._get("/auth/v1/user", headers={"Authorization": f"Bearer {access_token}"})

    def list_users(self) -> Dict[str, Any]:
        return self._get("/auth/v1/admin/users")

    # -- Storage --

    def list_buckets(self) -> Dict[str, Any]:
        return self._get("/storage/v1/bucket")

    def create_bucket(self, name: str, public: bool = False) -> Dict[str, Any]:
        return self._post("/storage/v1/bucket", json={"id": name, "name": name, "public": public})

    def list_objects(self, bucket: str, path: str = "") -> Dict[str, Any]:
        return self._post(f"/storage/v1/object/list/{bucket}", json={"prefix": path})

    # -- Functions (Edge Functions) --

    def invoke_function(self, function_name: str,
                        payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post(f"/functions/v1/{function_name}", json=payload or {})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/rest/v1/")
        result["integration"] = self.INTEGRATION_NAME
        return result

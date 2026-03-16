"""
Firebase Integration — Murphy System World Model Connector.

Uses Firebase REST APIs (Realtime Database, Firestore, Auth, Storage).
Required credentials: FIREBASE_PROJECT_ID, FIREBASE_WEB_API_KEY
  (optional: FIREBASE_DATABASE_URL, FIREBASE_ACCESS_TOKEN for admin operations)
Setup: https://firebase.google.com/docs/web/setup
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class FirebaseConnector(BaseIntegrationConnector):
    """Firebase REST API connector."""

    INTEGRATION_NAME = "Firebase"
    BASE_URL = ""  # dynamic
    CREDENTIAL_KEYS = [
        "FIREBASE_PROJECT_ID",
        "FIREBASE_WEB_API_KEY",
        "FIREBASE_DATABASE_URL",
        "FIREBASE_ACCESS_TOKEN",
    ]
    REQUIRED_CREDENTIALS = ["FIREBASE_PROJECT_ID"]
    FREE_TIER = True
    SETUP_URL = "https://console.firebase.google.com/"
    DOCUMENTATION_URL = "https://firebase.google.com/docs"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("FIREBASE_PROJECT_ID")
            and (self._credentials.get("FIREBASE_WEB_API_KEY")
                 or self._credentials.get("FIREBASE_ACCESS_TOKEN"))
        )

    def _project_id(self) -> str:
        return self._credentials.get("FIREBASE_PROJECT_ID", "")

    def _web_api_key(self) -> str:
        return self._credentials.get("FIREBASE_WEB_API_KEY", "")

    def _db_url(self) -> str:
        url = self._credentials.get("FIREBASE_DATABASE_URL", "")
        if not url:
            url = f"https://{self._project_id()}-default-rtdb.firebaseio.com"
        return url.rstrip("/")

    def _auth_header(self) -> Dict[str, str]:
        token = self._credentials.get("FIREBASE_ACCESS_TOKEN", "")
        if token:
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        return {"Content-Type": "application/json"}

    # -- Realtime Database --

    def rtdb_get(self, path: str) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("rtdb_get")
        url = f"{self._db_url()}/{path.lstrip('/')}.json"
        return self._http_direct("GET", url, headers=self._auth_header())

    def rtdb_set(self, path: str, data: Any) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("rtdb_set")
        url = f"{self._db_url()}/{path.lstrip('/')}.json"
        return self._http_direct("PUT", url, json=data, headers=self._auth_header())

    def rtdb_push(self, path: str, data: Any) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("rtdb_push")
        url = f"{self._db_url()}/{path.lstrip('/')}.json"
        return self._http_direct("POST", url, json=data, headers=self._auth_header())

    def rtdb_delete(self, path: str) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("rtdb_delete")
        url = f"{self._db_url()}/{path.lstrip('/')}.json"
        return self._http_direct("DELETE", url, headers=self._auth_header())

    # -- Firestore --

    def firestore_list_documents(self, collection: str,
                                 page_size: int = 100) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("firestore_list_documents")
        url = (f"https://firestore.googleapis.com/v1/projects/{self._project_id()}"
               f"/databases/(default)/documents/{collection}")
        params: Dict[str, Any] = {"pageSize": min(page_size, 300)}
        return self._http_direct("GET", url, params=params, headers=self._auth_header())

    def firestore_get_document(self, collection: str, doc_id: str) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("firestore_get_document")
        url = (f"https://firestore.googleapis.com/v1/projects/{self._project_id()}"
               f"/databases/(default)/documents/{collection}/{doc_id}")
        return self._http_direct("GET", url, headers=self._auth_header())

    def firestore_create_document(self, collection: str,
                                  fields: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("firestore_create_document")
        url = (f"https://firestore.googleapis.com/v1/projects/{self._project_id()}"
               f"/databases/(default)/documents/{collection}")
        return self._http_direct("POST", url, json={"fields": fields},
                                 headers=self._auth_header())

    # -- Auth --

    def sign_up_email(self, email: str, password: str) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("sign_up_email")
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={self._web_api_key()}"
        return self._http_direct("POST", url, json={
            "email": email, "password": password, "returnSecureToken": True})

    def sign_in_email(self, email: str, password: str) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("sign_in_email")
        url = (f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
               f"?key={self._web_api_key()}")
        return self._http_direct("POST", url, json={
            "email": email, "password": password, "returnSecureToken": True})

    def _http_direct(self, method: str, url: str, headers: Optional[Dict[str, str]] = None,
                     params: Optional[Dict[str, Any]] = None,
                     json: Optional[Any] = None) -> Dict[str, Any]:
        """Make a direct HTTP call to a full URL (not via BASE_URL prefix)."""
        import threading
        with self._lock:
            self._request_count += 1
        try:
            import httpx
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method, url, headers=headers or {}, params=params, json=json)
            if response.is_success:
                try:
                    data = response.json()
                except Exception as exc:
                    data = response.text
                return {"success": True, "configured": True, "simulated": False,
                        "data": data, "status_code": response.status_code, "error": None}
            with self._lock:
                self._error_count += 1
            return {"success": False, "configured": True, "simulated": False, "data": None,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}: {response.text[:512]}"}
        except ImportError:
            return {"success": False, "configured": True, "simulated": False, "data": None,
                    "error": "httpx not installed; run: pip install httpx"}
        except Exception as exc:
            with self._lock:
                self._error_count += 1
            return {"success": False, "configured": True, "simulated": False,
                    "data": None, "error": str(exc)}

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.rtdb_get(".info/connected")
        result["integration"] = self.INTEGRATION_NAME
        return result

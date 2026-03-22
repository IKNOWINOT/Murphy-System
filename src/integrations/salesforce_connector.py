"""
Salesforce Integration — Murphy System World Model Connector.

Uses Salesforce REST API (Connected App OAuth).
Required credentials: SALESFORCE_USERNAME, SALESFORCE_PASSWORD,
                      SALESFORCE_SECURITY_TOKEN, SALESFORCE_CONSUMER_KEY,
                      SALESFORCE_CONSUMER_SECRET
Setup: https://help.salesforce.com/s/articleView?id=sf.connected_app_create.htm
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class SalesforceConnector(BaseIntegrationConnector):
    """Salesforce REST API connector (Username-Password OAuth flow)."""

    INTEGRATION_NAME = "Salesforce"
    BASE_URL = "https://login.salesforce.com"
    CREDENTIAL_KEYS = [
        "SALESFORCE_USERNAME", "SALESFORCE_PASSWORD",
        "SALESFORCE_SECURITY_TOKEN", "SALESFORCE_CONSUMER_KEY",
        "SALESFORCE_CONSUMER_SECRET", "SALESFORCE_INSTANCE_URL",
    ]
    REQUIRED_CREDENTIALS = ["SALESFORCE_CONSUMER_KEY"]
    FREE_TIER = False
    SETUP_URL = "https://help.salesforce.com/s/articleView?id=sf.connected_app_create.htm"
    DOCUMENTATION_URL = "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/"

    def __init__(self, credentials=None, **kwargs):
        super().__init__(credentials=credentials, **kwargs)
        self._access_token: Optional[str] = None
        self._instance_url: str = self._credentials.get("SALESFORCE_INSTANCE_URL", "")

    def _authenticate(self) -> bool:
        """Obtain an access token via username-password flow."""
        if self._access_token:
            return True
        username = self._credentials.get("SALESFORCE_USERNAME", "")
        password = self._credentials.get("SALESFORCE_PASSWORD", "")
        token = self._credentials.get("SALESFORCE_SECURITY_TOKEN", "")
        consumer_key = self._credentials.get("SALESFORCE_CONSUMER_KEY", "")
        consumer_secret = self._credentials.get("SALESFORCE_CONSUMER_SECRET", "")
        if not (username and password and consumer_key):
            return False
        import httpx
        try:
            r = httpx.post(
                f"{self.BASE_URL}/services/oauth2/token",
                data={
                    "grant_type": "password",
                    "client_id": consumer_key,
                    "client_secret": consumer_secret,
                    "username": username,
                    "password": password + token,
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            self._access_token = data.get("access_token")
            self._instance_url = data.get("instance_url", "")
            return bool(self._access_token)
        except Exception:
            return False

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token or ''}",
            "Content-Type": "application/json",
        }

    def _sf_get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        if not self._authenticate():
            return {"success": False, "error": "Authentication failed"}
        import httpx
        try:
            r = httpx.get(f"{self._instance_url}/services/data/v58.0{path}",
                          headers=self._build_headers(),
                          params=params or {}, timeout=self._timeout)
            r.raise_for_status()
            return {"success": True, "data": r.json(), "configured": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _sf_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._authenticate():
            return {"success": False, "error": "Authentication failed"}
        import httpx
        try:
            r = httpx.post(f"{self._instance_url}/services/data/v58.0{path}",
                           headers=self._build_headers(),
                           json=payload, timeout=self._timeout)
            r.raise_for_status()
            return {"success": True, "data": r.json(), "configured": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # -- Accounts --

    def list_accounts(self, limit: int = 25) -> Dict[str, Any]:
        return self._sf_get("/query",
                            {"q": f"SELECT Id,Name,Phone,Website FROM Account LIMIT {min(limit, 200)}"})

    def get_account(self, account_id: str) -> Dict[str, Any]:
        return self._sf_get(f"/sobjects/Account/{account_id}")

    def create_account(self, name: str,
                       extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._sf_post("/sobjects/Account", {"Name": name, **(extra or {})})

    # -- Contacts --

    def list_contacts(self, limit: int = 25) -> Dict[str, Any]:
        return self._sf_get("/query", {
            "q": f"SELECT Id,FirstName,LastName,Email,Phone FROM Contact LIMIT {min(limit, 200)}"
        })

    def create_contact(self, first_name: str, last_name: str,
                       email: str = "", account_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"FirstName": first_name, "LastName": last_name}
        if email:
            payload["Email"] = email
        if account_id:
            payload["AccountId"] = account_id
        return self._sf_post("/sobjects/Contact", payload)

    # -- Leads --

    def list_leads(self, limit: int = 25) -> Dict[str, Any]:
        return self._sf_get("/query", {
            "q": f"SELECT Id,FirstName,LastName,Email,Status FROM Lead LIMIT {min(limit, 200)}"
        })

    def create_lead(self, first_name: str, last_name: str,
                    company: str, email: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "FirstName": first_name, "LastName": last_name, "Company": company
        }
        if email:
            payload["Email"] = email
        return self._sf_post("/sobjects/Lead", payload)

    # -- Opportunities --

    def list_opportunities(self, limit: int = 25) -> Dict[str, Any]:
        return self._sf_get("/query", {
            "q": (f"SELECT Id,Name,StageName,Amount,CloseDate FROM Opportunity "
                  f"ORDER BY CloseDate DESC LIMIT {min(limit, 200)}")
        })

    # -- SOQL --

    def query(self, soql: str) -> Dict[str, Any]:
        """Execute a raw SOQL query."""
        return self._sf_get("/query", {"q": soql})

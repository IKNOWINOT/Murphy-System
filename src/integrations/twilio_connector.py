"""
Twilio Integration — Murphy System World Model Connector.

Uses Twilio REST API v2010.
Required credentials: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
Setup: https://www.twilio.com/console
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class TwilioConnector(BaseIntegrationConnector):
    """Twilio REST API v2010 connector."""

    INTEGRATION_NAME = "Twilio"
    BASE_URL = "https://api.twilio.com/2010-04-01"
    CREDENTIAL_KEYS = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]
    REQUIRED_CREDENTIALS = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]
    FREE_TIER = True
    SETUP_URL = "https://www.twilio.com/try-twilio"
    DOCUMENTATION_URL = "https://www.twilio.com/docs/usage/api"

    def _build_headers(self) -> Dict[str, str]:
        sid = self._credentials.get("TWILIO_ACCOUNT_SID", "")
        token = self._credentials.get("TWILIO_AUTH_TOKEN", "")
        encoded = base64.b64encode(f"{sid}:{token}".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _account_url(self, path: str) -> str:
        sid = self._credentials.get("TWILIO_ACCOUNT_SID", "ACXXXXX")
        return f"/Accounts/{sid}{path}.json"

    def _http(self, method: str, path: str, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        # Twilio uses form-encoded bodies
        if "json" in kwargs and kwargs["json"] is not None:
            kwargs["data"] = kwargs.pop("json")
        return super()._http(method, path, **kwargs)

    # -- SMS --

    def send_sms(self, to: str, from_: str, body: str) -> Dict[str, Any]:
        """Send an SMS message."""
        return self._post(self._account_url("/Messages"),
                          json={"To": to, "From": from_, "Body": body})

    def list_messages(self, limit: int = 20,
                      to: Optional[str] = None,
                      from_: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"PageSize": min(limit, 100)}
        if to:
            params["To"] = to
        if from_:
            params["From"] = from_
        return self._get(self._account_url("/Messages"), params=params)

    def get_message(self, message_sid: str) -> Dict[str, Any]:
        return self._get(self._account_url(f"/Messages/{message_sid}"))

    # -- Voice --

    def make_call(self, to: str, from_: str, twiml_url: str) -> Dict[str, Any]:
        """Initiate an outbound call."""
        return self._post(self._account_url("/Calls"),
                          json={"To": to, "From": from_, "Url": twiml_url})

    def list_calls(self, limit: int = 20) -> Dict[str, Any]:
        return self._get(self._account_url("/Calls"),
                         params={"PageSize": min(limit, 100)})

    # -- Phone Numbers --

    def list_phone_numbers(self) -> Dict[str, Any]:
        return self._get(self._account_url("/IncomingPhoneNumbers"))

    def list_available_numbers(self, country_code: str = "US",
                               area_code: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if area_code:
            params["AreaCode"] = area_code
        return self._get(f"/AvailablePhoneNumbers/{country_code}/Local.json",
                         params=params)

    # -- Verify --

    def create_verify_service(self, friendly_name: str) -> Dict[str, Any]:
        return self._post("/Services.json",
                          json={"FriendlyName": friendly_name},
                          base_url_override="https://verify.twilio.com/v2")

    def send_verification(self, service_sid: str, to: str,
                          channel: str = "sms") -> Dict[str, Any]:
        return self._post(f"/Services/{service_sid}/Verifications",
                          json={"To": to, "Channel": channel},
                          base_url_override="https://verify.twilio.com/v2")

    def check_verification(self, service_sid: str, to: str,
                           code: str) -> Dict[str, Any]:
        return self._post(f"/Services/{service_sid}/VerificationCheck",
                          json={"To": to, "Code": code},
                          base_url_override="https://verify.twilio.com/v2")

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None,  # type: ignore[override]
              base_url_override: Optional[str] = None) -> Dict[str, Any]:
        if base_url_override:
            original = self.BASE_URL
            self.BASE_URL = base_url_override
            result = super()._post(path, json=json)
            self.BASE_URL = original
            return result
        return super()._post(path, json=json)

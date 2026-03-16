"""
Stripe Payments Integration — Murphy System World Model Connector.

Uses Stripe API v1.
Required credentials: STRIPE_SECRET_KEY
Setup: https://stripe.com/docs/api
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class StripeConnector(BaseIntegrationConnector):
    """Stripe API connector."""

    INTEGRATION_NAME = "Stripe"
    BASE_URL = "https://api.stripe.com/v1"
    CREDENTIAL_KEYS = ["STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY"]
    REQUIRED_CREDENTIALS = ["STRIPE_SECRET_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://dashboard.stripe.com/apikeys"
    DOCUMENTATION_URL = "https://stripe.com/docs/api"

    def _build_headers(self) -> Dict[str, str]:
        secret = self._credentials.get("STRIPE_SECRET_KEY", "")
        import base64
        encoded = base64.b64encode(f"{secret}:".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _http(self, method: str, path: str, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        # Stripe uses form-encoded bodies; convert json→params for POST
        if "json" in kwargs and kwargs["json"] is not None:
            kwargs["params"] = {**kwargs.get("params", {}), **_flatten(kwargs.pop("json"))}
        return super()._http(method, path, **kwargs)

    # -- Customers --

    def list_customers(self, limit: int = 100, email: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if email:
            params["email"] = email
        return self._get("/customers", params=params)

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        return self._get(f"/customers/{customer_id}")

    def create_customer(self, email: str, name: str = "",
                        description: str = "") -> Dict[str, Any]:
        return self._post("/customers", json={"email": email, "name": name,
                                              "description": description})

    def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("POST", f"/customers/{customer_id}", json=updates)

    # -- Payment Intents --

    def create_payment_intent(self, amount: int, currency: str = "usd",
                              customer_id: Optional[str] = None,
                              description: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {"amount": amount, "currency": currency,
                                   "description": description}
        if customer_id:
            payload["customer"] = customer_id
        return self._post("/payment_intents", json=payload)

    def confirm_payment_intent(self, payment_intent_id: str,
                               payment_method: str) -> Dict[str, Any]:
        return self._post(f"/payment_intents/{payment_intent_id}/confirm",
                          json={"payment_method": payment_method})

    def cancel_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        return self._post(f"/payment_intents/{payment_intent_id}/cancel")

    def list_payment_intents(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/payment_intents", params={"limit": min(limit, 100)})

    # -- Subscriptions --

    def list_subscriptions(self, customer_id: Optional[str] = None,
                           status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if customer_id:
            params["customer"] = customer_id
        if status:
            params["status"] = status
        return self._get("/subscriptions", params=params)

    def create_subscription(self, customer_id: str,
                            price_id: str) -> Dict[str, Any]:
        return self._post("/subscriptions", json={
            "customer": customer_id,
            "items": [{"price": price_id}],
        })

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return self._delete(f"/subscriptions/{subscription_id}")

    # -- Products / Prices --

    def list_products(self, active: bool = True) -> Dict[str, Any]:
        return self._get("/products", params={"active": "true" if active else "false"})

    def create_product(self, name: str, description: str = "") -> Dict[str, Any]:
        return self._post("/products", json={"name": name, "description": description})

    def list_prices(self, product_id: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if product_id:
            params["product"] = product_id
        return self._get("/prices", params=params)

    def create_price(self, unit_amount: int, currency: str, product_id: str,
                     recurring: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "unit_amount": unit_amount,
            "currency": currency,
            "product": product_id,
        }
        if recurring:
            payload["recurring"] = recurring
        return self._post("/prices", json=payload)

    # -- Invoices --

    def list_invoices(self, customer_id: Optional[str] = None,
                      limit: int = 100) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if customer_id:
            params["customer"] = customer_id
        return self._get("/invoices", params=params)

    # -- Balance --

    def get_balance(self) -> Dict[str, Any]:
        return self._get("/balance")

    def list_balance_transactions(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/balance_transactions", params={"limit": min(limit, 100)})

    # -- Webhooks --

    def list_webhooks(self) -> Dict[str, Any]:
        return self._get("/webhook_endpoints")

    def create_webhook(self, url: str, events: List[str]) -> Dict[str, Any]:
        return self._post("/webhook_endpoints", json={"url": url, "enabled_events": events})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_balance()
        result["integration"] = self.INTEGRATION_NAME
        return result


def _flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Flatten nested dict for Stripe form-encoding."""
    result: Dict[str, str] = {}
    for key, value in d.items():
        full_key = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten(value, full_key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    result.update(_flatten(item, f"{full_key}[{i}]"))
                else:
                    result[f"{full_key}[{i}]"] = str(item)
        else:
            result[full_key] = str(value)
    return result

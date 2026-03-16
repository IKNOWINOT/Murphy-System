"""
Shopify E-Commerce Integration — Murphy System World Model Connector.

Uses Shopify Admin REST API 2024-01.
Required credentials: SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN
Setup: https://shopify.dev/docs/api/admin-rest
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class ShopifyConnector(BaseIntegrationConnector):
    """Shopify Admin REST API connector."""

    INTEGRATION_NAME = "Shopify"
    BASE_URL = ""  # dynamic — https://{store}.myshopify.com/admin/api/2024-01
    CREDENTIAL_KEYS = ["SHOPIFY_STORE_URL", "SHOPIFY_ACCESS_TOKEN"]
    REQUIRED_CREDENTIALS = ["SHOPIFY_STORE_URL", "SHOPIFY_ACCESS_TOKEN"]
    FREE_TIER = False
    SETUP_URL = "https://shopify.dev/docs/api/admin-rest"
    DOCUMENTATION_URL = "https://shopify.dev/docs/api/admin-rest"

    def _shopify_base(self) -> str:
        store_url = self._credentials.get("SHOPIFY_STORE_URL", "").rstrip("/")
        if not store_url.startswith("http"):
            store_url = f"https://{store_url}"
        return f"{store_url}/admin/api/2024-01"

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("SHOPIFY_ACCESS_TOKEN", "")
        return {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }

    def _http(self, method: str, path: str, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        self.BASE_URL = self._shopify_base()
        return super()._http(method, path, **kwargs)

    # -- Products --

    def list_products(self, limit: int = 50, status: str = "active") -> Dict[str, Any]:
        return self._get("/products.json", params={"limit": min(limit, 250), "status": status})

    def get_product(self, product_id: int) -> Dict[str, Any]:
        return self._get(f"/products/{product_id}.json")

    def create_product(self, title: str, body_html: str = "",
                       vendor: str = "", product_type: str = "",
                       variants: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        product: Dict[str, Any] = {
            "title": title,
            "body_html": body_html,
            "vendor": vendor,
            "product_type": product_type,
        }
        if variants:
            product["variants"] = variants
        return self._post("/products.json", json={"product": product})

    def update_product(self, product_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("PUT", f"/products/{product_id}.json", json={"product": updates})

    def delete_product(self, product_id: int) -> Dict[str, Any]:
        return self._delete(f"/products/{product_id}.json")

    # -- Orders --

    def list_orders(self, limit: int = 50, status: str = "open",
                    financial_status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": min(limit, 250), "status": status}
        if financial_status:
            params["financial_status"] = financial_status
        return self._get("/orders.json", params=params)

    def get_order(self, order_id: int) -> Dict[str, Any]:
        return self._get(f"/orders/{order_id}.json")

    def update_order(self, order_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("PUT", f"/orders/{order_id}.json", json={"order": updates})

    def cancel_order(self, order_id: int) -> Dict[str, Any]:
        return self._post(f"/orders/{order_id}/cancel.json")

    def fulfill_order(self, order_id: int, tracking_number: Optional[str] = None) -> Dict[str, Any]:
        fulfillment: Dict[str, Any] = {}
        if tracking_number:
            fulfillment["tracking_number"] = tracking_number
        return self._post(f"/orders/{order_id}/fulfillments.json",
                          json={"fulfillment": fulfillment})

    # -- Customers --

    def list_customers(self, limit: int = 50) -> Dict[str, Any]:
        return self._get("/customers.json", params={"limit": min(limit, 250)})

    def get_customer(self, customer_id: int) -> Dict[str, Any]:
        return self._get(f"/customers/{customer_id}.json")

    def create_customer(self, email: str, first_name: str = "",
                        last_name: str = "") -> Dict[str, Any]:
        return self._post("/customers.json", json={"customer": {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }})

    def search_customers(self, query: str) -> Dict[str, Any]:
        return self._get("/customers/search.json", params={"query": query})

    # -- Inventory --

    def list_inventory_levels(self, location_ids: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if location_ids:
            params["location_ids"] = location_ids
        return self._get("/inventory_levels.json", params=params)

    def adjust_inventory(self, inventory_item_id: int, location_id: int,
                         adjustment: int) -> Dict[str, Any]:
        return self._post("/inventory_levels/adjust.json", json={
            "inventory_item_id": inventory_item_id,
            "location_id": location_id,
            "available_adjustment": adjustment,
        })

    # -- Analytics --

    def get_reports(self) -> Dict[str, Any]:
        return self._get("/reports.json")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/shop.json")
        result["integration"] = self.INTEGRATION_NAME
        return result

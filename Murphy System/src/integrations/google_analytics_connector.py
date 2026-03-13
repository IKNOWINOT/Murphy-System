"""
Google Analytics 4 (GA4) Integration — Murphy System World Model Connector.

Uses Google Analytics Data API v1 (GA4).
Required credentials: GOOGLE_ANALYTICS_ACCESS_TOKEN, GOOGLE_ANALYTICS_PROPERTY_ID
Setup: https://developers.google.com/analytics/devguides/reporting/data/v1
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class GoogleAnalyticsConnector(BaseIntegrationConnector):
    """Google Analytics 4 Data API connector."""

    INTEGRATION_NAME = "Google Analytics"
    BASE_URL = "https://analyticsdata.googleapis.com/v1beta"
    CREDENTIAL_KEYS = ["GOOGLE_ANALYTICS_ACCESS_TOKEN", "GOOGLE_ANALYTICS_PROPERTY_ID"]
    REQUIRED_CREDENTIALS = ["GOOGLE_ANALYTICS_ACCESS_TOKEN", "GOOGLE_ANALYTICS_PROPERTY_ID"]
    FREE_TIER = True
    SETUP_URL = "https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com"
    DOCUMENTATION_URL = "https://developers.google.com/analytics/devguides/reporting/data/v1"

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("GOOGLE_ANALYTICS_ACCESS_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @property
    def _property_id(self) -> str:
        return self._credentials.get("GOOGLE_ANALYTICS_PROPERTY_ID", "")

    # -- Reports --

    def run_report(self, dimensions: List[str], metrics: List[str],
                   date_ranges: Optional[List[Dict[str, str]]] = None,
                   limit: int = 100) -> Dict[str, Any]:
        """Run a GA4 report."""
        if not date_ranges:
            date_ranges = [{"startDate": "30daysAgo", "endDate": "today"}]
        payload = {
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "dateRanges": date_ranges,
            "limit": min(limit, 1000),
        }
        return self._post(f"/properties/{self._property_id}:runReport", json=payload)

    def run_realtime_report(self, dimensions: List[str],
                            metrics: List[str]) -> Dict[str, Any]:
        payload = {
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
        }
        return self._post(f"/properties/{self._property_id}:runRealtimeReport", json=payload)

    def get_active_users(self) -> Dict[str, Any]:
        return self.run_realtime_report(
            dimensions=["country"],
            metrics=["activeUsers"],
        )

    def get_page_views(self, days: int = 30) -> Dict[str, Any]:
        return self.run_report(
            dimensions=["pagePath"],
            metrics=["screenPageViews", "sessions", "bounceRate"],
            date_ranges=[{"startDate": f"{days}daysAgo", "endDate": "today"}],
        )

    def get_traffic_sources(self, days: int = 30) -> Dict[str, Any]:
        return self.run_report(
            dimensions=["sessionSource", "sessionMedium"],
            metrics=["sessions", "newUsers", "bounceRate"],
            date_ranges=[{"startDate": f"{days}daysAgo", "endDate": "today"}],
        )

    def get_user_demographics(self, days: int = 30) -> Dict[str, Any]:
        return self.run_report(
            dimensions=["country", "city", "deviceCategory"],
            metrics=["activeUsers", "sessions"],
            date_ranges=[{"startDate": f"{days}daysAgo", "endDate": "today"}],
        )

    def get_conversions(self, days: int = 30) -> Dict[str, Any]:
        return self.run_report(
            dimensions=["eventName"],
            metrics=["eventCount", "conversions", "totalRevenue"],
            date_ranges=[{"startDate": f"{days}daysAgo", "endDate": "today"}],
        )

    def batch_run_reports(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._post(f"/properties/{self._property_id}:batchRunReports",
                          json={"requests": requests})

    def get_metadata(self) -> Dict[str, Any]:
        return self._get(f"/properties/{self._property_id}/metadata")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_metadata()
        result["integration"] = self.INTEGRATION_NAME
        return result

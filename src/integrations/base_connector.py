"""
Base Connector — shared foundation for all Murphy System world-model integrations.

Every connector inherits from BaseIntegrationConnector which provides:
  - Credential management (load from env or explicit dict)
  - Lazy httpx client with timeout/retry defaults
  - Graceful "not configured" response when no credentials are set
  - Structured result dict: {success, data, error, configured, simulated}
  - Thread-safe request counting and error tracking
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_NOT_CONFIGURED_TEMPLATE = {
    "success": False,
    "configured": False,
    "simulated": False,
    "error": "Integration not configured — add credentials in Settings or set the required "
             "environment variables.",
    "data": None,
}


class NotConfiguredError(RuntimeError):
    """Raised when a connector has no credentials and cannot proceed."""


class BaseIntegrationConnector:
    """Abstract base for all world-model integration connectors.

    Sub-classes must define:
        - ``CREDENTIAL_KEYS`` (list[str]): env-var names that supply credentials
        - ``INTEGRATION_NAME`` (str): human-readable name
        - ``BASE_URL`` (str): root API URL (may be overridden in __init__)
        - ``REQUIRED_CREDENTIALS`` (list[str]): subset of CREDENTIAL_KEYS that are mandatory
    """

    INTEGRATION_NAME: str = "Unknown"
    BASE_URL: str = ""
    CREDENTIAL_KEYS: List[str] = []
    REQUIRED_CREDENTIALS: List[str] = []
    SETUP_URL: str = ""
    DOCUMENTATION_URL: str = ""
    FREE_TIER: bool = False

    def __init__(
        self,
        credentials: Optional[Dict[str, str]] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self._credentials: Dict[str, str] = {}
        self._timeout = timeout
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._request_count = 0
        self._error_count = 0

        # Load from explicit dict first, then fall back to environment variables
        if credentials:
            self._credentials.update(credentials)

        for key in self.CREDENTIAL_KEYS:
            if key not in self._credentials:
                env_val = os.environ.get(key, "")
                if env_val:
                    self._credentials[key] = env_val

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Return True when all required credentials are present."""
        for key in self.REQUIRED_CREDENTIALS:
            if not self._credentials.get(key):
                return False
        return True

    def configure(self, credentials: Dict[str, str]) -> "BaseIntegrationConnector":
        """Update credentials and return self for chaining."""
        with self._lock:
            self._credentials.update(credentials)
        return self

    def get_status(self) -> Dict[str, Any]:
        """Return connectivity/configuration status."""
        return {
            "integration": self.INTEGRATION_NAME,
            "configured": self.is_configured(),
            "setup_url": self.SETUP_URL,
            "documentation_url": self.DOCUMENTATION_URL,
            "free_tier": self.FREE_TIER,
            "request_count": self._request_count,
            "error_count": self._error_count,
        }

    # ------------------------------------------------------------------
    # HTTP helpers (real calls via httpx, not simulated)
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._http("GET", path, params=params, headers=headers)

    def _post(self, path: str, json: Optional[Any] = None,
              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._http("POST", path, json=json, headers=headers)

    def _patch(self, path: str, json: Optional[Any] = None,
               headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._http("PATCH", path, json=json, headers=headers)

    def _delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._http("DELETE", path, headers=headers)

    def _build_headers(self) -> Dict[str, str]:
        """Build auth headers — override in sub-classes."""
        return {}

    def _http(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return dict(_NOT_CONFIGURED_TEMPLATE)

        base = self.BASE_URL.rstrip("/")
        url = f"{base}/{path.lstrip('/')}"
        merged_headers = {**self._build_headers(), **(headers or {})}

        with self._lock:
            self._request_count += 1

        for attempt in range(1, self._max_retries + 1):
            try:
                import httpx
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.request(
                        method, url,
                        headers=merged_headers,
                        params=params,
                        json=json,
                    )
                if response.is_success:
                    try:
                        data = response.json()
                    except Exception as exc:
                        data = response.text
                    return {
                        "success": True,
                        "configured": True,
                        "simulated": False,
                        "data": data,
                        "status_code": response.status_code,
                        "error": None,
                    }
                with self._lock:
                    self._error_count += 1
                return {
                    "success": False,
                    "configured": True,
                    "simulated": False,
                    "data": None,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}: {response.text[:512]}",
                }
            except ImportError:
                logger.warning("httpx not installed — cannot make real API call to %s", self.INTEGRATION_NAME)
                with self._lock:
                    self._error_count += 1
                return {
                    "success": False,
                    "configured": True,
                    "simulated": False,
                    "data": None,
                    "error": "httpx not installed; run: pip install httpx",
                }
            except Exception as exc:
                if attempt == self._max_retries:
                    with self._lock:
                        self._error_count += 1
                    logger.warning("API call to %s failed: %s", self.INTEGRATION_NAME, exc)
                    return {
                        "success": False,
                        "configured": True,
                        "simulated": False,
                        "data": None,
                        "error": str(exc),
                    }
                wait = 2 ** attempt
                logger.debug("Retrying %s call in %ss (attempt %d/%d)", self.INTEGRATION_NAME, wait, attempt, self._max_retries)
                time.sleep(wait)

        # Should not reach here
        return {
            "success": False,
            "configured": True,
            "simulated": False,
            "data": None,
            "error": "Max retries exceeded",
        }

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def not_configured_response(self, action: str = "") -> Dict[str, Any]:
        """Return a standardised not-configured response."""
        resp = dict(_NOT_CONFIGURED_TEMPLATE)
        if action:
            resp["action"] = action
        resp["integration"] = self.INTEGRATION_NAME
        resp["setup_url"] = self.SETUP_URL
        return resp

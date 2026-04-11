"""
Murphy CLI — HTTP client
========================

Thin wrapper around ``requests`` for Murphy API calls.  Handles auth
header injection, timeout, error envelope parsing, streaming SSE, and
retry with backoff.

Module label: CLI-CLIENT-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants  (CLI-CLIENT-CONST-001)
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_BASE = 1.0   # seconds


# ---------------------------------------------------------------------------
# Response wrapper  (CLI-CLIENT-RESP-001)
# ---------------------------------------------------------------------------

@dataclass
class APIResponse:
    """Normalised API response.  (CLI-CLIENT-RESP-001)"""

    success: bool = False
    status_code: int = 0
    data: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw: Optional[requests.Response] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict.  (CLI-CLIENT-RESP-DICT-001)"""
        d: Dict[str, Any] = {
            "success": self.success,
            "status_code": self.status_code,
        }
        if self.data is not None:
            d["data"] = self.data
        if self.error_code:
            d["error"] = {"code": self.error_code, "message": self.error_message}
        return d


# ---------------------------------------------------------------------------
# Client  (CLI-CLIENT-CORE-001)
# ---------------------------------------------------------------------------

class MurphyClient:
    """HTTP client for the Murphy System API.  (CLI-CLIENT-CORE-001)"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        *,
        verbose: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.verbose = verbose
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "murphy-cli/1.0.0",
            "Accept": "application/json",
        })

    # -- header injection  (CLI-CLIENT-AUTH-001) ----------------------------

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers with auth.  (CLI-CLIENT-AUTH-001)"""
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if extra:
            headers.update(extra)
        return headers

    # -- core request  (CLI-CLIENT-REQ-001) ---------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        retries: int = MAX_RETRIES,
    ) -> APIResponse:
        """Execute an HTTP request with retry.  (CLI-CLIENT-REQ-001)"""
        url = f"{self.base_url}{path}"
        effective_timeout = timeout if timeout is not None else self.timeout

        if self.verbose:
            logger.debug("CLI-CLIENT-REQ-001: %s %s", method, url)

        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                resp = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    data=data,
                    headers=self._headers(headers),
                    timeout=effective_timeout,
                )
                return self._parse_response(resp)
            except requests.ConnectionError as exc:  # CLI-CLIENT-ERR-001
                last_exc = exc
                if attempt < retries - 1:
                    wait = BACKOFF_BASE * (2 ** attempt)
                    logger.debug("CLI-CLIENT-ERR-001: Connection error, retry in %.1fs", wait)
                    time.sleep(wait)
            except requests.Timeout as exc:  # CLI-CLIENT-ERR-002
                last_exc = exc
                logger.debug("CLI-CLIENT-ERR-002: Request timed out after %ds", effective_timeout)
                break  # timeouts are not retried
            except requests.RequestException as exc:  # CLI-CLIENT-ERR-003
                last_exc = exc
                break

        return APIResponse(
            success=False,
            error_code="CLI-CLIENT-ERR-004",
            error_message=f"Request failed after {retries} attempt(s): {last_exc}",
        )

    # -- convenience methods ------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> APIResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> APIResponse:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> APIResponse:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> APIResponse:
        return self.request("DELETE", path, **kwargs)

    # -- streaming SSE  (CLI-CLIENT-STREAM-001) -----------------------------

    def stream_sse(
        self,
        path: str,
        *,
        method: str = "GET",
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        on_event: Optional[Callable[[str, str], None]] = None,
        timeout: Optional[int] = None,
    ) -> Generator[Dict[str, str], None, None]:
        """Stream Server-Sent Events.  (CLI-CLIENT-STREAM-001)

        Yields dicts ``{"event": ..., "data": ...}`` for each SSE frame.
        Optionally calls ``on_event(event_type, data_str)`` inline.
        """
        url = f"{self.base_url}{path}"
        effective_timeout = timeout if timeout is not None else self.timeout

        try:
            resp = self._session.request(
                method=method,
                url=url,
                json=json_body,
                params=params,
                headers=self._headers({"Accept": "text/event-stream"}),
                timeout=effective_timeout,
                stream=True,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:  # CLI-CLIENT-ERR-005
            logger.error("CLI-CLIENT-ERR-005: SSE connection failed: %s", exc)
            return

        event_type = "message"
        data_buffer: list[str] = []

        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line

            if line == "":
                # End of event frame
                if data_buffer:
                    data_str = "\n".join(data_buffer)
                    frame = {"event": event_type, "data": data_str}
                    if on_event:
                        on_event(event_type, data_str)
                    yield frame
                    data_buffer = []
                    event_type = "message"
                continue

            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_buffer.append(line[5:].strip())
            # ignore id:, retry:, comments (:)

    # -- response parsing  (CLI-CLIENT-PARSE-001) ---------------------------

    @staticmethod
    def _parse_response(resp: requests.Response) -> APIResponse:
        """Parse a Murphy API JSON envelope.  (CLI-CLIENT-PARSE-001)"""
        result = APIResponse(status_code=resp.status_code, raw=resp)

        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError):  # CLI-CLIENT-ERR-006
            body = None

        if isinstance(body, dict):
            result.success = body.get("success", resp.ok)
            result.data = body.get("data", body)
            err = body.get("error", {})
            if isinstance(err, dict):
                result.error_code = err.get("code")
                result.error_message = err.get("message")
            elif resp.status_code >= 400:
                result.error_message = str(body)
        elif body is not None:
            result.success = resp.ok
            result.data = body
        else:
            result.success = resp.ok
            if resp.text:
                result.data = resp.text

        if not result.success and not result.error_message:
            result.error_message = f"HTTP {resp.status_code}"
            result.error_code = f"CLI-HTTP-{resp.status_code}"

        return result

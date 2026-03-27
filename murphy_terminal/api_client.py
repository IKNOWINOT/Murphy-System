"""
Murphy Terminal — API Client

Thin wrapper around the Murphy System REST API for terminal interactions.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

from typing import Optional, Tuple, Dict, Any

import requests

from murphy_terminal.config import API_URL


class MurphyAPIClient:
    """Thin wrapper around the Murphy System REST API."""

    def __init__(self, base_url: str = API_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.last_error: Optional[str] = None

    # -- helpers --

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _get(self, path: str) -> Dict[str, Any]:
        resp = requests.get(self._url(path), timeout=self.timeout)
        resp.raise_for_status()
        self.last_error = None
        return resp.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(
            self._url(path), json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        self.last_error = None
        return resp.json()

    def set_base_url(self, url: str) -> None:
        """Update the backend API URL at runtime."""
        self.base_url = url.rstrip("/")
        self.session_id = None
        self.last_error = None

    def test_connection(self) -> Tuple[bool, str]:
        """Test connectivity to backend. Returns (ok, detail_message)."""
        try:
            data = self.health()
            status = data.get("status", "unknown")
            version = data.get("version", "n/a")
            return True, f"Healthy — status={status}, version={version}"
        except requests.ConnectionError:
            msg = f"Connection refused at {self.base_url}"
            self.last_error = msg
            return False, msg
        except requests.Timeout:
            msg = f"Timeout after {self.timeout}s reaching {self.base_url}"
            self.last_error = msg
            return False, msg
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            msg = f"HTTP {code} from {self.base_url}"
            self.last_error = msg
            return False, msg
        except Exception as exc:
            msg = f"Cannot reach {self.base_url}: {type(exc).__name__}"
            self.last_error = msg
            return False, msg

    # -- public API methods --

    def health(self) -> Dict[str, Any]:
        return self._get("/api/health")

    def status(self) -> Dict[str, Any]:
        return self._get("/api/status")

    def info(self) -> Dict[str, Any]:
        return self._get("/api/info")

    def create_session(self, name: Optional[str] = None) -> Dict[str, Any]:
        result = self._post("/api/sessions/create", {"name": name or "terminal"})
        self.session_id = result.get("session_id", self.session_id)
        return result

    def chat(self, message: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"message": message}
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/chat", payload)

    def execute(
        self,
        task_description: str,
        task_type: str = "general",
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "task_description": task_description,
            "task_type": task_type,
        }
        if parameters:
            payload["parameters"] = parameters
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/execute", payload)

    def corrections_stats(self) -> Dict[str, Any]:
        return self._get("/api/corrections/statistics")

    def hitl_pending(self) -> Dict[str, Any]:
        return self._get("/api/hitl/interventions/pending")

    def hitl_stats(self) -> Dict[str, Any]:
        return self._get("/api/hitl/statistics")

    def librarian_ask(self, message: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"message": message}
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/librarian/ask", payload)

    def llm_status(self) -> Dict[str, Any]:
        return self._get("/api/llm/status")

    def configure_llm(self, provider: str, api_key: str) -> Dict[str, Any]:
        """Notify the backend to hot-reload LLM config with the new provider/key."""
        try:
            return self._post("/api/llm/configure", {"provider": provider, "api_key": api_key})
        except requests.RequestException:
            return {"success": False, "error": "backend not reachable"}

    def librarian_status(self) -> Dict[str, Any]:
        return self._get("/api/librarian/status")

    def llm_test(self) -> Dict[str, Any]:
        """Ask the backend to make a minimal test call to verify the LLM key."""
        try:
            return self._post("/api/llm/test", {})
        except requests.RequestException:
            return {"success": False, "error": "backend not reachable"}

    def llm_reload(self) -> Dict[str, Any]:
        """Ask the backend to re-read .env and reinitialise LLM config."""
        try:
            return self._post("/api/llm/reload", {})
        except requests.RequestException:
            return {"success": False, "error": "backend not reachable"}

    def create_document(
        self,
        title: str,
        content: str,
        doc_type: str = "general"
    ) -> Dict[str, Any]:
        """Create a living document for block-command workflows."""
        payload: Dict[str, Any] = {"title": title, "content": content, "type": doc_type}
        if self.session_id:
            payload["session_id"] = self.session_id
        return self._post("/api/documents", payload)

    def magnify_document(self, doc_id: str, domain: str = "general") -> Dict[str, Any]:
        """Expand domain depth of a living document to increase context coverage."""
        return self._post(f"/api/documents/{doc_id}/magnify", {"domain": domain})

    def simplify_document(self, doc_id: str) -> Dict[str, Any]:
        """Reduce complexity of a living document to improve clarity."""
        return self._post(f"/api/documents/{doc_id}/simplify", {})

    def solidify_document(self, doc_id: str) -> Dict[str, Any]:
        """Lock a document and trigger swarm task generation."""
        return self._post(f"/api/documents/{doc_id}/solidify", {})

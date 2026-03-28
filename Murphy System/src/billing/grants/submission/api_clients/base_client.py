# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseApiClient(ABC):
    def __init__(self, api_key: Optional[str] = None, base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url

    def _auth_headers(self) -> Dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _with_retry(self, func, max_retries: int = 3) -> Any:
        """Stub retry logic — Phase B will implement real HTTP retries."""
        return func()

    @abstractmethod
    def submit(self, payload: Dict) -> Dict:
        ...

    @abstractmethod
    def check_status(self, submission_id: str) -> Dict:
        ...

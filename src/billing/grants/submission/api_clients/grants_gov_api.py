# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import Dict, Optional

from src.billing.grants.submission.api_clients.base_client import BaseApiClient

_NOT_IMPLEMENTED = {
    "status": "not_implemented",
    "message": (
        "Direct Grants.gov API submission is planned for Phase B. "
        "Please follow the manual submission instructions."
    ),
}


class GrantsGovApiClient(BaseApiClient):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key, base_url="https://apply07.grants.gov/grantsws/rest")

    def submit(self, payload: Dict) -> Dict:
        return _NOT_IMPLEMENTED.copy()

    def check_status(self, submission_id: str) -> Dict:
        return _NOT_IMPLEMENTED.copy()

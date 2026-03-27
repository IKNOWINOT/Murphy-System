# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import Dict, Optional

from src.billing.grants.submission.api_clients.base_client import BaseApiClient

_NOT_IMPLEMENTED = {
    "status": "not_implemented",
    "message": (
        "Direct SAM.gov API submission is planned for Phase B. "
        "Please follow the manual submission instructions."
    ),
}


class SamGovApiClient(BaseApiClient):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key, base_url="https://api.sam.gov/entity-information/v3")

    def submit(self, payload: Dict) -> Dict:
        return _NOT_IMPLEMENTED.copy()

    def check_status(self, submission_id: str) -> Dict:
        return _NOT_IMPLEMENTED.copy()

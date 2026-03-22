# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from src.billing.grants.submission.api_clients.grants_gov_api import GrantsGovApiClient
from src.billing.grants.submission.api_clients.sam_gov_api import SamGovApiClient


def test_grants_gov_submit_returns_not_implemented():
    client = GrantsGovApiClient()
    result = client.submit({"application_id": "test"})
    assert result["status"] == "not_implemented"


def test_grants_gov_submit_has_message():
    client = GrantsGovApiClient()
    result = client.submit({})
    assert "message" in result
    assert len(result["message"]) > 0


def test_grants_gov_check_status_returns_not_implemented():
    client = GrantsGovApiClient()
    result = client.check_status("submission-001")
    assert result["status"] == "not_implemented"


def test_sam_gov_submit_returns_not_implemented():
    client = SamGovApiClient()
    result = client.submit({"entity_id": "test"})
    assert result["status"] == "not_implemented"


def test_sam_gov_submit_has_message():
    client = SamGovApiClient()
    result = client.submit({})
    assert "message" in result


def test_sam_gov_check_status_returns_not_implemented():
    client = SamGovApiClient()
    result = client.check_status("sam-sub-001")
    assert result["status"] == "not_implemented"

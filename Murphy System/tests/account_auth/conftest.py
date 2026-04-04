"""Tests for the account_auth domain.

pytest.mark.account_auth applied automatically.
Run: pytest -m account_auth

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "account_auth" in str(item.fspath):
            item.add_marker(pytest.mark.account_auth)

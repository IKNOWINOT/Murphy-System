"""Tests for the competitive domain.

pytest.mark.competitive applied automatically.
Run: pytest -m competitive

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "competitive" in str(item.fspath):
            item.add_marker(pytest.mark.competitive)

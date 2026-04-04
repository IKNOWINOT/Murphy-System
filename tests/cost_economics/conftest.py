"""Tests for the cost_economics domain.

pytest.mark.cost_economics applied automatically.
Run: pytest -m cost_economics

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "cost_economics" in str(item.fspath):
            item.add_marker(pytest.mark.cost_economics)

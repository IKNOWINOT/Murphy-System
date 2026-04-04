"""Tests for the resilience domain.

pytest.mark.resilience applied automatically.
Run: pytest -m resilience

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "resilience" in str(item.fspath):
            item.add_marker(pytest.mark.resilience)

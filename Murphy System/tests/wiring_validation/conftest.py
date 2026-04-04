"""Tests for the wiring_validation domain.

pytest.mark.wiring_validation applied automatically.
Run: pytest -m wiring_validation

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "wiring_validation" in str(item.fspath):
            item.add_marker(pytest.mark.wiring_validation)

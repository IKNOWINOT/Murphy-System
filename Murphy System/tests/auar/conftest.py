"""Tests for the auar domain.

pytest.mark.auar applied automatically.
Run: pytest -m auar

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "auar" in str(item.fspath):
            item.add_marker(pytest.mark.auar)

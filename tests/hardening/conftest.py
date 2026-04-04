"""Tests for the hardening domain.

pytest.mark.hardening applied automatically.
Run: pytest -m hardening

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "hardening" in str(item.fspath):
            item.add_marker(pytest.mark.hardening)

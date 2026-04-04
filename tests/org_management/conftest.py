"""
Tests for the org_management domain.

All tests in this directory are automatically marked with
pytest.mark.org_management so they can be run selectively:

    pytest -m org_management          # run only org_management tests
    pytest -m "not org_management"    # skip org_management tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.org_management to all tests in this directory."""
    for item in items:
        if "org_management" in str(item.fspath):
            item.add_marker(pytest.mark.org_management)

"""
Tests for the scheduling domain.

All tests in this directory are automatically marked with
pytest.mark.scheduling so they can be run selectively:

    pytest -m scheduling          # run only scheduling tests
    pytest -m "not scheduling"    # skip scheduling tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.scheduling to all tests in this directory."""
    for item in items:
        if "scheduling" in str(item.fspath):
            item.add_marker(pytest.mark.scheduling)

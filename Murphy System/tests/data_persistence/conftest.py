"""
Tests for the data_persistence domain.

All tests in this directory are automatically marked with
pytest.mark.data_persistence so they can be run selectively:

    pytest -m data_persistence          # run only data_persistence tests
    pytest -m "not data_persistence"    # skip data_persistence tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.data_persistence to all tests in this directory."""
    for item in items:
        if "data_persistence" in str(item.fspath):
            item.add_marker(pytest.mark.data_persistence)

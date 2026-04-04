"""
Tests for the integration_connector domain.

All tests in this directory are automatically marked with
pytest.mark.integration_connector so they can be run selectively:

    pytest -m integration_connector          # run only integration_connector tests
    pytest -m "not integration_connector"    # skip integration_connector tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.integration_connector to all tests in this directory."""
    for item in items:
        if "integration_connector" in str(item.fspath):
            item.add_marker(pytest.mark.integration_connector)

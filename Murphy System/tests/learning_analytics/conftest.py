"""
Tests for the learning_analytics domain.

All tests in this directory are automatically marked with
pytest.mark.learning_analytics so they can be run selectively:

    pytest -m learning_analytics          # run only learning_analytics tests
    pytest -m "not learning_analytics"    # skip learning_analytics tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.learning_analytics to all tests in this directory."""
    for item in items:
        if "learning_analytics" in str(item.fspath):
            item.add_marker(pytest.mark.learning_analytics)

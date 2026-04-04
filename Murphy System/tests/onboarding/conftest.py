"""
Tests for the onboarding domain.

All tests in this directory are automatically marked with
pytest.mark.onboarding so they can be run selectively:

    pytest -m onboarding          # run only onboarding tests
    pytest -m "not onboarding"    # skip onboarding tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.onboarding to all tests in this directory."""
    for item in items:
        if "onboarding" in str(item.fspath):
            item.add_marker(pytest.mark.onboarding)

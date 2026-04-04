"""
Tests for the platform_config domain.

All tests in this directory are automatically marked with
pytest.mark.platform_config so they can be run selectively:

    pytest -m platform_config          # run only platform_config tests
    pytest -m "not platform_config"    # skip platform_config tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.platform_config to all tests in this directory."""
    for item in items:
        if "platform_config" in str(item.fspath):
            item.add_marker(pytest.mark.platform_config)

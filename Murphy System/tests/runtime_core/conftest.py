"""
Tests for the runtime_core domain.

All tests in this directory are automatically marked with
pytest.mark.runtime_core so they can be run selectively:

    pytest -m runtime_core          # run only runtime_core tests
    pytest -m "not runtime_core"    # skip runtime_core tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.runtime_core to all tests in this directory."""
    for item in items:
        if "runtime_core" in str(item.fspath):
            item.add_marker(pytest.mark.runtime_core)

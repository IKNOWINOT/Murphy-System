"""
Robotics, building automation, and energy management tests

Domain: industrial
Marker: @pytest.mark.industrial

All tests in this directory are automatically marked with
pytest.mark.industrial so they can be run selectively:

    pytest -m industrial          # run only industrial tests
    pytest -m "not industrial"    # skip industrial tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.industrial to all tests in this directory."""
    for item in items:
        if "industrial" in str(item.fspath):
            item.add_marker(pytest.mark.industrial)

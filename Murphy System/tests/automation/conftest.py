"""
Automation engine and workflow scheduling tests

Domain: automation
Marker: @pytest.mark.automation

All tests in this directory are automatically marked with
pytest.mark.automation so they can be run selectively:

    pytest -m automation          # run only automation tests
    pytest -m "not automation"    # skip automation tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.automation to all tests in this directory."""
    for item in items:
        if "automation" in str(item.fspath):
            item.add_marker(pytest.mark.automation)

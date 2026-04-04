"""
Bot framework, governance, and telemetry tests

Domain: bots
Marker: @pytest.mark.bots

All tests in this directory are automatically marked with
pytest.mark.bots so they can be run selectively:

    pytest -m bots          # run only bots tests
    pytest -m "not bots"    # skip bots tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.bots to all tests in this directory."""
    for item in items:
        if "bots" in str(item.fspath):
            item.add_marker(pytest.mark.bots)

"""
Communication hub, Matrix bridge, and email tests

Domain: communication
Marker: @pytest.mark.communication

All tests in this directory are automatically marked with
pytest.mark.communication so they can be run selectively:

    pytest -m communication          # run only communication tests
    pytest -m "not communication"    # skip communication tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.communication to all tests in this directory."""
    for item in items:
        if "communication" in str(item.fspath):
            item.add_marker(pytest.mark.communication)

"""
Execution engine, orchestration, and swarm tests

Domain: execution
Marker: @pytest.mark.execution

All tests in this directory are automatically marked with
pytest.mark.execution so they can be run selectively:

    pytest -m execution          # run only execution tests
    pytest -m "not execution"    # skip execution tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.execution to all tests in this directory."""
    for item in items:
        if "execution" in str(item.fspath):
            item.add_marker(pytest.mark.execution)

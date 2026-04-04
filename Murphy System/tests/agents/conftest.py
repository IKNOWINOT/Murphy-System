"""
Agent system, multi-agent coordination, and CI agent tests

Domain: agents
Marker: @pytest.mark.agents

All tests in this directory are automatically marked with
pytest.mark.agents so they can be run selectively:

    pytest -m agents          # run only agents tests
    pytest -m "not agents"    # skip agents tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.agents to all tests in this directory."""
    for item in items:
        if "agents" in str(item.fspath):
            item.add_marker(pytest.mark.agents)

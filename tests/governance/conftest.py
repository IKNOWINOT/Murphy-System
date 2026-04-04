"""
Governance framework, authority gates, and policy tests

Domain: governance
Marker: @pytest.mark.governance

All tests in this directory are automatically marked with
pytest.mark.governance so they can be run selectively:

    pytest -m governance          # run only governance tests
    pytest -m "not governance"    # skip governance tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.governance to all tests in this directory."""
    for item in items:
        if "governance" in str(item.fspath):
            item.add_marker(pytest.mark.governance)

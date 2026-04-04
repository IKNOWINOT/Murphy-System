"""
CI/CD, deployment, containerization, and infrastructure tests

Domain: devops
Marker: @pytest.mark.devops

All tests in this directory are automatically marked with
pytest.mark.devops so they can be run selectively:

    pytest -m devops          # run only devops tests
    pytest -m "not devops"    # skip devops tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.devops to all tests in this directory."""
    for item in items:
        if "devops" in str(item.fspath):
            item.add_marker(pytest.mark.devops)

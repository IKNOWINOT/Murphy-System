"""
Audit, compliance, and security hardening tests

Domain: compliance
Marker: @pytest.mark.compliance

All tests in this directory are automatically marked with
pytest.mark.compliance so they can be run selectively:

    pytest -m compliance          # run only compliance tests
    pytest -m "not compliance"    # skip compliance tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.compliance to all tests in this directory."""
    for item in items:
        if "compliance" in str(item.fspath):
            item.add_marker(pytest.mark.compliance)

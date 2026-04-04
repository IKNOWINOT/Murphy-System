"""
Billing, grants, trading, and financial reporting tests

Domain: finance
Marker: @pytest.mark.finance

All tests in this directory are automatically marked with
pytest.mark.finance so they can be run selectively:

    pytest -m finance          # run only finance tests
    pytest -m "not finance"    # skip finance tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.finance to all tests in this directory."""
    for item in items:
        if "finance" in str(item.fspath):
            item.add_marker(pytest.mark.finance)

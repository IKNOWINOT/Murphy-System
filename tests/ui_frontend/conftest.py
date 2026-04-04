"""
UI, dashboard, terminal, and frontend wiring tests

Domain: ui_frontend
Marker: @pytest.mark.ui_frontend

All tests in this directory are automatically marked with
pytest.mark.ui_frontend so they can be run selectively:

    pytest -m ui_frontend          # run only ui_frontend tests
    pytest -m "not ui_frontend"    # skip ui_frontend tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.ui_frontend to all tests in this directory."""
    for item in items:
        if "ui_frontend" in str(item.fspath):
            item.add_marker(pytest.mark.ui_frontend)

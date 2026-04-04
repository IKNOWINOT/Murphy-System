"""
Tests for the notification_alert domain.

All tests in this directory are automatically marked with
pytest.mark.notification_alert so they can be run selectively:

    pytest -m notification_alert          # run only notification_alert tests
    pytest -m "not notification_alert"    # skip notification_alert tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.notification_alert to all tests in this directory."""
    for item in items:
        if "notification_alert" in str(item.fspath):
            item.add_marker(pytest.mark.notification_alert)

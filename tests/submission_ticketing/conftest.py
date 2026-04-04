"""Tests for the submission_ticketing domain.

pytest.mark.submission_ticketing applied automatically.
Run: pytest -m submission_ticketing

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "submission_ticketing" in str(item.fspath):
            item.add_marker(pytest.mark.submission_ticketing)

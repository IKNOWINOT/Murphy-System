"""
Tests for the workflow_task domain.

All tests in this directory are automatically marked with
pytest.mark.workflow_task so they can be run selectively:

    pytest -m workflow_task          # run only workflow_task tests
    pytest -m "not workflow_task"    # skip workflow_task tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.workflow_task to all tests in this directory."""
    for item in items:
        if "workflow_task" in str(item.fspath):
            item.add_marker(pytest.mark.workflow_task)

"""Tests for the documentation_qa domain.

pytest.mark.documentation_qa applied automatically.
Run: pytest -m documentation_qa

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "documentation_qa" in str(item.fspath):
            item.add_marker(pytest.mark.documentation_qa)

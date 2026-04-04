"""Core module unit tests.

All tests in this directory are automatically marked with
pytest.mark.modules so they can be run selectively:

    pytest -m modules          # run only core module tests
    pytest -m "not modules"    # skip core module tests

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "/modules/" in str(item.fspath):
            item.add_marker(pytest.mark.modules)

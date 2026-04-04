"""Tests for the testing_meta domain.

pytest.mark.testing_meta applied automatically.
Run: pytest -m testing_meta

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "testing_meta" in str(item.fspath):
            item.add_marker(pytest.mark.testing_meta)

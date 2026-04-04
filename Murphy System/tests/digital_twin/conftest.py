"""Tests for the digital_twin domain.

pytest.mark.digital_twin applied automatically.
Run: pytest -m digital_twin

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "digital_twin" in str(item.fspath):
            item.add_marker(pytest.mark.digital_twin)

"""
LLM provider integration and routing tests

Domain: llm
Marker: @pytest.mark.llm

All tests in this directory are automatically marked with
pytest.mark.llm so they can be run selectively:

    pytest -m llm          # run only llm tests
    pytest -m "not llm"    # skip llm tests

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.llm to all tests in this directory."""
    for item in items:
        if "llm" in str(item.fspath):
            item.add_marker(pytest.mark.llm)

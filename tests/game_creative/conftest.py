"""
Tests for the game_creative domain.

All tests in this directory are automatically marked with
pytest.mark.game_creative so they can be run selectively:

    pytest -m game_creative          # run only game_creative tests
    pytest -m "not game_creative"    # skip game_creative tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.game_creative to all tests in this directory."""
    for item in items:
        if "game_creative" in str(item.fspath):
            item.add_marker(pytest.mark.game_creative)

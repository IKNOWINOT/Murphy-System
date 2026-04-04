"""Tests for the content_media domain.

pytest.mark.content_media applied automatically.
Run: pytest -m content_media

Copyright (c) 2020 Inoni Limited Liability Company | License: BSL 1.1
"""
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "content_media" in str(item.fspath):
            item.add_marker(pytest.mark.content_media)

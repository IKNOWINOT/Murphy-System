"""
Tests for the document_export domain.

All tests in this directory are automatically marked with
pytest.mark.document_export so they can be run selectively:

    pytest -m document_export          # run only document_export tests
    pytest -m "not document_export"    # skip document_export tests

Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import pytest


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.document_export to all tests in this directory."""
    for item in items:
        if "document_export" in str(item.fspath):
            item.add_marker(pytest.mark.document_export)

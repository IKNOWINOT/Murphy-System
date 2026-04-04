"""
Test configuration for Murphy System.

sys.path is configured via pyproject.toml [tool.pytest.ini_options] pythonpath,
which adds the project root ("."), "src/", and "strategic/" to sys.path.

Preferred import style in tests:
    from src.xxx import yyy          # always works (src package)
    from confidence_engine import yyy  # works when src/ is in path

Do NOT add ``sys.path`` hacks in test files — the pyproject.toml
pythonpath setting handles it automatically for pytest runs.  For
editable-install / runtime use, ``pip install -e .`` covers it.
"""

import asyncio
import os
import sys


# ---------------------------------------------------------------------------
# Event loop — ensure every test thread has a usable asyncio event loop
# so that tests calling asyncio.get_event_loop().run_until_complete(...)
# work on Python 3.10+ (which no longer auto-creates a loop for
# non-async contexts).
# ---------------------------------------------------------------------------

def pytest_runtest_setup(item):
    """Create a new event loop for each test that lacks one."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


# ---------------------------------------------------------------------------
# Communication Hub — clean slate between tests
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(autouse=True)
def _comms_hub_clean_db(request):
    """
    Before each test in test_communication_hub.py, truncate all comms hub
    tables so tests are fully independent of one another even though they
    share the same SQLite file.
    """
    if "test_communication_hub" not in request.fspath.basename:
        yield
        return

    # Truncate before the test
    _truncate_comms_tables()
    yield
    # No teardown needed — next test will truncate again


def _truncate_comms_tables():
    """Delete all rows from every comms hub table (if the DB is available)."""
    try:
        from src.db import (
            _get_session_factory,
            IMThread, IMMessage,
            CallSession, EmailRecord,
            CommsAutomationRule, CommsModAuditLog,
            CommsBroadcast, CommsUserProfile,
        )
        session = _get_session_factory()()
        try:
            for model in (
                IMMessage, IMThread,
                CallSession, EmailRecord,
                CommsAutomationRule, CommsModAuditLog,
                CommsBroadcast, CommsUserProfile,
            ):
                session.query(model).delete()
            session.commit()
        finally:
            session.close()
    except Exception:
        pass  # DB not available — tests will use in-memory fallback

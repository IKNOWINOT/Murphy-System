"""Tests for ``src/runtime/module_loader.py`` — Class S Roadmap, Item 20 follow-up.

These tests pin the behaviour of :class:`ModuleLoader` so that a future PR can
incrementally migrate the ad-hoc ``try/except`` blocks in
``src/runtime/app.py`` to use the loader without regressing today's
behaviour.

The module is intentionally framework-agnostic — it only knows that it
receives an opaque ``app`` object and calls registered loader callables.
We exercise that contract with a tiny ``_FakeApp`` stand-in so the suite
runs without FastAPI installed.

Coverage:

* ``ModulePriority`` and ``LoadStatus`` enum round-trips
* :class:`ModuleLoadReport` defaults
* :meth:`ModuleLoader.register` accumulates entries in registration order
* :meth:`ModuleLoader.load_all` happy path — every registered loader is
  invoked, ``router_registered`` reflects the loader's return value, and
  ``load_time_ms`` is populated.
* Optional-failure path — failure of an OPTIONAL module is captured in
  the report but does **not** raise.
* Critical-failure path — failure of a CRITICAL module raises
  ``SystemError`` with the failing module's name in the message.
* Mixed registration — convenience accessors (``loaded`` / ``failed`` /
  ``critical_failures`` / ``optional_failures``) bucket reports
  correctly.
* ``ModuleLoaderResult.as_dict`` is JSON-serialisable and contains the
  keys consumed by the planned ``/api/health`` and ``/api/modules``
  endpoints.
* ``ModuleLoaderResult.banner_lines`` produces a clean line for the
  no-failure case and an annotated multi-line block for the
  failures-present case (with truncation at 3 names).
"""

from __future__ import annotations

import json
from typing import Any, List

import pytest

from src.runtime.module_loader import (
    LoadStatus,
    ModuleLoader,
    ModuleLoaderResult,
    ModuleLoadReport,
    ModulePriority,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeApp:
    """Minimal stand-in for the FastAPI ``app`` object.

    Loader callables in real usage call ``app.include_router(...)``; here
    we just record the calls so tests can assert behaviour without
    importing FastAPI.
    """

    def __init__(self) -> None:
        self.included: List[Any] = []

    def include_router(self, router: Any) -> None:
        self.included.append(router)


# ---------------------------------------------------------------------------
# Enums + dataclass defaults
# ---------------------------------------------------------------------------


def test_load_status_enum_string_values() -> None:
    assert LoadStatus.LOADED.value == "loaded"
    assert LoadStatus.FAILED.value == "failed"
    assert LoadStatus.SKIPPED.value == "skipped"


def test_module_priority_enum_string_values() -> None:
    assert ModulePriority.CRITICAL.value == "critical"
    assert ModulePriority.OPTIONAL.value == "optional"


def test_module_load_report_defaults() -> None:
    report = ModuleLoadReport(name="x", priority=ModulePriority.OPTIONAL)
    assert report.name == "x"
    assert report.priority is ModulePriority.OPTIONAL
    assert report.status is LoadStatus.SKIPPED
    assert report.error is None
    assert report.load_time_ms == 0.0
    assert report.router_registered is False


# ---------------------------------------------------------------------------
# register() preserves order
# ---------------------------------------------------------------------------


def test_register_preserves_order() -> None:
    loader = ModuleLoader()
    calls: List[str] = []

    loader.register("first", ModulePriority.OPTIONAL, lambda app: calls.append("first") or False)
    loader.register("second", ModulePriority.OPTIONAL, lambda app: calls.append("second") or False)
    loader.register("third", ModulePriority.OPTIONAL, lambda app: calls.append("third") or False)

    loader.load_all(_FakeApp())

    assert calls == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_all_happy_path_router_and_non_router() -> None:
    loader = ModuleLoader()
    app = _FakeApp()

    sentinel_router = object()

    def _load_router(app: _FakeApp) -> bool:
        app.include_router(sentinel_router)
        return True

    def _load_middleware(app: _FakeApp) -> bool:
        # Middleware-only module — no router registered.
        return False

    loader.register("with_router", ModulePriority.OPTIONAL, _load_router)
    loader.register("middleware_only", ModulePriority.OPTIONAL, _load_middleware)

    result = loader.load_all(app)

    assert isinstance(result, ModuleLoaderResult)
    assert len(result.reports) == 2
    assert all(r.status is LoadStatus.LOADED for r in result.reports)

    by_name = {r.name: r for r in result.reports}
    assert by_name["with_router"].router_registered is True
    assert by_name["middleware_only"].router_registered is False
    # load_time_ms is populated for every report (>= 0, and the field is set).
    assert all(r.load_time_ms >= 0.0 for r in result.reports)
    # The fake app actually saw the include_router call.
    assert app.included == [sentinel_router]


# ---------------------------------------------------------------------------
# Optional failure — captured, not raised
# ---------------------------------------------------------------------------


def test_optional_failure_is_captured_not_raised() -> None:
    loader = ModuleLoader()

    def _broken(app: _FakeApp) -> bool:
        raise RuntimeError("dependency missing")

    loader.register("broken_optional", ModulePriority.OPTIONAL, _broken)

    # Must not raise.
    result = loader.load_all(_FakeApp())

    assert len(result.failed) == 1
    failure = result.failed[0]
    assert failure.name == "broken_optional"
    assert failure.status is LoadStatus.FAILED
    assert failure.error == "dependency missing"
    assert failure.priority is ModulePriority.OPTIONAL
    assert result.optional_failures == [failure]
    assert result.critical_failures == []


# ---------------------------------------------------------------------------
# Critical failure — raises SystemError
# ---------------------------------------------------------------------------


def test_critical_failure_raises_system_error_with_module_name() -> None:
    loader = ModuleLoader()

    def _broken(app: _FakeApp) -> bool:
        raise RuntimeError("DB unavailable")

    loader.register("auth_critical", ModulePriority.CRITICAL, _broken)

    with pytest.raises(SystemError) as exc_info:
        loader.load_all(_FakeApp())

    assert "auth_critical" in str(exc_info.value)
    # The result is still recorded on the loader for post-mortem inspection.
    assert len(loader.result.critical_failures) == 1
    assert loader.result.critical_failures[0].error == "DB unavailable"


def test_critical_failure_lists_all_failing_critical_modules_in_message() -> None:
    loader = ModuleLoader()

    def _broken_a(app: _FakeApp) -> bool:
        raise RuntimeError("a-down")

    def _broken_b(app: _FakeApp) -> bool:
        raise RuntimeError("b-down")

    loader.register("crit_a", ModulePriority.CRITICAL, _broken_a)
    loader.register("crit_b", ModulePriority.CRITICAL, _broken_b)

    with pytest.raises(SystemError) as exc_info:
        loader.load_all(_FakeApp())

    msg = str(exc_info.value)
    assert "crit_a" in msg
    assert "crit_b" in msg


# ---------------------------------------------------------------------------
# Mixed registration — accessor buckets are correct
# ---------------------------------------------------------------------------


def test_mixed_registration_accessor_buckets() -> None:
    loader = ModuleLoader()

    loader.register("ok_opt", ModulePriority.OPTIONAL, lambda app: True)
    loader.register("ok_opt_2", ModulePriority.OPTIONAL, lambda app: False)

    def _broken(app: _FakeApp) -> bool:
        raise ValueError("nope")

    loader.register("bad_opt", ModulePriority.OPTIONAL, _broken)

    result = loader.load_all(_FakeApp())

    assert len(result.loaded) == 2
    assert {r.name for r in result.loaded} == {"ok_opt", "ok_opt_2"}
    assert len(result.failed) == 1
    assert result.failed[0].name == "bad_opt"
    assert result.skipped == []
    assert result.critical_failures == []
    assert len(result.optional_failures) == 1


# ---------------------------------------------------------------------------
# as_dict() — JSON-serialisable, schema for /api/modules
# ---------------------------------------------------------------------------


def test_as_dict_is_json_serialisable_and_has_expected_schema() -> None:
    loader = ModuleLoader()
    loader.register("ok", ModulePriority.OPTIONAL, lambda app: True)

    def _broken(app: _FakeApp) -> bool:
        raise RuntimeError("boom")

    loader.register("bad", ModulePriority.OPTIONAL, _broken)
    result = loader.load_all(_FakeApp())

    payload = result.as_dict()

    # Round-trip through JSON to prove serialisability.
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)

    assert decoded["summary"] == {
        "total": 2,
        "loaded": 1,
        "failed": 1,
        "skipped": 0,
        "critical_failures": 0,
        "optional_failures": 1,
    }
    assert isinstance(decoded["modules"], list)
    assert len(decoded["modules"]) == 2

    module_keys = {"name", "priority", "status", "error", "load_time_ms", "router_registered"}
    for entry in decoded["modules"]:
        assert set(entry.keys()) == module_keys

    by_name = {m["name"]: m for m in decoded["modules"]}
    assert by_name["ok"]["status"] == "loaded"
    assert by_name["ok"]["router_registered"] is True
    assert by_name["bad"]["status"] == "failed"
    assert by_name["bad"]["error"] == "boom"


# ---------------------------------------------------------------------------
# banner_lines() — startup banner output
# ---------------------------------------------------------------------------


def test_banner_lines_no_failures_is_single_line() -> None:
    loader = ModuleLoader()
    loader.register("a", ModulePriority.OPTIONAL, lambda app: True)
    loader.register("b", ModulePriority.OPTIONAL, lambda app: True)

    result = loader.load_all(_FakeApp())
    lines = result.banner_lines()

    assert len(lines) == 1
    assert "2/2 modules loaded" in lines[0]


def test_banner_lines_truncates_failure_names_at_three() -> None:
    loader = ModuleLoader()

    def _make_broken(label: str):
        def _broken(app: _FakeApp) -> bool:
            raise RuntimeError(f"err-{label}")

        return _broken

    # 5 optional failures — banner should truncate at 3 and say "and 2 more".
    for i in range(5):
        loader.register(f"opt_{i}", ModulePriority.OPTIONAL, _make_broken(str(i)))

    result = loader.load_all(_FakeApp())
    text = "\n".join(result.banner_lines())

    assert "0/5 modules loaded" in text
    assert "5 optional unavailable" in text
    assert "opt_0" in text
    assert "opt_1" in text
    assert "opt_2" in text
    assert "and 2 more" in text
    # Names beyond the truncation window are NOT inlined.
    assert "opt_3" not in text
    assert "opt_4" not in text


def test_banner_lines_separates_optional_and_critical_sections() -> None:
    loader = ModuleLoader()

    def _broken_opt(app: _FakeApp) -> bool:
        raise RuntimeError("opt-err")

    def _broken_crit(app: _FakeApp) -> bool:
        raise RuntimeError("crit-err")

    loader.register("ok_one", ModulePriority.OPTIONAL, lambda app: True)
    loader.register("opt_bad", ModulePriority.OPTIONAL, _broken_opt)
    loader.register("crit_bad", ModulePriority.CRITICAL, _broken_crit)

    with pytest.raises(SystemError):
        loader.load_all(_FakeApp())

    text = "\n".join(loader.result.banner_lines())

    assert "1/3 modules loaded" in text
    assert "1 optional unavailable" in text
    assert "opt_bad" in text
    assert "1 CRITICAL failures" in text
    assert "crit_bad" in text

"""
Unit tests for the ModuleLoader framework (ML-001).

Design Label: TEST-ML-001
Owner: QA Team
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

from runtime.module_loader import (
    LoadStatus,
    ModuleLoadReport,
    ModuleLoader,
    ModuleLoaderResult,
    ModulePriority,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _succeeding_loader(_app):
    return True


def _failing_loader(_app):
    raise ImportError("simulated missing dependency")


# ---------------------------------------------------------------------------
# ModuleLoadReport
# ---------------------------------------------------------------------------

class TestModuleLoadReport:
    def test_defaults(self):
        r = ModuleLoadReport(name="billing", priority=ModulePriority.OPTIONAL)
        assert r.status == LoadStatus.SKIPPED
        assert r.error is None
        assert r.load_time_ms == 0.0
        assert r.router_registered is False

    def test_fields(self):
        r = ModuleLoadReport(
            name="security_plane",
            priority=ModulePriority.CRITICAL,
            status=LoadStatus.LOADED,
            error=None,
            load_time_ms=12.5,
            router_registered=True,
        )
        assert r.name == "security_plane"
        assert r.priority == ModulePriority.CRITICAL
        assert r.status == LoadStatus.LOADED
        assert r.load_time_ms == 12.5
        assert r.router_registered is True


# ---------------------------------------------------------------------------
# ModuleLoaderResult
# ---------------------------------------------------------------------------

class TestModuleLoaderResult:
    def _make_result(self):
        reports = [
            ModuleLoadReport("a", ModulePriority.CRITICAL, LoadStatus.LOADED),
            ModuleLoadReport("b", ModulePriority.OPTIONAL, LoadStatus.LOADED),
            ModuleLoadReport("c", ModulePriority.OPTIONAL, LoadStatus.FAILED, error="oops"),
            ModuleLoadReport("d", ModulePriority.CRITICAL, LoadStatus.SKIPPED),
        ]
        return ModuleLoaderResult(reports=reports)

    def test_loaded_filter(self):
        r = self._make_result()
        assert [x.name for x in r.loaded] == ["a", "b"]

    def test_failed_filter(self):
        r = self._make_result()
        assert [x.name for x in r.failed] == ["c"]

    def test_skipped_filter(self):
        r = self._make_result()
        assert [x.name for x in r.skipped] == ["d"]

    def test_critical_failures_empty_when_no_critical_failed(self):
        r = self._make_result()
        assert r.critical_failures == []

    def test_critical_failures_populated(self):
        reports = [
            ModuleLoadReport("db", ModulePriority.CRITICAL, LoadStatus.FAILED, error="conn refused"),
        ]
        r = ModuleLoaderResult(reports=reports)
        assert len(r.critical_failures) == 1
        assert r.critical_failures[0].name == "db"

    def test_optional_failures(self):
        r = self._make_result()
        assert [x.name for x in r.optional_failures] == ["c"]

    def test_as_dict_shape(self):
        r = self._make_result()
        d = r.as_dict()
        assert "summary" in d
        assert "modules" in d
        s = d["summary"]
        assert s["total"] == 4
        assert s["loaded"] == 2
        assert s["failed"] == 1
        assert s["skipped"] == 1
        assert s["critical_failures"] == 0
        assert s["optional_failures"] == 1

    def test_as_dict_module_fields(self):
        r = self._make_result()
        modules_by_name = {m["name"]: m for m in r.as_dict()["modules"]}
        c = modules_by_name["c"]
        assert c["status"] == "failed"
        assert c["error"] == "oops"
        assert c["priority"] == "optional"

    def test_banner_all_loaded(self):
        reports = [ModuleLoadReport("x", ModulePriority.OPTIONAL, LoadStatus.LOADED)]
        r = ModuleLoaderResult(reports=reports)
        lines = r.banner_lines()
        assert len(lines) >= 1
        assert "✅" in lines[0]
        assert "1/1" in lines[0]

    def test_banner_with_failures(self):
        reports = [
            ModuleLoadReport("ok", ModulePriority.OPTIONAL, LoadStatus.LOADED),
            ModuleLoadReport("bad", ModulePriority.OPTIONAL, LoadStatus.FAILED, error="missing"),
        ]
        r = ModuleLoaderResult(reports=reports)
        banner = "\n".join(r.banner_lines())
        assert "⚠️" in banner
        assert "bad" in banner

    def test_banner_truncates_long_failure_list(self):
        reports = [
            ModuleLoadReport(f"opt{i}", ModulePriority.OPTIONAL, LoadStatus.FAILED, error="err")
            for i in range(5)
        ]
        r = ModuleLoaderResult(reports=reports)
        banner = "\n".join(r.banner_lines())
        assert "⚠️" in banner
        assert "…and 2 more" in banner

    def test_banner_with_critical_failures(self):
        reports = [
            ModuleLoadReport("security", ModulePriority.CRITICAL, LoadStatus.FAILED, error="crash"),
        ]
        r = ModuleLoaderResult(reports=reports)
        banner = "\n".join(r.banner_lines())
        assert "❌" in banner
        assert "security" in banner


# ---------------------------------------------------------------------------
# ModuleLoader
# ---------------------------------------------------------------------------

class TestModuleLoader:
    def test_empty_loader(self):
        loader = ModuleLoader()
        result = loader.load_all(object())
        assert len(result.reports) == 0

    def test_successful_optional_module(self):
        loader = ModuleLoader()
        loader.register("billing", ModulePriority.OPTIONAL, _succeeding_loader)
        result = loader.load_all(object())
        assert len(result.reports) == 1
        r = result.reports[0]
        assert r.name == "billing"
        assert r.status == LoadStatus.LOADED
        assert r.router_registered is True
        assert r.error is None

    def test_failing_optional_module_does_not_raise(self):
        loader = ModuleLoader()
        loader.register("mobile", ModulePriority.OPTIONAL, _failing_loader)
        result = loader.load_all(object())
        r = result.reports[0]
        assert r.status == LoadStatus.FAILED
        assert "simulated missing dependency" in r.error

    def test_failing_critical_module_raises(self):
        loader = ModuleLoader()
        loader.register("database", ModulePriority.CRITICAL, _failing_loader)
        with pytest.raises(SystemError, match="database"):
            loader.load_all(object())

    def test_load_time_recorded(self):
        loader = ModuleLoader()
        loader.register("billing", ModulePriority.OPTIONAL, _succeeding_loader)
        result = loader.load_all(object())
        assert result.reports[0].load_time_ms >= 0.0

    def test_result_stored_on_loader(self):
        loader = ModuleLoader()
        loader.register("x", ModulePriority.OPTIONAL, _succeeding_loader)
        result = loader.load_all(object())
        assert loader.result is result

    def test_multiple_modules_mixed_results(self):
        loader = ModuleLoader()
        loader.register("ok1", ModulePriority.OPTIONAL, _succeeding_loader)
        loader.register("fail1", ModulePriority.OPTIONAL, _failing_loader)
        loader.register("ok2", ModulePriority.OPTIONAL, _succeeding_loader)
        result = loader.load_all(object())
        assert len(result.loaded) == 2
        assert len(result.failed) == 1

    def test_critical_failure_still_processes_remaining_modules(self):
        """All modules are attempted before the SystemError is raised."""
        loader = ModuleLoader()
        loader.register("ok", ModulePriority.OPTIONAL, _succeeding_loader)
        loader.register("critical_fail", ModulePriority.CRITICAL, _failing_loader)
        loader.register("ok2", ModulePriority.OPTIONAL, _succeeding_loader)
        with pytest.raises(SystemError):
            loader.load_all(object())
        # All three entries were attempted
        assert len(loader.result.reports) == 3

    def test_register_order_preserved(self):
        loader = ModuleLoader()
        for name in ["alpha", "beta", "gamma"]:
            loader.register(name, ModulePriority.OPTIONAL, _succeeding_loader)
        result = loader.load_all(object())
        assert [r.name for r in result.reports] == ["alpha", "beta", "gamma"]

    def test_loader_callable_receives_app(self):
        received = []

        def _capture_app(_app):
            received.append(_app)
            return True

        sentinel = object()
        loader = ModuleLoader()
        loader.register("test", ModulePriority.OPTIONAL, _capture_app)
        loader.load_all(sentinel)
        assert received == [sentinel]

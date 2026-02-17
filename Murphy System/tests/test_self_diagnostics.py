"""
Tests for the self-diagnostics module.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'murphy_integrated'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'murphy_integrated', 'src'))


class TestModuleHealthChecker:
    """Tests for the ModuleHealthChecker."""

    def test_import(self):
        from self_diagnostics import ModuleHealthChecker
        checker = ModuleHealthChecker()
        assert checker is not None

    def test_run_health_check(self):
        from self_diagnostics import ModuleHealthChecker
        checker = ModuleHealthChecker()
        result = checker.run_health_check()
        assert result is not None
        assert "total_modules" in result
        assert "healthy" in result
        assert "overall_status" in result
        assert "recommendations" in result
        assert result["total_modules"] > 0

    def test_health_check_has_modules(self):
        from self_diagnostics import ModuleHealthChecker
        checker = ModuleHealthChecker()
        result = checker.run_health_check()
        assert len(result["modules"]) > 0
        for module in result["modules"]:
            assert "name" in module
            assert "status" in module
            assert module["status"] in ("healthy", "degraded", "failed", "unknown")

    def test_core_modules_healthy(self):
        from self_diagnostics import ModuleHealthChecker
        checker = ModuleHealthChecker()
        result = checker.run_health_check()
        # At least some core modules should be healthy
        assert result["healthy"] > 0


class TestSystemDiagnostics:
    """Tests for the SystemDiagnostics."""

    def test_import(self):
        from self_diagnostics import SystemDiagnostics
        diag = SystemDiagnostics()
        assert diag is not None

    def test_run_full_diagnostics(self):
        from self_diagnostics import SystemDiagnostics
        diag = SystemDiagnostics()
        result = diag.run_full_diagnostics()
        assert "module_health" in result
        assert "system_resources" in result
        assert "python_environment" in result
        assert "integration_status" in result

    def test_python_environment_check(self):
        from self_diagnostics import SystemDiagnostics
        diag = SystemDiagnostics()
        result = diag._check_python_environment()
        assert result["status"] == "healthy"
        assert "python_version" in result

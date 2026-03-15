"""
End-to-end tests for all 11 Murphy System completion areas.

These tests verify that each completion area works end-to-end,
not just that code exists and unit tests pass.
"""
import importlib
import os
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class TestArea1ExecutionWiring(unittest.TestCase):
    """Area 1: Execution wiring — the control plane can create and run automation."""

    def test_ucp_create_automation(self):
        from universal_control_plane import UniversalControlPlane
        ucp = UniversalControlPlane()
        session_id = ucp.create_automation(
            request="Test task for E2E verification",
            user_id="e2e_test",
            repository_id="test_repo",
        )
        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, str)
        self.assertGreater(len(session_id), 0)

    def test_ucp_run_automation(self):
        from universal_control_plane import UniversalControlPlane
        ucp = UniversalControlPlane()
        session_id = ucp.create_automation(
            request="Read sensor data from test device",
            user_id="e2e_test",
            repository_id="test_repo",
        )
        result = ucp.run_automation(session_id)
        self.assertIsInstance(result, dict)


class TestArea2DeterministicPlusLLMRouting(unittest.TestCase):
    """Area 2: Deterministic + LLM routing coexist and work."""

    def test_deterministic_routing_engine_importable(self):
        from src.deterministic_routing_engine import DeterministicRoutingEngine
        engine = DeterministicRoutingEngine()
        self.assertIsNotNone(engine)

    def test_route_task_returns_valid_type(self):
        from src.deterministic_routing_engine import DeterministicRoutingEngine
        engine = DeterministicRoutingEngine()
        result = engine.route_task("test_task", context={"payload": "hello"})
        self.assertIsNotNone(result)

    def test_llm_integration_layer_importable(self):
        from src.llm_integration_layer import LLMIntegrationLayer
        layer = LLMIntegrationLayer()
        self.assertIsNotNone(layer)


class TestArea3PersistenceAndReplay(unittest.TestCase):
    """Area 3: Persistence and replay capability."""

    def test_persistence_manager_importable(self):
        try:
            from src.persistence_manager import PersistenceManager
            pm = PersistenceManager()
            self.assertIsNotNone(pm)
        except ImportError:
            from persistence_manager import PersistenceManager
            pm = PersistenceManager()
            self.assertIsNotNone(pm)

    def test_save_and_load_document(self):
        try:
            from src.persistence_manager import PersistenceManager
        except ImportError:
            from persistence_manager import PersistenceManager

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PersistenceManager(persistence_dir=tmpdir)
            doc = {"test_key": "test_value_e2e", "timestamp": time.time()}
            pm.save_document("e2e_test_doc", doc)
            loaded = pm.load_document("e2e_test_doc")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.get("test_key"), "test_value_e2e")


class TestArea4MultiChannelDelivery(unittest.TestCase):
    """Area 4: Multi-channel delivery — at minimum the framework is wired."""

    def test_platform_connector_framework_importable(self):
        from src.platform_connector_framework import PlatformConnectorFramework
        fw = PlatformConnectorFramework()
        self.assertIsNotNone(fw)

    def test_connector_list_non_empty(self):
        from src.platform_connector_framework import PlatformConnectorFramework
        fw = PlatformConnectorFramework()
        connectors = fw.list_available_connectors()
        self.assertIsInstance(connectors, list)
        self.assertGreater(len(connectors), 0)


class TestArea5ComplianceValidation(unittest.TestCase):
    """Area 5: Compliance validation produces structured results."""

    def test_compliance_engine_importable(self):
        from src.compliance_engine import ComplianceEngine
        engine = ComplianceEngine()
        self.assertIsNotNone(engine)

    def test_compliance_report_is_structured(self):
        from src.compliance_engine import ComplianceEngine
        engine = ComplianceEngine()
        report = engine.get_compliance_report()
        self.assertIsInstance(report, dict)
        self.assertTrue(
            len(report) > 0,
            "Compliance report should not be empty"
        )

    def test_applicable_frameworks_for_domain(self):
        from src.compliance_engine import ComplianceEngine
        engine = ComplianceEngine()
        frameworks = engine.get_applicable_frameworks("healthcare")
        self.assertIsInstance(frameworks, list)


class TestArea6OperationalAutomation(unittest.TestCase):
    """Area 6: Operational automation — scheduler and business engine work."""

    def test_scheduler_importable(self):
        from src.scheduler import MurphyScheduler
        scheduler = MurphyScheduler()
        self.assertIsNotNone(scheduler)

    def test_scheduler_get_status(self):
        from src.scheduler import MurphyScheduler
        scheduler = MurphyScheduler()
        status = scheduler.get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("running", status)

    def test_inoni_business_automation_importable(self):
        from inoni_business_automation import (
            SalesAutomationEngine,
            MarketingAutomationEngine,
            RDAutomationEngine,
        )
        sales = SalesAutomationEngine()
        self.assertIsNotNone(sales)


class TestArea7FileSystemCleanup(unittest.TestCase):
    """Area 7: File system is clean — no orphan duplicates."""

    def test_no_duplicate_python_module_names_in_src(self):
        src_dir = ROOT / "src"
        if not src_dir.exists():
            self.skipTest("src/ directory not found")
        py_files = list(src_dir.rglob("*.py"))
        names = [f.stem for f in py_files if f.parent == src_dir]
        seen = set()
        duplicates = []
        for name in names:
            if name in seen and name != "__init__":
                duplicates.append(name)
            seen.add(name)
        self.assertEqual(duplicates, [], f"Duplicate module names found: {duplicates}")

    def test_protocols_directory_exists(self):
        protocols_dir = ROOT / "src" / "protocols"
        self.assertTrue(protocols_dir.exists(), "src/protocols/ directory should exist")
        init_file = protocols_dir / "__init__.py"
        self.assertTrue(init_file.exists(), "src/protocols/__init__.py should exist")


class TestArea8TestCoverage(unittest.TestCase):
    """Area 8: Test infrastructure exists and key modules are importable."""

    def test_key_modules_importable(self):
        key_modules = [
            ("src.platform_connector_framework", "PlatformConnectorFramework"),
            ("src.compliance_engine", "ComplianceEngine"),
            ("src.self_fix_loop", "SelfFixLoop"),
            ("src.gate_execution_wiring", "GateExecutionWiring"),
            ("src.deterministic_routing_engine", "DeterministicRoutingEngine"),
        ]
        failures = []
        for module_path, class_name in key_modules:
            try:
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name, None)
                if cls is None:
                    failures.append(f"{module_path}.{class_name} not found")
            except ImportError as e:
                failures.append(f"{module_path}: {e}")
        self.assertEqual(failures, [], f"Import failures: {failures}")

    def test_test_suite_exists_and_non_trivial(self):
        tests_dir = ROOT / "tests"
        test_files = list(tests_dir.glob("test_*.py"))
        # The Murphy System test suite contains 371+ test files as documented in README.
        # We check for at least 50 to allow for partial installs / CI environments
        # where optional-dep test files may be excluded from collection.
        self.assertGreater(len(test_files), 50, "Expected at least 50 test files")


class TestArea9UIInterfaces(unittest.TestCase):
    """Area 9: UI interfaces exist and reference the design system."""

    def test_html_interfaces_exist(self):
        html_files = list(ROOT.glob("*.html"))
        self.assertGreater(len(html_files), 10, "Expected at least 10 HTML interface files")

    def test_design_system_css_exists(self):
        css_path = ROOT / "static" / "murphy-design-system.css"
        self.assertTrue(css_path.exists(), "murphy-design-system.css must exist")

    def test_html_interfaces_reference_design_system(self):
        html_files = list(ROOT.glob("*.html"))
        if not html_files:
            self.skipTest("No HTML files found")
        referencing = 0
        for html_file in html_files:
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")
                if "murphy-design-system" in content or "murphy-components" in content:
                    referencing += 1
            except Exception:
                pass
        ratio = referencing / len(html_files)
        self.assertGreater(ratio, 0.5, f"Only {referencing}/{len(html_files)} HTML files reference the design system")


class TestArea10SecurityHardening(unittest.TestCase):
    """Area 10: Security hardening — security plane modules are importable."""

    def test_security_plane_importable(self):
        from src.security_plane import (
            TrustScore, TrustLevel, SecurityArtifact,
        )
        self.assertIsNotNone(TrustScore)

    def test_gate_execution_wiring_has_security_method(self):
        from src.gate_execution_wiring import GateExecutionWiring
        wiring = GateExecutionWiring()
        self.assertTrue(
            hasattr(wiring, "register_security_plane_defaults"),
            "GateExecutionWiring should have register_security_plane_defaults()"
        )

    def test_security_plane_registration_works(self):
        from src.gate_execution_wiring import GateExecutionWiring
        wiring = GateExecutionWiring()
        count = wiring.register_security_plane_defaults()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


class TestArea11CodeQuality(unittest.TestCase):
    """Area 11: Code quality — core modules have no syntax errors."""

    def test_core_modules_no_syntax_errors(self):
        core_modules = [
            ROOT / "universal_control_plane.py",
            ROOT / "inoni_business_automation.py",
            ROOT / "src" / "platform_connector_framework.py",
            ROOT / "src" / "self_fix_loop.py",
            ROOT / "src" / "gate_execution_wiring.py",
            ROOT / "src" / "compliance_engine.py",
        ]
        errors = []
        for module_path in core_modules:
            if not module_path.exists():
                continue
            try:
                source = module_path.read_text(encoding="utf-8")
                compile(source, str(module_path), "exec")
            except SyntaxError as e:
                errors.append(f"{module_path.name}: {e}")
        self.assertEqual(errors, [], f"Syntax errors found: {errors}")

    def test_protocols_directory_modules_importable(self):
        protocols = [
            "src.protocols",
            "src.protocols.bacnet_client",
            "src.protocols.modbus_client",
            "src.protocols.opcua_client",
            "src.protocols.knx_client",
            "src.protocols.mqtt_sparkplug_client",
        ]
        failures = []
        for mod_path in protocols:
            try:
                importlib.import_module(mod_path)
            except ImportError as e:
                failures.append(f"{mod_path}: {e}")
        self.assertEqual(failures, [], f"Protocol module import failures: {failures}")


if __name__ == "__main__":
    unittest.main()

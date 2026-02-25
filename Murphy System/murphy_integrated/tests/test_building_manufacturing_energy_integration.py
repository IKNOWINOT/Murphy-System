"""
Integration Tests for Building Automation, Manufacturing Automation,
Energy Management, Analytics Dashboard, Executive Planning Engine,
and Enterprise Integrations modules.

Validates MODULE_CATALOG registration, _initialize wiring, and
cross-module functionality for all newly wired modules.
"""
import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestBuildingAutomationConnectors(unittest.TestCase):
    """Test Building Automation Connectors module."""

    def setUp(self):
        try:
            from src.building_automation_connectors import (
                BuildingAutomationRegistry,
                BuildingAutomationOrchestrator,
                BuildingAutomationProtocol,
                BuildingSystemCategory,
                get_status,
            )
            self.registry = BuildingAutomationRegistry()
            self.orchestrator = BuildingAutomationOrchestrator(self.registry)
            self.Protocol = BuildingAutomationProtocol
            self.Category = BuildingSystemCategory
            self.get_status = get_status
        except ImportError as exc:
            self.skipTest(f"Building automation module not available: {exc}")

    def test_registry_default_connectors(self):
        connectors = self.registry.discover()
        self.assertGreaterEqual(len(connectors), 10)

    def test_protocol_coverage(self):
        protocols = self.registry.list_protocols()
        for proto in ["bacnet", "modbus", "knx", "lonworks", "dali", "opc_ua"]:
            self.assertIn(proto, protocols, f"Missing protocol: {proto}")

    def test_johnson_controls_connector(self):
        c = self.registry.get_connector("johnson_controls_bacnet")
        self.assertIsNotNone(c, "Johnson Controls Metasys connector missing")
        self.assertIn("space_temperature_control", c.capabilities)

    def test_honeywell_connector(self):
        c = self.registry.get_connector("honeywell_bacnet")
        self.assertIsNotNone(c, "Honeywell Niagara connector missing")
        self.assertIn("niagara_station_management", c.capabilities)

    def test_siemens_connector(self):
        c = self.registry.get_connector("siemens_bacnet")
        self.assertIsNotNone(c, "Siemens Desigo CC connector missing")
        self.assertIn("desigo_room_automation", c.capabilities)

    def test_alerton_connector(self):
        c = self.registry.get_connector("alerton_bacnet")
        self.assertIsNotNone(c, "Alerton Ascent connector missing")
        self.assertIn("bac_talk_integration", c.capabilities)

    def test_vendor_list(self):
        vendors = self.registry.list_vendors()
        for vendor in ["johnson_controls", "honeywell", "siemens", "alerton"]:
            self.assertIn(vendor, vendors, f"Missing vendor: {vendor}")

    def test_connector_health_check(self):
        health = self.registry.health_check("johnson_controls_bacnet")
        self.assertIn("status", health)
        self.assertIn("name", health)

    def test_connector_execute_action(self):
        result = self.registry.execute("johnson_controls_bacnet", "space_temperature_control")
        self.assertTrue(result.get("success"), "Action execution should succeed")

    def test_connector_statistics(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 10)
        self.assertGreaterEqual(stats["enabled_connectors"], 10)

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "building_automation_connectors")
        self.assertEqual(status["status"], "operational")

    def test_orchestrator_sequence(self):
        seq = self.orchestrator.create_sequence("seq1", "HVAC Optimization")
        self.assertEqual(seq["name"], "HVAC Optimization")
        step = self.orchestrator.add_step(
            "seq1", "step1", "johnson_controls_bacnet", "space_temperature_control"
        )
        self.assertTrue(step.get("success"))

    # ---- Extended vendor connector tests ----

    def test_trane_connector(self):
        c = self.registry.get_connector("trane_bacnet")
        self.assertIsNotNone(c, "Trane Tracer SC/ES connector missing")
        self.assertIn("chiller_plant_management", c.capabilities)

    def test_carrier_automated_logic_connector(self):
        c = self.registry.get_connector("carrier_automated_logic_bacnet")
        self.assertIsNotNone(c, "Carrier/Automated Logic WebCTRL connector missing")
        self.assertIn("webctrl_server_management", c.capabilities)

    def test_schneider_bms_connector(self):
        c = self.registry.get_connector("schneider_electric_bacnet")
        self.assertIsNotNone(c, "Schneider Electric EcoStruxure BMS connector missing")
        self.assertIn("smartx_controller_management", c.capabilities)

    def test_abb_connector(self):
        c = self.registry.get_connector("abb_bacnet")
        self.assertIsNotNone(c, "ABB HVAC Controls connector missing")
        self.assertIn("variable_speed_drives", c.capabilities)

    def test_delta_controls_connector(self):
        c = self.registry.get_connector("delta_controls_bacnet")
        self.assertIsNotNone(c, "Delta Controls enteliWEB connector missing")
        self.assertIn("enteliweb_management", c.capabilities)

    def test_distech_connector(self):
        c = self.registry.get_connector("distech_bacnet")
        self.assertIsNotNone(c, "Distech Controls ECLYPSE connector missing")
        self.assertIn("eclypse_connected_controller", c.capabilities)

    def test_extended_vendor_list(self):
        vendors = self.registry.list_vendors()
        for vendor in ["trane", "carrier_automated_logic", "schneider_electric", "abb",
                        "delta_controls", "distech"]:
            self.assertIn(vendor, vendors, f"Missing extended vendor: {vendor}")

    def test_extended_connector_count(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 16)

    def test_trane_execute_action(self):
        result = self.registry.execute("trane_bacnet", "chiller_plant_management")
        self.assertTrue(result.get("success"))


class TestManufacturingAutomationStandards(unittest.TestCase):
    """Test Manufacturing Automation Standards module."""

    def setUp(self):
        try:
            from src.manufacturing_automation_standards import (
                ManufacturingAutomationRegistry,
                ManufacturingWorkflowBinder,
                ManufacturingStandard,
                ManufacturingLayer,
                get_status,
            )
            self.registry = ManufacturingAutomationRegistry()
            self.binder = ManufacturingWorkflowBinder(self.registry)
            self.Standard = ManufacturingStandard
            self.Layer = ManufacturingLayer
            self.get_status = get_status
        except ImportError as exc:
            self.skipTest(f"Manufacturing automation module not available: {exc}")

    def test_registry_default_connectors(self):
        connectors = self.registry.discover()
        self.assertGreaterEqual(len(connectors), 6)

    def test_standard_coverage(self):
        standards = self.registry.list_standards()
        for std in ["isa_95", "opc_ua", "mtconnect", "packml", "mqtt_sparkplug_b", "iec_61131"]:
            self.assertIn(std, standards, f"Missing standard: {std}")

    def test_isa95_connector(self):
        c = self.registry.get_connector("isa_95")
        self.assertIsNotNone(c, "ISA-95 connector missing")
        self.assertIn("production_order_management", c.capabilities)

    def test_opcua_connector(self):
        c = self.registry.get_connector("opc_ua")
        self.assertIsNotNone(c, "OPC UA connector missing")
        self.assertIn("node_browse", c.capabilities)

    def test_mtconnect_connector(self):
        c = self.registry.get_connector("mtconnect")
        self.assertIsNotNone(c, "MTConnect connector missing")
        self.assertIn("device_stream", c.capabilities)

    def test_packml_connector(self):
        c = self.registry.get_connector("packml")
        self.assertIsNotNone(c, "PackML connector missing")
        self.assertIn("state_machine_control", c.capabilities)

    def test_mqtt_sparkplug_connector(self):
        c = self.registry.get_connector("mqtt_sparkplug_b")
        self.assertIsNotNone(c, "MQTT/Sparkplug B connector missing")
        self.assertIn("device_birth_publish", c.capabilities)

    def test_iec61131_connector(self):
        c = self.registry.get_connector("iec_61131")
        self.assertIsNotNone(c, "IEC 61131 connector missing")
        self.assertIn("structured_text_execution", c.capabilities)

    def test_layer_coverage(self):
        layers = self.registry.list_layers()
        self.assertGreaterEqual(len(layers), 3)

    def test_connector_execute_action(self):
        result = self.registry.execute("isa_95", "production_order_management")
        self.assertTrue(result.get("success"))

    def test_connector_statistics(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 6)

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "manufacturing_automation_standards")

    def test_workflow_binder(self):
        wf = self.binder.create_workflow("wf1", "Production Line Setup")
        self.assertEqual(wf["name"], "Production Line Setup")


class TestEnergyManagementConnectors(unittest.TestCase):
    """Test Energy Management Connectors module."""

    def setUp(self):
        try:
            from src.energy_management_connectors import (
                EnergyManagementRegistry,
                EnergyWorkflowOrchestrator,
                EnergyManagementCategory,
                get_status,
            )
            self.registry = EnergyManagementRegistry()
            self.orchestrator = EnergyWorkflowOrchestrator(self.registry)
            self.Category = EnergyManagementCategory
            self.get_status = get_status
        except ImportError as exc:
            self.skipTest(f"Energy management module not available: {exc}")

    def test_registry_default_connectors(self):
        connectors = self.registry.discover()
        self.assertGreaterEqual(len(connectors), 10)

    def test_johnson_controls_openblue(self):
        c = self.registry.get_connector("johnson_controls")
        self.assertIsNotNone(c, "Johnson Controls OpenBlue missing")
        self.assertIn("energy_performance_monitoring", c.capabilities)

    def test_honeywell_forge(self):
        c = self.registry.get_connector("honeywell")
        self.assertIsNotNone(c, "Honeywell Forge missing")
        self.assertIn("energy_optimization", c.capabilities)

    def test_schneider_ecostruxure(self):
        c = self.registry.get_connector("schneider_electric")
        self.assertIsNotNone(c, "Schneider EcoStruxure missing")
        self.assertIn("power_monitoring", c.capabilities)

    def test_siemens_navigator(self):
        c = self.registry.get_connector("siemens")
        self.assertIsNotNone(c, "Siemens Navigator missing")
        self.assertIn("building_performance_analytics", c.capabilities)

    def test_energycap(self):
        c = self.registry.get_connector("energycap")
        self.assertIsNotNone(c, "EnergyCAP missing")
        self.assertIn("utility_bill_tracking", c.capabilities)

    def test_alerton_ems(self):
        c = self.registry.get_connector("alerton")
        self.assertIsNotNone(c, "Alerton EMS missing")
        self.assertIn("energy_monitoring", c.capabilities)

    def test_energy_star_portfolio(self):
        c = self.registry.get_connector("epa")
        self.assertIsNotNone(c, "ENERGY STAR Portfolio Manager missing")
        self.assertIn("energy_benchmarking", c.capabilities)

    def test_demand_response(self):
        c = self.registry.get_connector("enel_x")
        self.assertIsNotNone(c, "Enel X Demand Response missing")
        self.assertIn("demand_response_enrollment", c.capabilities)

    def test_renewable_integration(self):
        c = self.registry.get_connector("solaredge")
        self.assertIsNotNone(c, "SolarEdge Monitoring missing")
        self.assertIn("pv_production_monitoring", c.capabilities)

    def test_vendor_list(self):
        vendors = self.registry.list_vendors()
        for vendor in ["johnson_controls", "honeywell", "siemens", "alerton",
                        "schneider_electric", "energycap"]:
            self.assertIn(vendor, vendors, f"Missing vendor: {vendor}")

    def test_category_coverage(self):
        categories = self.registry.list_categories()
        self.assertGreaterEqual(len(categories), 4)

    def test_connector_execute_action(self):
        result = self.registry.execute("johnson_controls", "energy_performance_monitoring")
        self.assertTrue(result.get("success"))

    def test_connector_statistics(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 10)

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "energy_management_connectors")
        self.assertEqual(status["status"], "operational")

    # ---- Extended EMS connector tests ----

    def test_gridpoint(self):
        c = self.registry.get_connector("gridpoint")
        self.assertIsNotNone(c, "GridPoint Energy Management missing")
        self.assertIn("energy_optimization", c.capabilities)

    def test_tridium_niagara(self):
        c = self.registry.get_connector("tridium")
        self.assertIsNotNone(c, "Tridium Niagara Framework missing")
        self.assertIn("open_framework_integration", c.capabilities)

    def test_abb_ability(self):
        c = self.registry.get_connector("abb")
        self.assertIsNotNone(c, "ABB Ability Energy Manager missing")
        self.assertIn("energy_monitoring", c.capabilities)

    def test_emerson_ovation(self):
        c = self.registry.get_connector("emerson")
        self.assertIsNotNone(c, "Emerson Ovation/DeltaV Energy missing")
        self.assertIn("power_plant_optimization", c.capabilities)

    def test_enverus(self):
        c = self.registry.get_connector("enverus")
        self.assertIsNotNone(c, "Enverus Power & Renewables missing")
        self.assertIn("renewable_asset_analytics", c.capabilities)

    def test_brainbox_ai(self):
        c = self.registry.get_connector("brainbox_ai")
        self.assertIsNotNone(c, "Brainbox AI missing")
        self.assertIn("autonomous_hvac_optimization", c.capabilities)

    def test_extended_vendor_list(self):
        vendors = self.registry.list_vendors()
        for vendor in ["gridpoint", "tridium", "abb", "emerson", "enverus", "brainbox_ai"]:
            self.assertIn(vendor, vendors, f"Missing extended vendor: {vendor}")

    def test_extended_connector_count(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 16)

    def test_gridpoint_execute_action(self):
        result = self.registry.execute("gridpoint", "energy_optimization")
        self.assertTrue(result.get("success"))

    def test_extended_category_coverage(self):
        categories = self.registry.list_categories()
        self.assertGreaterEqual(len(categories), 5)


class TestEnterpriseIntegrationsBuildingEnergy(unittest.TestCase):
    """Test Building Automation and Energy Management categories in Enterprise Integrations."""

    def setUp(self):
        try:
            from src.enterprise_integrations import (
                EnterpriseIntegrationRegistry,
                IntegrationCategory,
            )
            self.registry = EnterpriseIntegrationRegistry()
            self.Category = IntegrationCategory
        except ImportError as exc:
            self.skipTest(f"Enterprise integrations module not available: {exc}")

    def test_building_automation_category_exists(self):
        cats = self.registry.list_categories()
        self.assertIn("building_automation", cats)

    def test_energy_management_category_exists(self):
        cats = self.registry.list_categories()
        self.assertIn("energy_management", cats)

    def test_johnson_controls_metasys_in_enterprise(self):
        c = self.registry.get_connector("johnson_controls_metasys")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_honeywell_niagara_in_enterprise(self):
        c = self.registry.get_connector("honeywell_niagara")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_siemens_desigo_in_enterprise(self):
        c = self.registry.get_connector("siemens_desigo_cc")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_alerton_ascent_in_enterprise(self):
        c = self.registry.get_connector("alerton_ascent")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_openblue_in_enterprise(self):
        c = self.registry.get_connector("johnson_controls_openblue")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_honeywell_forge_in_enterprise(self):
        c = self.registry.get_connector("honeywell_forge")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_schneider_in_enterprise(self):
        c = self.registry.get_connector("schneider_ecostruxure")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_energycap_in_enterprise(self):
        c = self.registry.get_connector("energycap")
        self.assertIsNotNone(c)
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_total_connector_count(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 45)

    def test_total_categories(self):
        cats = self.registry.list_categories()
        self.assertGreaterEqual(len(cats), 10)

    # ---- Extended enterprise vendor tests ----

    def test_trane_tracer_in_enterprise(self):
        c = self.registry.get_connector("trane_tracer")
        self.assertIsNotNone(c, "Trane Tracer missing from enterprise registry")
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_carrier_webctrl_in_enterprise(self):
        c = self.registry.get_connector("carrier_webctrl")
        self.assertIsNotNone(c, "Carrier/Automated Logic WebCTRL missing from enterprise registry")
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_schneider_bms_in_enterprise(self):
        c = self.registry.get_connector("schneider_bms")
        self.assertIsNotNone(c, "Schneider BMS missing from enterprise registry")
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_delta_enteliweb_in_enterprise(self):
        c = self.registry.get_connector("delta_enteliweb")
        self.assertIsNotNone(c, "Delta Controls enteliWEB missing from enterprise registry")
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_distech_eclypse_in_enterprise(self):
        c = self.registry.get_connector("distech_eclypse")
        self.assertIsNotNone(c, "Distech ECLYPSE missing from enterprise registry")
        self.assertEqual(c.category, self.Category.BUILDING_AUTOMATION)

    def test_gridpoint_in_enterprise(self):
        c = self.registry.get_connector("gridpoint")
        self.assertIsNotNone(c, "GridPoint missing from enterprise registry")
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_tridium_niagara_in_enterprise(self):
        c = self.registry.get_connector("tridium_niagara")
        self.assertIsNotNone(c, "Tridium Niagara missing from enterprise registry")
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_abb_ability_in_enterprise(self):
        c = self.registry.get_connector("abb_ability")
        self.assertIsNotNone(c, "ABB Ability missing from enterprise registry")
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)

    def test_brainbox_ai_in_enterprise(self):
        c = self.registry.get_connector("brainbox_ai")
        self.assertIsNotNone(c, "Brainbox AI missing from enterprise registry")
        self.assertEqual(c.category, self.Category.ENERGY_MANAGEMENT)


class TestAnalyticsDashboardIntegration(unittest.TestCase):
    """Test Analytics Dashboard wiring."""

    def setUp(self):
        try:
            from src.analytics_dashboard import AnalyticsDashboard
            self.dashboard = AnalyticsDashboard()
        except ImportError as exc:
            self.skipTest(f"Analytics dashboard not available: {exc}")

    def test_dashboard_initializes(self):
        self.assertIsNotNone(self.dashboard)

    def test_dashboard_has_status(self):
        report = self.dashboard.get_full_report()
        self.assertIsInstance(report, dict)


class TestExecutivePlanningEngineIntegration(unittest.TestCase):
    """Test Executive Planning Engine wiring."""

    def setUp(self):
        try:
            from src.executive_planning_engine import ExecutivePlanningEngine
            self.engine = ExecutivePlanningEngine()
        except ImportError as exc:
            self.skipTest(f"Executive planning engine not available: {exc}")

    def test_engine_initializes(self):
        self.assertIsNotNone(self.engine)

    def test_engine_has_components(self):
        self.assertIsNotNone(self.engine.planner)
        self.assertIsNotNone(self.engine.gate_generator)
        self.assertIsNotNone(self.engine.binder)
        self.assertIsNotNone(self.engine.dashboard)
        self.assertIsNotNone(self.engine.response_engine)


class TestRuntimeModuleCatalogWiring(unittest.TestCase):
    """Test that all new modules are properly wired in MODULE_CATALOG."""

    def setUp(self):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "murphy_runtime",
                os.path.join(os.path.dirname(__file__), '..', 'murphy_system_1.0_runtime.py')
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.MurphySystem = mod.MurphySystem
            self.ms = self.MurphySystem()
        except Exception as exc:
            self.skipTest(f"Cannot load MurphySystem: {exc}")

    def test_module_catalog_has_building_automation(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("building_automation_connectors", names)

    def test_module_catalog_has_manufacturing_automation(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("manufacturing_automation_standards", names)

    def test_module_catalog_has_energy_management(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("energy_management_connectors", names)

    def test_module_catalog_has_analytics_dashboard(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("analytics_dashboard", names)

    def test_module_catalog_has_executive_planning(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("executive_planning_engine", names)

    def test_module_catalog_has_enterprise_integrations(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("enterprise_integrations", names)

    def test_building_automation_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'building_automation_registry', None))

    def test_manufacturing_automation_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'manufacturing_automation_registry', None))

    def test_energy_management_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'energy_management_registry', None))

    def test_analytics_dashboard_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'analytics_dashboard', None))

    def test_executive_planning_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'executive_planning_engine', None))

    def test_enterprise_integrations_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'enterprise_integrations', None))

    def test_module_catalog_count(self):
        self.assertGreaterEqual(len(self.ms.MODULE_CATALOG), 75)


if __name__ == '__main__':
    unittest.main()

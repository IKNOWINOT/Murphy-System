"""Tests for universal_ingestion_framework.py"""
import pytest, sys, os

from universal_ingestion_framework import (
    AdapterRegistry, GRAINGER_BEST_SELLERS, IngestionFormat,
    BACnetEDEAdapter, ModbusRegisterMapAdapter,
    ComponentRecommendation, IngestionResult,
)


@pytest.fixture
def registry():
    return AdapterRegistry()

SAMPLE_EDE = """object-name\tobject-type\tobject-identifier\tdescription\tunits-code
SAT\tanalog-input\t0\tSupply Air Temp\t62
RAT\tanalog-input\t1\tReturn Air Temp\t62
CC_POS\tanalog-output\t0\tCooling Coil Valve\t98"""

SAMPLE_MODBUS = """address,register_type,description,units
40001,holding,Chiller Enable,
40002,holding,Chilled Water Setpoint,degF"""

SAMPLE_CSV = "point_name,point_type,description,units\nSAT,AI,Supply Air Temp,degF\nCC,AO,Cooling Coil,pct"

class TestGraingerCatalog:
    def test_11_categories(self): assert len(GRAINGER_BEST_SELLERS) == 11
    def test_each_has_items(self):
        for cat, items in GRAINGER_BEST_SELLERS.items():
            assert len(items) >= 1, f"Category {cat} must have items"
    def test_items_have_ashrae_reference(self):
        for cat, items in GRAINGER_BEST_SELLERS.items():
            for item in items:
                assert item.why_recommended, f"Item in {cat} must have why_recommended"

class TestAdapterRegistry:
    def test_has_adapters(self, registry): assert len(registry._adapters) >= 5
    def test_auto_detect_ede(self, registry):
        result = registry.auto_detect_and_ingest(SAMPLE_EDE, "ahu.ede")
        assert result.records_ingested >= 3
        assert "BACnet" in result.adapter_name or "EDE" in result.adapter_name or "bacnet" in result.adapter_name
    def test_auto_detect_modbus(self, registry):
        result = registry.auto_detect_and_ingest(SAMPLE_MODBUS, "ch01.csv")
        assert result.records_ingested >= 1
    def test_auto_detect_csv(self, registry):
        result = registry.auto_detect_and_ingest(SAMPLE_CSV, "points.csv")
        assert result.records_ingested >= 1
    def test_result_has_equipment_specs(self, registry):
        result = registry.auto_detect_and_ingest(SAMPLE_EDE, "ahu.ede")
        assert hasattr(result, "equipment_specs") or hasattr(result, "points")
    def test_get_component_recs(self, registry):
        recs = registry.get_component_recommendations("AHU", "hvac")
        assert len(recs) >= 1

class TestEDEAdapter:
    def test_can_handle_ede(self):
        a = BACnetEDEAdapter()
        assert a.can_handle(SAMPLE_EDE, "ahu.ede")
    def test_parses_3_points(self):
        a = BACnetEDEAdapter()
        r = a.ingest(SAMPLE_EDE)
        assert r.records_ingested >= 3
    def test_schema(self):
        a = BACnetEDEAdapter()
        s = a.get_schema()
        assert "description" in s or "fields" in s

class TestModbusAdapter:
    def test_can_handle_modbus(self):
        a = ModbusRegisterMapAdapter()
        assert a.can_handle(SAMPLE_MODBUS)
    def test_parses_registers(self):
        a = ModbusRegisterMapAdapter()
        r = a.ingest(SAMPLE_MODBUS)
        assert r.records_ingested >= 1

class TestIngestionResult:
    def test_summary(self):
        r = IngestionResult(result_id="test", adapter_name="Test", format_used=IngestionFormat.CSV.value,
                             records_ingested=5, records_failed=0, warnings=[], equipment_specs=[],
                             component_recommendations=[], raw_data={},
                             ingested_at="2026-01-01T00:00:00Z")
        assert "5" in r.summary()
    def test_to_dict(self):
        r = IngestionResult(result_id="test", adapter_name="Test", format_used=IngestionFormat.CSV.value,
                             records_ingested=1, records_failed=0, warnings=[], equipment_specs=[],
                             component_recommendations=[], raw_data={},
                             ingested_at="2026-01-01T00:00:00Z")
        d = r.to_dict()
        assert "adapter_name" in d

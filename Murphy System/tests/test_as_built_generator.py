"""Tests for as_built_generator.py"""
import pytest, sys, os

from as_built_generator import (
    AsBuiltGenerator, DrawingDatabase, DrawingElement, DrawingElementType,
    ControlDiagram, PointScheduleEntry,
)


@pytest.fixture
def gen():
    return AsBuiltGenerator()

@pytest.fixture
def db():
    return DrawingDatabase()

@pytest.fixture
def simple_diagram():
    d = ControlDiagram(title="Test", system_name="AHU-TEST")
    d.elements.append(DrawingElement(element_type=DrawingElementType.EQUIPMENT_TAG,
                                      tag="AHU-01", description="Air Handling Unit",
                                      manufacturer="Carrier", model="39N"))
    d.elements.append(DrawingElement(element_type=DrawingElementType.INSTRUMENT_TAG,
                                      tag="SAT-01", description="Supply Air Temp Sensor",
                                      manufacturer="Dwyer", model="RSBT-A",
                                      cutsheet_reference="DWY.pdf"))
    d.point_schedule.append(PointScheduleEntry(point_name="SAT", point_type="AI",
                                                 description="Supply Air Temp", engineering_units="degF"))
    return d

class TestDrawingDatabase:
    def test_ingest(self, db, simple_diagram):
        n = db.ingest_drawing(simple_diagram)
        assert n == 2
    def test_len(self, db, simple_diagram):
        db.ingest_drawing(simple_diagram)
        assert len(db) == 2
    def test_dedup(self, db, simple_diagram):
        db.ingest_drawing(simple_diagram)
        db.ingest_drawing(simple_diagram)
        removed = db.deduplicate()
        assert removed >= 0
    def test_search(self, db, simple_diagram):
        db.ingest_drawing(simple_diagram)
        results = db.search("SAT")
        assert any(e.tag == "SAT-01" for e in results)
    def test_get_best(self, db, simple_diagram):
        db.ingest_drawing(simple_diagram)
        best = db.get_best_element(DrawingElementType.INSTRUMENT_TAG, "SAT")
        assert best is not None
        assert best.manufacturer == "Dwyer"
    def test_export_catalog(self, db, simple_diagram):
        db.ingest_drawing(simple_diagram)
        cat = db.export_catalog()
        assert len(cat) == 2

class TestAsBuiltFromSpec:
    def test_from_spec_dict(self, gen):
        class FakeSpec:
            equipment_name = "CH-01"
            description = "Centrifugal Chiller"
            manufacturer = "Trane"
            model_number = "CentraVac"
            control_points = [
                {"name":"CHWS_TEMP","point_type":"AI","description":"Chilled Water Supply Temp","units":"degF"},
                {"name":"CHWS_FLOW","point_type":"AI","description":"CHW Flow","units":"GPM"},
            ]
        d = gen.from_equipment_spec(FakeSpec(), "CH-01")
        assert len(d.point_schedule) == 2
        assert any(p.point_name == "CHWS_TEMP" for p in d.point_schedule)
    def test_from_virtual_controller_like(self, gen):
        class FakePoint:
            name = "SAT"; object_type = "analog-input"; object_instance = 0
            description = "Supply Air Temp"; engineering_units = "degF"
        class FakeVC:
            controller_id = "VC-01"
            points = [FakePoint()]
        d = gen.from_virtual_controller(FakeVC(), "AHU-01")
        assert len(d.point_schedule) == 1

class TestMergeWithDatabase:
    def test_enriches_empty_fields(self, gen, db, simple_diagram):
        db.ingest_drawing(simple_diagram)
        new_diag = ControlDiagram(title="New", system_name="AHU-NEW")
        new_diag.elements.append(DrawingElement(element_type=DrawingElementType.INSTRUMENT_TAG,
                                                  tag="SAT-01", description="SAT"))
        merged = gen.merge_with_database(new_diag, db)
        sat = next((e for e in merged.elements if e.tag == "SAT-01"), None)
        assert sat is not None
        assert sat.manufacturer == "Dwyer"

class TestGenerateMethods:
    def test_point_schedule(self, gen, simple_diagram):
        sched = gen.generate_point_schedule(simple_diagram)
        assert len(sched) == 1
        assert sched[0]["point_type"] == "AI"
    def test_schematic_description(self, gen, simple_diagram):
        desc = gen.generate_schematic_description(simple_diagram)
        assert "AHU-01" in desc and "CONTROL SCHEMATIC" in desc
    def test_proposal_check_complete(self, gen, simple_diagram):
        result = gen.check_proposal_completeness(simple_diagram, ["AHU-01"])
        assert result["complete"] is True
    def test_proposal_check_missing(self, gen, simple_diagram):
        result = gen.check_proposal_completeness(simple_diagram, ["AHU-01","MISSING_POINT"])
        assert "MISSING_POINT" in result["missing"]
    def test_export(self, gen, simple_diagram):
        export = gen.export_as_built(simple_diagram)
        assert export["point_count"] == 1 and "diagram" in export

class TestDiagramSummary:
    def test_summary(self, simple_diagram):
        s = simple_diagram.summary()
        assert "Test" in s and "AHU-TEST" in s
    def test_to_dict(self, simple_diagram):
        d = simple_diagram.to_dict()
        assert "diagram_id" in d and "elements" in d

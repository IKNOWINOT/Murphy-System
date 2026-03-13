"""
Tests for Murphy Drawing Engine (Subsystem 1).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import pytest

from src.murphy_drawing_engine import (
    AgenticDrawingAssistant,
    BOMExtractor,
    Discipline,
    DrawingElement,
    DrawingExporter,
    DrawingProject,
    DrawingSheet,
    ElementType,
    SheetSize,
    TitleBlock,
    ParametricConstraint,
    ConstraintType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project():
    return DrawingProject(name="Test Project", discipline=Discipline.MECHANICAL)


@pytest.fixture
def project_with_sheet(project):
    sheet = DrawingSheet(size=SheetSize.ANSI_D)
    project.sheets.append(sheet)
    return project


@pytest.fixture
def assistant(project):
    return AgenticDrawingAssistant(project)


# ---------------------------------------------------------------------------
# DrawingProject
# ---------------------------------------------------------------------------

class TestDrawingProject:

    def test_creation(self, project):
        assert project.name == "Test Project"
        assert project.discipline == Discipline.MECHANICAL
        assert project.project_id is not None

    def test_default_units(self, project):
        assert project.units == "imperial"

    def test_multiple_disciplines(self):
        for disc in Discipline:
            p = DrawingProject(name=f"{disc.value} project", discipline=disc)
            assert p.discipline == disc


# ---------------------------------------------------------------------------
# DrawingSheet and elements
# ---------------------------------------------------------------------------

class TestDrawingSheet:

    def test_default_sheet(self):
        sheet = DrawingSheet()
        assert sheet.sheet_id is not None
        assert sheet.elements == []

    def test_all_sheet_sizes(self):
        for size in SheetSize:
            sheet = DrawingSheet(size=size)
            assert sheet.size == size

    def test_title_block_defaults(self):
        tb = TitleBlock()
        assert tb.revision == "A"
        assert tb.pe_stamp_id is None


# ---------------------------------------------------------------------------
# DrawingElement
# ---------------------------------------------------------------------------

class TestDrawingElement:

    def test_line_element(self):
        elem = DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "z1": 0, "x2": 10, "y2": 0, "z2": 0},
        )
        assert elem.element_type == ElementType.LINE
        assert elem.element_id is not None

    def test_all_element_types(self):
        for etype in ElementType:
            elem = DrawingElement(element_type=etype)
            assert elem.element_type == etype


# ---------------------------------------------------------------------------
# ParametricConstraint
# ---------------------------------------------------------------------------

class TestParametricConstraint:

    def test_constraint_creation(self):
        c = ParametricConstraint(
            constraint_type=ConstraintType.PARALLEL,
            element_ids=["e1", "e2"],
        )
        assert c.constraint_type == ConstraintType.PARALLEL
        assert len(c.element_ids) == 2


# ---------------------------------------------------------------------------
# BOM Extractor
# ---------------------------------------------------------------------------

class TestBOMExtractor:

    def test_empty_project(self, project):
        bom = BOMExtractor().extract(project)
        assert bom == []

    def test_extracts_block_refs(self, project):
        sheet = DrawingSheet()
        sheet.elements.append(DrawingElement(
            element_type=ElementType.BLOCK_REF,
            properties={"block_name": "BOLT_M10", "quantity": 4, "part_number": "BLT-M10"},
        ))
        project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert len(bom) == 1
        assert bom[0]["block_name"] == "BOLT_M10"
        assert bom[0]["quantity"] == 4

    def test_ignores_non_block_elements(self, project):
        sheet = DrawingSheet()
        sheet.elements.append(DrawingElement(element_type=ElementType.LINE))
        project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert len(bom) == 0


# ---------------------------------------------------------------------------
# Drawing Exporter
# ---------------------------------------------------------------------------

class TestDrawingExporter:

    def test_dxf_header(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "z1": 0, "x2": 10, "y2": 0, "z2": 0},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "SECTION" in dxf
        assert "ENTITIES" in dxf
        assert "EOF" in dxf
        assert "LINE" in dxf

    def test_dxf_circle(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": 5, "cy": 5, "cz": 0, "radius": 3},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "CIRCLE" in dxf

    def test_svg_output(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": 50, "cy": 50, "radius": 20},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "svg" in svg
        assert "circle" in svg

    def test_svg_rectangle(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.RECTANGLE,
            geometry={"x": 10, "y": 10, "width": 30, "height": 20},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "rect" in svg

    def test_pdf_placeholder(self, project_with_sheet):
        result = DrawingExporter().to_pdf_placeholder(project_with_sheet)
        assert result["project_id"] == project_with_sheet.project_id
        assert result["format"] == "PDF"


# ---------------------------------------------------------------------------
# Agentic Drawing Assistant
# ---------------------------------------------------------------------------

class TestAgenticDrawingAssistant:

    def test_draw_rectangle(self, assistant, project):
        result = assistant.execute("draw a 10x20 rectangle at origin")
        assert result["success"] is True
        assert len(project.sheets) == 1
        assert project.sheets[0].elements[0].element_type == ElementType.RECTANGLE

    def test_draw_rectangle_dimensions(self, assistant, project):
        assistant.execute("draw a 10x20 rectangle at origin")
        elem = project.sheets[0].elements[0]
        assert elem.geometry["width"] == 10.0
        assert elem.geometry["height"] == 20.0

    def test_draw_circle(self, assistant, project):
        result = assistant.execute("add a circle radius 5 at 10,10")
        assert result["success"] is True
        assert project.sheets[0].elements[0].element_type == ElementType.CIRCLE

    def test_draw_circle_radius(self, assistant, project):
        assistant.execute("add a circle radius 7 at 0,0")
        elem = project.sheets[0].elements[0]
        assert elem.geometry["radius"] == 7.0

    def test_add_text(self, assistant, project):
        result = assistant.execute("add text 'Murphy Drawing' at 0,0")
        assert result["success"] is True
        elem = project.sheets[0].elements[0]
        assert elem.element_type == ElementType.TEXT
        assert elem.properties["text"] == "Murphy Drawing"

    def test_draw_line(self, assistant, project):
        result = assistant.execute("draw line from (0,0) to (10,10)")
        assert result["success"] is True
        assert project.sheets[0].elements[0].element_type == ElementType.LINE

    def test_create_sheet(self, assistant, project):
        result = assistant.execute("create sheet A1")
        assert result["success"] is True
        assert any(s.size == SheetSize.A1 for s in project.sheets)

    def test_unknown_command(self, assistant):
        result = assistant.execute("do something impossible")
        assert result["success"] is False

    def test_command_log(self, assistant):
        assistant.execute("draw a 5x5 rectangle at origin")
        log = assistant.get_command_log()
        assert len(log) == 1
        assert "rectangle" in log[0]["command"].lower()

    def test_multiple_commands(self, assistant, project):
        assistant.execute("draw a 10x20 rectangle at origin")
        assistant.execute("add a circle radius 3 at 5,5")
        assert len(project.sheets[0].elements) == 2


# ---------------------------------------------------------------------------
# Production-readiness tests (30+ new cases)
# ---------------------------------------------------------------------------

class TestDXFExporterProduction:

    def test_dxf_structure_markers(self, project_with_sheet):
        """DXF output must have SECTION/HEADER/ENTITIES/ENDSEC/EOF markers."""
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "0\nSECTION" in dxf
        assert "2\nHEADER" in dxf
        assert "0\nENDSEC" in dxf
        assert "2\nENTITIES" in dxf
        assert "0\nEOF" in dxf

    def test_dxf_text_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": 1.0, "y": 2.0, "z": 0.0, "height": 5.0},
            properties={"text": "TEST_LABEL"},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "TEXT" in dxf
        assert "TEST_LABEL" in dxf

    def test_dxf_empty_project(self, project):
        dxf = DrawingExporter().to_dxf(project)
        assert "SECTION" in dxf
        assert "EOF" in dxf

    def test_dxf_multiple_elements(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(element_type=ElementType.LINE, geometry={"x1": 0, "y1": 0, "z1": 0, "x2": 5, "y2": 5, "z2": 0}))
        sheet.elements.append(DrawingElement(element_type=ElementType.CIRCLE, geometry={"cx": 10, "cy": 10, "cz": 0, "radius": 3}))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert dxf.count("LINE") >= 1
        assert dxf.count("CIRCLE") >= 1

    def test_dxf_line_coordinates(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 1.5, "y1": 2.5, "z1": 0, "x2": 8.0, "y2": 9.0, "z2": 0},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "1.5" in dxf
        assert "8.0" in dxf


class TestSVGExporterProduction:

    def test_svg_is_valid_xml(self, project_with_sheet):
        """SVG output must be well-formed XML."""
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 10, "y2": 10}))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_svg_polygon_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.POLYGON,
            geometry={"vertices": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 5, "y": 10}]},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "polygon" in svg
        assert "points=" in svg

    def test_svg_arc_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.ARC,
            geometry={"cx": 50, "cy": 50, "radius": 20, "start_angle": 0, "end_angle": 90},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<path" in svg

    def test_svg_text_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": 5, "y": 10, "height": 12},
            properties={"text": "Hello"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "Hello" in svg
        assert "<text" in svg

    def test_svg_custom_dimensions(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet, width=1200, height=900)
        assert 'width="1200"' in svg
        assert 'height="900"' in svg

    def test_svg_xml_declaration(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert svg.startswith('<?xml')


class TestBOMExtractorProduction:

    def test_bom_multiple_block_refs(self, project):
        sheet = DrawingSheet()
        for i in range(3):
            sheet.elements.append(DrawingElement(
                element_type=ElementType.BLOCK_REF,
                properties={"block_name": f"PART_{i}", "quantity": i + 1},
            ))
        project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert len(bom) == 3
        assert bom[0]["item_number"] == 1
        assert bom[2]["item_number"] == 3

    def test_bom_mixed_elements(self, project):
        sheet = DrawingSheet()
        sheet.elements.append(DrawingElement(element_type=ElementType.LINE))
        sheet.elements.append(DrawingElement(element_type=ElementType.BLOCK_REF, properties={"block_name": "VALVE", "quantity": 2}))
        sheet.elements.append(DrawingElement(element_type=ElementType.CIRCLE))
        project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert len(bom) == 1
        assert bom[0]["block_name"] == "VALVE"

    def test_bom_across_multiple_sheets(self, project):
        for i in range(2):
            sheet = DrawingSheet()
            sheet.elements.append(DrawingElement(
                element_type=ElementType.BLOCK_REF,
                properties={"block_name": f"COMP_{i}", "quantity": 1},
            ))
            project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert len(bom) == 2

    def test_bom_part_number_default(self, project):
        sheet = DrawingSheet()
        sheet.elements.append(DrawingElement(element_type=ElementType.BLOCK_REF, properties={"block_name": "X"}))
        project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert bom[0]["part_number"] == ""

    def test_bom_includes_sheet_id(self, project):
        sheet = DrawingSheet()
        sheet.elements.append(DrawingElement(element_type=ElementType.BLOCK_REF, properties={"block_name": "WIDGET"}))
        project.sheets.append(sheet)
        bom = BOMExtractor().extract(project)
        assert bom[0]["sheet_id"] == sheet.sheet_id


class TestAgenticDrawingAssistantProduction:

    def test_empty_command(self, assistant):
        result = assistant.execute("")
        assert result["success"] is False

    def test_draw_polygon(self, assistant, project):
        result = assistant.execute("draw polygon (0,0) (10,0) (5,10)")
        assert result["success"] is True
        assert project.sheets[0].elements[0].element_type == ElementType.POLYGON

    def test_polygon_default_vertices(self, assistant, project):
        """Polygon with fewer than 3 coords gets default triangle."""
        result = assistant.execute("draw polygon")
        assert result["success"] is True
        verts = project.sheets[0].elements[0].geometry["vertices"]
        assert len(verts) == 3

    def test_rectangle_coords(self, assistant, project):
        assistant.execute("draw a 5x15 rectangle at 3,7")
        elem = project.sheets[0].elements[0]
        assert elem.geometry["width"] == 5.0
        assert elem.geometry["height"] == 15.0
        assert elem.geometry["x"] == 3.0
        assert elem.geometry["y"] == 7.0

    def test_malformed_coords_rectangle(self, assistant, project):
        """Command with no coords should use defaults."""
        result = assistant.execute("draw a rectangle")
        assert result["success"] is True
        elem = project.sheets[0].elements[0]
        assert elem.geometry["x"] == 0.0

    def test_circle_default_radius(self, assistant, project):
        result = assistant.execute("add a circle at origin")
        assert result["success"] is True
        assert project.sheets[0].elements[0].geometry["radius"] == 5.0

    def test_line_single_point_defaults(self, assistant, project):
        """Line with only one coord pair uses defaults for the second point."""
        result = assistant.execute("draw line from (0,0)")
        assert result["success"] is True

    def test_overlapping_elements(self, assistant, project):
        """Two elements at same coords should both be added."""
        assistant.execute("draw a 5x5 rectangle at 0,0")
        assistant.execute("add a circle radius 3 at 0,0")
        assert len(project.sheets[0].elements) == 2

    def test_command_log_grows(self, assistant):
        for i in range(5):
            assistant.execute(f"draw a {i+1}x{i+1} rectangle at origin")
        assert len(assistant.get_command_log()) == 5

    def test_command_log_records_failure(self, assistant):
        assistant.execute("unknown command xyz")
        log = assistant.get_command_log()
        assert log[-1]["success"] is False

    def test_create_ansi_d_sheet(self, assistant, project):
        result = assistant.execute("create sheet ANSI_D")
        assert result["success"] is True
        assert any(s.size == SheetSize.ANSI_D for s in project.sheets)

    def test_revision_history_on_project(self):
        """DrawingProject supports revision history tracking."""
        p = DrawingProject(name="Rev Test")
        p.revision_history.append({"rev": "A", "date": "2026-01-01", "by": "Alice"})
        p.revision_history.append({"rev": "B", "date": "2026-02-01", "by": "Bob"})
        assert len(p.revision_history) == 2
        assert p.revision_history[1]["rev"] == "B"


class TestMultiSheetProjectProduction:

    def test_multi_discipline_project(self):
        p = DrawingProject(name="Multi", discipline=Discipline.STRUCTURAL)
        for disc in list(Discipline)[:3]:
            s = DrawingSheet()
            s.title_block.drawn_by = disc.value
            p.sheets.append(s)
        assert len(p.sheets) == 3

    def test_pe_stamp_id_on_title_block(self):
        tb = TitleBlock(pe_stamp_id="STAMP-001", drawn_by="Alice", checked_by="Bob")
        assert tb.pe_stamp_id == "STAMP-001"

    def test_drawing_approval_integration_success(self):
        """DrawingApprovalIntegration wires project → credential gate."""
        from src.murphy_drawing_engine import DrawingApprovalIntegration
        from src.murphy_credential_gate import (
            CredentialRegistry, CredentialVerifier, EStampEngine,
            CredentialGatedApproval, CredentialType, ProfessionalCredential,
            CredentialStatus,
        )
        from datetime import timedelta

        registry = CredentialRegistry()
        exp = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d")
        iss = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cred = ProfessionalCredential(
            holder_name="PE Engineer",
            holder_email="pe@example.com",
            credential_type=CredentialType.PE,
            license_number="PE-999",
            issuing_authority="State Board",
            jurisdiction="TX",
            issued_date=iss,
            expiration_date=exp,
        )
        registry.register(cred)
        verifier = CredentialVerifier(registry)
        stamp_engine = EStampEngine(registry, verifier)
        gated = CredentialGatedApproval(registry, verifier, stamp_engine)

        project = DrawingProject(name="Stamped Drawing")
        dai = DrawingApprovalIntegration(gated)
        result = dai.request_pe_stamp(
            project=project,
            approver_credential_id=cred.credential_id,
            required_credential_types=[CredentialType.PE],
            jurisdiction="TX",
        )
        assert result["status"] == "approved"
        assert result["has_stamp"] is True

    def test_drawing_approval_integration_no_credential(self):
        """DrawingApprovalIntegration returns requires_credential when cred missing."""
        from src.murphy_drawing_engine import DrawingApprovalIntegration
        from src.murphy_credential_gate import (
            CredentialRegistry, CredentialVerifier, EStampEngine,
            CredentialGatedApproval, CredentialType,
        )

        registry = CredentialRegistry()
        verifier = CredentialVerifier(registry)
        stamp_engine = EStampEngine(registry, verifier)
        gated = CredentialGatedApproval(registry, verifier, stamp_engine)

        project = DrawingProject(name="Unstamped Drawing")
        dai = DrawingApprovalIntegration(gated)
        result = dai.request_pe_stamp(
            project=project,
            approver_credential_id="nonexistent-id",
            required_credential_types=[CredentialType.PE],
        )
        assert result["status"] == "requires_credential"
        assert result["has_stamp"] is False


import math as _math
from datetime import datetime, timezone

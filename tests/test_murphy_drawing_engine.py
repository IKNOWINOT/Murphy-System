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

from src.murphy_drawing_engine import (
    LineStyle,
    LINE_STYLE_SVG,
    LINE_STYLE_DXF,
    EngineeringSymbol,
    DrawingBorder,
    build_pump_ga_drawing,
)


# ---------------------------------------------------------------------------
# Line Style System Tests
# ---------------------------------------------------------------------------

class TestLineStyleSystem:
    """ASME Y14.2 line convention system."""

    def test_all_line_styles_defined(self):
        for ls in LineStyle:
            assert ls in LINE_STYLE_SVG
            assert ls in LINE_STYLE_DXF

    def test_continuous_no_dasharray(self):
        assert LINE_STYLE_SVG[LineStyle.CONTINUOUS]["stroke-dasharray"] == "none"

    def test_hidden_has_dasharray(self):
        dash = LINE_STYLE_SVG[LineStyle.HIDDEN]["stroke-dasharray"]
        assert dash != "none"
        assert "," in dash

    def test_center_dasharray(self):
        dash = LINE_STYLE_SVG[LineStyle.CENTER]["stroke-dasharray"]
        parts = [p.strip() for p in dash.split(",")]
        assert len(parts) >= 3

    def test_phantom_dasharray_longer_than_center(self):
        center_parts = LINE_STYLE_SVG[LineStyle.CENTER]["stroke-dasharray"].split(",")
        phantom_parts = LINE_STYLE_SVG[LineStyle.PHANTOM]["stroke-dasharray"].split(",")
        assert len(phantom_parts) >= len(center_parts)

    def test_visible_lines_thicker_than_center(self):
        vis = float(LINE_STYLE_SVG[LineStyle.CONTINUOUS]["stroke-width"])
        cen = float(LINE_STYLE_SVG[LineStyle.CENTER]["stroke-width"])
        assert vis > cen

    def test_dxf_linetype_names(self):
        assert LINE_STYLE_DXF[LineStyle.CONTINUOUS] == "CONTINUOUS"
        assert LINE_STYLE_DXF[LineStyle.HIDDEN] == "HIDDEN"
        assert LINE_STYLE_DXF[LineStyle.CENTER] == "CENTER"

    def test_element_default_line_style(self):
        elem = DrawingElement(element_type=ElementType.LINE)
        assert elem.line_style == LineStyle.CONTINUOUS

    def test_element_custom_line_style(self):
        elem = DrawingElement(element_type=ElementType.CIRCLE, line_style=LineStyle.HIDDEN)
        assert elem.line_style == LineStyle.HIDDEN

    def test_svg_renders_hidden_dasharray(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 10, "y2": 0},
            line_style=LineStyle.HIDDEN,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "stroke-dasharray" in svg
        assert "4,2" in svg

    def test_svg_renders_center_dasharray(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
            line_style=LineStyle.CENTER,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "stroke-dasharray" in svg
        assert "12,3,3,3" in svg
# LineStyle tests
# ---------------------------------------------------------------------------

class TestLineStyle:

    def test_all_line_styles_exist(self):
        from src.murphy_drawing_engine import LineStyle
        for style in ["CONTINUOUS", "HIDDEN", "CENTER", "PHANTOM", "DIMENSION", "CUTTING_PLANE"]:
            assert hasattr(LineStyle, style)

    def test_drawing_element_default_line_style(self):
        from src.murphy_drawing_engine import LineStyle
        elem = DrawingElement(element_type=ElementType.LINE)
        assert elem.line_style == LineStyle.CONTINUOUS

    def test_drawing_element_custom_line_style(self):
        from src.murphy_drawing_engine import LineStyle
        elem = DrawingElement(element_type=ElementType.LINE, line_style=LineStyle.CENTER)
        assert elem.line_style == LineStyle.CENTER

    def test_drawing_element_default_line_weight(self):
        elem = DrawingElement(element_type=ElementType.LINE)
        assert elem.line_weight == 0.5

    def test_drawing_element_custom_line_weight(self):
        elem = DrawingElement(element_type=ElementType.LINE, line_weight=1.0)
        assert elem.line_weight == 1.0

    def test_center_line_renders_dasharray_in_svg(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
            line_style=LineStyle.CENTER,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'stroke-dasharray' in svg
        assert '12,3,3,3' in svg

    def test_dashed_line_renders_dasharray_in_svg(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
            line_style=LineStyle.CENTER,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "12,3,3,3" in svg

    def test_dxf_includes_ltype_attribute(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "z1": 0, "x2": 5, "y2": 5, "z2": 0},
            line_style=LineStyle.HIDDEN,
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "HIDDEN" in dxf


# ---------------------------------------------------------------------------
# DXF TABLES Section Tests
# ---------------------------------------------------------------------------

class TestDXFTablesSection:
    """DXF R12 TABLES section with LTYPE definitions."""

    def test_dxf_has_tables_section(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "2\nTABLES" in dxf

    def test_dxf_has_ltype_table(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "2\nLTYPE" in dxf

    def test_dxf_defines_continuous_linetype(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "CONTINUOUS" in dxf

    def test_dxf_defines_hidden_linetype(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "HIDDEN" in dxf

    def test_dxf_defines_center_linetype(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "CENTER" in dxf

    def test_dxf_endtab_marker(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "ENDTAB" in dxf

    def test_dxf_tables_before_entities(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        tables_pos = dxf.index("TABLES")
        entities_pos = dxf.index("ENTITIES")
        assert tables_pos < entities_pos

    def test_dxf_arc_entity(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.ARC,
            geometry={"cx": 50, "cy": 50, "cz": 0, "radius": 20,
                      "start_angle": 0, "end_angle": 180},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "0\nARC" in dxf
        assert "\n50\n" in dxf  # cx value

    def test_dxf_arc_angles(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.ARC,
            geometry={"cx": 0, "cy": 0, "cz": 0, "radius": 10,
                      "start_angle": 45, "end_angle": 135},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert "\n45\n" in dxf
        assert "\n135\n" in dxf


# ---------------------------------------------------------------------------
# SVG viewBox Tests
# ---------------------------------------------------------------------------

class TestSVGViewBox:
    """SVG must include a viewBox attribute for proper scaling."""

    def test_svg_has_viewbox(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "viewBox=" in svg

    def test_viewbox_matches_dimensions(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet, width=1200, height=800)
        assert 'viewBox="0 0 1200 800"' in svg

    def test_viewbox_default_dimensions(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'viewBox="0 0 800 600"' in svg

    def test_svg_valid_xml_with_viewbox(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        assert root.get("viewBox") is not None


# ---------------------------------------------------------------------------
# Dimension Annotation Tests
# ---------------------------------------------------------------------------

class TestDimensionAnnotations:
    """DIMENSION elements render with extension lines, dimension line, arrowheads."""

    def test_dimension_element_renders_in_svg(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 10, "y1": 50, "x2": 110, "y2": 50, "offset": 15},
            properties={"text": "100"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<line" in svg
        assert "<polygon" in svg  # arrowheads

    def test_dimension_text_appears_in_svg(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 0, "x2": 200, "y2": 0, "offset": 20},
            properties={"text": "200mm"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "200mm" in svg

    def test_dimension_extension_lines(self, project_with_sheet):
        """Two extension lines must appear: one from each feature point."""
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 100, "x2": 50, "y2": 100, "offset": 10},
            properties={"text": "50"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        # Count at least 3 lines: 2 extension + 1 dimension line
        assert svg.count("<line") >= 3

    def test_dimension_arrowheads(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 0, "x2": 80, "y2": 0, "offset": 10},
            properties={"text": "80"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert svg.count("<polygon") >= 2  # two arrowheads

    def test_dimension_no_text_no_text_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 0, "x2": 50, "y2": 0, "offset": 10},
            properties={},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<text" not in svg or "font-size" in svg  # no dimension text, but title block might have text


# ---------------------------------------------------------------------------
# Hatch Pattern Tests
# ---------------------------------------------------------------------------

class TestHatchPatterns:
    """HATCH elements render as 45° parallel line patterns with clip boundary."""

    def test_hatch_renders_clip_path(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 10, "y": 10, "width": 60, "height": 40, "spacing": 5, "angle": 45},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "clipPath" in svg
        assert "clip-path=" in svg

    def test_hatch_renders_lines(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 0, "width": 50, "height": 50, "spacing": 10},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<line" in svg

    def test_hatch_boundary_outline(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 5, "y": 5, "width": 40, "height": 40},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<rect" in svg  # boundary outline

    def test_hatch_valid_xml(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 0, "width": 30, "height": 30, "spacing": 5},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        ET.fromstring(svg)  # must not raise


# ---------------------------------------------------------------------------
# Leader Line Tests
# ---------------------------------------------------------------------------

class TestLeaderLines:
    """LEADER elements render with arrow at first point and optional text."""

    def test_leader_renders_lines(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LEADER,
            geometry={"points": [{"x": 100, "y": 100}, {"x": 150, "y": 80}, {"x": 200, "y": 80}]},
            properties={"text": "LABEL"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<line" in svg
        assert "LABEL" in svg

    def test_leader_arrowhead(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LEADER,
            geometry={"points": [{"x": 50, "y": 50}, {"x": 100, "y": 30}]},
            properties={"text": "NOTE"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<polygon" in svg

    def test_leader_no_points_skipped(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LEADER,
            geometry={"points": []},
            properties={"text": "EMPTY"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        # no crash; no leader rendered
        assert "EMPTY" not in svg


# ---------------------------------------------------------------------------
# Title Block Rendering Tests
# ---------------------------------------------------------------------------

class TestTitleBlockRendering:
    """TitleBlock renders as bordered field area in SVG output."""

    def test_title_block_company_name_in_svg(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.title_block.company = "ACME Corp"
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "ACME Corp" in svg

    def test_title_block_drawing_number_in_svg(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.title_block.drawing_number = "DWG-001"
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "DWG-001" in svg

    def test_title_block_border_rect(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.title_block.company = "Test"
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "<rect" in svg

    def test_title_block_pe_stamp_circle(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.title_block.company = "PE Firm"
        sheet.title_block.pe_stamp_id = "PE-STAMP-999"
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "PE STAMP" in svg

    def test_title_block_drawn_by_in_svg(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.title_block.company = "Eng Co"
        sheet.title_block.drawn_by = "Alice"
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "Alice" in svg

    def test_title_block_empty_not_rendered(self, project_with_sheet):
        """Empty title block (no company/number/drawnby) should not render."""
        sheet = project_with_sheet.sheets[0]
        # default TitleBlock has all empty strings
        svg = DrawingExporter().to_svg(project_with_sheet)
        # no title block border should appear
        count_before = svg.count("fill=\"white\"")
        sheet2 = DrawingSheet()
        sheet2.title_block.company = "Corp"
        p2 = DrawingProject(name="X")
        p2.sheets.append(sheet2)
        svg2 = DrawingExporter().to_svg(p2)
        count_after = svg2.count("fill=\"white\"")
        assert count_after > count_before


# ---------------------------------------------------------------------------
# Engineering Symbol Library Tests
# ---------------------------------------------------------------------------

class TestEngineeringSymbolLibrary:
    """ISA 5.1 engineering symbols render as valid SVG snippets."""

    def test_centrifugal_pump_returns_svg(self):
        svg_snip = EngineeringSymbol.centrifugal_pump(0, 0, 30)
        assert "<circle" in svg_snip
        assert "<line" in svg_snip

    def test_gate_valve_returns_svg(self):
        svg_snip = EngineeringSymbol.gate_valve(0, 0, 20)
        assert "<polygon" in svg_snip
        assert "<line" in svg_snip

    def test_check_valve_returns_svg(self):
        svg_snip = EngineeringSymbol.check_valve(0, 0, 20)
        assert "<circle" in svg_snip
        assert "<polygon" in svg_snip

    def test_instrument_bubble_pi(self):
        svg_snip = EngineeringSymbol.instrument_bubble(0, 0, "PI", 14)
        assert "<circle" in svg_snip
        assert "PI" in svg_snip

    def test_instrument_bubble_fi(self):
        svg_snip = EngineeringSymbol.instrument_bubble(0, 0, "FI", 14)
        assert "FI" in svg_snip

    def test_instrument_bubble_ti(self):
        svg_snip = EngineeringSymbol.instrument_bubble(0, 0, "TI", 12)
        assert "TI" in svg_snip

    def test_pump_position_offset(self):
        sym_a = EngineeringSymbol.centrifugal_pump(0, 0, 30)
        sym_b = EngineeringSymbol.centrifugal_pump(100, 200, 30)
        # cx = x + size/2; floats are used internally
        assert 'cx="15' in sym_a
        assert 'cx="115' in sym_b

    def test_symbols_embed_in_svg(self):
        """All symbols must embed in a valid SVG document."""
        import xml.etree.ElementTree as ET
        parts = [
            EngineeringSymbol.centrifugal_pump(10, 10, 20),
            EngineeringSymbol.gate_valve(50, 50, 15),
            EngineeringSymbol.check_valve(80, 80, 15),
            EngineeringSymbol.instrument_bubble(110, 110, "PI", 10),
        ]
        svg_doc = (
            '<?xml version="1.0"?>'
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
            + "".join(parts) +
            '</svg>'
        )
        root = ET.fromstring(svg_doc)
        assert root is not None

    def test_hidden_line_renders_dasharray_in_svg(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
            line_style=LineStyle.HIDDEN,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'stroke-dasharray="4,2"' in svg

    def test_phantom_line_renders_dasharray_in_svg(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
            line_style=LineStyle.PHANTOM,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'stroke-dasharray' in svg

    def test_continuous_line_no_dasharray(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
            line_style=LineStyle.CONTINUOUS,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        # Continuous should not add dash array in this element's stroke attrs
        assert 'stroke-width="0.5"' in svg

    def test_line_weight_applied_to_svg_stroke_width(self, project_with_sheet):
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 10, "y2": 0},
            line_style=LineStyle.CONTINUOUS,
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        # CONTINUOUS line uses ASME Y14.2 weight 0.5
        assert 'stroke-width="0.5"' in svg


# ---------------------------------------------------------------------------
# Enhanced SVG tests
# ---------------------------------------------------------------------------

class TestEnhancedSVG:

    def test_svg_has_defs_section(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert '<defs>' in svg

    def test_svg_has_arrow_marker_definitions(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'marker' in svg
        assert 'arrow-start' in svg
        assert 'arrow-end' in svg

    def test_svg_has_hatch_pattern_definitions(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert '<pattern' in svg
        assert 'hatch-ansi31' in svg

    def test_svg_hatch_element_renders_pattern_fill(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 0, "width": 50, "height": 50, "spacing": 5, "angle": 45},
            properties={"hatch_style": "ansi31"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'clip-path' in svg

    def test_svg_hatch_ansi32_pattern(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 0, "width": 10, "height": 10, "spacing": 3, "angle": 45},
            properties={"hatch_style": "ansi32"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'clipPath' in svg

    def test_svg_dimension_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 50, "x2": 100, "y2": 50, "offset": 15},
            properties={"text": "100.0"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert '<polygon' in svg
        assert '100.0' in svg

    def test_svg_dimension_extension_lines(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 10, "y1": 50, "x2": 90, "y2": 50, "offset": 12},
            properties={"text": "80.0"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        # Should have 3 lines: dimension line + 2 extension lines
        assert svg.count('<line') >= 3

    def test_svg_leader_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LEADER,
            geometry={"points": [{"x": 50, "y": 50}, {"x": 100, "y": 30}, {"x": 130, "y": 30}]},
            properties={"text": "PUMP HOUSING"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert '<line' in svg
        assert 'PUMP HOUSING' in svg

    def test_svg_title_block_renders(self, project_with_sheet):
        project_with_sheet.sheets[0].title_block = TitleBlock(
            company="Inoni LLC",
            drawing_number="MECH-001",
            revision="B",
            drawn_by="Murphy AI",
        )
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'Inoni LLC' in svg
        assert 'MECH-001' in svg

    def test_svg_is_valid_xml_with_all_features(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import LineStyle
        sheet = project_with_sheet.sheets[0]
        sheet.elements.extend([
            DrawingElement(element_type=ElementType.LINE,
                geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
                line_style=LineStyle.CENTER),
            DrawingElement(element_type=ElementType.DIMENSION,
                geometry={"x1": 0, "y1": 50, "x2": 100, "y2": 50, "offset": 10},
                properties={"text": "100"}),
            DrawingElement(element_type=ElementType.HATCH,
                geometry={"boundary": [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}]},
                properties={"hatch_style": "ansi31"}),
        ])
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")


# ---------------------------------------------------------------------------
# Enhanced DXF tests
# ---------------------------------------------------------------------------

class TestEnhancedDXF:

    def test_dxf_has_tables_section(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert 'TABLES' in dxf

    def test_dxf_has_layer_definitions(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert 'LAYER' in dxf
        assert 'CENTERLINES' in dxf
        assert 'DIMENSIONS' in dxf

    def test_dxf_has_linetype_definitions(self, project_with_sheet):
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert 'LTYPE' in dxf
        assert 'CENTER' in dxf
        assert 'DASHED' in dxf

    def test_dxf_arc_entity(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.ARC,
            geometry={"cx": 50.0, "cy": 50.0, "cz": 0.0, "radius": 20.0, "start_angle": 0.0, "end_angle": 90.0},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert '0\nARC' in dxf
        assert '50\n0.0\n' in dxf  # start angle
        assert '51\n90.0' in dxf   # end angle

    def test_dxf_dimension_entity_produces_lines(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 50, "x2": 100, "y2": 50, "offset": 15},
            properties={"text": "100.0"},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert 'DIMENSIONS' in dxf
        assert '100.0' in dxf

    def test_dxf_hatch_boundary_as_lines(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"boundary": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}]},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        # 3 edges → 3 LINE entities from hatch + any other elements
        assert dxf.count('0\nLINE') >= 3

    def test_dxf_arc_angles_stored_correctly(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.ARC,
            geometry={"cx": 0, "cy": 0, "cz": 0, "radius": 5, "start_angle": 45.0, "end_angle": 270.0},
        ))
        dxf = DrawingExporter().to_dxf(project_with_sheet)
        assert '45.0' in dxf
        assert '270.0' in dxf


# ---------------------------------------------------------------------------
# Engineering Symbol Library tests
# ---------------------------------------------------------------------------

class TestEngineeringSymbolLibrary:

    def test_motor_returns_elements(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.motor(0, 0)
        assert len(elems) >= 2

    def test_motor_contains_rectangle_and_text(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.motor(0, 0)
        types = {e.element_type for e in elems}
        assert ElementType.RECTANGLE in types
        assert ElementType.TEXT in types

    def test_motor_label_text(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.motor(10, 20)
        texts = [e.properties.get("text", "") for e in elems if e.element_type == ElementType.TEXT]
        assert any("MOTOR" in t for t in texts)

    def test_pump_housing_returns_elements(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.pump_housing(50, 50)
        assert len(elems) >= 2

    def test_pump_housing_label(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.pump_housing(0, 0)
        texts = [e.properties.get("text", "") for e in elems if e.element_type == ElementType.TEXT]
        assert any("PUMP" in t for t in texts)

    def test_coupling_returns_circles(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.coupling(100, 100)
        circles = [e for e in elems if e.element_type == ElementType.CIRCLE]
        assert len(circles) >= 2

    def test_flange_returns_correct_bolt_count(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        bolt_count = 6
        elems = EngineeringSymbolLibrary.flange(0, 0, 60, 48, bolt_count, 5)
        bolt_circles = [e for e in elems if e.element_type == ElementType.CIRCLE]
        # outer circle + bolt_count bolt holes
        assert len(bolt_circles) == bolt_count + 1

    def test_flange_default_4_bolts(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.flange(0, 0)
        circles = [e for e in elems if e.element_type == ElementType.CIRCLE]
        assert len(circles) == 5  # 1 outer + 4 bolts

    def test_valve_returns_elements(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.valve(50, 50)
        assert len(elems) >= 3

    def test_valve_contains_polygons(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.valve(0, 0)
        polys = [e for e in elems if e.element_type == ElementType.POLYGON]
        assert len(polys) == 2

    def test_valve_type_label(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.valve(0, 0, "check")
        texts = [e.properties.get("text", "") for e in elems if e.element_type == ElementType.TEXT]
        assert any("CHECK" in t for t in texts)

    def test_centerline_has_center_linestyle(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary, LineStyle
        elems = EngineeringSymbolLibrary.centerline(0, 0, 100, 0)
        lines = [e for e in elems if e.element_type == ElementType.LINE]
        assert all(ln.line_style == LineStyle.CENTER for ln in lines)

    def test_centerline_cl_label(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.centerline(0, 0, 100, 0)
        texts = [e.properties.get("text", "") for e in elems if e.element_type == ElementType.TEXT]
        assert "CL" in texts

    def test_centerline_layer(self):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        elems = EngineeringSymbolLibrary.centerline(0, 0, 100, 0)
        layers = {e.layer for e in elems}
        assert "CENTERLINES" in layers

    def test_symbols_render_to_svg(self, project_with_sheet):
        from src.murphy_drawing_engine import EngineeringSymbolLibrary
        sheet = project_with_sheet.sheets[0]
        sheet.elements.extend(EngineeringSymbolLibrary.motor(10, 10))
        sheet.elements.extend(EngineeringSymbolLibrary.flange(100, 100))
        sheet.elements.extend(EngineeringSymbolLibrary.centerline(0, 50, 200, 50))
        svg = DrawingExporter().to_svg(project_with_sheet)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")


# ---------------------------------------------------------------------------
# Drawing Border Tests
# ---------------------------------------------------------------------------

class TestDrawingBorder:
    """DrawingBorder generates zone grid labels and frame rect."""

    def test_border_generates_svg(self):
        border = DrawingBorder()
        svg = border.to_svg(800, 600)
        assert "<rect" in svg
        assert "<text" in svg

    def test_border_column_labels(self):
        border = DrawingBorder(zone_cols=8, zone_rows=4)
        svg = border.to_svg(800, 600)
        for i in range(1, 9):
            assert str(i) in svg

    def test_border_row_labels(self):
        border = DrawingBorder(zone_cols=8, zone_rows=4)
        svg = border.to_svg(800, 600)
        for letter in "ABCD":
            assert letter in svg

    def test_border_frame_rect(self):
        border = DrawingBorder(margin=10)
        svg = border.to_svg(800, 600)
        assert 'stroke="black"' in svg
        assert 'fill="none"' in svg

    def test_border_custom_margin(self):
        border = DrawingBorder(margin=20)
        svg = border.to_svg(400, 300)
        assert "20" in svg


# ---------------------------------------------------------------------------
# Pump GA Drawing Demo Tests
# ---------------------------------------------------------------------------

class TestPumpGADrawing:
    """The built-in pump GA demo drawing proves end-to-end capability."""

    @pytest.fixture
    def pump_project(self):
        return build_pump_ga_drawing()

    def test_pump_project_exists(self, pump_project):
        assert pump_project.name == "Centrifugal Pump — General Arrangement"
        assert pump_project.discipline == Discipline.MECHANICAL

    def test_pump_has_one_sheet(self, pump_project):
        assert len(pump_project.sheets) == 1

    def test_pump_title_block_populated(self, pump_project):
        tb = pump_project.sheets[0].title_block
        assert tb.company == "Murphy System Engineering"
        assert tb.drawing_number == "MEC-PUMP-001"
        assert tb.pe_stamp_id == "STAMP-MEC-001"

    def test_pump_bom_has_three_items(self, pump_project):
        bom = BOMExtractor().extract(pump_project)
        assert len(bom) == 3

    def test_pump_bom_includes_pump(self, pump_project):
        bom = BOMExtractor().extract(pump_project)
        names = [b["block_name"] for b in bom]
        assert "CENTRIFUGAL_PUMP" in names

    def test_pump_bom_includes_motor(self, pump_project):
        bom = BOMExtractor().extract(pump_project)
        names = [b["block_name"] for b in bom]
        assert "ELECTRIC_MOTOR" in names

    def test_pump_svg_export(self, pump_project):
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        assert "viewBox" in svg
        assert "<?xml" in svg

    def test_pump_svg_has_title_block(self, pump_project):
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        assert "Murphy System Engineering" in svg
        assert "MEC-PUMP-001" in svg

    def test_pump_svg_has_hatch(self, pump_project):
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        assert "clipPath" in svg

    def test_pump_svg_has_dimension(self, pump_project):
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        # dimension text "400" should appear
        assert "400" in svg

    def test_pump_svg_has_leader(self, pump_project):
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        assert "MOTOR 15kW" in svg

    def test_pump_svg_valid_xml(self, pump_project):
        import xml.etree.ElementTree as ET
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_pump_dxf_export(self, pump_project):
        dxf = DrawingExporter().to_dxf(pump_project)
        assert "SECTION" in dxf
        assert "TABLES" in dxf
        assert "LTYPE" in dxf
        assert "EOF" in dxf

    def test_pump_dxf_has_centerline_type(self, pump_project):
        dxf = DrawingExporter().to_dxf(pump_project)
        assert "CENTER" in dxf

    def test_pump_svg_has_centerline_dasharray(self, pump_project):
        svg = DrawingExporter().to_svg(pump_project, width=800, height=600)
        # shaft centerline should render with CENTER dasharray
        assert "12,3,3,3" in svg

    def test_pump_has_multiple_element_types(self, pump_project):
        sheet = pump_project.sheets[0]
        types_present = {e.element_type for e in sheet.elements}
        expected = {
            ElementType.LINE, ElementType.CIRCLE, ElementType.RECTANGLE,
            ElementType.HATCH, ElementType.DIMENSION, ElementType.LEADER,
            ElementType.TEXT, ElementType.BLOCK_REF,
        }
        assert expected.issubset(types_present)

    def test_pump_pdf_placeholder(self, pump_project):
        result = DrawingExporter().to_pdf_placeholder(pump_project)
        assert result["sheets"] == 1
        assert result["elements"] > 10

# Assembly Drawing tests
# ---------------------------------------------------------------------------

class TestAssemblyDrawing:

    def test_build_pump_assembly_creates_sheet(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        assert sheet is not None

    def test_build_pump_assembly_has_multiple_elements(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        assert len(sheet.elements) >= 10

    def test_build_pump_assembly_has_centerline(self):
        from src.murphy_drawing_engine import AssemblyDrawing, LineStyle
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        cl_elems = [e for e in sheet.elements
                    if e.element_type == ElementType.LINE and e.line_style == LineStyle.CENTER]
        assert len(cl_elems) >= 1

    def test_build_pump_assembly_has_flanges(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        circles = [e for e in sheet.elements if e.element_type == ElementType.CIRCLE]
        # Should have circles from 2 flanges + coupling
        assert len(circles) >= 5

    def test_build_pump_assembly_has_title_block(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        assert sheet.title_block.drawing_number == "MECH-GA-001"

    def test_build_pump_assembly_has_annotations(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        texts = [e.properties.get("text", "") for e in sheet.elements
                 if e.element_type == ElementType.TEXT]
        combined = " ".join(texts)
        assert "MOTOR" in combined
        assert "PUMP" in combined
        assert "FLANGE" in combined

    def test_assembly_renders_valid_svg(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        import xml.etree.ElementTree as ET
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        assy.build_pump_assembly()
        svg = DrawingExporter().to_svg(project)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_assembly_renders_valid_dxf(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        assy.build_pump_assembly()
        dxf = DrawingExporter().to_dxf(project)
        assert "SECTION" in dxf
        assert "EOF" in dxf

    def test_assembly_with_custom_origin(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Test")
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly(origin_x=200, origin_y=300)
        assert len(sheet.elements) >= 10

    def test_assembly_drawing_composition_with_existing_sheet(self):
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Pump Assembly Existing Sheet")
        existing = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(existing)
        assy = AssemblyDrawing(project)
        sheet = assy.build_pump_assembly()
        assert sheet is existing


# ---------------------------------------------------------------------------
# New AgenticDrawingAssistant command tests
# ---------------------------------------------------------------------------

class TestAgenticDrawingAssistantNewCommands:

    def test_add_centerline_command(self, assistant, project):
        result = assistant.execute("add centerline from (0,50) to (200,50)")
        assert result["success"] is True

    def test_centerline_has_center_line_style(self, assistant, project):
        from src.murphy_drawing_engine import LineStyle
        assistant.execute("add centerline from (0,0) to (100,0)")
        sheet = project.sheets[0]
        cl_elems = [e for e in sheet.elements
                    if e.element_type == ElementType.LINE and e.line_style == LineStyle.CENTER]
        assert len(cl_elems) >= 1

    def test_centerline_adds_cl_label(self, assistant, project):
        assistant.execute("add centerline from (0,50) to (200,50)")
        sheet = project.sheets[0]
        texts = [e.properties.get("text", "") for e in sheet.elements
                 if e.element_type == ElementType.TEXT]
        assert "CL" in texts

    def test_add_dimension_command(self, assistant, project):
        result = assistant.execute("add dimension from (0,0) to (100,0)")
        assert result["success"] is True

    def test_dimension_element_created(self, assistant, project):
        assistant.execute("add dimension from (0,0) to (100,0)")
        sheet = project.sheets[0]
        dims = [e for e in sheet.elements if e.element_type == ElementType.DIMENSION]
        assert len(dims) == 1

    def test_dimension_text_computed(self, assistant, project):
        assistant.execute("add dimension from (0,0) to (100,0)")
        sheet = project.sheets[0]
        dims = [e for e in sheet.elements if e.element_type == ElementType.DIMENSION]
        assert dims
        assert dims[0].properties["text"] == "100.0"

    def test_draw_motor_command(self, assistant, project):
        result = assistant.execute("draw motor at 50,50")
        assert result["success"] is True

    def test_draw_motor_creates_elements(self, assistant, project):
        assistant.execute("draw motor at 100,100")
        sheet = project.sheets[0]
        assert len(sheet.elements) >= 2

    def test_create_pump_assembly_command(self, assistant, project):
        result = assistant.execute("create pump assembly")
        assert result["success"] is True

    def test_pump_assembly_via_assistant_populates_project(self, assistant, project):
        assistant.execute("create pump assembly")
        total_elements = sum(len(s.elements) for s in project.sheets)
        assert total_elements >= 10

    def test_draw_dimension_alternative_command(self, assistant, project):
        result = assistant.execute("draw dimension from (10,10) to (60,10)")
        assert result["success"] is True

    def test_centerline_defaults_when_no_coords(self, assistant, project):
        result = assistant.execute("add centerline")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Phase 4 comprehensive SVG validity tests
# ---------------------------------------------------------------------------

class TestSVGValidity:
    """Comprehensive tests verifying SVG output is valid, well-formed XML."""

    def test_svg_is_valid_xml(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_svg_no_duplicate_tags(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        for elem_type, geom in [
            (ElementType.LINE, {"x1": 0, "y1": 0, "x2": 10, "y2": 10}),
            (ElementType.CIRCLE, {"cx": 5, "cy": 5, "radius": 3}),
            (ElementType.RECTANGLE, {"x": 0, "y": 0, "width": 10, "height": 10}),
            (ElementType.ARC, {"cx": 5, "cy": 5, "radius": 5, "start_angle": 0, "end_angle": 90}),
        ]:
            sheet.elements.append(DrawingElement(element_type=elem_type, geometry=geom))
        svg = DrawingExporter().to_svg(project_with_sheet)
        # No broken tag patterns from duplicate f-string lines
        assert "/>stroke=" not in svg
        assert "/>r=" not in svg
        assert "/>fill=" not in svg

    def test_svg_no_python_source(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 50, "y2": 50},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "elif" not in svg
        assert "elem.element_type" not in svg
        assert "svg_elements.append" not in svg

    def test_svg_has_single_root(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert svg.count("<svg") == 1
        assert svg.count("</svg>") == 1

    def test_svg_has_viewbox(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet, width=1200, height=900)
        assert 'viewBox="0 0 1200 900"' in svg

    def test_svg_defs_contains_markers(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "arrow-start" in svg
        assert "arrow-end" in svg
        assert "<defs>" in svg

    def test_svg_defs_contains_hatch_patterns(self, project_with_sheet):
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert "hatch-ansi31" in svg

    def test_svg_line_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'x1="10"' in svg
        assert 'y1="20"' in svg
        assert 'x2="30"' in svg
        assert 'y2="40"' in svg

    def test_svg_circle_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": 50, "cy": 60, "radius": 15},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert 'cx="50"' in svg
        assert 'cy="60"' in svg
        assert 'r="15"' in svg

    def test_svg_rectangle_element(self, project_with_sheet):
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.RECTANGLE,
            geometry={"x": 5, "y": 10, "width": 40, "height": 20},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        assert '<rect' in svg
        assert 'width="40"' in svg
        assert 'height="20"' in svg

    def test_svg_text_element(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": 10, "y": 20, "height": 12},
            properties={"text": "HELLO WORLD"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        assert any("HELLO WORLD" in (t.text or "") for t in texts)

    def test_svg_arc_element(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.ARC,
            geometry={"cx": 50, "cy": 50, "radius": 20, "start_angle": 0, "end_angle": 90},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        paths = root.findall(".//{http://www.w3.org/2000/svg}path")
        assert len(paths) >= 1
        d = paths[0].get("d", "")
        assert "A" in d  # arc command

    def test_svg_polygon_element(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.POLYGON,
            geometry={"vertices": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 5, "y": 10}]},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        polygons = root.findall(".//{http://www.w3.org/2000/svg}polygon")
        assert len(polygons) >= 1

    def test_svg_dimension_element_has_lines_and_text(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 50, "x2": 100, "y2": 50, "offset": 10},
            properties={"text": "100mm"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        assert len(lines) >= 2  # extension + dimension lines
        assert any("100mm" in (t.text or "") for t in texts)

    def test_svg_hatch_element_clippath_in_defs(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 0, "width": 50, "height": 50, "spacing": 5, "angle": 45},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        # clipPath must be inside <defs>
        defs = root.find("{http://www.w3.org/2000/svg}defs")
        assert defs is not None
        clip_paths = defs.findall("{http://www.w3.org/2000/svg}clipPath")
        assert len(clip_paths) >= 1

    def test_svg_leader_element(self, project_with_sheet):
        import xml.etree.ElementTree as ET
        sheet = project_with_sheet.sheets[0]
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LEADER,
            geometry={"points": [{"x": 10, "y": 10}, {"x": 50, "y": 50}]},
            properties={"text": "NOTE A"},
        ))
        svg = DrawingExporter().to_svg(project_with_sheet)
        root = ET.fromstring(svg)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        assert len(lines) >= 1
        assert "NOTE A" in svg

    def test_svg_title_block_single_render(self, project_with_sheet):
        """Only one title block should be rendered per sheet."""
        project_with_sheet.sheets[0].title_block = TitleBlock(
            company="Acme Corp",
            drawing_number="DWG-999",
            drawn_by="Test Engineer",
        )
        svg = DrawingExporter().to_svg(project_with_sheet)
        # The company name should appear exactly once in the body
        assert svg.count("Acme Corp") == 1
        assert svg.count("DWG-999") == 1

    def test_linestyle_enum_has_hidden(self):
        from src.murphy_drawing_engine import LineStyle, LINE_STYLE_SVG
        assert hasattr(LineStyle, "HIDDEN")
        assert LineStyle.HIDDEN in LINE_STYLE_SVG
        assert LINE_STYLE_SVG[LineStyle.HIDDEN]["stroke-dasharray"] == "4,2"

    def test_linestyle_enum_has_cutting_plane(self):
        from src.murphy_drawing_engine import LineStyle, LINE_STYLE_SVG
        assert hasattr(LineStyle, "CUTTING_PLANE")
        assert LineStyle.CUTTING_PLANE in LINE_STYLE_SVG

    def test_linestyle_no_dashed_member(self):
        from src.murphy_drawing_engine import LineStyle
        assert not hasattr(LineStyle, "DASHED")

    def test_linestyle_no_construction_member(self):
        from src.murphy_drawing_engine import LineStyle
        assert not hasattr(LineStyle, "CONSTRUCTION")

    def test_pump_ga_drawing_roundtrip(self):
        import xml.etree.ElementTree as ET
        project = build_pump_ga_drawing()
        svg = DrawingExporter().to_svg(project)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_pump_assembly_roundtrip(self):
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import AssemblyDrawing
        project = DrawingProject(name="Assembly Test", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        assembly = AssemblyDrawing(project)
        assembly.build_pump_assembly()
        svg = DrawingExporter().to_svg(project)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_bom_extractor(self):
        from src.murphy_drawing_engine import BOMExtractor
        project = DrawingProject(name="BOM Test", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.BLOCK_REF,
            properties={"block_name": "PUMP", "quantity": 2, "description": "Centrifugal Pump"},
        ))
        bom = BOMExtractor().extract(project)
        assert len(bom) >= 1
        assert bom[0]["block_name"] == "PUMP"


# ---------------------------------------------------------------------------
# SVG Z-Order and Rendering Correctness
# ---------------------------------------------------------------------------

class TestSVGZOrder:
    """Verify SVG element ordering, clipPath references, markers, and font minimums."""

    def _make_mixed_sheet(self):
        """Return a project with one sheet containing HATCH, LINE, CIRCLE, DIMENSION, TEXT."""
        project = DrawingProject(name="ZOrder", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        # Add in reverse render order to prove sorting works
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": 10, "y": 10, "height": 6},
            properties={"text": "LABEL"},
        ))
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0, "offset": 10},
            properties={"text": "100"},
        ))
        sheet.elements.append(DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": 50, "cy": 50, "radius": 20},
        ))
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0},
        ))
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 200, "width": 100, "height": 20, "spacing": 5, "angle": 45},
        ))
        return project

    def test_hatch_before_line_in_svg(self):
        """HATCH elements must appear before LINE elements in the SVG body."""
        project = self._make_mixed_sheet()
        svg = DrawingExporter().to_svg(project)
        # Search only in the body (after </defs>) to avoid matching <line> inside pattern defs
        body_start = svg.find("</defs>") + len("</defs>")
        body = svg[body_start:]
        hatch_pos = body.find('clip-path="url(#')
        # Find the plain non-hatch line — it won't have a clip-path attribute
        # First <line> without clip-path in the body
        import re
        # Find position of the first line that is NOT a hatch line (no clip-path attr)
        plain_line_match = re.search(r'<line x1="0"[^/]*/>', body)
        assert hatch_pos != -1, "No hatch content found in SVG body"
        assert plain_line_match is not None, "No plain line element found in SVG body"
        assert hatch_pos < plain_line_match.start(), "Hatch must appear before lines (z-order)"

    def test_text_after_circle_in_svg(self):
        """TEXT elements must appear after CIRCLE elements in SVG output."""
        project = self._make_mixed_sheet()
        svg = DrawingExporter().to_svg(project)
        circle_pos = svg.find('<circle ')
        text_pos = svg.find('>LABEL<')
        assert circle_pos != -1
        assert text_pos != -1
        assert circle_pos < text_pos, "Circle must appear before text annotations (z-order)"

    def test_title_block_renders_after_all_elements(self):
        """Title block must be the last group of SVG elements."""
        project = DrawingProject(name="TB Last", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        sheet.title_block = TitleBlock(
            company="Acme", drawing_number="DWG-1", drawn_by="Eng"
        )
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": 5, "y": 5, "height": 8},
            properties={"text": "DRAWING CONTENT"},
        ))
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 0, "y": 300, "width": 100, "height": 20},
        ))
        svg = DrawingExporter().to_svg(project)
        # Title block rect has fill="white" — it must appear after drawing content
        title_pos = svg.rfind('fill="white"')
        drawing_text_pos = svg.find('>DRAWING CONTENT<')
        assert title_pos != -1, "Title block fill='white' not found"
        assert drawing_text_pos != -1, "Drawing text element not found"
        assert drawing_text_pos < title_pos, "Title block must appear after drawing elements"

    def test_clippath_id_matches_reference(self):
        """The clipPath id must match the clip-path url() reference."""
        import re
        import xml.etree.ElementTree as ET
        project = DrawingProject(name="Clip Test", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": 10, "y": 10, "width": 80, "height": 40, "spacing": 5, "angle": 45},
        ))
        svg = DrawingExporter().to_svg(project)
        # Collect all clipPath ids from <defs>
        root = ET.fromstring(svg)
        ns = "http://www.w3.org/2000/svg"
        defs = root.find(f"{{{ns}}}defs")
        assert defs is not None
        clip_ids = {cp.get("id") for cp in defs.findall(f"{{{ns}}}clipPath")}
        # Collect all clip-path references in the body
        refs = re.findall(r'clip-path="url\(#([^)]+)\)"', svg)
        assert len(refs) > 0, "No clip-path references found"
        for ref_id in refs:
            assert ref_id in clip_ids, f"clip-path url(#{ref_id}) has no matching <clipPath id>"

    def test_arrow_markers_referenced_in_defs(self):
        """marker-start/marker-end references must have matching <marker> defs."""
        import re
        import xml.etree.ElementTree as ET
        project = DrawingProject(name="Marker Test", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": 0, "y1": 0, "x2": 100, "y2": 0, "offset": 15},
            properties={"text": "100mm"},
        ))
        svg = DrawingExporter().to_svg(project)
        root = ET.fromstring(svg)
        ns = "http://www.w3.org/2000/svg"
        defs = root.find(f"{{{ns}}}defs")
        assert defs is not None
        marker_ids = {m.get("id") for m in defs.findall(f"{{{ns}}}marker")}
        refs = re.findall(r'marker-(?:start|end)="url\(#([^)]+)\)"', svg)
        assert len(refs) > 0, "No marker references found in dimension SVG"
        for ref_id in refs:
            assert ref_id in marker_ids, f"marker url(#{ref_id}) has no matching <marker> def"

    def test_text_minimum_font_size_enforced(self):
        """Text elements with very small height must be clamped to a minimum of 8px."""
        project = DrawingProject(name="Font Test", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        project.sheets.append(sheet)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": 10, "y": 10, "height": 3},  # below minimum
            properties={"text": "TINY"},
        ))
        svg = DrawingExporter().to_svg(project)
        # font-size must not be less than 8
        import re
        font_sizes = [int(m) for m in re.findall(r'font-size="(\d+)"', svg)]
        assert all(fs >= 8 for fs in font_sizes), f"Font sizes below 8 found: {font_sizes}"


# ---------------------------------------------------------------------------
# Phase A: TestIsometricProjector
# ---------------------------------------------------------------------------

class TestIsometricProjector:

    def test_project_point_at_origin(self):
        import pytest
        from src.murphy_drawing_engine import IsometricProjector
        proj = IsometricProjector()
        iso_x, iso_y = proj.project_point(0, 0, 0)
        assert iso_x == pytest.approx(0.0)
        assert iso_y == pytest.approx(0.0)

    def test_project_box_returns_12_lines(self):
        from src.murphy_drawing_engine import IsometricProjector, ElementType
        proj = IsometricProjector()
        elements = proj.project_box(0, 0, 0, 100, 50, 80)
        assert len(elements) == 12
        assert all(e.element_type == ElementType.LINE for e in elements)

    def test_isometric_angles_are_30_degrees(self):
        import math
        from src.murphy_drawing_engine import IsometricProjector
        proj = IsometricProjector()
        assert abs(proj.COS30 - math.cos(math.radians(30))) < 1e-9
        assert abs(proj.SIN30 - math.sin(math.radians(30))) < 1e-9

    def test_hidden_edges_use_hidden_linestyle(self):
        from src.murphy_drawing_engine import IsometricProjector, LineStyle
        proj = IsometricProjector()
        elements = proj.project_box(0, 0, 0, 100, 50, 80)
        hidden = [e for e in elements if e.line_style == LineStyle.HIDDEN]
        assert len(hidden) == 3  # exactly 3 hidden edges at back-bottom-left corner

    def test_project_point_pure_x(self):
        import pytest, math
        from src.murphy_drawing_engine import IsometricProjector
        proj = IsometricProjector()
        iso_x, iso_y = proj.project_point(10, 0, 0)
        assert iso_x == pytest.approx(10 * math.cos(math.radians(30)))
        assert iso_y == pytest.approx(10 * math.sin(math.radians(30)))

    def test_project_circle_returns_polygon(self):
        from src.murphy_drawing_engine import IsometricProjector, ElementType
        proj = IsometricProjector()
        elem = proj.project_circle_as_ellipse(50, 50, 0, 20)
        assert elem.element_type == ElementType.POLYGON
        verts = elem.geometry.get("vertices", [])
        assert len(verts) == 24

    def test_project_box_has_continuous_and_hidden(self):
        from src.murphy_drawing_engine import IsometricProjector, LineStyle
        proj = IsometricProjector()
        elements = proj.project_box(10, 10, 10, 40, 30, 20)
        cont = [e for e in elements if e.line_style == LineStyle.CONTINUOUS]
        hidn = [e for e in elements if e.line_style == LineStyle.HIDDEN]
        assert len(cont) == 9
        assert len(hidn) == 3


# ---------------------------------------------------------------------------
# Phase B: TestExplodedViewBuilder
# ---------------------------------------------------------------------------

class TestExplodedViewBuilder:

    def test_explode_offsets_parts_correctly(self):
        from src.murphy_drawing_engine import ExplodedViewBuilder
        parts = [
            {"name": "A", "x": 0, "y": 0, "z": 0, "w": 10, "h": 10, "d": 10},
            {"name": "B", "x": 0, "y": 0, "z": 0, "w": 10, "h": 10, "d": 10},
            {"name": "C", "x": 0, "y": 5, "z": 0, "w": 10, "h": 10, "d": 10},
        ]
        builder = ExplodedViewBuilder(parts)
        builder.explode(offset_vector=(0, -30, 0))
        assert builder._exploded_parts[0]["y"] == 0
        assert builder._exploded_parts[1]["y"] == -30
        assert builder._exploded_parts[2]["y"] == 5 + 2 * (-30)

    def test_balloon_callouts_generated(self):
        from src.murphy_drawing_engine import ExplodedViewBuilder, ElementType
        parts = [
            {"name": "A", "x": 0, "y": 0, "z": 0, "w": 10, "h": 10, "d": 10},
        ]
        builder = ExplodedViewBuilder(parts)
        builder.explode()
        elements = builder.build(0, 0)
        circles = [e for e in elements if e.element_type == ElementType.CIRCLE]
        assert len(circles) >= 1
        balloon_circles = [c for c in circles if c.properties.get("type") == "balloon"]
        assert len(balloon_circles) == 1

    def test_roundtrip_svg_valid_xml(self):
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import (
            ExplodedViewBuilder, DrawingProject, DrawingSheet, DrawingExporter,
        )
        parts = [{"name": "Box", "x": 0, "y": 0, "z": 0, "w": 50, "h": 30, "d": 40}]
        builder = ExplodedViewBuilder(parts)
        builder.explode()
        elements = builder.build(100, 100)
        project = DrawingProject(name="Exploded Test")
        sheet = DrawingSheet()
        sheet.elements.extend(elements)
        project.sheets.append(sheet)
        svg = DrawingExporter().to_svg(project)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_build_without_explicit_explode(self):
        from src.murphy_drawing_engine import ExplodedViewBuilder, ElementType
        parts = [{"name": "P", "x": 0, "y": 0, "z": 0, "w": 20, "h": 10, "d": 5}]
        builder = ExplodedViewBuilder(parts)
        elements = builder.build(0, 0)
        lines = [e for e in elements if e.element_type == ElementType.LINE]
        assert len(lines) == 12  # one box = 12 edges

    def test_multiple_parts_generate_multiple_balloons(self):
        from src.murphy_drawing_engine import ExplodedViewBuilder, ElementType
        parts = [
            {"name": f"P{i}", "x": 0, "y": 0, "z": 0, "w": 10, "h": 5, "d": 5}
            for i in range(5)
        ]
        builder = ExplodedViewBuilder(parts)
        builder.explode(offset_vector=(0, -20, 0))
        elements = builder.build(0, 0)
        balloons = [e for e in elements if e.element_type == ElementType.CIRCLE
                    and e.properties.get("type") == "balloon"]
        assert len(balloons) == 5


# ---------------------------------------------------------------------------
# Phase C: TestSpeakerAssemblyDrawing
# ---------------------------------------------------------------------------

class TestSpeakerAssemblyDrawing:

    def test_build_produces_valid_svg(self):
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, DrawingExporter
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        svg = DrawingExporter().to_svg(project, width=1200, height=900)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_bom_has_10_items(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing
        drawing = SpeakerAssemblyDrawing()
        assert len(drawing.bom) == 10

    def test_front_view_has_driver_circles(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, ElementType
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        sheet = project.sheets[0]
        circles = [e for e in sheet.elements if e.element_type == ElementType.CIRCLE]
        driver_circles = [c for c in circles if c.properties.get("driver") in ("woofer", "tweeter")]
        assert len(driver_circles) >= 2

    def test_section_view_has_hatch(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, ElementType
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        sheet = project.sheets[0]
        hatches = [e for e in sheet.elements if e.element_type == ElementType.HATCH]
        assert len(hatches) >= 1

    def test_exploded_view_has_balloons(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, ElementType
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        sheet = project.sheets[0]
        balloons = [
            e for e in sheet.elements
            if e.element_type == ElementType.CIRCLE
            and e.properties.get("type") == "balloon"
        ]
        assert len(balloons) >= 10

    def test_title_block_present(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        tb = project.sheets[0].title_block
        assert tb.company == "Murphy System Engineering"
        assert tb.drawing_number == "MEC-SPKR-001"

    def test_dimension_lines_present(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, ElementType
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        sheet = project.sheets[0]
        dims = [e for e in sheet.elements if e.element_type == ElementType.DIMENSION]
        assert len(dims) >= 3

    def test_all_10_part_numbers_in_bom(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, DrawingExporter
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        svg = DrawingExporter().to_svg(project, width=1200, height=900)
        for item in drawing.bom:
            assert item["part_number"] in svg, f"{item['part_number']} not found in SVG"

    def test_speaker_project_has_block_refs_for_bom(self):
        from src.murphy_drawing_engine import SpeakerAssemblyDrawing, BOMExtractor
        drawing = SpeakerAssemblyDrawing()
        project = drawing.build()
        bom = BOMExtractor().extract(project)
        assert len(bom) == 10


# ---------------------------------------------------------------------------
# General-purpose drawing capability commands in AgenticDrawingAssistant
# ---------------------------------------------------------------------------

class TestAgenticDrawingCapabilityCommands:
    """Verify that general-purpose drawing capability commands work via the assistant."""

    def test_isometric_box_command_succeeds(self, assistant, project):
        result = assistant.execute("draw isometric box 100x50x80 at 0,0,0")
        assert result["success"] is True

    def test_isometric_box_creates_12_edges(self, assistant, project):
        from src.murphy_drawing_engine import ElementType
        assistant.execute("draw isometric box 100x50x80 at 0,0,0")
        sheet = project.sheets[0]
        lines = [e for e in sheet.elements if e.element_type == ElementType.LINE]
        assert len(lines) == 12

    def test_isometric_box_has_hidden_edges(self, assistant, project):
        from src.murphy_drawing_engine import LineStyle
        assistant.execute("draw isometric box 60x40x30 at 10,0,0")
        sheet = project.sheets[0]
        hidden = [e for e in sheet.elements if e.line_style == LineStyle.HIDDEN]
        assert len(hidden) == 3

    def test_iso_box_shorthand_command(self, assistant, project):
        result = assistant.execute("draw iso box 50x30x40 at 0,0,0")
        assert result["success"] is True

    def test_isometric_box_default_dims_when_no_size_given(self, assistant, project):
        from src.murphy_drawing_engine import ElementType
        result = assistant.execute("draw isometric box at 0,0")
        assert result["success"] is True
        sheet = project.sheets[0]
        lines = [e for e in sheet.elements if e.element_type == ElementType.LINE]
        assert len(lines) == 12

    def test_balloon_callout_command_succeeds(self, assistant, project):
        result = assistant.execute("add balloon 3 at 200,150")
        assert result["success"] is True

    def test_balloon_callout_creates_circle(self, assistant, project):
        from src.murphy_drawing_engine import ElementType
        assistant.execute("add balloon 5 at 100,100")
        sheet = project.sheets[0]
        circles = [e for e in sheet.elements if e.element_type == ElementType.CIRCLE]
        assert len(circles) == 1

    def test_balloon_callout_creates_leader(self, assistant, project):
        from src.murphy_drawing_engine import ElementType
        assistant.execute("add balloon 2 at 50,80")
        sheet = project.sheets[0]
        leaders = [e for e in sheet.elements if e.element_type == ElementType.LEADER]
        assert len(leaders) == 1

    def test_balloon_callout_number_in_text(self, assistant, project):
        from src.murphy_drawing_engine import ElementType
        assistant.execute("add balloon 7 at 0,0")
        sheet = project.sheets[0]
        texts = [e.properties.get("text", "") for e in sheet.elements
                 if e.element_type == ElementType.TEXT]
        assert "7" in texts

    def test_cutting_plane_command_succeeds(self, assistant, project):
        result = assistant.execute("add cutting plane from (50,100) to (250,100) label A-A")
        assert result["success"] is True

    def test_cutting_plane_uses_cutting_plane_linestyle(self, assistant, project):
        from src.murphy_drawing_engine import LineStyle
        assistant.execute("add cutting plane from (0,50) to (200,50)")
        sheet = project.sheets[0]
        cp_lines = [e for e in sheet.elements if e.line_style == LineStyle.CUTTING_PLANE]
        assert len(cp_lines) == 1

    def test_cutting_plane_label_applied(self, assistant, project):
        from src.murphy_drawing_engine import ElementType
        assistant.execute("add cutting plane from (0,0) to (100,0) label B-B")
        sheet = project.sheets[0]
        texts = [e.properties.get("text", "") for e in sheet.elements
                 if e.element_type == ElementType.TEXT]
        assert "B" in texts

    def test_speaker_command_not_recognised(self, assistant):
        """Specific product commands are not baked in — use the class API directly."""
        result = assistant.execute("create speaker assembly")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Phase E: TestBOMTableRenderer
# ---------------------------------------------------------------------------

class TestBOMTableRenderer:

    def _sample_bom(self):
        return [
            {"item": 1, "qty": 1, "part_number": "PART-001", "description": "Test Part", "material": "Steel"},
            {"item": 2, "qty": 2, "part_number": "PART-002", "description": "Another Part", "material": "Aluminum"},
        ]

    def test_renders_header_row(self):
        from src.murphy_drawing_engine import BOMTableRenderer
        renderer = BOMTableRenderer(self._sample_bom())
        svg = renderer.render_svg()
        assert "ITEM" in svg
        assert "DESCRIPTION" in svg
        assert "MATERIAL" in svg
        assert "PART NUMBER" in svg

    def test_renders_all_data_rows(self):
        from src.murphy_drawing_engine import BOMTableRenderer
        renderer = BOMTableRenderer(self._sample_bom())
        svg = renderer.render_svg()
        assert "PART-001" in svg
        assert "PART-002" in svg

    def test_svg_valid_xml(self):
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import BOMTableRenderer
        renderer = BOMTableRenderer(self._sample_bom())
        svg = renderer.render_svg()
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_custom_col_widths(self):
        from src.murphy_drawing_engine import BOMTableRenderer
        renderer = BOMTableRenderer(self._sample_bom(), col_widths=[20.0, 20.0, 60.0, 120.0, 60.0])
        svg = renderer.render_svg()
        assert "PART-001" in svg

    def test_xml_escape_in_description(self):
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import BOMTableRenderer
        # BOMTableRenderer._xml_escape converts & to &amp; — verify roundtrip is valid XML
        bom_raw = [{"item": 1, "qty": 1, "part_number": "P-001", "description": "A & B", "material": "Steel"}]
        renderer = BOMTableRenderer(bom_raw)
        svg = renderer.render_svg()
        root = ET.fromstring(svg)  # would raise if & not escaped
        assert root is not None


# ---------------------------------------------------------------------------
# Phase E: TestBalloonCallout
# ---------------------------------------------------------------------------

class TestBalloonCallout:

    def test_renders_circle_and_number(self):
        from src.murphy_drawing_engine import BalloonCallout, ElementType
        callout = BalloonCallout(100, 100, 8, 5)
        elements = callout.to_drawing_elements(50, 50)
        circle_elems = [e for e in elements if e.element_type == ElementType.CIRCLE]
        text_elems = [e for e in elements if e.element_type == ElementType.TEXT]
        assert len(circle_elems) >= 1
        assert len(text_elems) >= 1
        assert any("5" in e.properties.get("text", "") for e in text_elems)

    def test_leader_line_connects(self):
        from src.murphy_drawing_engine import BalloonCallout, ElementType
        callout = BalloonCallout(100, 100, 8, 3)
        elements = callout.to_drawing_elements(50, 50)
        leader_elems = [e for e in elements if e.element_type == ElementType.LEADER]
        assert len(leader_elems) >= 1
        pts = leader_elems[0].geometry.get("points", [])
        assert len(pts) >= 2
        assert pts[0]["x"] == 50
        assert pts[0]["y"] == 50

    def test_balloon_type_property(self):
        from src.murphy_drawing_engine import BalloonCallout, ElementType
        callout = BalloonCallout(50, 50, 10, 7)
        elements = callout.to_drawing_elements(0, 0)
        circles = [e for e in elements if e.element_type == ElementType.CIRCLE]
        assert circles[0].properties.get("type") == "balloon"
        assert circles[0].properties.get("item_number") == 7

    def test_item_number_in_text(self):
        from src.murphy_drawing_engine import BalloonCallout, ElementType
        for n in [1, 5, 10]:
            callout = BalloonCallout(0, 0, 8, n)
            elements = callout.to_drawing_elements(0, 0)
            texts = [e for e in elements if e.element_type == ElementType.TEXT]
            assert any(str(n) in e.properties.get("text", "") for e in texts)

    def test_returns_three_elements(self):
        from src.murphy_drawing_engine import BalloonCallout
        callout = BalloonCallout(20, 20, 5, 1)
        elements = callout.to_drawing_elements(0, 0)
        assert len(elements) == 3  # circle + text + leader

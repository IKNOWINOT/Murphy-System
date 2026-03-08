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

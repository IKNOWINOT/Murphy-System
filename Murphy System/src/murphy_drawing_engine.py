"""
Murphy System - Murphy Drawing Engine
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Discipline(str, Enum):
    """Discipline enumeration."""
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    STRUCTURAL = "structural"
    CIVIL = "civil"
    ARCHITECTURAL = "architectural"
    PIPING = "piping"
    HVAC = "hvac"


class SheetSize(str, Enum):
    """SheetSize enumeration."""
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    ARCH_A = "ARCH_A"
    ARCH_B = "ARCH_B"
    ARCH_C = "ARCH_C"
    ARCH_D = "ARCH_D"
    ARCH_E = "ARCH_E"
    ANSI_A = "ANSI_A"
    ANSI_B = "ANSI_B"
    ANSI_C = "ANSI_C"
    ANSI_D = "ANSI_D"
    ANSI_E = "ANSI_E"


class ElementType(str, Enum):
    """ElementType enumeration."""
    POINT = "point"
    LINE = "line"
    ARC = "arc"
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    SPLINE = "spline"
    TEXT = "text"
    DIMENSION = "dimension"
    LEADER = "leader"
    HATCH = "hatch"
    BLOCK_REF = "block_ref"
    SECTION_VIEW = "section_view"
    DETAIL_VIEW = "detail_view"


class ConstraintType(str, Enum):
    """ConstraintType enumeration."""
    COINCIDENT = "coincident"
    PARALLEL = "parallel"
    PERPENDICULAR = "perpendicular"
    TANGENT = "tangent"
    EQUAL = "equal"
    FIXED = "fixed"
    DIMENSION = "dimension"
    SYMMETRIC = "symmetric"
    CONCENTRIC = "concentric"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DrawingElement(BaseModel):
    """DrawingElement — drawing element definition."""
    element_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    element_type: ElementType
    geometry: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)
    layer: str = "0"
    constraints: List[Dict[str, Any]] = Field(default_factory=list)


class TitleBlock(BaseModel):
    """TitleBlock — title block definition."""
    company: str = ""
    project: str = ""
    drawing_number: str = ""
    revision: str = "A"
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    drawn_by: str = ""
    checked_by: str = ""
    approved_by: str = ""
    pe_stamp_id: Optional[str] = None


class DrawingSheet(BaseModel):
    """DrawingSheet — drawing sheet definition."""
    sheet_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    size: SheetSize = SheetSize.ANSI_D
    title_block: TitleBlock = Field(default_factory=TitleBlock)
    scale: str = "1:1"
    elements: List[DrawingElement] = Field(default_factory=list)
    revision: str = "A"


class DrawingProject(BaseModel):
    """DrawingProject — drawing project definition."""
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    discipline: Discipline = Discipline.MECHANICAL
    units: str = "imperial"
    coordinate_system: str = "cartesian"
    revision_history: List[Dict[str, Any]] = Field(default_factory=list)
    sheets: List[DrawingSheet] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ParametricConstraint(BaseModel):
    """ParametricConstraint — parametric constraint definition."""
    constraint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    constraint_type: ConstraintType
    element_ids: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# BOM Extractor
# ---------------------------------------------------------------------------

class BOMExtractor:
    """Extract Bill of Materials from drawing elements."""

    def extract(self, project: DrawingProject) -> List[Dict[str, Any]]:
        """Return a list of BOM line items from all block references in the project."""
        items: List[Dict[str, Any]] = []
        for sheet in project.sheets:
            for elem in sheet.elements:
                if elem.element_type == ElementType.BLOCK_REF:
                    items.append({
                        "item_number": len(items) + 1,
                        "block_name": elem.properties.get("block_name", "UNKNOWN"),
                        "quantity": elem.properties.get("quantity", 1),
                        "description": elem.properties.get("description", ""),
                        "part_number": elem.properties.get("part_number", ""),
                        "material": elem.properties.get("material", ""),
                        "sheet_id": sheet.sheet_id,
                        "element_id": elem.element_id,
                    })
        return items


# ---------------------------------------------------------------------------
# Drawing Exporter
# ---------------------------------------------------------------------------

class DrawingExporter:
    """Export drawings to DXF (text-based), SVG, and PDF formats."""

    def to_dxf(self, project: DrawingProject) -> str:
        """Generate a minimal DXF R12 ASCII string from the project."""
        lines: List[str] = []
        lines.append("0\nSECTION\n2\nHEADER\n0\nENDSEC")
        lines.append("0\nSECTION\n2\nENTITIES")
        for sheet in project.sheets:
            for elem in sheet.elements:
                if elem.element_type == ElementType.LINE:
                    g = elem.geometry
                    lines.append(
                        "0\nLINE\n"
                        f"8\n{elem.layer}\n"
                        f"10\n{g.get('x1', 0.0)}\n"
                        f"20\n{g.get('y1', 0.0)}\n"
                        f"30\n{g.get('z1', 0.0)}\n"
                        f"11\n{g.get('x2', 0.0)}\n"
                        f"21\n{g.get('y2', 0.0)}\n"
                        f"31\n{g.get('z2', 0.0)}"
                    )
                elif elem.element_type == ElementType.CIRCLE:
                    g = elem.geometry
                    lines.append(
                        "0\nCIRCLE\n"
                        f"8\n{elem.layer}\n"
                        f"10\n{g.get('cx', 0.0)}\n"
                        f"20\n{g.get('cy', 0.0)}\n"
                        f"30\n{g.get('cz', 0.0)}\n"
                        f"40\n{g.get('radius', 1.0)}"
                    )
                elif elem.element_type == ElementType.TEXT:
                    g = elem.geometry
                    lines.append(
                        "0\nTEXT\n"
                        f"8\n{elem.layer}\n"
                        f"10\n{g.get('x', 0.0)}\n"
                        f"20\n{g.get('y', 0.0)}\n"
                        f"30\n{g.get('z', 0.0)}\n"
                        f"40\n{g.get('height', 2.5)}\n"
                        f"1\n{elem.properties.get('text', '')}"
                    )
        lines.append("0\nENDSEC\n0\nEOF")
        return "\n".join(lines)

    def to_svg(self, project: DrawingProject, width: int = 800, height: int = 600) -> str:
        """Generate a minimal SVG string from the project."""
        svg_elements: List[str] = []
        for sheet in project.sheets:
            for elem in sheet.elements:
                if elem.element_type == ElementType.LINE:
                    g = elem.geometry
                    svg_elements.append(
                        f'<line x1="{g.get("x1", 0)}" y1="{g.get("y1", 0)}" '
                        f'x2="{g.get("x2", 0)}" y2="{g.get("y2", 0)}" '
                        f'stroke="black" stroke-width="1"/>'
                    )
                elif elem.element_type == ElementType.CIRCLE:
                    g = elem.geometry
                    svg_elements.append(
                        f'<circle cx="{g.get("cx", 0)}" cy="{g.get("cy", 0)}" '
                        f'r="{g.get("radius", 1)}" fill="none" stroke="black" stroke-width="1"/>'
                    )
                elif elem.element_type == ElementType.RECTANGLE:
                    g = elem.geometry
                    svg_elements.append(
                        f'<rect x="{g.get("x", 0)}" y="{g.get("y", 0)}" '
                        f'width="{g.get("width", 10)}" height="{g.get("height", 10)}" '
                        f'fill="none" stroke="black" stroke-width="1"/>'
                    )
                elif elem.element_type == ElementType.TEXT:
                    g = elem.geometry
                    text_val = elem.properties.get("text", "")
                    svg_elements.append(
                        f'<text x="{g.get("x", 0)}" y="{g.get("y", 0)}" '
                        f'font-size="{g.get("height", 12)}">{text_val}</text>'
                    )
        body = "\n  ".join(svg_elements)
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n'
            f'  {body}\n'
            f'</svg>'
        )

    def to_pdf_placeholder(self, project: DrawingProject) -> Dict[str, Any]:
        """Return metadata for PDF generation (actual PDF via reportlab in production)."""
        return {
            "project_id": project.project_id,
            "project_name": project.name,
            "sheets": len(project.sheets),
            "elements": sum(len(s.elements) for s in project.sheets),
            "format": "PDF",
            "note": "PDF rendering requires reportlab. Use to_svg() for immediate output.",
        }


# ---------------------------------------------------------------------------
# Agentic Drawing Assistant
# ---------------------------------------------------------------------------

class AgenticDrawingAssistant:
    """AI-powered drawing assistant that interprets natural-language commands."""

    def __init__(self, project: DrawingProject) -> None:
        self.project = project
        self._command_log: List[Dict[str, Any]] = []

    def execute(self, command: str) -> Dict[str, Any]:
        """
        Parse and execute a natural-language drawing command.

        Examples:
          - "draw a 10x20 rectangle at origin"
          - "add a circle radius 5 at 10,10"
          - "add text 'Murphy Drawing' at 0,0"
          - "create sheet A1"
        """
        cmd = command.strip().lower()
        result: Dict[str, Any] = {"command": command, "success": False, "message": ""}

        try:
            if "rectangle" in cmd:
                result = self._handle_rectangle(command)
            elif "circle" in cmd:
                result = self._handle_circle(command)
            elif "line" in cmd:
                result = self._handle_line(command)
            elif "text" in cmd or "label" in cmd:
                result = self._handle_text(command)
            elif "sheet" in cmd and "create" in cmd:
                result = self._handle_create_sheet(command)
            else:
                result["message"] = f"Command not recognized: '{command}'"
        except Exception as exc:
            logger.warning("AgenticDrawingAssistant.execute error: %s", exc)
            result["message"] = f"Error executing command: {exc}"
            result["success"] = False

        self._command_log.append(result)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_sheet(self) -> DrawingSheet:
        if not self.project.sheets:
            sheet = DrawingSheet()
            self.project.sheets.append(sheet)
        return self.project.sheets[-1]

    def _handle_rectangle(self, command: str) -> Dict[str, Any]:
        import re
        # Try to parse "10x20" dimensions
        dims = re.findall(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)", command)
        coords = re.findall(r"at\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        w = float(dims[0][0]) if dims else 10.0
        h = float(dims[0][1]) if dims else 10.0
        x = float(coords[0][0]) if coords else 0.0
        y = float(coords[0][1]) if coords else 0.0
        elem = DrawingElement(
            element_type=ElementType.RECTANGLE,
            geometry={"x": x, "y": y, "width": w, "height": h},
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Rectangle {w}x{h} at ({x},{y}) added",
            "element_id": elem.element_id,
        }

    def _handle_circle(self, command: str) -> Dict[str, Any]:
        import re
        r_match = re.findall(r"radius\s+(\d+(?:\.\d+)?)", command, re.IGNORECASE)
        coords = re.findall(r"at\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        radius = float(r_match[0]) if r_match else 5.0
        cx = float(coords[0][0]) if coords else 0.0
        cy = float(coords[0][1]) if coords else 0.0
        elem = DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": cx, "cy": cy, "cz": 0.0, "radius": radius},
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Circle radius={radius} at ({cx},{cy}) added",
            "element_id": elem.element_id,
        }

    def _handle_line(self, command: str) -> Dict[str, Any]:
        import re
        pts = re.findall(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        x1, y1 = (float(pts[0][0]), float(pts[0][1])) if len(pts) > 0 else (0.0, 0.0)
        x2, y2 = (float(pts[1][0]), float(pts[1][1])) if len(pts) > 1 else (10.0, 10.0)
        elem = DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": x1, "y1": y1, "z1": 0.0, "x2": x2, "y2": y2, "z2": 0.0},
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Line from ({x1},{y1}) to ({x2},{y2}) added",
            "element_id": elem.element_id,
        }

    def _handle_text(self, command: str) -> Dict[str, Any]:
        import re
        text_match = re.findall(r"['\"]([^'\"]+)['\"]", command)
        coords = re.findall(r"at\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        text_val = text_match[0] if text_match else "Label"
        x = float(coords[0][0]) if coords else 0.0
        y = float(coords[0][1]) if coords else 0.0
        elem = DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": x, "y": y, "z": 0.0, "height": 2.5},
            properties={"text": text_val},
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Text '{text_val}' at ({x},{y}) added",
            "element_id": elem.element_id,
        }

    def _handle_create_sheet(self, command: str) -> Dict[str, Any]:
        import re
        size_match = re.findall(
            r"\b(A0|A1|A2|A3|A4|ARCH_[A-E]|ANSI_[A-E])\b", command, re.IGNORECASE
        )
        size = SheetSize(size_match[0].upper()) if size_match else SheetSize.ANSI_D
        sheet = DrawingSheet(size=size)
        self.project.sheets.append(sheet)
        return {
            "command": command,
            "success": True,
            "message": f"Sheet {size} created",
            "sheet_id": sheet.sheet_id,
        }

    def get_command_log(self) -> List[Dict[str, Any]]:
        """Return the history of executed commands."""
        return list(self._command_log)

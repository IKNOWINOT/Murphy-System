"""
Murphy System - Murphy Drawing Engine
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import math
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

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


class LineStyle(str, Enum):
    """ASME Y14.2 line convention types."""
    CONTINUOUS = "continuous"        # visible lines, 0.5 mm
    HIDDEN = "hidden"                # hidden/dashed lines, 0.35 mm
    CENTER = "center"                # centerlines, long-short dash, 0.25 mm
    PHANTOM = "phantom"              # phantom lines, long-short-short, 0.25 mm
    DIMENSION = "dimension"          # dimension / extension lines, thin, 0.25 mm
    CUTTING_PLANE = "cutting_plane"  # cutting plane lines, thick, 0.5 mm


# ASME Y14.2 SVG rendering attributes keyed by LineStyle
LINE_STYLE_SVG: Dict[LineStyle, Dict[str, str]] = {
    LineStyle.CONTINUOUS: {"stroke-dasharray": "none", "stroke-width": "0.5"},
    LineStyle.HIDDEN: {"stroke-dasharray": "4,2", "stroke-width": "0.35"},
    LineStyle.CENTER: {"stroke-dasharray": "12,3,3,3", "stroke-width": "0.25"},
    LineStyle.PHANTOM: {"stroke-dasharray": "12,3,3,3,3,3", "stroke-width": "0.25"},
    LineStyle.DIMENSION: {"stroke-dasharray": "none", "stroke-width": "0.25"},
    LineStyle.CUTTING_PLANE: {"stroke-dasharray": "12,3,3,3", "stroke-width": "0.5"},
}

# ASME Y14.2 DXF R12 linetype names keyed by LineStyle
LINE_STYLE_DXF: Dict[LineStyle, str] = {
    LineStyle.CONTINUOUS: "CONTINUOUS",
    LineStyle.HIDDEN: "HIDDEN",
    LineStyle.CENTER: "CENTER",
    LineStyle.PHANTOM: "PHANTOM",
    LineStyle.DIMENSION: "CONTINUOUS",
    LineStyle.CUTTING_PLANE: "CENTER2",
}


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
    line_style: LineStyle = LineStyle.CONTINUOUS
    line_weight: float = 0.5


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

    # ------------------------------------------------------------------
    # SVG defs builders
    # ------------------------------------------------------------------

    @staticmethod
    def _svg_arrow_marker_defs() -> str:
        """Return SVG <marker> definitions for dimension/leader arrows."""
        return (
            '<marker id="arrow-start" markerWidth="10" markerHeight="7" '
            'refX="0" refY="3.5" orient="auto">'
            '<polygon points="10 0, 10 7, 0 3.5" fill="black"/></marker>\n'
            '    <marker id="arrow-end" markerWidth="10" markerHeight="7" '
            'refX="10" refY="3.5" orient="auto-start-reverse">'
            '<polygon points="10 0, 10 7, 0 3.5" fill="black"/></marker>'
        )

    @staticmethod
    def _svg_hatch_pattern_defs() -> str:
        """Return SVG <pattern> definitions for standard ANSI hatch styles."""
        return (
            '<pattern id="hatch-ansi31" patternUnits="userSpaceOnUse" '
            'width="8" height="8" patternTransform="rotate(45)">'
            '<line x1="0" y1="0" x2="0" y2="8" stroke="black" stroke-width="0.5"/>'
            '</pattern>\n'
            '    <pattern id="hatch-ansi32" patternUnits="userSpaceOnUse" '
            'width="8" height="8" patternTransform="rotate(45)">'
            '<line x1="0" y1="0" x2="0" y2="8" stroke="black" stroke-width="0.5"/>'
            '<line x1="4" y1="0" x2="4" y2="8" stroke="black" stroke-width="0.5"/>'
            '</pattern>\n'
            '    <pattern id="hatch-ansi33" patternUnits="userSpaceOnUse" '
            'width="8" height="8" patternTransform="rotate(30)">'
            '<line x1="0" y1="0" x2="0" y2="8" stroke="black" stroke-width="0.5"/>'
            '<line x1="4" y1="0" x2="4" y2="8" stroke="black" stroke-width="0.75"/>'
            '</pattern>\n'
            '    <pattern id="hatch-ansi37" patternUnits="userSpaceOnUse" '
            'width="10" height="10">'
            '<rect width="10" height="10" fill="none" stroke="black" stroke-width="0.3"/>'
            '<line x1="0" y1="5" x2="10" y2="5" stroke="black" stroke-width="0.3"/>'
            '</pattern>'
        )

    @staticmethod
    def _svg_stroke_attrs(elem: "DrawingElement") -> str:
        """Return SVG stroke attributes from element line_style and line_weight."""
        ls = LINE_STYLE_SVG.get(elem.line_style, LINE_STYLE_SVG[LineStyle.CONTINUOUS])
        weight = elem.line_weight
        attrs = f'stroke="black" stroke-width="{weight}"'
        dasharray = ls.get("stroke-dasharray", "none")
        if dasharray and dasharray != "none":
            attrs += f' stroke-dasharray="{dasharray}"'
        return attrs

    def to_dxf(self, project: DrawingProject) -> str:
        """Generate DXF R12 ASCII string with TABLES/LTYPE section from the project."""
        lines: List[str] = []
        # HEADER section
        lines.append("0\nSECTION\n2\nHEADER\n0\nENDSEC")

        # TABLES section — define standard linetypes per ASME Y14.2
        lines.append("0\nSECTION\n2\nTABLES")
        lines.append("0\nTABLE\n2\nLTYPE")
        _ltype_defs = [
            ("CONTINUOUS", "Solid line", 0, []),
            ("HIDDEN", "__ __ __ __", 2, [4.0, -2.0]),
            ("CENTER", "_____ _ ___", 4, [12.0, -3.0, 3.0, -3.0]),
            ("PHANTOM", "____ _ _ ___", 6, [12.0, -3.0, 3.0, -3.0, 3.0, -3.0]),
            ("CENTER2", "___ _ ___", 4, [9.0, -2.0, 2.5, -2.0]),
        ]
        for lt_name, lt_desc, lt_elems, lt_pattern in _ltype_defs:
            pattern_str = "".join(f"49\n{p}\n" for p in lt_pattern)
            lines.append(
                f"0\nLTYPE\n2\n{lt_name}\n70\n0\n3\n{lt_desc}\n"
                f"72\n65\n73\n{lt_elems}\n40\n{sum(abs(p) for p in lt_pattern):.1f}\n"
                f"{pattern_str}"
            )
        lines.append("0\nENDTAB")
        lines.append("0\nENDSEC")

        # TABLES section — layer and linetype definitions
        lines.append("0\nSECTION\n2\nTABLES")
        lines.append(
            "0\nTABLE\n2\nLTYPE\n70\n6\n"
            "0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolid line\n72\n65\n73\n0\n40\n0.0\n"
            "0\nLTYPE\n2\nDASHED\n70\n0\n3\nDashed\n72\n65\n73\n2\n40\n0.75\n49\n0.5\n49\n-0.25\n"
            "0\nLTYPE\n2\nCENTER\n70\n0\n3\nCenter\n72\n65\n73\n4\n40\n2.0\n49\n1.25\n49\n-0.25\n49\n0.25\n49\n-0.25\n"
            "0\nLTYPE\n2\nPHANTOM\n70\n0\n3\nPhantom\n72\n65\n73\n6\n40\n2.5\n49\n1.25\n49\n-0.25\n49\n0.25\n49\n-0.25\n49\n0.25\n49\n-0.25\n"
            "0\nENDTAB"
        )
        lines.append(
            "0\nTABLE\n2\nLAYER\n70\n4\n"
            "0\nLAYER\n2\n0\n70\n0\n62\n7\n6\nCONTINUOUS\n"
            "0\nLAYER\n2\nCENTERLINES\n70\n0\n62\n1\n6\nCENTER\n"
            "0\nLAYER\n2\nHIDDEN\n70\n0\n62\n3\n6\nDASHED\n"
            "0\nLAYER\n2\nDIMENSIONS\n70\n0\n62\n2\n6\nCONTINUOUS\n"
            "0\nENDTAB"
        )
        lines.append("0\nENDSEC")
        # ENTITIES section
        lines.append("0\nSECTION\n2\nENTITIES")
        for sheet in project.sheets:
            for elem in sheet.elements:
                ltype = LINE_STYLE_DXF.get(elem.line_style, "CONTINUOUS")
                if elem.element_type == ElementType.LINE:
                    g = elem.geometry
                    lines.append(
                        "0\nLINE\n"
                        f"8\n{elem.layer}\n"
                        f"6\n{ltype}\n"
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
                        f"6\n{ltype}\n"
                        f"10\n{g.get('cx', 0.0)}\n"
                        f"20\n{g.get('cy', 0.0)}\n"
                        f"30\n{g.get('cz', 0.0)}\n"
                        f"40\n{g.get('radius', 1.0)}"
                    )
                elif elem.element_type == ElementType.ARC:
                    g = elem.geometry
                    lines.append(
                        "0\nARC\n"
                        f"8\n{elem.layer}\n"
                        f"6\n{ltype}\n"
                        f"10\n{g.get('cx', 0.0)}\n"
                        f"20\n{g.get('cy', 0.0)}\n"
                        f"30\n{g.get('cz', 0.0)}\n"
                        f"40\n{g.get('radius', 1.0)}\n"
                        f"50\n{g.get('start_angle', 0.0)}\n"
                        f"51\n{g.get('end_angle', 90.0)}"
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
                elif elem.element_type == ElementType.DIMENSION:
                    # Emit dimension as paired lines + text in DXF R12
                    g = elem.geometry
                    x1 = g.get("x1", 0.0)
                    y1 = g.get("y1", 0.0)
                    x2 = g.get("x2", 10.0)
                    y2 = g.get("y2", 0.0)
                    offset = g.get("offset", 10.0)
                    dim_text = elem.properties.get("text", "")
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2 - offset
                    # Dimension line
                    lines.append(
                        f"0\nLINE\n8\nDIMENSIONS\n"
                        f"10\n{x1}\n20\n{y1 - offset}\n30\n0.0\n"
                        f"11\n{x2}\n21\n{y2 - offset}\n31\n0.0"
                    )
                    # Extension lines
                    lines.append(
                        f"0\nLINE\n8\nDIMENSIONS\n"
                        f"10\n{x1}\n20\n{y1}\n30\n0.0\n"
                        f"11\n{x1}\n21\n{y1 - offset}\n31\n0.0"
                    )
                    lines.append(
                        f"0\nLINE\n8\nDIMENSIONS\n"
                        f"10\n{x2}\n20\n{y2}\n30\n0.0\n"
                        f"11\n{x2}\n21\n{y2 - offset}\n31\n0.0"
                    )
                    if dim_text:
                        lines.append(
                            f"0\nTEXT\n8\nDIMENSIONS\n"
                            f"10\n{mid_x}\n20\n{mid_y}\n30\n0.0\n"
                            f"40\n2.5\n1\n{dim_text}"
                        )
                elif elem.element_type == ElementType.HATCH:
                    # Emit hatch boundary as LINE entities
                    g = elem.geometry
                    boundary = g.get("boundary", [])
                    for i in range(len(boundary)):
                        p1 = boundary[i]
                        p2 = boundary[(i + 1) % len(boundary)]
                        lines.append(
                            f"0\nLINE\n8\n{elem.layer}\n"
                            f"10\n{p1.get('x', 0.0)}\n20\n{p1.get('y', 0.0)}\n30\n0.0\n"
                            f"11\n{p2.get('x', 0.0)}\n21\n{p2.get('y', 0.0)}\n31\n0.0"
                        )
        lines.append("0\nENDSEC\n0\nEOF")
        return "\n".join(lines)

    # Render priority for SVG z-ordering: lower numbers paint first (background).
    _ELEMENT_RENDER_ORDER: Dict[str, int] = {
        ElementType.HATCH: 0,
        ElementType.RECTANGLE: 1,
        ElementType.LINE: 1,
        ElementType.CIRCLE: 2,
        ElementType.ARC: 2,
        ElementType.POLYGON: 2,
        ElementType.SECTION_VIEW: 2,
        ElementType.DETAIL_VIEW: 2,
        ElementType.DIMENSION: 3,
        ElementType.LEADER: 3,
        ElementType.TEXT: 4,
        ElementType.POINT: 4,
        ElementType.SPLINE: 4,
        ElementType.BLOCK_REF: 5,
    }

    def to_svg(self, project: DrawingProject, width: int = 800, height: int = 600) -> str:
        """Generate an SVG string with viewBox, line styles, and extended element support."""
        defs_parts: List[str] = [
            self._svg_arrow_marker_defs(),
            self._svg_hatch_pattern_defs(),
        ]
        clip_defs: List[str] = []

        svg_elements: List[str] = []
        for sheet in project.sheets:
            # Sort elements by render order so that hatches paint first (background),
            # structural geometry next, and annotations / title block on top.
            sorted_elems = sorted(
                sheet.elements,
                key=lambda e: self._ELEMENT_RENDER_ORDER.get(e.element_type, 99),
            )
            for elem in sorted_elems:
                ls = LINE_STYLE_SVG.get(
                    elem.line_style, LINE_STYLE_SVG[LineStyle.CONTINUOUS]
                )
                stroke_w = ls["stroke-width"]
                dash = f' stroke-dasharray="{ls["stroke-dasharray"]}"' if ls["stroke-dasharray"] != "none" else ""
                base_attrs = f'stroke="black" stroke-width="{stroke_w}"{dash}'

                if elem.element_type == ElementType.LINE:
                    g = elem.geometry
                    svg_elements.append(
                        f'<line x1="{g.get("x1", 0)}" y1="{g.get("y1", 0)}" '
                        f'x2="{g.get("x2", 0)}" y2="{g.get("y2", 0)}" '
                        f'{base_attrs}/>'
                    )
                elif elem.element_type == ElementType.CIRCLE:
                    g = elem.geometry
                    svg_elements.append(
                        f'<circle cx="{g.get("cx", 0)}" cy="{g.get("cy", 0)}" '
                        f'r="{g.get("radius", 1)}" fill="none" {base_attrs}/>'
                    )
                elif elem.element_type == ElementType.RECTANGLE:
                    g = elem.geometry
                    svg_elements.append(
                        f'<rect x="{g.get("x", 0)}" y="{g.get("y", 0)}" '
                        f'width="{g.get("width", 10)}" height="{g.get("height", 10)}" '
                        f'fill="none" {base_attrs}/>'
                    )
                elif elem.element_type == ElementType.TEXT:
                    g = elem.geometry
                    text_val = elem.properties.get("text", "")
                    font_size = max(g.get("height", 12), 8)
                    svg_elements.append(
                        f'<text x="{g.get("x", 0)}" y="{g.get("y", 0)}" '
                        f'font-size="{font_size}" font-family="sans-serif" fill="black">{text_val}</text>'
                    )
                elif elem.element_type == ElementType.ARC:
                    g = elem.geometry
                    cx = g.get("cx", 0)
                    cy = g.get("cy", 0)
                    r = g.get("radius", 10)
                    start_deg = g.get("start_angle", 0)
                    end_deg = g.get("end_angle", 90)
                    start_rad = math.radians(start_deg)
                    end_rad = math.radians(end_deg)
                    x1 = cx + r * math.cos(start_rad)
                    y1 = cy + r * math.sin(start_rad)
                    x2 = cx + r * math.cos(end_rad)
                    y2 = cy + r * math.sin(end_rad)
                    large_arc = 1 if (end_deg - start_deg) % 360 > 180 else 0
                    svg_elements.append(
                        f'<path d="M {x1:.3f} {y1:.3f} A {r} {r} 0 {large_arc} 1 {x2:.3f} {y2:.3f}" '
                        f'fill="none" {base_attrs}/>'
                    )
                elif elem.element_type == ElementType.POLYGON:
                    g = elem.geometry
                    verts = g.get("vertices", [])
                    if verts:
                        pts_str = " ".join(f'{v.get("x",0)},{v.get("y",0)}' for v in verts)
                        svg_elements.append(
                            f'<polygon points="{pts_str}" fill="none" {base_attrs}/>'
                        )
                elif elem.element_type == ElementType.DIMENSION:
                    svg_elements.extend(self._render_dimension_svg(elem, base_attrs))
                elif elem.element_type == ElementType.HATCH:
                    hatch_parts = self._render_hatch_svg(elem)
                    # First element from _render_hatch_svg is the <clipPath> — move it to defs
                    if hatch_parts and hatch_parts[0].startswith("<clipPath"):
                        clip_defs.append(hatch_parts[0])
                        svg_elements.extend(hatch_parts[1:])
                    else:
                        svg_elements.extend(hatch_parts)
                elif elem.element_type == ElementType.LEADER:
                    svg_elements.extend(self._render_leader_svg(elem, base_attrs))

            # Title block renders last — on top of all drawing elements.
            tb = sheet.title_block
            if tb.company or tb.drawing_number or tb.drawn_by:
                svg_elements.extend(self._render_title_block_svg(tb, width, height))

        all_defs = defs_parts + clip_defs
        defs = "  <defs>\n    " + "\n    ".join(all_defs) + "\n  </defs>"
        body = "\n  ".join(svg_elements)
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n'
            f'{defs}\n'
            f'  {body}\n'
            f'</svg>'
        )

    # ------------------------------------------------------------------
    # SVG helpers for advanced element types
    # ------------------------------------------------------------------

    def _render_title_block_svg(self, tb: "TitleBlock", width: int, height: int) -> List[str]:
        """Render a title block border with fields in the lower-right corner."""
        tw, th = min(width, 280), 60
        tx = width - tw - 5
        ty = height - th - 5
        parts: List[str] = [
            f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" '
            f'fill="white" stroke="black" stroke-width="0.5"/>',
            f'<text x="{tx+4}" y="{ty+12}" font-size="8" font-weight="bold" fill="black">{tb.company}</text>',
            f'<text x="{tx+4}" y="{ty+24}" font-size="8" fill="black">{tb.project}</text>',
            f'<text x="{tx+4}" y="{ty+36}" font-size="8" fill="black">DWG: {tb.drawing_number}</text>',
            f'<text x="{tx+4}" y="{ty+48}" font-size="8" fill="black">'
            f'By: {tb.drawn_by}  Chk: {tb.checked_by}  Rev: {tb.revision}</text>',
        ]
        if tb.pe_stamp_id:
            parts.append(
                f'<circle cx="{tx+tw-20}" cy="{ty+30}" r="18" fill="none" '
                f'stroke="black" stroke-width="0.5"/>'
            )
            parts.append(
                f'<text x="{tx+tw-20}" y="{ty+34}" font-size="8" text-anchor="middle" fill="black">'
                f'PE STAMP</text>'
            )
        return parts

    def _render_dimension_svg(self, elem: "DrawingElement", base_attrs: str) -> List[str]:
        """Render a DIMENSION element: extension lines, dimension line, arrowheads, text."""
        g = elem.geometry
        x1, y1 = g.get("x1", 0), g.get("y1", 0)
        x2, y2 = g.get("x2", 100), g.get("y2", 0)
        offset = g.get("offset", 10)
        text_val = elem.properties.get("text", "") or elem.properties.get("dimension_text", "")
        dim_attrs = 'stroke="black" stroke-width="0.25"'

        # dimension line (parallel to feature, offset) — use SVG markers for arrowheads
        dy1, dy2 = y1 - offset, y2 - offset
        parts: List[str] = [
            f'<line x1="{x1}" y1="{y1}" x2="{x1}" y2="{dy1}" {dim_attrs}/>',
            f'<line x1="{x2}" y1="{y2}" x2="{x2}" y2="{dy2}" {dim_attrs}/>',
            f'<line x1="{x1}" y1="{dy1}" x2="{x2}" y2="{dy2}" {dim_attrs} '
            f'marker-start="url(#arrow-start)" marker-end="url(#arrow-end)"/>',
        ]
        # dimension text centred on the dimension line
        mid_x = (x1 + x2) / 2
        if text_val:
            parts.append(
                f'<text x="{mid_x}" y="{dy1-2}" font-size="10" font-family="sans-serif" '
                f'text-anchor="middle" fill="black">{text_val}</text>'
            )
        return parts

    def _render_hatch_svg(self, elem: "DrawingElement") -> List[str]:
        """Render a HATCH element as 45° parallel line pattern within a bounding rect."""
        g = elem.geometry
        x, y = g.get("x", 0), g.get("y", 0)
        w, h = g.get("width", 50), g.get("height", 50)
        spacing = g.get("spacing", 5)
        angle_deg = g.get("angle", 45)
        pid = f"hatch_{elem.element_id[:8]}"
        tan_a = math.tan(math.radians(angle_deg)) if angle_deg != 90 else 1e9
        hatch_lines: List[str] = []
        step = spacing
        total = int((w + h) / step) + 2
        for i in range(-total, total):
            offset_x = i * step
            if abs(tan_a) > 1e8:
                x0, x1c = x + offset_x, x + offset_x
                y0, y1c = y, y + h
            else:
                x0, y0 = x + offset_x, y
                x1c = x0 + h / tan_a if tan_a != 0 else x0
                y1c = y + h
            hatch_lines.append(
                f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1c:.2f}" y2="{y1c:.2f}" '
                f'stroke="black" stroke-width="0.25" clip-path="url(#{pid}_clip)"/>'
            )
        border = (
            f'<clipPath id="{pid}_clip">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>'
            f'</clipPath>'
        )
        outline = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'fill="none" stroke="black" stroke-width="0.5"/>'
        )
        return [border] + hatch_lines + [outline]

    def _render_leader_svg(self, elem: "DrawingElement", base_attrs: str) -> List[str]:
        """Render a LEADER element: arrowhead line with annotation text."""
        g = elem.geometry
        pts = g.get("points", [])
        if len(pts) < 2:
            return []
        text_val = elem.properties.get("text", "")
        segs: List[str] = []
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            # Place arrowhead marker at the start of the first segment
            marker_attr = ' marker-start="url(#arrow-start)"' if i == 0 else ""
            segs.append(
                f'<line x1="{p0.get("x",0)}" y1="{p0.get("y",0)}" '
                f'x2="{p1.get("x",0)}" y2="{p1.get("y",0)}" {base_attrs}{marker_attr}/>'
            )
        if text_val:
            last = pts[-1]
            segs.append(
                f'<text x="{last.get("x",0)+2}" y="{last.get("y",0)}" '
                f'font-size="10" font-family="sans-serif" fill="black">{text_val}</text>'
            )
        return segs
    @staticmethod
    def _svg_title_block(tb: "TitleBlock", width: int, height: int) -> List[str]:
        """Render the title block as SVG elements at the bottom-right of the sheet."""
        bx = width - 200
        by = height - 60
        return [
            f'<rect x="{bx}" y="{by}" width="200" height="60" '
            f'fill="white" stroke="black" stroke-width="0.5"/>',
            f'<text x="{bx + 5}" y="{by + 12}" font-size="8" font-family="sans-serif" fill="black">'
            f'{tb.company}</text>',
            f'<text x="{bx + 5}" y="{by + 24}" font-size="8" font-family="sans-serif" fill="black">'
            f'DWG: {tb.drawing_number}  REV: {tb.revision}</text>',
            f'<text x="{bx + 5}" y="{by + 36}" font-size="8" font-family="sans-serif" fill="black">'
            f'BY: {tb.drawn_by}  CHK: {tb.checked_by}</text>',
            f'<text x="{bx + 5}" y="{by + 48}" font-size="8" font-family="sans-serif" fill="black">'
            f'APPR: {tb.approved_by}  DATE: {tb.date}</text>',
            f'<text x="{bx + 5}" y="{by + 58}" font-size="8" font-family="sans-serif" fill="black">'
            f'PE: {tb.pe_stamp_id or "N/A"}</text>',
        ]

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
          - "add centerline from (0,0) to (100,0)"
          - "add dimension from (0,0) to (100,0)"
          - "draw motor at 50,50"
          - "create pump assembly"
          - "draw isometric box 100x50x80 at 0,0,0"
          - "add balloon 3 at 200,150"
          - "add cutting plane from (50,100) to (250,100) label A-A"
        """
        cmd = command.strip().lower()
        result: Dict[str, Any] = {"command": command, "success": False, "message": ""}

        try:
            if "isometric box" in cmd or "iso box" in cmd:
                result = self._handle_isometric_box(command)
            elif "balloon" in cmd and ("add" in cmd or "draw" in cmd):
                result = self._handle_balloon_callout(command)
            elif "cutting plane" in cmd:
                result = self._handle_cutting_plane(command)
            elif "pump assembly" in cmd or "pump_assembly" in cmd:
                result = self._handle_pump_assembly(command)
            elif "centerline" in cmd:
                result = self._handle_centerline(command)
            elif "dimension" in cmd and ("add" in cmd or "draw" in cmd):
                result = self._handle_dimension(command)
            elif "motor" in cmd and "draw" in cmd:
                result = self._handle_motor(command)
            elif "rectangle" in cmd:
                result = self._handle_rectangle(command)
            elif "circle" in cmd:
                result = self._handle_circle(command)
            elif "polygon" in cmd:
                result = self._handle_polygon(command)
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

        capped_append(self._command_log, result)
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

    def _handle_polygon(self, command: str) -> Dict[str, Any]:
        import re
        # Parse coordinate pairs like "(x,y)" from the command
        pts = re.findall(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        if len(pts) < 3:
            # Default triangle
            pts = [("0", "0"), ("10", "0"), ("5", "10")]
        vertices = [{"x": float(p[0]), "y": float(p[1])} for p in pts]
        elem = DrawingElement(
            element_type=ElementType.POLYGON,
            geometry={"vertices": vertices},
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Polygon with {len(vertices)} vertices added",
            "element_id": elem.element_id,
        }

    def _handle_centerline(self, command: str) -> Dict[str, Any]:
        import re
        pts = re.findall(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        x1, y1 = (float(pts[0][0]), float(pts[0][1])) if len(pts) > 0 else (0.0, 0.0)
        x2, y2 = (float(pts[1][0]), float(pts[1][1])) if len(pts) > 1 else (100.0, 0.0)
        elem = DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": x1, "y1": y1, "z1": 0.0, "x2": x2, "y2": y2, "z2": 0.0},
            layer="CENTERLINES",
            line_style=LineStyle.CENTER,
            line_weight=0.35,
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        # Add "CL" label near start
        label = DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": x1 - 8, "y": y1, "z": 0.0, "height": 2.5},
            properties={"text": "CL"},
            layer="CENTERLINES",
        )
        sheet.elements.append(label)
        return {
            "command": command,
            "success": True,
            "message": f"Centerline from ({x1},{y1}) to ({x2},{y2}) added",
            "element_id": elem.element_id,
        }

    def _handle_dimension(self, command: str) -> Dict[str, Any]:
        import re
        pts = re.findall(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        x1, y1 = (float(pts[0][0]), float(pts[0][1])) if len(pts) > 0 else (0.0, 0.0)
        x2, y2 = (float(pts[1][0]), float(pts[1][1])) if len(pts) > 1 else (100.0, 0.0)
        distance = math.hypot(x2 - x1, y2 - y1)
        dim_text = f"{distance:.1f}"
        elem = DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": x1, "y1": y1, "x2": x2, "y2": y2, "offset": 15.0},
            properties={"text": dim_text},
            layer="DIMENSIONS",
            line_style=LineStyle.DIMENSION,
            line_weight=0.25,
        )
        sheet = self._get_or_create_sheet()
        sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Dimension {dim_text} from ({x1},{y1}) to ({x2},{y2}) added",
            "element_id": elem.element_id,
        }

    def _handle_motor(self, command: str) -> Dict[str, Any]:
        import re
        coords = re.findall(r"at\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        x = float(coords[0][0]) if coords else 0.0
        y = float(coords[0][1]) if coords else 0.0
        sheet = self._get_or_create_sheet()
        elements = EngineeringSymbolLibrary.motor(x, y, 60.0, 40.0)
        for e in elements:
            sheet.elements.append(e)
        return {
            "command": command,
            "success": True,
            "message": f"Motor symbol at ({x},{y}) added ({len(elements)} elements)",
        }

    def _handle_pump_assembly(self, command: str) -> Dict[str, Any]:
        assembly = AssemblyDrawing(self.project)
        assembly.build_pump_assembly()
        return {
            "command": command,
            "success": True,
            "message": "Pump assembly created",
        }

    def _handle_isometric_box(self, command: str) -> Dict[str, Any]:
        """Handle: "draw isometric box WxHxD at X,Y,Z [at origin_x,origin_y]"."""
        import re
        dims = re.findall(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)", command)
        coords = re.findall(r"at\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*(?:,\s*(-?\d+(?:\.\d+)?))?\s*\)?", command)
        w = float(dims[0][0]) if dims else 100.0
        h = float(dims[0][1]) if dims else 50.0
        d = float(dims[0][2]) if dims else 80.0
        if coords:
            bx = float(coords[0][0])
            by = float(coords[0][1])
            bz = float(coords[0][2]) if coords[0][2] else 0.0
        else:
            bx, by, bz = 0.0, 0.0, 0.0
        from murphy_drawing_engine_extensions import IsometricProjector
        proj = IsometricProjector()
        elements = proj.project_box(bx, by, bz, w, h, d)
        sheet = self._get_or_create_sheet()
        for elem in elements:
            sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Isometric box {w}x{h}x{d} at ({bx},{by},{bz}) added ({len(elements)} edges)",
        }

    def _handle_balloon_callout(self, command: str) -> Dict[str, Any]:
        """Handle: "add balloon N at X,Y" — places a numbered balloon at (X,Y)."""
        import re
        num_match = re.findall(r"balloon\s+(\d+)", command, re.IGNORECASE)
        coords = re.findall(r"at\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        item_number = int(num_match[0]) if num_match else 1
        cx = float(coords[0][0]) if coords else 0.0
        cy = float(coords[0][1]) if coords else 0.0
        # Leader tip slightly offset from balloon centre
        lx, ly = cx - 20.0, cy
        from murphy_drawing_engine_extensions import BalloonCallout
        callout = BalloonCallout(cx, cy, r=8.0, item_number=item_number)
        elements = callout.to_drawing_elements(leader_x=lx, leader_y=ly)
        sheet = self._get_or_create_sheet()
        for elem in elements:
            sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Balloon callout {item_number} at ({cx},{cy}) added",
        }

    def _handle_cutting_plane(self, command: str) -> Dict[str, Any]:
        """Handle: "add cutting plane from X1,Y1 to X2,Y2 [label L]"."""
        import re
        pts = re.findall(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", command)
        label_match = re.findall(r"label\s+([A-Za-z0-9\-]+)", command, re.IGNORECASE)
        x1, y1 = (float(pts[0][0]), float(pts[0][1])) if len(pts) > 0 else (0.0, 0.0)
        x2, y2 = (float(pts[1][0]), float(pts[1][1])) if len(pts) > 1 else (100.0, 0.0)
        label = label_match[0] if label_match else "A-A"
        from murphy_drawing_engine_extensions import CuttingPlaneLine
        cpl = CuttingPlaneLine(x1, y1, x2, y2, label)
        elements = cpl.to_drawing_elements()
        sheet = self._get_or_create_sheet()
        for elem in elements:
            sheet.elements.append(elem)
        return {
            "command": command,
            "success": True,
            "message": f"Cutting plane {label} from ({x1},{y1}) to ({x2},{y2}) added",
        }

    def get_command_log(self) -> List[Dict[str, Any]]:
        """Return the history of executed commands."""
        return list(self._command_log)


# ---------------------------------------------------------------------------
# Engineering Symbol Library
# ---------------------------------------------------------------------------

class EngineeringSymbolLibrary:
    """
    Factory methods that return lists of DrawingElement representing
    common mechanical/piping engineering symbols.
    """

    @staticmethod
    def motor(x: float, y: float, width: float = 60.0, height: float = 40.0) -> List[DrawingElement]:
        """Motor symbol: rectangle with 'MOTOR' label."""
        return [
            DrawingElement(
                element_type=ElementType.RECTANGLE,
                geometry={"x": x, "y": y, "width": width, "height": height},
                layer="EQUIPMENT",
                line_weight=0.5,
            ),
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": x + width / 2 - 10, "y": y + height / 2, "z": 0.0, "height": 5.0},
                properties={"text": "MOTOR"},
                layer="EQUIPMENT",
            ),
        ]

    @staticmethod
    def pump_housing(x: float, y: float, width: float = 120.0, height: float = 80.0) -> List[DrawingElement]:
        """Pump housing symbol: rectangle with label."""
        return [
            DrawingElement(
                element_type=ElementType.RECTANGLE,
                geometry={"x": x, "y": y, "width": width, "height": height},
                layer="EQUIPMENT",
                line_weight=0.7,
            ),
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": x + 5, "y": y + height / 2, "z": 0.0, "height": 4.5},
                properties={"text": "PUMP HOUSING"},
                layer="EQUIPMENT",
            ),
        ]

    @staticmethod
    def coupling(x: float, y: float, radius: float = 12.0) -> List[DrawingElement]:
        """Coupling symbol: two concentric circles at the shaft connection point."""
        return [
            DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": x, "cy": y, "cz": 0.0, "radius": radius},
                layer="EQUIPMENT",
                line_weight=0.5,
            ),
            DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": x, "cy": y, "cz": 0.0, "radius": radius * 0.5},
                layer="EQUIPMENT",
                line_weight=0.35,
            ),
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": x - 12, "y": y + radius + 6, "z": 0.0, "height": 3.5},
                properties={"text": "COUPLING"},
                layer="EQUIPMENT",
            ),
        ]

    @staticmethod
    def flange(
        cx: float,
        cy: float,
        od: float = 50.0,
        bolt_circle_dia: float = 40.0,
        bolt_count: int = 4,
        bolt_dia: float = 5.0,
    ) -> List[DrawingElement]:
        """Flange symbol: outer circle with bolt holes arranged on the bolt circle."""
        elements: List[DrawingElement] = [
            DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": cx, "cy": cy, "cz": 0.0, "radius": od / 2},
                layer="EQUIPMENT",
                line_weight=0.5,
            ),
        ]
        bolt_r = bolt_circle_dia / 2
        for i in range(bolt_count):
            angle = math.radians(i * 360.0 / bolt_count)
            bx = cx + bolt_r * math.cos(angle)
            by = cy + bolt_r * math.sin(angle)
            elements.append(DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": bx, "cy": by, "cz": 0.0, "radius": bolt_dia / 2},
                layer="EQUIPMENT",
                line_weight=0.35,
            ))
        return elements

    @staticmethod
    def valve(x: float, y: float, valve_type: str = "gate") -> List[DrawingElement]:
        """Valve symbol: two triangles representing a gate/globe valve."""
        half = 10.0
        body_pts = [
            {"x": x - half, "y": y - half},
            {"x": x + half, "y": y},
            {"x": x - half, "y": y + half},
        ]
        actuator_pts = [
            {"x": x + half, "y": y - half},
            {"x": x - half, "y": y},
            {"x": x + half, "y": y + half},
        ]
        return [
            DrawingElement(
                element_type=ElementType.POLYGON,
                geometry={"vertices": body_pts},
                layer="EQUIPMENT",
                line_weight=0.5,
            ),
            DrawingElement(
                element_type=ElementType.POLYGON,
                geometry={"vertices": actuator_pts},
                layer="EQUIPMENT",
                line_weight=0.5,
            ),
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": x - 5, "y": y - half - 4, "z": 0.0, "height": 3.5},
                properties={"text": valve_type.upper()},
                layer="EQUIPMENT",
            ),
        ]

    @staticmethod
    def centerline(x1: float, y1: float, x2: float, y2: float) -> List[DrawingElement]:
        """Centerline: CENTER linestyle line with 'CL' annotation."""
        return [
            DrawingElement(
                element_type=ElementType.LINE,
                geometry={"x1": x1, "y1": y1, "z1": 0.0, "x2": x2, "y2": y2, "z2": 0.0},
                layer="CENTERLINES",
                line_style=LineStyle.CENTER,
                line_weight=0.35,
            ),
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": x1 - 8, "y": y1, "z": 0.0, "height": 3.5},
                properties={"text": "CL"},
                layer="CENTERLINES",
            ),
        ]


# ---------------------------------------------------------------------------
# Assembly Drawing
# ---------------------------------------------------------------------------

class AssemblyDrawing:
    """
    Composes multiple engineering symbols into a complete assembly drawing.
    """

    def __init__(self, project: DrawingProject) -> None:
        self.project = project

    def _get_or_create_sheet(self) -> DrawingSheet:
        if not self.project.sheets:
            sheet = DrawingSheet(size=SheetSize.ANSI_D)
            self.project.sheets.append(sheet)
        return self.project.sheets[-1]

    def build_pump_assembly(self, origin_x: float = 50.0, origin_y: float = 150.0) -> DrawingSheet:
        """
        Build a centrifugal pump GA drawing:
        Motor → Coupling → Pump Housing → Outlet Flange + Inlet Flange.
        Includes centerline through the assembly and title block.
        """
        sheet = self._get_or_create_sheet()
        sym = EngineeringSymbolLibrary

        # Motor
        motor_x = origin_x
        motor_y = origin_y
        motor_w, motor_h = 60.0, 40.0
        for elem in sym.motor(motor_x, motor_y, motor_w, motor_h):
            sheet.elements.append(elem)

        # Coupling — positioned to the right of motor
        coupling_x = motor_x + motor_w + 15.0
        coupling_y = motor_y + motor_h / 2
        for elem in sym.coupling(coupling_x, coupling_y, 12.0):
            sheet.elements.append(elem)

        # Pump housing
        pump_x = coupling_x + 15.0
        pump_y = motor_y
        pump_w, pump_h = 120.0, 80.0
        for elem in sym.pump_housing(pump_x, pump_y, pump_w, pump_h):
            sheet.elements.append(elem)

        # Outlet flange (top of pump housing)
        outlet_cx = pump_x + pump_w / 2
        outlet_cy = pump_y - 30.0
        for elem in sym.flange(outlet_cx, outlet_cy, 40.0, 32.0, 4, 5.0):
            sheet.elements.append(elem)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": outlet_cx - 20, "y": outlet_cy - 25, "z": 0.0, "height": 4.0},
            properties={"text": 'OUTLET 4" FLANGE'},
            layer="ANNOTATIONS",
        ))

        # Inlet flange (right side of pump housing)
        inlet_cx = pump_x + pump_w + 30.0
        inlet_cy = pump_y + pump_h / 2
        for elem in sym.flange(inlet_cx, inlet_cy, 50.0, 40.0, 4, 6.0):
            sheet.elements.append(elem)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": inlet_cx + 30, "y": inlet_cy, "z": 0.0, "height": 4.0},
            properties={"text": 'INLET 6" FLANGE'},
            layer="ANNOTATIONS",
        ))

        # Centerline through the entire assembly
        cl_x1 = motor_x - 10.0
        cl_x2 = inlet_cx + 60.0
        cl_y = motor_y + motor_h / 2
        for elem in sym.centerline(cl_x1, cl_y, cl_x2, cl_y):
            sheet.elements.append(elem)

        # Title block
        sheet.title_block = TitleBlock(
            company="Inoni LLC",
            project="Murphy Pump Station GA",
            drawing_number="MECH-GA-001",
            revision="A",
            drawn_by="Murphy AI",
            checked_by="Engineer",
            approved_by="PE",
        )

        return sheet


# ---------------------------------------------------------------------------
# Drawing Approval Integration
# ---------------------------------------------------------------------------

class DrawingApprovalIntegration:
    """
    Wire a DrawingProject to a CredentialGatedApproval instance.
    Serializes the project to bytes and requests PE-stamped approval.
    """

    def __init__(self, gated_approval: Any) -> None:
        """
        gated_approval: a CredentialGatedApproval instance (from murphy_credential_gate).
        Accepts Any to avoid a hard circular import at module load.
        """
        self._gated_approval = gated_approval

    def request_pe_stamp(
        self,
        project: DrawingProject,
        approver_credential_id: str,
        required_credential_types: Optional[Any] = None,
        jurisdiction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Serialize the project and request credential-gated approval.
        Returns the approval record as a dict.
        """
        import json
        doc_bytes = project.model_dump_json().encode() if hasattr(project, "model_dump_json") else (
            json.dumps(project.dict()).encode()
        )
        record = self._gated_approval.request_approval(
            document_id=project.project_id,
            document_bytes=doc_bytes,
            approver_credential_id=approver_credential_id,
            required_credential_types=required_credential_types or [],
            jurisdiction=jurisdiction,
        )
        return {
            "approval_id": record.approval_id,
            "document_id": record.document_id,
            "status": record.approval_status.value,
            "notes": record.notes,
            "has_stamp": record.e_stamp is not None,
        }


# ---------------------------------------------------------------------------
# Re-export from extensions module for convenient single-import access
# ---------------------------------------------------------------------------

from murphy_drawing_engine_extensions import (  # noqa: E402
    EngineeringSymbol,
    DrawingBorder,
    build_pump_ga_drawing,
    IsometricProjector,
    ExplodedViewBuilder,
    BalloonCallout,
    BOMTableRenderer,
    CuttingPlaneLine,
    SpeakerAssemblyDrawing,
)


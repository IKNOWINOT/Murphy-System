"""
Murphy System - Murphy Drawing Engine Extensions
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Engineering symbol library, drawing border/frame, and demo drawing builder.
Imported by murphy_drawing_engine.py to keep that module under the 1000-line limit.
"""

from __future__ import annotations
import logging

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Engineering Symbol Library (ISA 5.1 / IEC 60617 conventions)
# ---------------------------------------------------------------------------

class EngineeringSymbol:
    """
    SVG symbol library for engineering drawings.
    Provides centrifugal pump, gate valve, check valve, and instrument bubble
    per ISA 5.1 / IEC 60617 conventions.  All methods return raw SVG strings
    that can be embedded directly inside an <svg> element.
    """

    @staticmethod
    def centrifugal_pump(x: float = 0, y: float = 0, size: float = 30) -> str:
        """Centrifugal pump symbol: circle (casing) + two tangent lines (nozzles)."""
        r = size / 2
        cx, cy = x + r, y + r
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="black" stroke-width="0.5"/>'
            f'<line x1="{cx-r}" y1="{cy}" x2="{cx+r}" y2="{cy}" '
            f'stroke="black" stroke-width="0.5"/>'
            f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy+r}" '
            f'stroke="black" stroke-width="0.5"/>'
            f'<text x="{cx}" y="{cy+r+8}" font-size="4" text-anchor="middle">P</text>'
        )

    @staticmethod
    def gate_valve(x: float = 0, y: float = 0, size: float = 16) -> str:
        """Gate valve symbol: two opposing triangles representing the gate."""
        half = size / 2
        cx, cy = x + half, y + half
        return (
            f'<polygon points="{cx-half},{cy-half} {cx+half},{cy-half} {cx},{cy}" '
            f'fill="none" stroke="black" stroke-width="0.5"/>'
            f'<polygon points="{cx-half},{cy+half} {cx+half},{cy+half} {cx},{cy}" '
            f'fill="none" stroke="black" stroke-width="0.5"/>'
            f'<line x1="{cx-half}" y1="{cy}" x2="{cx+half}" y2="{cy}" '
            f'stroke="black" stroke-width="0.5"/>'
        )

    @staticmethod
    def check_valve(x: float = 0, y: float = 0, size: float = 16) -> str:
        """Check valve symbol: circle with arrow indicating flow direction."""
        half = size / 2
        cx, cy = x + half, y + half
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{half}" fill="none" '
            f'stroke="black" stroke-width="0.5"/>'
            f'<polygon points="{cx-half*0.6},{cy} {cx+half*0.6},{cy-half*0.5} '
            f'{cx+half*0.6},{cy+half*0.5}" fill="black"/>'
        )

    @staticmethod
    def instrument_bubble(
        x: float = 0, y: float = 0, tag: str = "PI", size: float = 12
    ) -> str:
        """ISA 5.1 instrument bubble: circle with tag text inside."""
        r = size / 2
        cx, cy = x + r, y + r
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="white" '
            f'stroke="black" stroke-width="0.5"/>'
            f'<text x="{cx}" y="{cy+2}" font-size="{r*0.8:.1f}" '
            f'text-anchor="middle">{tag}</text>'
        )


# ---------------------------------------------------------------------------
# Drawing Border / Sheet Frame
# ---------------------------------------------------------------------------

@dataclass
class DrawingBorder:
    """
    Engineering drawing border/frame with zone grid (A-D rows, 1-8 columns).
    Generates SVG that can be embedded as the outermost frame of a sheet.
    """
    margin: float = 10.0
    zone_cols: int = 8
    zone_rows: int = 4
    zone_label_size: float = 3.5

    def to_svg(self, sheet_width: float, sheet_height: float) -> str:
        """Return SVG string for the drawing border frame with zone labels."""
        m = self.margin
        fw = sheet_width - 2 * m
        fh = sheet_height - 2 * m
        col_w = fw / self.zone_cols
        row_h = fh / self.zone_rows
        parts: List[str] = [
            f'<rect x="{m}" y="{m}" width="{fw}" height="{fh}" '
            f'fill="none" stroke="black" stroke-width="0.5"/>',
        ]
        for i in range(self.zone_cols):
            lx = m + (i + 0.5) * col_w
            label = str(i + 1)
            parts.append(
                f'<text x="{lx:.1f}" y="{m - 2:.1f}" font-size="{self.zone_label_size}" '
                f'text-anchor="middle">{label}</text>'
            )
            parts.append(
                f'<text x="{lx:.1f}" y="{m + fh + self.zone_label_size:.1f}" '
                f'font-size="{self.zone_label_size}" text-anchor="middle">{label}</text>'
            )
        row_letters = "ABCDEFGH"
        for j in range(self.zone_rows):
            ly = m + (j + 0.5) * row_h + self.zone_label_size / 3
            letter = row_letters[j] if j < len(row_letters) else str(j)
            parts.append(
                f'<text x="{m - 3:.1f}" y="{ly:.1f}" font-size="{self.zone_label_size}" '
                f'text-anchor="middle">{letter}</text>'
            )
            parts.append(
                f'<text x="{m + fw + 3:.1f}" y="{ly:.1f}" font-size="{self.zone_label_size}" '
                f'text-anchor="middle">{letter}</text>'
            )
        for i in range(1, self.zone_cols):
            lx = m + i * col_w
            parts.append(
                f'<line x1="{lx:.1f}" y1="{m:.1f}" x2="{lx:.1f}" y2="{m + fh:.1f}" '
                f'stroke="black" stroke-width="0.1"/>'
            )
        for j in range(1, self.zone_rows):
            ly = m + j * row_h
            parts.append(
                f'<line x1="{m:.1f}" y1="{ly:.1f}" x2="{m + fw:.1f}" y2="{ly:.1f}" '
                f'stroke="black" stroke-width="0.1"/>'
            )
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pump GA Demo Builder
# ---------------------------------------------------------------------------

def build_pump_ga_drawing():  # type: ignore[return]
    """
    Build a centrifugal pump General Arrangement (GA) drawing project.

    Demonstrates: lines, circles, rectangles, arcs, dimensions, hatching,
    leader lines, text annotations, title block, and block references.
    Returns a DrawingProject ready for SVG/DXF export.
    """
    from murphy_drawing_engine import (
        DrawingProject, DrawingSheet, DrawingElement,
        TitleBlock, ElementType, Discipline, SheetSize, LineStyle,
    )
    project = DrawingProject(
        name="Centrifugal Pump \u2014 General Arrangement",
        discipline=Discipline.MECHANICAL,
    )
    sheet = DrawingSheet(size=SheetSize.ANSI_D)
    sheet.title_block = TitleBlock(
        company="Murphy System Engineering",
        project="Centrifugal Pump GA",
        drawing_number="MEC-PUMP-001",
        revision="A",
        drawn_by="Murphy AI",
        checked_by="QA Lead",
        approved_by="PE Smith",
        pe_stamp_id="STAMP-MEC-001",
    )
    elems = sheet.elements

    elems.append(DrawingElement(
        element_type=ElementType.RECTANGLE,
        geometry={"x": 50, "y": 300, "width": 400, "height": 30},
        properties={"description": "Base plate"},
        line_style=LineStyle.CONTINUOUS,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.CIRCLE,
        geometry={"cx": 250, "cy": 240, "cz": 0, "radius": 60},
        properties={"description": "Pump volute casing"},
        line_style=LineStyle.CONTINUOUS,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.CIRCLE,
        geometry={"cx": 250, "cy": 240, "cz": 0, "radius": 35},
        properties={"description": "Impeller OD"},
        line_style=LineStyle.HIDDEN,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.LINE,
        geometry={"x1": 50, "y1": 240, "z1": 0, "x2": 450, "y2": 240, "z2": 0},
        properties={"description": "Shaft centerline"},
        line_style=LineStyle.CENTER,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.RECTANGLE,
        geometry={"x": 320, "y": 190, "width": 120, "height": 100},
        properties={"description": "Motor housing"},
        line_style=LineStyle.CONTINUOUS,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.RECTANGLE,
        geometry={"x": 310, "y": 228, "width": 20, "height": 24},
        properties={"description": "Flexible coupling"},
        line_style=LineStyle.CONTINUOUS,
    ))
    for x1, y1, x2, y2 in [
        (240, 180, 240, 130), (260, 180, 260, 130),
        (50, 230, 190, 230), (50, 250, 190, 250),
    ]:
        elems.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": x1, "y1": y1, "z1": 0, "x2": x2, "y2": y2, "z2": 0},
            line_style=LineStyle.CONTINUOUS,
        ))
    for angle_deg in range(0, 360, 45):
        angle_rad = math.radians(angle_deg)
        elems.append(DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": 70 + 12 * math.cos(angle_rad),
                      "cy": 240 + 12 * math.sin(angle_rad), "cz": 0, "radius": 2},
            properties={"description": "Suction flange bolt hole"},
            line_style=LineStyle.CONTINUOUS,
        ))
    elems.append(DrawingElement(
        element_type=ElementType.HATCH,
        geometry={"x": 50, "y": 300, "width": 400, "height": 30, "angle": 45, "spacing": 5},
        properties={"description": "Base plate section fill"},
        line_style=LineStyle.CONTINUOUS,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.DIMENSION,
        geometry={"x1": 50, "y1": 330, "x2": 450, "y2": 330, "offset": 30, "arrowhead_size": 4},
        properties={"text": "400", "dimension_text": "400"},
        line_style=LineStyle.DIMENSION,
    ))
    elems.append(DrawingElement(
        element_type=ElementType.LEADER,
        geometry={"points": [
            {"x": 380, "y": 190}, {"x": 430, "y": 160}, {"x": 470, "y": 160},
        ]},
        properties={"text": "MOTOR 15kW"},
        line_style=LineStyle.CONTINUOUS,
    ))
    for text_val, tx, ty, fsize in [
        ("PUMP", 210, 245, 5),
        ("BASE PLATE - A36 STEEL", 55, 320, 4),
        ('3"-150# ANSI DISCHARGE', 225, 120, 5),
        ('4"-150# ANSI SUCTION', 55, 225, 5),
    ]:
        elems.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": tx, "y": ty, "height": fsize},
            properties={"text": text_val},
            line_style=LineStyle.CONTINUOUS,
        ))
    for block_name, part_num, desc, mat in [
        ("CENTRIFUGAL_PUMP", "PMP-4X3-10", "Centrifugal Pump 4x3x10", "316SS"),
        ("ELECTRIC_MOTOR", "MOT-15KW-460V", "Electric Motor 15kW 460V 60Hz", "TEFC"),
        ("BASEPLATE", "BP-STD-001", "Fabricated Steel Baseplate", "A36"),
    ]:
        elems.append(DrawingElement(
            element_type=ElementType.BLOCK_REF,
            properties={
                "block_name": block_name, "quantity": 1,
                "part_number": part_num, "description": desc, "material": mat,
            },
        ))
    project.sheets.append(sheet)
    return project


# ===========================================================================
# IsometricProjector — Phase A
# ===========================================================================


class IsometricProjector:
    """Projects 3D points to 2D using standard 30° isometric projection.

    iso_x = (x - z) * cos(30°)
    iso_y = (x + z) * sin(30°) - y
    """

    COS30: float = math.cos(math.radians(30))
    SIN30: float = math.sin(math.radians(30))

    def project_point(self, x: float, y: float, z: float) -> Tuple[float, float]:
        """Project a single 3D point to 2D isometric coordinates."""
        iso_x = (x - z) * self.COS30
        iso_y = (x + z) * self.SIN30 - y
        return iso_x, iso_y

    def project_box(
        self,
        x: float,
        y: float,
        z: float,
        w: float,
        h: float,
        d: float,
    ) -> List[Any]:
        """Project a 3D box as 12 DrawingElement edges in isometric view.

        Visible edges (top / front / right faces) use CONTINUOUS line style.
        Hidden edges (bottom-left corner) use HIDDEN line style.
        Returns exactly 12 DrawingElement objects.
        """
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        # 8 corners
        c = [
            (x,     y,     z),      # 0: front-bottom-left
            (x + w, y,     z),      # 1: front-bottom-right
            (x + w, y + h, z),      # 2: front-top-right
            (x,     y + h, z),      # 3: front-top-left
            (x,     y,     z + d),  # 4: back-bottom-left  (hidden vertex)
            (x + w, y,     z + d),  # 5: back-bottom-right
            (x + w, y + h, z + d),  # 6: back-top-right
            (x,     y + h, z + d),  # 7: back-top-left
        ]
        _C = LineStyle.CONTINUOUS
        _H = LineStyle.HIDDEN
        # (corner_a, corner_b, line_style)
        edge_defs: List[Tuple[int, int, Any]] = [
            (0, 1, _C),  # front face bottom
            (1, 2, _C),  # front face right
            (2, 3, _C),  # front face top
            (3, 0, _C),  # front face left
            (4, 5, _H),  # back-bottom edge       (hidden)
            (5, 6, _C),  # right face depth bottom
            (6, 7, _C),  # top face back
            (7, 4, _H),  # back-left edge         (hidden)
            (0, 4, _H),  # bottom-left depth edge (hidden)
            (1, 5, _C),  # bottom-right depth
            (2, 6, _C),  # top-right depth
            (3, 7, _C),  # top-left depth
        ]
        elements: List[Any] = []
        for c1, c2, style in edge_defs:
            p1 = self.project_point(*c[c1])
            p2 = self.project_point(*c[c2])
            elements.append(
                DrawingElement(
                    element_type=ElementType.LINE,
                    geometry={
                        "x1": round(p1[0], 3),
                        "y1": round(p1[1], 3),
                        "z1": 0.0,
                        "x2": round(p2[0], 3),
                        "y2": round(p2[1], 3),
                        "z2": 0.0,
                    },
                    line_style=style,
                    line_weight=0.5 if style == _C else 0.35,
                )
            )
        return elements

    def project_circle_as_ellipse(
        self,
        cx: float,
        cy: float,
        cz: float,
        r: float,
        plane: str = "xy",
    ) -> Any:
        """Project a 3D circle as an isometric ellipse (24-point polygon).

        plane: 'xy' | 'xz' | 'yz'
        """
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        n = 24
        points: List[Dict[str, float]] = []
        for i in range(n):
            angle = 2.0 * math.pi * i / n
            if plane == "xy":
                px, py, pz = cx + r * math.cos(angle), cy + r * math.sin(angle), cz
            elif plane == "xz":
                px, py, pz = cx + r * math.cos(angle), cy, cz + r * math.sin(angle)
            else:  # yz
                px, py, pz = cx, cy + r * math.sin(angle), cz + r * math.cos(angle)
            ix, iy = self.project_point(px, py, pz)
            points.append({"x": round(ix, 3), "y": round(iy, 3)})
        return DrawingElement(
            element_type=ElementType.POLYGON,
            geometry={"vertices": points},
            line_style=LineStyle.CONTINUOUS,
            line_weight=0.5,
        )


# ===========================================================================
# BalloonCallout — Phase E
# ===========================================================================


class BalloonCallout:
    """Renders a numbered balloon callout circle with a leader line to a part."""

    def __init__(self, cx: float, cy: float, r: float, item_number: int) -> None:
        self.cx = cx
        self.cy = cy
        self.r = r
        self.item_number = item_number

    def to_drawing_elements(
        self, leader_x: float, leader_y: float
    ) -> List[Any]:
        """Return [circle, number-text, leader-line] DrawingElements."""
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        circle = DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": self.cx, "cy": self.cy, "cz": 0.0, "radius": self.r},
            properties={"type": "balloon", "item_number": self.item_number},
            line_style=LineStyle.CONTINUOUS,
            line_weight=0.35,
        )
        text = DrawingElement(
            element_type=ElementType.TEXT,
            geometry={
                "x": self.cx,
                "y": self.cy + self.r * 0.35,
                "height": max(self.r * 1.2, 8),
            },
            properties={
                "text": str(self.item_number),
                "text_anchor": "middle",
            },
            line_style=LineStyle.CONTINUOUS,
        )
        leader = DrawingElement(
            element_type=ElementType.LEADER,
            geometry={
                "points": [
                    {"x": leader_x, "y": leader_y},
                    {"x": self.cx - self.r, "y": self.cy},
                ]
            },
            properties={"type": "balloon_leader"},
            line_style=LineStyle.CONTINUOUS,
            line_weight=0.35,
        )
        return [circle, text, leader]


# ===========================================================================
# ExplodedViewBuilder — Phase B
# ===========================================================================


class ExplodedViewBuilder:
    """Builds an exploded isometric view from a list of 3D parts."""

    def __init__(self, parts: List[Dict[str, Any]]) -> None:
        self.parts = parts
        self._projector = IsometricProjector()
        self._exploded_parts: List[Dict[str, Any]] = list(parts)

    def explode(
        self,
        offset_vector: Tuple[float, float, float] = (0.0, -40.0, 0.0),
    ) -> "ExplodedViewBuilder":
        """Displace each part i along offset_vector by i * offset_vector."""
        ox, oy, oz = offset_vector
        self._exploded_parts = []
        for i, part in enumerate(self.parts):
            self._exploded_parts.append(
                {
                    **part,
                    "x": part["x"] + i * ox,
                    "y": part["y"] + i * oy,
                    "z": part["z"] + i * oz,
                }
            )
        return self

    def build(
        self, origin_x: float = 0.0, origin_y: float = 0.0
    ) -> List[Any]:
        """Project all exploded parts to DrawingElements and add balloon callouts.

        Returns a flat list of DrawingElement objects.
        """
        elements: List[Any] = []
        balloon_r = 8.0
        balloon_offset_x = 30.0
        balloon_offset_y = -15.0

        for i, part in enumerate(self._exploded_parts):
            box_elems = self._projector.project_box(
                part["x"] + origin_x,
                part["y"] + origin_y,
                part["z"],
                part["w"],
                part["h"],
                part["d"],
            )
            elements.extend(box_elems)

            # Balloon callout centred on the projected box centroid
            cx_3d = part["x"] + origin_x + part["w"] / 2.0
            cy_3d = part["y"] + origin_y + part["h"] / 2.0
            cz_3d = part["z"] + part["d"] / 2.0
            iso_cx, iso_cy = self._projector.project_point(cx_3d, cy_3d, cz_3d)

            b_cx = iso_cx + balloon_offset_x
            b_cy = iso_cy + balloon_offset_y
            balloon = BalloonCallout(b_cx, b_cy, balloon_r, i + 1)
            elements.extend(balloon.to_drawing_elements(iso_cx, iso_cy))

        return elements


# ===========================================================================
# BOMTableRenderer — Phase E
# ===========================================================================


class BOMTableRenderer:
    """Renders a Bill of Materials as a self-contained SVG table."""

    HEADERS: List[str] = ["ITEM", "QTY", "PART NUMBER", "DESCRIPTION", "MATERIAL"]

    def __init__(
        self,
        bom_data: List[Dict[str, Any]],
        col_widths: Optional[List[float]] = None,
    ) -> None:
        self.bom_data = bom_data
        self.col_widths = col_widths or [30.0, 25.0, 90.0, 180.0, 90.0]

    @staticmethod
    def _xml_escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def render_svg(
        self,
        x: float = 10,
        y: float = 10,
        row_height: float = 18,
    ) -> str:
        """Return a complete SVG document rendering the BOM table."""
        total_w = sum(self.col_widths)
        n_rows = len(self.bom_data) + 1  # header + data rows
        svg_w = int(total_w + 2 * x)
        svg_h = int(n_rows * row_height + 2 * y + row_height)

        parts: List[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{svg_w}" height="{svg_h}" '
                f'viewBox="0 0 {svg_w} {svg_h}">'
            ),
        ]

        # Header row
        cur_x = x
        for header, cw in zip(self.HEADERS, self.col_widths):
            parts.append(
                f'<rect x="{cur_x:.1f}" y="{y:.1f}" '
                f'width="{cw:.1f}" height="{row_height:.1f}" '
                f'fill="#cccccc" stroke="black" stroke-width="0.5"/>'
            )
            parts.append(
                f'<text x="{cur_x + 2:.1f}" y="{y + row_height - 4:.1f}" '
                f'font-size="9" font-weight="bold" '
                f'font-family="sans-serif" fill="black">{header}</text>'
            )
            cur_x += cw

        # Data rows
        for i, row in enumerate(self.bom_data):
            row_y = y + (i + 1) * row_height
            cur_x = x
            vals = [
                str(row.get("item", i + 1)),
                str(row.get("qty", 1)),
                self._xml_escape(str(row.get("part_number", ""))),
                self._xml_escape(str(row.get("description", ""))),
                self._xml_escape(str(row.get("material", ""))),
            ]
            for val, cw in zip(vals, self.col_widths):
                parts.append(
                    f'<rect x="{cur_x:.1f}" y="{row_y:.1f}" '
                    f'width="{cw:.1f}" height="{row_height:.1f}" '
                    f'fill="white" stroke="black" stroke-width="0.5"/>'
                )
                parts.append(
                    f'<text x="{cur_x + 2:.1f}" y="{row_y + row_height - 4:.1f}" '
                    f'font-size="8" font-family="sans-serif" '
                    f'fill="black">{val}</text>'
                )
                cur_x += cw

        parts.append("</svg>")
        return "\n".join(parts)


# ===========================================================================
# CuttingPlaneLine — Phase E
# ===========================================================================


class CuttingPlaneLine:
    """Renders an engineering cutting-plane line with directional arrows and label."""

    def __init__(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        label: str = "A-A",
    ) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.label = label

    def to_drawing_elements(self) -> List[Any]:
        """Return DrawingElement list for the cutting plane line + labels."""
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        elements: List[Any] = [
            DrawingElement(
                element_type=ElementType.LINE,
                geometry={
                    "x1": self.x1,
                    "y1": self.y1,
                    "z1": 0.0,
                    "x2": self.x2,
                    "y2": self.y2,
                    "z2": 0.0,
                },
                line_style=LineStyle.CUTTING_PLANE,
                line_weight=0.5,
            ),
        ]
        # Label at start/end (e.g. 'A-A' → start='A', end='A')
        if "-" in self.label:
            parts_label = self.label.split("-", 1)
            start_label, end_label = parts_label[0], parts_label[1]
        else:
            start_label = self.label[0] if self.label else "A"
            end_label = self.label[-1] if self.label else "A"
        elements.append(
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": self.x1 - 12, "y": self.y1 + 4, "height": 10},
                properties={"text": start_label},
                line_style=LineStyle.CONTINUOUS,
            )
        )
        elements.append(
            DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": self.x2 + 3, "y": self.y2 + 4, "height": 10},
                properties={"text": end_label},
                line_style=LineStyle.CONTINUOUS,
            )
        )
        return elements


# ===========================================================================
# SpeakerAssemblyDrawing — Phase C
# ===========================================================================


class SpeakerAssemblyDrawing:
    """Builds a stereo speaker assembly GA drawing.

    Three views on a single ANSI_D sheet:
      1. Front View — orthographic with drivers, screws, dimensions, cutting plane
      2. Section A-A — internal cross-section with MDF / insulation hatch
      3. Exploded Isometric — ExplodedViewBuilder with balloon callouts (1-10)
    Plus a BOM table and professional title block.
    """

    BOM: List[Dict[str, Any]] = [
        {
            "item": 1, "qty": 1,
            "part_number": "CAB-MDF-200",
            "description": "Speaker Cabinet 200x180x380",
            "material": "18mm MDF",
        },
        {
            "item": 2, "qty": 1,
            "part_number": "WFR-8IN-PP",
            "description": "8in Woofer 140mm frame",
            "material": "PP Cone",
        },
        {
            "item": 3, "qty": 1,
            "part_number": "TWE-1IN-SILK",
            "description": "1in Dome Tweeter 50mm frame",
            "material": "Silk Dome",
        },
        {
            "item": 4, "qty": 8,
            "part_number": "SCR-M4X20-SS",
            "description": "Driver Mounting Screws M4x20",
            "material": "18-8 SS",
        },
        {
            "item": 5, "qty": 1,
            "part_number": "XOVR-2WAY-3K",
            "description": "2-Way Crossover 3kHz 12dB/oct",
            "material": "FR4 PCB",
        },
        {
            "item": 6, "qty": 1,
            "part_number": "GRL-FABRIC-BK",
            "description": "Speaker Grille with Frame",
            "material": "ABS + Fabric",
        },
        {
            "item": 7, "qty": 1,
            "part_number": "TRM-BIND-POST",
            "description": "Binding Post Terminal Plate",
            "material": "ABS + Brass",
        },
        {
            "item": 8, "qty": 1,
            "part_number": "WIR-16AWG-SET",
            "description": "Internal Wiring Harness 16AWG",
            "material": "OFC Copper",
        },
        {
            "item": 9, "qty": 1,
            "part_number": "INS-POLYFILL",
            "description": "Acoustic Damping Polyfill",
            "material": "Polyester",
        },
        {
            "item": 10, "qty": 4,
            "part_number": "FT-RUBBER-20",
            "description": "Rubber Isolation Feet D20",
            "material": "Neoprene",
        },
    ]

    # 3D part definitions for ExplodedViewBuilder (simplified box per part)
    _PARTS_3D: List[Dict[str, Any]] = [
        {"name": "Cabinet",    "x":  0, "y":  0, "z":  0, "w": 100, "h": 20, "d": 50},
        {"name": "Woofer",     "x": 15, "y":  0, "z":  0, "w":  70, "h": 12, "d": 15},
        {"name": "Tweeter",    "x": 32, "y":  0, "z":  0, "w":  36, "h":  8, "d": 12},
        {"name": "Screws",     "x":  8, "y":  0, "z":  0, "w":   5, "h":  5, "d":  5},
        {"name": "Crossover",  "x": 10, "y":  0, "z":  5, "w":  80, "h":  5, "d": 40},
        {"name": "Grille",     "x":  0, "y":  0, "z":  0, "w": 100, "h":  5, "d": 50},
        {"name": "Terminal",   "x": 70, "y":  0, "z": 10, "w":  30, "h":  5, "d": 20},
        {"name": "Wiring",     "x": 10, "y":  0, "z":  5, "w":  80, "h":  3, "d": 40},
        {"name": "Insulation", "x":  5, "y":  0, "z":  5, "w":  90, "h":  3, "d": 40},
        {"name": "Feet",       "x": 10, "y":  0, "z": 10, "w":  10, "h":  5, "d": 10},
    ]

    def __init__(self) -> None:
        self.bom: List[Dict[str, Any]] = list(self.BOM)

    def build(self) -> Any:
        """Build the complete speaker assembly drawing project and return it."""
        from murphy_drawing_engine import (
            DrawingProject, DrawingSheet, TitleBlock,
            Discipline, SheetSize,
        )

        project = DrawingProject(
            name="Stereo Speaker Assembly -- GA",
            discipline=Discipline.MECHANICAL,
        )
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        sheet.title_block = TitleBlock(
            company="Murphy System Engineering",
            project="Stereo Speaker Assembly -- GA",
            drawing_number="MEC-SPKR-001",
            revision="A",
            drawn_by="Murphy AI",
            checked_by="QA Lead",
            approved_by="PE Smith",
            pe_stamp_id="STAMP-SPKR-001",
        )

        elems = sheet.elements
        self._build_front_view(elems, origin_x=50.0, origin_y=60.0)
        self._build_section_view(elems, origin_x=240.0, origin_y=60.0)
        self._build_exploded_isometric(elems, origin_x=580.0, origin_y=280.0)
        self._build_bom_elements(elems, x=50.0, y=520.0)

        project.sheets.append(sheet)
        return project

    # ------------------------------------------------------------------
    # Private view builders
    # ------------------------------------------------------------------

    def _build_front_view(
        self, elems: List[Any], origin_x: float, origin_y: float
    ) -> None:
        """Build front orthographic view elements (scale 1:2)."""
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        # Cabinet: 200mm wide x 380mm tall at 1:2 → 100 x 190 px
        cab_w, cab_h = 100.0, 190.0
        cx = origin_x + cab_w / 2.0  # horizontal centre

        # Cabinet outline
        elems.append(DrawingElement(
            element_type=ElementType.RECTANGLE,
            geometry={"x": origin_x, "y": origin_y, "width": cab_w, "height": cab_h},
            properties={"description": "Cabinet outline"},
            line_style=LineStyle.CONTINUOUS,
        ))

        # --- Woofer (lower centre, 140mm frame → r=35px) ---
        wfr_cy = origin_y + 140.0
        for r, desc in [
            (35.0, "woofer"),
            (28.0, "Woofer cone"),
            (10.0, "Woofer dust cap"),
        ]:
            elems.append(DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": cx, "cy": wfr_cy, "cz": 0, "radius": r},
                properties={"description": desc, "driver": "woofer"} if r == 35.0 else {"description": desc},
                line_style=LineStyle.CONTINUOUS,
            ))
        # 8 woofer mounting screw holes (bolt circle r=38px)
        for k in range(8):
            ang = math.radians(k * 45)
            elems.append(DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": cx + 38.0 * math.cos(ang), "cy": wfr_cy + 38.0 * math.sin(ang), "cz": 0, "radius": 2.0},
                properties={"description": "Woofer mounting screw"},
                line_style=LineStyle.CONTINUOUS,
            ))

        # --- Tweeter (upper centre, 50mm frame → r=12.5px, 70mm from top → 35px) ---
        twe_cy = origin_y + 35.0
        for r, desc in [
            (12.5, "tweeter"),
            (6.0, "Tweeter dome"),
        ]:
            elems.append(DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": cx, "cy": twe_cy, "cz": 0, "radius": r},
                properties={"description": desc, "driver": "tweeter"} if r == 12.5 else {"description": desc},
                line_style=LineStyle.CONTINUOUS,
            ))
        # 4 tweeter mounting screw holes
        for k in range(4):
            ang = math.radians(k * 90 + 45)
            elems.append(DrawingElement(
                element_type=ElementType.CIRCLE,
                geometry={"cx": cx + 16.0 * math.cos(ang), "cy": twe_cy + 16.0 * math.sin(ang), "cz": 0, "radius": 1.5},
                properties={"description": "Tweeter mounting screw"},
                line_style=LineStyle.CONTINUOUS,
            ))

        # Cutting plane A-A
        cut_y = origin_y + cab_h / 2.0
        for elem in CuttingPlaneLine(origin_x - 15, cut_y, origin_x + cab_w + 15, cut_y, "A-A").to_drawing_elements():
            elems.append(elem)

        # Dimension: overall width 200mm
        elems.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": origin_x, "y1": origin_y + cab_h + 20, "x2": origin_x + cab_w, "y2": origin_y + cab_h + 20, "offset": 15},
            properties={"text": "200", "dimension_text": "200"},
            line_style=LineStyle.DIMENSION,
        ))
        # Dimension: overall height 380mm
        elems.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": origin_x - 25, "y1": origin_y, "x2": origin_x - 25 + 1, "y2": origin_y + cab_h, "offset": 15},
            properties={"text": "380", "dimension_text": "380"},
            line_style=LineStyle.DIMENSION,
        ))
        # Dimension: tweeter centre offset from top 70mm
        elems.append(DrawingElement(
            element_type=ElementType.DIMENSION,
            geometry={"x1": origin_x + cab_w + 15, "y1": origin_y, "x2": origin_x + cab_w + 16, "y2": twe_cy, "offset": 15},
            properties={"text": "70", "dimension_text": "70"},
            line_style=LineStyle.DIMENSION,
        ))

        # View label (bold, font-size >= 10 per gap analysis)
        elems.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": origin_x, "y": origin_y - 10, "height": 10},
            properties={"text": "FRONT VIEW"},
            line_style=LineStyle.CONTINUOUS,
        ))

    def _build_section_view(
        self, elems: List[Any], origin_x: float, origin_y: float
    ) -> None:
        """Build Section A-A cross-section elements."""
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        # Same scale 1:2; cabinet 200 x 380 → 100 x 190 px; wall t=9px (18mm MDF)
        cab_w, cab_h, wall_t = 100.0, 190.0, 9.0

        # MDF wall hatch (ANSI31, 45°)
        for hg in [
            {"x": origin_x,                 "y": origin_y,                "width": wall_t,          "height": cab_h, "angle": 45, "spacing": 4},
            {"x": origin_x + cab_w - wall_t, "y": origin_y,                "width": wall_t,          "height": cab_h, "angle": 45, "spacing": 4},
            {"x": origin_x,                 "y": origin_y,                "width": cab_w,            "height": wall_t, "angle": 45, "spacing": 4},
            {"x": origin_x,                 "y": origin_y + cab_h - wall_t, "width": cab_w,          "height": wall_t, "angle": 45, "spacing": 4},
        ]:
            elems.append(DrawingElement(
                element_type=ElementType.HATCH,
                geometry={**hg},
                properties={"description": "MDF wall hatch"},
                line_style=LineStyle.CONTINUOUS,
            ))

        # Insulation fill (horizontal hatch, angle=0, different spacing)
        elems.append(DrawingElement(
            element_type=ElementType.HATCH,
            geometry={"x": origin_x + wall_t, "y": origin_y + wall_t,
                      "width": cab_w - 2 * wall_t, "height": cab_h - 2 * wall_t,
                      "angle": 0, "spacing": 6},
            properties={"description": "Insulation (Polyfill)"},
            line_style=LineStyle.CONTINUOUS,
        ))

        # Wiring path (CENTER linestyle)
        elems.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": origin_x + cab_w / 2, "y1": origin_y + wall_t, "z1": 0,
                      "x2": origin_x + cab_w / 2, "y2": origin_y + cab_h - wall_t, "z2": 0},
            properties={"description": "WIRING"},
            line_style=LineStyle.CENTER,
            line_weight=0.25,
        ))

        # Crossover PCB
        elems.append(DrawingElement(
            element_type=ElementType.RECTANGLE,
            geometry={"x": origin_x + wall_t + 5, "y": origin_y + cab_h - 60, "width": 60, "height": 20},
            properties={"description": "XOVER"},
            line_style=LineStyle.CONTINUOUS,
        ))

        # Annotations
        for txt, tx, ty in [
            ("INSULATION", origin_x + 15, origin_y + 80),
            ("WIRING",     origin_x + 55, origin_y + 100),
            ("XOVER",      origin_x + wall_t + 8, origin_y + cab_h - 47),
        ]:
            elems.append(DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": tx, "y": ty, "height": 8},
                properties={"text": txt},
                line_style=LineStyle.CONTINUOUS,
            ))

        # View label
        elems.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": origin_x, "y": origin_y - 10, "height": 10},
            properties={"text": "SECTION A-A"},
            line_style=LineStyle.CONTINUOUS,
        ))

    def _build_exploded_isometric(
        self, elems: List[Any], origin_x: float, origin_y: float
    ) -> None:
        """Build exploded isometric view using ExplodedViewBuilder."""
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        builder = ExplodedViewBuilder(self._PARTS_3D)
        builder.explode(offset_vector=(0.0, -30.0, 0.0))
        iso_elements = builder.build(origin_x=origin_x, origin_y=origin_y)
        elems.extend(iso_elements)

        elems.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": origin_x - 50, "y": origin_y - 25, "height": 10},
            properties={"text": "EXPLODED ISOMETRIC"},
            line_style=LineStyle.CONTINUOUS,
        ))

    def _build_bom_elements(
        self, elems: List[Any], x: float, y: float
    ) -> None:
        """Add BOM table header, data rows, and BLOCK_REF elements."""
        from murphy_drawing_engine import DrawingElement, ElementType, LineStyle

        # BLOCK_REF entries (for BOMExtractor compatibility)
        for item in self.bom:
            elems.append(DrawingElement(
                element_type=ElementType.BLOCK_REF,
                geometry={"x": x, "y": y},
                properties={
                    "block_name": item["part_number"],
                    "quantity": item["qty"],
                    "part_number": item["part_number"],
                    "description": item["description"],
                    "material": item["material"],
                    "item": item["item"],
                },
            ))

        # BOM title
        elems.append(DrawingElement(
            element_type=ElementType.TEXT,
            geometry={"x": x, "y": y - 10, "height": 10},
            properties={"text": "BILL OF MATERIALS"},
            line_style=LineStyle.CONTINUOUS,
        ))

        # Table header row
        col_ws = [30.0, 25.0, 90.0, 180.0, 90.0]
        headers = ["ITEM", "QTY", "PART NUMBER", "DESCRIPTION", "MATERIAL"]
        row_h = 15.0
        cur_x = x
        for header, cw in zip(headers, col_ws):
            elems.append(DrawingElement(
                element_type=ElementType.RECTANGLE,
                geometry={"x": cur_x, "y": y, "width": cw, "height": row_h},
                properties={"description": f"BOM header: {header}"},
                line_style=LineStyle.CONTINUOUS,
            ))
            elems.append(DrawingElement(
                element_type=ElementType.TEXT,
                geometry={"x": cur_x + 2, "y": y + 11, "height": 8},
                properties={"text": header},
                line_style=LineStyle.CONTINUOUS,
            ))
            cur_x += cw

        # Data rows — include part numbers so SVG contains all 10
        for i, item in enumerate(self.bom):
            row_y = y + (i + 1) * row_h
            vals = [
                str(item["item"]),
                str(item["qty"]),
                item["part_number"],
                item["description"],
                item["material"],
            ]
            cur_x = x
            for val, cw in zip(vals, col_ws):
                elems.append(DrawingElement(
                    element_type=ElementType.TEXT,
                    geometry={"x": cur_x + 2, "y": row_y + 11, "height": 7},
                    properties={"text": val},
                    line_style=LineStyle.CONTINUOUS,
                ))
                cur_x += cw

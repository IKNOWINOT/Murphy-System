"""
Murphy System - Murphy Drawing Engine Extensions
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Engineering symbol library, drawing border/frame, and demo drawing builder.
Imported by murphy_drawing_engine.py to keep that module under the 1000-line limit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List


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

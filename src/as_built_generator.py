"""
As-Built Generator
==================
Generates control point schedules, schematics, and drawing element
databases from equipment specs and virtual controllers.

DrawingDatabase: ingests multiple drawings, deduplicates elements,
and provides best-of-all-drawings references.

Copyright (c) 2020 Inoni Limited Liability Company  Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DrawingElementType(str, Enum):
    EQUIPMENT_TAG = "equipment_tag"
    INSTRUMENT_TAG = "instrument_tag"
    PIPE_LINE = "pipe_line"
    DUCT_LINE = "duct_line"
    CONTROL_WIRE = "control_wire"
    SIGNAL_WIRE = "signal_wire"
    POWER_WIRE = "power_wire"
    VALVE = "valve"
    DAMPER = "damper"
    SENSOR = "sensor"
    CONTROLLER = "controller"
    ACTUATOR = "actuator"
    TERMINAL_BLOCK = "terminal_block"
    ANNOTATION = "annotation"
    TITLE_BLOCK = "title_block"
    REVISION_BLOCK = "revision_block"


@dataclass
class DrawingElement:
    element_id: str = field(default_factory=lambda: str(uuid.uuid4())[:10])
    element_type: DrawingElementType = DrawingElementType.ANNOTATION
    tag: str = ""
    description: str = ""
    specifications: Dict[str, Any] = field(default_factory=dict)
    manufacturer: str = ""
    model: str = ""
    cutsheet_reference: str = ""
    drawing_reference: str = ""
    revision: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_type": self.element_type.value if hasattr(self.element_type,"value") else str(self.element_type),
            "tag": self.tag, "description": self.description,
            "specifications": self.specifications,
            "manufacturer": self.manufacturer, "model": self.model,
            "cutsheet_reference": self.cutsheet_reference,
            "drawing_reference": self.drawing_reference,
            "revision": self.revision,
        }

    def _quality_score(self) -> int:
        score = 0
        if self.manufacturer: score += 2
        if self.model: score += 2
        if self.cutsheet_reference: score += 3
        score += len(self.specifications)
        return score


@dataclass
class PointScheduleEntry:
    point_id: str = field(default_factory=lambda: str(uuid.uuid4())[:10])
    point_name: str = ""
    point_type: str = "AI"
    object_type: str = "analog-input"
    object_instance: int = 0
    description: str = ""
    engineering_units: str = ""
    normal_state: str = ""
    alarm_low: Optional[float] = None
    alarm_high: Optional[float] = None
    setpoint: Optional[float] = None
    wiring_terminal: str = ""
    field_device: str = ""
    controller_address: str = ""
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ControlDiagram:
    diagram_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str = ""
    system_name: str = ""
    revision: str = "A"
    elements: List[DrawingElement] = field(default_factory=list)
    point_schedule: List[PointScheduleEntry] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    drawn_by: str = "Murphy System"
    checked_by: str = ""
    date: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagram_id": self.diagram_id, "title": self.title,
            "system_name": self.system_name, "revision": self.revision,
            "elements": [e.to_dict() for e in self.elements],
            "point_schedule": [p.to_dict() for p in self.point_schedule],
            "notes": self.notes, "drawn_by": self.drawn_by,
            "checked_by": self.checked_by, "date": self.date,
        }

    def summary(self) -> str:
        return (f"Diagram: {self.title} | System: {self.system_name} | "
                f"Elements: {len(self.elements)} | Points: {len(self.point_schedule)} | "
                f"Rev: {self.revision}")


class DrawingDatabase:
    """Multi-drawing reference database with deduplication."""

    def __init__(self) -> None:
        self._elements: Dict[str, DrawingElement] = {}
        self._diagrams: List[ControlDiagram] = []

    def ingest_drawing(self, diagram: ControlDiagram) -> int:
        self._diagrams.append(diagram)
        new_count = 0
        for elem in diagram.elements:
            key = f"{elem.element_type}|{elem.tag}|{elem.manufacturer}|{elem.model}"
            if key not in self._elements:
                self._elements[key] = elem
                new_count += 1
            else:
                existing = self._elements[key]
                if elem._quality_score() > existing._quality_score():
                    self._elements[key] = elem
        return new_count

    def deduplicate(self) -> int:
        seen: Dict[str, str] = {}
        to_remove = []
        for key, elem in self._elements.items():
            dedup_key = f"{elem.element_type}|{elem.tag}"
            if dedup_key in seen:
                existing_key = seen[dedup_key]
                if self._elements[key]._quality_score() > self._elements[existing_key]._quality_score():
                    to_remove.append(existing_key)
                    seen[dedup_key] = key
                else:
                    to_remove.append(key)
            else:
                seen[dedup_key] = key
        for k in to_remove:
            self._elements.pop(k, None)
        return len(to_remove)

    def get_best_element(self, element_type: DrawingElementType,
                          tag_pattern: str) -> Optional[DrawingElement]:
        candidates = [
            e for e in self._elements.values()
            if e.element_type == element_type and tag_pattern.lower() in e.tag.lower()
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda e: e._quality_score())

    def search(self, query: str) -> List[DrawingElement]:
        q = query.lower()
        return [e for e in self._elements.values()
                if q in e.tag.lower() or q in e.description.lower()
                or q in e.manufacturer.lower()]

    def export_catalog(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._elements.values()]

    def __len__(self) -> int:
        return len(self._elements)


class AsBuiltGenerator:
    """Generate as-built control diagrams from virtual controllers or specs."""

    def from_virtual_controller(self, controller: Any, system_name: str) -> ControlDiagram:
        diagram = ControlDiagram(
            title=f"{system_name} Control Diagram",
            system_name=system_name,
        )
        if hasattr(controller, "points"):
            for pt in controller.points:
                obj_type = getattr(pt, "object_type", "analog-input")
                p_type = "AI"
                if "output" in obj_type:
                    p_type = "AO"
                elif "binary" in obj_type and "output" in obj_type:
                    p_type = "DO"
                elif "binary" in obj_type:
                    p_type = "DI"
                entry = PointScheduleEntry(
                    point_name=getattr(pt, "name", ""),
                    point_type=p_type,
                    object_type=obj_type,
                    object_instance=getattr(pt, "object_instance", 0),
                    description=getattr(pt, "description", ""),
                    engineering_units=getattr(pt, "engineering_units", ""),
                    controller_address=getattr(controller, "controller_id", ""),
                    verified=True,
                )
                diagram.point_schedule.append(entry)
                elem = DrawingElement(
                    element_type=DrawingElementType.INSTRUMENT_TAG,
                    tag=entry.point_name,
                    description=entry.description,
                )
                diagram.elements.append(elem)
        diagram.notes.append("Generated from VirtualController by Murphy System")
        return diagram

    def from_equipment_spec(self, spec: Any, system_name: str) -> ControlDiagram:
        diagram = ControlDiagram(
            title=f"{system_name} Control Diagram",
            system_name=system_name,
        )
        equip_name = getattr(spec, "equipment_name", getattr(spec, "name", system_name))
        equip_tag = DrawingElement(
            element_type=DrawingElementType.EQUIPMENT_TAG,
            tag=equip_name,
            description=getattr(spec, "description", ""),
            manufacturer=getattr(spec, "manufacturer", ""),
            model=getattr(spec, "model_number", ""),
        )
        diagram.elements.append(equip_tag)
        points = getattr(spec, "control_points", getattr(spec, "points", []))
        for i, pt in enumerate(points):
            if isinstance(pt, dict):
                name = pt.get("name", f"PT_{i}")
                desc = pt.get("description", "")
                units = pt.get("units", pt.get("engineering_units", ""))
                pt_type = pt.get("point_type", "AI")
            else:
                name = getattr(pt, "name", f"PT_{i}")
                desc = getattr(pt, "description", "")
                units = getattr(pt, "engineering_units", "")
                pt_type = getattr(pt, "point_type", "AI")
            entry = PointScheduleEntry(
                point_name=name,
                point_type=pt_type,
                description=desc,
                engineering_units=units,
            )
            diagram.point_schedule.append(entry)
            diagram.elements.append(DrawingElement(
                element_type=DrawingElementType.INSTRUMENT_TAG,
                tag=name, description=desc,
            ))
        diagram.notes.append(f"Generated from EquipmentSpec: {equip_name}")
        return diagram

    def merge_with_database(self, diagram: ControlDiagram,
                             db: DrawingDatabase) -> ControlDiagram:
        for elem in diagram.elements:
            best = db.get_best_element(elem.element_type, elem.tag)
            if best:
                if not elem.manufacturer and best.manufacturer:
                    elem.manufacturer = best.manufacturer
                if not elem.model and best.model:
                    elem.model = best.model
                if not elem.cutsheet_reference and best.cutsheet_reference:
                    elem.cutsheet_reference = best.cutsheet_reference
                for k, v in best.specifications.items():
                    if k not in elem.specifications:
                        elem.specifications[k] = v
        return diagram

    def generate_point_schedule(self, diagram: ControlDiagram) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in diagram.point_schedule]

    def generate_schematic_description(self, diagram: ControlDiagram) -> str:
        lines = [
            f"CONTROL SCHEMATIC — {diagram.title}",
            f"System: {diagram.system_name} | Revision: {diagram.revision} | Date: {diagram.date}",
            "",
            "EQUIPMENT:",
        ]
        for e in diagram.elements:
            if e.element_type == DrawingElementType.EQUIPMENT_TAG:
                mfr = f" [{e.manufacturer} {e.model}]" if e.manufacturer else ""
                lines.append(f"  {e.tag}{mfr}: {e.description}")
        lines.extend(["", "INSTRUMENTS/SENSORS:"])
        for e in diagram.elements:
            if e.element_type == DrawingElementType.INSTRUMENT_TAG:
                lines.append(f"  {e.tag}: {e.description}")
        lines.extend(["", "CONTROL POINTS:", "  Point Name | Type | Description | Units"])
        for p in diagram.point_schedule:
            lines.append(f"  {p.point_name} | {p.point_type} | {p.description} | {p.engineering_units}")
        if diagram.notes:
            lines.extend(["", "NOTES:"])
            for n in diagram.notes:
                lines.append(f"  - {n}")
        return "\n".join(lines)

    def check_proposal_completeness(self, diagram: ControlDiagram,
                                     proposal_requirements: List[str]) -> Dict[str, Any]:
        diagram_tags = {e.tag.lower() for e in diagram.elements}
        diagram_tags |= {p.point_name.lower() for p in diagram.point_schedule}
        missing = [r for r in proposal_requirements if r.lower() not in diagram_tags]
        extra = [t for t in diagram_tags if t and not any(r.lower() in t for r in proposal_requirements)]
        return {
            "complete": len(missing) == 0,
            "missing": missing,
            "extra": list(extra)[:10],
            "coverage_pct": round((len(proposal_requirements) - len(missing)) / max(len(proposal_requirements), 1) * 100, 1),
        }

    def export_as_built(self, diagram: ControlDiagram, fmt: str = "json") -> Dict[str, Any]:
        return {
            "format": fmt,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagram": diagram.to_dict(),
            "point_count": len(diagram.point_schedule),
            "element_count": len(diagram.elements),
            "summary": diagram.summary(),
        }

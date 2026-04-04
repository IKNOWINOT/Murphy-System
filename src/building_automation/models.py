# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""BAS-002 · Murphy-native building model hierarchy and semantic tagging.

Brick Schema-inspired (Murphy's own version) dataclass hierarchy that models
buildings, floors, zones, and control points with rich semantic metadata.

Thread-safe: immutable dataclasses; no shared mutable state.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PointKind(str, Enum):
    """Semantic role of a control point."""

    SENSOR = "sensor"
    SETPOINT = "setpoint"
    COMMAND = "command"
    STATUS = "status"


class Substance(str, Enum):
    """Medium that the point measures or controls."""

    AIR = "air"
    WATER = "water"
    ELECTRICITY = "electricity"
    GAS = "gas"
    STEAM = "steam"
    REFRIGERANT = "refrigerant"


class Phenomenon(str, Enum):
    """Physical quantity being observed."""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    FLOW = "flow"
    POWER = "power"
    ENERGY = "energy"
    CO2 = "co2"
    OCCUPANCY = "occupancy"
    LIGHT_LEVEL = "light_level"
    VOLTAGE = "voltage"
    CURRENT = "current"


class PointQuality(str, Enum):
    """Current quality / trustworthiness of a point value."""

    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MurphyPoint:
    """A single BAS control / monitoring point."""

    point_id: str = field(default_factory=lambda: f"pt-{uuid.uuid4().hex[:12]}")
    name: str = ""
    ref: str = ""  # semantic reference, e.g. "ahu-1/sat"
    kind: PointKind = PointKind.SENSOR
    substance: Substance = Substance.AIR
    phenomenon: Phenomenon = Phenomenon.TEMPERATURE
    value: float = 0.0
    quality: PointQuality = PointQuality.GOOD
    unit: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "name": self.name,
            "ref": self.ref,
            "kind": self.kind.value,
            "substance": self.substance.value,
            "phenomenon": self.phenomenon.value,
            "value": self.value,
            "quality": self.quality.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    def is_valid(self) -> bool:
        """Return *True* when quality is neither OFFLINE nor BAD."""
        return self.quality not in (PointQuality.OFFLINE, PointQuality.BAD)


@dataclass
class MurphyZone:
    """A thermal / lighting zone inside a floor."""

    zone_id: str = field(default_factory=lambda: f"zn-{uuid.uuid4().hex[:12]}")
    name: str = ""
    floor_id: str = ""
    zone_type: str = "office"  # office, conference, lobby, corridor, server_room …
    area_sqft: float = 0.0
    occupancy_capacity: int = 0
    temperature_setpoint: float = 72.0  # °F
    humidity_setpoint: float = 45.0  # %RH
    points: Dict[str, MurphyPoint] = field(default_factory=dict)
    occupied: bool = False
    occupant_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "floor_id": self.floor_id,
            "zone_type": self.zone_type,
            "area_sqft": self.area_sqft,
            "occupancy_capacity": self.occupancy_capacity,
            "temperature_setpoint": self.temperature_setpoint,
            "humidity_setpoint": self.humidity_setpoint,
            "points": {pid: p.to_dict() for pid, p in self.points.items()},
            "occupied": self.occupied,
            "occupant_count": self.occupant_count,
        }

    def get_point(self, point_id: str) -> Optional[MurphyPoint]:
        return self.points.get(point_id)

    def get_points_by_kind(self, kind: PointKind) -> List[MurphyPoint]:
        return [p for p in self.points.values() if p.kind == kind]


@dataclass
class MurphyFloor:
    """A single floor / level inside a building."""

    floor_id: str = field(default_factory=lambda: f"fl-{uuid.uuid4().hex[:12]}")
    name: str = ""
    building_id: str = ""
    level: int = 0
    zones: Dict[str, MurphyZone] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "floor_id": self.floor_id,
            "name": self.name,
            "building_id": self.building_id,
            "level": self.level,
            "zones": {zid: z.to_dict() for zid, z in self.zones.items()},
        }

    def get_zone(self, zone_id: str) -> Optional[MurphyZone]:
        return self.zones.get(zone_id)

    def total_area_sqft(self) -> float:
        return sum(z.area_sqft for z in self.zones.values())


@dataclass
class MurphyBuilding:
    """Top-level building entity."""

    building_id: str = field(default_factory=lambda: f"bld-{uuid.uuid4().hex[:12]}")
    name: str = ""
    address: str = ""
    total_sqft: float = 0.0
    year_built: int = 0
    building_type: str = ""
    floors: Dict[str, MurphyFloor] = field(default_factory=dict)
    latitude: float = 0.0
    longitude: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "building_id": self.building_id,
            "name": self.name,
            "address": self.address,
            "total_sqft": self.total_sqft,
            "year_built": self.year_built,
            "building_type": self.building_type,
            "floors": {fid: f.to_dict() for fid, f in self.floors.items()},
            "latitude": self.latitude,
            "longitude": self.longitude,
        }

    def get_floor(self, floor_id: str) -> Optional[MurphyFloor]:
        return self.floors.get(floor_id)

    def get_zone(self, zone_id: str) -> Optional[MurphyZone]:
        for fl in self.floors.values():
            zone = fl.get_zone(zone_id)
            if zone is not None:
                return zone
        return None

    def all_zones(self) -> List[MurphyZone]:
        return [z for fl in self.floors.values() for z in fl.zones.values()]

    def all_points(self) -> List[MurphyPoint]:
        return [
            p
            for fl in self.floors.values()
            for z in fl.zones.values()
            for p in z.points.values()
        ]

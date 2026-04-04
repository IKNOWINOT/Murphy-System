# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""BAS-001 · Building Automation & Energy Management — package root.

Layer 2 of the Murphy Building Automation System.  Provides HVAC control,
lighting, occupancy modelling, and sequence-of-operations execution for
commercial buildings.

Modules
-------
models           – Murphy-native building object hierarchy & semantic tags.
hvac_control     – PID, AHU, and zone temperature control logic.
lighting_control – Daylight harvesting, occupancy-aware dimming, scenes.
occupancy_model  – Multi-sensor fusion occupancy estimation.
soo_engine       – Sequence-of-operations scripting and audit engine.
"""

from __future__ import annotations

from building_automation.models import (
    MurphyBuilding,
    MurphyFloor,
    MurphyPoint,
    MurphyZone,
    Phenomenon,
    PointKind,
    PointQuality,
    Substance,
)
from building_automation.hvac_control import (
    AHUController,
    PIDController,
    ZoneTemperatureController,
)
from building_automation.lighting_control import (
    DaylightHarvestingModel,
    LightingZoneController,
    OccupancySchedule,
)
from building_automation.occupancy_model import (
    OccupancyEstimate,
    OccupancyModel,
    OccupancySensorInput,
)
from building_automation.soo_engine import (
    SOOEngine,
    SOOExecutionResult,
    SOOScript,
    SOOStep,
)

__all__ = [
    # models
    "MurphyBuilding",
    "MurphyFloor",
    "MurphyPoint",
    "MurphyZone",
    "Phenomenon",
    "PointKind",
    "PointQuality",
    "Substance",
    # hvac
    "AHUController",
    "PIDController",
    "ZoneTemperatureController",
    # lighting
    "DaylightHarvestingModel",
    "LightingZoneController",
    "OccupancySchedule",
    # occupancy
    "OccupancyEstimate",
    "OccupancyModel",
    "OccupancySensorInput",
    # soo
    "SOOEngine",
    "SOOExecutionResult",
    "SOOScript",
    "SOOStep",
]

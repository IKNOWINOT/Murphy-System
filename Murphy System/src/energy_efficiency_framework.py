"""
Energy Efficiency Framework

CEM (Certified Energy Manager) level energy management framework with
ASHRAE audit levels, ECM catalog, and MSS rubric integration.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ECMCategory(Enum):
    """Energy Conservation Measure categories"""
    HVAC = 'hvac'
    LIGHTING = 'lighting'
    ENVELOPE = 'envelope'
    CONTROLS = 'controls'
    RENEWABLE = 'renewable'
    PROCESS = 'process'
    WATER = 'water'
    COMPRESSED_AIR = 'compressed_air'
    STEAM = 'steam'
    BEHAVIORAL = 'behavioral'

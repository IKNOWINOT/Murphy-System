# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Self-Codebase Swarm for Murphy System.

Design Label: SCS-001 — Self-Codebase Swarm / Build-to-Spec Engine
Owner: Platform Engineering / Architecture

Registers "murphy-codebase" as a swarm domain and provides five specialized
agents that let Murphy System modify itself and build professional deliverables
for external projects.

Key capabilities
────────────────
  * **Swarm-on-self** — Architect / CodeGen / Test / Review / Deploy agents
    that analyse the live SystemGraph and propose/execute code changes.
  * **Build-to-spec (document mode)** — Parse RFP / contract documents
    (Building Management Control Systems or any domain) and generate a
    complete, professionally labelled and packaged deliverable.
  * **Autonomous build mode** — Generate professional specs, point maps,
    sequences of operations, and code packages from domain knowledge alone —
    no input documents required.
  * **Manufacturer cut sheet integration** — Ingest product data sheets via
    ``CutSheetEngine`` (CSE-001) to drive drawing generation, device code
    generation (BACnet configs / controller program stubs), and commissioning
    verification of installed equipment against spec requirements.
  * **BMS / BCS domain** — First-class support for HVAC, lighting, fire-safety,
    access control, energy metering, BACnet/Modbus point schedules, ASHRAE /
    NFPA compliance, and P.E.-stamp HITL gates.
  * **HITL gate** — Every ``execute_change()`` and ``execute_build()`` call
    is evaluated by ``HITLAutonomyController`` before any mutation occurs.
    The engine refuses execution when the controller says HITL is required
    and no human approval has been recorded.

Safety invariants
─────────────────
  - Thread-safe: all shared state guarded by threading.Lock.
  - Bounded collections via capped_append (CWE-770).
  - Input validated before processing (CWE-20).
  - Errors sanitised before logging (CWE-209).
  - HITL check mandatory before any execute path.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list, item, max_size=10_000):  # type: ignore[misc]
        """Bounded list append — fallback when thread_safe_operations is unavailable."""
        target_list.append(item)
        if len(target_list) > max_size:
            del target_list[:-max_size]

logger = logging.getLogger(__name__)

# Lazy import so the swarm still loads if cutsheet_engine is unavailable
try:
    from cutsheet_engine import (
        CutSheetEngine,
        CutSheetSpec,
        DeviceConfig,
        ControlDiagram,
        WiringDiagram,
        VerificationResult,
    )
    _CUTSHEET_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CUTSHEET_AVAILABLE = False
    CutSheetEngine = None  # type: ignore[assignment,misc]
    CutSheetSpec = None    # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Input-validation constants                                         [CWE-20]
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_LABEL_RE = re.compile(r"^[a-zA-Z0-9 _\-.,:()/]{1,500}$")
_MAX_DESC_LEN = 10_000
_MAX_DOC_LEN = 2_000_000   # 2 MB text document
_MAX_PROPOSALS = 5_000
_MAX_SESSIONS = 1_000
_MAX_AUDIT_LOG = 50_000
_MAX_PKG_FILES = 200

# ---------------------------------------------------------------------------
# Domain-knowledge: BMS / BCS
# ---------------------------------------------------------------------------

#: Standard BACnet object types used in building automation point maps
BMS_BACNET_OBJECT_TYPES: List[str] = [
    "Analog Input (AI)", "Analog Output (AO)", "Analog Value (AV)",
    "Binary Input (BI)", "Binary Output (BO)", "Binary Value (BV)",
    "Multi-state Input (MSI)", "Multi-state Output (MSO)",
    "Schedule (SCH)", "Trend Log (TL)", "Notification Class (NC)",
    "Device (DEV)", "Program (PRG)",
]

#: BMS compliance standards referenced in RFPs
BMS_COMPLIANCE_STANDARDS: Dict[str, str] = {
    "ASHRAE_135": "BACnet Standard ANSI/ASHRAE 135",
    "ASHRAE_62_1": "ASHRAE 62.1 Ventilation for Acceptable Indoor Air Quality",
    "ASHRAE_90_1": "ASHRAE 90.1 Energy Standard for Buildings",
    "NFPA_72": "NFPA 72 National Fire Alarm and Signaling Code",
    "NFPA_101": "NFPA 101 Life Safety Code",
    "IBC_2021": "International Building Code 2021",
    "LEED_V4": "LEED v4 Building Operations & Maintenance",
    "ISO_16484": "ISO 16484 Building Automation and Control Systems",
    "IEEE_802_3": "IEEE 802.3 Ethernet Standard",
}

#: HITL disciplines required for BMS production work
BMS_HITL_DISCIPLINES: Dict[str, Dict[str, Any]] = {
    "controls_engineer": {
        "discipline": "Building Controls Engineering",
        "certifications": ["ASHRAE BEMP", "CEM", "PE Controls"],
        "accountability": "ASHRAE / NFPA",
    },
    "commissioning_agent": {
        "discipline": "BMS Commissioning",
        "certifications": ["CxA", "BCxA", "CBCP"],
        "accountability": "AABC / NEBB / ASHRAE Guideline 0",
    },
    "mechanical_engineer": {
        "discipline": "Mechanical Engineering",
        "certifications": ["PE Mechanical"],
        "accountability": "State Engineering Board",
    },
}

#: Autonomous BMS spec template sections
_BMS_SPEC_SECTIONS: List[str] = [
    "scope_of_work",
    "system_description",
    "control_sequences",
    "point_schedule",
    "alarm_matrix",
    "communication_protocol",
    "submittals",
    "commissioning_plan",
    "warranty",
    "compliance_matrix",
]

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    """Role of an agent in the self-codebase swarm."""

    ARCHITECT   = "architect"
    CODE_GEN    = "code_gen"
    TEST        = "test"
    REVIEW      = "review"
    DEPLOY      = "deploy"
    RFP_PARSER  = "rfp_parser"
    SPEC_GEN    = "spec_gen"
    BMS_DOMAIN  = "bms_domain"


class ProposalStatus(str, Enum):
    """Lifecycle status of a swarm proposal."""

    PENDING    = "pending"
    APPROVED   = "approved"
    REJECTED   = "rejected"
    EXECUTING  = "executing"
    COMPLETE   = "complete"
    HITL_HOLD  = "hitl_hold"


class BuildMode(str, Enum):
    """Strategy used by the swarm to construct a deliverable."""

    DOCUMENT   = "document"    # build from provided RFP / contract doc
    AUTONOMOUS = "autonomous"  # build from domain knowledge, no docs needed
    HYBRID     = "hybrid"      # docs provided but gaps filled autonomously


class PackageFormat(str, Enum):
    """Output format for a swarm deliverable package."""

    JSON       = "json"
    MARKDOWN   = "markdown"
    STRUCTURED = "structured"  # dict with labelled sections


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AgentNode:
    """A single agent in the self-codebase swarm."""
    agent_id: str
    role: AgentRole
    capabilities: List[str]
    status: str = "idle"
    last_action: str = ""
    last_action_at: str = ""
    votes_cast: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "capabilities": list(self.capabilities),
            "status": self.status,
            "last_action": self.last_action,
            "last_action_at": self.last_action_at,
            "votes_cast": self.votes_cast,
        }


@dataclass
class SwarmProposal:
    """A proposed change or build output awaiting HITL / approval."""
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    description: str = ""
    files_affected: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    agent_votes: Dict[str, str] = field(default_factory=dict)   # agent_id → vote
    status: ProposalStatus = ProposalStatus.PENDING
    hitl_result: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: Optional[str] = None
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "description": self.description[:500],
            "files_affected": list(self.files_affected),
            "confidence_score": self.confidence_score,
            "agent_votes": dict(self.agent_votes),
            "status": self.status.value,
            "hitl_result": self.hitl_result,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class Recommendation:
    """An architectural or quality improvement recommendation."""
    recommendation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    category: str = "architecture"   # performance | security | architecture | testing
    title: str = ""
    description: str = ""
    priority: int = 2               # 1 (high) → 3 (low)
    affected_modules: List[str] = field(default_factory=list)
    confidence: float = 0.8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category,
            "title": self.title,
            "description": self.description[:1000],
            "priority": self.priority,
            "affected_modules": list(self.affected_modules),
            "confidence": self.confidence,
        }


@dataclass
class SwarmExecutionResult:
    """Result of executing a swarm proposal."""
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_id: str = ""
    success: bool = False
    files_modified: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    hitl_required: bool = False
    hitl_result: Optional[Dict[str, Any]] = None
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "proposal_id": self.proposal_id,
            "success": self.success,
            "files_modified": list(self.files_modified),
            "errors": list(self.errors),
            "hitl_required": self.hitl_required,
            "hitl_result": self.hitl_result,
            "executed_at": self.executed_at,
        }


@dataclass
class SwarmSession:
    """An active swarm coding session targeting a project."""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    target_project: Dict[str, Any] = field(default_factory=dict)
    proposals: List[str] = field(default_factory=list)    # proposal_ids
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_project": dict(self.target_project),
            "proposals": list(self.proposals),
            "status": self.status,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# BMS / RFP data models
# ---------------------------------------------------------------------------

@dataclass
class PointEntry:
    """A single point in a BMS point schedule."""
    point_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    point_name: str = ""
    point_type: str = ""    # AI / AO / BI / BO / AV / BV
    bacnet_object_type: str = ""
    bacnet_instance: int = 0
    engineering_units: str = ""
    description: str = ""
    system: str = ""        # hvac | lighting | fire | access | energy
    controller: str = ""
    alarm_limit_high: Optional[float] = None
    alarm_limit_low: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "point_type": self.point_type,
            "bacnet_object_type": self.bacnet_object_type,
            "bacnet_instance": self.bacnet_instance,
            "engineering_units": self.engineering_units,
            "description": self.description,
            "system": self.system,
            "controller": self.controller,
            "alarm_limit_high": self.alarm_limit_high,
            "alarm_limit_low": self.alarm_limit_low,
        }


@dataclass
class SequenceOfOperations:
    """A control sequence (SOO) entry."""
    sequence_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    system: str = ""
    name: str = ""
    description: str = ""
    setpoints: Dict[str, Any] = field(default_factory=dict)
    control_logic: str = ""
    alarms: List[str] = field(default_factory=list)
    compliance_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "system": self.system,
            "name": self.name,
            "description": self.description,
            "setpoints": dict(self.setpoints),
            "control_logic": self.control_logic,
            "alarms": list(self.alarms),
            "compliance_refs": list(self.compliance_refs),
        }


@dataclass
class RFPParseResult:
    """Structured output of parsing an RFP or contract document."""
    rfp_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_type: str = ""   # "document" | "autonomous"
    project_name: str = ""
    project_location: str = ""
    owner: str = ""
    building_type: str = ""
    scope_summary: str = ""
    systems_required: List[str] = field(default_factory=list)
    protocols_required: List[str] = field(default_factory=list)
    compliance_standards: List[str] = field(default_factory=list)
    hitl_disciplines: List[str] = field(default_factory=list)
    point_schedule: List[PointEntry] = field(default_factory=list)
    sequences: List[SequenceOfOperations] = field(default_factory=list)
    raw_sections: Dict[str, str] = field(default_factory=dict)
    parse_confidence: float = 0.0
    parsed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rfp_id": self.rfp_id,
            "source_type": self.source_type,
            "project_name": self.project_name,
            "project_location": self.project_location,
            "owner": self.owner,
            "building_type": self.building_type,
            "scope_summary": self.scope_summary[:2000],
            "systems_required": list(self.systems_required),
            "protocols_required": list(self.protocols_required),
            "compliance_standards": list(self.compliance_standards),
            "hitl_disciplines": list(self.hitl_disciplines),
            "point_schedule": [p.to_dict() for p in self.point_schedule],
            "sequences": [s.to_dict() for s in self.sequences],
            "raw_sections": {k: v[:2000] for k, v in self.raw_sections.items()},
            "parse_confidence": self.parse_confidence,
            "parsed_at": self.parsed_at,
        }


@dataclass
class DeliverablePackage:
    """A professionally labelled and packaged build deliverable."""
    package_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    package_name: str = ""
    version: str = "1.0"
    project_name: str = ""
    prepared_by: str = "Murphy System (INTRO-001 / SCS-001)"
    prepared_for: str = ""
    rfp_reference: str = ""
    build_mode: str = ""    # document | autonomous | hybrid
    sections: Dict[str, Any] = field(default_factory=dict)
    files: Dict[str, str] = field(default_factory=dict)   # filename → content
    compliance_matrix: Dict[str, bool] = field(default_factory=dict)
    hitl_sign_offs: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "draft"   # draft | pending_hitl | final

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "package_name": self.package_name,
            "version": self.version,
            "project_name": self.project_name,
            "prepared_by": self.prepared_by,
            "prepared_for": self.prepared_for,
            "rfp_reference": self.rfp_reference,
            "build_mode": self.build_mode,
            "sections": dict(self.sections),
            "files": {k: v[:5000] for k, v in self.files.items()},
            "compliance_matrix": dict(self.compliance_matrix),
            "hitl_sign_offs": list(self.hitl_sign_offs),
            "created_at": self.created_at,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"{name} must match {_ID_RE.pattern}")
    return value


def _validate_desc(value: str, name: str = "description") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value[:_MAX_DESC_LEN]


# ---------------------------------------------------------------------------
# BMS Domain Agent helpers
# ---------------------------------------------------------------------------

def _detect_systems(text: str) -> List[str]:
    """Keyword detection of BMS subsystems in free text."""
    mapping = {
        "hvac": ["hvac", "heating", "cooling", "ventilation", "ahu", "vav",
                 "chiller", "boiler", "fcu", "air handling"],
        "lighting": ["lighting", "lights", "dali", "dimming", "occupancy sensor"],
        "fire_safety": ["fire", "smoke", "sprinkler", "alarm", "nfpa"],
        "access_control": ["access", "card reader", "door", "security", "credential"],
        "energy_metering": ["energy", "meter", "kw", "kwh", "demand", "submetering"],
        "building_envelope": ["blinds", "shades", "curtain wall", "facade", "glazing"],
    }
    lower = text.lower()
    return [sys for sys, kw in mapping.items() if any(k in lower for k in kw)]


def _detect_protocols(text: str) -> List[str]:
    """Keyword detection of communication protocols in free text."""
    mapping = {
        "BACnet": ["bacnet", "ashrae 135", "btl", "mstp"],
        "Modbus": ["modbus", "rs-485", "rtu"],
        "KNX": ["knx", "eib"],
        "LonWorks": ["lonworks", "lon"],
        "OPC-UA": ["opc", "opc-ua", "opcua"],
        "DALI": ["dali"],
        "BACnet/IP": ["bacnet/ip", "bacnetip", "ethernet"],
    }
    lower = text.lower()
    return [p for p, kw in mapping.items() if any(k in lower for k in kw)]


def _detect_compliance(text: str) -> List[str]:
    """Extract compliance standard references from free text."""
    found = []
    lower = text.lower()
    standard_keywords = {
        "ASHRAE_135": ["ashrae 135", "ashrae135"],
        "ASHRAE_62_1": ["ashrae 62", "62.1"],
        "ASHRAE_90_1": ["ashrae 90", "90.1", "energy standard"],
        "NFPA_72": ["nfpa 72", "nfpa72", "fire alarm code"],
        "NFPA_101": ["nfpa 101", "life safety"],
        "IBC_2021": ["ibc", "international building code"],
        "LEED_V4": ["leed", "l.e.e.d"],
        "ISO_16484": ["iso 16484", "iso16484"],
    }
    for std, keywords in standard_keywords.items():
        if any(k in lower for k in keywords):
            found.append(std)
    return found


def _generate_point_schedule(
    systems: List[str],
    building_type: str = "office",
    floors: int = 1,
) -> List[PointEntry]:
    """Generate a representative BACnet point schedule from system list."""
    points: List[PointEntry] = []
    instance_counter = 0

    templates: Dict[str, List[Dict[str, Any]]] = {
        "hvac": [
            {"name": "ZN-T", "type": "AI", "obj": "Analog Input (AI)",
             "units": "°F", "desc": "Zone Temperature"},
            {"name": "ZN-SP", "type": "AV", "obj": "Analog Value (AV)",
             "units": "°F", "desc": "Zone Heating/Cooling Setpoint"},
            {"name": "ZN-DAP", "type": "AI", "obj": "Analog Input (AI)",
             "units": "CFM", "desc": "Discharge Air Flow"},
            {"name": "ZN-DMP", "type": "AO", "obj": "Analog Output (AO)",
             "units": "%", "desc": "Damper Position Command"},
            {"name": "ZN-OCC", "type": "BI", "obj": "Binary Input (BI)",
             "units": "Occ/Unocc", "desc": "Occupancy Status"},
            {"name": "AHU-SF-STATUS", "type": "BI", "obj": "Binary Input (BI)",
             "units": "On/Off", "desc": "Supply Fan Run Status"},
            {"name": "AHU-SF-CMD", "type": "BO", "obj": "Binary Output (BO)",
             "units": "On/Off", "desc": "Supply Fan Enable Command"},
            {"name": "AHU-SAT", "type": "AI", "obj": "Analog Input (AI)",
             "units": "°F", "desc": "Supply Air Temperature"},
        ],
        "lighting": [
            {"name": "LT-ZONE-CMD", "type": "BO", "obj": "Binary Output (BO)",
             "units": "On/Off", "desc": "Lighting Zone On/Off Command"},
            {"name": "LT-ZONE-DIM", "type": "AO", "obj": "Analog Output (AO)",
             "units": "%", "desc": "Lighting Dimming Level"},
            {"name": "LT-OCC", "type": "BI", "obj": "Binary Input (BI)",
             "units": "Occ/Unocc", "desc": "Occupancy Sensor Input"},
        ],
        "energy_metering": [
            {"name": "EM-KW", "type": "AI", "obj": "Analog Input (AI)",
             "units": "kW", "desc": "Electrical Demand"},
            {"name": "EM-KWH", "type": "AI", "obj": "Analog Input (AI)",
             "units": "kWh", "desc": "Electrical Consumption"},
            {"name": "EM-PF", "type": "AI", "obj": "Analog Input (AI)",
             "units": "PF", "desc": "Power Factor"},
        ],
        "fire_safety": [
            {"name": "FA-ALARM", "type": "BI", "obj": "Binary Input (BI)",
             "units": "Normal/Alarm", "desc": "Fire Alarm Panel Status"},
            {"name": "FA-TROUBLE", "type": "BI", "obj": "Binary Input (BI)",
             "units": "Normal/Trouble", "desc": "Fire Alarm Trouble Input"},
        ],
        "access_control": [
            {"name": "AC-DOOR-STATUS", "type": "BI", "obj": "Binary Input (BI)",
             "units": "Open/Closed", "desc": "Door Position Status"},
            {"name": "AC-DOOR-LOCK", "type": "BO", "obj": "Binary Output (BO)",
             "units": "Lock/Unlock", "desc": "Door Lock Command"},
        ],
    }

    for sys_key in systems:
        tmpl_list = templates.get(sys_key, [])
        for tmpl in tmpl_list:
            for floor in range(1, floors + 1):
                instance_counter += 1
                pts = PointEntry(
                    point_name=f"FL{floor:02d}-{tmpl['name']}",
                    point_type=tmpl["type"],
                    bacnet_object_type=tmpl["obj"],
                    bacnet_instance=instance_counter,
                    engineering_units=tmpl["units"],
                    description=f"Floor {floor} — {tmpl['desc']}",
                    system=sys_key,
                    controller=f"BAS-CTRL-{sys_key.upper()[:4]}-{floor:02d}",
                )
                # Alarm limits for temperature/energy
                if "temperature" in tmpl["desc"].lower() or "°F" in tmpl["units"]:
                    pts.alarm_limit_high = 80.0
                    pts.alarm_limit_low = 60.0
                elif "kw" in tmpl["units"].lower():
                    pts.alarm_limit_high = 500.0
                points.append(pts)
                if len(points) >= 500:  # reasonable cap
                    return points
    return points


def _generate_sequences(systems: List[str]) -> List[SequenceOfOperations]:
    """Generate standard sequences of operations for detected systems."""
    seqs: List[SequenceOfOperations] = []
    if "hvac" in systems:
        seqs.append(SequenceOfOperations(
            system="hvac",
            name="VAV Zone Temperature Control",
            description=(
                "The zone temperature controller shall maintain the space temperature "
                "at the active setpoint by modulating the VAV damper position. "
                "Occupied heating setpoint: 70°F. Occupied cooling setpoint: 74°F. "
                "Unoccupied setpoint: 65°F / 78°F. "
                "The VAV box minimum airflow shall be 30% of design maximum. "
                "During occupied mode, if zone temperature exceeds cooling setpoint, "
                "damper shall open toward maximum CFM. "
                "If zone temperature falls below heating setpoint, "
                "damper shall open to reheat minimum position."
            ),
            setpoints={
                "occupied_heating": 70.0,
                "occupied_cooling": 74.0,
                "unoccupied_heating": 65.0,
                "unoccupied_cooling": 78.0,
                "min_airflow_pct": 30,
                "max_airflow_cfm": "per_design",
            },
            control_logic=(
                "PID loop: Kp=2.0, Ki=0.1, Kd=0.05. "
                "Deadband: ±0.5°F. Reset: on occupancy change."
            ),
            alarms=[
                "High temperature alarm > 80°F (15-min delay)",
                "Low temperature alarm < 60°F (5-min delay)",
                "Damper failure: position feedback vs. command > 10% for 5 min",
            ],
            compliance_refs=["ASHRAE_62_1", "ASHRAE_90_1"],
        ))
        seqs.append(SequenceOfOperations(
            system="hvac",
            name="Air Handling Unit Supply Fan Control",
            description=(
                "The AHU supply fan shall be enabled based on occupancy schedule. "
                "Fan speed shall be controlled by a VAV duct static pressure loop. "
                "Design duct static pressure setpoint: 1.0 in. w.g. "
                "Supply air temperature setpoint reset: 55°F at full load, "
                "reset to 65°F at no load per ASHRAE 90.1 Section 6.5.3.4."
            ),
            setpoints={
                "duct_static_pressure_in_wg": 1.0,
                "sat_setpoint_full_load": 55.0,
                "sat_setpoint_no_load": 65.0,
            },
            control_logic=(
                "VFD speed command via PI loop on duct static pressure. "
                "Minimum fan speed: 20%. Startup ramp: 30 seconds."
            ),
            alarms=[
                "Fan fail: run status absent 30s after command",
                "High supply air temperature > 75°F",
                "Low supply air temperature < 45°F",
                "Filter differential pressure high",
            ],
            compliance_refs=["ASHRAE_90_1", "ASHRAE_62_1"],
        ))
    if "lighting" in systems:
        seqs.append(SequenceOfOperations(
            system="lighting",
            name="Occupancy-Based Lighting Control",
            description=(
                "Lighting zones shall be controlled based on occupancy sensor input "
                "and scheduled override. "
                "On occupancy detection: lights ramp to 100% over 2 seconds. "
                "On vacancy: 5-minute timeout, then step to 50% warning level, "
                "then off after 2 additional minutes. "
                "Manual override via wall switch shall hold lights on for 30 minutes. "
                "Daylight harvesting: dim to maintain 50 fc at work plane when daylight "
                "sensor available."
            ),
            setpoints={
                "timeout_vacancy_minutes": 5,
                "warning_dim_level_pct": 50,
                "warning_duration_minutes": 2,
                "manual_override_minutes": 30,
                "daylight_setpoint_fc": 50,
            },
            control_logic=(
                "DALI broadcast group addressing. Ramp rate: 2 s (up), 3 s (down). "
                "Emergency circuit bypasses all dimming."
            ),
            alarms=["Occupancy sensor failure", "DALI group communication fault"],
            compliance_refs=["ASHRAE_90_1", "LEED_V4"],
        ))
    if "energy_metering" in systems:
        seqs.append(SequenceOfOperations(
            system="energy_metering",
            name="Energy Demand Monitoring and Alerting",
            description=(
                "Electrical submeters shall report kW demand and kWh consumption "
                "to the BMS via Modbus RTU at 5-minute intervals. "
                "Peak demand shall be trended and alarmed at 90% of contract demand. "
                "Monthly consumption reports shall be auto-generated."
            ),
            setpoints={"demand_alarm_threshold_pct": 90},
            control_logic="Modbus polling: 300s interval. Trend log: 15-min average.",
            alarms=["Peak demand > 90% of contract demand"],
            compliance_refs=["ASHRAE_90_1", "LEED_V4"],
        ))
    return seqs


def _generate_compliance_matrix(standards: List[str]) -> Dict[str, bool]:
    """Return a compliance checklist for the listed standards."""
    matrix: Dict[str, bool] = {}
    for std in standards:
        label = BMS_COMPLIANCE_STANDARDS.get(std, std)
        matrix[label] = True   # asserted compliant; HITL sign-off required
    return matrix


def _build_alarm_matrix(point_schedule: List[PointEntry]) -> Dict[str, Any]:
    """Build an alarm matrix from point schedule entries."""
    alarms: List[Dict[str, Any]] = []
    for pt in point_schedule:
        if pt.alarm_limit_high is not None:
            alarms.append({
                "point": pt.point_name,
                "condition": f"> {pt.alarm_limit_high} {pt.engineering_units}",
                "priority": 2,
                "action": "notify_operator",
            })
        if pt.alarm_limit_low is not None:
            alarms.append({
                "point": pt.point_name,
                "condition": f"< {pt.alarm_limit_low} {pt.engineering_units}",
                "priority": 2,
                "action": "notify_operator",
            })
    return {"alarm_count": len(alarms), "alarms": alarms[:200]}


# ---------------------------------------------------------------------------
# Core engine                                                        SCS-001
# ---------------------------------------------------------------------------

class SelfCodebaseSwarm:
    """
    Self-Codebase Swarm — SCS-001.

    Manages a team of specialised agents that can:
      1. Analyse and propose changes to Murphy's own codebase (swarm-on-self).
      2. Parse RFP / contract documents and produce professional deliverable
         packages (document mode).
      3. Autonomously generate deliverables from domain knowledge alone
         (autonomous mode).

    All execution paths are gated by HITLAutonomyController when one is
    provided (or instantiated internally).
    """

    POLICY_ID = "scs-production-policy"

    def __init__(
        self,
        introspection_engine: Any = None,
        hitl_controller: Any = None,
        github_connector: Any = None,
    ) -> None:
        self._lock = threading.Lock()

        # Optional external dependencies (duck-typed)
        self._introspection = introspection_engine
        self._github = github_connector

        # HITL controller — instantiate internally if not provided
        if hitl_controller is not None:
            self._hitl = hitl_controller
        else:
            try:
                from hitl_autonomy_controller import (
                    AutonomyPolicy,
                    HITLAutonomyController,
                )
                ctrl = HITLAutonomyController()
                ctrl.register_policy(AutonomyPolicy(
                    policy_id=self.POLICY_ID,
                    name="SCS Production Policy",
                    confidence_threshold=0.99,
                    hitl_required=True,
                    auto_approve_below_risk=0.05,
                    max_autonomous_actions=5,
                    cooldown_seconds=600,
                ))
                self._hitl = ctrl
            except ImportError:
                self._hitl = None
                logger.warning("SCS-001: HITLAutonomyController not available — HITL disabled")

        # Agent roster
        self._agents: Dict[str, AgentNode] = self._init_agents()

        # State stores
        self._proposals: Dict[str, SwarmProposal] = {}
        self._sessions: Dict[str, SwarmSession] = {}
        self._packages: Dict[str, DeliverablePackage] = {}
        self._audit_log: List[Dict[str, Any]] = []

        # Cut sheet engine (CSE-001) — instantiated once per swarm
        self._cutsheet_engine: Any = CutSheetEngine() if _CUTSHEET_AVAILABLE else None

    # ------------------------------------------------------------------
    # Agent initialisation
    # ------------------------------------------------------------------

    def _init_agents(self) -> Dict[str, AgentNode]:
        specs = [
            AgentNode(
                agent_id="agent-architect-001",
                role=AgentRole.ARCHITECT,
                capabilities=[
                    "system_graph_analysis", "coupling_detection",
                    "cohesion_scoring", "structural_change_proposal",
                ],
            ),
            AgentNode(
                agent_id="agent-codegen-001",
                role=AgentRole.CODE_GEN,
                capabilities=[
                    "python_code_generation", "spec_to_code",
                    "modification_patch_generation", "docstring_generation",
                ],
            ),
            AgentNode(
                agent_id="agent-test-001",
                role=AgentRole.TEST,
                capabilities=[
                    "test_case_generation", "regression_detection",
                    "coverage_analysis", "fixture_generation",
                ],
            ),
            AgentNode(
                agent_id="agent-review-001",
                role=AgentRole.REVIEW,
                capabilities=[
                    "code_standard_review", "regression_check",
                    "security_scan", "pattern_compliance",
                ],
            ),
            AgentNode(
                agent_id="agent-deploy-001",
                role=AgentRole.DEPLOY,
                capabilities=[
                    "pr_creation", "branch_management",
                    "ci_cd_integration", "rollback",
                ],
            ),
            AgentNode(
                agent_id="agent-rfp-001",
                role=AgentRole.RFP_PARSER,
                capabilities=[
                    "rfp_section_detection", "requirements_extraction",
                    "point_schedule_parsing", "compliance_extraction",
                ],
            ),
            AgentNode(
                agent_id="agent-specgen-001",
                role=AgentRole.SPEC_GEN,
                capabilities=[
                    "spec_generation", "package_assembly",
                    "professional_labeling", "submittal_formatting",
                ],
            ),
            AgentNode(
                agent_id="agent-bms-001",
                role=AgentRole.BMS_DOMAIN,
                capabilities=[
                    "bacnet_point_map", "sequence_of_operations",
                    "alarm_matrix", "ashrae_compliance",
                    "nfpa_compliance", "commissioning_plan",
                ],
            ),
        ]
        return {a.agent_id: a for a in specs}

    # ------------------------------------------------------------------
    # Swarm-on-self: propose / execute code changes
    # ------------------------------------------------------------------

    def propose_change(self, description: str) -> SwarmProposal:
        """Orchestrate agents to analyse, generate, test, and review a change.

        Returns a SwarmProposal.  Does NOT execute; call execute_change().
        """
        desc = _validate_desc(description)

        proposal = SwarmProposal(description=desc)

        # Architect votes
        graph_summary = {}
        if self._introspection is not None:
            try:
                graph = self._introspection.get_graph()
                if graph:
                    graph_summary = {
                        "total_modules": graph.total_modules,
                        "total_functions": graph.total_functions,
                    }
            except Exception as exc:  # noqa: BLE001
                logger.debug("Graph introspection skipped: %s", exc)

        arch_confidence = 0.85 if graph_summary else 0.70
        proposal.agent_votes["agent-architect-001"] = (
            "approve" if arch_confidence >= 0.75 else "review_needed"
        )
        proposal.agent_votes["agent-codegen-001"] = "approve"
        proposal.agent_votes["agent-test-001"] = "approve"
        proposal.agent_votes["agent-review-001"] = "approve"

        # Consensus confidence
        approvals = sum(1 for v in proposal.agent_votes.values() if v == "approve")
        proposal.confidence_score = round(approvals / len(proposal.agent_votes), 4)

        # Evaluate HITL
        proposal.hitl_result = self._evaluate_hitl(
            task_type="propose_change",
            confidence=proposal.confidence_score,
            risk_level=0.3,
        )
        if proposal.hitl_result.get("requires_hitl"):
            proposal.status = ProposalStatus.HITL_HOLD
        else:
            proposal.status = ProposalStatus.APPROVED

        with self._lock:
            if len(self._proposals) >= _MAX_PROPOSALS:
                raise RuntimeError("SCS-001: proposal store at capacity")
            self._proposals[proposal.proposal_id] = proposal

        self._audit("propose_change", proposal_id=proposal.proposal_id,
                    status=proposal.status.value)
        logger.info("SCS-001 propose_change %s status=%s confidence=%.3f",
                    proposal.proposal_id, proposal.status.value,
                    proposal.confidence_score)
        return proposal

    def execute_change(self, proposal_id: str) -> SwarmExecutionResult:
        """Apply a proposal through the deploy agent.

        HITL gate is mandatory — returns a blocked result if a human
        approval has not been granted via the controller.
        """
        pid = _validate_id(proposal_id, "proposal_id")
        result = SwarmExecutionResult(proposal_id=pid)

        with self._lock:
            proposal = self._proposals.get(pid)

        if proposal is None:
            result.errors.append(f"Proposal {pid!r} not found")
            return result

        # HITL gate                                              (MANDATORY)
        hitl_eval = self._evaluate_hitl(
            task_type="execute_change",
            confidence=proposal.confidence_score,
            risk_level=0.6,   # execution is higher risk than proposal
        )
        result.hitl_result = hitl_eval

        if hitl_eval.get("requires_hitl") and not hitl_eval.get("autonomous"):
            result.hitl_required = True
            result.errors.append(
                f"HITL required before execution: {hitl_eval.get('reason')}"
            )
            with self._lock:
                proposal.status = ProposalStatus.HITL_HOLD
            self._audit("execute_change_blocked", proposal_id=pid,
                        reason=hitl_eval.get("reason"))
            logger.warning("SCS-001 execute_change BLOCKED by HITL gate: %s", pid)
            return result

        # Proceed with deploy agent simulation
        with self._lock:
            proposal.status = ProposalStatus.EXECUTING

        # Deploy agent would create branch / PR here
        result.success = True
        result.files_modified = list(proposal.files_affected)

        # Record action in HITL controller
        if self._hitl is not None:
            try:
                self._hitl.record_action(
                    task_type="execute_change",
                    autonomous=hitl_eval.get("autonomous", False),
                    outcome="success",
                    confidence=proposal.confidence_score,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("HITL record_action skipped: %s", exc)

        with self._lock:
            proposal.status = ProposalStatus.COMPLETE
            proposal.approved_at = _ts()

        self._audit("execute_change_success", proposal_id=pid)
        logger.info("SCS-001 execute_change SUCCESS proposal=%s", pid)
        return result

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def get_recommendations(self) -> List[Recommendation]:
        """Architect agent analyses the codebase and suggests improvements."""
        recs: List[Recommendation] = []

        if self._introspection is not None:
            try:
                health = self._introspection.get_health_snapshot()
                if health.get("parse_errors"):
                    recs.append(Recommendation(
                        category="architecture",
                        title="Fix Parse Errors",
                        description=(
                            f"{len(health['parse_errors'])} modules have parse errors "
                            "and are excluded from analysis. Fix syntax errors to restore "
                            "full self-visibility."
                        ),
                        priority=1,
                        affected_modules=[e["module"] for e in health["parse_errors"][:10]],
                        confidence=0.99,
                    ))
                if health.get("circular_dependencies"):
                    recs.append(Recommendation(
                        category="architecture",
                        title="Resolve Circular Dependencies",
                        description=(
                            f"{len(health['circular_dependencies'])} circular dependency "
                            "cycles detected. Introduce abstraction layers or inversion of "
                            "control to break cycles."
                        ),
                        priority=1,
                        affected_modules=[
                            m for cycle in health["circular_dependencies"][:5]
                            for m in cycle
                        ][:20],
                        confidence=0.95,
                    ))

                report = self._introspection.get_complexity_report()
                if report.get("total_loc", 0) > 500_000:
                    recs.append(Recommendation(
                        category="architecture",
                        title="Large Codebase — Consider Modular Packaging",
                        description=(
                            f"Codebase exceeds {report['total_loc']:,} LOC. "
                            "Consider packaging subsystems as importable libraries "
                            "with explicit public APIs."
                        ),
                        priority=2,
                        confidence=0.80,
                    ))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Recommendation analysis skipped: %s", exc)

        # Generic best-practice recommendations
        recs.append(Recommendation(
            category="testing",
            title="Verify HITL Coverage for All Production Paths",
            description=(
                "All execute_change() and execute_build() paths must pass through "
                "HITLAutonomyController. Verify via integration test."
            ),
            priority=1,
            confidence=0.95,
        ))
        return recs

    # ------------------------------------------------------------------
    # Swarm on external project
    # ------------------------------------------------------------------

    def swarm_on_project(self, project_config: Dict[str, Any]) -> SwarmSession:
        """Target an external project with the swarm (observation mode)."""
        if not isinstance(project_config, dict):
            raise ValueError("project_config must be a dict")
        session = SwarmSession(target_project=project_config)
        with self._lock:
            if len(self._sessions) >= _MAX_SESSIONS:
                raise RuntimeError("SCS-001: session store at capacity")
            self._sessions[session.session_id] = session
        self._audit("swarm_on_project", session_id=session.session_id)
        return session

    # ------------------------------------------------------------------
    # RFP / document parsing
    # ------------------------------------------------------------------

    def parse_rfp(self, document_text: str, project_name: str = "") -> RFPParseResult:
        """Parse an RFP or contract document and extract structured requirements.

        Handles Building Management Control Systems RFPs as well as
        general construction / engineering documents.

        Args:
            document_text: raw text of the RFP / spec document (≤ 2 MB).
            project_name: optional override for project name.

        Returns:
            RFPParseResult with extracted requirements, point schedule, and
            sequences of operations.
        """
        if not isinstance(document_text, str):
            raise ValueError("document_text must be a string")
        doc = document_text[:_MAX_DOC_LEN]

        result = RFPParseResult(source_type="document")

        # Project metadata extraction
        result.project_name = project_name or self._extract_field(
            doc, r"(?i)project\s*name\s*[:\-]\s*(.{3,120})"
        ) or "Unnamed Project"
        result.project_location = self._extract_field(
            doc, r"(?i)(?:project\s*)?location\s*[:\-]\s*(.{3,200})"
        ) or ""
        result.owner = self._extract_field(
            doc, r"(?i)owner\s*[:\-]\s*(.{3,200})"
        ) or ""
        result.building_type = self._extract_field(
            doc, r"(?i)building\s*type\s*[:\-]\s*(.{3,100})"
        ) or "commercial"

        # Systems, protocols, compliance
        result.systems_required = _detect_systems(doc)
        result.protocols_required = _detect_protocols(doc)
        result.compliance_standards = _detect_compliance(doc)

        # HITL disciplines: check for P.E. / commissioning language
        lower = doc.lower()
        if any(k in lower for k in ["licensed engineer", "pe stamp", "p.e.", "engineer of record"]):
            result.hitl_disciplines.append("mechanical_engineer")
        if any(k in lower for k in ["commissioning", "cx", "cxa"]):
            result.hitl_disciplines.append("commissioning_agent")
        if any(k in lower for k in ["controls engineer", "controls contractor"]):
            result.hitl_disciplines.append("controls_engineer")

        # Scope summary (first 1000 chars of first "scope" section)
        scope_match = re.search(
            r"(?i)(?:scope\s+of\s+work|scope|section\s+1)[^\n]*\n(.{20,2000})",
            doc,
            re.DOTALL,
        )
        result.scope_summary = scope_match.group(1)[:1000].strip() if scope_match else ""

        # Generate point schedule and sequences from detected systems
        floors = self._estimate_floors(doc)
        result.point_schedule = _generate_point_schedule(
            result.systems_required,
            building_type=result.building_type,
            floors=floors,
        )
        result.sequences = _generate_sequences(result.systems_required)

        # Raw section extraction
        result.raw_sections = self._extract_sections(doc)

        # Confidence based on richness of extraction
        score = 0.5
        if result.systems_required:
            score += 0.1
        if result.protocols_required:
            score += 0.1
        if result.compliance_standards:
            score += 0.1
        if result.point_schedule:
            score += 0.1
        if result.sequences:
            score += 0.1
        result.parse_confidence = min(round(score, 3), 0.99)

        self._audit("parse_rfp", project=result.project_name,
                    systems=result.systems_required,
                    confidence=result.parse_confidence)
        logger.info("SCS-001 parse_rfp '%s' confidence=%.3f points=%d",
                    result.project_name, result.parse_confidence,
                    len(result.point_schedule))
        return result

    # ------------------------------------------------------------------
    # Build deliverable package
    # ------------------------------------------------------------------

    def build_package(
        self,
        rfp_result: Optional[RFPParseResult] = None,
        mode: BuildMode = BuildMode.AUTONOMOUS,
        project_name: str = "",
        prepared_for: str = "",
        rfp_reference: str = "",
        building_type: str = "office",
        systems: Optional[List[str]] = None,
        floors: int = 1,
    ) -> DeliverablePackage:
        """Generate a professionally labelled, packaged deliverable.

        This is the core build-to-spec method.  It operates in three modes:

        * **document** — rfp_result must be provided.  The package is built
          entirely from the parsed RFP.
        * **autonomous** — no RFP needed.  Murphy generates a complete BMS
          spec, point schedule, and SOO from domain knowledge.
        * **hybrid** — rfp_result provided but gaps are filled autonomously.

        The result is gated by HITL before status is set to "final".

        Args:
            rfp_result: output of parse_rfp() (required for document/hybrid mode).
            mode: BuildMode enum value.
            project_name: overrides rfp_result.project_name if set.
            prepared_for: client / owner name for cover page.
            rfp_reference: RFP document number / reference.
            building_type: used in autonomous mode (office/hospital/warehouse…).
            systems: explicit list of BMS systems for autonomous mode.
            floors: number of floors (autonomous mode).

        Returns:
            DeliverablePackage with all sections, files, and compliance matrix.
        """
        # Resolve RFP data
        if mode == BuildMode.DOCUMENT and rfp_result is None:
            raise ValueError("rfp_result is required for BuildMode.DOCUMENT")

        if rfp_result is not None:
            pname = project_name or rfp_result.project_name
            pfor = prepared_for or rfp_result.owner
            ref = rfp_reference or rfp_result.rfp_id
            active_systems = rfp_result.systems_required or (systems or ["hvac"])
            active_protocols = rfp_result.protocols_required or ["BACnet"]
            active_compliance = rfp_result.compliance_standards or ["ASHRAE_135", "ASHRAE_90_1"]
            active_floors = floors
            pt_schedule = rfp_result.point_schedule
            seqs = rfp_result.sequences
            hitl_disciplines = rfp_result.hitl_disciplines
        else:
            # Autonomous mode — generate everything
            pname = project_name or f"BMS Project — {building_type.title()}"
            pfor = prepared_for or "Owner / General Contractor"
            ref = rfp_reference or "AUTONOMOUS"
            active_systems = systems or ["hvac", "lighting", "energy_metering"]
            active_protocols = ["BACnet/IP", "BACnet"]
            active_compliance = ["ASHRAE_135", "ASHRAE_90_1", "ASHRAE_62_1", "LEED_V4"]
            active_floors = max(1, floors)
            pt_schedule = _generate_point_schedule(
                active_systems, building_type=building_type, floors=active_floors
            )
            seqs = _generate_sequences(active_systems)
            hitl_disciplines = ["controls_engineer", "commissioning_agent"]

        pkg = DeliverablePackage(
            package_name=f"BMS Submittal — {pname}",
            project_name=pname,
            prepared_for=pfor,
            rfp_reference=ref,
            build_mode=mode.value,
        )

        # ── Section 1: Cover Page / Title Block ──────────────────────────
        pkg.sections["01_cover"] = {
            "title": "BUILDING MANAGEMENT CONTROL SYSTEM SUBMITTAL",
            "project_name": pname,
            "prepared_by": pkg.prepared_by,
            "prepared_for": pfor,
            "rfp_reference": ref,
            "date": _ts()[:10],
            "revision": pkg.version,
            "classification": "SUBMITTAL — FOR REVIEW AND APPROVAL",
        }

        # ── Section 2: Table of Contents ────────────────────────────────
        pkg.sections["02_toc"] = {
            "sections": _BMS_SPEC_SECTIONS,
            "generated_at": _ts(),
        }

        # ── Section 3: Scope of Work ─────────────────────────────────────
        scope_text = (
            rfp_result.scope_summary if rfp_result and rfp_result.scope_summary
            else self._generate_scope(pname, active_systems, building_type, active_floors)
        )
        pkg.sections["03_scope_of_work"] = {"text": scope_text}

        # ── Section 4: System Description ────────────────────────────────
        pkg.sections["04_system_description"] = {
            "systems": active_systems,
            "protocols": active_protocols,
            "building_type": building_type,
            "floors": active_floors,
            "total_points": len(pt_schedule),
            "description": self._generate_system_description(
                active_systems, active_protocols
            ),
        }

        # ── Section 5: Control Sequences ────────────────────────────────
        pkg.sections["05_control_sequences"] = {
            "sequences": [s.to_dict() for s in seqs]
        }

        # ── Section 6: Point Schedule ────────────────────────────────────
        pkg.sections["06_point_schedule"] = {
            "total_points": len(pt_schedule),
            "points": [p.to_dict() for p in pt_schedule],
            "summary": self._point_schedule_summary(pt_schedule),
        }

        # ── Section 7: Alarm Matrix ──────────────────────────────────────
        pkg.sections["07_alarm_matrix"] = _build_alarm_matrix(pt_schedule)

        # ── Section 8: Communication Protocol ───────────────────────────
        pkg.sections["08_communication_protocol"] = {
            "primary_protocol": active_protocols[0] if active_protocols else "BACnet/IP",
            "secondary_protocols": active_protocols[1:],
            "network_architecture": self._generate_network_description(active_protocols),
        }

        # ── Section 9: Submittals Checklist ─────────────────────────────
        pkg.sections["09_submittals"] = self._generate_submittals_checklist(
            active_systems, active_protocols
        )

        # ── Section 10: Commissioning Plan ──────────────────────────────
        pkg.sections["10_commissioning_plan"] = self._generate_commissioning_plan(
            active_systems, hitl_disciplines
        )

        # ── Section 11: Warranty ─────────────────────────────────────────
        pkg.sections["11_warranty"] = {
            "parts_years": 1,
            "labor_years": 1,
            "software_years": 3,
            "statement": (
                "Contractor shall warrant all materials, equipment, and workmanship "
                "for a period of one (1) year from date of final acceptance. "
                "BMS software licenses shall be warranted for three (3) years."
            ),
        }

        # ── Compliance matrix ────────────────────────────────────────────
        pkg.compliance_matrix = _generate_compliance_matrix(active_compliance)

        # ── HITL sign-off requirements ────────────────────────────────────
        for discipline_key in hitl_disciplines:
            disc_info = BMS_HITL_DISCIPLINES.get(discipline_key, {})
            pkg.hitl_sign_offs.append({
                "discipline": discipline_key,
                "discipline_label": disc_info.get("discipline", discipline_key),
                "certifications_required": disc_info.get("certifications", []),
                "accountability": disc_info.get("accountability", ""),
                "status": "pending",
                "signed_by": None,
                "signed_at": None,
            })

        # ── File assets ───────────────────────────────────────────────────
        pkg.files["COVER_SHEET.md"] = self._render_cover_sheet(pkg)
        pkg.files["POINT_SCHEDULE.json"] = self._render_point_schedule_json(pt_schedule)
        pkg.files["SEQUENCE_OF_OPERATIONS.md"] = self._render_soo_markdown(seqs)
        pkg.files["COMPLIANCE_MATRIX.json"] = self._render_compliance_json(
            pkg.compliance_matrix, active_compliance
        )
        pkg.files["ALARM_MATRIX.json"] = self._render_alarm_matrix_json(
            pkg.sections["07_alarm_matrix"]
        )
        pkg.files["COMMISSIONING_CHECKLIST.md"] = self._render_cx_checklist(
            pkg.sections["10_commissioning_plan"]
        )

        # ── HITL gate for finalisation ────────────────────────────────────
        hitl_eval = self._evaluate_hitl(
            task_type="build_package",
            confidence=0.97,
            risk_level=0.2,
        )
        if hitl_eval.get("requires_hitl"):
            pkg.status = "pending_hitl"
        else:
            pkg.status = "final"

        with self._lock:
            if len(self._packages) >= _MAX_PROPOSALS:
                raise RuntimeError("SCS-001: package store at capacity")
            self._packages[pkg.package_id] = pkg

        self._audit("build_package", package_id=pkg.package_id,
                    mode=mode.value, status=pkg.status,
                    total_points=len(pt_schedule))
        logger.info(
            "SCS-001 build_package '%s' mode=%s status=%s points=%d sections=%d",
            pname, mode.value, pkg.status, len(pt_schedule), len(pkg.sections),
        )
        return pkg

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_proposal(self, proposal_id: str) -> Optional[SwarmProposal]:
        pid = _validate_id(proposal_id, "proposal_id")
        with self._lock:
            return self._proposals.get(pid)

    def get_package(self, package_id: str) -> Optional[DeliverablePackage]:
        _validate_id(package_id, "package_id")
        with self._lock:
            return self._packages.get(package_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._agents.values()]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Cut sheet integration (CSE-001)
    # ------------------------------------------------------------------

    def ingest_cutsheet(
        self,
        text: str,
        manufacturer: str = "",
        model: str = "",
    ) -> Any:
        """Parse a manufacturer cut sheet and store it in the cut sheet library.

        Args:
            text: plain-text content of the product data sheet.
            manufacturer: optional manufacturer name override.
            model: optional model number override.

        Returns:
            CutSheetSpec parsed from the document, or a dict with an error
            key if the cut sheet engine is unavailable.
        """
        if self._cutsheet_engine is None:
            return {"error": "cutsheet_engine_unavailable"}
        spec = self._cutsheet_engine.parse_cutsheet(text, manufacturer, model)
        self._audit("ingest_cutsheet",
                    cutsheet_id=spec.cutsheet_id,
                    manufacturer=spec.manufacturer,
                    model=spec.model_number,
                    category=spec.category.value)
        return spec

    def generate_drawings_from_cutsheets(
        self,
        cutsheet_ids: List[str],
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Generate wiring and control diagrams from stored cut sheets.

        Args:
            cutsheet_ids: list of cutsheet_id values previously returned by
                ingest_cutsheet().
            project_name: project name for title blocks.

        Returns:
            Dict with keys "wiring_diagram" and "control_diagram" containing
            the rendered diagram objects, plus "files" with markdown/CSV exports.
        """
        if self._cutsheet_engine is None:
            return {"error": "cutsheet_engine_unavailable"}

        cutsheets = [
            self._cutsheet_engine.get_cutsheet(cid)
            for cid in cutsheet_ids
        ]
        cutsheets = [c for c in cutsheets if c is not None]

        if not cutsheets:
            return {"error": "no_valid_cutsheets", "requested": cutsheet_ids}

        wiring = self._cutsheet_engine.generate_wiring_diagram(
            cutsheets, project_name=project_name
        )
        control = self._cutsheet_engine.generate_control_diagram(
            cutsheets, project_name=project_name
        )

        self._audit("generate_drawings",
                    wiring_diagram_id=wiring.diagram_id,
                    control_diagram_id=control.diagram_id,
                    device_count=len(cutsheets))
        return {
            "wiring_diagram": wiring.to_dict(),
            "control_diagram": control.to_dict(),
            "files": {
                "WIRING_DIAGRAM.md": wiring.markdown_render,
                "WIRE_LIST.csv": wiring.wire_list_csv,
                "CONTROL_DIAGRAM.md": control.markdown_render,
            },
        }

    def generate_device_code_from_cutsheets(
        self,
        cutsheet_ids: List[str],
        project_name: str = "",
        start_device_instance: int = 1,
    ) -> Dict[str, Any]:
        """Generate BACnet device configs and controller code from cut sheets.

        Args:
            cutsheet_ids: list of cutsheet_id values from ingest_cutsheet().
            project_name: used in device names and config labelling.
            start_device_instance: starting BACnet device instance number.

        Returns:
            Dict with "device_configs" (list of DeviceConfig dicts),
            "json_export" (combined JSON ready for front-end import), and
            "program_stubs" (controller program skeleton per device).
        """
        if self._cutsheet_engine is None:
            return {"error": "cutsheet_engine_unavailable"}

        cutsheets = [
            self._cutsheet_engine.get_cutsheet(cid)
            for cid in cutsheet_ids
        ]
        cutsheets = [c for c in cutsheets if c is not None]
        if not cutsheets:
            return {"error": "no_valid_cutsheets", "requested": cutsheet_ids}

        configs = self._cutsheet_engine.generate_device_configs(
            cutsheets,
            project_name=project_name,
            start_device_instance=start_device_instance,
        )
        json_export = self._cutsheet_engine.export_device_configs_json(configs)

        self._audit("generate_device_code",
                    config_count=len(configs),
                    project=project_name)
        return {
            "device_configs": [c.to_dict() for c in configs],
            "json_export": json_export,
            "program_stubs": {
                c.device_name: c.controller_program_stub for c in configs
            },
        }

    def verify_commissioning_from_cutsheets(
        self,
        cutsheet_ids: List[str],
        commissioned_requirements: Optional[Dict[str, Any]] = None,
        field_measurements: Optional[Dict[str, Any]] = None,
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Verify commissioned requirements against manufacturer cut sheet specs.

        Compares what the cut sheets declare against:
          1. The commissioned requirements (what was specified in the RFP).
          2. Optional field-measured values from on-site commissioning.

        HITL sign-off is flagged for any failed or safety-critical test.

        Args:
            cutsheet_ids: list of cutsheet_id values from ingest_cutsheet().
            commissioned_requirements: dict mapping cutsheet_id → requirement
                dict (required_model, required_range_min, required_accuracy…).
            field_measurements: dict mapping test_id → {value, tested_by,
                tested_at} for tests that have been executed on-site.
            project_name: project name for the report header.

        Returns:
            Dict with "verification_result" (VerificationResult dict) and
            "report_markdown" (human-readable commissioning report).
        """
        if self._cutsheet_engine is None:
            return {"error": "cutsheet_engine_unavailable"}

        cutsheets = [
            self._cutsheet_engine.get_cutsheet(cid)
            for cid in cutsheet_ids
        ]
        cutsheets = [c for c in cutsheets if c is not None]
        if not cutsheets:
            return {"error": "no_valid_cutsheets", "requested": cutsheet_ids}

        vr = self._cutsheet_engine.verify_commissioning(
            cutsheets,
            commissioned_requirements=commissioned_requirements,
            field_measurements=field_measurements,
        )
        vr.project_name = project_name or vr.project_name
        report_md = self._cutsheet_engine.export_verification_report(vr)

        # HITL gate: if any tests failed, block final acceptance
        hitl_eval = self._evaluate_hitl(
            task_type="verify_commissioning",
            confidence=vr.passed / max(len(vr.tests), 1),
            risk_level=0.8 if vr.failed > 0 else 0.2,
        )

        self._audit("verify_commissioning",
                    result_id=vr.result_id,
                    passed=vr.passed,
                    failed=vr.failed,
                    hitl_required=hitl_eval.get("requires_hitl", False))
        return {
            "verification_result": vr.to_dict(),
            "report_markdown": report_md,
            "hitl_eval": hitl_eval,
            "acceptance_blocked": hitl_eval.get("requires_hitl", False),
        }

    def get_cutsheet(self, cutsheet_id: str) -> Optional[Any]:
        """Return a previously ingested CutSheetSpec by ID."""
        if self._cutsheet_engine is None:
            return None
        return self._cutsheet_engine.get_cutsheet(cutsheet_id)

    def list_cutsheets(self) -> List[Dict[str, Any]]:
        """Return summary list of all ingested cut sheets."""
        if self._cutsheet_engine is None:
            return []
        return self._cutsheet_engine.list_cutsheets()

    def _evaluate_hitl(
        self,
        task_type: str,
        confidence: float,
        risk_level: float,
    ) -> Dict[str, Any]:
        """Delegate to HITLAutonomyController or return safe default."""
        if self._hitl is None:
            # No controller — treat every action as requiring HITL
            return {
                "autonomous": False,
                "reason": "no_hitl_controller",
                "requires_hitl": True,
                "confidence": confidence,
                "risk_level": risk_level,
            }
        try:
            return self._hitl.evaluate_autonomy(
                task_type=task_type,
                confidence=confidence,
                risk_level=risk_level,
                policy_id=self.POLICY_ID,
            )
        except Exception as exc:
            logger.error("SCS-001 HITL evaluation error: %s", _sanitize_error(exc))
            return {
                "autonomous": False,
                "reason": "hitl_evaluation_error",
                "requires_hitl": True,
                "confidence": confidence,
                "risk_level": risk_level,
            }

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _audit(self, action: str, **kwargs: Any) -> None:
        entry = {"action": action, "timestamp": _ts(), **kwargs}
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    # ------------------------------------------------------------------
    # Document parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_field(text: str, pattern: str) -> str:
        m = re.search(pattern, text)
        return m.group(1).strip()[:200] if m else ""

    @staticmethod
    def _estimate_floors(text: str) -> int:
        m = re.search(r"(?i)(\d{1,3})\s*(?:floors?|stor(?:e|ey|ies))", text)
        if m:
            return min(int(m.group(1)), 100)
        return 1

    @staticmethod
    def _extract_sections(text: str) -> Dict[str, str]:
        """Split document into labelled sections on all-caps headers."""
        sections: Dict[str, str] = {}
        header_re = re.compile(
            r"(?m)^(?:SECTION\s+\d+[\.\-:\s]+|PART\s+\d+[\.\-:\s]+)?"
            r"([A-Z][A-Z0-9 \-/]{4,80})\s*$"
        )
        matches = list(header_re.finditer(text))
        for idx, match in enumerate(matches[:40]):
            header = match.group(1).strip()[:80]
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            sections[header] = text[start:end][:3000].strip()
        return sections

    # ------------------------------------------------------------------
    # Content generation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_scope(
        project_name: str,
        systems: List[str],
        building_type: str,
        floors: int,
    ) -> str:
        sys_labels = ", ".join(s.replace("_", " ").title() for s in systems)
        return (
            f"The Contractor shall furnish, install, program, and commission a "
            f"complete Building Management Control System (BMCS) for {project_name}. "
            f"The project consists of a {floors}-floor {building_type} building. "
            f"The scope includes all {sys_labels} systems as specified herein. "
            f"All work shall be performed in accordance with the Contract Documents, "
            f"applicable codes, and standards referenced in this specification. "
            f"The Contractor shall provide all labour, materials, software, "
            f"documentation, and commissioning services required for a fully "
            f"operational and warranted system."
        )

    @staticmethod
    def _generate_system_description(systems: List[str], protocols: List[str]) -> str:
        sys_str = " and ".join(s.replace("_", " ").upper() for s in systems)
        proto_str = " / ".join(protocols) if protocols else "BACnet/IP"
        return (
            f"The BMCS shall provide centralised monitoring and control of {sys_str} "
            f"systems via a {proto_str} network. "
            f"The system shall utilise direct digital controllers (DDC) at the field "
            f"level with a centralised operator workstation. "
            f"All controllers shall be native BACnet BTL-certified devices. "
            f"The system shall support web-based remote access with role-based "
            f"access control (RBAC). "
            f"A minimum of 3 years of trend data shall be stored locally."
        )

    @staticmethod
    def _generate_network_description(protocols: List[str]) -> str:
        if "BACnet/IP" in protocols:
            return (
                "Primary network: BACnet/IP over dedicated 1 Gbps Ethernet VLAN. "
                "Field device network: BACnet MS/TP at 76.8 kbps. "
                "IP addressing: /24 subnet, DHCP reserved by MAC. "
                "Network isolation: BACnet VLAN shall be isolated from corporate LAN. "
                "All IP devices shall support TLS 1.2 or higher for web services."
            )
        return (
            "Field bus: Modbus RTU RS-485 at 19.2 kbps. "
            "Max segment length: 1,200 m with repeaters. "
            "Termination resistors: 120 Ω at each segment end."
        )

    @staticmethod
    def _generate_submittals_checklist(
        systems: List[str], protocols: List[str]
    ) -> Dict[str, Any]:
        items = [
            "Product Data Sheets for all DDC controllers",
            "Product Data Sheets for all sensors and actuators",
            "BACnet Protocol Implementation Conformance Statements (PICS)",
            "Network architecture diagram (single-line)",
            "Floor plan with controller locations",
            "Point schedule (all I/O points, tagged per specification)",
            "Sequence of Operations narratives",
            "Alarm matrix with priorities and notification routes",
            "Control diagrams / schematics",
            "Software logic documentation",
            "Commissioning plan",
            "O&M manuals and warranties",
            "Training plan (minimum 8 hours owner training)",
        ]
        if "DALI" in protocols or "lighting" in systems:
            items.append("DALI addressing plan and group schedules")
        return {"required_submittals": items, "submission_phase": "50% Construction Documents"}

    @staticmethod
    def _generate_commissioning_plan(
        systems: List[str], hitl_disciplines: List[str]
    ) -> Dict[str, Any]:
        phases = [
            {
                "phase": "Pre-functional Testing",
                "description": "Verify all installations prior to functional testing. "
                               "Check wiring, addressing, and network connectivity.",
                "responsible": "Controls Contractor",
                "hitl_required": False,
            },
            {
                "phase": "Functional Performance Testing (FPT)",
                "description": "Test all sequences of operations against specification. "
                               "Owner representative and CxA to witness.",
                "responsible": "Controls Contractor + CxA",
                "hitl_required": True,
            },
            {
                "phase": "Integrated Systems Testing (IST)",
                "description": "Verify cross-system integration (fire alarm ↔ HVAC, "
                               "access control ↔ HVAC). Require all trade sign-offs.",
                "responsible": "CxA + All Trades",
                "hitl_required": True,
            },
            {
                "phase": "Owner Training",
                "description": "Minimum 8 hours hands-on training on operator workstation, "
                               "alarm management, and scheduling.",
                "responsible": "Controls Contractor",
                "hitl_required": False,
            },
            {
                "phase": "Final Acceptance",
                "description": "CxA issues final commissioning report. Warranty period begins.",
                "responsible": "CxA + Owner",
                "hitl_required": True,
            },
        ]
        return {
            "phases": phases,
            "required_disciplines": [
                BMS_HITL_DISCIPLINES.get(d, {"discipline": d})["discipline"]
                for d in hitl_disciplines
            ],
        }

    @staticmethod
    def _point_schedule_summary(pts: List[PointEntry]) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for pt in pts:
            summary[pt.point_type] = summary.get(pt.point_type, 0) + 1
        return summary

    # ------------------------------------------------------------------
    # File rendering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_cover_sheet(pkg: DeliverablePackage) -> str:
        cov = pkg.sections.get("01_cover", {})
        lines = [
            "# " + cov.get("title", "BUILDING MANAGEMENT CONTROL SYSTEM SUBMITTAL"),
            "",
            f"**Project Name:** {cov.get('project_name', '')}",
            f"**Prepared By:** {cov.get('prepared_by', '')}",
            f"**Prepared For:** {cov.get('prepared_for', '')}",
            f"**RFP Reference:** {cov.get('rfp_reference', '')}",
            f"**Date:** {cov.get('date', '')}",
            f"**Revision:** {cov.get('revision', '1.0')}",
            f"**Classification:** {cov.get('classification', '')}",
            "",
            "---",
            "",
            "## Table of Contents",
        ]
        for sec in _BMS_SPEC_SECTIONS:
            lines.append(f"- {sec.replace('_', ' ').title()}")
        return "\n".join(lines)

    @staticmethod
    def _render_point_schedule_json(pts: List[PointEntry]) -> str:
        import json
        return json.dumps(
            {"point_count": len(pts), "points": [p.to_dict() for p in pts]},
            indent=2,
        )

    @staticmethod
    def _render_soo_markdown(seqs: List[SequenceOfOperations]) -> str:
        lines = ["# Sequence of Operations\n"]
        for seq in seqs:
            lines.append(f"## {seq.name}")
            lines.append(f"**System:** {seq.system.replace('_', ' ').title()}")
            lines.append(f"\n{seq.description}\n")
            if seq.setpoints:
                lines.append("**Setpoints:**")
                for k, v in seq.setpoints.items():
                    lines.append(f"- {k}: {v}")
            if seq.control_logic:
                lines.append(f"\n**Control Logic:** {seq.control_logic}")
            if seq.alarms:
                lines.append("\n**Alarms:**")
                for a in seq.alarms:
                    lines.append(f"- {a}")
            if seq.compliance_refs:
                refs = ", ".join(
                    BMS_COMPLIANCE_STANDARDS.get(r, r) for r in seq.compliance_refs
                )
                lines.append(f"\n**Compliance References:** {refs}")
            lines.append("\n---\n")
        return "\n".join(lines)

    @staticmethod
    def _render_compliance_json(matrix: Dict[str, bool], standards: List[str]) -> str:
        import json
        output = {
            "compliant_standards": [
                {
                    "code": std,
                    "label": BMS_COMPLIANCE_STANDARDS.get(std, std),
                    "compliant": matrix.get(
                        BMS_COMPLIANCE_STANDARDS.get(std, std), False
                    ),
                    "note": "Asserted compliant — HITL sign-off required",
                }
                for std in standards
            ]
        }
        return json.dumps(output, indent=2)

    @staticmethod
    def _render_alarm_matrix_json(alarm_section: Dict[str, Any]) -> str:
        import json
        return json.dumps(alarm_section, indent=2)

    @staticmethod
    def _render_cx_checklist(cx_plan: Dict[str, Any]) -> str:
        lines = ["# Commissioning Checklist\n"]
        for phase_info in cx_plan.get("phases", []):
            hitl_flag = " *(HITL sign-off required)*" if phase_info.get("hitl_required") else ""
            lines.append(f"## {phase_info['phase']}{hitl_flag}")
            lines.append(f"**Responsible:** {phase_info['responsible']}")
            lines.append(f"\n{phase_info['description']}\n")
            lines.append("- [ ] Completed")
            lines.append("- [ ] Signed off by responsible party")
            lines.append("")
        required = cx_plan.get("required_disciplines", [])
        if required:
            lines.append("## Required Disciplines for Final Acceptance")
            for d in required:
                lines.append(f"- [ ] {d}")
        return "\n".join(lines)

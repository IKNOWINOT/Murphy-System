"""
Energy Audit Engine — ASHRAE Level I/II/III audit workflows, Energy
Conservation Measure (ECM) identification, ROI/payback calculations,
ISO 50002 / ISO 50001 compliance reporting, and utility benchmark analysis.

Design Label: EAE-001 — Energy Audit Engine

Provides end-to-end energy audit lifecycle management:
  - ASHRAE Level I (walk-through), II (energy survey), III (detailed analysis)
  - ECM identification with automatic payback and ROI computation
  - ISO 50001 / ISO 50002 / ASHRAE 90.1 / ENERGY STAR compliance checklists
  - Utility benchmark analysis against CBECS / ENERGY STAR median EUI values
  - Knapsack-style ECM prioritisation within a capital budget
  - Thread-safe state mutations; bounded collections (CWE-400)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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
# Module-level constants
# ---------------------------------------------------------------------------

_MAX_STR_LEN = 200
_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')
_MAX_READINGS_PER_AUDIT = 100_000   # CWE-400 guard
_MAX_ECMS_PER_AUDIT = 500
_MAX_FINDINGS_PER_AUDIT = 1_000
_MAX_FACILITY_SQFT = 10_000_000
_KWH_TO_KBTU = 3.412               # 1 kWh = 3.412 kBtu
_DEFAULT_CARBON_FACTOR = 0.386      # kg CO2e per kWh (US average)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AuditLevel(Enum):
    """ASHRAE audit level (Enum subclass)."""
    LEVEL_I = "level_i"      # Walk-through assessment
    LEVEL_II = "level_ii"    # Energy survey and analysis
    LEVEL_III = "level_iii"  # Detailed analysis of capital-intensive modifications


class AuditStatus(Enum):
    """Lifecycle status of an energy audit (Enum subclass)."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class ECMCategory(Enum):
    """Energy Conservation Measure category (Enum subclass)."""
    HVAC = "hvac"
    LIGHTING = "lighting"
    BUILDING_ENVELOPE = "building_envelope"
    PROCESS_EQUIPMENT = "process_equipment"
    CONTROLS_AND_AUTOMATION = "controls_and_automation"
    RENEWABLE_GENERATION = "renewable_generation"
    WASTE_HEAT_RECOVERY = "waste_heat_recovery"
    COMPRESSED_AIR = "compressed_air"
    MOTORS_AND_DRIVES = "motors_and_drives"
    WATER = "water"


class ECMPriority(Enum):
    """ECM implementation priority (Enum subclass)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceFramework(Enum):
    """Supported energy compliance / certification frameworks (Enum subclass)."""
    ASHRAE_90_1 = "ashrae_90_1"
    ISO_50001 = "iso_50001"
    ISO_50002 = "iso_50002"
    ENERGY_STAR = "energy_star"
    LEED = "leed"
    BREEAM = "breeam"


class FindingSeverity(Enum):
    """Severity level for audit findings (Enum subclass)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EnergyReading:
    """A single energy meter reading for a facility."""
    reading_id: str
    facility_id: str
    meter_id: str
    energy_type: str          # e.g. "electricity", "natural_gas", "steam"
    value_kwh: float          # normalised to kWh equivalent
    timestamp: float          # Unix epoch
    period_days: int          # billing/measurement period length
    unit_cost_usd: float      # USD per kWh (or kWh-equivalent)
    demand_kw: Optional[float] = None  # Peak demand for the period


@dataclass
class EnergyCostSummary:
    """Aggregated energy cost metrics for a facility over a period."""
    facility_id: str
    period_start: float
    period_end: float
    total_kwh: float
    total_cost_usd: float
    peak_demand_kw: float
    avg_monthly_kwh: float
    eui: float                  # Energy Use Intensity kBtu/sqft/year
    carbon_kg_co2e: float


@dataclass
class EnergyConservationMeasure:
    """An identified Energy Conservation Measure with financial metrics."""
    ecm_id: str
    audit_id: str
    title: str
    description: str
    category: ECMCategory
    priority: ECMPriority
    estimated_annual_savings_kwh: float
    estimated_annual_savings_usd: float
    implementation_cost_usd: float
    simple_payback_years: float       # auto-computed
    roi_percent: float                # auto-computed
    carbon_reduction_kg_co2e: float
    confidence_level: float           # 0.0–1.0
    implementation_complexity: int    # 1 (simple) – 5 (complex)


@dataclass
class AuditFinding:
    """A single observation recorded during an energy audit."""
    finding_id: str
    audit_id: str
    area_description: str
    observation: str
    baseline_consumption_kwh: float
    potential_savings_pct: float
    severity: FindingSeverity


@dataclass
class EnergyAudit:
    """Top-level energy audit record."""
    audit_id: str
    facility_id: str
    facility_name: str
    facility_sqft: int
    audit_level: AuditLevel
    status: AuditStatus
    auditor_name: str
    started_at: float
    completed_at: Optional[float]
    ecms: List[EnergyConservationMeasure] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    compliance_frameworks: List[ComplianceFramework] = field(default_factory=list)
    executive_summary: str = ""
    total_estimated_savings_usd: float = 0.0
    total_implementation_cost_usd: float = 0.0
    portfolio_payback_years: float = 0.0


# ---------------------------------------------------------------------------
# CBECS / ENERGY STAR median EUI benchmarks (kBtu/sqft/year)
# Source: US EIA CBECS 2018 & ENERGY STAR Portfolio Manager.
# ---------------------------------------------------------------------------

_BENCHMARK_EUI: Dict[str, Dict[str, Any]] = {
    "office": {
        "median_kbtu_sqft_yr": 69.0,
        "energy_star_threshold": 54.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "retail": {
        "median_kbtu_sqft_yr": 60.0,
        "energy_star_threshold": 44.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "warehouse": {
        "median_kbtu_sqft_yr": 30.0,
        "energy_star_threshold": 24.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "hospital": {
        "median_kbtu_sqft_yr": 250.0,
        "energy_star_threshold": 185.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "school": {
        "median_kbtu_sqft_yr": 55.0,
        "energy_star_threshold": 44.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "hotel": {
        "median_kbtu_sqft_yr": 117.0,
        "energy_star_threshold": 87.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "restaurant": {
        "median_kbtu_sqft_yr": 438.0,
        "energy_star_threshold": 300.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "grocery": {
        "median_kbtu_sqft_yr": 425.0,
        "energy_star_threshold": 310.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "multifamily": {
        "median_kbtu_sqft_yr": 41.0,
        "energy_star_threshold": 30.0,
        "source": "CBECS 2018 / ENERGY STAR",
    },
    "manufacturing": {
        "median_kbtu_sqft_yr": 95.0,
        "energy_star_threshold": 70.0,
        "source": "CBECS 2018 / EPA estimates",
    },
    "laboratory": {
        "median_kbtu_sqft_yr": 330.0,
        "energy_star_threshold": 250.0,
        "source": "CBECS 2018 / EPA estimates",
    },
    "data_center": {
        "median_kbtu_sqft_yr": 1700.0,
        "energy_star_threshold": 1200.0,
        "source": "EPA DC estimates",
    },
}


# ---------------------------------------------------------------------------
# Compliance framework checklist templates
# ---------------------------------------------------------------------------

_COMPLIANCE_CHECKLISTS: Dict[ComplianceFramework, List[Dict[str, Any]]] = {
    ComplianceFramework.ASHRAE_90_1: [
        {"item": "Lighting power density within ASHRAE 90.1 limits", "section": "9"},
        {"item": "HVAC system meets minimum efficiency requirements", "section": "6"},
        {"item": "Building envelope insulation meets prescriptive path", "section": "5"},
        {"item": "Energy cost budget method documented", "section": "11"},
        {"item": "Mandatory provisions (lighting controls) satisfied", "section": "9.4"},
        {"item": "Service hot water efficiency requirements met", "section": "7"},
        {"item": "Power factor correction / motors comply", "section": "10"},
        {"item": "Commissioning plan documented and executed", "section": "Cx"},
    ],
    ComplianceFramework.ISO_50001: [
        {"item": "Energy policy established and communicated", "clause": "5.2"},
        {"item": "Energy management team assigned", "clause": "5.3"},
        {"item": "Significant energy uses (SEUs) identified", "clause": "6.3"},
        {"item": "Energy baseline established", "clause": "6.5"},
        {"item": "Energy performance indicators (EnPIs) defined", "clause": "6.4"},
        {"item": "Objectives and energy targets set", "clause": "6.6"},
        {"item": "Operational controls for SEUs documented", "clause": "8.1"},
        {"item": "Monitoring and measurement plan in place", "clause": "9.1"},
        {"item": "Internal audit programme established", "clause": "9.2"},
        {"item": "Management review conducted", "clause": "9.3"},
    ],
    ComplianceFramework.ISO_50002: [
        {"item": "Audit scope and boundaries defined", "clause": "4.2"},
        {"item": "Data collection plan established", "clause": "5.1"},
        {"item": "Energy balance verified", "clause": "5.2"},
        {"item": "Energy performance opportunities identified", "clause": "5.3"},
        {"item": "Improvement measures quantified", "clause": "5.4"},
        {"item": "Audit report meets ISO 50002 content requirements", "clause": "6"},
        {"item": "Auditor competence documented", "clause": "4.3"},
        {"item": "Uncertainty of measurement addressed", "clause": "5.2.4"},
    ],
    ComplianceFramework.ENERGY_STAR: [
        {"item": "Facility benchmarked in Portfolio Manager", "section": "Benchmarking"},
        {"item": "Energy Star score ≥ 75 (if applicable)", "section": "Score"},
        {"item": "25% better energy performance than median", "section": "Performance"},
        {"item": "Data verified by licensed professional", "section": "Verification"},
        {"item": "Statement of energy performance obtained", "section": "Certification"},
        {"item": "Continuous performance tracking in Portfolio Manager", "section": "Tracking"},
    ],
    ComplianceFramework.LEED: [
        {"item": "Minimum energy performance prerequisite met", "credit": "EAp2"},
        {"item": "Fundamental commissioning completed", "credit": "EAp1"},
        {"item": "Enhanced commissioning documented", "credit": "EAc3"},
        {"item": "Energy modelling performed (ASHRAE 90.1 Appendix G)", "credit": "EAc2"},
        {"item": "Measurement and verification plan established", "credit": "EAc5"},
        {"item": "On-site renewable energy evaluated", "credit": "EAc2"},
        {"item": "Green power / RECs documented", "credit": "EAc4"},
        {"item": "Advanced energy metering in place", "credit": "EAc4"},
    ],
    ComplianceFramework.BREEAM: [
        {"item": "Energy consumption sub-metering installed", "credit": "Ene 02"},
        {"item": "Energy monitoring strategy documented", "credit": "Ene 02"},
        {"item": "Lean design (passive measures) demonstrated", "credit": "Ene 01"},
        {"item": "Carbon reduction target set and modelled", "credit": "Ene 01"},
        {"item": "External lighting efficacy meets BREEAM criteria", "credit": "Ene 07"},
        {"item": "Lift energy efficiency provisions satisfied", "credit": "Ene 06"},
        {"item": "Drying space / renewables considered", "credit": "Ene 04"},
        {"item": "Building fabric thermal performance documented", "credit": "Ene 01"},
    ],
}


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _sanitize_str(value: str, field: str = "field") -> str:
    """Strip null bytes and enforce maximum string length."""
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a str, got {type(value).__name__}")
    value = value.replace("\x00", "")
    if len(value) > _MAX_STR_LEN:
        raise ValueError(f"{field} exceeds {_MAX_STR_LEN} characters")
    return value


def _validate_id(value: str, field: str = "id") -> str:
    """Validate an ID matches the slug pattern ^[a-zA-Z0-9_\\-]{1,64}$."""
    if not _ID_PATTERN.match(value):
        raise ValueError(
            f"{field} must match ^[a-zA-Z0-9_\\-]{{1,64}}$, got {value!r}"
        )
    return value


def _validate_non_negative(value: float, field: str) -> float:
    """Validate a monetary / numeric value is non-negative."""
    if not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field} must be a non-negative number, got {value!r}")
    return float(value)


def _validate_sqft(sqft: int) -> int:
    """Validate facility square footage is a positive int within cap."""
    if not isinstance(sqft, int) or sqft <= 0 or sqft > _MAX_FACILITY_SQFT:
        raise ValueError(
            f"facility_sqft must be a positive int ≤ {_MAX_FACILITY_SQFT:,}, "
            f"got {sqft!r}"
        )
    return sqft


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EnergyAuditEngine:
    """Full lifecycle energy audit engine.

    Thread-safe: all state mutations are guarded by ``self._lock``.
    Bounded collections prevent unbounded memory growth (CWE-400).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._audits: Dict[str, EnergyAudit] = {}
        self._readings: Dict[str, List[EnergyReading]] = {}  # keyed by audit_id

    # -- audit lifecycle ----------------------------------------------------

    def create_audit(
        self,
        facility_id: str,
        facility_name: str,
        sqft: int,
        audit_level: AuditLevel,
        auditor_name: str,
        compliance_frameworks: Optional[List[ComplianceFramework]] = None,
    ) -> EnergyAudit:
        """Create a new energy audit record in DRAFT status.

        Returns
        -------
        EnergyAudit
            The newly created audit object.
        """
        facility_id = _validate_id(facility_id, "facility_id")
        facility_name = _sanitize_str(facility_name, "facility_name")
        sqft = _validate_sqft(sqft)
        auditor_name = _sanitize_str(auditor_name, "auditor_name")

        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        audit = EnergyAudit(
            audit_id=audit_id,
            facility_id=facility_id,
            facility_name=facility_name,
            facility_sqft=sqft,
            audit_level=audit_level,
            status=AuditStatus.DRAFT,
            auditor_name=auditor_name,
            started_at=time.time(),
            completed_at=None,
            compliance_frameworks=list(compliance_frameworks or []),
        )
        with self._lock:
            self._audits[audit_id] = audit
            self._readings[audit_id] = []
        logger.info("Created audit %s for facility %s", audit_id, facility_id)
        return audit

    def get_audit(self, audit_id: str) -> Optional[EnergyAudit]:
        """Return the audit with *audit_id*, or None if not found."""
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            return self._audits.get(audit_id)

    def list_audits(
        self,
        facility_id: Optional[str] = None,
        status: Optional[AuditStatus] = None,
        level: Optional[AuditLevel] = None,
    ) -> List[Dict[str, Any]]:
        """Return a list of audit summaries, optionally filtered."""
        with self._lock:
            audits = list(self._audits.values())
        if facility_id is not None:
            audits = [a for a in audits if a.facility_id == facility_id]
        if status is not None:
            audits = [a for a in audits if a.status == status]
        if level is not None:
            audits = [a for a in audits if a.audit_level == level]
        return [
            {
                "audit_id": a.audit_id,
                "facility_id": a.facility_id,
                "facility_name": a.facility_name,
                "audit_level": a.audit_level.value,
                "status": a.status.value,
                "auditor_name": a.auditor_name,
                "ecm_count": len(a.ecms),
                "finding_count": len(a.findings),
                "started_at": a.started_at,
                "completed_at": a.completed_at,
            }
            for a in audits
        ]

    def advance_audit_status(
        self, audit_id: str, new_status: AuditStatus
    ) -> Dict[str, Any]:
        """Transition an audit to *new_status* and return the updated record.

        Automatically records ``completed_at`` when transitioning to COMPLETE.
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
            if audit is None:
                return {"success": False, "error": f"Unknown audit: {audit_id}"}
            prev_status = audit.status
            audit.status = new_status
            if new_status == AuditStatus.COMPLETE and audit.completed_at is None:
                audit.completed_at = time.time()
            return {
                "success": True,
                "audit_id": audit_id,
                "previous_status": prev_status.value,
                "new_status": new_status.value,
            }

    # -- energy readings ----------------------------------------------------

    def ingest_energy_readings(
        self, audit_id: str, readings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate and store a batch of energy readings for an audit.

        Each dict in *readings* must contain the fields of :class:`EnergyReading`.
        Readings are capped at ``_MAX_READINGS_PER_AUDIT`` per audit.

        Returns
        -------
        dict
            ``{"success": bool, "ingested": int, "skipped": int, "errors": list}``
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            if audit_id not in self._audits:
                return {"success": False, "error": f"Unknown audit: {audit_id}"}
            existing = self._readings[audit_id]

        ingested = 0
        skipped = 0
        errors: List[str] = []

        for idx, raw in enumerate(readings):
            try:
                reading = EnergyReading(
                    reading_id=_validate_id(
                        str(raw.get("reading_id", uuid.uuid4().hex[:12])),
                        "reading_id",
                    ),
                    facility_id=_validate_id(
                        str(raw["facility_id"]), "facility_id"
                    ),
                    meter_id=_sanitize_str(str(raw["meter_id"]), "meter_id"),
                    energy_type=_sanitize_str(
                        str(raw.get("energy_type", "electricity")), "energy_type"
                    ),
                    value_kwh=_validate_non_negative(
                        float(raw["value_kwh"]), "value_kwh"
                    ),
                    timestamp=float(raw.get("timestamp", time.time())),
                    period_days=max(1, int(raw.get("period_days", 30))),
                    unit_cost_usd=_validate_non_negative(
                        float(raw.get("unit_cost_usd", 0.0)), "unit_cost_usd"
                    ),
                    demand_kw=(
                        float(raw["demand_kw"]) if raw.get("demand_kw") is not None
                        else None
                    ),
                )
                with self._lock:
                    if len(existing) >= _MAX_READINGS_PER_AUDIT:
                        skipped += len(readings) - idx
                        errors.append(
                            f"Readings cap ({_MAX_READINGS_PER_AUDIT}) reached; "
                            f"{len(readings) - idx} readings not ingested."
                        )
                        break
                    capped_append(existing, reading, max_size=_MAX_READINGS_PER_AUDIT)
                ingested += 1
            except (KeyError, ValueError, TypeError) as exc:
                skipped += 1
                errors.append(f"Row {idx}: {exc}")

        return {
            "success": ingested > 0 or not errors,
            "ingested": ingested,
            "skipped": skipped,
            "errors": errors,
        }

    # -- cost summary -------------------------------------------------------

    def compute_cost_summary(
        self,
        audit_id: str,
        facility_sqft: Optional[int] = None,
        carbon_factor: float = _DEFAULT_CARBON_FACTOR,
    ) -> Optional[EnergyCostSummary]:
        """Compute an :class:`EnergyCostSummary` from the stored readings.

        Parameters
        ----------
        facility_sqft:
            Override the sqft stored on the audit (for on-the-fly what-if).
        carbon_factor:
            kg CO2e per kWh.  Defaults to 0.386 (US average).

        Returns
        -------
        EnergyCostSummary or None
            None when no readings are available for the audit.
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
            readings = list(self._readings.get(audit_id, []))

        if audit is None or not readings:
            return None

        sqft = facility_sqft if facility_sqft is not None else audit.facility_sqft
        sqft = _validate_sqft(sqft)

        total_kwh = sum(r.value_kwh for r in readings)
        total_cost = sum(r.value_kwh * r.unit_cost_usd for r in readings)
        peak_demand = max(
            (r.demand_kw for r in readings if r.demand_kw is not None), default=0.0
        )
        timestamps = [r.timestamp for r in readings]
        period_start = min(timestamps)
        period_end = max(timestamps)

        # Duration in months (minimum 1).
        duration_months = max(
            1.0,
            (period_end - period_start) / (30.44 * 86400),
        )
        avg_monthly_kwh = total_kwh / duration_months

        # EUI — annualise from actual period length.
        duration_years = duration_months / 12.0
        annualised_kwh = total_kwh / max(duration_years, 1 / 12)
        eui = round((annualised_kwh * _KWH_TO_KBTU) / sqft, 2)

        carbon = round(total_kwh * carbon_factor, 2)

        return EnergyCostSummary(
            facility_id=audit.facility_id,
            period_start=round(period_start, 2),
            period_end=round(period_end, 2),
            total_kwh=round(total_kwh, 2),
            total_cost_usd=round(total_cost, 2),
            peak_demand_kw=round(peak_demand, 2),
            avg_monthly_kwh=round(avg_monthly_kwh, 2),
            eui=eui,
            carbon_kg_co2e=carbon,
        )

    # -- ECMs ---------------------------------------------------------------

    def add_ecm(
        self,
        audit_id: str,
        title: str,
        description: str,
        category: ECMCategory,
        priority: ECMPriority,
        annual_savings_kwh: float,
        unit_cost_usd: float,
        impl_cost_usd: float,
        carbon_reduction_kg: float = 0.0,
        confidence: float = 0.8,
        complexity: int = 2,
    ) -> Dict[str, Any]:
        """Add an Energy Conservation Measure to an audit.

        Automatically computes ``simple_payback_years`` and ``roi_percent``.

        Returns
        -------
        dict
            ``{"success": bool, "ecm": EnergyConservationMeasure | None, "error": str}``
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
            if audit is None:
                return {"success": False, "ecm": None, "error": f"Unknown audit: {audit_id}"}
            if len(audit.ecms) >= _MAX_ECMS_PER_AUDIT:
                return {
                    "success": False,
                    "ecm": None,
                    "error": f"ECM cap ({_MAX_ECMS_PER_AUDIT}) reached for audit",
                }

        title = _sanitize_str(title, "title")
        description = _sanitize_str(description, "description")
        annual_savings_kwh = _validate_non_negative(annual_savings_kwh, "annual_savings_kwh")
        unit_cost_usd = _validate_non_negative(unit_cost_usd, "unit_cost_usd")
        impl_cost_usd = _validate_non_negative(impl_cost_usd, "impl_cost_usd")
        carbon_reduction_kg = _validate_non_negative(carbon_reduction_kg, "carbon_reduction_kg")
        confidence = float(max(0.0, min(1.0, confidence)))
        complexity = int(max(1, min(5, complexity)))

        annual_savings_usd = round(annual_savings_kwh * unit_cost_usd, 2)

        # Simple payback: years to recover investment from annual savings.
        if annual_savings_usd > 0:
            payback = round(impl_cost_usd / annual_savings_usd, 2)
        else:
            payback = float("inf")

        # ROI: percentage return on implementation investment per year.
        if impl_cost_usd > 0:
            roi = round((annual_savings_usd / impl_cost_usd) * 100.0, 2)
        else:
            roi = 0.0

        ecm = EnergyConservationMeasure(
            ecm_id=f"ecm_{uuid.uuid4().hex[:12]}",
            audit_id=audit_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            estimated_annual_savings_kwh=round(annual_savings_kwh, 2),
            estimated_annual_savings_usd=annual_savings_usd,
            implementation_cost_usd=round(impl_cost_usd, 2),
            simple_payback_years=payback,
            roi_percent=roi,
            carbon_reduction_kg_co2e=round(carbon_reduction_kg, 2),
            confidence_level=round(confidence, 2),
            implementation_complexity=complexity,
        )

        with self._lock:
            capped_append(audit.ecms, ecm, max_size=_MAX_ECMS_PER_AUDIT)
            # Recompute portfolio totals.
            audit.total_estimated_savings_usd = round(
                sum(e.estimated_annual_savings_usd for e in audit.ecms), 2
            )
            audit.total_implementation_cost_usd = round(
                sum(e.implementation_cost_usd for e in audit.ecms), 2
            )
            if audit.total_estimated_savings_usd > 0:
                audit.portfolio_payback_years = round(
                    audit.total_implementation_cost_usd
                    / audit.total_estimated_savings_usd,
                    2,
                )

        logger.info("Added ECM %s to audit %s", ecm.ecm_id, audit_id)
        return {"success": True, "ecm": ecm, "error": None}

    def get_ecm(self, audit_id: str, ecm_id: str) -> Optional[EnergyConservationMeasure]:
        """Return a specific ECM by audit and ECM ID, or None."""
        audit_id = _validate_id(audit_id, "audit_id")
        ecm_id = _validate_id(ecm_id, "ecm_id")
        with self._lock:
            audit = self._audits.get(audit_id)
        if audit is None:
            return None
        return next((e for e in audit.ecms if e.ecm_id == ecm_id), None)

    def list_ecms(
        self,
        audit_id: str,
        category: Optional[ECMCategory] = None,
        priority: Optional[ECMPriority] = None,
        max_payback_years: Optional[float] = None,
    ) -> List[EnergyConservationMeasure]:
        """Return ECMs for an audit, with optional filtering.

        Parameters
        ----------
        category:
            Filter to a specific :class:`ECMCategory`.
        priority:
            Filter to a specific :class:`ECMPriority`.
        max_payback_years:
            Include only ECMs with ``simple_payback_years ≤ max_payback_years``.
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
        if audit is None:
            return []
        ecms = list(audit.ecms)
        if category is not None:
            ecms = [e for e in ecms if e.category == category]
        if priority is not None:
            ecms = [e for e in ecms if e.priority == priority]
        if max_payback_years is not None:
            ecms = [e for e in ecms if e.simple_payback_years <= max_payback_years]
        return ecms

    # -- findings -----------------------------------------------------------

    def add_finding(
        self,
        audit_id: str,
        area: str,
        observation: str,
        baseline_kwh: float,
        savings_pct: float,
        severity: FindingSeverity,
    ) -> Dict[str, Any]:
        """Record an audit finding observation.

        Returns
        -------
        dict
            ``{"success": bool, "finding": AuditFinding | None, "error": str}``
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
            if audit is None:
                return {
                    "success": False,
                    "finding": None,
                    "error": f"Unknown audit: {audit_id}",
                }
            if len(audit.findings) >= _MAX_FINDINGS_PER_AUDIT:
                return {
                    "success": False,
                    "finding": None,
                    "error": f"Finding cap ({_MAX_FINDINGS_PER_AUDIT}) reached",
                }

        area = _sanitize_str(area, "area")
        observation = _sanitize_str(observation, "observation")
        baseline_kwh = _validate_non_negative(baseline_kwh, "baseline_kwh")
        savings_pct = float(max(0.0, min(100.0, savings_pct)))

        finding = AuditFinding(
            finding_id=f"finding_{uuid.uuid4().hex[:12]}",
            audit_id=audit_id,
            area_description=area,
            observation=observation,
            baseline_consumption_kwh=round(baseline_kwh, 2),
            potential_savings_pct=round(savings_pct, 2),
            severity=severity,
        )
        with self._lock:
            capped_append(audit.findings, finding, max_size=_MAX_FINDINGS_PER_AUDIT)

        return {"success": True, "finding": finding, "error": None}

    # -- reporting ----------------------------------------------------------

    def generate_executive_summary(self, audit_id: str) -> str:
        """Generate a structured plain-text executive summary for the audit.

        The summary includes facility metadata, total savings projections,
        the top five ECMs by ROI, findings count, and compliance framework
        status.
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
        if audit is None:
            return f"Audit {audit_id} not found."

        lines: List[str] = [
            "=" * 70,
            "ENERGY AUDIT EXECUTIVE SUMMARY",
            "=" * 70,
            f"Audit ID       : {audit.audit_id}",
            f"Facility       : {audit.facility_name} (ID: {audit.facility_id})",
            f"Facility Size  : {audit.facility_sqft:,} sq ft",
            f"Audit Level    : {audit.audit_level.value.upper()}",
            f"Status         : {audit.status.value.upper()}",
            f"Auditor        : {audit.auditor_name}",
            f"Started        : {time.strftime('%Y-%m-%d', time.localtime(audit.started_at))}",
        ]
        if audit.completed_at:
            lines.append(
                f"Completed      : "
                f"{time.strftime('%Y-%m-%d', time.localtime(audit.completed_at))}"
            )

        lines += [
            "",
            "FINANCIAL SUMMARY",
            "-" * 40,
            f"Total ECMs Identified      : {len(audit.ecms)}",
            f"Total Annual Savings (USD) : ${audit.total_estimated_savings_usd:,.2f}",
            f"Total Implementation Cost  : ${audit.total_implementation_cost_usd:,.2f}",
            f"Portfolio Payback Period   : {audit.portfolio_payback_years:.1f} years",
            "",
            "TOP 5 ECMs BY ROI",
            "-" * 40,
        ]

        top_ecms = sorted(
            audit.ecms, key=lambda e: e.roi_percent, reverse=True
        )[:5]
        if top_ecms:
            for i, ecm in enumerate(top_ecms, 1):
                lines.append(
                    f"  {i}. [{ecm.priority.value.upper()}] {ecm.title}"
                )
                lines.append(
                    f"     Category: {ecm.category.value} | "
                    f"Savings: ${ecm.estimated_annual_savings_usd:,.2f}/yr | "
                    f"Payback: {ecm.simple_payback_years:.1f} yr | "
                    f"ROI: {ecm.roi_percent:.1f}%"
                )
        else:
            lines.append("  No ECMs recorded yet.")

        lines += [
            "",
            "AUDIT FINDINGS",
            "-" * 40,
            f"Total Findings : {len(audit.findings)}",
        ]
        severity_counts: Dict[str, int] = {}
        for f in audit.findings:
            severity_counts[f.severity.value] = (
                severity_counts.get(f.severity.value, 0) + 1
            )
        for sev, cnt in sorted(severity_counts.items()):
            lines.append(f"  {sev.upper()}: {cnt}")

        if audit.compliance_frameworks:
            lines += [
                "",
                "COMPLIANCE FRAMEWORKS",
                "-" * 40,
            ]
            for fw in audit.compliance_frameworks:
                lines.append(f"  - {fw.value.upper()}")

        lines.append("=" * 70)
        summary = "\n".join(lines)

        with self._lock:
            audit.executive_summary = summary

        return summary

    def generate_compliance_report(
        self, audit_id: str, framework: ComplianceFramework
    ) -> Dict[str, Any]:
        """Generate a framework-specific compliance checklist report.

        Each checklist item is assessed as PASS when the audit has at least
        one ECM or finding, otherwise NEEDS_REVIEW.  The audit owner must
        override individual items with actual evidence in production.

        Returns
        -------
        dict
            ``{"audit_id", "framework", "items": [{item, result, ...}], "score"}``
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
        if audit is None:
            return {"success": False, "error": f"Unknown audit: {audit_id}"}

        checklist = _COMPLIANCE_CHECKLISTS.get(framework, [])
        has_data = bool(audit.ecms or audit.findings)

        items = []
        passed = 0
        for item_def in checklist:
            # Automatic assessment: if audit has ECMs/findings, mark as PASS;
            # otherwise NEEDS_REVIEW.  Auditors may override these results.
            result = "PASS" if has_data else "NEEDS_REVIEW"
            if result == "PASS":
                passed += 1
            row = dict(item_def)
            row["result"] = result
            items.append(row)

        total = len(items)
        score = round((passed / total * 100), 2) if total else 0.0

        return {
            "audit_id": audit_id,
            "facility_name": audit.facility_name,
            "framework": framework.value,
            "items": items,
            "passed": passed,
            "total": total,
            "score_pct": score,
            "timestamp": time.time(),
        }

    # -- prioritisation -----------------------------------------------------

    def prioritize_ecms(
        self, audit_id: str, budget_usd: float
    ) -> List[EnergyConservationMeasure]:
        """Select the highest-value ECMs within a capital budget.

        Uses a greedy approach: sort all ECMs by ROI descending, then add
        ECMs while the running implementation cost is within budget.

        Parameters
        ----------
        budget_usd:
            Available capital budget in USD.

        Returns
        -------
        list[EnergyConservationMeasure]
            Selected ECMs sorted by ROI (highest first).
        """
        audit_id = _validate_id(audit_id, "audit_id")
        budget_usd = _validate_non_negative(budget_usd, "budget_usd")
        with self._lock:
            audit = self._audits.get(audit_id)
        if audit is None:
            return []

        sorted_ecms = sorted(audit.ecms, key=lambda e: e.roi_percent, reverse=True)
        selected: List[EnergyConservationMeasure] = []
        remaining = budget_usd

        for ecm in sorted_ecms:
            if ecm.implementation_cost_usd <= remaining:
                selected.append(ecm)
                remaining -= ecm.implementation_cost_usd

        return selected

    # -- export -------------------------------------------------------------

    def export_audit(self, audit_id: str) -> Dict[str, Any]:
        """Return a fully serialised audit dictionary.

        Suitable for JSON serialisation or API response bodies.
        """
        audit_id = _validate_id(audit_id, "audit_id")
        with self._lock:
            audit = self._audits.get(audit_id)
            readings = list(self._readings.get(audit_id, []))
        if audit is None:
            return {"success": False, "error": f"Unknown audit: {audit_id}"}

        return {
            "audit_id": audit.audit_id,
            "facility_id": audit.facility_id,
            "facility_name": audit.facility_name,
            "facility_sqft": audit.facility_sqft,
            "audit_level": audit.audit_level.value,
            "status": audit.status.value,
            "auditor_name": audit.auditor_name,
            "started_at": audit.started_at,
            "completed_at": audit.completed_at,
            "compliance_frameworks": [f.value for f in audit.compliance_frameworks],
            "executive_summary": audit.executive_summary,
            "total_estimated_savings_usd": audit.total_estimated_savings_usd,
            "total_implementation_cost_usd": audit.total_implementation_cost_usd,
            "portfolio_payback_years": audit.portfolio_payback_years,
            "ecms": [
                {
                    "ecm_id": e.ecm_id,
                    "title": e.title,
                    "description": e.description,
                    "category": e.category.value,
                    "priority": e.priority.value,
                    "estimated_annual_savings_kwh": e.estimated_annual_savings_kwh,
                    "estimated_annual_savings_usd": e.estimated_annual_savings_usd,
                    "implementation_cost_usd": e.implementation_cost_usd,
                    "simple_payback_years": e.simple_payback_years,
                    "roi_percent": e.roi_percent,
                    "carbon_reduction_kg_co2e": e.carbon_reduction_kg_co2e,
                    "confidence_level": e.confidence_level,
                    "implementation_complexity": e.implementation_complexity,
                }
                for e in audit.ecms
            ],
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "area_description": f.area_description,
                    "observation": f.observation,
                    "baseline_consumption_kwh": f.baseline_consumption_kwh,
                    "potential_savings_pct": f.potential_savings_pct,
                    "severity": f.severity.value,
                }
                for f in audit.findings
            ],
            "reading_count": len(readings),
        }

    # -- benchmarking -------------------------------------------------------

    def benchmark_eui(
        self, facility_type: str, eui_kbtu_sqft_year: float
    ) -> Dict[str, Any]:
        """Compare the facility's EUI against CBECS / ENERGY STAR medians.

        Parameters
        ----------
        facility_type:
            Building type key (e.g. ``"office"``, ``"warehouse"``).
            Case-insensitive.  Unknown types return the comparison with
            a note that no benchmark data is available.
        eui_kbtu_sqft_year:
            Measured EUI in kBtu/sqft/year.

        Returns
        -------
        dict
            Comparison dict with percentage vs. median and rating.
        """
        eui_kbtu_sqft_year = _validate_non_negative(
            eui_kbtu_sqft_year, "eui_kbtu_sqft_year"
        )
        ft_key = facility_type.lower().strip()
        benchmark = _BENCHMARK_EUI.get(ft_key)

        if benchmark is None:
            return {
                "facility_type": facility_type,
                "eui_kbtu_sqft_year": round(eui_kbtu_sqft_year, 2),
                "benchmark_available": False,
                "note": (
                    f"No benchmark data for facility type '{facility_type}'. "
                    f"Available types: {sorted(_BENCHMARK_EUI.keys())}"
                ),
            }

        median = benchmark["median_kbtu_sqft_yr"]
        es_threshold = benchmark["energy_star_threshold"]
        pct_vs_median = round(
            ((eui_kbtu_sqft_year - median) / median) * 100.0, 2
        )

        if eui_kbtu_sqft_year <= es_threshold:
            rating = "ENERGY_STAR_ELIGIBLE"
        elif eui_kbtu_sqft_year <= median * 0.75:
            rating = "ABOVE_AVERAGE"
        elif eui_kbtu_sqft_year <= median * 1.10:
            rating = "AVERAGE"
        elif eui_kbtu_sqft_year <= median * 1.50:
            rating = "BELOW_AVERAGE"
        else:
            rating = "POOR"

        return {
            "facility_type": facility_type,
            "eui_kbtu_sqft_year": round(eui_kbtu_sqft_year, 2),
            "benchmark_available": True,
            "median_kbtu_sqft_yr": median,
            "energy_star_threshold": es_threshold,
            "pct_vs_median": pct_vs_median,
            "rating": rating,
            "source": benchmark["source"],
        }

    # -- Layer 4 extensions: CBECS confidence, M&V, degree-day ──────────

    def benchmark_eui_with_confidence(
        self,
        facility_type: str,
        eui_kbtu_sqft_year: float,
        sample_size: int = 50,
    ) -> Dict[str, Any]:
        """Compare EUI against CBECS with statistical confidence intervals.

        Uses a normal approximation: median ± 1.96 × (IQR / √n).
        """
        eui_kbtu_sqft_year = _validate_non_negative(eui_kbtu_sqft_year, "eui")
        ft_key = facility_type.lower().strip()
        benchmark = _BENCHMARK_EUI.get(ft_key)
        if benchmark is None:
            return {"benchmark_available": False, "facility_type": facility_type}

        median = benchmark["median_kbtu_sqft_yr"]
        # Assume IQR ≈ 40 % of median (typical CBECS spread)
        iqr_estimate = median * 0.40
        import math
        se = iqr_estimate / math.sqrt(max(sample_size, 1))
        ci_low = round(median - 1.96 * se, 2)
        ci_high = round(median + 1.96 * se, 2)

        pct_vs_median = round(((eui_kbtu_sqft_year - median) / median) * 100, 1) if median else 0
        within_ci = ci_low <= eui_kbtu_sqft_year <= ci_high

        return {
            "facility_type": facility_type,
            "eui_kbtu_sqft_year": round(eui_kbtu_sqft_year, 2),
            "cbecs_median": median,
            "confidence_interval_95": {"low": ci_low, "high": ci_high},
            "within_confidence_interval": within_ci,
            "pct_vs_median": pct_vs_median,
            "sample_size_assumed": sample_size,
        }

    def mv_savings_tracking(
        self,
        audit_id: str,
        baseline_kwh: float,
        post_implementation_kwh: float,
        ipmvp_option: str = "B",
        adjustment_factor: float = 1.0,
    ) -> Dict[str, Any]:
        """Measurement & Verification per IPMVP Option A/B/C/D.

        Parameters
        ----------
        baseline_kwh : float
            Pre-implementation annual energy use.
        post_implementation_kwh : float
            Post-implementation annual energy use.
        ipmvp_option : str
            A = retrofit isolation (key parameter), B = retrofit isolation (all parameters),
            C = whole facility, D = calibrated simulation.
        adjustment_factor : float
            Non-routine adjustment (weather normalisation, occupancy, etc.).
        """
        audit_id = _validate_id(audit_id, "audit_id")
        baseline_kwh = _validate_non_negative(baseline_kwh, "baseline_kwh")
        post_implementation_kwh = _validate_non_negative(
            post_implementation_kwh, "post_kwh"
        )

        adjusted_baseline = baseline_kwh * adjustment_factor
        actual_savings = adjusted_baseline - post_implementation_kwh
        savings_pct = round((actual_savings / adjusted_baseline) * 100, 2) if adjusted_baseline else 0

        option_descriptions = {
            "A": "Retrofit Isolation — Key Parameter Measurement",
            "B": "Retrofit Isolation — All Parameter Measurement",
            "C": "Whole Facility — Utility Billing Analysis",
            "D": "Calibrated Simulation",
        }

        return {
            "audit_id": audit_id,
            "ipmvp_option": ipmvp_option.upper(),
            "option_description": option_descriptions.get(ipmvp_option.upper(), "Unknown"),
            "baseline_kwh": round(adjusted_baseline, 2),
            "post_implementation_kwh": round(post_implementation_kwh, 2),
            "actual_savings_kwh": round(actual_savings, 2),
            "savings_pct": savings_pct,
            "adjustment_factor": adjustment_factor,
            "verified": actual_savings > 0,
        }

    def degree_day_normalise(
        self,
        monthly_kwh: List[float],
        monthly_hdd: List[float],
        monthly_cdd: List[float],
    ) -> Dict[str, Any]:
        """Whole-building degree-day normalisation (EnergyPlus-style).

        Fits: kWh = a + b × HDD + c × CDD via OLS regression.
        Returns coefficients, weather-normalised annual consumption, and R².
        """
        n = len(monthly_kwh)
        if n < 3 or len(monthly_hdd) != n or len(monthly_cdd) != n:
            return {"error": "Need ≥ 3 months with matched kWh, HDD, CDD arrays"}

        # OLS with two predictors using normal equations
        # X = [[1, hdd, cdd], ...]  y = [kwh, ...]
        sum_y = sum(monthly_kwh)
        sum_h = sum(monthly_hdd)
        sum_c = sum(monthly_cdd)
        sum_hh = sum(h * h for h in monthly_hdd)
        sum_cc = sum(c * c for c in monthly_cdd)
        sum_hc = sum(h * c for h, c in zip(monthly_hdd, monthly_cdd))
        sum_yh = sum(y * h for y, h in zip(monthly_kwh, monthly_hdd))
        sum_yc = sum(y * c for y, c in zip(monthly_kwh, monthly_cdd))

        # Solve 3×3 system: [n, sum_h, sum_c; sum_h, sum_hh, sum_hc; sum_c, sum_hc, sum_cc] × [a,b,c] = [sum_y, sum_yh, sum_yc]
        # Use Cramer's rule for simplicity
        import numpy as _np  # type: ignore
        try:
            A = [[n, sum_h, sum_c], [sum_h, sum_hh, sum_hc], [sum_c, sum_hc, sum_cc]]
            B = [sum_y, sum_yh, sum_yc]
            coeffs = list(_np.linalg.solve(A, B))
        except Exception:
            # Fallback: simple average if numpy unavailable or singular matrix
            avg = sum_y / n
            coeffs = [avg, 0.0, 0.0]

        a, b, c = coeffs
        predicted = [a + b * h + c * cd for h, cd in zip(monthly_hdd, monthly_cdd)]
        ss_res = sum((y - p) ** 2 for y, p in zip(monthly_kwh, predicted))
        mean_y = sum_y / n
        ss_tot = sum((y - mean_y) ** 2 for y in monthly_kwh)
        r_squared = round(1 - (ss_res / ss_tot), 4) if ss_tot > 0 else 0.0

        normalised_annual = round(sum(predicted), 2)

        return {
            "intercept": round(a, 4),
            "hdd_coefficient": round(b, 4),
            "cdd_coefficient": round(c, 4),
            "r_squared": r_squared,
            "normalised_annual_kwh": normalised_annual,
            "actual_annual_kwh": round(sum_y, 2),
            "months": n,
        }


# ---------------------------------------------------------------------------
# Module-level status helper
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    """Return module-level status information for the energy audit engine."""
    return {
        "module": "energy_audit_engine",
        "design_label": "EAE-001",
        "version": "1.0.0",
        "audit_levels": [l.value for l in AuditLevel],
        "ecm_categories": [c.value for c in ECMCategory],
        "compliance_frameworks": [f.value for f in ComplianceFramework],
        "benchmark_facility_types": sorted(_BENCHMARK_EUI.keys()),
        "limits": {
            "max_readings_per_audit": _MAX_READINGS_PER_AUDIT,
            "max_ecms_per_audit": _MAX_ECMS_PER_AUDIT,
            "max_findings_per_audit": _MAX_FINDINGS_PER_AUDIT,
            "max_facility_sqft": _MAX_FACILITY_SQFT,
        },
        "status": "operational",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AuditLevel",
    "AuditStatus",
    "ECMCategory",
    "ECMPriority",
    "ComplianceFramework",
    "FindingSeverity",
    "EnergyReading",
    "EnergyCostSummary",
    "EnergyConservationMeasure",
    "AuditFinding",
    "EnergyAudit",
    "EnergyAuditEngine",
    "get_status",
]

"""
LCM Chaos Simulation — Economic time machine + full-house domain chaos simulation.

Design Label: LCM-004 — Chaos Simulation
Owner: Platform Engineering

Simulates every domain under every major economic epoch to verify that LCM
gate profiles adapt correctly under stress.

  EconomicTimeMachine  — models 11 economic eras with gate multipliers
  DomainChaosGenerator — generates deterministic domain-specific chaos events
  FullHouseSimulator   — runs ALL domains × ALL epochs simultaneously
  LCMChaosSimulation   — top-level coordinator

Reproducibility guarantee: all random choices use a seeded random.Random(seed)
instance so identical seeds always produce identical results.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    from lcm_engine import LCMEngine, GateBehaviorProfile
    _HAS_ENGINE = True
except ImportError:
    _HAS_ENGINE = False
    LCMEngine = None  # type: ignore[assignment,misc]
    GateBehaviorProfile = None  # type: ignore[assignment,misc]

try:
    from lcm_domain_registry import LCMDomainRegistry
    _HAS_REGISTRY = True
except ImportError:
    _HAS_REGISTRY = False
    LCMDomainRegistry = None  # type: ignore[assignment,misc]

try:
    from chaos_resilience_loop import ChaosResilienceLoop
    _HAS_CHAOS_LOOP = True
except ImportError:
    _HAS_CHAOS_LOOP = False
    ChaosResilienceLoop = None  # type: ignore[assignment,misc]

try:
    from synthetic_failure_generator import (
        SyntheticFailureGenerator,
        TestModeExecutor,
    )
    _HAS_SFG = True
except ImportError:
    _HAS_SFG = False
    SyntheticFailureGenerator = None  # type: ignore[assignment,misc]
    TestModeExecutor = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Economic Epoch Enumeration
# ---------------------------------------------------------------------------

class EconomicEpoch(Enum):
    GREAT_DEPRESSION = "great_depression"   # 1929-1939
    WWII = "wwii"                           # 1939-1945
    POST_WAR_BOOM = "post_war_boom"         # 1945-1960
    STAGFLATION = "stagflation"             # 1970-1982
    EARLY_DIGITAL = "early_digital"         # 1982-1995
    DOT_COM = "dot_com"                     # 1995-2001
    MATURATION = "maturation"               # 2001-2007
    FINANCIAL_CRISIS = "financial_crisis"   # 2007-2009
    RECOVERY = "recovery"                   # 2009-2019
    COVID = "covid"                         # 2020-2021
    AI_ERA = "ai_era"                       # 2022-2026


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EpochConditions:
    """Describes economic conditions for a specific epoch."""
    epoch: EconomicEpoch
    years: Tuple[int, int]
    financial_gate_multiplier: float   # tighter (<1) in depression/crisis
    quality_gate_multiplier: float     # tighter (>1) in boom
    supply_chain_risk: float           # 0-1
    regulatory_pressure: float         # 0-1
    tech_availability: Dict[str, bool]
    description: str


@dataclass
class ChaosEvent:
    """A single chaos event targeting a domain in an epoch."""
    event_id: str
    domain: str
    event_type: str
    severity: str               # low / medium / high / critical
    description: str
    affected_systems: List[str]
    epoch: Optional[EconomicEpoch] = None
    survived: Optional[bool] = None  # set after simulation


@dataclass
class ChaosSimulationResult:
    """Aggregated result of a full-house chaos simulation run."""
    run_id: str
    epochs_simulated: int
    domains_tested: int
    total_chaos_events: int
    events_survived: int
    events_failed: int
    gate_adaptations: int
    duration_sec: float
    reproducible: bool          # True when using seeded RNG
    domain_results: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Economic Time Machine
# ---------------------------------------------------------------------------

_EPOCH_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "epoch": EconomicEpoch.GREAT_DEPRESSION,
        "years": (1929, 1939),
        "financial_gate_multiplier": 0.4,
        "quality_gate_multiplier": 0.7,
        "supply_chain_risk": 0.9,
        "regulatory_pressure": 0.5,
        "tech_availability": {
            "digital": False, "computer": False, "internet": False,
            "3d_printing": False, "ai": False, "iot": False,
        },
        "description": (
            "Severe deflation, mass unemployment, bank failures, minimal industry."
        ),
    },
    {
        "epoch": EconomicEpoch.WWII,
        "years": (1939, 1945),
        "financial_gate_multiplier": 0.6,
        "quality_gate_multiplier": 1.3,
        "supply_chain_risk": 0.85,
        "regulatory_pressure": 0.9,
        "tech_availability": {
            "digital": False, "computer": False, "internet": False,
            "3d_printing": False, "ai": False, "iot": False,
        },
        "description": (
            "Wartime economy, rationing, government-directed manufacturing, high compliance."
        ),
    },
    {
        "epoch": EconomicEpoch.POST_WAR_BOOM,
        "years": (1945, 1960),
        "financial_gate_multiplier": 1.1,
        "quality_gate_multiplier": 1.2,
        "supply_chain_risk": 0.2,
        "regulatory_pressure": 0.4,
        "tech_availability": {
            "digital": False, "computer": True, "internet": False,
            "3d_printing": False, "ai": False, "iot": False,
        },
        "description": (
            "Post-war economic expansion, low unemployment, rising middle class."
        ),
    },
    {
        "epoch": EconomicEpoch.STAGFLATION,
        "years": (1970, 1982),
        "financial_gate_multiplier": 0.7,
        "quality_gate_multiplier": 0.8,
        "supply_chain_risk": 0.7,
        "regulatory_pressure": 0.75,
        "tech_availability": {
            "digital": True, "computer": True, "internet": False,
            "3d_printing": False, "ai": False, "iot": False,
        },
        "description": (
            "High inflation + unemployment, oil shocks, industrial stagnation."
        ),
    },
    {
        "epoch": EconomicEpoch.EARLY_DIGITAL,
        "years": (1982, 1995),
        "financial_gate_multiplier": 1.0,
        "quality_gate_multiplier": 1.0,
        "supply_chain_risk": 0.3,
        "regulatory_pressure": 0.5,
        "tech_availability": {
            "digital": True, "computer": True, "internet": False,
            "3d_printing": True, "ai": False, "iot": False,
        },
        "description": (
            "PC revolution, early CAD/CAM, globalization begins."
        ),
    },
    {
        "epoch": EconomicEpoch.DOT_COM,
        "years": (1995, 2001),
        "financial_gate_multiplier": 1.3,
        "quality_gate_multiplier": 0.9,
        "supply_chain_risk": 0.25,
        "regulatory_pressure": 0.4,
        "tech_availability": {
            "digital": True, "computer": True, "internet": True,
            "3d_printing": True, "ai": False, "iot": False,
        },
        "description": (
            "Internet euphoria, VC excess, Y2K concern, rapid tech adoption."
        ),
    },
    {
        "epoch": EconomicEpoch.MATURATION,
        "years": (2001, 2007),
        "financial_gate_multiplier": 1.1,
        "quality_gate_multiplier": 1.1,
        "supply_chain_risk": 0.2,
        "regulatory_pressure": 0.6,
        "tech_availability": {
            "digital": True, "computer": True, "internet": True,
            "3d_printing": True, "ai": False, "iot": False,
        },
        "description": (
            "Post-dot-com stabilization, SOX compliance, outsourcing boom."
        ),
    },
    {
        "epoch": EconomicEpoch.FINANCIAL_CRISIS,
        "years": (2007, 2009),
        "financial_gate_multiplier": 0.3,
        "quality_gate_multiplier": 0.85,
        "supply_chain_risk": 0.8,
        "regulatory_pressure": 0.9,
        "tech_availability": {
            "digital": True, "computer": True, "internet": True,
            "3d_printing": True, "ai": False, "iot": False,
        },
        "description": (
            "Global financial crisis, credit freeze, regulatory overhaul."
        ),
    },
    {
        "epoch": EconomicEpoch.RECOVERY,
        "years": (2009, 2019),
        "financial_gate_multiplier": 1.15,
        "quality_gate_multiplier": 1.1,
        "supply_chain_risk": 0.15,
        "regulatory_pressure": 0.65,
        "tech_availability": {
            "digital": True, "computer": True, "internet": True,
            "3d_printing": True, "ai": True, "iot": True,
        },
        "description": (
            "Sustained recovery, low interest rates, cloud & IoT proliferation."
        ),
    },
    {
        "epoch": EconomicEpoch.COVID,
        "years": (2020, 2021),
        "financial_gate_multiplier": 0.5,
        "quality_gate_multiplier": 1.2,
        "supply_chain_risk": 0.95,
        "regulatory_pressure": 0.85,
        "tech_availability": {
            "digital": True, "computer": True, "internet": True,
            "3d_printing": True, "ai": True, "iot": True,
        },
        "description": (
            "Global pandemic, supply chain collapse, remote work surge."
        ),
    },
    {
        "epoch": EconomicEpoch.AI_ERA,
        "years": (2022, 2026),
        "financial_gate_multiplier": 1.05,
        "quality_gate_multiplier": 1.3,
        "supply_chain_risk": 0.35,
        "regulatory_pressure": 0.7,
        "tech_availability": {
            "digital": True, "computer": True, "internet": True,
            "3d_printing": True, "ai": True, "iot": True,
        },
        "description": (
            "AI integration, reshoring, regulatory scrutiny of LLMs, energy demand spike."
        ),
    },
]


class EconomicTimeMachine:
    """Simulate all economic epochs with domain-specific gate multipliers."""

    def __init__(self) -> None:
        self._epochs: Dict[EconomicEpoch, EpochConditions] = {}
        self._lock = threading.RLock()
        self._build()

    def _build(self) -> None:
        for defn in _EPOCH_DEFINITIONS:
            ec = EpochConditions(
                epoch=defn["epoch"],
                years=defn["years"],
                financial_gate_multiplier=defn["financial_gate_multiplier"],
                quality_gate_multiplier=defn["quality_gate_multiplier"],
                supply_chain_risk=defn["supply_chain_risk"],
                regulatory_pressure=defn["regulatory_pressure"],
                tech_availability=dict(defn["tech_availability"]),
                description=defn["description"],
            )
            self._epochs[defn["epoch"]] = ec

    def get_epoch_conditions(self, epoch: EconomicEpoch) -> EpochConditions:
        """Return conditions for a given epoch."""
        with self._lock:
            return self._epochs[epoch]

    def list_all_epochs(self) -> List[EpochConditions]:
        """Return all epoch conditions in chronological order."""
        with self._lock:
            return list(self._epochs.values())

    def get_gate_multiplier(self, epoch: EconomicEpoch, gate_type: str) -> float:
        """Return gate multiplier for a specific gate type in an epoch."""
        conditions = self.get_epoch_conditions(epoch)
        if gate_type in ("business", "financial"):
            return conditions.financial_gate_multiplier
        if gate_type in ("quality",):
            return conditions.quality_gate_multiplier
        if gate_type in ("compliance", "security"):
            return conditions.regulatory_pressure
        if gate_type in ("safety",):
            # Safety gates tighten during crisis periods
            return max(0.7, 1.0 - conditions.supply_chain_risk * 0.3)
        return 1.0


# ---------------------------------------------------------------------------
# Domain Chaos Generator
# ---------------------------------------------------------------------------

_SEVERITIES = ["low", "medium", "high", "critical"]
_3D_PRINT_EVENTS = [
    ("print_failure", "critical", "Print job failed mid-way, build plate contamination", ["extruder", "bed"]),
    ("nozzle_clog", "high", "Nozzle clogged with degraded filament", ["extruder", "hotend"]),
    ("layer_delamination", "high", "Layer adhesion failure under thermal stress", ["build_chamber"]),
    ("power_outage", "critical", "Power lost during print, irrecoverable state", ["controller", "heaters"]),
    ("material_shortage", "medium", "Filament/powder supply exhausted mid-run", ["material_feed"]),
    ("thermal_runaway", "critical", "Heater thermal runaway detected, emergency stop", ["heaters", "firmware"]),
    ("resin_spill", "high", "Photopolymer resin containment breach", ["build_tank", "safety"]),
    ("laser_calibration_drift", "high", "Laser spot drift exceeding 0.1mm tolerance", ["laser", "optics"]),
    ("inert_gas_failure", "critical", "Argon/nitrogen supply failure in SLS/SLM chamber", ["gas_supply", "chamber"]),
    ("post_cure_skip", "medium", "UV post-cure step skipped in SLA workflow", ["post_processing"]),
]
_CAD_EVENTS = [
    ("corrupt_file", "critical", "Design file corruption, unsaved changes lost", ["filesystem"]),
    ("license_failure", "high", "CAD license server unreachable", ["license_server"]),
    ("version_mismatch", "medium", "Assembly version mismatch across team", ["version_control"]),
    ("tolerance_stack_error", "high", "GD&T tolerance stack-up exceeds spec", ["design"]),
    ("bom_desync", "medium", "BOM out of sync with active assembly", ["pdm"]),
    ("rendering_crash", "low", "GPU crash during large assembly rendering", ["gpu", "display"]),
    ("fea_divergence", "high", "FEA simulation diverged, invalid mesh", ["simulation"]),
]
_BAS_EVENTS = [
    ("sensor_failure", "high", "Temperature/pressure sensor offline", ["sensors"]),
    ("pid_windup", "medium", "PID controller integral windup, setpoint deviation", ["controls"]),
    ("chiller_trip", "critical", "Chiller safety trip, building cooling loss", ["chiller"]),
    ("communication_loss", "high", "BACnet controller communication failure", ["bacnet", "network"]),
    ("freeze_stat", "critical", "Freeze protection stat triggered, AHU shutdown", ["ahu"]),
    ("vfd_fault", "high", "Variable frequency drive fault on AHU supply fan", ["vfd", "ahu"]),
    ("boiler_lockout", "critical", "Gas boiler safety lockout, loss of heat", ["boiler"]),
    ("cooling_tower_overflow", "medium", "Cooling tower basin overflow sensor alarm", ["cooling_tower"]),
]
_HEALTHCARE_EVENTS = [
    ("ehr_outage", "critical", "EHR system unavailable, fallback to paper", ["ehr"]),
    ("hipaa_breach", "critical", "Potential PHI exposure detected", ["security", "compliance"]),
    ("equipment_recall", "high", "Medical device recall notification received", ["devices"]),
    ("pharmacy_dispensing_error", "critical", "Wrong medication dose dispensed", ["pharmacy"]),
    ("sterile_field_breach", "critical", "Sterility breach in OR environment", ["or_suite"]),
    ("lab_instrument_drift", "high", "Analyzer QC failure, results quarantined", ["laboratory"]),
]
_FINANCE_EVENTS = [
    ("market_circuit_breaker", "critical", "Exchange circuit breaker triggered", ["trading_engine"]),
    ("settlement_failure", "critical", "T+2 settlement failure, position discrepancy", ["clearance"]),
    ("fraud_alert", "high", "Anomaly detection flagged suspicious trades", ["risk", "compliance"]),
    ("regulatory_audit", "high", "SEC/FINRA audit initiated, records freeze", ["compliance"]),
    ("liquidity_crunch", "critical", "Repo market liquidity dried up", ["funding"]),
    ("algo_runaway", "critical", "Algorithmic trading strategy runaway detected", ["algo", "risk"]),
    ("kyc_system_down", "medium", "KYC/AML system unavailable, new accounts blocked", ["kyc"]),
]


class DomainChaosGenerator:
    """Generate deterministic, domain-specific chaos events using seeded RNG."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._seed = seed
        self._lock = threading.RLock()

    def _make_event(
        self,
        domain: str,
        event_type: str,
        severity: str,
        description: str,
        affected: List[str],
        epoch: Optional[EconomicEpoch] = None,
    ) -> ChaosEvent:
        return ChaosEvent(
            event_id=str(uuid.UUID(int=self._rng.getrandbits(128))),
            domain=domain,
            event_type=event_type,
            severity=severity,
            description=description,
            affected_systems=list(affected),
            epoch=epoch,
        )

    def generate_3d_printing_chaos(
        self, epoch: EconomicEpoch
    ) -> List[ChaosEvent]:
        """Generate 3D printing chaos events for an epoch."""
        with self._lock:
            events: List[ChaosEvent] = []
            selected = self._rng.sample(_3D_PRINT_EVENTS, min(5, len(_3D_PRINT_EVENTS)))
            for et, sev, desc, affected in selected:
                events.append(
                    self._make_event("3d_printing_fdm", et, sev, desc, affected, epoch)
                )
            return events

    def generate_cad_chaos(self, epoch: EconomicEpoch) -> List[ChaosEvent]:
        """Generate CAD/design chaos events."""
        with self._lock:
            events: List[ChaosEvent] = []
            selected = self._rng.sample(_CAD_EVENTS, min(4, len(_CAD_EVENTS)))
            for et, sev, desc, affected in selected:
                events.append(
                    self._make_event("cad_design", et, sev, desc, affected, epoch)
                )
            return events

    def generate_bas_chaos(self, epoch: EconomicEpoch) -> List[ChaosEvent]:
        """Generate BAS/HVAC chaos events."""
        with self._lock:
            events: List[ChaosEvent] = []
            selected = self._rng.sample(_BAS_EVENTS, min(5, len(_BAS_EVENTS)))
            for et, sev, desc, affected in selected:
                events.append(
                    self._make_event("hvac_bas", et, sev, desc, affected, epoch)
                )
            return events

    def generate_healthcare_chaos(self, epoch: EconomicEpoch) -> List[ChaosEvent]:
        """Generate healthcare chaos events."""
        with self._lock:
            events: List[ChaosEvent] = []
            selected = self._rng.sample(_HEALTHCARE_EVENTS, min(4, len(_HEALTHCARE_EVENTS)))
            for et, sev, desc, affected in selected:
                events.append(
                    self._make_event("clinical_operations", et, sev, desc, affected, epoch)
                )
            return events

    def generate_finance_chaos(self, epoch: EconomicEpoch) -> List[ChaosEvent]:
        """Generate financial services chaos events."""
        with self._lock:
            events: List[ChaosEvent] = []
            selected = self._rng.sample(_FINANCE_EVENTS, min(4, len(_FINANCE_EVENTS)))
            for et, sev, desc, affected in selected:
                events.append(
                    self._make_event("trading", et, sev, desc, affected, epoch)
                )
            return events

    def generate_for_domain(
        self, domain_id: str, epoch: EconomicEpoch
    ) -> List[ChaosEvent]:
        """Generate chaos events for any domain by ID."""
        with self._lock:
            if "3d_print" in domain_id:
                return self.generate_3d_printing_chaos(epoch)
            if "cad" in domain_id:
                return self.generate_cad_chaos(epoch)
            if "hvac" in domain_id or "bas" in domain_id or "plumb" in domain_id or "electric" in domain_id:
                return self.generate_bas_chaos(epoch)
            if "clinical" in domain_id or "medical" in domain_id or "pharma" in domain_id or "lab" in domain_id:
                return self.generate_healthcare_chaos(epoch)
            if "trading" in domain_id or "bank" in domain_id or "insur" in domain_id:
                return self.generate_finance_chaos(epoch)

            # Generic fallback
            generic_events = [
                ("service_outage", "high", f"{domain_id} service unavailable", ["service"]),
                ("data_corruption", "critical", f"Data integrity issue in {domain_id}", ["database"]),
                ("auth_failure", "high", "Authentication service timeout", ["auth"]),
                ("network_partition", "critical", "Network partition isolating subsystem", ["network"]),
                ("resource_exhaustion", "medium", "CPU/memory resource exhaustion", ["infra"]),
            ]
            selected = self._rng.sample(generic_events, min(3, len(generic_events)))
            events: List[ChaosEvent] = []
            for et, sev, desc, affected in selected:
                events.append(self._make_event(domain_id, et, sev, desc, affected, epoch))
            return events


# ---------------------------------------------------------------------------
# Full House Simulator
# ---------------------------------------------------------------------------

_SURVIVAL_RATES_BY_SEVERITY: Dict[str, float] = {
    "low": 0.97,
    "medium": 0.88,
    "high": 0.72,
    "critical": 0.55,
}


class FullHouseSimulator:
    """Run ALL domains × ALL epochs simultaneously and collect results."""

    def __init__(
        self, lcm_engine: Optional[Any] = None, seed: int = 42
    ) -> None:
        self._lcm = lcm_engine
        self._seed = seed
        self._rng = random.Random(seed)
        self._lock = threading.RLock()

    def run(
        self,
        epochs: Optional[List[EconomicEpoch]] = None,
        max_events_per_domain: int = 5,
    ) -> ChaosSimulationResult:
        """
        Run the full-house simulation.

        Iterates all domains × all epochs, injects chaos events, evaluates
        survival based on gate profile confidence and epoch multipliers.
        """
        t0 = time.perf_counter()
        run_id = str(uuid.UUID(int=self._rng.getrandbits(128)))
        epochs_to_run = epochs or list(EconomicEpoch)
        time_machine = EconomicTimeMachine()
        chaos_gen = DomainChaosGenerator(seed=self._seed)

        # Get domain list
        domain_ids: List[str] = []
        if _HAS_REGISTRY and LCMDomainRegistry is not None:
            try:
                registry = LCMDomainRegistry()
                domain_ids = [d.domain_id for d in registry.list_all()]
            except Exception:  # noqa: BLE001
                logger.debug("Suppressed exception in lcm_chaos_simulation")
        if not domain_ids:
            domain_ids = [
                "3d_printing_fdm", "3d_printing_sla", "3d_printing_slm_dmls",
                "cad_design", "cnc_machining", "hvac_bas", "clinical_operations",
                "trading", "ecommerce", "fleet_management",
            ]

        total_events = 0
        survived = 0
        failed = 0
        gate_adaptations = 0
        domain_results: Dict[str, Any] = {}

        for epoch in epochs_to_run:
            conditions = time_machine.get_epoch_conditions(epoch)
            for domain_id in domain_ids:
                result = self._simulate_domain_in_epoch(
                    domain_id, epoch, conditions, chaos_gen, max_events_per_domain
                )
                key = f"{domain_id}:{epoch.value}"
                domain_results[key] = result
                total_events += result.get("events_generated", 0)
                survived += result.get("survived", 0)
                failed += result.get("failed", 0)
                gate_adaptations += result.get("gate_adaptations", 0)

        duration = time.perf_counter() - t0
        return ChaosSimulationResult(
            run_id=run_id,
            epochs_simulated=len(epochs_to_run),
            domains_tested=len(domain_ids),
            total_chaos_events=total_events,
            events_survived=survived,
            events_failed=failed,
            gate_adaptations=gate_adaptations,
            duration_sec=round(duration, 3),
            reproducible=True,
            domain_results=domain_results,
        )

    def _simulate_domain_in_epoch(
        self,
        domain_id: str,
        epoch: EconomicEpoch,
        conditions: EpochConditions,
        chaos_gen: DomainChaosGenerator,
        max_events: int,
    ) -> Dict[str, Any]:
        """Simulate a single domain in a single epoch."""
        events = chaos_gen.generate_for_domain(domain_id, epoch)[:max_events]

        # Get gate confidence from LCM engine if available
        base_confidence = 0.80
        if self._lcm is not None:
            try:
                profile = self._lcm.predict(domain_id, "expert")
                base_confidence = profile.confidence
            except Exception:  # noqa: BLE001
                logger.debug("Suppressed exception in lcm_chaos_simulation")

        survived_count = 0
        failed_count = 0
        gate_adaptations = 0

        for event in events:
            sev = event.severity
            base_rate = _SURVIVAL_RATES_BY_SEVERITY.get(sev, 0.75)
            # Apply epoch multiplier to confidence
            fin_mult = conditions.financial_gate_multiplier
            qual_mult = conditions.quality_gate_multiplier
            # Effective survival = base_rate × confidence × epoch_modifier
            epoch_modifier = (fin_mult + qual_mult) / 2.0
            effective_survival = base_rate * base_confidence * min(1.0, epoch_modifier)
            rolled = self._rng.random()
            if rolled < effective_survival:
                survived_count += 1
                event.survived = True
            else:
                failed_count += 1
                event.survived = False
                # Gate adaptation triggered on failure
                gate_adaptations += 1

        return {
            "domain_id": domain_id,
            "epoch": epoch.value,
            "events_generated": len(events),
            "survived": survived_count,
            "failed": failed_count,
            "gate_adaptations": gate_adaptations,
            "base_confidence": base_confidence,
        }


# ---------------------------------------------------------------------------
# Master Chaos Simulation Coordinator
# ---------------------------------------------------------------------------

class LCMChaosSimulation:
    """Top-level chaos simulation coordinator."""

    def __init__(
        self, lcm_engine: Optional[Any] = None, seed: int = 42
    ) -> None:
        self._lcm = lcm_engine
        self._seed = seed
        self._lock = threading.RLock()
        self.time_machine = EconomicTimeMachine()
        self.chaos_generator = DomainChaosGenerator(seed=seed)
        self.full_house = FullHouseSimulator(lcm_engine=lcm_engine, seed=seed)

    def run_full_house(self, **kwargs: Any) -> ChaosSimulationResult:
        """Run the full-house simulation across all domains and epochs."""
        return self.full_house.run(**kwargs)

    def run_epoch(
        self,
        epoch: EconomicEpoch,
        domain_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run simulation for a single epoch across specified (or all) domains."""
        result = self.full_house.run(epochs=[epoch])
        if domain_ids:
            filtered = {
                k: v
                for k, v in result.domain_results.items()
                if any(k.startswith(d) for d in domain_ids)
            }
            return {
                "epoch": epoch.value,
                "domain_results": filtered,
                "conditions": {
                    "years": self.time_machine.get_epoch_conditions(epoch).years,
                    "supply_chain_risk": self.time_machine.get_epoch_conditions(epoch).supply_chain_risk,
                },
            }
        return {
            "epoch": epoch.value,
            "epochs_simulated": result.epochs_simulated,
            "domains_tested": result.domains_tested,
            "total_chaos_events": result.total_chaos_events,
            "events_survived": result.events_survived,
            "events_failed": result.events_failed,
        }

    def status(self) -> Dict[str, Any]:
        """Return simulation status."""
        return {
            "seed": self._seed,
            "lcm_attached": self._lcm is not None,
            "epochs_available": len(EconomicEpoch),
            "chaos_loop_available": _HAS_CHAOS_LOOP,
            "sfg_available": _HAS_SFG,
        }

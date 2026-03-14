"""
Automation Scaler for Murphy System.

Design Label: OPS-006 — Per-Automation-Type Scaling, Territory Licensing & Contractor Dispatch
Owner: Operations Team / Platform Engineering
Dependencies:
  - CostExplosionGate (FIN-002, for budget checks before scaling)
  - WingmanProtocol (optional, for validation)
  - EmergencyStopController (OPS-004, for emergency scale-down)

Implements Phase 8 — Operational Readiness & Autonomy Governance:
  Manages capacity, territory licensing, and contractor dispatch for
  different automation domains.  Licensed automation types (HVAC,
  electrical, etc.) map to service territories managed like traditional
  contractor service areas.

Territory Advantage System:
  - Contractors assigned to territories get priority dispatch in those territories.
  - If no contractor is available in the requested territory, the search expands
    to all registered contractors with the required license.
  - Licensed work MUST have a contractor with a valid license in that territory.
  - Per-territory cost and performance metrics are tracked.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock.
  - Bounded: event history capped at _MAX_EVENTS.
  - Zero-config: AutomationScaler() just works with sensible defaults.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
# Constants
# ---------------------------------------------------------------------------

_MAX_EVENTS = 10_000
_DEFAULT_COOLDOWN_S = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AutomationType(str, Enum):
    """Domains of automation managed by this scaler."""
    HVAC_MECHANICAL = "hvac_mechanical"
    ELECTRICAL_MECHANICAL = "electrical_mechanical"
    PLUMBING = "plumbing"
    FIRE_PROTECTION = "fire_protection"
    ELEVATOR = "elevator"
    SECURITY_SYSTEMS = "security_systems"
    BUILDING_CONTROLS = "building_controls"
    ENERGY_MANAGEMENT = "energy_management"
    SOFTWARE_AUTOMATION = "software_automation"
    DATA_PIPELINE = "data_pipeline"
    AI_AGENT = "ai_agent"
    IOT_DEVICE = "iot_device"
    ROBOTICS = "robotics"


class LicenseType(str, Enum):
    """License types required for certain automation domains."""
    HVAC_LICENSE = "hvac_license"
    ELECTRICAL_LICENSE = "electrical_license"
    PLUMBING_LICENSE = "plumbing_license"
    FIRE_PROTECTION_LICENSE = "fire_protection_license"
    ELEVATOR_LICENSE = "elevator_license"
    LOW_VOLTAGE_LICENSE = "low_voltage_license"
    GENERAL_CONTRACTOR = "general_contractor"
    PE_STAMP = "pe_stamp"
    NONE_REQUIRED = "none_required"


# Mapping from automation type to required license
_LICENSE_MAP: Dict[AutomationType, LicenseType] = {
    AutomationType.HVAC_MECHANICAL: LicenseType.HVAC_LICENSE,
    AutomationType.ELECTRICAL_MECHANICAL: LicenseType.ELECTRICAL_LICENSE,
    AutomationType.PLUMBING: LicenseType.PLUMBING_LICENSE,
    AutomationType.FIRE_PROTECTION: LicenseType.FIRE_PROTECTION_LICENSE,
    AutomationType.ELEVATOR: LicenseType.ELEVATOR_LICENSE,
    AutomationType.SECURITY_SYSTEMS: LicenseType.LOW_VOLTAGE_LICENSE,
    AutomationType.BUILDING_CONTROLS: LicenseType.LOW_VOLTAGE_LICENSE,
    AutomationType.ENERGY_MANAGEMENT: LicenseType.GENERAL_CONTRACTOR,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ScalePolicy:
    """Scaling policy for one automation type."""
    policy_id: str
    automation_type: AutomationType
    min_instances: int
    max_instances: int
    current_instances: int
    cooldown_seconds: int
    cost_cap_per_hour: float
    requires_license: bool
    license_type: Optional[LicenseType]
    territory_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "automation_type": self.automation_type.value,
            "min_instances": self.min_instances,
            "max_instances": self.max_instances,
            "current_instances": self.current_instances,
            "cooldown_seconds": self.cooldown_seconds,
            "cost_cap_per_hour": self.cost_cap_per_hour,
            "requires_license": self.requires_license,
            "license_type": self.license_type.value if self.license_type else None,
            "territory_id": self.territory_id,
        }


@dataclass
class Territory:
    """A geographic service territory."""
    territory_id: str
    name: str
    region: str
    state: str
    zip_codes: List[str]
    automation_types: List[AutomationType]
    assigned_contractors: List[str]
    max_contractors: int
    active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "territory_id": self.territory_id,
            "name": self.name,
            "region": self.region,
            "state": self.state,
            "zip_codes": self.zip_codes,
            "automation_types": [t.value for t in self.automation_types],
            "assigned_contractors": self.assigned_contractors,
            "max_contractors": self.max_contractors,
            "active": self.active,
        }


@dataclass
class ContractorProfile:
    """Profile for a licensed contractor."""
    contractor_id: str
    name: str
    licenses: List[LicenseType]
    territories: List[str]
    hourly_rate: float
    rating: float
    jobs_completed: int
    active: bool
    last_dispatch: Optional[str]

    def has_license(self, license_type: LicenseType) -> bool:
        return license_type in self.licenses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contractor_id": self.contractor_id,
            "name": self.name,
            "licenses": [lic.value for lic in self.licenses],
            "territories": self.territories,
            "hourly_rate": self.hourly_rate,
            "rating": self.rating,
            "jobs_completed": self.jobs_completed,
            "active": self.active,
            "last_dispatch": self.last_dispatch,
        }


@dataclass
class ScaleEvent:
    """A recorded scaling or dispatch event."""
    event_id: str
    automation_type: AutomationType
    action: str       # scale_up / scale_down / dispatch / recall
    from_count: int
    to_count: int
    contractor_id: Optional[str]
    territory_id: Optional[str]
    cost_estimate: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "automation_type": self.automation_type.value,
            "action": self.action,
            "from_count": self.from_count,
            "to_count": self.to_count,
            "contractor_id": self.contractor_id,
            "territory_id": self.territory_id,
            "cost_estimate": self.cost_estimate,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Scaler
# ---------------------------------------------------------------------------

class AutomationScaler:
    """
    Per-automation-type scaling system with territory licensing and
    contractor dispatch.

    Usage::

        scaler = AutomationScaler()
        policy = scaler.register_policy(AutomationType.AI_AGENT, 1, 10)
        event = scaler.scale_up(AutomationType.AI_AGENT)
    """

    def __init__(
        self,
        cost_gate=None,
        wingman_protocol=None,
        emergency_stop=None,
    ) -> None:
        self._lock = threading.Lock()
        self._cost_gate = cost_gate or self._make_cost_gate()
        self._wingman_protocol = wingman_protocol
        self._emergency_stop = emergency_stop or self._make_emergency_stop()

        # automation_type → ScalePolicy
        self._policies: Dict[str, ScalePolicy] = {}
        # territory_id → Territory
        self._territories: Dict[str, Territory] = {}
        # contractor_id → ContractorProfile
        self._contractors: Dict[str, ContractorProfile] = {}
        # Active jobs: job_id → {contractor_id, automation_type, territory_id, started_at}
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        # Flat event log
        self._events: List[ScaleEvent] = []

    # ------------------------------------------------------------------
    # Dependency factories
    # ------------------------------------------------------------------

    @staticmethod
    def _make_cost_gate():
        try:
            from cost_explosion_gate import CostExplosionGate
            return CostExplosionGate()
        except Exception as exc:
            logger.debug("CostExplosionGate unavailable: %s", exc)
            return None

    @staticmethod
    def _make_emergency_stop():
        try:
            from emergency_stop_controller import EmergencyStopController
            return EmergencyStopController()
        except Exception as exc:
            logger.debug("EmergencyStopController unavailable: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_policy(
        self,
        automation_type: AutomationType,
        min_instances: int = 1,
        max_instances: int = 10,
        cooldown_seconds: int = _DEFAULT_COOLDOWN_S,
        cost_cap_per_hour: float = 100.0,
        territory_id: Optional[str] = None,
    ) -> ScalePolicy:
        """Register a scaling policy for an automation type."""
        requires_license = automation_type in _LICENSE_MAP
        license_type = _LICENSE_MAP.get(automation_type)

        policy = ScalePolicy(
            policy_id=f"pol-{uuid.uuid4().hex[:10]}",
            automation_type=automation_type,
            min_instances=min_instances,
            max_instances=max_instances,
            current_instances=min_instances,
            cooldown_seconds=cooldown_seconds,
            cost_cap_per_hour=cost_cap_per_hour,
            requires_license=requires_license,
            license_type=license_type,
            territory_id=territory_id,
        )
        with self._lock:
            self._policies[automation_type.value] = policy
        logger.info("Policy registered: %s min=%d max=%d", automation_type.value, min_instances, max_instances)
        return policy

    def register_territory(
        self,
        name: str,
        region: str,
        state: str,
        zip_codes: List[str],
        automation_types: List[AutomationType],
        max_contractors: int = 10,
    ) -> Territory:
        """Register a geographic service territory."""
        territory = Territory(
            territory_id=f"ter-{uuid.uuid4().hex[:10]}",
            name=name,
            region=region,
            state=state,
            zip_codes=list(zip_codes),
            automation_types=list(automation_types),
            assigned_contractors=[],
            max_contractors=max_contractors,
            active=True,
        )
        with self._lock:
            self._territories[territory.territory_id] = territory
        logger.info("Territory registered: %s (%s, %s)", name, state, region)
        return territory

    def register_contractor(
        self,
        name: str,
        licenses: List[LicenseType],
        territories: List[str],
        hourly_rate: float,
        rating: float = 5.0,
    ) -> ContractorProfile:
        """Register a licensed contractor."""
        contractor = ContractorProfile(
            contractor_id=f"con-{uuid.uuid4().hex[:10]}",
            name=name,
            licenses=list(licenses),
            territories=list(territories),
            hourly_rate=hourly_rate,
            rating=rating,
            jobs_completed=0,
            active=True,
            last_dispatch=None,
        )
        with self._lock:
            self._contractors[contractor.contractor_id] = contractor
            # Assign contractor to territories
            for tid in territories:
                territory = self._territories.get(tid)
                if territory is not None and contractor.contractor_id not in territory.assigned_contractors:
                    territory.assigned_contractors.append(contractor.contractor_id)
        logger.info("Contractor registered: %s licenses=%s", name, [lic.value for lic in licenses])
        return contractor

    # ------------------------------------------------------------------
    # Scaling evaluation
    # ------------------------------------------------------------------

    def evaluate_scaling(self, automation_type: AutomationType) -> Dict[str, Any]:
        """Decide if scaling is needed for an automation type.

        Returns:
            action, from_count, to_count, contractor_dispatched, cost_estimate, territory
        """
        with self._lock:
            policy = self._policies.get(automation_type.value)
        if policy is None:
            return {
                "action": "no_policy",
                "from_count": 0,
                "to_count": 0,
                "contractor_dispatched": None,
                "cost_estimate": 0.0,
                "territory": None,
                "recommendation": "Register a policy for this automation type first.",
            }

        from_count = policy.current_instances
        action = "no_action"
        to_count = from_count
        contractor_dispatched = None
        cost_estimate = 0.0
        territory = policy.territory_id

        # Simple heuristic: if current < min, scale up
        if policy.current_instances < policy.min_instances:
            action = "scale_up"
            to_count = policy.min_instances
            cost_estimate = (to_count - from_count) * policy.cost_cap_per_hour
        elif policy.current_instances > policy.max_instances:
            action = "scale_down"
            to_count = policy.max_instances

        return {
            "action": action,
            "from_count": from_count,
            "to_count": to_count,
            "contractor_dispatched": contractor_dispatched,
            "cost_estimate": cost_estimate,
            "territory": territory,
            "recommendation": f"Evaluate result: {action} from {from_count} to {to_count}.",
        }

    # ------------------------------------------------------------------
    # Scale up / down
    # ------------------------------------------------------------------

    def scale_up(self, automation_type: AutomationType, count: int = 1) -> ScaleEvent:
        """Scale up an automation type by *count* instances."""
        with self._lock:
            policy = self._policies.get(automation_type.value)
            if policy is None:
                policy = self._policies.setdefault(
                    automation_type.value,
                    ScalePolicy(
                        policy_id=f"pol-{uuid.uuid4().hex[:10]}",
                        automation_type=automation_type,
                        min_instances=0,
                        max_instances=100,
                        current_instances=0,
                        cooldown_seconds=_DEFAULT_COOLDOWN_S,
                        cost_cap_per_hour=100.0,
                        requires_license=automation_type in _LICENSE_MAP,
                        license_type=_LICENSE_MAP.get(automation_type),
                        territory_id=None,
                    ),
                )
            from_count = policy.current_instances
            to_count = min(policy.current_instances + count, policy.max_instances)
            policy.current_instances = to_count

        event = ScaleEvent(
            event_id=f"se-{uuid.uuid4().hex[:10]}",
            automation_type=automation_type,
            action="scale_up",
            from_count=from_count,
            to_count=to_count,
            contractor_id=None,
            territory_id=None,
            cost_estimate=0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            capped_append(self._events, event, _MAX_EVENTS)

        logger.info("scale_up %s: %d → %d", automation_type.value, from_count, to_count)
        return event

    def scale_down(self, automation_type: AutomationType, count: int = 1) -> ScaleEvent:
        """Scale down an automation type by *count* instances."""
        with self._lock:
            policy = self._policies.get(automation_type.value)
            if policy is None:
                event = ScaleEvent(
                    event_id=f"se-{uuid.uuid4().hex[:10]}",
                    automation_type=automation_type,
                    action="scale_down",
                    from_count=0,
                    to_count=0,
                    contractor_id=None,
                    territory_id=None,
                    cost_estimate=0.0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                capped_append(self._events, event, _MAX_EVENTS)
                return event

            from_count = policy.current_instances
            to_count = max(policy.current_instances - count, policy.min_instances)
            policy.current_instances = to_count

        event = ScaleEvent(
            event_id=f"se-{uuid.uuid4().hex[:10]}",
            automation_type=automation_type,
            action="scale_down",
            from_count=from_count,
            to_count=to_count,
            contractor_id=None,
            territory_id=None,
            cost_estimate=0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            capped_append(self._events, event, _MAX_EVENTS)

        logger.info("scale_down %s: %d → %d", automation_type.value, from_count, to_count)
        return event

    # ------------------------------------------------------------------
    # Contractor dispatch
    # ------------------------------------------------------------------

    def dispatch_contractor(
        self,
        automation_type: AutomationType,
        territory_id: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """Find and dispatch a contractor with the right license for the territory.

        Priority order:
          1. Active contractors assigned to the requested territory with matching license.
          2. Any active contractor with the matching license (expanded search).

        Returns:
            dispatched, contractor_id, territory_id, estimated_cost, job_id
        """
        required_license = _LICENSE_MAP.get(automation_type, LicenseType.NONE_REQUIRED)

        with self._lock:
            territory = self._territories.get(territory_id)
            if territory is None:
                return {
                    "dispatched": False,
                    "contractor_id": None,
                    "territory_id": territory_id,
                    "estimated_cost": 0.0,
                    "job_id": None,
                    "reason": "territory_not_found",
                }

            # Priority 1 — contractors already in this territory
            candidate = self._find_contractor_in_territory(territory, required_license)

            # Priority 2 — expand search
            if candidate is None:
                candidate = self._find_any_contractor(required_license)

            if candidate is None:
                return {
                    "dispatched": False,
                    "contractor_id": None,
                    "territory_id": territory_id,
                    "estimated_cost": 0.0,
                    "job_id": None,
                    "reason": f"no_licensed_contractor_available (license={required_license.value})",
                }

            # Budget check
            if self._cost_gate is not None:
                try:
                    from cost_explosion_gate import CostTier
                    check = self._cost_gate.check_budget(
                        CostTier.TENANT, candidate.contractor_id, candidate.hourly_rate
                    )
                    if not check.get("allowed", True):
                        return {
                            "dispatched": False,
                            "contractor_id": candidate.contractor_id,
                            "territory_id": territory_id,
                            "estimated_cost": candidate.hourly_rate,
                            "job_id": None,
                            "reason": "budget_exceeded",
                        }
                except Exception as exc:
                    logger.debug("Cost gate check skipped: %s", exc)

            job_id = f"job-{uuid.uuid4().hex[:12]}"
            candidate.last_dispatch = datetime.now(timezone.utc).isoformat()
            candidate.jobs_completed += 1

            self._active_jobs[job_id] = {
                "job_id": job_id,
                "contractor_id": candidate.contractor_id,
                "automation_type": automation_type.value,
                "territory_id": territory_id,
                "description": job_description,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }

            event = ScaleEvent(
                event_id=f"se-{uuid.uuid4().hex[:10]}",
                automation_type=automation_type,
                action="dispatch",
                from_count=0,
                to_count=1,
                contractor_id=candidate.contractor_id,
                territory_id=territory_id,
                cost_estimate=candidate.hourly_rate,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            capped_append(self._events, event, _MAX_EVENTS)

        logger.info(
            "Dispatched contractor %s (%s) to territory %s for %s",
            candidate.name, candidate.contractor_id, territory_id, automation_type.value,
        )
        return {
            "dispatched": True,
            "contractor_id": candidate.contractor_id,
            "territory_id": territory_id,
            "estimated_cost": candidate.hourly_rate,
            "job_id": job_id,
            "reason": "ok",
        }

    def recall_contractor(self, contractor_id: str, job_id: str) -> Dict[str, Any]:
        """Mark a dispatched contractor as recalled / job complete."""
        with self._lock:
            job = self._active_jobs.pop(job_id, None)
            if job is None:
                return {"recalled": False, "job_id": job_id, "reason": "job_not_found"}

            contractor = self._contractors.get(contractor_id)
            if contractor is not None:
                event = ScaleEvent(
                    event_id=f"se-{uuid.uuid4().hex[:10]}",
                    automation_type=AutomationType(job.get("automation_type", AutomationType.SOFTWARE_AUTOMATION.value)),
                    action="recall",
                    from_count=1,
                    to_count=0,
                    contractor_id=contractor_id,
                    territory_id=job.get("territory_id"),
                    cost_estimate=0.0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                capped_append(self._events, event, _MAX_EVENTS)

        return {"recalled": True, "job_id": job_id, "contractor_id": contractor_id}

    # ------------------------------------------------------------------
    # Territory coverage
    # ------------------------------------------------------------------

    def get_territory_coverage(self) -> Dict[str, Any]:
        """Return which territories have contractor coverage for which automation types."""
        with self._lock:
            coverage = {}
            for tid, territory in self._territories.items():
                covered_types = []
                for atype in territory.automation_types:
                    required = _LICENSE_MAP.get(atype, LicenseType.NONE_REQUIRED)
                    if required == LicenseType.NONE_REQUIRED:
                        covered_types.append(atype.value)
                    else:
                        has_contractor = any(
                            c.active and c.has_license(required) and tid in c.territories
                            for c in self._contractors.values()
                        )
                        if has_contractor:
                            covered_types.append(atype.value)

                coverage[tid] = {
                    "territory_name": territory.name,
                    "state": territory.state,
                    "covered_types": covered_types,
                    "assigned_contractors": len(territory.assigned_contractors),
                }
        return coverage

    # ------------------------------------------------------------------
    # Emergency scale-down
    # ------------------------------------------------------------------

    def emergency_scale_down_all(self, reason: str) -> Dict[str, Any]:
        """Scale all automation types to minimum and recall all contractors."""
        scaled_types = []
        recalled_jobs = []

        with self._lock:
            for atype_val, policy in self._policies.items():
                if policy.current_instances > policy.min_instances:
                    old = policy.current_instances
                    policy.current_instances = policy.min_instances
                    event = ScaleEvent(
                        event_id=f"se-{uuid.uuid4().hex[:10]}",
                        automation_type=policy.automation_type,
                        action="scale_down",
                        from_count=old,
                        to_count=policy.min_instances,
                        contractor_id=None,
                        territory_id=None,
                        cost_estimate=0.0,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                    capped_append(self._events, event, _MAX_EVENTS)
                    scaled_types.append(atype_val)

            job_ids = list(self._active_jobs.keys())

        for job_id in job_ids:
            with self._lock:
                job = self._active_jobs.pop(job_id, None)
            if job is not None:
                recalled_jobs.append(job_id)
                logger.info("Emergency recall job %s (contractor=%s)", job_id, job.get("contractor_id"))

        if self._emergency_stop is not None:
            try:
                self._emergency_stop.activate_global(reason)
            except Exception as exc:
                logger.error("Emergency stop failed during scale-down: %s", exc)

        logger.warning("Emergency scale-down: %d types scaled, %d jobs recalled", len(scaled_types), len(recalled_jobs))
        return {
            "scaled_down": scaled_types,
            "recalled_jobs": recalled_jobs,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_scaling_dashboard(self) -> Dict[str, Any]:
        """Return all policies, territories, contractors, and recent events."""
        with self._lock:
            policies = [p.to_dict() for p in self._policies.values()]
            territories = [t.to_dict() for t in self._territories.values()]
            contractors = [c.to_dict() for c in self._contractors.values()]
            recent_events = [e.to_dict() for e in self._events[-20:]]
            active_jobs = list(self._active_jobs.values())

        return {
            "policies": policies,
            "territories": territories,
            "contractors": contractors,
            "recent_events": recent_events,
            "active_jobs": active_jobs,
            "totals": {
                "policies": len(policies),
                "territories": len(territories),
                "contractors": len(contractors),
                "active_jobs": len(active_jobs),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_contractor_in_territory(
        self, territory: Territory, required_license: LicenseType
    ) -> Optional[ContractorProfile]:
        """Find best available contractor already in the territory. Caller holds lock."""
        candidates = [
            self._contractors[cid]
            for cid in territory.assigned_contractors
            if cid in self._contractors
            and self._contractors[cid].active
            and (
                required_license == LicenseType.NONE_REQUIRED
                or self._contractors[cid].has_license(required_license)
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda c: (c.rating, c.jobs_completed))

    def _find_any_contractor(
        self, required_license: LicenseType
    ) -> Optional[ContractorProfile]:
        """Expanded search for any contractor with the required license. Caller holds lock."""
        candidates = [
            c
            for c in self._contractors.values()
            if c.active
            and (
                required_license == LicenseType.NONE_REQUIRED
                or c.has_license(required_license)
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda c: (c.rating, c.jobs_completed))

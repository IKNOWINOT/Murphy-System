"""
Rosetta Stone Heartbeat Synchronization Module — Murphy System

Provides organization-wide state propagation modelled as a rhythmic
heartbeat that originates from the executive branch and cascades through
every organizational tier.  Each beat carries a *pulse* — a normalised
state snapshot that every subsystem can translate into its own domain
language (hence "Rosetta Stone").

Key concepts:
  - **Pulse**: A timestamped state envelope with executive directives,
    health metrics, and configuration deltas.
  - **Heartbeat**: A periodic emission cycle that propagates pulses
    from the executive tier downward through the org hierarchy.
  - **Tier**: An organizational level (EXECUTIVE → MANAGEMENT →
    OPERATIONS → WORKER → INTEGRATION).
  - **Translator**: A per-tier adapter that converts the universal
    pulse schema into the tier's native operational language.
  - **Sync check**: Verification that all tiers received and
    acknowledged the latest pulse within the tolerance window.

All operations are thread-safe and designed for continuous background
execution in the Murphy runtime.
"""

import enum
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

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
# Enums
# ---------------------------------------------------------------------------

class OrganizationTier(enum.Enum):
    """Organization tier (Enum subclass)."""
    EXECUTIVE = "executive"
    MANAGEMENT = "management"
    OPERATIONS = "operations"
    WORKER = "worker"
    INTEGRATION = "integration"


class PulseStatus(enum.Enum):
    """Pulse status (Enum subclass)."""
    EMITTED = "emitted"
    PROPAGATING = "propagating"
    ACKNOWLEDGED = "acknowledged"
    STALE = "stale"
    FAILED = "failed"


class HeartbeatState(enum.Enum):
    """Heartbeat state (Enum subclass)."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


# Canonical tier propagation order (executive first)
TIER_ORDER: List[OrganizationTier] = [
    OrganizationTier.EXECUTIVE,
    OrganizationTier.MANAGEMENT,
    OrganizationTier.OPERATIONS,
    OrganizationTier.WORKER,
    OrganizationTier.INTEGRATION,
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Pulse:
    """A single heartbeat pulse carrying organizational state."""
    pulse_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    sequence: int = 0
    origin_tier: OrganizationTier = OrganizationTier.EXECUTIVE
    directives: Dict[str, Any] = field(default_factory=dict)
    health_metrics: Dict[str, Any] = field(default_factory=dict)
    config_deltas: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pulse_id": self.pulse_id,
            "sequence": self.sequence,
            "origin_tier": self.origin_tier.value,
            "directives": self.directives,
            "health_metrics": self.health_metrics,
            "config_deltas": self.config_deltas,
            "metadata": self.metadata,
            "emitted_at": self.emitted_at,
        }


@dataclass
class TierState:
    """Tracks per-tier heartbeat reception state."""
    tier: OrganizationTier = OrganizationTier.EXECUTIVE
    last_pulse_id: Optional[str] = None
    last_acknowledged_at: Optional[float] = None
    pulse_count: int = 0
    missed_count: int = 0
    status: PulseStatus = PulseStatus.STALE
    translator_registered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "last_pulse_id": self.last_pulse_id,
            "last_acknowledged_at": self.last_acknowledged_at,
            "pulse_count": self.pulse_count,
            "missed_count": self.missed_count,
            "status": self.status.value,
            "translator_registered": self.translator_registered,
        }


# ---------------------------------------------------------------------------
# Heartbeat engine
# ---------------------------------------------------------------------------

class RosettaStoneHeartbeat:
    """Organization-wide heartbeat synchronisation engine.

    The heartbeat originates from the executive tier and propagates
    downward through each organizational tier in sequence.  Each tier
    can register a *translator* callback that receives the universal
    pulse and converts it into tier-specific actions.
    """

    def __init__(self, interval_seconds: float = 5.0,
                 stale_threshold_seconds: float = 15.0):
        self._lock = threading.RLock()
        self._interval = interval_seconds
        self._stale_threshold = stale_threshold_seconds
        self._state = HeartbeatState.IDLE
        self._sequence = 0

        # Per-tier state
        self._tiers: Dict[str, TierState] = {}
        for tier in TIER_ORDER:
            self._tiers[tier.value] = TierState(tier=tier)

        # Translator callbacks: tier_name → callable(pulse_dict) → ack_dict
        self._translators: Dict[str, Callable] = {}

        # Pulse history (bounded)
        self._pulse_history: List[Dict[str, Any]] = []
        self._max_history = 100

        # Sync check log
        self._sync_log: List[Dict[str, Any]] = []

    # -- Translator registration --------------------------------------------

    def register_translator(self, tier: OrganizationTier,
                            callback: Callable) -> Dict[str, Any]:
        """Register a translator callback for a tier."""
        with self._lock:
            self._translators[tier.value] = callback
            self._tiers[tier.value].translator_registered = True
            return {"registered": True, "tier": tier.value}

    def unregister_translator(self, tier: OrganizationTier) -> Dict[str, Any]:
        """Remove a tier's translator."""
        with self._lock:
            self._translators.pop(tier.value, None)
            self._tiers[tier.value].translator_registered = False
            return {"unregistered": True, "tier": tier.value}

    # -- Pulse emission -----------------------------------------------------

    def emit_pulse(self, directives: Optional[Dict[str, Any]] = None,
                   health_metrics: Optional[Dict[str, Any]] = None,
                   config_deltas: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Emit a new heartbeat pulse from the executive tier and propagate."""
        with self._lock:
            self._sequence += 1
            pulse = Pulse(
                sequence=self._sequence,
                origin_tier=OrganizationTier.EXECUTIVE,
                directives=directives or {},
                health_metrics=health_metrics or {},
                config_deltas=config_deltas or {},
                metadata=metadata or {},
                emitted_at=time.time(),
            )

            # Propagate through tiers in order
            propagation_results = []
            for tier in TIER_ORDER:
                tier_key = tier.value
                tier_state = self._tiers[tier_key]
                tier_state.last_pulse_id = pulse.pulse_id
                tier_state.pulse_count += 1

                translator = self._translators.get(tier_key)
                if translator:
                    try:
                        ack = translator(pulse.to_dict())
                        tier_state.status = PulseStatus.ACKNOWLEDGED
                        tier_state.last_acknowledged_at = time.time()
                        propagation_results.append({
                            "tier": tier_key,
                            "status": "acknowledged",
                            "ack": ack,
                        })
                    except Exception as exc:
                        logger.debug("Caught exception: %s", exc)
                        tier_state.status = PulseStatus.FAILED
                        tier_state.missed_count += 1
                        propagation_results.append({
                            "tier": tier_key,
                            "status": "failed",
                            "error": str(exc),
                        })
                else:
                    # No translator — mark as propagating (passive receipt)
                    tier_state.status = PulseStatus.PROPAGATING
                    tier_state.last_acknowledged_at = time.time()
                    propagation_results.append({
                        "tier": tier_key,
                        "status": "propagating",
                    })

            pulse_record = {
                **pulse.to_dict(),
                "propagation": propagation_results,
            }
            self._pulse_history.append(pulse_record)
            if len(self._pulse_history) > self._max_history:
                self._pulse_history = self._pulse_history[-self._max_history:]

            return {
                "success": True,
                "pulse_id": pulse.pulse_id,
                "sequence": pulse.sequence,
                "propagation": propagation_results,
            }

    # -- Sync check ---------------------------------------------------------

    def sync_check(self) -> Dict[str, Any]:
        """Verify all tiers are synchronised within the stale threshold."""
        with self._lock:
            now = time.time()
            tier_statuses = {}
            all_synced = True

            for tier in TIER_ORDER:
                ts = self._tiers[tier.value]
                if ts.last_acknowledged_at is None:
                    synced = False
                    age = None
                else:
                    age = round(now - ts.last_acknowledged_at, 3)
                    synced = age <= self._stale_threshold

                if not synced:
                    all_synced = False
                    if ts.status not in (PulseStatus.FAILED,):
                        ts.status = PulseStatus.STALE

                tier_statuses[tier.value] = {
                    "synced": synced,
                    "age_seconds": age,
                    "status": ts.status.value,
                    "pulse_count": ts.pulse_count,
                    "missed_count": ts.missed_count,
                }

            result = {
                "all_synced": all_synced,
                "sequence": self._sequence,
                "tiers": tier_statuses,
                "checked_at": now,
            }
            capped_append(self._sync_log, result)
            return result

    # -- Tier state queries -------------------------------------------------

    def get_tier_state(self, tier: OrganizationTier) -> Dict[str, Any]:
        with self._lock:
            return self._tiers[tier.value].to_dict()

    def get_all_tier_states(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._tiers.items()}

    def get_pulse_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._pulse_history[-limit:])

    # -- Heartbeat lifecycle ------------------------------------------------

    def start(self) -> Dict[str, Any]:
        """Mark heartbeat as running (actual timer loop is runtime-managed)."""
        with self._lock:
            self._state = HeartbeatState.RUNNING
            return {"state": self._state.value}

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            self._state = HeartbeatState.PAUSED
            return {"state": self._state.value}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._state = HeartbeatState.STOPPED
            return {"state": self._state.value}

    def get_state(self) -> HeartbeatState:
        with self._lock:
            return self._state

    # -- Statistics ---------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            tier_stats = {}
            for tier in TIER_ORDER:
                ts = self._tiers[tier.value]
                tier_stats[tier.value] = {
                    "pulse_count": ts.pulse_count,
                    "missed_count": ts.missed_count,
                    "status": ts.status.value,
                    "translator_registered": ts.translator_registered,
                }
            return {
                "heartbeat_state": self._state.value,
                "interval_seconds": self._interval,
                "stale_threshold_seconds": self._stale_threshold,
                "current_sequence": self._sequence,
                "pulse_history_size": len(self._pulse_history),
                "tiers": tier_stats,
            }


# ---------------------------------------------------------------------------
# Module-level status helper
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    """Return module-level status information."""
    return {
        "module": "rosetta_stone_heartbeat",
        "version": "1.0.0",
        "status": "operational",
        "tiers": [t.value for t in OrganizationTier],
        "tier_order": [t.value for t in TIER_ORDER],
        "pulse_statuses": [s.value for s in PulseStatus],
        "heartbeat_states": [s.value for s in HeartbeatState],
        "tier_count": len(TIER_ORDER),
        "timestamp": time.time(),
    }

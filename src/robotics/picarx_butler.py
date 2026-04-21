# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
PiCar-X AI Butler — **Reason**.

Design Label: ROBO-PICARX-BUTLER-001
Owner: Robotics / IoT / Automation
Rosetta ID: ``reason``

Reason is the physical embodiment of the Murphy System inside the home.
It is a SunFounder PiCar-X on a Raspberry Pi 3B+ whose job is to:

  1. Notify Corey Post of pending HITL requests (chronological order).
  2. Provide voice-activated control and dynamic conversation.
  3. Map the house with SLAM and patrol autonomously.
  4. Monitor its own battery and request charging.
  5. Feed every sensor reading and event back to the Murphy Learning Engine.
  6. Relay automation status updates on request.

On the Rosetta it is **reason**.

Dependencies (all optional — degrades to stub when absent):
  - picarx_hardware       (ROBO-PICARX-HW-001)
  - event_backbone        (EventBackbone)
  - learning_engine       (LearningEngine, PerformanceTracker)
  - voice_command_interface (VoiceCommandInterface)
  - rosetta.rosetta_models (Identity, RosettaAgentState, EmployeeContract …)
  - rosetta.rosetta_manager (RosettaManager)

Error codes: REASON-ERR-001 … REASON-ERR-012
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports — degrade gracefully
# ---------------------------------------------------------------------------

try:
    from robotics.picarx_hardware import (
        PiCarXHardware,
        SensorSnapshot,
        CHARGE_REQUEST_THRESHOLD,
        BATTERY_CRITICAL_VOLTAGE,
    )
    _HW_AVAILABLE = True
except ImportError:
    PiCarXHardware = None  # type: ignore[assignment,misc]
    SensorSnapshot = None  # type: ignore[assignment,misc]
    CHARGE_REQUEST_THRESHOLD = 7.0
    BATTERY_CRITICAL_VOLTAGE = 6.2
    _HW_AVAILABLE = False

try:
    from event_backbone import EventBackbone, EventType  # type: ignore[import-untyped]
    _BACKBONE_AVAILABLE = True
except ImportError:
    EventBackbone = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment,misc]
    _BACKBONE_AVAILABLE = False

try:
    from learning_engine.learning_engine import LearningEngine  # type: ignore[import-untyped]
    _LEARNING_AVAILABLE = True
except ImportError:
    LearningEngine = None  # type: ignore[assignment,misc]
    _LEARNING_AVAILABLE = False

try:
    from voice_command_interface import VoiceCommandInterface  # type: ignore[import-untyped]
    _VOICE_AVAILABLE = True
except ImportError:
    VoiceCommandInterface = None  # type: ignore[assignment,misc]
    _VOICE_AVAILABLE = False

try:
    from rosetta.rosetta_models import (  # type: ignore[import-untyped]
        AgentType,
        EmployeeContract,
        Identity,
        ManagementLayer,
        Metadata,
        RosettaAgentState,
        SystemState,
    )
    _ROSETTA_AVAILABLE = True
except ImportError:
    _ROSETTA_AVAILABLE = False

try:
    from rosetta.rosetta_manager import RosettaManager  # type: ignore[import-untyped]
    _ROSETTA_MGR_AVAILABLE = True
except ImportError:
    RosettaManager = None  # type: ignore[assignment,misc]
    _ROSETTA_MGR_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROSETTA_ID = "reason"
AGENT_NAME = "Reason"
AGENT_VERSION = "1.0.0"
ORGANISATION = "Inoni LLC"
OWNER = "Corey Post"

HEARTBEAT_INTERVAL_S = 30
HITL_POLL_INTERVAL_S = 30
SENSOR_POLL_INTERVAL_S = 5
PATROL_STEP_INTERVAL_S = 10


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class PatrolStatus(str, Enum):
    IDLE = "idle"
    PATROLLING = "patrolling"
    CHARGING = "charging"
    RETURNING_TO_CHARGE = "returning_to_charge"
    EMERGENCY_STOPPED = "emergency_stopped"


class ReasonStatus(str, Enum):
    OFFLINE = "offline"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass
class HITLNotification:
    """A pending HITL item surfaced to the owner."""
    hitl_id: str
    title: str
    description: str
    priority: str
    hitl_type: str
    created_at: str
    announced: bool = False


@dataclass
class ReasonState:
    """Full operational state of Reason."""
    status: ReasonStatus = ReasonStatus.OFFLINE
    patrol_status: PatrolStatus = PatrolStatus.IDLE
    battery_voltage: float = 0.0
    battery_percent: float = 0.0
    charge_requested: bool = False
    hitl_pending: List[HITLNotification] = field(default_factory=list)
    uptime_seconds: float = 0.0
    patrol_waypoints_visited: int = 0
    total_sensor_readings: int = 0
    total_learning_events: int = 0
    total_hitl_announced: int = 0
    total_voice_commands: int = 0
    last_heartbeat: float = 0.0
    slam_status: str = "idle"


# ---------------------------------------------------------------------------
# PiCarXButler — "Reason"
# ---------------------------------------------------------------------------

class PiCarXButler:
    """AI Butler for the Murphy System — codename **Reason**.

    On the Rosetta it is ``reason``.  Its job is to serve Corey Post as a
    loyal, proactive automation assistant inside the home.

    Key responsibilities:
      1. Surface HITL requests in chronological order.
      2. Voice-activated control and dynamic conversation.
      3. House mapping (SLAM) and autonomous patrol.
      4. Battery monitoring and charge requests.
      5. Feed all telemetry back to the Murphy Learning Engine.
      6. Relay automation status updates.
    """

    # -- construction --------------------------------------------------------

    def __init__(
        self,
        *,
        hardware: Any = None,
        backbone: Any = None,
        learning_engine: Any = None,
        voice_interface: Any = None,
        rosetta_manager: Any = None,
        hitl_fetch_fn: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        tts_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._state = ReasonState()
        self._start_time = 0.0
        self._stop_event = threading.Event()

        # -- hardware --------------------------------------------------------
        if hardware is not None:
            self._hw = hardware
        elif _HW_AVAILABLE and PiCarXHardware is not None:
            self._hw = PiCarXHardware()
        else:
            self._hw = None

        # -- integrations ----------------------------------------------------
        self._backbone = backbone
        self._learning = learning_engine
        self._voice = voice_interface
        self._rosetta_mgr = rosetta_manager
        self._hitl_fetch = hitl_fetch_fn or self._default_hitl_fetch
        self._tts = tts_fn or self._default_tts

        # -- threads ---------------------------------------------------------
        self._threads: List[threading.Thread] = []

        # Register Rosetta identity eagerly
        self._register_rosetta_identity()

        # Register voice patterns
        self._register_voice_patterns()

    # -- Rosetta identity (reason) ------------------------------------------

    def _register_rosetta_identity(self) -> None:
        """Register Reason on the Rosetta as agent ``reason``."""
        if not _ROSETTA_AVAILABLE:
            logger.info("Rosetta models unavailable — skipping identity registration")
            return
        try:
            identity = Identity(
                agent_id=ROSETTA_ID,
                name=AGENT_NAME,
                role="AI Butler — Ambient Automation Assistant",
                version=AGENT_VERSION,
                organization=ORGANISATION,
            )
            state = RosettaAgentState(
                identity=identity,
                system_state=SystemState(status="idle"),
                metadata=Metadata(
                    tags=["butler", "picarx", "reason", "iot", "home"],
                ),
            )
            if self._rosetta_mgr and hasattr(self._rosetta_mgr, "save_state"):
                self._rosetta_mgr.save_state(state)
                logger.info("Rosetta identity registered: %s", ROSETTA_ID)
            else:
                logger.info("Rosetta manager not provided — identity built but not persisted")
            self._rosetta_state = state
        except Exception as exc:  # REASON-ERR-001
            logger.error("Rosetta registration failed [REASON-ERR-001]: %s", exc)
            self._rosetta_state = None

    def get_rosetta_identity(self) -> Dict[str, Any]:
        """Return Reason's Rosetta identity dict."""
        return {
            "agent_id": ROSETTA_ID,
            "name": AGENT_NAME,
            "role": "AI Butler — Ambient Automation Assistant",
            "version": AGENT_VERSION,
            "organization": ORGANISATION,
            "owner": OWNER,
            "agent_type": "automation",
            "management_layer": "individual",
            "reports_to": OWNER,
            "department": "Home Automation",
            "authorised_actions": [
                "hitl_notify",
                "patrol",
                "map",
                "charge_request",
                "voice_relay",
                "sensor_read",
                "automation_status",
            ],
        }

    def build_employee_contract(self) -> Dict[str, Any]:
        """Build an EmployeeContract dict for Reason (Rosetta-compatible)."""
        return {
            "agent_type": "automation",
            "role_title": "AI Butler",
            "role_description": (
                f"Loyal automation assistant to {OWNER}. "
                "Surfaces HITL requests, maps the home, monitors battery, "
                "relays automation status, and feeds all telemetry back to "
                "the Murphy Learning Engine."
            ),
            "management_layer": "individual",
            "department": "Home Automation",
            "organisation_id": ORGANISATION,
            "reports_to": OWNER,
            "authorised_actions": [
                "hitl_notify", "patrol", "map", "charge_request",
                "voice_relay", "sensor_read", "automation_status",
            ],
            "work_order_scope": "assigned",
        }

    # -- voice patterns ------------------------------------------------------

    def _register_voice_patterns(self) -> None:
        """Register butler-specific voice command patterns."""
        if self._voice is None or not hasattr(self._voice, "register_pattern"):
            return
        try:
            patterns = [
                (r"\b(hitl|approvals?|pending|requests?)\b", "reason_hitl",
                 "monitor", "Show pending HITL requests",
                 ["what needs approval", "any pending requests"]),
                (r"\b(battery|charge|power)\b", "reason_battery",
                 "monitor", "Report battery status",
                 ["how much battery", "power level"]),
                (r"\b(patrol|explore|map|scout)\b", "reason_patrol",
                 "system", "Start or report patrol",
                 ["go patrol", "explore the house", "start mapping"]),
                (r"\b(status|report|state)\b", "reason_status",
                 "monitor", "Full status report",
                 ["give me a status report", "how are you"]),
                (r"\b(stop|halt|freeze)\b", "reason_stop",
                 "system", "Emergency stop",
                 ["stop now", "halt", "freeze"]),
                (r"\b(charge|dock|go charge)\b", "reason_charge",
                 "system", "Return to charger",
                 ["go charge", "dock yourself"]),
                (r"\b(automations?|updates?|what.*running)\b", "reason_automations",
                 "monitor", "Report automation status",
                 ["what automations are running", "any updates"]),
                (r"\b(help|what can you do)\b", "reason_help",
                 "help", "List capabilities",
                 ["help", "what can you do"]),
            ]
            for pattern, command, category, desc, aliases in patterns:
                self._voice.register_pattern(
                    pattern=pattern,
                    command=command,
                    category=category,
                    description=desc,
                    aliases=aliases,
                )
            logger.info("Registered %d voice patterns for Reason", len(patterns))
        except Exception as exc:  # REASON-ERR-002
            logger.warning("Voice pattern registration failed [REASON-ERR-002]: %s", exc)

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> bool:
        """Start Reason — connect hardware, launch daemon threads."""
        with self._lock:
            if self._state.status == ReasonStatus.RUNNING:
                return True
            self._state.status = ReasonStatus.STARTING
            self._start_time = time.monotonic()
            self._stop_event.clear()

        # Connect hardware
        if self._hw and hasattr(self._hw, "connect"):
            try:
                self._hw.connect()
            except Exception as exc:  # REASON-ERR-003
                logger.warning("Hardware connect failed [REASON-ERR-003]: %s", exc)

        # Launch background threads
        daemons = [
            ("reason-heartbeat", self._heartbeat_loop),
            ("reason-sensors", self._sensor_loop),
            ("reason-hitl", self._hitl_poll_loop),
        ]
        for name, target in daemons:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

        with self._lock:
            self._state.status = ReasonStatus.RUNNING
        logger.info("Reason started — %d daemon threads", len(self._threads))
        return True

    def stop(self) -> bool:
        """Stop Reason — halt motors, stop threads, disconnect."""
        self._stop_event.set()
        if self._hw and hasattr(self._hw, "stop"):
            try:
                self._hw.stop()
            except Exception:  # PROD-HARD A2: best-effort stop — proceed with disconnect regardless
                logger.warning("Hardware stop() failed during Reason shutdown; continuing to disconnect", exc_info=True)
        if self._hw and hasattr(self._hw, "disconnect"):
            try:
                self._hw.disconnect()
            except Exception:  # PROD-HARD A2: best-effort disconnect — continue thread join
                logger.warning("Hardware disconnect() failed during Reason shutdown; continuing to join threads", exc_info=True)
        for t in self._threads:
            t.join(timeout=5)
        self._threads.clear()
        with self._lock:
            self._state.status = ReasonStatus.STOPPED
            self._state.patrol_status = PatrolStatus.IDLE
        logger.info("Reason stopped")
        return True

    # -- HITL notification (chronological) -----------------------------------

    def fetch_pending_hitl(self) -> List[HITLNotification]:
        """Fetch pending HITL items and return in chronological order."""
        try:
            raw_items = self._hitl_fetch()
        except Exception as exc:  # REASON-ERR-004
            logger.warning("HITL fetch failed [REASON-ERR-004]: %s", exc)
            raw_items = []

        notifications: List[HITLNotification] = []
        for item in raw_items:
            if item.get("status") != "pending":
                continue
            notifications.append(HITLNotification(
                hitl_id=item.get("id", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                priority=item.get("priority", "normal"),
                hitl_type=item.get("type", ""),
                created_at=item.get("created_at", ""),
            ))

        # Strict chronological order (oldest first)
        notifications.sort(key=lambda n: n.created_at)

        with self._lock:
            self._state.hitl_pending = notifications
        return notifications

    def announce_hitl(self) -> List[str]:
        """Announce pending HITL items to the owner via TTS.

        Returns the list of announcement strings.
        """
        items = self.fetch_pending_hitl()
        if not items:
            return []

        announcements: List[str] = []
        count = len(items)
        header = (
            f"{count} pending approval{'s' if count != 1 else ''}. "
            "Presenting in chronological order."
        )
        announcements.append(header)
        self._tts(header)

        for i, item in enumerate(items, 1):
            msg = (
                f"Request {i}: {item.title}. "
                f"Priority: {item.priority}. "
                f"Type: {item.hitl_type}. "
                f"Created: {item.created_at}."
            )
            announcements.append(msg)
            self._tts(msg)
            item.announced = True

        with self._lock:
            self._state.total_hitl_announced += count
        self._emit_learning("hitl_announced", {"count": count})
        return announcements

    # -- voice command dispatch ----------------------------------------------

    def handle_voice(self, text: str) -> Dict[str, Any]:
        """Process a voice command through the butler.

        Supports direct text input or STT transcript.
        """
        with self._lock:
            self._state.total_voice_commands += 1

        # Use VoiceCommandInterface if available
        result: Dict[str, Any] = {}
        if self._voice and hasattr(self._voice, "process_voice"):
            try:
                result = self._voice.process_voice(text)
            except Exception as exc:  # REASON-ERR-005
                logger.warning("Voice processing failed [REASON-ERR-005]: %s", exc)
                result = {"error": str(exc)}

        command = result.get("command", {}).get("command", "") if result else ""

        # Dispatch known butler commands
        response = self._dispatch_command(command or text.strip().lower())
        response["voice_result"] = result
        self._emit_learning("voice_command", {
            "text": text, "command": command,
            "response_type": response.get("type", "unknown"),
        })
        return response

    def _dispatch_command(self, command: str) -> Dict[str, Any]:
        """Route a parsed command to the appropriate handler."""
        if "reason_hitl" in command or "approval" in command or "pending" in command:
            announcements = self.announce_hitl()
            pending = len(self._state.hitl_pending)
            return {"type": "hitl", "announcements": announcements,
                    "count": pending}
        if "reason_battery" in command or "battery" in command or "power" in command:
            return {"type": "battery", **self.get_battery_status()}
        if "reason_patrol" in command or "patrol" in command or "explore" in command:
            self.start_patrol()
            return {"type": "patrol", "status": "started"}
        if "reason_stop" in command or "stop" in command or "halt" in command:
            self.emergency_stop()
            return {"type": "stop", "status": "stopped"}
        if "reason_charge" in command or "charge" in command or "dock" in command:
            self.request_charge()
            return {"type": "charge", "status": "returning_to_charge"}
        if "reason_status" in command or "status" in command or "report" in command:
            return {"type": "status", **self.get_full_status()}
        if "reason_automations" in command or "automation" in command:
            return {"type": "automations", "message": "Automation status relay ready."}
        if "reason_help" in command or "help" in command:
            return {"type": "help", "capabilities": self._get_capabilities()}
        return {"type": "unknown", "message": f"I didn't understand: {command}"}

    def _get_capabilities(self) -> List[str]:
        return [
            "hitl — Show pending HITL approval requests",
            "battery — Report battery and power status",
            "patrol — Start house patrol / mapping",
            "status — Full status report",
            "stop — Emergency stop all motors",
            "charge — Return to charging dock",
            "automations — Report automation status",
            "help — Show this list",
        ]

    # -- battery management --------------------------------------------------

    def get_battery_status(self) -> Dict[str, Any]:
        """Read battery and return status dict."""
        voltage = 0.0
        percent = 0.0
        if self._hw and hasattr(self._hw, "read_battery_voltage"):
            voltage = self._hw.read_battery_voltage()
        if self._hw and hasattr(self._hw, "read_all"):
            snap = self._hw.read_all()
            voltage = snap.battery_voltage
            percent = snap.battery_percent

        needs_charge = voltage > 0 and voltage < CHARGE_REQUEST_THRESHOLD
        critical = voltage > 0 and voltage < BATTERY_CRITICAL_VOLTAGE

        with self._lock:
            self._state.battery_voltage = voltage
            self._state.battery_percent = percent
            self._state.charge_requested = needs_charge

        return {
            "voltage": voltage,
            "percent": percent,
            "needs_charge": needs_charge,
            "critical": critical,
        }

    def request_charge(self) -> None:
        """Request a return-to-charger action."""
        with self._lock:
            self._state.charge_requested = True
            self._state.patrol_status = PatrolStatus.RETURNING_TO_CHARGE
        self._tts("Returning to charger.")
        self._emit_event("DELIVERY_REQUESTED", {
            "agent_id": ROSETTA_ID,
            "task": "return_to_charger",
        })
        self._emit_learning("charge_requested", {
            "voltage": self._state.battery_voltage,
        })
        logger.info("Reason: charge requested at %.2f V", self._state.battery_voltage)

    # -- patrol / mapping ----------------------------------------------------

    def start_patrol(self) -> None:
        """Begin an autonomous patrol sweep."""
        with self._lock:
            if self._state.patrol_status == PatrolStatus.PATROLLING:
                return
            self._state.patrol_status = PatrolStatus.PATROLLING
        self._tts("Starting patrol.")
        self._emit_learning("patrol_started", {})
        logger.info("Reason: patrol started")

    def stop_patrol(self) -> None:
        """Stop the current patrol."""
        with self._lock:
            self._state.patrol_status = PatrolStatus.IDLE
        self._tts("Patrol stopped.")
        self._emit_learning("patrol_stopped", {})

    def emergency_stop(self) -> None:
        """Immediate emergency stop — halt all motors."""
        if self._hw and hasattr(self._hw, "stop"):
            try:
                self._hw.stop()
            except Exception:  # PROD-HARD A2: emergency stop is best-effort — still transition to EMERGENCY_STOPPED below
                logger.error("Hardware stop() failed during EMERGENCY STOP; forcing state transition anyway", exc_info=True)
        with self._lock:
            self._state.patrol_status = PatrolStatus.EMERGENCY_STOPPED
        self._tts("Emergency stop activated.")
        self._emit_event("ALERT_FIRED", {
            "agent_id": ROSETTA_ID,
            "alert": "emergency_stop",
        })
        logger.warning("Reason: EMERGENCY STOP")

    # -- full status ---------------------------------------------------------

    def get_full_status(self) -> Dict[str, Any]:
        """Return Reason's complete operational state."""
        with self._lock:
            uptime = time.monotonic() - self._start_time if self._start_time > 0 else 0
            self._state.uptime_seconds = uptime
            return {
                "agent_id": ROSETTA_ID,
                "name": AGENT_NAME,
                "owner": OWNER,
                "status": self._state.status.value,
                "patrol_status": self._state.patrol_status.value,
                "battery_voltage": self._state.battery_voltage,
                "battery_percent": self._state.battery_percent,
                "charge_requested": self._state.charge_requested,
                "hitl_pending_count": len(self._state.hitl_pending),
                "uptime_seconds": round(uptime, 1),
                "patrol_waypoints_visited": self._state.patrol_waypoints_visited,
                "total_sensor_readings": self._state.total_sensor_readings,
                "total_learning_events": self._state.total_learning_events,
                "total_hitl_announced": self._state.total_hitl_announced,
                "total_voice_commands": self._state.total_voice_commands,
                "slam_status": self._state.slam_status,
            }

    # -- daemon loops --------------------------------------------------------

    def _heartbeat_loop(self) -> None:
        """Publish periodic heartbeat via EventBackbone."""
        while not self._stop_event.is_set():
            try:
                status = self.get_full_status()
                self._emit_event("BOT_HEARTBEAT_OK", status)
                with self._lock:
                    self._state.last_heartbeat = time.time()
            except Exception as exc:  # REASON-ERR-006
                logger.warning("Heartbeat error [REASON-ERR-006]: %s", exc)
            self._stop_event.wait(HEARTBEAT_INTERVAL_S)

    def _sensor_loop(self) -> None:
        """Continuously read sensors and feed to Learning Engine."""
        while not self._stop_event.is_set():
            try:
                if self._hw and hasattr(self._hw, "read_all"):
                    snap = self._hw.read_all()
                    with self._lock:
                        self._state.battery_voltage = snap.battery_voltage
                        self._state.battery_percent = snap.battery_percent
                        self._state.total_sensor_readings += 1
                    self._emit_learning("sensor_reading", {
                        "ultrasonic_cm": snap.ultrasonic_cm,
                        "grayscale": snap.grayscale,
                        "battery_voltage": snap.battery_voltage,
                        "battery_percent": snap.battery_percent,
                    })
                    # Auto-charge request
                    if (snap.battery_voltage > 0
                            and snap.battery_voltage < CHARGE_REQUEST_THRESHOLD
                            and self._state.patrol_status != PatrolStatus.RETURNING_TO_CHARGE
                            and self._state.patrol_status != PatrolStatus.CHARGING):
                        self.request_charge()
            except Exception as exc:  # REASON-ERR-007
                logger.warning("Sensor loop error [REASON-ERR-007]: %s", exc)
            self._stop_event.wait(SENSOR_POLL_INTERVAL_S)

    def _hitl_poll_loop(self) -> None:
        """Poll for new HITL items and announce them."""
        previous_ids: set = set()
        while not self._stop_event.is_set():
            try:
                items = self.fetch_pending_hitl()
                current_ids = {n.hitl_id for n in items}
                new_ids = current_ids - previous_ids
                if new_ids:
                    new_count = len(new_ids)
                    msg = (
                        f"Corey, {new_count} new approval "
                        f"request{'s' if new_count != 1 else ''} pending."
                    )
                    self._tts(msg)
                    self._emit_learning("hitl_new_items", {"count": new_count})
                previous_ids = current_ids
            except Exception as exc:  # REASON-ERR-008
                logger.warning("HITL poll error [REASON-ERR-008]: %s", exc)
            self._stop_event.wait(HITL_POLL_INTERVAL_S)

    # -- integration helpers -------------------------------------------------

    def _emit_event(self, event_type_name: str, payload: Dict[str, Any]) -> None:
        """Publish an event to the EventBackbone (if available)."""
        if not self._backbone or not _BACKBONE_AVAILABLE:
            return
        try:
            et = getattr(EventType, event_type_name, None) if EventType else None
            if et and hasattr(self._backbone, "publish"):
                self._backbone.publish(et, payload)
        except Exception as exc:  # REASON-ERR-009
            logger.debug("Event emit failed [REASON-ERR-009]: %s", exc)

    def _emit_learning(self, metric_name: str, context: Dict[str, Any]) -> None:
        """Record a learning metric (if LearningEngine available)."""
        with self._lock:
            self._state.total_learning_events += 1
        if not self._learning:
            return
        try:
            if hasattr(self._learning, "record_metric"):
                self._learning.record_metric(
                    f"reason.{metric_name}", 1.0, context=context)
            elif hasattr(self._learning, "tracker") and hasattr(
                    self._learning.tracker, "record_metric"):
                self._learning.tracker.record_metric(
                    f"reason.{metric_name}", 1.0, context=context)
        except Exception as exc:  # REASON-ERR-010
            logger.debug("Learning emit failed [REASON-ERR-010]: %s", exc)

    @staticmethod
    def _default_hitl_fetch() -> List[Dict[str, Any]]:
        """Stub HITL fetch — returns empty list when no real endpoint."""
        return []

    @staticmethod
    def _default_tts(text: str) -> None:
        """Stub TTS — logs the announcement."""
        logger.info("Reason [TTS]: %s", text)

    # -- convenience ---------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<PiCarXButler '{AGENT_NAME}' rosetta={ROSETTA_ID} "
            f"status={self._state.status.value}>"
        )

# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
Agentic Communications Router — Murphy System
===============================================

Routes structured messages between agents across Matrix rooms.

Every message is a :class:`AgentMessage` carrying:
  - ``sender``         — agent_id of the sender
  - ``room``           — target room key from SUBSYSTEM_ROOMS
  - ``message_type``   — QUERY | RESPONSE | BROADCAST | ESCALATE | CALIBRATE_SYNC
  - ``content``        — payload dict (free-form)
  - ``sensor_readings``— calibration data attached to the message

Routing logic
-------------
1. Look up the room in the module manifest → find all resident modules
2. Identify the responsible bot persona for the room
3. Optionally pass the message through the room's :class:`RoomLLMBrain`
   (MAGNIFY / SIMPLIFY / SOLIDIFY depending on room role)
4. Deliver to all subscribed handler callbacks
5. Emit a ``message_routed`` event to the EventBackbone if available

Calibration sync
----------------
A ``CALIBRATE_SYNC`` message attaches :class:`CalibrationBundle` sensor readings
from :mod:`world_knowledge_calibrator`.  Receiving agents update their local
sensor store and re-anchor their LLM inference accordingly.

Design:  ACOM-001
Owner:   Platform AI / Agent Intelligence
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    """Type of an inter-agent message."""

    QUERY           = "query"            # request information from a room
    RESPONSE        = "response"         # reply to a QUERY
    BROADCAST       = "broadcast"        # fan-out to all room subscribers
    ESCALATE        = "escalate"         # urgent — bypass normal queue
    CALIBRATE_SYNC  = "calibrate_sync"   # push calibration anchors to agents
    ROOM_INFER      = "room_infer"       # ask room LLM brain to infer
    INFER_RESULT    = "infer_result"     # result from room LLM brain


class DeliveryStatus(str, Enum):
    """Status of a message delivery attempt."""

    PENDING   = "pending"
    DELIVERED = "delivered"
    FAILED    = "failed"
    BOUNCED   = "bounced"    # no handlers in target room


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    """A single inter-agent message."""

    sender: str
    room: str
    message_type: MessageType
    content: Dict[str, Any]                     = field(default_factory=dict)
    message_id: str                             = field(default_factory=lambda: str(uuid.uuid4()))
    reply_to: Optional[str]                     = None          # message_id being replied to
    sensor_readings: List[Any]                  = field(default_factory=list)
    priority: int                               = 5             # 1=highest, 10=lowest
    created_at: float                           = field(default_factory=time.time)
    ttl_seconds: float                          = 300.0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


@dataclass
class DeliveryReceipt:
    """Record of a message delivery attempt."""

    message_id: str
    room: str
    status: DeliveryStatus
    handler_count: int          = 0
    latency_ms: float           = 0.0
    error: Optional[str]        = None
    brain_result: Optional[Any] = None   # RoomInferenceResult if ROOM_INFER


# ---------------------------------------------------------------------------
# Handler type
# ---------------------------------------------------------------------------

MessageHandler = Callable[[AgentMessage], Optional[AgentMessage]]
"""
A callable that receives an :class:`AgentMessage` and optionally returns a
reply :class:`AgentMessage`.  If ``None`` is returned no reply is sent.
"""


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class AgenticCommsRouter:
    """
    Routes messages between agents across Matrix rooms.

    Parameters
    ----------
    room_brain_registry:
        Optional :class:`~room_llm_brain.RoomBrainRegistry`.  When provided,
        ``ROOM_INFER`` messages are passed through the room's LLM brain.
    event_backbone:
        Optional event backbone for publishing ``message_routed`` events.
    """

    def __init__(
        self,
        room_brain_registry: Optional[Any] = None,
        event_backbone: Optional[Any] = None,
    ) -> None:
        self._lock     = threading.Lock()
        self._handlers: Dict[str, List[MessageHandler]] = {}   # room → handlers
        self._inbox:    Dict[str, List[AgentMessage]]   = {}   # agent_id → messages
        self._receipts: List[DeliveryReceipt]           = []
        self._brain_reg = room_brain_registry
        self._backbone  = event_backbone

    # ------------------------------------------------------------------
    # Subscription API
    # ------------------------------------------------------------------

    def subscribe(self, room: str, handler: MessageHandler) -> None:
        """Register *handler* as a listener for messages in *room*."""
        with self._lock:
            self._handlers.setdefault(room, []).append(handler)
        logger.debug("AgenticCommsRouter: subscribed handler to room '%s'", room)

    def unsubscribe(self, room: str, handler: MessageHandler) -> None:
        """Remove *handler* from *room*."""
        with self._lock:
            handlers = self._handlers.get(room, [])
            if handler in handlers:
                handlers.remove(handler)

    def subscribe_agent(self, agent_id: str) -> None:
        """Register an agent inbox (for targeted QUERY / RESPONSE)."""
        with self._lock:
            self._inbox.setdefault(agent_id, [])

    # ------------------------------------------------------------------
    # Send API
    # ------------------------------------------------------------------

    def send(self, message: AgentMessage) -> DeliveryReceipt:
        """
        Route *message* to the target room.

        For ``ROOM_INFER`` messages the room's LLM brain is invoked and the
        result is attached to the receipt.
        For ``ESCALATE`` messages handlers are called synchronously and ahead
        of the normal queue.
        """
        t0 = time.monotonic()

        if message.is_expired:
            return DeliveryReceipt(
                message_id   = message.message_id,
                room         = message.room,
                status       = DeliveryStatus.BOUNCED,
                error        = "Message expired before routing",
            )

        # ROOM_INFER: delegate to LLM brain ─────────────────────────────
        brain_result = None
        if message.message_type == MessageType.ROOM_INFER and self._brain_reg is not None:
            try:
                from room_llm_brain import RoomInferenceRequest
            except ImportError:
                from src.room_llm_brain import RoomInferenceRequest

            req = RoomInferenceRequest(
                content         = message.content.get("text", str(message.content)),
                agent_id        = message.sender,
                sensor_readings = message.sensor_readings,
            )
            brain_result = self._brain_reg.infer(message.room, req)

        # Deliver to handlers ────────────────────────────────────────────
        with self._lock:
            handlers = list(self._handlers.get(message.room, []))

        delivered = 0
        for handler in handlers:
            try:
                reply = handler(message)
                delivered += 1
                if reply is not None:
                    # Route reply back
                    reply.reply_to = message.message_id
                    self._route_reply(reply)
            except Exception as exc:
                logger.warning("Handler error in room '%s': %s", message.room, exc)

        # Deliver targeted messages to agent inbox ───────────────────────
        target = message.content.get("to")
        if target:
            with self._lock:
                if target in self._inbox:
                    self._inbox[target].append(message)
                    delivered += 1

        # Emit to EventBackbone if available ─────────────────────────────
        if self._backbone is not None:
            try:
                self._backbone.emit("message_routed", {
                    "message_id":   message.message_id,
                    "sender":       message.sender,
                    "room":         message.room,
                    "type":         message.message_type.value,
                })
            except Exception:
                pass

        status = DeliveryStatus.DELIVERED if delivered > 0 else DeliveryStatus.BOUNCED
        receipt = DeliveryReceipt(
            message_id   = message.message_id,
            room         = message.room,
            status       = status,
            handler_count= delivered,
            latency_ms   = (time.monotonic() - t0) * 1000,
            brain_result = brain_result,
        )
        with self._lock:
            if len(self._receipts) >= 10_000:
                del self._receipts[:1_000]
            self._receipts.append(receipt)
        return receipt

    def broadcast(self, sender: str, content: Dict[str, Any]) -> List[DeliveryReceipt]:
        """
        Broadcast a message to ALL registered rooms.

        Returns one :class:`DeliveryReceipt` per room.
        """
        with self._lock:
            rooms = list(self._handlers)
        receipts = []
        for room in rooms:
            msg = AgentMessage(
                sender=sender,
                room=room,
                message_type=MessageType.BROADCAST,
                content=content,
                priority=7,
            )
            receipts.append(self.send(msg))
        return receipts

    def calibrate_sync(
        self,
        sender: str,
        room: str,
        calibration_bundle: Any,
    ) -> DeliveryReceipt:
        """
        Push a :class:`~world_knowledge_calibrator.CalibrationBundle` to *room*.

        The bundle's sensor readings are embedded in a ``CALIBRATE_SYNC`` message
        so all agents in the room update their calibration anchors.
        """
        sensor_readings = []
        if calibration_bundle is not None and hasattr(calibration_bundle, "sensor_readings"):
            sensor_readings = calibration_bundle.sensor_readings()
        msg = AgentMessage(
            sender          = sender,
            room            = room,
            message_type    = MessageType.CALIBRATE_SYNC,
            content         = {
                "domain":          getattr(calibration_bundle, "domain", "unknown"),
                "avg_confidence":  getattr(calibration_bundle, "avg_confidence", lambda: 1.0)(),
            },
            sensor_readings = sensor_readings,
            priority        = 2,  # high priority
        )
        return self.send(msg)

    # ------------------------------------------------------------------
    # Inbox API
    # ------------------------------------------------------------------

    def read_inbox(self, agent_id: str, clear: bool = True) -> List[AgentMessage]:
        """Return and optionally clear messages in *agent_id*'s inbox."""
        with self._lock:
            msgs = list(self._inbox.get(agent_id, []))
            if clear:
                self._inbox[agent_id] = []
        return msgs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _route_reply(self, reply: AgentMessage) -> None:
        """Route a reply without recording a receipt (internal)."""
        with self._lock:
            handlers = list(self._handlers.get(reply.room, []))
        for handler in handlers:
            try:
                handler(reply)
            except Exception as exc:
                logger.debug("Reply handler error: %s", exc)

    def stats(self) -> Dict[str, Any]:
        """Return router statistics."""
        with self._lock:
            total = len(self._receipts)
            delivered = sum(1 for r in self._receipts if r.status == DeliveryStatus.DELIVERED)
            bounced   = sum(1 for r in self._receipts if r.status == DeliveryStatus.BOUNCED)
        return {
            "total_routed": total,
            "delivered":    delivered,
            "bounced":      bounced,
            "rooms_with_handlers": len(self._handlers),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_router: Optional[AgenticCommsRouter] = None
_router_lock = threading.Lock()


def get_agentic_router(
    room_brain_registry: Optional[Any] = None,
    event_backbone: Optional[Any] = None,
) -> AgenticCommsRouter:
    """Return (and lazily create) the default :class:`AgenticCommsRouter`."""
    global _default_router
    with _router_lock:
        if _default_router is None:
            _default_router = AgenticCommsRouter(
                room_brain_registry=room_brain_registry,
                event_backbone=event_backbone,
            )
    return _default_router


__all__ = [
    "MessageType",
    "DeliveryStatus",
    "AgentMessage",
    "DeliveryReceipt",
    "MessageHandler",
    "AgenticCommsRouter",
    "get_agentic_router",
]

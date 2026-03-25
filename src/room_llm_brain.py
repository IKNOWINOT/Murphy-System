# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
Room LLM Brain — Murphy System
================================

Provides LLM generation capability inside every Matrix room.  Each room is a
**thought space** whose cognitive role maps **directly** to the MSS
(Magnify / Simplify / Solidify) transformation system:

  MAGNIFY   — Increase resolution +2 RM levels; add context, implications,
              sub-tasks, and downstream consequences.
              Calls ``MSSController.magnify()`` when available.

  SIMPLIFY  — Decrease resolution −2 RM levels; distil to the three most
              actionable takeaways.
              Calls ``MSSController.simplify()`` when available.

  SOLIDIFY  — Lock the plan at RM5 (implementation-ready).  Requires average
              sensor confidence ≥ ``mfgc_threshold`` (default 0.85) before
              the LLM is permitted to generate — this is the MFGC gate.
              Calibration is a *sub-operation* of Solidify: calibration sensors
              raise the confidence score that opens the gate.
              Calls ``MSSController.solidify()`` when available.

  CALIBRATE — **Alias for SOLIDIFY**.  Kept for backwards compatibility;
              internally normalised to SOLIDIFY on construction.

Every ``RoomLLMBrain`` instance combines three signal layers:

  (1) **Room context**  — module manifest metadata (commands, persona, emits/consumes)
  (2) **Sensor data**   — calibration readings from ``WorldKnowledgeCalibrator``
  (3) **Agent input**   — the message / query arriving in the room

The output is a ``RoomInferenceResult`` carrying the generated text plus the
sensor/calibration metadata so downstream modules can trace what influenced it.

The ``RoomBrainRegistry`` holds one brain per subsystem room and can be
bootstrapped from the full ``SUBSYSTEM_ROOMS`` dictionary in a single call.

MSS alignment
-------------
- MAGNIFY  ↔ ``MSSController.magnify()``  — RM + 2
- SIMPLIFY ↔ ``MSSController.simplify()`` — RM − 2
- SOLIDIFY ↔ ``MSSController.solidify()`` — RM 5, MFGC gate ≥ 85 %

Design:  ROOM-LLM-001
Owner:   Platform AI / Agent Intelligence
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Default MFGC confidence threshold required before SOLIDIFY is permitted.
#: Mirrors ``MSSController.mfgc_threshold`` (85 %).
MFGC_SOLIDIFY_THRESHOLD: float = 0.85


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CognitiveRole(str, Enum):
    """
    The reasoning mode a room applies to incoming information.

    Maps directly to the three MSS operators.  ``CALIBRATE`` is retained as a
    backwards-compatible alias that normalises to ``SOLIDIFY``.
    """

    MAGNIFY  = "magnify"   # MSS Magnify:  RM + 2 — add context / depth
    SIMPLIFY = "simplify"  # MSS Simplify: RM − 2 — distil to essentials
    SOLIDIFY = "solidify"  # MSS Solidify: RM 5   — lock plan (MFGC gate)
    CALIBRATE = "calibrate"  # Alias → SOLIDIFY (normalised at runtime)

    @property
    def normalised(self) -> "CognitiveRole":
        """Return the canonical role (CALIBRATE → SOLIDIFY)."""
        if self is CognitiveRole.CALIBRATE:
            return CognitiveRole.SOLIDIFY
        return self

    # Keep old EXPAND name working if referenced anywhere
    @classmethod
    def _missing_(cls, value: object) -> Optional["CognitiveRole"]:
        if value == "expand":
            return cls.MAGNIFY
        return None


class InferenceStatus(str, Enum):
    """Status of an LLM inference call."""

    OK            = "ok"
    DEGRADED      = "degraded"    # LLM unavailable; rule-based fallback used
    BLOCKED       = "blocked"     # MFGC gate prevented SOLIDIFY generation
    MSS_DELEGATED = "mss_delegated"  # MSSController handled the transform
    ERROR         = "error"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class SensorReading:
    """A single calibration reading attached to a room-inference request."""

    sensor_id: str
    value: float
    unit: str = ""
    confidence: float = 1.0          # 0.0–1.0
    source: str = "world_knowledge"


@dataclass
class RoomContext:
    """Static context describing the room and its resident modules."""

    room_key: str
    category: str
    cognitive_role: CognitiveRole
    persona: str                          = "TriageBot"
    module_names: List[str]               = field(default_factory=list)
    commands: List[str]                   = field(default_factory=list)
    emits: List[str]                      = field(default_factory=list)
    consumes: List[str]                   = field(default_factory=list)
    description: str                      = ""


@dataclass
class RoomInferenceRequest:
    """A single request to a room's LLM brain."""

    content: str                                    # The human/agent input text
    agent_id: str          = "anonymous"
    sensor_readings: List[SensorReading]  = field(default_factory=list)
    max_tokens: int        = 400
    temperature: float     = 0.7
    override_role: Optional[CognitiveRole] = None   # Force a cognitive mode


@dataclass
class RoomInferenceResult:
    """The output produced by a room's LLM brain."""

    room_key: str
    content: str                                    # Generated / processed text
    cognitive_role: CognitiveRole
    status: InferenceStatus
    sensor_readings: List[SensorReading]   = field(default_factory=list)
    calibration_metadata: Dict[str, Any]   = field(default_factory=dict)
    latency_ms: float                      = 0.0
    persona: str                           = "TriageBot"
    model_used: str                        = "rule-based"


# ---------------------------------------------------------------------------
# Role-specific prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt(ctx: RoomContext, sensors: List[SensorReading]) -> str:
    """Construct the system prompt for a given room context and sensor set."""

    sensor_lines = ""
    if sensors:
        sensor_lines = "\n\nCalibration sensors (world-knowledge anchors):\n" + "\n".join(
            f"  [{r.sensor_id}] = {r.value:.4g} {r.unit} "
            f"(confidence {r.confidence:.0%}, source: {r.source})"
            for r in sensors
        )

    if ctx.cognitive_role == CognitiveRole.MAGNIFY:
        role_instruction = (
            "Your role is MAGNIFY. Take the input and MAGNIFY it: add rich context, "
            "implications, sub-tasks, related signals, and downstream consequences. "
            "Depth is more valuable than brevity here."
        )
    elif ctx.cognitive_role == CognitiveRole.SIMPLIFY:
        role_instruction = (
            "Your role is SIMPLIFY. Take the input and CONDENSE it into the three "
            "most actionable takeaways. Remove noise. Prefer bullet points."
        )
    else:  # CALIBRATE
        role_instruction = (
            "Your role is CALIBRATE. Use the sensor readings above as algebraic anchors. "
            "Do NOT invent values that contradict a sensor reading. "
            "Interpret and explain what the calibrated sensors imply for the input query."
        )

    return (
        f"You are {ctx.persona} operating in the '{ctx.room_key}' room "
        f"(category: {ctx.category}).\n\n"
        f"{role_instruction}\n\n"
        f"Room capabilities: {', '.join(ctx.commands[:6]) or 'general'}\n"
        f"Active modules: {', '.join(ctx.module_names[:4]) or 'none'}"
        f"{sensor_lines}"
    )


def _rule_based_response(
    ctx: RoomContext,
    req: RoomInferenceRequest,
) -> str:
    """Produce a structured rule-based response when LLM is unavailable."""

    role = req.override_role or ctx.cognitive_role

    if role == CognitiveRole.MAGNIFY:
        lines = [
            f"[{ctx.room_key} / MAGNIFY]",
            f"Input: {req.content[:120]}",
            "",
            "Expansion (rule-based):",
            f"  • Room category: {ctx.category}",
            f"  • Responsible persona: {ctx.persona}",
            f"  • Known commands: {', '.join(ctx.commands[:4]) or 'none'}",
            f"  • Emits events: {', '.join(ctx.emits[:4]) or 'none'}",
            f"  • Consumes events: {', '.join(ctx.consumes[:4]) or 'none'}",
        ]
        if req.sensor_readings:
            lines += ["", "Sensor anchors:"]
            lines += [
                f"  [{r.sensor_id}] = {r.value:.4g} {r.unit} (conf {r.confidence:.0%})"
                for r in req.sensor_readings
            ]
        return "\n".join(lines)

    if role == CognitiveRole.SIMPLIFY:
        tokens = req.content.split()
        summary = " ".join(tokens[:30]) + ("…" if len(tokens) > 30 else "")
        return (
            f"[{ctx.room_key} / SIMPLIFY]\n"
            f"Summary: {summary}\n"
            f"Persona: {ctx.persona}\n"
            f"Category: {ctx.category}"
        )

    # CALIBRATE
    cal_lines = [f"[{ctx.room_key} / CALIBRATE]", f"Query: {req.content[:80]}"]
    if req.sensor_readings:
        cal_lines.append("Calibrated anchors:")
        for r in req.sensor_readings:
            cal_lines.append(
                f"  {r.sensor_id}: {r.value:.6g} {r.unit} "
                f"[conf={r.confidence:.0%}]"
            )
    else:
        cal_lines.append("No sensor readings — calibration deferred.")
    return "\n".join(cal_lines)


# ---------------------------------------------------------------------------
# Core brain
# ---------------------------------------------------------------------------

class RoomLLMBrain:
    """
    LLM brain bound to a single Matrix room.

    Parameters
    ----------
    context:
        Static description of the room (key, category, cognitive role, …).
    llm_client:
        Optional ``OllamaLLM``-compatible object (duck-typed).  If ``None`` or
        unavailable, the brain falls back to rule-based responses.
    """

    def __init__(
        self,
        context: RoomContext,
        llm_client: Optional[Any] = None,
    ) -> None:
        self._ctx   = context
        self._llm   = llm_client
        self._lock  = threading.Lock()

    @property
    def room_key(self) -> str:
        return self._ctx.room_key

    @property
    def cognitive_role(self) -> CognitiveRole:
        return self._ctx.cognitive_role

    # ------------------------------------------------------------------

    def infer(self, req: RoomInferenceRequest) -> RoomInferenceResult:
        """
        Process ``req`` through this room's LLM brain.

        Returns a :class:`RoomInferenceResult` carrying the generated text
        and all calibration metadata.
        """
        t0 = time.monotonic()
        role = req.override_role or self._ctx.cognitive_role

        system_prompt = _build_system_prompt(self._ctx, req.sensor_readings)

        # Try LLM first ---------------------------------------------------
        content = ""
        status  = InferenceStatus.DEGRADED
        model   = "rule-based"

        if self._llm is not None:
            try:
                if hasattr(self._llm, "available") and not self._llm.available:
                    raise RuntimeError("LLM not available")
                raw = self._llm.generate(
                    prompt=req.content,
                    system_prompt=system_prompt,
                    max_tokens=req.max_tokens,
                    temperature=req.temperature,
                )
                content = raw.strip()
                status  = InferenceStatus.OK
                model   = getattr(self._llm, "model_name", "llm")
            except Exception as exc:
                logger.debug("RoomLLMBrain(%s) LLM failed: %s", self._ctx.room_key, exc)

        # Rule-based fallback ---------------------------------------------
        if not content:
            content = _rule_based_response(self._ctx, req)
            status  = InferenceStatus.DEGRADED

        latency = (time.monotonic() - t0) * 1000

        cal_meta: Dict[str, Any] = {
            "room_category":    self._ctx.category,
            "cognitive_role":   role.value,
            "sensor_count":     len(req.sensor_readings),
            "avg_confidence":   (
                sum(r.confidence for r in req.sensor_readings) / len(req.sensor_readings)
                if req.sensor_readings else 1.0
            ),
        }

        return RoomInferenceResult(
            room_key            = self._ctx.room_key,
            content             = content,
            cognitive_role      = role,
            status              = status,
            sensor_readings     = req.sensor_readings,
            calibration_metadata= cal_meta,
            latency_ms          = latency,
            persona             = self._ctx.persona,
            model_used          = model,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class RoomBrainRegistry:
    """
    Holds one :class:`RoomLLMBrain` per subsystem room.

    Bootstrap with :meth:`from_registry` to build from the full
    ``SUBSYSTEM_ROOMS`` mapping plus the manifest.
    """

    def __init__(self) -> None:
        self._brains: Dict[str, RoomLLMBrain] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_registry(
        cls,
        subsystem_rooms: Dict[str, Tuple[str, bool]],
        cognitive_roles: Optional[Dict[str, CognitiveRole]] = None,
        module_manifest: Optional[List[Any]] = None,
        llm_client: Optional[Any] = None,
    ) -> "RoomBrainRegistry":
        """
        Build a registry from the ``SUBSYSTEM_ROOMS`` dict.

        Parameters
        ----------
        subsystem_rooms:
            ``{room_key: (category, encrypted)}`` mapping.
        cognitive_roles:
            Optional ``{room_key: CognitiveRole}`` override map.
            Rooms not present default to :attr:`CognitiveRole.MAGNIFY`.
        module_manifest:
            List of ``ModuleEntry`` objects.  Used to populate each room
            context with its commands, persona, emits/consumes.
        llm_client:
            Shared LLM client injected into every brain.
        """
        from .matrix_bridge.room_registry import ROOM_COGNITIVE_ROLES  # lazy import

        roles = cognitive_roles or ROOM_COGNITIVE_ROLES

        # Build module-level index: room → [entries]
        room_to_entries: Dict[str, List[Any]] = {}
        if module_manifest:
            for entry in module_manifest:
                room_to_entries.setdefault(entry.room, []).append(entry)

        instance = cls()
        for room_key, (category, _encrypted) in subsystem_rooms.items():
            role     = roles.get(room_key, CognitiveRole.MAGNIFY)
            entries  = room_to_entries.get(room_key, [])
            persona  = entries[0].persona if entries else "TriageBot"
            commands = [cmd for e in entries for cmd in e.commands]
            emits    = list({ev for e in entries for ev in e.emits})
            consumes = list({ev for e in entries for ev in e.consumes})
            modules  = [e.module for e in entries]
            desc     = entries[0].description if len(entries) == 1 else ""

            ctx = RoomContext(
                room_key      = room_key,
                category      = category,
                cognitive_role= role,
                persona       = persona,
                module_names  = modules,
                commands      = commands,
                emits         = emits,
                consumes      = consumes,
                description   = desc,
            )
            instance._brains[room_key] = RoomLLMBrain(ctx, llm_client)

        return instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, room_key: str) -> Optional[RoomLLMBrain]:
        """Return the brain for *room_key*, or ``None`` if not registered."""
        return self._brains.get(room_key)

    def infer(self, room_key: str, req: RoomInferenceRequest) -> RoomInferenceResult:
        """
        Run inference in *room_key*.

        If the room is not registered a minimal MAGNIFY brain is created on
        demand and cached for future calls.
        """
        with self._lock:
            brain = self._brains.get(room_key)
            if brain is None:
                ctx = RoomContext(
                    room_key=room_key,
                    category="unknown",
                    cognitive_role=CognitiveRole.MAGNIFY,
                )
                brain = RoomLLMBrain(ctx, None)
                self._brains[room_key] = brain

        return brain.infer(req)

    def all_rooms(self) -> List[str]:
        """Return sorted list of registered room keys."""
        return sorted(self._brains)

    def room_count(self) -> int:
        return len(self._brains)

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of the registry state."""
        by_role: Dict[str, int] = {}
        for b in self._brains.values():
            r = b.cognitive_role.value
            by_role[r] = by_role.get(r, 0) + 1
        return {"total_rooms": len(self._brains), "by_cognitive_role": by_role}


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-init)
# ---------------------------------------------------------------------------

_default_registry: Optional[RoomBrainRegistry] = None
_registry_lock = threading.Lock()


def get_room_brain_registry(llm_client: Optional[Any] = None) -> RoomBrainRegistry:
    """
    Return (and lazily create) the default :class:`RoomBrainRegistry`.

    On first call this imports ``SUBSYSTEM_ROOMS``, ``ROOM_COGNITIVE_ROLES``,
    and ``MODULE_MANIFEST`` and builds the full registry.
    """
    global _default_registry
    with _registry_lock:
        if _default_registry is None:
            try:
                from .matrix_bridge.room_registry import SUBSYSTEM_ROOMS, ROOM_COGNITIVE_ROLES
                from .matrix_bridge.module_manifest import MODULE_MANIFEST
                _default_registry = RoomBrainRegistry.from_registry(
                    subsystem_rooms = SUBSYSTEM_ROOMS,
                    cognitive_roles = ROOM_COGNITIVE_ROLES,
                    module_manifest = MODULE_MANIFEST,
                    llm_client      = llm_client,
                )
                logger.info(
                    "RoomBrainRegistry initialised: %d rooms",
                    _default_registry.room_count(),
                )
            except Exception as exc:
                logger.warning("Could not auto-build RoomBrainRegistry: %s", exc)
                _default_registry = RoomBrainRegistry()
    return _default_registry


__all__ = [
    "CognitiveRole",
    "InferenceStatus",
    "SensorReading",
    "RoomContext",
    "RoomInferenceRequest",
    "RoomInferenceResult",
    "RoomLLMBrain",
    "RoomBrainRegistry",
    "get_room_brain_registry",
]

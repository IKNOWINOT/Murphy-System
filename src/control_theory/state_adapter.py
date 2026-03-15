"""
State adapters for the Murphy System canonical state vector.

Each adapter converts a legacy state type to :class:`CanonicalStateVector`
using only the fields that are available in the source type and falling back
to sensible defaults (0.0 / 0) for everything else.

No existing state class is modified; this module is purely additive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from control_theory.canonical_state import CanonicalStateVector

if TYPE_CHECKING:
    # Imported only for type hints — avoids hard import errors if optional
    # dependencies are missing at runtime.
    from logging_system import Session
    from mfgc_core import MFGCSystemState, Phase
    from rosetta.rosetta_models import SystemState as RosettaSystemState
    from unified_mfgc import SystemState as UnifiedSystemState


# ---------------------------------------------------------------------------
# Phase → index mapping (mirrors mfgc_core.Phase order)
# ---------------------------------------------------------------------------
_PHASE_TO_INDEX: Dict[str, int] = {
    "expand": 0,
    "type": 1,
    "enumerate": 2,
    "constrain": 3,
    "collapse": 4,
    "bind": 5,
    "execute": 6,
}


def _phase_index(phase: Any) -> int:
    """Convert a Phase enum (or string) to its canonical integer index."""
    if phase is None:
        return 0
    # Support both enum instances and raw strings
    value = phase.value if hasattr(phase, "value") else str(phase).lower()
    return _PHASE_TO_INDEX.get(value, 0)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def from_mfgc_state(state: "MFGCSystemState") -> CanonicalStateVector:
    """
    Convert a :class:`~mfgc_core.MFGCSystemState` to :class:`CanonicalStateVector`.

    Mapping:
        c_t  → confidence
        a_t  → authority
        M_t  → murphy_index
        p_t  → phase_index (via phase order)
        G_t  → gate_count (len of active gates list)
    """
    return CanonicalStateVector(
        confidence=getattr(state, "c_t", 0.0),
        authority=getattr(state, "a_t", 0.0),
        murphy_index=getattr(state, "M_t", 0.0),
        phase_index=_phase_index(getattr(state, "p_t", None)),
        gate_count=len(getattr(state, "G_t", []) or []),
    )


def from_unified_system_state(state: "UnifiedSystemState") -> CanonicalStateVector:
    """
    Convert a ``unified_mfgc.SystemState`` (dataclass) to
    :class:`CanonicalStateVector`.

    Mapping:
        confidence     → confidence
        complexity     → complexity
        artifacts_count → artifact_count
        gates_count    → gate_count
        domain         → domain (metadata)
    """
    return CanonicalStateVector(
        confidence=getattr(state, "confidence", 0.0),
        complexity=getattr(state, "complexity", 0.0),
        artifact_count=getattr(state, "artifacts_count", 0),
        gate_count=getattr(state, "gates_count", 0),
        domain=getattr(state, "domain", "general") or "general",
    )


def from_rosetta_state(state: "RosettaSystemState") -> CanonicalStateVector:
    """
    Convert a ``rosetta.rosetta_models.SystemState`` (Pydantic) to
    :class:`CanonicalStateVector`.

    Mapping:
        uptime_seconds    → uptime_seconds
        active_tasks      → active_tasks
        cpu_usage_percent → cpu_usage_percent
    """
    return CanonicalStateVector(
        uptime_seconds=getattr(state, "uptime_seconds", 0.0),
        active_tasks=getattr(state, "active_tasks", 0),
        cpu_usage_percent=getattr(state, "cpu_usage_percent", 0.0),
    )


def from_session(session: "Session") -> CanonicalStateVector:
    """
    Convert a ``logging_system.Session`` (dataclass) to
    :class:`CanonicalStateVector`.

    Mapping:
        confidence_history[-1]  → confidence  (most recent observation)
        murphy_index_history[-1] → murphy_index
        session_id              → session_id (metadata)
    """
    c_history: List[float] = getattr(session, "confidence_history", []) or []
    m_history: List[float] = getattr(session, "murphy_index_history", []) or []

    return CanonicalStateVector(
        confidence=c_history[-1] if c_history else 0.0,
        murphy_index=m_history[-1] if m_history else 0.0,
        session_id=getattr(session, "session_id", None),
    )


def from_dict(data: Dict[str, Any]) -> CanonicalStateVector:
    """
    Build a :class:`CanonicalStateVector` from an arbitrary dictionary.

    Only recognised field names are forwarded; unknown keys are silently
    ignored.  Missing fields fall back to their defaults.
    """
    recognised = set(CanonicalStateVector.model_fields.keys())
    filtered = {k: v for k, v in data.items() if k in recognised}
    return CanonicalStateVector(**filtered)

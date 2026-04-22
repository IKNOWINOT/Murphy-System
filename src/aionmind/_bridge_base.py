"""Shared helpers for AionMind capability bridges (Phase 2).

Every capability bridge in ``aionmind/`` follows the same shape:

1. Declare a list of :class:`Capability` objects describing what the
   subsystem can do — including non-empty ``input_schema`` and
   ``output_schema`` (Phase 2 / C17 — schema discipline).
2. Provide a handler for each capability.  The handler takes an
   :class:`ExecutionNode` and returns a dict.  Handlers should be
   *small* shims that call into the underlying subsystem and
   normalise the result.
3. Expose a ``load_<subsystem>_capabilities_into_kernel(kernel)``
   function that registers each capability + handler with the kernel
   and returns a count.

This module contains the cross-cutting pieces — the
``BridgeCapability`` dataclass, schema-discipline assertions, a safe
subsystem loader, and a stub-handler factory for cases where the
subsystem cannot be imported (so planning still works even if the
target service is absent at boot).

Why a shared helper? Without one, each bridge would re-implement the
same boilerplate and drift.  Worse, the schema-discipline rule (C17)
would be enforced by convention only.  Centralising the wrapper makes
"every capability has non-empty schemas" a *runtime invariant*.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from aionmind.capability_registry import Capability

logger = logging.getLogger(__name__)


# ── Risk + style constants ────────────────────────────────────────

# The four risk tiers used by every bridge.  Re-exported as plain
# strings to match :attr:`Capability.risk_level`'s declared type.
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"


# ── Bridge data model ─────────────────────────────────────────────


@dataclass
class BridgeCapability:
    """A capability declaration produced by a bridge.

    ``handler`` is intentionally optional — bridges may declare a
    capability for *planning* (so the reasoner can see it) even when
    no concrete handler exists yet.  When a node tries to execute a
    handler-less capability the orchestration engine fails the node;
    that is the right behaviour for "registered but unimplemented."
    """

    capability_id: str
    name: str
    description: str
    provider: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    risk_level: str = RISK_LOW
    requires_approval: bool = False
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable[..., Any]] = None

    def to_capability(self) -> Capability:
        """Convert to a registry :class:`Capability` object."""
        _assert_schema_discipline(self)
        return Capability(
            capability_id=self.capability_id,
            name=self.name,
            description=self.description,
            provider=self.provider,
            input_schema=dict(self.input_schema),
            output_schema=dict(self.output_schema),
            risk_level=self.risk_level,
            requires_approval=self.requires_approval,
            tags=list(self.tags) or ["general"],
            metadata=dict(self.metadata),
        )


# ── Schema discipline (C17) ───────────────────────────────────────


class CapabilitySchemaError(ValueError):
    """Raised when a bridge declares a capability with empty schemas.

    This enforces Phase 2 / C17 — every registered capability MUST
    declare both input and output schemas so downstream consumers
    (UI, tracing, contract tests) have something concrete to bind to.
    """


def _assert_schema_discipline(cap: "BridgeCapability") -> None:
    """Reject capabilities that omit input_schema or output_schema."""
    if not cap.input_schema:
        raise CapabilitySchemaError(
            f"Capability {cap.capability_id!r} has empty input_schema. "
            "Bridges must declare at least one input field "
            "(use {} only for explicitly nullary actions and pass "
            "{'_': {'type': 'null'}} as a sentinel)."
        )
    if not cap.output_schema:
        raise CapabilitySchemaError(
            f"Capability {cap.capability_id!r} has empty output_schema. "
            "Bridges must declare the response shape — at minimum "
            "{'status': {'type': 'string'}}."
        )


# ── Bridge loader ─────────────────────────────────────────────────


def register_bridge_capabilities(
    kernel: Any,
    bridge_name: str,
    capabilities: List[BridgeCapability],
) -> int:
    """Register a bridge's capabilities + handlers into *kernel*.

    Parameters
    ----------
    kernel : AionMindKernel
        Target kernel (typed as ``Any`` to avoid an import cycle).
    bridge_name : str
        Human label used in the startup summary log line (E24).
    capabilities : list[BridgeCapability]
        Capabilities to register.

    Returns
    -------
    int
        Number of capabilities successfully registered.
    """
    count = 0
    for cap in capabilities:
        try:
            kernel.register_capability(cap.to_capability())
            if cap.handler is not None:
                kernel.register_handler(cap.capability_id, cap.handler)
            count += 1
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "[%s] failed to register capability %s: %s",
                bridge_name,
                cap.capability_id,
                exc,
            )
    logger.info(
        "[aionmind/%s] registered %d/%d capabilities.",
        bridge_name,
        count,
        len(capabilities),
    )
    return count


def make_unavailable_handler(
    subsystem: str,
    reason: str = "subsystem_unavailable",
) -> Callable[..., Dict[str, Any]]:
    """Return a handler that reports a missing subsystem at execute time.

    Used by bridges whose target subsystem cannot be imported — the
    capability is still declared (so plans can mention it) but
    execution returns a structured failure rather than a Python
    ``ImportError``.
    """

    def _handler(node: Any) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "subsystem": subsystem,
            "reason": reason,
            "capability_id": getattr(node, "capability_id", None),
        }

    return _handler

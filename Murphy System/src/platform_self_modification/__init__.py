"""Platform-level self-modification HITL pipeline.

Distinct from per-tenant ``supervisor_system.hitl_*``: this package
controls *Murphy modifying its own code* under platform-operator
approval. Three pillars:

  * PSM-001 :class:`RSCSelfModificationGate` — Lyapunov pre-launch gate
  * PSM-002 :class:`SelfEditLedger`          — append-only hash-chained log
  * PSM-003 :func:`launch_endpoint`          — operator-approved HTTP launch
                                              (mounted in murphy_production_server)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from .rsc_gate import GateDecision, RSCSelfModificationGate
from .ledger import LedgerEntry, LedgerEntryKind, LedgerError, SelfEditLedger
from .endpoint import (
    LEDGER_PATH_ENV,
    OPERATOR_HEADER,
    OPERATOR_TOKEN_ENV,
    LaunchRequest,
    build_router,
)

__all__ = [
    "GateDecision",
    "RSCSelfModificationGate",
    "LedgerEntry",
    "LedgerEntryKind",
    "LedgerError",
    "SelfEditLedger",
    "LaunchRequest",
    "build_router",
    "LEDGER_PATH_ENV",
    "OPERATOR_HEADER",
    "OPERATOR_TOKEN_ENV",
]

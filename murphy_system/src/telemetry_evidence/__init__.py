"""
Telemetry Evidence Module

Design Label: ARCH-007 — Telemetry Evidence Storage
Owner: Backend Team

Stores real telemetry snapshots for historical analysis, trend detection,
and incident investigation evidence retrieval.

Public exports:
  - TelemetryEvidenceStore
  - TelemetrySnapshot
  - EvidenceQuery
  - SnapshotKind
"""

from .evidence_store import (
    EvidenceQuery,
    SnapshotKind,
    TelemetryEvidenceStore,
    TelemetrySnapshot,
)

__all__ = [
    "EvidenceQuery",
    "SnapshotKind",
    "TelemetryEvidenceStore",
    "TelemetrySnapshot",
]

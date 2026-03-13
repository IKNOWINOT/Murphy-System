"""
Automation Readiness Evaluator for Murphy System.

Design Label: OPS-001 — Cross-Phase Readiness Assessment & Wiring Validation
Owner: Platform Engineering / Architecture Team
Dependencies:
  - PersistenceManager (for durable readiness reports)
  - EventBackbone (publishes LEARNING_FEEDBACK on evaluation cycles)
  - AutomationIntegrationHub (INT-001, optional, for module registry)

Implements Phase 8 — Operational Readiness & Autonomy Governance:
  Evaluates system readiness by checking registration and health of
  all design-labeled modules across Phases 0–7.  Produces a per-phase
  readiness score and an overall ReadinessReport with go/no-go verdict.

Flow:
  1. Register expected modules per phase with design labels
  2. Check each module's status via a provided health callable
  3. Score each phase (registered and healthy / expected)
  4. Compute overall readiness score
  5. Persist ReadinessReport and publish LEARNING_FEEDBACK event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only: never modifies module state
  - Bounded: configurable max reports retained
  - Audit trail: every evaluation cycle is logged

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
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_REPORTS = 500

# ---------------------------------------------------------------------------
# Default module registry — all 46 design labels from Phases 0–10
# ---------------------------------------------------------------------------

DEFAULT_PHASE_MODULES: Dict[str, List[str]] = {
    "foundation":    ["ARCH-001", "ARCH-002", "GATE-001", "SEC-001"],
    "observability": ["OBS-001", "OBS-002", "OBS-003", "OBS-004"],
    "development":   ["DEV-001", "DEV-002", "DEV-003", "DEV-004", "DEV-005"],
    "support":       ["SUP-001", "SUP-002", "SUP-003", "SUP-004"],
    "compliance":    ["CMP-001"],
    "marketing":     ["MKT-001", "MKT-002", "MKT-003", "MKT-004", "MKT-005"],
    "business":      ["BIZ-001", "BIZ-002", "BIZ-003", "BIZ-004", "BIZ-005"],
    "advanced":      ["ADV-001", "ADV-002", "ADV-003", "ADV-004"],
    "integration":   ["INT-001"],
    "operations":    ["OPS-001", "OPS-002", "OPS-003", "OPS-004"],
    "safety":        ["SAF-001", "SAF-002", "SAF-003", "SAF-004", "SAF-005"],
    "orchestration": ["ORCH-001", "ORCH-002", "ORCH-003", "ORCH-004"],
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ReadinessVerdict(str, Enum):
    """Overall readiness outcome."""
    READY = "ready"
    PARTIAL = "partial"
    NOT_READY = "not_ready"


@dataclass
class ModuleCheck:
    """Result of checking a single module's readiness."""
    design_label: str
    phase: str
    registered: bool
    healthy: bool
    message: str = ""
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_label": self.design_label,
            "phase": self.phase,
            "registered": self.registered,
            "healthy": self.healthy,
            "message": self.message,
            "checked_at": self.checked_at,
        }


@dataclass
class PhaseScore:
    """Readiness score for a single phase."""
    phase: str
    expected: int
    registered: int
    healthy: int
    score: float  # 0.0 – 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "expected": self.expected,
            "registered": self.registered,
            "healthy": self.healthy,
            "score": round(self.score, 4),
        }


@dataclass
class ReadinessReport:
    """Overall system readiness report."""
    report_id: str
    verdict: ReadinessVerdict
    overall_score: float
    phase_scores: List[PhaseScore] = field(default_factory=list)
    module_checks: List[ModuleCheck] = field(default_factory=list)
    total_expected: int = 0
    total_registered: int = 0
    total_healthy: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "verdict": self.verdict.value,
            "overall_score": round(self.overall_score, 4),
            "total_expected": self.total_expected,
            "total_registered": self.total_registered,
            "total_healthy": self.total_healthy,
            "phase_scores": [ps.to_dict() for ps in self.phase_scores],
            "module_checks": [mc.to_dict() for mc in self.module_checks],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# AutomationReadinessEvaluator
# ---------------------------------------------------------------------------

class AutomationReadinessEvaluator:
    """Cross-phase readiness assessment and wiring validation.

    Design Label: OPS-001
    Owner: Platform Engineering / Architecture Team

    Usage::

        evaluator = AutomationReadinessEvaluator()
        evaluator.register_module("OBS-001", "observability", health_fn=lambda: True)
        report = evaluator.evaluate()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        phase_modules: Optional[Dict[str, List[str]]] = None,
        ready_threshold: float = 0.8,
        partial_threshold: float = 0.5,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._phase_modules = dict(phase_modules or DEFAULT_PHASE_MODULES)
        self._ready_threshold = ready_threshold
        self._partial_threshold = partial_threshold
        # label -> (phase, health_fn | None)
        self._registered: Dict[str, tuple] = {}
        self._reports: List[ReadinessReport] = []

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def register_module(
        self,
        design_label: str,
        phase: str,
        health_fn: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Register a module as present, optionally with a health check."""
        with self._lock:
            self._registered[design_label] = (phase, health_fn)
        logger.debug("Registered module %s in phase %s", design_label, phase)

    def unregister_module(self, design_label: str) -> bool:
        with self._lock:
            return self._registered.pop(design_label, None) is not None

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self) -> ReadinessReport:
        """Evaluate readiness across all phases."""
        with self._lock:
            registered = dict(self._registered)
            phases = dict(self._phase_modules)

        module_checks: List[ModuleCheck] = []
        phase_scores: List[PhaseScore] = []
        total_expected = 0
        total_registered = 0
        total_healthy = 0

        for phase, labels in phases.items():
            phase_reg = 0
            phase_ok = 0
            for label in labels:
                is_registered = label in registered
                is_healthy = False
                msg = ""
                if is_registered:
                    phase_reg += 1
                    _phase, fn = registered[label]
                    if fn is not None:
                        try:
                            is_healthy = bool(fn())
                        except Exception as exc:
                            logger.debug("Caught exception: %s", exc)
                            msg = str(exc)[:200]
                    else:
                        is_healthy = True  # registered without check → assume OK
                    if is_healthy:
                        phase_ok += 1
                else:
                    msg = "not registered"
                module_checks.append(ModuleCheck(
                    design_label=label,
                    phase=phase,
                    registered=is_registered,
                    healthy=is_healthy,
                    message=msg,
                ))
            score = phase_ok / (len(labels) or 1) if labels else 1.0
            phase_scores.append(PhaseScore(
                phase=phase,
                expected=len(labels),
                registered=phase_reg,
                healthy=phase_ok,
                score=score,
            ))
            total_expected += len(labels)
            total_registered += phase_reg
            total_healthy += phase_ok

        overall = total_healthy / total_expected if total_expected else 1.0
        if overall >= self._ready_threshold:
            verdict = ReadinessVerdict.READY
        elif overall >= self._partial_threshold:
            verdict = ReadinessVerdict.PARTIAL
        else:
            verdict = ReadinessVerdict.NOT_READY

        report = ReadinessReport(
            report_id=f"rr-{uuid.uuid4().hex[:8]}",
            verdict=verdict,
            overall_score=overall,
            phase_scores=phase_scores,
            module_checks=module_checks,
            total_expected=total_expected,
            total_registered=total_registered,
            total_healthy=total_healthy,
        )

        with self._lock:
            if len(self._reports) >= _MAX_REPORTS:
                self._reports = self._reports[_MAX_REPORTS // 10:]
            self._reports.append(report)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=report.report_id, document=report.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(report)

        logger.info(
            "Readiness evaluation: %s (score=%.2f, %d/%d healthy)",
            verdict.value, overall, total_healthy, total_expected,
        )
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._reports[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_expected_modules": sum(len(v) for v in self._phase_modules.values()),
                "total_registered": len(self._registered),
                "total_reports": len(self._reports),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, report: ReadinessReport) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "automation_readiness_evaluator",
                    "action": "readiness_evaluated",
                    "report_id": report.report_id,
                    "verdict": report.verdict.value,
                    "overall_score": report.overall_score,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="automation_readiness_evaluator",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)

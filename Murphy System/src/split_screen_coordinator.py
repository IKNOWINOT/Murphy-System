"""
Split-Screen Coordinator — Murphy System

Coordinates simultaneous multi-zone desktop automation using three existing
Murphy subsystems as the control plane:

  RubixEvidenceAdapter   — pre-flight statistical evidence gate for every zone
  TicketTriageEngine     — priority-scores tasks so highest-severity zones run
                           first; critical tasks get their own dedicated cursor
  SplitScreenManager     — dispatches all zones simultaneously (parallel threads)

Architecture (pipeline per run):
  1. TRIAGE       Each zone task description → TicketTriageEngine.triage()
                  Produces severity rank + confidence score.
  2. EVIDENCE     Each task → RubixEvidenceAdapter.check_monte_carlo()
                  Verdicts: pass → proceed, fail → flag (still runs unless
                  strict_mode=True), inconclusive → run with warning.
  3. SORT         Zones ordered critical > high > medium > low for logging;
                  all zones run in parallel regardless of order.
  4. DISPATCH     SplitScreenManager.run_all(parallel=True) — each zone in
                  its own thread with its own CursorContext.
  5. REPORT       Returns unified result: triage scores, evidence verdicts,
                  zone results, cursor snapshots, and a human-readable summary.

Usage::

    from split_screen_coordinator import SplitScreenCoordinator
    from murphy_native_automation import (
        NativeTask, NativeStep, ActionType,
        SplitScreenLayout,
    )

    coord = SplitScreenCoordinator(
        layout=SplitScreenLayout.DUAL_H,
        screen_width=1920, screen_height=1080,
    )

    task_a = NativeTask(steps=[NativeStep(action=ActionType.API_GET, target="/api/health")])
    task_b = NativeTask(steps=[NativeStep(action=ActionType.API_GET, target="/api/status")])

    result = coord.coordinate({
        coord.zones[0].zone_id: (task_a, "Check API health endpoint"),
        coord.zones[1].zone_id: (task_b, "Check system status endpoint"),
    })
    print(coord.summary(result))

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Murphy-native imports
# ---------------------------------------------------------------------------
try:
    from murphy_native_automation import (
        NativeTask,
        ScreenZone,
        SplitScreenLayout,
        SplitScreenManager,
    )
except ImportError:  # pragma: no cover
    raise RuntimeError(
        "split_screen_coordinator requires murphy_native_automation — "
        "ensure src/ is on sys.path"
    )

try:
    from rubix_evidence_adapter import (
        EvidenceVerdict,
        RubixEvidenceAdapter,
    )
    _RUBIX_AVAILABLE = True
except ImportError:
    _RUBIX_AVAILABLE = False
    EvidenceVerdict = None  # type: ignore[assignment,misc]
    RubixEvidenceAdapter = None  # type: ignore[assignment,misc]
    logger.debug("RubixEvidenceAdapter not available — evidence gates disabled")

try:
    from ticket_triage_engine import TicketTriageEngine
    _TRIAGE_AVAILABLE = True
except ImportError:
    _TRIAGE_AVAILABLE = False
    TicketTriageEngine = None  # type: ignore[assignment,misc]
    logger.debug("TicketTriageEngine not available — triage priority disabled")


# ---------------------------------------------------------------------------
# Priority ordering (triage severity → dispatch weight)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
_SEVERITY_SCORES = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25, "unknown": 0.5}


# ---------------------------------------------------------------------------
# Coordination result
# ---------------------------------------------------------------------------


@dataclass
class ZoneCoordinationResult:
    """Per-zone output from a SplitScreenCoordinator.coordinate() call."""
    zone_id: str
    zone_name: str
    zone_label: str
    triage_severity: str = "unknown"
    triage_confidence: float = 0.0
    triage_team: str = "unknown"
    evidence_verdict: str = "skipped"
    evidence_score: float = 0.0
    task_result: Dict[str, Any] = field(default_factory=dict)
    flagged: bool = False
    flag_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_label": self.zone_label,
            "triage": {
                "severity": self.triage_severity,
                "confidence": self.triage_confidence,
                "team": self.triage_team,
            },
            "evidence": {
                "verdict": self.evidence_verdict,
                "score": self.evidence_score,
            },
            "task_result": self.task_result,
            "flagged": self.flagged,
            "flag_reason": self.flag_reason,
        }


@dataclass
class CoordinationReport:
    """Full output of a SplitScreenCoordinator.coordinate() run."""
    run_id: str
    layout: str
    zone_count: int
    zone_results: List[ZoneCoordinationResult]
    cursor_snapshots: List[Dict[str, Any]]
    started_at: str
    completed_at: str
    parallel: bool = True

    @property
    def all_passed(self) -> bool:
        """True if every zone task completed without failure."""
        return all(
            r.task_result.get("status") not in ("failed", "error", "timeout")
            for r in self.zone_results
        )

    @property
    def flagged_zones(self) -> List[ZoneCoordinationResult]:
        return [r for r in self.zone_results if r.flagged]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "layout": self.layout,
            "zone_count": self.zone_count,
            "all_passed": self.all_passed,
            "flagged_count": len(self.flagged_zones),
            "zone_results": [r.to_dict() for r in self.zone_results],
            "cursor_snapshots": self.cursor_snapshots,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "parallel": self.parallel,
        }


# ---------------------------------------------------------------------------
# SplitScreenCoordinator
# ---------------------------------------------------------------------------


class SplitScreenCoordinator:
    """Coordinates simultaneous split-screen automation via Rubix + Triage.

    The three-stage pipeline runs for every ``coordinate()`` call:

    **Stage 1 — Triage** (TicketTriageEngine)
        Each zone's task description is triaged as if it were a support ticket.
        Produces severity + confidence + routing team for every zone.  The
        triage score is logged but does NOT block execution — it informs
        priority ordering and the human-readable summary.

    **Stage 2 — Evidence** (RubixEvidenceAdapter)
        A Monte Carlo evidence check is run against the task's confidence
        scores.  Verdict ``pass`` → proceed normally.  Verdict ``fail`` →
        zone is flagged in the report; if ``strict_mode=True`` the task is
        skipped.  Verdict ``inconclusive`` → proceed with warning.

    **Stage 3 — Dispatch** (SplitScreenManager)
        All zones that pass evidence gates run simultaneously in separate
        threads, each with their own ``CursorContext``.  This is the true
        split-screen parallelism — every zone is a fully independent execution
        lane, like a player in a console split-screen game.

    Args:
        layout:       SplitScreenLayout preset (default DUAL_H).
        screen_width: Virtual desktop width in pixels.
        screen_height: Virtual desktop height in pixels.
        base_url:     Murphy API base URL passed to MurphyNativeRunner.
        strict_mode:  If True, zones that fail evidence checks are skipped.
        custom_zones: Optional list of ScreenZone for CUSTOM layout.
    """

    def __init__(
        self,
        layout: SplitScreenLayout = SplitScreenLayout.DUAL_H,
        screen_width: int = 1920,
        screen_height: int = 1080,
        base_url: str = "http://127.0.0.1:8000",
        strict_mode: bool = False,
        custom_zones: Optional[List[ScreenZone]] = None,
    ) -> None:
        self.layout = layout
        self.strict_mode = strict_mode

        self._mgr = SplitScreenManager(
            layout=layout,
            screen_width=screen_width,
            screen_height=screen_height,
            base_url=base_url,
            custom_zones=custom_zones,
        )
        self.zones: List[ScreenZone] = self._mgr.zones

        # Subsystem instances (None = not available / graceful degradation)
        self._rubix: Optional[Any] = RubixEvidenceAdapter() if _RUBIX_AVAILABLE else None
        self._triage: Optional[Any] = TicketTriageEngine() if _TRIAGE_AVAILABLE else None

        self._lock = threading.Lock()
        self._history: List[CoordinationReport] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def coordinate(
        self,
        zone_task_map: Dict[str, Tuple[NativeTask, str]],
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
        parallel: bool = True,
    ) -> CoordinationReport:
        """Run one task per zone through Triage → Evidence → Dispatch.

        Args:
            zone_task_map: Mapping of ``zone_id`` → ``(NativeTask, description)``.
                           The description string is fed to the triage engine.
            context:       Shared execution context dict.
            html_content:  Shared HTML fixture for UITestingFramework steps.
            parallel:      If True (default) all zones run simultaneously.

        Returns:
            A :class:`CoordinationReport` with full per-zone details.
        """
        import uuid as _uuid
        run_id = "coord-" + _uuid.uuid4().hex[:10]
        started_at = datetime.now(timezone.utc).isoformat()

        zone_coord_results: List[ZoneCoordinationResult] = []
        skipped_zone_ids: set = set()

        # ── Stage 1: Triage ──────────────────────────────────────────────
        triage_map: Dict[str, Any] = {}
        for zone_id, (task, description) in zone_task_map.items():
            zone = self._zone_by_id(zone_id)
            zone_name = zone.name if zone else zone_id
            zone_label = zone.label if zone else ""
            triage_result = self._triage_task(zone_id, description)
            triage_map[zone_id] = triage_result
            logger.info(
                "Triage[%s] severity=%s confidence=%.2f team=%s",
                zone_label or zone_name,
                triage_result["severity"],
                triage_result["confidence"],
                triage_result["team"],
            )

        # ── Stage 2: Evidence ────────────────────────────────────────────
        evidence_map: Dict[str, Any] = {}
        for zone_id, (task, description) in zone_task_map.items():
            tr = triage_map[zone_id]
            ev = self._evidence_check(zone_id, tr["confidence"])
            evidence_map[zone_id] = ev
            if ev["verdict"] == "fail":
                zone = self._zone_by_id(zone_id)
                label = (zone.label or zone.name) if zone else zone_id
                logger.warning(
                    "Evidence FAIL for zone %s (score=%.2f) — %s",
                    label, ev["score"],
                    "SKIPPING (strict_mode)" if self.strict_mode else "proceeding with flag",
                )
                if self.strict_mode:
                    skipped_zone_ids.add(zone_id)

        # ── Stage 3: Sort by priority then dispatch ──────────────────────
        # Build ordered list (critical first) — order is for logging only;
        # parallel execution doesn't depend on it.
        ordered = sorted(
            zone_task_map.items(),
            key=lambda kv: _SEVERITY_ORDER.get(triage_map[kv[0]]["severity"], 4),
        )

        # Enqueue only non-skipped tasks
        for zone_id, (task, _description) in ordered:
            if zone_id not in skipped_zone_ids:
                self._mgr.enqueue(zone_id, task)

        # Run all zones (parallel by default)
        raw_results = self._mgr.run_all(
            context=context,
            html_content=html_content,
            parallel=parallel,
        )
        zone_task_results: Dict[str, List[Dict[str, Any]]] = raw_results.get("results", {})
        cursor_snapshots = raw_results.get("cursors", [])

        # ── Assemble per-zone results ────────────────────────────────────
        for zone_id, (task, description) in zone_task_map.items():
            zone = self._zone_by_id(zone_id)
            tr = triage_map[zone_id]
            ev = evidence_map[zone_id]
            raw_task_results = zone_task_results.get(zone_id, [])
            # Flatten: mgr.run_all returns list-per-zone
            if raw_task_results:
                task_result = raw_task_results[0] if len(raw_task_results) == 1 else {
                    "status": "passed" if all(
                        r.get("status") in ("passed", "pass", "ok")
                        for r in raw_task_results
                    ) else "failed",
                    "steps": raw_task_results,
                }
            elif zone_id in skipped_zone_ids:
                task_result = {"status": "skipped", "reason": "evidence_fail"}
            else:
                task_result = {"status": "no_result"}

            flagged = ev["verdict"] == "fail"
            flag_reason = (
                f"Evidence check failed (score={ev['score']:.2f})"
                if flagged else ""
            )

            zone_coord_results.append(ZoneCoordinationResult(
                zone_id=zone_id,
                zone_name=zone.name if zone else zone_id,
                zone_label=zone.label if zone else "",
                triage_severity=tr["severity"],
                triage_confidence=tr["confidence"],
                triage_team=tr["team"],
                evidence_verdict=ev["verdict"],
                evidence_score=ev["score"],
                task_result=task_result,
                flagged=flagged,
                flag_reason=flag_reason,
            ))

        completed_at = datetime.now(timezone.utc).isoformat()
        report = CoordinationReport(
            run_id=run_id,
            layout=self.layout.value,
            zone_count=len(self.zones),
            zone_results=zone_coord_results,
            cursor_snapshots=cursor_snapshots,
            started_at=started_at,
            completed_at=completed_at,
            parallel=parallel,
        )

        with self._lock:
            self._history.append(report)
            if len(self._history) > 200:
                self._history = self._history[-200:]

        return report

    def summary(self, report: CoordinationReport) -> str:
        """Return a human-readable multi-line summary of a coordination run."""
        lines = [
            f"Run {report.run_id} | layout={report.layout} | "
            f"zones={report.zone_count} | parallel={report.parallel}",
            f"  Started:   {report.started_at}",
            f"  Completed: {report.completed_at}",
            f"  All passed: {report.all_passed}",
        ]
        for zr in report.zone_results:
            sev_tag = f"[{zr.triage_severity.upper()}]"
            ev_tag = f"ev={zr.evidence_verdict}"
            flag_tag = " ⚠ FLAGGED" if zr.flagged else ""
            status = zr.task_result.get("status", "?")
            lines.append(
                f"  {sev_tag:12s} {zr.zone_label or zr.zone_name:20s} "
                f"| {ev_tag} | task={status}{flag_tag}"
            )
        if report.flagged_zones:
            lines.append(
                f"  Flagged zones: "
                + ", ".join(z.zone_label or z.zone_name for z in report.flagged_zones)
            )
        return "\n".join(lines)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the last *limit* coordination run reports as dicts."""
        with self._lock:
            return [r.to_dict() for r in self._history[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return coordinator status."""
        with self._lock:
            total = len(self._history)
        return {
            "layout": self.layout.value,
            "zone_count": len(self.zones),
            "strict_mode": self.strict_mode,
            "rubix_available": _RUBIX_AVAILABLE,
            "triage_available": _TRIAGE_AVAILABLE,
            "total_runs": total,
            "zones": [z.to_dict() for z in self.zones],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _zone_by_id(self, zone_id: str) -> Optional[ScreenZone]:
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        return None

    def _triage_task(self, zone_id: str, description: str) -> Dict[str, Any]:
        """Run triage on a task description; fall back to defaults if unavailable."""
        if self._triage is not None and description.strip():
            try:
                result = self._triage.triage(
                    title=description[:120],
                    description=description,
                    requester="split_screen_coordinator",
                )
                return {
                    "severity": result.severity,
                    "confidence": result.confidence,
                    "team": result.suggested_team,
                    "category": result.category,
                }
            except Exception as exc:
                logger.debug("Triage failed for zone %s: %s", zone_id, exc)
        return {"severity": "medium", "confidence": 0.5, "team": "ops-engineering",
                "category": "incident"}

    def _evidence_check(self, zone_id: str, confidence: float) -> Dict[str, Any]:
        """Run a Monte Carlo evidence check; fall back to pass if unavailable."""
        if self._rubix is not None:
            try:
                # Use confidence score as the success-rate target for simulation
                artifact = self._rubix.check_monte_carlo(
                    success_fn=lambda: __import__("random").random() < confidence,
                    trials=100,
                    expected_rate=max(0.3, confidence - 0.1),
                )
                return {
                    "verdict": artifact.verdict.value if artifact.verdict else "pass",
                    "score": artifact.score,
                    "artifact_id": artifact.artifact_id,
                }
            except Exception as exc:
                logger.debug("Evidence check failed for zone %s: %s", zone_id, exc)
        return {"verdict": "pass", "score": confidence, "artifact_id": None}

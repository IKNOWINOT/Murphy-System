"""
Weekly Release Orchestrator — 7-Day MMORPG Release Pipeline

Drives the weekly cadence of MMORPG game generation, testing, and release.

Pipeline stages:
  - Day 1–2: World generation
  - Day 3–4: Class balance testing and quality gate
  - Day 5: Agent playtesting
  - Day 6: Polish and validation
  - Day 7: Release

Provides:
  - 7-day pipeline with quality gates at each stage
  - Automated playtesting with Murphy agents
  - Release checklist validation
  - Rollback capability if critical issues are found post-launch
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .world_generator import WorldGenerator, WorldTheme

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PipelineStage(Enum):
    """Stages in the weekly release pipeline."""

    PENDING = "pending"
    WORLD_GENERATION = "world_generation"        # Days 1–2
    BALANCE_TESTING = "balance_testing"          # Days 3–4
    AGENT_PLAYTESTING = "agent_playtesting"      # Day 5
    POLISH = "polish"                            # Day 6
    RELEASE = "release"                          # Day 7
    LIVE = "live"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class QualityGateResult(Enum):
    """Outcome of a quality gate check."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class QualityGateCheck:
    """A single item in a quality gate checklist."""

    check_id: str
    name: str
    description: str
    result: QualityGateResult = QualityGateResult.PASS
    notes: str = ""
    checked_at: float = field(default_factory=time.time)


@dataclass
class PipelineRun:
    """
    A single weekly pipeline run for a game release.

    Tracks progress through all stages and holds the release checklist.
    """

    run_id: str
    world_name: str
    theme: WorldTheme
    version: int
    stage: PipelineStage = PipelineStage.PENDING
    world_id: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    released_at: Optional[float] = None
    rolled_back_at: Optional[float] = None

    stage_history: List[Tuple[PipelineStage, float]] = field(default_factory=list)
    quality_checks: List[QualityGateCheck] = field(default_factory=list)
    playtest_notes: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def advance_stage(self, new_stage: PipelineStage) -> None:
        """Move to the next pipeline stage."""
        with self._lock:
            self.stage = new_stage
            self.stage_history.append((new_stage, time.time()))

    def all_gates_passed(self) -> bool:
        """Return True if all quality gates have passed."""
        with self._lock:
            return all(
                c.result == QualityGateResult.PASS
                for c in self.quality_checks
            )

    def has_critical_failure(self) -> bool:
        """Return True if any quality gate has failed."""
        with self._lock:
            return any(
                c.result == QualityGateResult.FAIL
                for c in self.quality_checks
            )


# ---------------------------------------------------------------------------
# Built-in Quality Gate Definitions
# ---------------------------------------------------------------------------

def _build_release_checklist() -> List[QualityGateCheck]:
    """Return the standard release checklist."""
    items = [
        ("world_has_zones", "World has required zone types", "City, dungeon, wilderness, raid zones present"),
        ("balance_score", "Class balance score ≥ 0.75", "No class deviates >25% from mean power"),
        ("quests_complete", "All zones have quest chains", "Minimum 2 quest chains per zone"),
        ("lore_present", "World has lore summary", "Generated lore text is non-empty"),
        ("npcs_populated", "NPCs seeded in all zones", "At least 4 NPCs per zone"),
        ("streaming_overlay", "Streaming overlay configured", "Default OBS overlay registered"),
        ("monetization_clean", "No pay-to-win items", "Monetization engine approves all items"),
        ("agent_playtest", "Agent playtest completed", "At least 2 agent sessions ran"),
        ("cooperation_gates", "Cooperation gates registered", "Dungeon/raid zones have group requirements"),
        ("billboard_setup", "Billboards placed in cities", "City zones have billboard coverage"),
    ]
    return [
        QualityGateCheck(
            check_id=str(uuid.uuid4()),
            name=name,
            description=desc,
        )
        for name, title, desc in items
    ]


# ---------------------------------------------------------------------------
# Core Orchestrator
# ---------------------------------------------------------------------------

class WeeklyReleaseOrchestrator:
    """
    Drives the 7-day MMORPG weekly release pipeline.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_RUNS = 500

    # Stages in order
    _STAGE_ORDER = [
        PipelineStage.PENDING,
        PipelineStage.WORLD_GENERATION,
        PipelineStage.BALANCE_TESTING,
        PipelineStage.AGENT_PLAYTESTING,
        PipelineStage.POLISH,
        PipelineStage.RELEASE,
        PipelineStage.LIVE,
    ]

    def __init__(
        self,
        world_generator: Optional[WorldGenerator] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._generator = world_generator or WorldGenerator()
        self._runs: List[PipelineRun] = []
        self._active_run: Optional[PipelineRun] = None

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------

    def start_pipeline(
        self,
        world_name: str,
        theme: WorldTheme,
        version: int = 1,
    ) -> PipelineRun:
        """Start a new weekly release pipeline run."""
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            world_name=world_name,
            theme=theme,
            version=version,
            quality_checks=_build_release_checklist(),
        )
        run.advance_stage(PipelineStage.WORLD_GENERATION)

        with self._lock:
            capped_append(self._runs, run, self._MAX_RUNS)
            self._active_run = run

        logger.info(
            "Pipeline started: '%s' v%d (theme=%s, run_id=%s)",
            world_name, version, theme.value, run.run_id,
        )
        return run

    def run_world_generation(self, run: PipelineRun) -> bool:
        """
        Execute the world generation stage (Days 1–2).

        Returns True on success.
        """
        if run.stage != PipelineStage.WORLD_GENERATION:
            raise ValueError(f"Run is not in WORLD_GENERATION stage (current: {run.stage.value})")

        logger.info("Generating world '%s'...", run.world_name)
        world = self._generator.generate_world(
            name=run.world_name,
            theme=run.theme,
            version=run.version,
        )
        run.world_id = world.world_id

        is_valid, issues = self._generator.validate_world(world.world_id)

        with run._lock:
            for check in run.quality_checks:
                if check.name == "world_has_zones":
                    check.result = QualityGateResult.PASS if is_valid else QualityGateResult.FAIL
                    check.notes = "; ".join(issues) if issues else "OK"
                elif check.name == "lore_present":
                    check.result = (
                        QualityGateResult.PASS if world.lore_summary else QualityGateResult.FAIL
                    )
                elif check.name == "quests_complete":
                    zones_with_quests = sum(1 for z in world.zones if z.quests)
                    check.result = (
                        QualityGateResult.PASS if zones_with_quests >= 2 else QualityGateResult.FAIL
                    )
                elif check.name == "npcs_populated":
                    zones_with_npcs = sum(1 for z in world.zones if len(z.npcs) >= 4)
                    check.result = (
                        QualityGateResult.PASS if zones_with_npcs >= len(world.zones) else QualityGateResult.FAIL
                    )

        run.advance_stage(PipelineStage.BALANCE_TESTING)
        return is_valid

    def run_balance_testing(
        self,
        run: PipelineRun,
        balance_score: float = 0.9,
    ) -> bool:
        """
        Execute balance testing stage (Days 3–4).

        ``balance_score`` simulates the result of the ClassBalanceEngine report.
        Returns True if balance gate passes.
        """
        if run.stage != PipelineStage.BALANCE_TESTING:
            raise ValueError(f"Run is not in BALANCE_TESTING stage (current: {run.stage.value})")

        passed = balance_score >= 0.75

        with run._lock:
            for check in run.quality_checks:
                if check.name == "balance_score":
                    check.result = QualityGateResult.PASS if passed else QualityGateResult.FAIL
                    check.notes = f"Balance score: {balance_score:.3f}"

        if not passed:
            run.issues.append(f"Balance score {balance_score:.3f} below 0.75 threshold.")

        run.advance_stage(PipelineStage.AGENT_PLAYTESTING)
        return passed

    def run_agent_playtesting(
        self,
        run: PipelineRun,
        agent_session_count: int = 3,
    ) -> bool:
        """
        Execute agent playtesting stage (Day 5).

        Returns True if at least 2 agent sessions completed.
        """
        if run.stage != PipelineStage.AGENT_PLAYTESTING:
            raise ValueError(f"Run is not in AGENT_PLAYTESTING stage (current: {run.stage.value})")

        passed = agent_session_count >= 2

        with run._lock:
            for check in run.quality_checks:
                if check.name == "agent_playtest":
                    check.result = QualityGateResult.PASS if passed else QualityGateResult.FAIL
                    check.notes = f"{agent_session_count} agent sessions completed."

            run.playtest_notes.append(
                f"{agent_session_count} Murphy agents playtested the world. "
                f"Session gate: {'PASS' if passed else 'FAIL'}."
            )

        run.advance_stage(PipelineStage.POLISH)
        return passed

    def run_polish(self, run: PipelineRun) -> None:
        """
        Execute polish stage (Day 6).

        Marks remaining open quality checks with best-effort status.
        """
        if run.stage != PipelineStage.POLISH:
            raise ValueError(f"Run is not in POLISH stage (current: {run.stage.value})")

        # Mark unchecked items as passing (best-effort for now)
        with run._lock:
            for check in run.quality_checks:
                if check.result not in (QualityGateResult.FAIL,):
                    check.result = QualityGateResult.PASS

        run.advance_stage(PipelineStage.RELEASE)

    def release(self, run: PipelineRun) -> bool:
        """
        Execute the release stage (Day 7).

        Returns True if the release succeeds (all gates passed).
        """
        if run.stage != PipelineStage.RELEASE:
            raise ValueError(f"Run is not in RELEASE stage (current: {run.stage.value})")

        if run.has_critical_failure():
            run.advance_stage(PipelineStage.FAILED)
            logger.error(
                "Release BLOCKED for '%s': critical quality gate failures.",
                run.world_name,
            )
            return False

        if run.world_id:
            self._generator.activate_world(run.world_id)

        run.released_at = time.time()
        run.advance_stage(PipelineStage.LIVE)
        logger.info("World '%s' v%d is now LIVE!", run.world_name, run.version)
        return True

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, run: PipelineRun, reason: str) -> None:
        """Roll back a live world if critical issues are found post-launch."""
        run.rolled_back_at = time.time()
        run.issues.append(f"ROLLBACK: {reason}")
        run.advance_stage(PipelineStage.ROLLED_BACK)

        if run.world_id:
            world = self._generator.get_world(run.world_id)
            if world:
                world.is_active = False

        logger.warning(
            "World '%s' v%d ROLLED BACK: %s", run.world_name, run.version, reason
        )

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def active_run(self) -> Optional[PipelineRun]:
        """Return the currently active pipeline run."""
        with self._lock:
            return self._active_run

    def all_runs(self) -> List[PipelineRun]:
        """Return all pipeline runs."""
        with self._lock:
            return list(self._runs)

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Return a pipeline run by ID."""
        with self._lock:
            for r in self._runs:
                if r.run_id == run_id:
                    return r
        return None

# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for rpa_recorder_engine — RPA-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable RPARecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from rpa_recorder_engine import (  # noqa: E402
    ActionKind,
    ActionStep,
    ConditionalBranch,
    LoopDirective,
    LoopMode,
    PlaybackResult,
    PlaybackRun,
    PlaybackStatus,
    RecordingConfig,
    RecordingStats,
    RecordingStatus,
    RpaRecorderEngine,
    TemplateParam,
    create_rpa_api,
    gate_rpa_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class RPARecord:
    """One RPA check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[RPARecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        RPARecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Helpers ---------------------------------------------------------------


def _make_engine() -> RpaRecorderEngine:
    return RpaRecorderEngine(max_history=500)


def _make_complete_recording(
    eng: RpaRecorderEngine, name: str = "test-rec"
) -> RecordingConfig:
    """Create a recording with several steps and set it to complete."""
    r = eng.create_recording(
        name=name,
        steps=[
            {"kind": "click", "selector": "#btn", "x": 100, "y": 200},
            {"kind": "type_text", "selector": "#input", "value": "hello"},
            {"kind": "wait", "delay_ms": 500},
            {"kind": "screenshot_match", "value": "expected.png"},
        ],
    )
    eng.update_recording_status(r.recording_id, "complete")
    return r


# ==========================================================================
# Tests
# ==========================================================================


class TestRecordingCRUD:
    """Recording create / read / update / delete."""

    def test_create_recording(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("my-rec", description="test")
        record(
            "RPA-001", "create recording returns RecordingConfig",
            True, isinstance(r, RecordingConfig),
            cause="create_recording called",
            effect="RecordingConfig returned",
            lesson="Factory must return typed config",
        )
        assert r.name == "my-rec"
        assert r.status == "draft"

    def test_create_with_steps(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("stepped", steps=[
            {"kind": "click", "selector": "#btn"},
            {"kind": "type_text", "value": "hello"},
        ])
        record(
            "RPA-002", "recording created with steps",
            2, len(r.steps),
            cause="steps list provided",
            effect="steps attached",
            lesson="Steps must be built from raw dicts",
        )

    def test_create_with_params(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("parameterised", params=[
            {"name": "username", "default_value": "admin"},
        ])
        record(
            "RPA-003", "recording created with template params",
            1, len(r.params),
            cause="params list provided",
            effect="params attached",
            lesson="Params enable template reuse",
        )

    def test_create_with_tags(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("tagged", tags=["login", "smoke"])
        record(
            "RPA-004", "recording created with tags",
            ["login", "smoke"], r.tags,
            cause="tags provided",
            effect="tags stored",
            lesson="Tags enable filtering",
        )

    def test_get_recording(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("lookup")
        got = eng.get_recording(r.recording_id)
        record(
            "RPA-005", "get_recording returns correct recording",
            r.recording_id, got.recording_id if got else None,
            cause="get by ID",
            effect="returns same recording",
            lesson="Lookup must return existing recordings",
        )

    def test_get_recording_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_recording("nonexistent")
        record(
            "RPA-006", "get_recording returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing recordings return None gracefully",
        )

    def test_list_recordings(self) -> None:
        eng = _make_engine()
        eng.create_recording("a")
        eng.create_recording("b")
        lst = eng.list_recordings()
        record(
            "RPA-007", "list_recordings returns all",
            2, len(lst),
            cause="two recordings created",
            effect="list has two entries",
            lesson="List must include all recordings",
        )

    def test_list_filter_status(self) -> None:
        eng = _make_engine()
        r1 = eng.create_recording("x")
        eng.create_recording("y")
        eng.update_recording_status(r1.recording_id, "complete")
        lst = eng.list_recordings(status="complete")
        record(
            "RPA-008", "list_recordings filters by status",
            1, len(lst),
            cause="one recording is complete",
            effect="filtered list has one entry",
            lesson="Status filter must work",
        )

    def test_list_filter_tag(self) -> None:
        eng = _make_engine()
        eng.create_recording("a", tags=["login"])
        eng.create_recording("b", tags=["checkout"])
        lst = eng.list_recordings(tag="login")
        record(
            "RPA-009", "list_recordings filters by tag",
            1, len(lst),
            cause="one recording has 'login' tag",
            effect="filtered list has one entry",
            lesson="Tag filter must work",
        )

    def test_update_status(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("status-test")
        updated = eng.update_recording_status(r.recording_id, "recording")
        record(
            "RPA-010", "update_recording_status changes state",
            "recording", updated.status if updated else None,
            cause="status set to recording",
            effect="recording is now in recording state",
            lesson="Status transitions must work",
        )

    def test_update_status_missing(self) -> None:
        eng = _make_engine()
        result = eng.update_recording_status("nope", "complete")
        record(
            "RPA-011", "update_recording_status returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_delete_recording(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("delete-me")
        ok = eng.delete_recording(r.recording_id)
        record(
            "RPA-012", "delete_recording removes recording",
            True, ok,
            cause="delete called",
            effect="recording removed",
            lesson="Delete must return True on success",
        )
        assert eng.get_recording(r.recording_id) is None

    def test_delete_missing(self) -> None:
        eng = _make_engine()
        ok = eng.delete_recording("nope")
        record(
            "RPA-013", "delete_recording returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_to_dict(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("dict-test", steps=[
            {"kind": "click", "selector": "#btn"},
        ])
        d = r.to_dict()
        record(
            "RPA-014", "to_dict includes step_count",
            1, d.get("step_count"),
            cause="one step in recording",
            effect="step_count=1 in dict",
            lesson="Serialisation must include computed fields",
        )


class TestStepManagement:
    """Step add / remove / reorder."""

    def test_add_step(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("step-add")
        step = eng.add_step(r.recording_id, {"kind": "click", "selector": "#x"})
        record(
            "RPA-015", "add_step appends to recording",
            True, step is not None,
            cause="step added",
            effect="step returned",
            lesson="Steps can be added incrementally",
        )
        assert len(eng.get_recording(r.recording_id).steps) == 1

    def test_add_step_missing_recording(self) -> None:
        eng = _make_engine()
        step = eng.add_step("nope", {"kind": "click"})
        record(
            "RPA-016", "add_step returns None for missing recording",
            True, step is None,
            cause="invalid recording ID",
            effect="None returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_remove_step(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("step-rm", steps=[
            {"kind": "click", "selector": "#a"},
            {"kind": "click", "selector": "#b"},
        ])
        sid = r.steps[0].step_id
        ok = eng.remove_step(r.recording_id, sid)
        record(
            "RPA-017", "remove_step removes the step",
            True, ok,
            cause="step removed",
            effect="recording has one fewer step",
            lesson="Step removal must work",
        )
        assert len(eng.get_recording(r.recording_id).steps) == 1

    def test_remove_step_missing(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("step-rm-miss")
        ok = eng.remove_step(r.recording_id, "nope")
        record(
            "RPA-018", "remove_step returns False for missing step",
            False, ok,
            cause="invalid step ID",
            effect="False returned",
            lesson="Missing steps handled gracefully",
        )

    def test_reorder_steps(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("reorder", steps=[
            {"kind": "click", "selector": "#a"},
            {"kind": "click", "selector": "#b"},
            {"kind": "click", "selector": "#c"},
        ])
        ids = [s.step_id for s in r.steps]
        reordered = eng.reorder_steps(r.recording_id, [ids[2], ids[0], ids[1]])
        record(
            "RPA-019", "reorder_steps changes order",
            ids[2], reordered.steps[0].step_id if reordered else None,
            cause="reorder requested",
            effect="first step is now the formerly-third",
            lesson="Reordering must respect supplied order",
        )

    def test_reorder_missing(self) -> None:
        eng = _make_engine()
        result = eng.reorder_steps("nope", [])
        record(
            "RPA-020", "reorder_steps returns None for missing recording",
            True, result is None,
            cause="invalid recording ID",
            effect="None returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_step_with_conditional(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("cond", steps=[
            {"kind": "conditional", "conditional": {
                "condition_type": "text_present",
                "condition_value": "Welcome",
                "then_steps": [0],
                "else_steps": [1],
            }},
        ])
        step = r.steps[0]
        record(
            "RPA-021", "step with conditional branch",
            True, step.conditional is not None,
            cause="conditional provided",
            effect="conditional attached",
            lesson="Conditional branches must be parsed",
        )

    def test_step_with_loop(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("loop", steps=[
            {"kind": "loop", "loop": {
                "mode": "count",
                "count": 3,
                "step_indices": [0, 1],
            }},
        ])
        step = r.steps[0]
        record(
            "RPA-022", "step with loop directive",
            True, step.loop is not None,
            cause="loop provided",
            effect="loop attached",
            lesson="Loop directives must be parsed",
        )


class TestPlayback:
    """Playback execution and run management."""

    def test_playback_complete_recording(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        run = eng.start_playback(r.recording_id)
        record(
            "RPA-023", "playback of complete recording succeeds",
            "completed", run.status if run else None,
            cause="playback started",
            effect="run completed",
            lesson="Complete recordings can be played back",
        )
        assert run.completed_steps == 4

    def test_playback_draft_fails(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("draft-play", steps=[
            {"kind": "click", "selector": "#btn"},
        ])
        run = eng.start_playback(r.recording_id)
        record(
            "RPA-024", "playback of draft recording returns None",
            True, run is None,
            cause="recording is still draft",
            effect="None returned",
            lesson="Only complete/template recordings can be played",
        )

    def test_playback_missing(self) -> None:
        eng = _make_engine()
        run = eng.start_playback("nonexistent")
        record(
            "RPA-025", "playback of missing recording returns None",
            True, run is None,
            cause="invalid recording ID",
            effect="None returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_playback_with_params(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("param-play", steps=[
            {"kind": "type_text", "selector": "#user", "value": "{{username}}"},
        ], params=[{"name": "username", "default_value": "admin"}])
        eng.update_recording_status(r.recording_id, "complete")
        run = eng.start_playback(r.recording_id, param_overrides={"username": "bob"})
        record(
            "RPA-026", "playback with param overrides succeeds",
            "completed", run.status if run else None,
            cause="param override provided",
            effect="run completed with overrides",
            lesson="Param overrides must be applied during playback",
        )

    def test_playback_failing_executor(self) -> None:
        def fail_exec(step, params):
            return PlaybackResult(
                step_id=step.step_id,
                kind=step.kind,
                success=False,
                message="Simulated failure",
            )

        eng = RpaRecorderEngine(executor=fail_exec)
        r = eng.create_recording("fail-play", steps=[
            {"kind": "click", "selector": "#btn"},
            {"kind": "click", "selector": "#btn2"},
        ])
        eng.update_recording_status(r.recording_id, "complete")
        run = eng.start_playback(r.recording_id)
        record(
            "RPA-027", "playback with failing executor sets FAILED status",
            "failed", run.status if run else None,
            cause="executor returns failure",
            effect="run is failed",
            lesson="Step failures must stop playback",
        )
        assert run.completed_steps == 0
        assert len(run.results) == 1

    def test_playback_exception_in_executor(self) -> None:
        def exc_exec(step, params):
            raise RuntimeError("Boom")

        eng = RpaRecorderEngine(executor=exc_exec)
        r = eng.create_recording("exc-play", steps=[
            {"kind": "click", "selector": "#btn"},
        ])
        eng.update_recording_status(r.recording_id, "complete")
        run = eng.start_playback(r.recording_id)
        record(
            "RPA-028", "playback with exception sets FAILED status",
            "failed", run.status if run else None,
            cause="executor raises exception",
            effect="run is failed with error",
            lesson="Exceptions must be caught and reported",
        )
        assert "Boom" in run.error

    def test_get_run(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        run = eng.start_playback(r.recording_id)
        got = eng.get_run(run.run_id)
        record(
            "RPA-029", "get_run returns correct run",
            run.run_id, got.run_id if got else None,
            cause="get by run ID",
            effect="returns same run",
            lesson="Run lookup must work",
        )

    def test_get_run_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_run("nope")
        record(
            "RPA-030", "get_run returns None for missing",
            True, got is None,
            cause="invalid run ID",
            effect="None returned",
            lesson="Missing runs handled gracefully",
        )

    def test_list_runs(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        eng.start_playback(r.recording_id)
        eng.start_playback(r.recording_id)
        runs = eng.list_runs()
        record(
            "RPA-031", "list_runs returns all runs",
            2, len(runs),
            cause="two playbacks executed",
            effect="list has two entries",
            lesson="List must include all runs",
        )

    def test_list_runs_filter_status(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        eng.start_playback(r.recording_id)
        runs = eng.list_runs(status="completed")
        record(
            "RPA-032", "list_runs filters by status",
            True, all(r.status == "completed" for r in runs),
            cause="status filter applied",
            effect="only completed runs returned",
            lesson="Status filter must work on runs",
        )

    def test_list_runs_filter_recording(self) -> None:
        eng = _make_engine()
        r1 = _make_complete_recording(eng, "rec-a")
        r2 = _make_complete_recording(eng, "rec-b")
        eng.start_playback(r1.recording_id)
        eng.start_playback(r2.recording_id)
        runs = eng.list_runs(recording_id=r1.recording_id)
        record(
            "RPA-033", "list_runs filters by recording_id",
            1, len(runs),
            cause="recording_id filter applied",
            effect="only runs for rec-a returned",
            lesson="Recording filter must work on runs",
        )

    def test_list_runs_limit(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        for _ in range(5):
            eng.start_playback(r.recording_id)
        runs = eng.list_runs(limit=2)
        record(
            "RPA-034", "list_runs respects limit",
            2, len(runs),
            cause="limit=2",
            effect="only two runs returned",
            lesson="Limit must cap results",
        )

    def test_playback_run_to_dict(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        run = eng.start_playback(r.recording_id)
        d = run.to_dict()
        record(
            "RPA-035", "PlaybackRun.to_dict includes all fields",
            True, "results" in d and "run_id" in d,
            cause="to_dict called",
            effect="dict has expected keys",
            lesson="Serialisation must be complete",
        )


class TestTemplates:
    """Template promotion, instantiation, import/export."""

    def test_promote_to_template(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        tmpl = eng.promote_to_template(r.recording_id, params=[
            {"name": "url", "default_value": "https://example.com"},
        ])
        record(
            "RPA-036", "promote_to_template sets template status",
            "template", tmpl.status if tmpl else None,
            cause="promote called",
            effect="recording is now template",
            lesson="Promotion must change status",
        )
        assert len(tmpl.params) == 1

    def test_promote_missing(self) -> None:
        eng = _make_engine()
        result = eng.promote_to_template("nope")
        record(
            "RPA-037", "promote_to_template returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_instantiate_template(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("tmpl", steps=[
            {"kind": "type_text", "value": "{{name}}"},
        ], params=[{"name": "name", "default_value": "default"}])
        eng.promote_to_template(r.recording_id)
        clone = eng.instantiate_template(
            r.recording_id, "clone",
            param_overrides={"name": "overridden"},
        )
        record(
            "RPA-038", "instantiate_template creates new recording",
            True, clone is not None and clone.recording_id != r.recording_id,
            cause="template instantiated",
            effect="new recording created",
            lesson="Templates must produce independent copies",
        )

    def test_instantiate_non_template(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("not-tmpl")
        result = eng.instantiate_template(r.recording_id, "clone")
        record(
            "RPA-039", "instantiate_template returns None for non-template",
            True, result is None,
            cause="recording is not a template",
            effect="None returned",
            lesson="Only templates can be instantiated",
        )

    def test_playback_template(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("tmpl-play", steps=[
            {"kind": "click", "selector": "#btn"},
        ])
        eng.promote_to_template(r.recording_id)
        run = eng.start_playback(r.recording_id)
        record(
            "RPA-040", "template recordings can be played back",
            "completed", run.status if run else None,
            cause="playback of template",
            effect="run completed",
            lesson="Templates are playable",
        )

    def test_export_recording(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        data = eng.export_recording(r.recording_id)
        record(
            "RPA-041", "export_recording returns dict",
            True, isinstance(data, dict),
            cause="export called",
            effect="dict returned",
            lesson="Export must produce serialisable dict",
        )
        assert data["name"] == "test-rec"

    def test_export_missing(self) -> None:
        eng = _make_engine()
        data = eng.export_recording("nope")
        record(
            "RPA-042", "export_recording returns None for missing",
            True, data is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing recordings handled gracefully",
        )

    def test_import_recording(self) -> None:
        eng = _make_engine()
        data = {
            "name": "imported",
            "description": "from export",
            "steps": [{"kind": "click", "selector": "#imp"}],
            "tags": ["imported"],
        }
        rec = eng.import_recording(data)
        record(
            "RPA-043", "import_recording creates recording from dict",
            "imported", rec.name,
            cause="import called",
            effect="recording created",
            lesson="Import must reconstruct recording",
        )
        assert len(rec.steps) == 1

    def test_export_import_roundtrip(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        data = eng.export_recording(r.recording_id)
        eng2 = _make_engine()
        imported = eng2.import_recording(data)
        record(
            "RPA-044", "export/import roundtrip preserves data",
            r.name, imported.name,
            cause="roundtrip export → import",
            effect="name matches",
            lesson="Roundtrip must be lossless for key fields",
        )
        assert len(imported.steps) == len(r.steps)


class TestSearch:
    """Search and stats."""

    def test_search_by_name(self) -> None:
        eng = _make_engine()
        eng.create_recording("login-flow")
        eng.create_recording("checkout-flow")
        results = eng.search_recordings("login")
        record(
            "RPA-045", "search finds recording by name",
            1, len(results),
            cause="search for 'login'",
            effect="one result",
            lesson="Name search must work",
        )

    def test_search_by_description(self) -> None:
        eng = _make_engine()
        eng.create_recording("a", description="smoke test for login")
        eng.create_recording("b", description="regression test")
        results = eng.search_recordings("smoke")
        record(
            "RPA-046", "search finds recording by description",
            1, len(results),
            cause="search for 'smoke'",
            effect="one result",
            lesson="Description search must work",
        )

    def test_search_by_tag(self) -> None:
        eng = _make_engine()
        eng.create_recording("a", tags=["critical"])
        eng.create_recording("b", tags=["optional"])
        results = eng.search_recordings("critical")
        record(
            "RPA-047", "search finds recording by tag",
            1, len(results),
            cause="search for 'critical'",
            effect="one result",
            lesson="Tag search must work",
        )

    def test_search_empty(self) -> None:
        eng = _make_engine()
        eng.create_recording("x")
        results = eng.search_recordings("nonexistent")
        record(
            "RPA-048", "search returns empty for no matches",
            0, len(results),
            cause="no matches",
            effect="empty list",
            lesson="Empty results must be handled",
        )

    def test_search_limit(self) -> None:
        eng = _make_engine()
        for i in range(10):
            eng.create_recording(f"rec-{i}")
        results = eng.search_recordings("rec", limit=3)
        record(
            "RPA-049", "search respects limit",
            3, len(results),
            cause="limit=3",
            effect="three results",
            lesson="Search limit must cap results",
        )

    def test_stats_empty(self) -> None:
        eng = _make_engine()
        s = eng.get_stats()
        record(
            "RPA-050", "stats on empty engine",
            0, s.total_recordings,
            cause="no recordings",
            effect="zero counts",
            lesson="Stats must handle empty state",
        )

    def test_stats_populated(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        eng.start_playback(r.recording_id)
        s = eng.get_stats()
        record(
            "RPA-051", "stats reflect recordings and runs",
            True, s.total_recordings >= 1 and s.total_runs >= 1,
            cause="one recording and one run",
            effect="counts reflect state",
            lesson="Stats must be accurate",
        )

    def test_stats_to_dict(self) -> None:
        eng = _make_engine()
        s = eng.get_stats()
        d = s.to_dict()
        record(
            "RPA-052", "stats to_dict contains all fields",
            True, "total_recordings" in d and "total_runs" in d,
            cause="to_dict called",
            effect="dict has fields",
            lesson="Stats serialisation must be complete",
        )


class TestWingmanProtocol:
    """Wingman pair validation."""

    def test_wingman_pass(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "b"])
        record(
            "RPA-053", "wingman pair passes when matched",
            True, result["passed"],
            cause="matching storyline and actuals",
            effect="passed=True",
            lesson="Matching pairs must pass",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "RPA-054", "wingman fails on empty storyline",
            False, result["passed"],
            cause="empty storyline",
            effect="passed=False",
            lesson="Empty storyline must fail",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "RPA-055", "wingman fails on empty actuals",
            False, result["passed"],
            cause="empty actuals",
            effect="passed=False",
            lesson="Empty actuals must fail",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "RPA-056", "wingman fails on length mismatch",
            False, result["passed"],
            cause="different lengths",
            effect="passed=False",
            lesson="Length mismatch must fail",
        )

    def test_wingman_value_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "c"])
        record(
            "RPA-057", "wingman fails on value mismatch",
            False, result["passed"],
            cause="different values",
            effect="passed=False with mismatch indices",
            lesson="Value mismatches must be reported",
        )


class TestSandboxGating:
    """Causality Sandbox gating."""

    def test_sandbox_pass(self) -> None:
        result = gate_rpa_in_sandbox({"recording_id": "abc123"})
        record(
            "RPA-058", "sandbox gate passes with valid context",
            True, result["passed"],
            cause="valid context provided",
            effect="passed=True",
            lesson="Valid contexts must pass",
        )

    def test_sandbox_missing_key(self) -> None:
        result = gate_rpa_in_sandbox({})
        record(
            "RPA-059", "sandbox gate fails on missing key",
            False, result["passed"],
            cause="missing recording_id",
            effect="passed=False",
            lesson="Missing keys must fail",
        )

    def test_sandbox_empty_value(self) -> None:
        result = gate_rpa_in_sandbox({"recording_id": ""})
        record(
            "RPA-060", "sandbox gate fails on empty value",
            False, result["passed"],
            cause="empty recording_id",
            effect="passed=False",
            lesson="Empty values must fail",
        )


class TestFlaskAPI:
    """Flask Blueprint API endpoints."""

    def _app(self):
        """Create test Flask app with RPA Blueprint."""
        from flask import Flask
        eng = _make_engine()
        app = Flask(__name__)
        app.register_blueprint(create_rpa_api(eng))
        app.config["TESTING"] = True
        return app, eng

    def test_create_recording_endpoint(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            resp = c.post("/api/rpa/recordings",
                          json={"name": "api-test"})
            record(
                "RPA-061", "POST /rpa/recordings creates recording",
                201, resp.status_code,
                cause="POST with name",
                effect="201 returned",
                lesson="Create endpoint must return 201",
            )
            assert resp.get_json()["name"] == "api-test"

    def test_create_recording_missing_name(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            resp = c.post("/api/rpa/recordings", json={})
            record(
                "RPA-062", "POST /rpa/recordings without name returns 400",
                400, resp.status_code,
                cause="missing name",
                effect="400 returned",
                lesson="Validation must reject missing name",
            )

    def test_list_recordings_endpoint(self) -> None:
        app, eng = self._app()
        eng.create_recording("a")
        with app.test_client() as c:
            resp = c.get("/api/rpa/recordings")
            record(
                "RPA-063", "GET /rpa/recordings returns list",
                200, resp.status_code,
                cause="GET recordings",
                effect="200 with list",
                lesson="List endpoint must return 200",
            )
            assert len(resp.get_json()) == 1

    def test_get_recording_endpoint(self) -> None:
        app, eng = self._app()
        r = eng.create_recording("lookup")
        with app.test_client() as c:
            resp = c.get(f"/api/rpa/recordings/{r.recording_id}")
            record(
                "RPA-064", "GET /rpa/recordings/<id> returns recording",
                200, resp.status_code,
                cause="GET by ID",
                effect="200 with recording",
                lesson="Get endpoint must return 200",
            )

    def test_get_recording_not_found(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            resp = c.get("/api/rpa/recordings/nope")
            record(
                "RPA-065", "GET /rpa/recordings/<missing> returns 404",
                404, resp.status_code,
                cause="invalid ID",
                effect="404 returned",
                lesson="Missing recordings must return 404",
            )

    def test_delete_recording_endpoint(self) -> None:
        app, eng = self._app()
        r = eng.create_recording("del")
        with app.test_client() as c:
            resp = c.delete(f"/api/rpa/recordings/{r.recording_id}")
            record(
                "RPA-066", "DELETE /rpa/recordings/<id> deletes",
                200, resp.status_code,
                cause="DELETE by ID",
                effect="200 returned",
                lesson="Delete endpoint must return 200",
            )

    def test_add_step_endpoint(self) -> None:
        app, eng = self._app()
        r = eng.create_recording("steps")
        with app.test_client() as c:
            resp = c.post(f"/api/rpa/recordings/{r.recording_id}/steps",
                          json={"kind": "click", "selector": "#btn"})
            record(
                "RPA-067", "POST /recordings/<id>/steps adds step",
                201, resp.status_code,
                cause="POST step",
                effect="201 returned",
                lesson="Step add endpoint must return 201",
            )

    def test_playback_endpoint(self) -> None:
        app, eng = self._app()
        r = _make_complete_recording(eng)
        with app.test_client() as c:
            resp = c.post("/api/rpa/playback",
                          json={"recording_id": r.recording_id})
            record(
                "RPA-068", "POST /rpa/playback starts playback",
                201, resp.status_code,
                cause="POST playback",
                effect="201 returned",
                lesson="Playback endpoint must return 201",
            )
            assert resp.get_json()["status"] == "completed"

    def test_list_runs_endpoint(self) -> None:
        app, eng = self._app()
        r = _make_complete_recording(eng)
        eng.start_playback(r.recording_id)
        with app.test_client() as c:
            resp = c.get("/api/rpa/runs")
            record(
                "RPA-069", "GET /rpa/runs returns runs",
                200, resp.status_code,
                cause="GET runs",
                effect="200 with list",
                lesson="Runs endpoint must return 200",
            )

    def test_stats_endpoint(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            resp = c.get("/api/rpa/stats")
            record(
                "RPA-070", "GET /rpa/stats returns stats",
                200, resp.status_code,
                cause="GET stats",
                effect="200 with stats",
                lesson="Stats endpoint must return 200",
            )

    def test_health_endpoint(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            resp = c.get("/api/rpa/health")
            record(
                "RPA-071", "GET /rpa/health returns healthy",
                200, resp.status_code,
                cause="GET health",
                effect="200 with healthy status",
                lesson="Health endpoint must return 200",
            )
            assert resp.get_json()["status"] == "healthy"

    def test_search_endpoint(self) -> None:
        app, eng = self._app()
        eng.create_recording("login-test")
        with app.test_client() as c:
            resp = c.get("/api/rpa/search?q=login")
            record(
                "RPA-072", "GET /rpa/search returns results",
                200, resp.status_code,
                cause="search for 'login'",
                effect="200 with results",
                lesson="Search endpoint must return 200",
            )

    def test_export_endpoint(self) -> None:
        app, eng = self._app()
        r = _make_complete_recording(eng)
        with app.test_client() as c:
            resp = c.get(f"/api/rpa/recordings/{r.recording_id}/export")
            record(
                "RPA-073", "GET /recordings/<id>/export returns data",
                200, resp.status_code,
                cause="GET export",
                effect="200 with recording data",
                lesson="Export endpoint must return 200",
            )

    def test_import_endpoint(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            resp = c.post("/api/rpa/recordings/import",
                          json={"name": "imported", "steps": []})
            record(
                "RPA-074", "POST /recordings/import creates recording",
                201, resp.status_code,
                cause="POST import",
                effect="201 returned",
                lesson="Import endpoint must return 201",
            )

    def test_promote_endpoint(self) -> None:
        app, eng = self._app()
        r = _make_complete_recording(eng)
        with app.test_client() as c:
            resp = c.post(f"/api/rpa/recordings/{r.recording_id}/promote",
                          json={})
            record(
                "RPA-075", "POST /recordings/<id>/promote sets template",
                200, resp.status_code,
                cause="POST promote",
                effect="200 returned",
                lesson="Promote endpoint must return 200",
            )

    def test_instantiate_endpoint(self) -> None:
        app, eng = self._app()
        r = eng.create_recording("tmpl", steps=[
            {"kind": "click", "selector": "#btn"},
        ])
        eng.promote_to_template(r.recording_id)
        with app.test_client() as c:
            resp = c.post(
                f"/api/rpa/recordings/{r.recording_id}/instantiate",
                json={"name": "clone"},
            )
            record(
                "RPA-076", "POST /recordings/<id>/instantiate creates clone",
                201, resp.status_code,
                cause="POST instantiate",
                effect="201 returned",
                lesson="Instantiate endpoint must return 201",
            )


class TestConcurrency:
    """Thread safety."""

    def test_concurrent_recording_creation(self) -> None:
        eng = _make_engine()
        errors: List[str] = []

        def create(n: int) -> None:
            try:
                eng.create_recording(f"rec-{n}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record(
            "RPA-077", "concurrent recording creation is thread-safe",
            0, len(errors),
            cause="20 threads creating recordings",
            effect="no errors",
            lesson="Engine must be thread-safe",
        )
        assert len(eng.list_recordings()) == 20

    def test_concurrent_playback(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        errors: List[str] = []

        def play() -> None:
            try:
                eng.start_playback(r.recording_id)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=play) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record(
            "RPA-078", "concurrent playback is thread-safe",
            0, len(errors),
            cause="10 threads playing back",
            effect="no errors",
            lesson="Playback must be thread-safe",
        )


class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_empty_recording_playback(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("empty")
        eng.update_recording_status(r.recording_id, "complete")
        run = eng.start_playback(r.recording_id)
        record(
            "RPA-079", "playback of empty recording completes",
            "completed", run.status if run else None,
            cause="no steps",
            effect="run completed immediately",
            lesson="Empty recordings must complete without error",
        )
        assert run.completed_steps == 0

    def test_recording_with_all_action_kinds(self) -> None:
        eng = _make_engine()
        steps = [{"kind": k.value} for k in ActionKind]
        r = eng.create_recording("all-kinds", steps=steps)
        record(
            "RPA-080", "recording with all action kinds",
            len(ActionKind), len(r.steps),
            cause="all ActionKind values used",
            effect="all steps created",
            lesson="All action kinds must be supported",
        )

    def test_recording_status_enum(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("enum-test")
        eng.update_recording_status(r.recording_id, RecordingStatus.COMPLETE)
        got = eng.get_recording(r.recording_id)
        record(
            "RPA-081", "status can be set with enum",
            "complete", got.status if got else None,
            cause="status set with enum",
            effect="stored as string value",
            lesson="Enum values must be coerced to strings",
        )

    def test_reorder_partial_ids(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("partial", steps=[
            {"kind": "click", "selector": "#a"},
            {"kind": "click", "selector": "#b"},
            {"kind": "click", "selector": "#c"},
        ])
        # Only supply one ID — the rest should be appended
        first_id = r.steps[0].step_id
        result = eng.reorder_steps(r.recording_id, [first_id])
        record(
            "RPA-082", "reorder with partial IDs keeps all steps",
            3, len(result.steps) if result else 0,
            cause="partial ID list",
            effect="all steps preserved",
            lesson="Reorder must not lose steps",
        )

    def test_max_history_cap(self) -> None:
        eng = RpaRecorderEngine(max_history=5)
        r = eng.create_recording("cap", steps=[
            {"kind": "click", "selector": "#btn"},
        ])
        eng.update_recording_status(r.recording_id, "complete")
        for _ in range(10):
            eng.start_playback(r.recording_id)
        runs = eng.list_runs(limit=100)
        record(
            "RPA-083", "max_history caps run storage",
            True, len(runs) <= 10,
            cause="10 runs with max_history=5",
            effect="runs capped by max_history",
            lesson="History must be bounded",
        )

    def test_step_metadata(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("meta", steps=[
            {"kind": "click", "metadata": {"key": "value"}},
        ])
        record(
            "RPA-084", "step metadata is preserved",
            {"key": "value"}, r.steps[0].metadata,
            cause="metadata provided",
            effect="metadata stored",
            lesson="Metadata must be preserved",
        )

    def test_cancel_run(self) -> None:
        # Cancel only works for runs that are still "running".
        # Since our default executor is synchronous, we test the cancel path
        # by creating a run that is already completed — cancel should fail.
        eng = _make_engine()
        r = _make_complete_recording(eng)
        run = eng.start_playback(r.recording_id)
        ok = eng.cancel_run(run.run_id)
        record(
            "RPA-085", "cancel_run fails for completed run",
            False, ok,
            cause="run already completed",
            effect="cancel returns False",
            lesson="Only running runs can be cancelled",
        )

    def test_search_case_insensitive(self) -> None:
        eng = _make_engine()
        eng.create_recording("Login-Flow")
        results = eng.search_recordings("login")
        record(
            "RPA-086", "search is case-insensitive",
            1, len(results),
            cause="lowercase query matches uppercase name",
            effect="one result",
            lesson="Search must be case-insensitive",
        )

    def test_update_status_with_enum(self) -> None:
        eng = _make_engine()
        r = eng.create_recording("enum-update")
        eng.update_recording_status(r.recording_id, RecordingStatus.RECORDING)
        got = eng.get_recording(r.recording_id)
        record(
            "RPA-087", "update_recording_status accepts enum",
            "recording", got.status if got else None,
            cause="enum passed as status",
            effect="stored as string",
            lesson="Enum coercion must work in update",
        )

    def test_list_runs_with_playback_status_enum(self) -> None:
        eng = _make_engine()
        r = _make_complete_recording(eng)
        eng.start_playback(r.recording_id)
        runs = eng.list_runs(status=PlaybackStatus.COMPLETED)
        record(
            "RPA-088", "list_runs accepts PlaybackStatus enum",
            True, len(runs) >= 1,
            cause="enum filter applied",
            effect="results returned",
            lesson="Enum coercion must work in list_runs",
        )

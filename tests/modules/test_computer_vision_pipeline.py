# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for computer_vision_pipeline — CVP-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable CVPRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from computer_vision_pipeline import (  # noqa: E402
    AlertResult,
    AlertSeverity,
    ClassificationResult,
    ComputerVisionPipeline,
    DetectionResult,
    FrameFormat,
    FrameInput,
    ModelStage,
    PipelineConfig,
    PipelineRunResult,
    PipelineStats,
    PipelineStatus,
    StageKind,
    TrackingResult,
    create_cvp_api,
    gate_cvp_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class CVPRecord:
    """One CVP check record."""

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


_RESULTS: List[CVPRecord] = []


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
        CVPRecord(
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


def _make_engine() -> ComputerVisionPipeline:
    return ComputerVisionPipeline(max_history=500)


def _make_active_pipeline(eng: ComputerVisionPipeline,
                          name: str = "test-pipe") -> PipelineConfig:
    """Create a pipeline with detect+classify+track+alert stages, set active."""
    p = eng.create_pipeline(name=name, stages=[
        {"kind": "detect", "model_name": "builtin"},
        {"kind": "classify", "model_name": "builtin"},
        {"kind": "track", "model_name": "builtin"},
        {"kind": "alert", "model_name": "builtin",
         "config": {"alert_threshold": 0.8}},
    ])
    eng.update_pipeline_status(p.pipeline_id, "active")
    return p


# ==========================================================================
# Tests
# ==========================================================================


class TestPipelineCRUD:
    """Pipeline create / read / update / delete."""

    def test_create_pipeline(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("my-pipe", description="test")
        record("CVP-001", "create pipeline returns PipelineConfig",
               True, isinstance(p, PipelineConfig),
               cause="create_pipeline called",
               effect="PipelineConfig returned",
               lesson="Factory must return typed config")
        assert p.name == "my-pipe"
        assert p.status == "draft"

    def test_create_pipeline_with_stages(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("staged", stages=[
            {"kind": "detect", "model_name": "builtin"},
            {"kind": "classify"},
        ])
        record("CVP-002", "pipeline created with stages",
               2, len(p.stages),
               cause="stages list provided",
               effect="stages attached",
               lesson="Stages must be built from raw dicts")

    def test_get_pipeline(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("lookup")
        got = eng.get_pipeline(p.pipeline_id)
        record("CVP-003", "get_pipeline returns correct pipeline",
               p.pipeline_id, got.pipeline_id if got else None,
               cause="get by ID", effect="returns same pipeline",
               lesson="Lookup must return existing pipelines")

    def test_get_pipeline_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_pipeline("nonexistent")
        record("CVP-004", "get_pipeline returns None for missing",
               True, got is None,
               cause="invalid ID", effect="None returned",
               lesson="Missing pipelines return None gracefully")

    def test_list_pipelines(self) -> None:
        eng = _make_engine()
        eng.create_pipeline("a")
        eng.create_pipeline("b")
        lst = eng.list_pipelines()
        record("CVP-005", "list_pipelines returns all",
               2, len(lst),
               cause="two pipelines created",
               effect="list has two entries",
               lesson="List must include all pipelines")

    def test_list_pipelines_filter_status(self) -> None:
        eng = _make_engine()
        p1 = eng.create_pipeline("x")
        eng.create_pipeline("y")
        eng.update_pipeline_status(p1.pipeline_id, "active")
        active = eng.list_pipelines(status="active")
        record("CVP-006", "list filtered by status",
               1, len(active),
               cause="one pipeline activated",
               effect="filter returns only active",
               lesson="Status filter must work correctly")

    def test_update_status(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("s")
        updated = eng.update_pipeline_status(p.pipeline_id, "active")
        record("CVP-007", "update status to active",
               "active", updated.status if updated else None,
               cause="status update called",
               effect="status changed",
               lesson="Status transitions must persist")

    def test_update_status_invalid(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("s")
        updated = eng.update_pipeline_status(p.pipeline_id, "invalid")
        record("CVP-008", "invalid status returns None",
               True, updated is None,
               cause="invalid status value",
               effect="None returned",
               lesson="Invalid statuses must be rejected")

    def test_delete_pipeline(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("del")
        ok = eng.delete_pipeline(p.pipeline_id)
        record("CVP-009", "delete returns True",
               True, ok,
               cause="delete existing pipeline",
               effect="returns True",
               lesson="Delete must confirm success")
        assert eng.get_pipeline(p.pipeline_id) is None

    def test_delete_missing(self) -> None:
        eng = _make_engine()
        ok = eng.delete_pipeline("nope")
        record("CVP-010", "delete missing returns False",
               False, ok,
               cause="delete nonexistent",
               effect="returns False",
               lesson="Delete of missing must not crash")


class TestStageManagement:
    """Stage add / remove operations."""

    def test_add_stage(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("st")
        s = eng.add_stage(p.pipeline_id, "detect", model_name="yolo")
        record("CVP-011", "add_stage returns ModelStage",
               True, isinstance(s, ModelStage),
               cause="add_stage called",
               effect="ModelStage returned",
               lesson="Stage creation must return typed object")
        assert s.kind == "detect"

    def test_add_stage_missing_pipeline(self) -> None:
        eng = _make_engine()
        s = eng.add_stage("nope", "detect")
        record("CVP-012", "add_stage to missing pipeline returns None",
               True, s is None,
               cause="invalid pipeline_id",
               effect="None returned",
               lesson="Stage ops must validate pipeline existence")

    def test_remove_stage(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("rm")
        s = eng.add_stage(p.pipeline_id, "classify")
        ok = eng.remove_stage(p.pipeline_id, s.stage_id)
        record("CVP-013", "remove_stage returns True",
               True, ok,
               cause="remove existing stage",
               effect="returns True",
               lesson="Stage removal must confirm success")
        assert len(eng.get_pipeline(p.pipeline_id).stages) == 0

    def test_remove_stage_missing(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("rm2")
        ok = eng.remove_stage(p.pipeline_id, "bad_id")
        record("CVP-014", "remove missing stage returns False",
               False, ok,
               cause="invalid stage_id",
               effect="returns False",
               lesson="Missing stage removal must not crash")


class TestFrameProcessing:
    """Frame processing through pipelines."""

    def test_process_frame_basic(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "a person walking")
        record("CVP-015", "process_frame returns PipelineRunResult",
               True, isinstance(result, PipelineRunResult),
               cause="frame submitted",
               effect="result returned",
               lesson="Processing must return typed result")
        assert result.stages_executed == 4
        assert len(result.detections) > 0

    def test_process_frame_with_detections(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "person and car nearby")
        record("CVP-016", "detections found for known keywords",
               True, len(result.detections) >= 2,
               cause="frame with person+car",
               effect="both detected",
               lesson="Stub detector must find keywords")

    def test_process_frame_classifications(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "dog in yard")
        record("CVP-017", "classifications produced",
               True, len(result.classifications) > 0,
               cause="detection triggers classify",
               effect="classifications present",
               lesson="Classify stage runs after detect")
        assert result.classifications[0]["class_name"] == "animal"

    def test_process_frame_tracking(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "cat on roof")
        record("CVP-018", "tracking results produced",
               True, len(result.trackings) > 0,
               cause="detection triggers tracking",
               effect="track IDs assigned",
               lesson="Track stage assigns stable IDs")

    def test_process_frame_alerts(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "fire in building")
        record("CVP-019", "alerts raised for hazards",
               True, len(result.alerts) > 0,
               cause="fire detected",
               effect="alert raised",
               lesson="Alert stage fires on hazard classes")

    def test_process_frame_no_detections(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "empty scene nothing here")
        record("CVP-020", "no detections for unknown content",
               0, len(result.detections),
               cause="no keywords in frame",
               effect="zero detections",
               lesson="Detector must not hallucinate")

    def test_process_frame_inactive_pipeline(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("draft-pipe")
        result = eng.process_frame(p.pipeline_id, "person")
        record("CVP-021", "inactive pipeline returns None",
               True, result is None,
               cause="pipeline is draft",
               effect="None returned",
               lesson="Only active pipelines process frames")

    def test_process_frame_missing_pipeline(self) -> None:
        eng = _make_engine()
        result = eng.process_frame("nope", "data")
        record("CVP-022", "missing pipeline returns None",
               True, result is None,
               cause="invalid pipeline_id",
               effect="None returned",
               lesson="Missing pipeline must not crash")

    def test_process_frame_duration(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        result = eng.process_frame(p.pipeline_id, "person here")
        record("CVP-023", "duration_ms is positive",
               True, result.duration_ms >= 0.0,
               cause="processing takes time",
               effect="duration recorded",
               lesson="Timing must be captured")


class TestHistoryAndAlerts:
    """Run history and alert queries."""

    def test_run_history(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "person")
        eng.process_frame(p.pipeline_id, "car")
        hist = eng.get_run_history()
        record("CVP-024", "run history contains 2 entries",
               2, len(hist),
               cause="two frames processed",
               effect="two history entries",
               lesson="Each run must be recorded")

    def test_run_history_filter(self) -> None:
        eng = _make_engine()
        p1 = _make_active_pipeline(eng, name="a")
        p2 = _make_active_pipeline(eng, name="b")
        eng.process_frame(p1.pipeline_id, "person")
        eng.process_frame(p2.pipeline_id, "car")
        hist = eng.get_run_history(pipeline_id=p1.pipeline_id)
        record("CVP-025", "history filter by pipeline_id",
               1, len(hist),
               cause="filter applied",
               effect="only matching runs",
               lesson="Pipeline filter must work")

    def test_alerts_list(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "fire smoke")
        alerts = eng.get_alerts()
        record("CVP-026", "alerts list non-empty for hazards",
               True, len(alerts) > 0,
               cause="hazard detected",
               effect="alerts recorded",
               lesson="Alerts must persist after runs")

    def test_alerts_filter_severity(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "fire")
        critical = eng.get_alerts(severity="critical")
        record("CVP-027", "severity filter works",
               True, all(a["severity"] == "critical" for a in critical),
               cause="filter by critical",
               effect="only critical returned",
               lesson="Severity filter must be accurate")

    def test_clear_alerts(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "fire")
        n = eng.clear_alerts()
        record("CVP-028", "clear_alerts returns count",
               True, n > 0,
               cause="alerts exist",
               effect="count returned",
               lesson="Clear must report count")
        assert len(eng.get_alerts()) == 0


class TestStats:
    """Engine statistics."""

    def test_stats_empty(self) -> None:
        eng = _make_engine()
        st = eng.get_stats()
        record("CVP-029", "empty engine stats",
               0, st.total_runs,
               cause="no frames processed",
               effect="zero runs",
               lesson="Stats start at zero")

    def test_stats_after_processing(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "person walking")
        st = eng.get_stats()
        record("CVP-030", "stats updated after processing",
               1, st.total_runs,
               cause="one frame processed",
               effect="total_runs is 1",
               lesson="Stats must be updated after each run")
        assert st.total_detections > 0

    def test_stats_pipeline_count(self) -> None:
        eng = _make_engine()
        _make_active_pipeline(eng, "x")
        eng.create_pipeline("y")
        st = eng.get_stats()
        record("CVP-031", "pipeline counts in stats",
               2, st.total_pipelines,
               cause="two pipelines created",
               effect="total_pipelines is 2",
               lesson="Pipeline count must be accurate")
        assert st.active_pipelines == 1


class TestEnums:
    """Enum coverage."""

    def test_stage_kinds(self) -> None:
        kinds = [e.value for e in StageKind]
        record("CVP-032", "StageKind has expected values",
               True, "detect" in kinds and "alert" in kinds,
               cause="enum defined",
               effect="values present",
               lesson="Enums must cover all stage types")

    def test_pipeline_status(self) -> None:
        statuses = [e.value for e in PipelineStatus]
        record("CVP-033", "PipelineStatus has expected values",
               True, "active" in statuses and "archived" in statuses,
               cause="enum defined",
               effect="values present",
               lesson="Status enum must be complete")

    def test_alert_severity(self) -> None:
        sevs = [e.value for e in AlertSeverity]
        record("CVP-034", "AlertSeverity has expected values",
               3, len(sevs),
               cause="enum defined",
               effect="3 severities",
               lesson="info/warning/critical required")

    def test_frame_format(self) -> None:
        fmts = [e.value for e in FrameFormat]
        record("CVP-035", "FrameFormat covers common types",
               True, "jpeg" in fmts and "png" in fmts,
               cause="enum defined",
               effect="formats present",
               lesson="Common formats must be listed")


class TestDataModels:
    """Dataclass serialization tests."""

    def test_model_stage_to_dict(self) -> None:
        s = ModelStage(stage_id="s1", kind="detect", model_name="yolo")
        d = s.to_dict()
        record("CVP-036", "ModelStage serialises",
               "detect", d["kind"],
               cause="to_dict called",
               effect="dict returned",
               lesson="Dataclasses must serialise cleanly")

    def test_detection_result_to_dict(self) -> None:
        det = DetectionResult(detection_id="d1", label="person",
                              confidence=0.9)
        d = det.to_dict()
        record("CVP-037", "DetectionResult serialises",
               "person", d["label"],
               cause="to_dict called",
               effect="label present",
               lesson="All result types must serialise")

    def test_pipeline_config_to_dict(self) -> None:
        cfg = PipelineConfig(pipeline_id="p1", name="test")
        d = cfg.to_dict()
        record("CVP-038", "PipelineConfig serialises",
               "test", d["name"],
               cause="to_dict called",
               effect="name present",
               lesson="Config must include all fields")

    def test_alert_result_to_dict(self) -> None:
        a = AlertResult(alert_id="a1", severity="critical",
                        message="fire!")
        d = a.to_dict()
        record("CVP-039", "AlertResult serialises",
               "critical", d["severity"],
               cause="to_dict called",
               effect="severity present",
               lesson="Alerts must serialise for API responses")

    def test_pipeline_stats_to_dict(self) -> None:
        st = PipelineStats(total_pipelines=5)
        d = st.to_dict()
        record("CVP-040", "PipelineStats serialises",
               5, d["total_pipelines"],
               cause="to_dict called",
               effect="count present",
               lesson="Stats must be JSON-serialisable")


class TestWingmanProtocol:
    """Wingman pair validation."""

    def test_wingman_pass(self) -> None:
        r = validate_wingman_pair(["a", "b"], ["a", "b"])
        record("CVP-041", "wingman pass with matching pairs",
               True, r["passed"],
               cause="matching lists",
               effect="passed True",
               lesson="Matching pairs must pass")

    def test_wingman_empty_storyline(self) -> None:
        r = validate_wingman_pair([], ["a"])
        record("CVP-042", "wingman fails on empty storyline",
               False, r["passed"],
               cause="empty storyline",
               effect="failed",
               lesson="Empty inputs must fail")

    def test_wingman_empty_actuals(self) -> None:
        r = validate_wingman_pair(["a"], [])
        record("CVP-043", "wingman fails on empty actuals",
               False, r["passed"],
               cause="empty actuals",
               effect="failed",
               lesson="Both lists required")

    def test_wingman_length_mismatch(self) -> None:
        r = validate_wingman_pair(["a"], ["a", "b"])
        record("CVP-044", "wingman fails on length mismatch",
               False, r["passed"],
               cause="different lengths",
               effect="failed",
               lesson="Lists must be same length")

    def test_wingman_content_mismatch(self) -> None:
        r = validate_wingman_pair(["a", "b"], ["a", "c"])
        record("CVP-045", "wingman fails on content mismatch",
               False, r["passed"],
               cause="values differ at index 1",
               effect="failed with mismatch details",
               lesson="Content must match pairwise")


class TestSandboxGating:
    """Causality Sandbox gate tests."""

    def test_sandbox_pass(self) -> None:
        r = gate_cvp_in_sandbox({"pipeline_id": "p1", "frame_data": "img"})
        record("CVP-046", "sandbox pass with valid context",
               True, r["passed"],
               cause="all keys present",
               effect="passed",
               lesson="Valid context must pass gate")

    def test_sandbox_missing_key(self) -> None:
        r = gate_cvp_in_sandbox({"pipeline_id": "p1"})
        record("CVP-047", "sandbox fails on missing key",
               False, r["passed"],
               cause="frame_data missing",
               effect="failed",
               lesson="Required keys must be checked")

    def test_sandbox_empty_pipeline_id(self) -> None:
        r = gate_cvp_in_sandbox({"pipeline_id": "", "frame_data": "img"})
        record("CVP-048", "sandbox fails on empty pipeline_id",
               False, r["passed"],
               cause="empty pipeline_id",
               effect="failed",
               lesson="Non-empty values required")

    def test_sandbox_empty_frame_data(self) -> None:
        r = gate_cvp_in_sandbox({"pipeline_id": "p1", "frame_data": ""})
        record("CVP-049", "sandbox fails on empty frame_data",
               False, r["passed"],
               cause="empty frame_data",
               effect="failed",
               lesson="Frame data must not be empty")


class TestFlaskAPI:
    """Flask Blueprint endpoint tests."""

    def _client(self) -> Any:
        from flask import Flask
        eng = _make_engine()
        app = Flask(__name__)
        bp = create_cvp_api(eng)
        app.register_blueprint(bp)
        app.config["TESTING"] = True
        return app.test_client(), eng

    def test_create_pipeline_endpoint(self) -> None:
        c, _ = self._client()
        resp = c.post("/api/cvp/pipelines",
                       json={"name": "api-pipe"})
        record("CVP-050", "POST /cvp/pipelines returns 201",
               201, resp.status_code,
               cause="valid request",
               effect="pipeline created",
               lesson="Create endpoint must return 201")
        data = resp.get_json()
        assert data["name"] == "api-pipe"

    def test_create_pipeline_missing_name(self) -> None:
        c, _ = self._client()
        resp = c.post("/api/cvp/pipelines", json={})
        record("CVP-051", "POST /cvp/pipelines without name returns 400",
               400, resp.status_code,
               cause="missing name",
               effect="400 error",
               lesson="Validation must reject missing fields")

    def test_list_pipelines_endpoint(self) -> None:
        c, _ = self._client()
        c.post("/api/cvp/pipelines", json={"name": "a"})
        resp = c.get("/api/cvp/pipelines")
        record("CVP-052", "GET /cvp/pipelines returns list",
               200, resp.status_code,
               cause="pipelines exist",
               effect="list returned",
               lesson="List endpoint must work")

    def test_get_pipeline_endpoint(self) -> None:
        c, _ = self._client()
        r1 = c.post("/api/cvp/pipelines", json={"name": "x"})
        pid = r1.get_json()["pipeline_id"]
        resp = c.get(f"/api/cvp/pipelines/{pid}")
        record("CVP-053", "GET /cvp/pipelines/<id> returns pipeline",
               200, resp.status_code,
               cause="valid ID",
               effect="pipeline returned",
               lesson="Get by ID must work")

    def test_get_pipeline_not_found(self) -> None:
        c, _ = self._client()
        resp = c.get("/api/cvp/pipelines/nope")
        record("CVP-054", "GET missing pipeline returns 404",
               404, resp.status_code,
               cause="invalid ID",
               effect="404 returned",
               lesson="Not found must return 404")

    def test_update_status_endpoint(self) -> None:
        c, _ = self._client()
        r1 = c.post("/api/cvp/pipelines", json={"name": "s"})
        pid = r1.get_json()["pipeline_id"]
        resp = c.put(f"/api/cvp/pipelines/{pid}/status",
                      json={"status": "active"})
        record("CVP-055", "PUT /status returns 200",
               200, resp.status_code,
               cause="valid status update",
               effect="status changed",
               lesson="Status update endpoint must work")

    def test_delete_pipeline_endpoint(self) -> None:
        c, _ = self._client()
        r1 = c.post("/api/cvp/pipelines", json={"name": "d"})
        pid = r1.get_json()["pipeline_id"]
        resp = c.delete(f"/api/cvp/pipelines/{pid}")
        record("CVP-056", "DELETE /cvp/pipelines/<id> returns 200",
               200, resp.status_code,
               cause="valid delete",
               effect="pipeline deleted",
               lesson="Delete must confirm success")

    def test_add_stage_endpoint(self) -> None:
        c, _ = self._client()
        r1 = c.post("/api/cvp/pipelines", json={"name": "st"})
        pid = r1.get_json()["pipeline_id"]
        resp = c.post(f"/api/cvp/pipelines/{pid}/stages",
                       json={"kind": "detect"})
        record("CVP-057", "POST /stages returns 201",
               201, resp.status_code,
               cause="valid stage add",
               effect="stage created",
               lesson="Stage add endpoint must work")

    def test_remove_stage_endpoint(self) -> None:
        c, _ = self._client()
        r1 = c.post("/api/cvp/pipelines", json={"name": "rs"})
        pid = r1.get_json()["pipeline_id"]
        r2 = c.post(f"/api/cvp/pipelines/{pid}/stages",
                      json={"kind": "detect"})
        sid = r2.get_json()["stage_id"]
        resp = c.delete(f"/api/cvp/pipelines/{pid}/stages/{sid}")
        record("CVP-058", "DELETE /stages/<sid> returns 200",
               200, resp.status_code,
               cause="valid stage remove",
               effect="stage removed",
               lesson="Stage remove endpoint must work")

    def test_process_endpoint(self) -> None:
        c, eng = self._client()
        p = _make_active_pipeline(eng)
        resp = c.post("/api/cvp/process", json={
            "pipeline_id": p.pipeline_id,
            "frame_data": "person walking",
        })
        record("CVP-059", "POST /cvp/process returns 200",
               200, resp.status_code,
               cause="valid frame submitted",
               effect="result returned",
               lesson="Process endpoint must work")
        data = resp.get_json()
        assert len(data["detections"]) > 0

    def test_process_missing_pipeline(self) -> None:
        c, _ = self._client()
        resp = c.post("/api/cvp/process", json={
            "pipeline_id": "bad",
            "frame_data": "data",
        })
        record("CVP-060", "process missing pipeline returns 404",
               404, resp.status_code,
               cause="invalid pipeline",
               effect="404 returned",
               lesson="Process must validate pipeline")

    def test_history_endpoint(self) -> None:
        c, eng = self._client()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "person")
        resp = c.get("/api/cvp/history")
        record("CVP-061", "GET /cvp/history returns results",
               200, resp.status_code,
               cause="runs exist",
               effect="history returned",
               lesson="History endpoint must work")

    def test_alerts_endpoint(self) -> None:
        c, eng = self._client()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "fire")
        resp = c.get("/api/cvp/alerts")
        record("CVP-062", "GET /cvp/alerts returns results",
               200, resp.status_code,
               cause="alerts exist",
               effect="alerts returned",
               lesson="Alerts endpoint must work")

    def test_clear_alerts_endpoint(self) -> None:
        c, eng = self._client()
        p = _make_active_pipeline(eng)
        eng.process_frame(p.pipeline_id, "fire")
        resp = c.delete("/api/cvp/alerts")
        record("CVP-063", "DELETE /cvp/alerts returns 200",
               200, resp.status_code,
               cause="alerts cleared",
               effect="count returned",
               lesson="Clear alerts endpoint must work")

    def test_stats_endpoint(self) -> None:
        c, _ = self._client()
        resp = c.get("/api/cvp/stats")
        record("CVP-064", "GET /cvp/stats returns 200",
               200, resp.status_code,
               cause="stats requested",
               effect="stats returned",
               lesson="Stats endpoint must always work")

    def test_health_endpoint(self) -> None:
        c, _ = self._client()
        resp = c.get("/api/cvp/health")
        record("CVP-065", "GET /cvp/health returns 200",
               200, resp.status_code,
               cause="health check requested",
               effect="healthy response",
               lesson="Health endpoint must always respond")
        data = resp.get_json()
        assert data["module"] == "CVP-001"


class TestThreadSafety:
    """Concurrent access tests."""

    def test_concurrent_pipeline_creation(self) -> None:
        eng = _make_engine()
        errors: List[str] = []

        def create_pipe(n: int) -> None:
            try:
                eng.create_pipeline(f"pipe-{n}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=create_pipe, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record("CVP-066", "concurrent pipeline creation",
               0, len(errors),
               cause="20 threads creating pipelines",
               effect="no errors",
               lesson="Pipeline creation must be thread-safe")
        assert eng.get_stats().total_pipelines == 20

    def test_concurrent_frame_processing(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        errors: List[str] = []

        def process(n: int) -> None:
            try:
                eng.process_frame(p.pipeline_id, f"person-{n}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=process, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record("CVP-067", "concurrent frame processing",
               0, len(errors),
               cause="10 threads processing frames",
               effect="no errors",
               lesson="Frame processing must be thread-safe")
        assert eng.get_stats().total_runs == 10


class TestEdgeCases:
    """Boundary and edge case tests."""

    def test_empty_pipeline_name(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("")
        record("CVP-068", "empty name pipeline creation",
               True, p.pipeline_id is not None,
               cause="empty name allowed by engine",
               effect="pipeline created",
               lesson="Engine does not reject empty names (API does)")

    def test_disabled_stage_skipped(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("skip", stages=[
            {"kind": "detect", "enabled": True},
            {"kind": "classify", "enabled": False},
        ])
        eng.update_pipeline_status(p.pipeline_id, "active")
        result = eng.process_frame(p.pipeline_id, "person")
        record("CVP-069", "disabled stage skipped",
               1, result.stages_executed,
               cause="classify stage disabled",
               effect="only detect ran",
               lesson="Disabled stages must be skipped")

    def test_high_confidence_threshold_filters(self) -> None:
        eng = _make_engine()
        p = eng.create_pipeline("thresh", stages=[
            {"kind": "detect", "confidence_threshold": 0.99},
        ])
        eng.update_pipeline_status(p.pipeline_id, "active")
        result = eng.process_frame(p.pipeline_id, "person")
        record("CVP-070", "high threshold filters out detections",
               0, len(result.detections),
               cause="threshold 0.99 > stub confidence",
               effect="no detections pass",
               lesson="Confidence threshold must filter")

    def test_multiple_pipelines_independent(self) -> None:
        eng = _make_engine()
        p1 = _make_active_pipeline(eng, "ind1")
        p2 = _make_active_pipeline(eng, "ind2")
        eng.process_frame(p1.pipeline_id, "person")
        hist2 = eng.get_run_history(pipeline_id=p2.pipeline_id)
        record("CVP-071", "pipelines are independent",
               0, len(hist2),
               cause="only p1 processed",
               effect="p2 history empty",
               lesson="Pipeline data must not leak")

    def test_history_limit(self) -> None:
        eng = _make_engine()
        p = _make_active_pipeline(eng)
        for i in range(10):
            eng.process_frame(p.pipeline_id, f"person-{i}")
        hist = eng.get_run_history(limit=3)
        record("CVP-072", "history limit respected",
               3, len(hist),
               cause="limit=3 requested",
               effect="only 3 returned",
               lesson="Limit must cap results")

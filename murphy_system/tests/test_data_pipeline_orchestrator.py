# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for data_pipeline_orchestrator — DPO-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable DPORecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from data_pipeline_orchestrator import (  # noqa: E402
    DataPipeline,
    DataPipelineOrchestrator,
    DataQualityCheck,
    PipelineRun,
    PipelineStage,
    PipelineStatus,
    QualityCheckResult,
    RunStatus,
    ScheduleType,
    StageResult,
    StageType,
    create_pipeline_api,
    gate_pipeline_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------

@dataclass
class DPORecord:
    """One DPO check record."""
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

_RESULTS: List[DPORecord] = []

def record(
    check_id: str, desc: str, expected: Any, actual: Any,
    cause: str = "", effect: str = "", lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(DPORecord(
        check_id=check_id, description=desc, expected=expected,
        actual=actual, passed=ok, cause=cause, effect=effect, lesson=lesson,
    ))
    return ok

# -- Helpers ---------------------------------------------------------------

def _orch(**kw: Any) -> DataPipelineOrchestrator:
    return DataPipelineOrchestrator(**kw)


def _stages(n: int = 3) -> List[PipelineStage]:
    """Return *n* ordered stages: extract → transform → load (→ validate → notify)."""
    types = [StageType.extract, StageType.transform, StageType.load,
             StageType.validate, StageType.notify]
    return [PipelineStage(name=f"stage-{i}", stage_type=types[i % len(types)])
            for i in range(n)]


def _active_pipeline(o: DataPipelineOrchestrator, name: str = "p",
                     stages: list | None = None) -> DataPipeline:
    """Create and activate a pipeline in one step."""
    p = o.create_pipeline(name, stages=stages or _stages())
    o.activate_pipeline(p.id)
    return o.get_pipeline(p.id)  # type: ignore[return-value]


def _complete_run(o: DataPipelineOrchestrator, pipe: DataPipeline,
                  recs: int = 100, fails: int = 0) -> PipelineRun:
    """Trigger a run and advance all stages to completion."""
    run = o.trigger_run(pipe.id)
    assert run is not None
    for s in pipe.stages:
        o.advance_stage(run.id, s.id, records_processed=recs, records_failed=fails)
    return o.get_run(run.id)  # type: ignore[return-value]

# ================================================================== #
#  Pipeline CRUD                                                      #
# ================================================================== #

def test_dpo_001_create_pipeline():
    o = _orch()
    p = o.create_pipeline("ingest", stages=_stages())
    assert record("DPO-001", "Create pipeline", True, p is not None,
                  cause="valid args", effect="pipeline created", lesson="basic CRUD")

def test_dpo_002_create_returns_correct_fields():
    o = _orch()
    p = o.create_pipeline("etl", description="d", owner="alice", tags=["x"])
    ok = (p.name == "etl" and p.description == "d" and p.owner == "alice"
          and "x" in p.tags and p.status == PipelineStatus.draft)
    assert record("DPO-002", "Fields match", True, ok)

def test_dpo_003_get_existing_pipeline():
    o = _orch(); p = o.create_pipeline("p1")
    assert record("DPO-003", "Get by ID", p.id, o.get_pipeline(p.id).id)

def test_dpo_004_get_nonexistent():
    o = _orch()
    assert record("DPO-004", "Missing pipeline", None, o.get_pipeline("nope"))

def test_dpo_005_list_no_filter():
    o = _orch()
    for i in range(3): o.create_pipeline(f"p{i}")
    assert record("DPO-005", "List all", 3, len(o.list_pipelines()))

def test_dpo_006_list_status_filter():
    o = _orch()
    p = o.create_pipeline("a", stages=_stages()); o.activate_pipeline(p.id)
    o.create_pipeline("b")
    assert record("DPO-006", "Status filter", 1,
                  len(o.list_pipelines(status_filter=PipelineStatus.active)))

def test_dpo_007_list_owner_filter():
    o = _orch()
    o.create_pipeline("a", owner="bob"); o.create_pipeline("b", owner="sue")
    assert record("DPO-007", "Owner filter", 1,
                  len(o.list_pipelines(owner_filter="bob")))

def test_dpo_008_list_tag_filter():
    o = _orch()
    o.create_pipeline("a", tags=["ml"]); o.create_pipeline("b", tags=["etl"])
    assert record("DPO-008", "Tag filter", 1,
                  len(o.list_pipelines(tag_filter="ml")))

def test_dpo_009_update_pipeline():
    o = _orch(); p = o.create_pipeline("old")
    u = o.update_pipeline(p.id, name="new")
    assert record("DPO-009", "Update name", "new", u.name)

def test_dpo_010_delete_pipeline():
    o = _orch(); p = o.create_pipeline("d")
    assert record("DPO-010", "Delete", True, o.delete_pipeline(p.id))

def test_dpo_011_delete_nonexistent():
    o = _orch()
    assert record("DPO-011", "Delete missing", False, o.delete_pipeline("no"))

# ================================================================== #
#  Pipeline Lifecycle                                                  #
# ================================================================== #

def test_dpo_012_activate_draft():
    o = _orch(); p = o.create_pipeline("p", stages=_stages())
    r = o.activate_pipeline(p.id)
    assert record("DPO-012", "Activate draft", PipelineStatus.active, r.status)

def test_dpo_013_activate_already_active():
    o = _orch(); p = _active_pipeline(o)
    assert record("DPO-013", "Re-activate", None, o.activate_pipeline(p.id))

def test_dpo_014_pause_active():
    o = _orch(); p = _active_pipeline(o)
    r = o.pause_pipeline(p.id)
    assert record("DPO-014", "Pause active", PipelineStatus.paused, r.status)

def test_dpo_015_pause_draft():
    o = _orch(); p = o.create_pipeline("p")
    assert record("DPO-015", "Pause draft", None, o.pause_pipeline(p.id))

def test_dpo_016_reactivate_paused():
    o = _orch(); p = _active_pipeline(o); o.pause_pipeline(p.id)
    r = o.activate_pipeline(p.id)
    assert record("DPO-016", "Reactivate paused", PipelineStatus.active, r.status)

def test_dpo_017_lifecycle_draft_to_active():
    o = _orch(); p = o.create_pipeline("p", stages=_stages())
    assert record("DPO-017", "Initial draft", PipelineStatus.draft, p.status)

def test_dpo_018_activate_nonexistent():
    o = _orch()
    assert record("DPO-018", "Activate missing", None, o.activate_pipeline("x"))

def test_dpo_019_pause_nonexistent():
    o = _orch()
    assert record("DPO-019", "Pause missing", None, o.pause_pipeline("x"))

# ================================================================== #
#  Pipeline Runs                                                       #
# ================================================================== #

def test_dpo_020_trigger_run():
    o = _orch(); p = _active_pipeline(o)
    run = o.trigger_run(p.id)
    assert record("DPO-020", "Trigger run", True, run is not None,
                  cause="active pipeline", effect="run created")

def test_dpo_021_trigger_on_draft():
    o = _orch(); p = o.create_pipeline("p")
    assert record("DPO-021", "Trigger draft", None, o.trigger_run(p.id))

def test_dpo_022_get_run():
    o = _orch(); p = _active_pipeline(o); run = o.trigger_run(p.id)
    assert record("DPO-022", "Get run", run.id, o.get_run(run.id).id)

def test_dpo_023_get_nonexistent_run():
    o = _orch()
    assert record("DPO-023", "Missing run", None, o.get_run("nope"))

def test_dpo_024_list_runs_for_pipeline():
    o = _orch(); p = _active_pipeline(o, stages=_stages())
    _complete_run(o, p); o.trigger_run(p.id)
    assert record("DPO-024", "List runs", 2, len(o.list_runs(pipeline_id=p.id)))

def test_dpo_025_list_runs_status_filter():
    o = _orch(); p = _active_pipeline(o, stages=_stages())
    _complete_run(o, p); o.trigger_run(p.id)
    assert record("DPO-025", "Filter running", 1,
                  len(o.list_runs(pipeline_id=p.id, status_filter=RunStatus.running)))

def test_dpo_026_list_runs_limit():
    o = _orch(); p = _active_pipeline(o, stages=_stages())
    for _ in range(3): _complete_run(o, p)
    assert record("DPO-026", "Limit runs", 2,
                  len(o.list_runs(pipeline_id=p.id, limit=2)))

def test_dpo_027_cancel_running():
    o = _orch(); p = _active_pipeline(o); run = o.trigger_run(p.id)
    assert record("DPO-027", "Cancel run", True, o.cancel_run(run.id))

def test_dpo_028_cancel_completed():
    o = _orch(); p = _active_pipeline(o, stages=_stages())
    run = _complete_run(o, p)
    assert record("DPO-028", "Cancel completed", False, o.cancel_run(run.id))

def test_dpo_029_run_status_running():
    o = _orch(); p = _active_pipeline(o); run = o.trigger_run(p.id)
    assert record("DPO-029", "Run status running", RunStatus.running, run.status)

# ================================================================== #
#  Stage Advancement                                                   #
# ================================================================== #

def test_dpo_030_advance_first_stage():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = o.trigger_run(p.id)
    sr = o.advance_stage(run.id, stg[0].id, records_processed=50)
    assert record("DPO-030", "Advance first", True, sr is not None)

def test_dpo_031_stage_result_fields():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = o.trigger_run(p.id)
    sr = o.advance_stage(run.id, stg[0].id, records_processed=42, records_failed=3)
    ok = (sr.stage_id == stg[0].id and sr.records_processed == 42
          and sr.records_failed == 3 and sr.status == RunStatus.succeeded)
    assert record("DPO-031", "StageResult fields", True, ok)

def test_dpo_032_all_stages_completes_run():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = _complete_run(o, p)
    assert record("DPO-032", "Run completed", RunStatus.succeeded, run.status)

def test_dpo_033_advance_with_error():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = o.trigger_run(p.id)
    sr = o.advance_stage(run.id, stg[0].id, error_message="boom")
    actual_run = o.get_run(run.id)
    assert record("DPO-033", "Error fails run", RunStatus.failed, actual_run.status)

def test_dpo_034_advance_completed_run():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = _complete_run(o, p)
    assert record("DPO-034", "Advance completed", None,
                  o.advance_stage(run.id, stg[0].id))

def test_dpo_035_records_tracked():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    run = o.trigger_run(p.id)
    o.advance_stage(run.id, stg[0].id, records_processed=200, records_failed=5)
    updated = o.get_run(run.id)
    sr = updated.stage_results[stg[0].id]
    assert record("DPO-035", "Records counts", (200, 5),
                  (sr.records_processed, sr.records_failed))

def test_dpo_036_advance_invalid_stage():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = o.trigger_run(p.id)
    assert record("DPO-036", "Bad stage ID", None,
                  o.advance_stage(run.id, "nonexistent"))

def test_dpo_037_advance_nonexistent_run():
    o = _orch()
    assert record("DPO-037", "Bad run ID", None,
                  o.advance_stage("bad", "bad"))

def test_dpo_038_error_sets_message():
    o = _orch(); stg = _stages(); p = _active_pipeline(o, stages=stg)
    run = o.trigger_run(p.id)
    o.advance_stage(run.id, stg[0].id, error_message="disk full")
    assert record("DPO-038", "Error msg stored", "disk full",
                  o.get_run(run.id).error_message)

def test_dpo_039_stage_result_to_dict():
    sr = StageResult(stage_id="s1", status=RunStatus.succeeded, records_processed=10)
    d = sr.to_dict()
    assert record("DPO-039", "StageResult to_dict", "succeeded", d["status"])

# ================================================================== #
#  Quality Checks                                                      #
# ================================================================== #

def test_dpo_040_add_quality_check():
    o = _orch(); p = o.create_pipeline("p")
    chk = o.add_quality_check("null-check", p.id, check_type="completeness")
    assert record("DPO-040", "Add QC", True, chk is not None and chk.name == "null-check")

def test_dpo_041_list_quality_checks():
    o = _orch(); p = o.create_pipeline("p")
    o.add_quality_check("a", p.id); o.add_quality_check("b", p.id)
    assert record("DPO-041", "List QCs", 2, len(o.list_quality_checks(p.id)))

def test_dpo_042_run_quality_checks():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("comp", p.id, "completeness", {"min_records": 1})
    run = _complete_run(o, p, recs=50)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-042", "QC passes", True,
                  len(results) == 1 and results[0].passed)

def test_dpo_043_quality_no_run():
    o = _orch(); p = o.create_pipeline("p")
    o.add_quality_check("c", p.id)
    assert record("DPO-043", "QC no run", [], o.run_quality_checks(p.id, "nope"))

def test_dpo_044_multiple_quality_checks():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("comp", p.id, "completeness", {"min_records": 1})
    o.add_quality_check("uniq", p.id, "uniqueness", {"max_duplicates": 10})
    run = _complete_run(o, p, recs=50, fails=2)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-044", "Multiple QCs", 2, len(results))

def test_dpo_045_completeness_fails():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("comp", p.id, "completeness", {"min_records": 999})
    run = _complete_run(o, p, recs=5)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-045", "Completeness fail", False, results[0].passed)

def test_dpo_046_uniqueness_fails():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("uniq", p.id, "uniqueness", {"max_duplicates": 0})
    run = _complete_run(o, p, recs=50, fails=5)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-046", "Uniqueness fail", False, results[0].passed)

def test_dpo_047_range_check():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("rng", p.id, "range", {"max_failure_rate": 0.01})
    run = _complete_run(o, p, recs=100, fails=50)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-047", "Range check fail", False, results[0].passed)

def test_dpo_048_custom_check_no_expr():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("cust", p.id, "custom", {})
    run = _complete_run(o, p)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-048", "Custom no expr", False, results[0].passed)

# ================================================================== #
#  Statistics                                                          #
# ================================================================== #

def test_dpo_050_stats_no_runs():
    o = _orch(); p = o.create_pipeline("p")
    s = o.get_pipeline_stats(p.id)
    assert record("DPO-050", "Stats zero runs", 0, s["total_runs"])

def test_dpo_051_stats_after_runs():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    _complete_run(o, p); _complete_run(o, p)
    s = o.get_pipeline_stats(p.id)
    assert record("DPO-051", "Stats succeeded", 2, s["succeeded"])

def test_dpo_052_global_stats():
    o = _orch()
    o.create_pipeline("a"); o.create_pipeline("b")
    s = o.get_global_stats()
    assert record("DPO-052", "Global pipelines", 2, s["total_pipelines"])

def test_dpo_053_stats_missing_pipeline():
    o = _orch()
    assert record("DPO-053", "Stats missing", {}, o.get_pipeline_stats("x"))

def test_dpo_054_global_run_statuses():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    _complete_run(o, p)
    s = o.get_global_stats()
    assert record("DPO-054", "Global run status", True,
                  s["run_statuses"].get("succeeded", 0) >= 1)

# ================================================================== #
#  Flask API                                                           #
# ================================================================== #

def _flask_client(o: DataPipelineOrchestrator):
    """Return a Flask test client with the DPO blueprint registered."""
    try:
        from flask import Flask
    except ImportError:
        return None
    app = Flask(__name__)
    app.register_blueprint(create_pipeline_api(o))
    return app.test_client()

def test_dpo_060_api_create_pipeline():
    o = _orch(); c = _flask_client(o)
    if not c:
        assert record("DPO-060", "Flask N/A", True, True); return
    resp = c.post("/api/pipelines", json={"name": "api-pipe", "stages": [
        {"name": "s1", "stage_type": "extract"}]})
    assert record("DPO-060", "POST create", 201, resp.status_code)

def test_dpo_061_api_list_pipelines():
    o = _orch(); o.create_pipeline("x"); c = _flask_client(o)
    if not c:
        assert record("DPO-061", "Flask N/A", True, True); return
    resp = c.get("/api/pipelines")
    assert record("DPO-061", "GET list", True, resp.status_code == 200
                  and len(resp.get_json()) >= 1)

def test_dpo_062_api_get_pipeline():
    o = _orch(); p = o.create_pipeline("x"); c = _flask_client(o)
    if not c:
        assert record("DPO-062", "Flask N/A", True, True); return
    resp = c.get(f"/api/pipelines/{p.id}")
    assert record("DPO-062", "GET pipeline", 200, resp.status_code)

def test_dpo_063_api_activate():
    o = _orch(); p = o.create_pipeline("x", stages=_stages()); c = _flask_client(o)
    if not c:
        assert record("DPO-063", "Flask N/A", True, True); return
    resp = c.post(f"/api/pipelines/{p.id}/activate")
    assert record("DPO-063", "POST activate", 200, resp.status_code)

def test_dpo_064_api_trigger():
    o = _orch(); p = _active_pipeline(o); c = _flask_client(o)
    if not c:
        assert record("DPO-064", "Flask N/A", True, True); return
    resp = c.post(f"/api/pipelines/{p.id}/trigger", json={})
    assert record("DPO-064", "POST trigger", 201, resp.status_code)

def test_dpo_065_api_cancel_run():
    o = _orch(); p = _active_pipeline(o); run = o.trigger_run(p.id)
    c = _flask_client(o)
    if not c:
        assert record("DPO-065", "Flask N/A", True, True); return
    resp = c.post(f"/api/runs/{run.id}/cancel")
    assert record("DPO-065", "POST cancel", 200, resp.status_code)

def test_dpo_066_api_global_stats():
    o = _orch(); c = _flask_client(o)
    if not c:
        assert record("DPO-066", "Flask N/A", True, True); return
    resp = c.get("/api/pipelines/stats/global")
    assert record("DPO-066", "GET global stats", 200, resp.status_code)

def test_dpo_067_api_missing_pipeline():
    o = _orch(); c = _flask_client(o)
    if not c:
        assert record("DPO-067", "Flask N/A", True, True); return
    resp = c.get("/api/pipelines/doesnotexist")
    assert record("DPO-067", "404 missing", 404, resp.status_code)

# ================================================================== #
#  Wingman + Sandbox                                                   #
# ================================================================== #

def test_dpo_070_wingman_valid():
    r = validate_wingman_pair("Pipeline ingests CSV data", "CSV row count=500")
    assert record("DPO-070", "Wingman pass", True, r["passed"])

def test_dpo_071_wingman_mismatch():
    r = validate_wingman_pair("x", "y" * 5000)
    assert record("DPO-071", "Wingman mismatch", False, r["passed"])

def test_dpo_072_sandbox_allowed():
    r = gate_pipeline_in_sandbox("run_etl", {"pipeline_id": "p1", "triggered_by": "ci"})
    assert record("DPO-072", "Sandbox pass", True, r["passed"])

def test_dpo_073_sandbox_forbidden():
    r = gate_pipeline_in_sandbox("drop_table", {"pipeline_id": "p1", "triggered_by": "ci"})
    assert record("DPO-073", "Sandbox block", False, r["passed"])

def test_dpo_074_wingman_empty_storyline():
    r = validate_wingman_pair("", "data")
    assert record("DPO-074", "Empty storyline", False, r["passed"])

def test_dpo_075_wingman_empty_actuals():
    r = validate_wingman_pair("story", "")
    assert record("DPO-075", "Empty actuals", False, r["passed"])

def test_dpo_076_sandbox_missing_keys():
    r = gate_pipeline_in_sandbox("run", {})
    assert record("DPO-076", "Missing metadata", False, r["passed"])

def test_dpo_077_sandbox_empty_pipeline_id():
    r = gate_pipeline_in_sandbox("run", {"pipeline_id": "", "triggered_by": "ci"})
    assert record("DPO-077", "Empty pipe id", False, r["passed"])

# ================================================================== #
#  Thread Safety                                                       #
# ================================================================== #

def test_dpo_080_concurrent_creation():
    o = _orch(); errors = []
    def _create(i: int):
        try: o.create_pipeline(f"pipe-{i}", stages=_stages())
        except Exception as exc: errors.append(exc)
    threads = [threading.Thread(target=_create, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert record("DPO-080", "Concurrent create", True,
                  len(errors) == 0 and len(o.list_pipelines()) == 20)

def test_dpo_081_concurrent_triggers():
    o = _orch(); p = _active_pipeline(o, stages=_stages())
    o.update_pipeline(p.id, max_concurrent_runs=20)
    errors = []
    def _trig():
        try:
            pipe = o.get_pipeline(p.id)
            for _ in range(5): _complete_run(o, pipe)
        except Exception as exc: errors.append(exc)
    threads = [threading.Thread(target=_trig) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert record("DPO-081", "Concurrent trigger", True, len(errors) == 0)

def test_dpo_082_concurrent_advance():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.update_pipeline(p.id, max_concurrent_runs=10)
    errors = []
    def _adv():
        try:
            run = o.trigger_run(p.id)
            if run:
                o.advance_stage(run.id, stg[0].id, records_processed=1)
        except Exception as exc: errors.append(exc)
    threads = [threading.Thread(target=_adv) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert record("DPO-082", "Concurrent advance", True, len(errors) == 0)

# ================================================================== #
#  Edge Cases                                                          #
# ================================================================== #

def test_dpo_090_empty_name():
    o = _orch(); p = o.create_pipeline("")
    assert record("DPO-090", "Empty name", True, p is not None and p.name == "")

def test_dpo_091_no_stages():
    o = _orch(); p = o.create_pipeline("empty-stages")
    assert record("DPO-091", "No stages", 0, len(p.stages))

def test_dpo_092_long_name():
    o = _orch(); name = "A" * 5000
    p = o.create_pipeline(name)
    assert record("DPO-092", "Long name", name, p.name)

def test_dpo_093_duplicate_names():
    o = _orch()
    a = o.create_pipeline("dup"); b = o.create_pipeline("dup")
    assert record("DPO-093", "Dup names diff IDs", True,
                  a.id != b.id and a.name == b.name)

def test_dpo_094_to_dict_roundtrip():
    o = _orch(); stg = _stages(2)
    p = o.create_pipeline("rt", stages=stg, owner="me", tags=["a"])
    d = p.to_dict()
    assert record("DPO-094", "to_dict keys", True,
                  d["name"] == "rt" and d["owner"] == "me" and len(d["stages"]) == 2)

def test_dpo_095_pipeline_run_to_dict():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    run = _complete_run(o, p)
    d = run.to_dict()
    assert record("DPO-095", "Run to_dict", "succeeded", d["status"])

def test_dpo_096_quality_check_to_dict():
    chk = DataQualityCheck(name="chk", pipeline_id="p1")
    d = chk.to_dict()
    assert record("DPO-096", "QC to_dict", "chk", d["name"])

def test_dpo_097_quality_result_to_dict():
    qr = QualityCheckResult(check_id="c1", passed=True, message="ok")
    d = qr.to_dict()
    assert record("DPO-097", "QR to_dict", True, d["passed"])

# ================================================================== #
#  Enum coverage                                                       #
# ================================================================== #

def test_dpo_098_pipeline_status_enum():
    expected = {"draft", "active", "paused", "completed", "failed", "archived"}
    assert record("DPO-098", "PipelineStatus values", expected,
                  {m.value for m in PipelineStatus})

def test_dpo_099_stage_type_enum():
    expected = {"extract", "transform", "load", "validate", "notify"}
    assert record("DPO-099", "StageType values", expected,
                  {m.value for m in StageType})

def test_dpo_100_schedule_type_enum():
    expected = {"manual", "interval", "cron_like", "event_triggered"}
    assert record("DPO-100", "ScheduleType values", expected,
                  {m.value for m in ScheduleType})

def test_dpo_101_run_status_enum():
    expected = {"pending", "running", "succeeded", "failed", "cancelled", "timed_out"}
    assert record("DPO-101", "RunStatus values", expected,
                  {m.value for m in RunStatus})

# ================================================================== #
#  Dataclass defaults                                                  #
# ================================================================== #

def test_dpo_102_pipeline_stage_defaults():
    s = PipelineStage()
    assert record("DPO-102", "Stage defaults", True,
                  bool(s.id) and s.stage_type == StageType.extract
                  and s.timeout_seconds == 300)

def test_dpo_103_data_pipeline_defaults():
    p = DataPipeline()
    assert record("DPO-103", "Pipeline defaults", True,
                  bool(p.id) and p.status == PipelineStatus.draft
                  and p.max_concurrent_runs == 1)

def test_dpo_104_pipeline_run_defaults():
    r = PipelineRun()
    assert record("DPO-104", "Run defaults", True,
                  bool(r.id) and r.status == RunStatus.pending)

def test_dpo_105_stage_to_dict():
    s = PipelineStage(name="ex", stage_type=StageType.load)
    d = s.to_dict()
    assert record("DPO-105", "Stage to_dict", "load", d["stage_type"])

# ================================================================== #
#  Format quality check                                                #
# ================================================================== #

def test_dpo_106_format_check_pass():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("fmt", p.id, "format", {"max_format_errors": 5})
    run = _complete_run(o, p, recs=100, fails=2)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-106", "Format pass", True, results[0].passed)

def test_dpo_107_format_check_fail():
    o = _orch(); stg = _stages(1); p = _active_pipeline(o, stages=stg)
    o.add_quality_check("fmt", p.id, "format", {"max_format_errors": 0})
    run = _complete_run(o, p, recs=100, fails=3)
    results = o.run_quality_checks(p.id, run.id)
    assert record("DPO-107", "Format fail", False, results[0].passed)

# ================================================================== #
#  Cancel status                                                       #
# ================================================================== #

def test_dpo_108_cancel_sets_status():
    o = _orch(); p = _active_pipeline(o); run = o.trigger_run(p.id)
    o.cancel_run(run.id)
    assert record("DPO-108", "Cancelled status", RunStatus.cancelled,
                  o.get_run(run.id).status)

def test_dpo_109_cancel_nonexistent():
    o = _orch()
    assert record("DPO-109", "Cancel missing", False, o.cancel_run("nope"))

# ================================================================== #
#  Max concurrent runs                                                 #
# ================================================================== #

def test_dpo_110_max_concurrent_blocks():
    o = _orch(); p = _active_pipeline(o)
    r1 = o.trigger_run(p.id)
    r2 = o.trigger_run(p.id)
    assert record("DPO-110", "Max concurrent", True,
                  r1 is not None and r2 is None)

# ================================================================== #
#  Summary                                                             #
# ================================================================== #

def test_dpo_999_summary():
    """Print all DPO check results."""
    width = 90
    print("\n" + "=" * width)
    print("DPO-001 Data Pipeline Orchestrator — Test Summary")
    print("=" * width)
    passed = sum(1 for r in _RESULTS if r.passed)
    total = len(_RESULTS)
    for r in _RESULTS:
        flag = "PASS" if r.passed else "FAIL"
        print(f"  [{flag}] {r.check_id}: {r.description}")
    print("-" * width)
    print(f"  Total: {total}  Passed: {passed}  Failed: {total - passed}")
    print("=" * width)
    assert record("DPO-999", "Summary", True, passed == total,
                  lesson="All DPO checks must pass")

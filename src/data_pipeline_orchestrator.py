# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1

"""Data Pipeline Orchestrator for Murphy's Decision Engine — DPO-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Manage ETL/ELT data pipelines: define stages, schedule runs, advance through
extract→transform→load→validate→notify stages, and enforce data-quality checks.

Classes: PipelineStatus/StageType/ScheduleType/RunStatus (enums),
PipelineStage/DataPipeline/PipelineRun/StageResult/DataQualityCheck/
QualityCheckResult (dataclasses), DataPipelineOrchestrator (thread-safe).
``create_pipeline_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via capped_append;
no external dependencies beyond stdlib + Flask.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]
    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}
    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}
        @staticmethod
        def get_json(silent: bool = True) -> dict: return {}
    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 50_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# -- Enums -----------------------------------------------------------------

class PipelineStatus(str, Enum):
    """Lifecycle status of a data pipeline."""
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    archived = "archived"

class StageType(str, Enum):
    """Type of pipeline stage."""
    extract = "extract"
    transform = "transform"
    load = "load"
    validate = "validate"
    notify = "notify"

class ScheduleType(str, Enum):
    """How a pipeline is triggered."""
    manual = "manual"
    interval = "interval"
    cron_like = "cron_like"
    event_triggered = "event_triggered"

class RunStatus(str, Enum):
    """Status of an individual pipeline run."""
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    timed_out = "timed_out"

# -- Dataclasses -----------------------------------------------------------

def _now() -> str: return datetime.now(timezone.utc).isoformat()

@dataclass
class PipelineStage:
    """A single stage within a data pipeline."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    stage_type: StageType = StageType.extract
    config: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    retry_count: int = 0
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["stage_type"] = self.stage_type.value
        return d


@dataclass
class DataPipeline:
    """Definition of a data pipeline."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    stages: List[PipelineStage] = field(default_factory=list)
    schedule_type: ScheduleType = ScheduleType.manual
    schedule_config: Dict[str, Any] = field(default_factory=dict)
    status: PipelineStatus = PipelineStatus.draft
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    tags: List[str] = field(default_factory=list)
    owner: str = ""
    max_concurrent_runs: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        d["schedule_type"] = self.schedule_type.value
        d["stages"] = [s.to_dict() if isinstance(s, PipelineStage) else s for s in self.stages]
        return d

@dataclass
class StageResult:
    """Outcome of a single stage execution."""
    stage_id: str = ""
    status: RunStatus = RunStatus.pending
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    records_processed: int = 0
    records_failed: int = 0
    error_message: str = ""
    output_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

@dataclass
class PipelineRun:
    """A single execution of a data pipeline."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    pipeline_id: str = ""
    status: RunStatus = RunStatus.pending
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    error_message: str = ""
    duration_seconds: float = 0.0
    triggered_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        d["stage_results"] = {
            k: (v.to_dict() if isinstance(v, StageResult) else v)
            for k, v in self.stage_results.items()
        }
        return d

@dataclass
class DataQualityCheck:
    """A data-quality rule bound to a pipeline."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    pipeline_id: str = ""
    check_type: str = "completeness"
    config: Dict[str, Any] = field(default_factory=dict)
    severity: str = "warning"
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

@dataclass
class QualityCheckResult:
    """Outcome of running a single quality check."""
    check_id: str = ""
    passed: bool = True
    message: str = ""
    checked_at: str = field(default_factory=_now)
    records_checked: int = 0
    records_failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

# -- Core orchestrator -----------------------------------------------------

class DataPipelineOrchestrator:
    """Thread-safe data-pipeline orchestrator.

    Parameters
    ----------
    max_pipelines : int  –  Maximum pipelines retained in memory.
    max_runs : int  –  Maximum runs retained in memory."""

    def __init__(self, max_pipelines: int = 2_000, max_runs: int = 50_000) -> None:
        self._lock = threading.Lock()
        self._pipelines: Dict[str, DataPipeline] = {}
        self._runs: Dict[str, PipelineRun] = {}
        self._quality_checks: Dict[str, DataQualityCheck] = {}
        self._run_log: List[PipelineRun] = []
        self._max_pipelines = max_pipelines
        self._max_runs = max_runs

    # -- Pipeline CRUD -----------------------------------------------------

    def create_pipeline(
        self,
        name: str,
        description: str = "",
        stages: Optional[List[PipelineStage]] = None,
        schedule_type: ScheduleType = ScheduleType.manual,
        schedule_config: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        owner: str = "",
        max_concurrent: int = 1,
    ) -> DataPipeline:
        """Create a new pipeline in *draft* status."""
        pipe = DataPipeline(
            name=name, description=description,
            stages=stages or [], schedule_type=schedule_type,
            schedule_config=schedule_config or {},
            tags=tags or [], owner=owner,
            max_concurrent_runs=max(1, max_concurrent),
        )
        with self._lock:
            if len(self._pipelines) >= self._max_pipelines:
                self._evict_archived_pipelines()
            self._pipelines[pipe.id] = pipe
        logger.info("Pipeline created: %s (%s)", pipe.name, pipe.id)
        return pipe

    def get_pipeline(self, pipeline_id: str) -> Optional[DataPipeline]:
        """Return a pipeline by ID, or *None*."""
        with self._lock:
            return self._pipelines.get(pipeline_id)

    def list_pipelines(
        self,
        status_filter: Optional[PipelineStatus] = None,
        owner_filter: Optional[str] = None,
        tag_filter: Optional[str] = None,
    ) -> List[DataPipeline]:
        """List pipelines with optional filters."""
        with self._lock:
            results = list(self._pipelines.values())
        if status_filter:
            results = [p for p in results if p.status == status_filter]
        if owner_filter:
            results = [p for p in results if p.owner == owner_filter]
        if tag_filter:
            results = [p for p in results if tag_filter in p.tags]
        return results

    def update_pipeline(self, pipeline_id: str, **kwargs: Any) -> Optional[DataPipeline]:
        """Update mutable fields on a pipeline."""
        allowed = {"name", "description", "stages", "schedule_type",
                    "schedule_config", "tags", "owner", "max_concurrent_runs"}
        # Accept the create_pipeline shorthand too
        if "max_concurrent" in kwargs:
            kwargs["max_concurrent_runs"] = kwargs.pop("max_concurrent")
        with self._lock:
            pipe = self._pipelines.get(pipeline_id)
            if not pipe:
                return None
            for key, val in kwargs.items():
                if key in allowed and val is not None:
                    setattr(pipe, key, val)
            pipe.updated_at = _now()
        return pipe

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Remove a pipeline. Returns *True* if it existed."""
        with self._lock:
            return self._pipelines.pop(pipeline_id, None) is not None

    def activate_pipeline(self, pipeline_id: str) -> Optional[DataPipeline]:
        """Transition a pipeline to *active*."""
        with self._lock:
            pipe = self._pipelines.get(pipeline_id)
            if not pipe or pipe.status not in (PipelineStatus.draft, PipelineStatus.paused):
                return None
            pipe.status = PipelineStatus.active
            pipe.updated_at = _now()
        return pipe

    def pause_pipeline(self, pipeline_id: str) -> Optional[DataPipeline]:
        """Transition a pipeline to *paused*."""
        with self._lock:
            pipe = self._pipelines.get(pipeline_id)
            if not pipe or pipe.status != PipelineStatus.active:
                return None
            pipe.status = PipelineStatus.paused
            pipe.updated_at = _now()
        return pipe

    # -- Run management ----------------------------------------------------

    def trigger_run(self, pipeline_id: str, triggered_by: str = "") -> Optional[PipelineRun]:
        """Trigger a new run for an *active* pipeline."""
        with self._lock:
            pipe = self._pipelines.get(pipeline_id)
            if not pipe or pipe.status != PipelineStatus.active:
                return None
            active = [r for r in self._runs.values()
                      if r.pipeline_id == pipeline_id
                      and r.status in (RunStatus.pending, RunStatus.running)]
            if len(active) >= pipe.max_concurrent_runs:
                return None
            run = PipelineRun(pipeline_id=pipeline_id, status=RunStatus.running,
                              triggered_by=triggered_by)
            if len(self._runs) >= self._max_runs:
                self._evict_completed_runs()
            self._runs[run.id] = run
            capped_append(self._run_log, run, self._max_runs)
        logger.info("Run triggered: %s for pipeline %s", run.id, pipeline_id)
        return run

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Return a run by ID, or *None*."""
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(
        self,
        pipeline_id: Optional[str] = None,
        status_filter: Optional[RunStatus] = None,
        limit: int = 100,
    ) -> List[PipelineRun]:
        """List runs with optional filters."""
        with self._lock:
            runs = list(self._runs.values())
        if pipeline_id:
            runs = [r for r in runs if r.pipeline_id == pipeline_id]
        if status_filter:
            runs = [r for r in runs if r.status == status_filter]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    def advance_stage(
        self,
        run_id: str,
        stage_id: str,
        records_processed: int = 0,
        records_failed: int = 0,
        output_metadata: Optional[Dict[str, Any]] = None,
        error_message: str = "",
    ) -> Optional[StageResult]:
        """Record stage completion and advance the run.

        If the stage failed (error_message set), the run is marked *failed*.
        When all stages succeed the run is marked *succeeded*.
        """
        with self._lock:
            run = self._runs.get(run_id)
            if not run or run.status != RunStatus.running:
                return None
            pipe = self._pipelines.get(run.pipeline_id)
            if not pipe:
                return None
            stage_ids = [s.id for s in pipe.stages]
            if stage_id not in stage_ids:
                return None
            status = RunStatus.failed if error_message else RunStatus.succeeded
            result = StageResult(
                stage_id=stage_id, status=status, completed_at=_now(),
                records_processed=records_processed,
                records_failed=records_failed,
                error_message=error_message,
                output_metadata=output_metadata or {},
            )
            run.stage_results[stage_id] = result
            if error_message:
                run.status = RunStatus.failed
                run.error_message = error_message
                run.completed_at = _now()
                self._compute_duration(run)
            elif all(sid in run.stage_results for sid in stage_ids):
                run.status = RunStatus.succeeded
                run.completed_at = _now()
                self._compute_duration(run)
        return result

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a pending or running run."""
        with self._lock:
            run = self._runs.get(run_id)
            if not run or run.status not in (RunStatus.pending, RunStatus.running):
                return False
            run.status = RunStatus.cancelled
            run.completed_at = _now()
            self._compute_duration(run)
        return True

    # -- Quality checks ----------------------------------------------------

    def add_quality_check(
        self,
        name: str,
        pipeline_id: str,
        check_type: str = "completeness",
        config: Optional[Dict[str, Any]] = None,
        severity: str = "warning",
        enabled: bool = True,
    ) -> DataQualityCheck:
        """Register a data-quality check for a pipeline."""
        chk = DataQualityCheck(
            name=name, pipeline_id=pipeline_id, check_type=check_type,
            config=config or {}, severity=severity, enabled=enabled,
        )
        with self._lock:
            self._quality_checks[chk.id] = chk
        logger.info("Quality check added: %s (%s)", chk.name, chk.id)
        return chk

    def list_quality_checks(self, pipeline_id: str) -> List[DataQualityCheck]:
        """Return all quality checks for a pipeline."""
        with self._lock:
            return [c for c in self._quality_checks.values()
                    if c.pipeline_id == pipeline_id]

    def run_quality_checks(self, pipeline_id: str, run_id: str) -> List[QualityCheckResult]:
        """Evaluate enabled quality checks against a completed run."""
        with self._lock:
            checks = [c for c in self._quality_checks.values()
                      if c.pipeline_id == pipeline_id and c.enabled]
            run = self._runs.get(run_id)
        if not run:
            return []
        results: List[QualityCheckResult] = []
        for chk in checks:
            results.append(self._evaluate_check(chk, run))
        return results

    # -- Statistics --------------------------------------------------------

    def get_pipeline_stats(self, pipeline_id: str) -> Dict[str, Any]:
        """Compute statistics for a single pipeline."""
        with self._lock:
            runs = [r for r in self._runs.values() if r.pipeline_id == pipeline_id]
            pipe = self._pipelines.get(pipeline_id)
        if not pipe:
            return {}
        succeeded = [r for r in runs if r.status == RunStatus.succeeded]
        failed = [r for r in runs if r.status == RunStatus.failed]
        durations = [r.duration_seconds for r in succeeded if r.duration_seconds > 0]
        avg_dur = sum(durations) / len(durations) if durations else 0.0
        stage_stats: Dict[str, Dict[str, int]] = {}
        for r in runs:
            for sid, sr in r.stage_results.items():
                entry = stage_stats.setdefault(
                    sid, {"succeeded": 0, "failed": 0, "total_records": 0})
                if isinstance(sr, StageResult):
                    if sr.status == RunStatus.succeeded:
                        entry["succeeded"] += 1
                    else:
                        entry["failed"] += 1
                    entry["total_records"] += sr.records_processed
        return {"pipeline_id": pipeline_id, "total_runs": len(runs),
                "succeeded": len(succeeded), "failed": len(failed),
                "avg_duration_seconds": round(avg_dur, 3),
                "stage_breakdown": stage_stats}

    def get_global_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics across all pipelines."""
        with self._lock:
            total_pipes = len(self._pipelines)
            statuses: Dict[str, int] = {}
            for p in self._pipelines.values():
                statuses[p.status.value] = statuses.get(p.status.value, 0) + 1
            total_runs = len(self._runs)
            run_statuses: Dict[str, int] = {}
            for r in self._runs.values():
                run_statuses[r.status.value] = run_statuses.get(r.status.value, 0) + 1
        return {"total_pipelines": total_pipes, "pipeline_statuses": statuses,
                "total_runs": total_runs, "run_statuses": run_statuses}

    # -- Private helpers ---------------------------------------------------

    def _evict_archived_pipelines(self) -> None:
        """Remove oldest archived pipelines to free space (call under lock)."""
        archived = sorted((p for p in self._pipelines.values()
                           if p.status == PipelineStatus.archived),
                          key=lambda p: p.updated_at)
        for p in archived[: max(1, len(archived) // 2)]:
            del self._pipelines[p.id]

    def _evict_completed_runs(self) -> None:
        """Remove oldest completed runs to free space (call under lock)."""
        done = sorted((r for r in self._runs.values()
                       if r.status in (RunStatus.succeeded, RunStatus.failed,
                                       RunStatus.cancelled, RunStatus.timed_out)),
                      key=lambda r: r.started_at)
        for r in done[: max(1, len(done) // 2)]:
            del self._runs[r.id]

    @staticmethod
    def _compute_duration(run: PipelineRun) -> None:
        """Set duration_seconds from started_at / completed_at."""
        try:
            start = datetime.fromisoformat(run.started_at)
            end = datetime.fromisoformat(run.completed_at)
            run.duration_seconds = round((end - start).total_seconds(), 3)
        except (ValueError, TypeError):
            run.duration_seconds = 0.0

    @staticmethod
    def _evaluate_check(chk: DataQualityCheck, run: PipelineRun) -> QualityCheckResult:
        """Evaluate a single quality check against run stage results."""
        total_processed = 0
        total_failed = 0
        for sr in run.stage_results.values():
            if isinstance(sr, StageResult):
                total_processed += sr.records_processed
                total_failed += sr.records_failed
        cfg = chk.config
        passed = True
        message = "Check passed"
        if chk.check_type == "completeness":
            threshold = cfg.get("min_records", 1)
            if total_processed < threshold:
                passed = False
                message = f"Processed {total_processed} records, need >= {threshold}"
        elif chk.check_type == "uniqueness":
            max_dup = cfg.get("max_duplicates", 0)
            if total_failed > max_dup:
                passed = False
                message = f"{total_failed} failures exceed max duplicates {max_dup}"
        elif chk.check_type == "range":
            max_fail_rate = cfg.get("max_failure_rate", 0.01)
            rate = total_failed / total_processed if total_processed else 0.0
            if rate > max_fail_rate:
                passed = False
                message = f"Failure rate {rate:.4f} exceeds {max_fail_rate}"
        elif chk.check_type == "format":
            if total_failed > cfg.get("max_format_errors", 0):
                passed = False
                message = f"{total_failed} format errors detected"
        elif chk.check_type == "custom":
            expr = cfg.get("expression", "")
            if not expr:
                passed = False
                message = "Custom check has no expression configured"
        return QualityCheckResult(
            check_id=chk.id, passed=passed, message=message,
            records_checked=total_processed, records_failed=total_failed,
        )

# -- Wingman + Causality Sandbox gates -------------------------------------

def validate_wingman_pair(storyline: str, actuals: str) -> dict:
    """DPO-001 Wingman gate.

    Validate that a storyline and actuals pair is non-empty and coherent.
    Returns a pass/fail dict with diagnostics.
    """
    if not storyline or not storyline.strip():
        return {"passed": False, "message": "Storyline is empty"}
    if not actuals or not actuals.strip():
        return {"passed": False, "message": "Actuals data is empty"}
    sl, al = len(storyline.strip()), len(actuals.strip())
    ratio = max(sl, al) / max(min(sl, al), 1)
    if ratio > 50:
        return {"passed": False,
                "message": f"Length mismatch ratio {ratio:.1f} exceeds threshold"}
    return {"passed": True, "message": "Wingman pair validated",
            "storyline_len": sl, "actuals_len": al}

def gate_pipeline_in_sandbox(action: str, metadata: dict) -> dict:
    """DPO-001 Causality Sandbox gate.

    Verify that a pipeline action is permitted inside the sandbox and that
    required metadata keys are present.
    """
    forbidden = {"drop_table", "truncate", "delete_all", "shutdown", "exec_raw"}
    if action in forbidden:
        return {"passed": False,
                "message": f"Action '{action}' is forbidden in sandbox"}
    required_keys = {"pipeline_id", "triggered_by"}
    missing = required_keys - set(metadata.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing metadata keys: {sorted(missing)}"}
    if not metadata.get("pipeline_id"):
        return {"passed": False, "message": "pipeline_id must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed", "action": action}

# -- Flask Blueprint helpers ------------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "DPO_MISSING"}), 400
    return None

def _api_404(msg: str = "Not found") -> Any:
    """Standard 404 response."""
    return jsonify({"error": msg, "code": "DPO_404"}), 404

def _parse_stages(raw: List[Dict[str, Any]]) -> List[PipelineStage]:
    """Build PipelineStage list from raw JSON dicts."""
    out: List[PipelineStage] = []
    for s in raw:
        out.append(PipelineStage(
            id=s.get("id", uuid.uuid4().hex[:12]),
            name=s.get("name", ""),
            stage_type=StageType(s.get("stage_type", "extract")),
            config=s.get("config", {}),
            timeout_seconds=int(s.get("timeout_seconds", 300)),
            retry_count=int(s.get("retry_count", 0)),
            depends_on=s.get("depends_on", []),
        ))
    return out

# -- Flask Blueprint route registration ------------------------------------
def _register_pipeline_routes(bp: Any, engine: DataPipelineOrchestrator) -> None:
    """Attach pipeline CRUD + action routes to *bp*."""

    @bp.route("/pipelines", methods=["POST"])
    def create_pipeline() -> Any:
        b = _api_body()
        err = _api_need(b, "name")
        if err:
            return err
        pipe = engine.create_pipeline(
            name=b["name"], description=b.get("description", ""),
            stages=_parse_stages(b.get("stages", [])),
            schedule_type=ScheduleType(b.get("schedule_type", "manual")),
            schedule_config=b.get("schedule_config", {}),
            tags=b.get("tags", []), owner=b.get("owner", ""),
            max_concurrent=int(b.get("max_concurrent_runs", 1)),
        )
        return jsonify(pipe.to_dict()), 201

    @bp.route("/pipelines", methods=["GET"])
    def list_pipelines() -> Any:
        sv = request.args.get("status")
        status = PipelineStatus(sv) if sv else None
        owner = request.args.get("owner")
        tag = request.args.get("tag")
        return jsonify([p.to_dict() for p in engine.list_pipelines(status, owner, tag)])

    @bp.route("/pipelines/stats/global", methods=["GET"])
    def global_stats() -> Any:
        return jsonify(engine.get_global_stats())

    @bp.route("/pipelines/<pid>", methods=["GET"])
    def get_pipeline(pid: str) -> Any:
        p = engine.get_pipeline(pid)
        return jsonify(p.to_dict()) if p else _api_404()

    @bp.route("/pipelines/<pid>", methods=["PUT"])
    def update_pipeline(pid: str) -> Any:
        b = _api_body()
        p = engine.update_pipeline(pid, **b)
        return jsonify(p.to_dict()) if p else _api_404()

    @bp.route("/pipelines/<pid>", methods=["DELETE"])
    def delete_pipeline(pid: str) -> Any:
        if engine.delete_pipeline(pid):
            return jsonify({"deleted": True})
        return _api_404()

    @bp.route("/pipelines/<pid>/activate", methods=["POST"])
    def activate_pipeline(pid: str) -> Any:
        p = engine.activate_pipeline(pid)
        if p:
            return jsonify(p.to_dict())
        return jsonify({"error": "Cannot activate", "code": "DPO_STATE"}), 409

    @bp.route("/pipelines/<pid>/pause", methods=["POST"])
    def pause_pipeline(pid: str) -> Any:
        p = engine.pause_pipeline(pid)
        if p:
            return jsonify(p.to_dict())
        return jsonify({"error": "Cannot pause", "code": "DPO_STATE"}), 409

    @bp.route("/pipelines/<pid>/trigger", methods=["POST"])
    def trigger_run(pid: str) -> Any:
        b = _api_body()
        run = engine.trigger_run(pid, triggered_by=b.get("triggered_by", ""))
        if run:
            return jsonify(run.to_dict()), 201
        return jsonify({"error": "Cannot trigger run", "code": "DPO_STATE"}), 409

    @bp.route("/pipelines/<pid>/runs", methods=["GET"])
    def list_pipeline_runs(pid: str) -> Any:
        sv = request.args.get("status")
        status = RunStatus(sv) if sv else None
        limit = int(request.args.get("limit", 100))
        return jsonify([r.to_dict() for r in engine.list_runs(pid, status, limit)])

    @bp.route("/pipelines/<pid>/stats", methods=["GET"])
    def pipeline_stats(pid: str) -> Any:
        stats = engine.get_pipeline_stats(pid)
        return jsonify(stats) if stats else _api_404()

def _register_run_routes(bp: Any, engine: DataPipelineOrchestrator) -> None:
    """Attach run-level routes to *bp*."""

    @bp.route("/runs/<rid>", methods=["GET"])
    def get_run(rid: str) -> Any:
        r = engine.get_run(rid)
        return jsonify(r.to_dict()) if r else _api_404()

    @bp.route("/runs/<rid>/stages/<stage_id>/advance", methods=["POST"])
    def advance_stage(rid: str, stage_id: str) -> Any:
        b = _api_body()
        result = engine.advance_stage(
            run_id=rid, stage_id=stage_id,
            records_processed=int(b.get("records_processed", 0)),
            records_failed=int(b.get("records_failed", 0)),
            output_metadata=b.get("output_metadata"),
            error_message=b.get("error_message", ""),
        )
        if result:
            return jsonify(result.to_dict())
        return jsonify({"error": "Cannot advance stage", "code": "DPO_STATE"}), 409

    @bp.route("/runs/<rid>/cancel", methods=["POST"])
    def cancel_run(rid: str) -> Any:
        if engine.cancel_run(rid):
            return jsonify({"cancelled": True})
        return jsonify({"error": "Cannot cancel run", "code": "DPO_STATE"}), 409

def _register_quality_routes(bp: Any, engine: DataPipelineOrchestrator) -> None:
    """Attach quality-check routes to *bp*."""

    @bp.route("/quality-checks", methods=["POST"])
    def add_quality_check() -> Any:
        b = _api_body()
        err = _api_need(b, "name", "pipeline_id")
        if err:
            return err
        chk = engine.add_quality_check(
            name=b["name"], pipeline_id=b["pipeline_id"],
            check_type=b.get("check_type", "completeness"),
            config=b.get("config", {}),
            severity=b.get("severity", "warning"),
            enabled=b.get("enabled", True),
        )
        return jsonify(chk.to_dict()), 201

    @bp.route("/quality-checks", methods=["GET"])
    def list_quality_checks() -> Any:
        pid = request.args.get("pipeline_id", "")
        if not pid:
            return jsonify({"error": "pipeline_id required", "code": "DPO_MISSING"}), 400
        return jsonify([c.to_dict() for c in engine.list_quality_checks(pid)])

    @bp.route("/quality-checks/<pid>/run", methods=["POST"])
    def run_quality_checks(pid: str) -> Any:
        b = _api_body()
        rid = b.get("run_id", "")
        if not rid:
            return jsonify({"error": "run_id required", "code": "DPO_MISSING"}), 400
        results = engine.run_quality_checks(pid, rid)
        return jsonify([r.to_dict() for r in results])

# -- Blueprint factory -----------------------------------------------------

def create_pipeline_api(engine: DataPipelineOrchestrator) -> Any:
    """Create a Flask Blueprint exposing data-pipeline endpoints.

    All routes live under ``/api`` and return JSON with an error envelope
    ``{"error": "…", "code": "DPO_*"}`` on failure.
    """
    if not _HAS_FLASK:
        return Blueprint("data_pipelines", __name__)  # type: ignore[call-arg]
    bp = Blueprint("data_pipelines", __name__, url_prefix="/api")
    _register_pipeline_routes(bp, engine)
    _register_run_routes(bp, engine)
    _register_quality_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp

# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""CI/CD Pipeline Manager — CICD-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Programmatic CI/CD pipeline management for the Murphy System — pipeline
definitions, triggers, status monitoring, artifact tracking, and deployment
gates with full lifecycle control.

Classes: PipelineStage/PipelineStatus/TriggerType/DeployEnvironment (enums),
StageResult/PipelineDefinition/PipelineRun/BuildArtifact (dataclasses),
PipelineManager (thread-safe orchestrator).
``create_cicd_api(manager)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state guarded by threading.Lock; run/artifact lists
bounded via capped_append (CWE-770); no secrets stored in artifact paths.
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

    class _StubBlueprint:
        """No-op Blueprint stand-in when Flask is absent."""
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass
        def route(self, *a: Any, **kw: Any) -> Any:
            return lambda fn: fn

    Blueprint = _StubBlueprint  # type: ignore[misc,assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PipelineStage(str, Enum):
    """Ordered stages a pipeline may execute."""
    SOURCE = "source"
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    PACKAGE = "package"
    DEPLOY_STAGING = "deploy_staging"
    INTEGRATION_TEST = "integration_test"
    DEPLOY_PRODUCTION = "deploy_production"

class PipelineStatus(str, Enum):
    """Lifecycle status of a pipeline run or stage."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"

class TriggerType(str, Enum):
    """What initiated a pipeline run."""
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    WEBHOOK = "webhook"
    TAG = "tag"


class DeployEnvironment(str, Enum):
    """Target deployment environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    CANARY = "canary"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Outcome record for a single pipeline stage."""
    stage: PipelineStage
    status: PipelineStatus
    started_at: str
    finished_at: str
    duration_seconds: float
    logs: str
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data = asdict(self)
        data["stage"] = self.stage.value
        data["status"] = self.status.value
        return data


@dataclass
class PipelineDefinition:
    """Declarative template for a CI/CD pipeline."""
    pipeline_id: str
    name: str
    repository: str
    branch_pattern: str
    stages: List[PipelineStage]
    trigger_types: List[TriggerType]
    environment: DeployEnvironment
    timeout_seconds: int = 1800
    max_retries: int = 0
    require_approval: bool = False
    created_at: str = ""
    updated_at: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data = asdict(self)
        data["stages"] = [s.value for s in self.stages]
        data["trigger_types"] = [t.value for t in self.trigger_types]
        data["environment"] = self.environment.value
        return data


@dataclass
class PipelineRun:
    """Single execution of a pipeline definition."""
    run_id: str
    pipeline_id: str
    trigger_type: TriggerType
    trigger_ref: str
    status: PipelineStatus
    stage_results: List[StageResult]
    current_stage: Optional[PipelineStage]
    started_at: str
    finished_at: str
    triggered_by: str
    approval_required: bool = False
    approved_by: str = ""
    artifacts: List[str] = field(default_factory=list)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data: Dict[str, Any] = {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "trigger_type": self.trigger_type.value,
            "trigger_ref": self.trigger_ref,
            "status": self.status.value,
            "stage_results": [sr.to_dict() for sr in self.stage_results],
            "current_stage": self.current_stage.value if self.current_stage else None,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "triggered_by": self.triggered_by,
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "artifacts": list(self.artifacts),
            "retry_count": self.retry_count,
        }
        return data


@dataclass
class BuildArtifact:
    """Tracked artifact produced by a pipeline run."""
    artifact_id: str
    run_id: str
    pipeline_id: str
    name: str
    artifact_type: str
    size_bytes: int
    checksum_sha256: str
    storage_path: str
    created_at: str
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return asdict(self)

# ---------------------------------------------------------------------------
# PipelineManager
# ---------------------------------------------------------------------------

_MAX_RUNS = 10_000
_MAX_ARTIFACTS = 10_000


class PipelineManager:
    """Thread-safe orchestrator for CI/CD pipeline management."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipelines: Dict[str, PipelineDefinition] = {}
        self._runs: Dict[str, PipelineRun] = {}
        self._artifacts: Dict[str, BuildArtifact] = {}
        self._run_list: List[str] = []
        self._artifact_list: List[str] = []

    @staticmethod
    def _now() -> str:
        """Return current UTC timestamp as ISO-8601 string."""
        return datetime.now(timezone.utc).isoformat()

    # -- Pipeline CRUD -----------------------------------------------------

    def create_pipeline(
        self,
        name: str,
        repository: str,
        branch_pattern: str,
        stages: List[PipelineStage],
        trigger_types: List[TriggerType],
        environment: DeployEnvironment,
        timeout_seconds: int = 1800,
        max_retries: int = 0,
        require_approval: bool = False,
        pipeline_id: Optional[str] = None,
    ) -> PipelineDefinition:
        """Create a new pipeline definition; raises ValueError if fields are empty."""
        if not name or not repository or not stages or not trigger_types:
            raise ValueError("name, repository, stages, and trigger_types are required")

        now = self._now()
        pid = pipeline_id or uuid.uuid4().hex
        defn = PipelineDefinition(
            pipeline_id=pid,
            name=name,
            repository=repository,
            branch_pattern=branch_pattern,
            stages=list(stages),
            trigger_types=list(trigger_types),
            environment=environment,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            require_approval=require_approval,
            created_at=now,
            updated_at=now,
            enabled=True,
        )
        with self._lock:
            self._pipelines[pid] = defn
        logger.info("Pipeline created: %s (%s)", pid, name)
        return defn

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineDefinition]:
        """Return a pipeline definition by ID, or None."""
        with self._lock:
            return self._pipelines.get(pipeline_id)

    def list_pipelines(
        self,
        repository: Optional[str] = None,
        environment: Optional[DeployEnvironment] = None,
    ) -> List[PipelineDefinition]:
        """List pipelines, optionally filtered by repository and/or environment."""
        with self._lock:
            results = list(self._pipelines.values())
        if repository:
            results = [p for p in results if p.repository == repository]
        if environment:
            results = [p for p in results if p.environment == environment]
        return results

    def update_pipeline(self, pipeline_id: str, **kwargs: Any) -> PipelineDefinition:
        """Update mutable fields on a pipeline; raises KeyError if not found."""
        with self._lock:
            defn = self._pipelines.get(pipeline_id)
            if defn is None:
                raise KeyError(f"Pipeline {pipeline_id} not found")
            allowed = {
                "name", "branch_pattern", "stages", "trigger_types",
                "environment", "timeout_seconds", "max_retries",
                "require_approval", "enabled",
            }
            for k, v in kwargs.items():
                if k in allowed:
                    setattr(defn, k, v)
            defn.updated_at = self._now()
        return defn

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline definition; returns True if deleted, False if not found."""
        with self._lock:
            return self._pipelines.pop(pipeline_id, None) is not None

    def enable_pipeline(self, pipeline_id: str) -> PipelineDefinition:
        """Enable a pipeline; raises KeyError if not found."""
        return self.update_pipeline(pipeline_id, enabled=True)

    def disable_pipeline(self, pipeline_id: str) -> PipelineDefinition:
        """Disable a pipeline; raises KeyError if not found."""
        return self.update_pipeline(pipeline_id, enabled=False)

    # -- Run management ----------------------------------------------------

    def trigger_run(
        self,
        pipeline_id: str,
        trigger_type: TriggerType,
        trigger_ref: str,
        triggered_by: str,
    ) -> PipelineRun:
        """Trigger a new pipeline run; raises KeyError/RuntimeError on invalid state."""
        with self._lock:
            defn = self._pipelines.get(pipeline_id)
            if defn is None:
                raise KeyError(f"Pipeline {pipeline_id} not found")
            if not defn.enabled:
                raise RuntimeError(f"Pipeline {pipeline_id} is disabled")
            now = self._now()
            run = PipelineRun(
                run_id=uuid.uuid4().hex,
                pipeline_id=pipeline_id,
                trigger_type=trigger_type,
                trigger_ref=trigger_ref,
                status=PipelineStatus.RUNNING,
                stage_results=[],
                current_stage=defn.stages[0] if defn.stages else None,
                started_at=now,
                finished_at="",
                triggered_by=triggered_by,
                approval_required=defn.require_approval,
            )
            self._runs[run.run_id] = run
            capped_append(self._run_list, run.run_id, _MAX_RUNS)
        logger.info("Run triggered: %s for pipeline %s", run.run_id, pipeline_id)
        return run

    def advance_stage(
        self,
        run_id: str,
        stage: PipelineStage,
        status: PipelineStatus,
        logs: str = "",
        artifacts: Optional[List[str]] = None,
        duration: float = 0.0,
    ) -> PipelineRun:
        """Record a stage result and advance the run; raises KeyError/RuntimeError."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Run {run_id} not found")
            if run.status not in (PipelineStatus.RUNNING, PipelineStatus.PENDING):
                raise RuntimeError(f"Run {run_id} is {run.status.value}, cannot advance")

            now = self._now()
            result = StageResult(
                stage=stage,
                status=status,
                started_at=now,
                finished_at=now,
                duration_seconds=duration,
                logs=logs[-4096:] if logs else "",
                artifacts=list(artifacts or []),
            )
            run.stage_results.append(result)

            if status == PipelineStatus.FAILED:
                defn = self._pipelines.get(run.pipeline_id)
                max_ret = defn.max_retries if defn else 0
                if run.retry_count < max_ret:
                    run.retry_count += 1
                    run.status = PipelineStatus.RUNNING
                    logger.info("Run %s retrying (%d/%d)", run_id, run.retry_count, max_ret)
                else:
                    run.status = PipelineStatus.FAILED
                    run.finished_at = now
            elif status == PipelineStatus.PASSED:
                defn = self._pipelines.get(run.pipeline_id)
                if defn:
                    stage_list = defn.stages
                    try:
                        idx = stage_list.index(stage)
                    except ValueError:
                        idx = -1
                    if idx + 1 < len(stage_list):
                        run.current_stage = stage_list[idx + 1]
                    else:
                        run.status = PipelineStatus.PASSED
                        run.finished_at = now
                        run.current_stage = None
                else:
                    run.status = PipelineStatus.PASSED
                    run.finished_at = now
                    run.current_stage = None
            if artifacts:
                run.artifacts.extend(artifacts)
        return run

    def approve_run(self, run_id: str, approved_by: str) -> PipelineRun:
        """Approve a manual gate; raises KeyError/RuntimeError."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Run {run_id} not found")
            if not run.approval_required:
                raise RuntimeError(f"Run {run_id} does not require approval")
            run.approved_by = approved_by
        logger.info("Run %s approved by %s", run_id, approved_by)
        return run

    def cancel_run(self, run_id: str) -> PipelineRun:
        """Cancel a running pipeline run; raises KeyError/RuntimeError."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Run {run_id} not found")
            terminal = {PipelineStatus.PASSED, PipelineStatus.FAILED, PipelineStatus.CANCELLED}
            if run.status in terminal:
                raise RuntimeError(f"Run {run_id} already finished ({run.status.value})")
            run.status = PipelineStatus.CANCELLED
            run.finished_at = self._now()
        logger.info("Run %s cancelled", run_id)
        return run

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Return a pipeline run by ID, or None."""
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(
        self,
        pipeline_id: Optional[str] = None,
        status: Optional[PipelineStatus] = None,
        limit: int = 50,
    ) -> List[PipelineRun]:
        """List pipeline runs, optionally filtered by pipeline_id and/or status."""
        with self._lock:
            runs = list(self._runs.values())
        if pipeline_id:
            runs = [r for r in runs if r.pipeline_id == pipeline_id]
        if status:
            runs = [r for r in runs if r.status == status]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    # -- Artifact management -----------------------------------------------

    def register_artifact(
        self,
        run_id: str,
        name: str,
        artifact_type: str,
        size_bytes: int,
        checksum_sha256: str,
        storage_path: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> BuildArtifact:
        """Register a build artifact for a run; raises KeyError if run not found."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Run {run_id} not found")
            aid = uuid.uuid4().hex
            artifact = BuildArtifact(
                artifact_id=aid,
                run_id=run_id,
                pipeline_id=run.pipeline_id,
                name=name,
                artifact_type=artifact_type,
                size_bytes=size_bytes,
                checksum_sha256=checksum_sha256,
                storage_path=storage_path,
                created_at=self._now(),
                metadata=dict(metadata or {}),
            )
            self._artifacts[aid] = artifact
            capped_append(self._artifact_list, aid, _MAX_ARTIFACTS)
            run.artifacts.append(aid)
        logger.info("Artifact registered: %s for run %s", aid, run_id)
        return artifact

    def get_artifact(self, artifact_id: str) -> Optional[BuildArtifact]:
        """Return a build artifact by ID, or None."""
        with self._lock:
            return self._artifacts.get(artifact_id)

    def get_run_artifacts(self, run_id: str) -> List[BuildArtifact]:
        """Return all artifacts for a given run."""
        with self._lock:
            return [a for a in self._artifacts.values() if a.run_id == run_id]

    # -- Statistics --------------------------------------------------------

    def get_pipeline_stats(self, pipeline_id: str) -> Dict[str, Any]:
        """Compute statistics for a pipeline; raises KeyError if not found."""
        with self._lock:
            if pipeline_id not in self._pipelines:
                raise KeyError(f"Pipeline {pipeline_id} not found")
            runs = [r for r in self._runs.values() if r.pipeline_id == pipeline_id]

        total = len(runs)
        passed = sum(1 for r in runs if r.status == PipelineStatus.PASSED)
        failed = sum(1 for r in runs if r.status == PipelineStatus.FAILED)
        cancelled = sum(1 for r in runs if r.status == PipelineStatus.CANCELLED)

        durations: List[float] = []
        for r in runs:
            for sr in r.stage_results:
                durations.append(sr.duration_seconds)

        avg_dur = sum(durations) / (len(durations) or 1) if durations else 0.0
        recent_failures = [
            r.run_id for r in sorted(runs, key=lambda x: x.started_at, reverse=True)
            if r.status == PipelineStatus.FAILED
        ][:5]

        return {
            "pipeline_id": pipeline_id,
            "total_runs": total,
            "passed_runs": passed,
            "failed_runs": failed,
            "cancelled_runs": cancelled,
            "success_rate": round(passed / total, 4) if total else 0.0,
            "avg_duration_seconds": round(avg_dur, 2),
            "recent_failures": recent_failures,
        }

    # -- Timeout check (used by external schedulers) -----------------------

    def check_timeout(self, run_id: str) -> bool:
        """Check if a run has exceeded its pipeline timeout; returns True if timed out."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status != PipelineStatus.RUNNING:
                return False
            defn = self._pipelines.get(run.pipeline_id)
            if defn is None:
                return False
            try:
                started = datetime.fromisoformat(run.started_at)
            except (ValueError, TypeError):
                return False
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if elapsed > defn.timeout_seconds:
                run.status = PipelineStatus.FAILED
                run.finished_at = self._now()
                logger.warning("Run %s timed out after %.1fs", run_id, elapsed)
                return True
        return False

# ---------------------------------------------------------------------------
# Flask Blueprint
# ---------------------------------------------------------------------------


def create_cicd_api(
    manager: Optional[PipelineManager] = None,
) -> Any:
    """Create a Flask Blueprint for CI/CD pipeline management."""
    mgr = manager or PipelineManager()

    if not _HAS_FLASK:
        return Blueprint()  # type: ignore[call-arg]

    bp = Blueprint("cicd", __name__, url_prefix="/api/cicd")

    # -- Pipeline CRUD -----------------------------------------------------

    @bp.route("/pipelines", methods=["POST"])
    def create_pipeline() -> Any:
        """Create a new pipeline definition."""
        body = request.get_json(silent=True) or {}
        name = body.get("name", "")
        repository = body.get("repository", "")
        if not name or not repository:
            return jsonify({"error": "name and repository are required", "code": "MISSING_FIELDS"}), 400
        try:
            stages = [PipelineStage(s) for s in body.get("stages", [])]
            trigger_types = [TriggerType(t) for t in body.get("trigger_types", [])]
            environment = DeployEnvironment(body.get("environment", "development"))
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_ENUM"}), 400
        if not stages or not trigger_types:
            return jsonify({"error": "stages and trigger_types are required", "code": "MISSING_FIELDS"}), 400
        try:
            defn = mgr.create_pipeline(
                name=name,
                repository=repository,
                branch_pattern=body.get("branch_pattern", ".*"),
                stages=stages,
                trigger_types=trigger_types,
                environment=environment,
                timeout_seconds=int(body.get("timeout_seconds", 1800)),
                max_retries=int(body.get("max_retries", 0)),
                require_approval=bool(body.get("require_approval", False)),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "VALIDATION_ERROR"}), 400
        return jsonify(defn.to_dict()), 201

    @bp.route("/pipelines", methods=["GET"])
    def list_pipelines() -> Any:
        """List pipelines with optional filters."""
        repo = request.args.get("repository")
        env_str = request.args.get("environment")
        env = DeployEnvironment(env_str) if env_str else None
        results = mgr.list_pipelines(repository=repo, environment=env)
        return jsonify([p.to_dict() for p in results])

    @bp.route("/pipelines/<pid>", methods=["GET"])
    def get_pipeline(pid: str) -> Any:
        """Get a pipeline by ID."""
        defn = mgr.get_pipeline(pid)
        if defn is None:
            return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404
        return jsonify(defn.to_dict())

    @bp.route("/pipelines/<pid>", methods=["PUT"])
    def update_pipeline(pid: str) -> Any:
        """Update a pipeline definition."""
        body = request.get_json(silent=True) or {}
        try:
            updated = mgr.update_pipeline(pid, **body)
        except KeyError:
            return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404
        return jsonify(updated.to_dict())

    @bp.route("/pipelines/<pid>", methods=["DELETE"])
    def delete_pipeline(pid: str) -> Any:
        """Delete a pipeline."""
        if mgr.delete_pipeline(pid):
            return jsonify({"deleted": True})
        return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404

    @bp.route("/pipelines/<pid>/enable", methods=["POST"])
    def enable_pipeline(pid: str) -> Any:
        """Enable a pipeline."""
        try:
            defn = mgr.enable_pipeline(pid)
        except KeyError:
            return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404
        return jsonify(defn.to_dict())

    @bp.route("/pipelines/<pid>/disable", methods=["POST"])
    def disable_pipeline(pid: str) -> Any:
        """Disable a pipeline."""
        try:
            defn = mgr.disable_pipeline(pid)
        except KeyError:
            return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404
        return jsonify(defn.to_dict())

    @bp.route("/pipelines/<pid>/trigger", methods=["POST"])
    def trigger_run(pid: str) -> Any:
        """Trigger a pipeline run."""
        body = request.get_json(silent=True) or {}
        try:
            ttype = TriggerType(body.get("trigger_type", "manual"))
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_ENUM"}), 400
        try:
            run = mgr.trigger_run(
                pipeline_id=pid,
                trigger_type=ttype,
                trigger_ref=body.get("trigger_ref", ""),
                triggered_by=body.get("triggered_by", "system"),
            )
        except KeyError:
            return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc), "code": "PIPELINE_DISABLED"}), 409
        return jsonify(run.to_dict()), 201

    @bp.route("/pipelines/<pid>/stats", methods=["GET"])
    def pipeline_stats(pid: str) -> Any:
        """Get pipeline statistics."""
        try:
            stats = mgr.get_pipeline_stats(pid)
        except KeyError:
            return jsonify({"error": "Pipeline not found", "code": "PIPELINE_NOT_FOUND"}), 404
        return jsonify(stats)

    # -- Run endpoints -----------------------------------------------------

    @bp.route("/runs", methods=["GET"])
    def list_runs() -> Any:
        """List runs with optional filters."""
        pid = request.args.get("pipeline_id")
        status_str = request.args.get("status")
        limit = int(request.args.get("limit", 50))
        st = PipelineStatus(status_str) if status_str else None
        results = mgr.list_runs(pipeline_id=pid, status=st, limit=limit)
        return jsonify([r.to_dict() for r in results])

    @bp.route("/runs/<rid>", methods=["GET"])
    def get_run(rid: str) -> Any:
        """Get run details."""
        run = mgr.get_run(rid)
        if run is None:
            return jsonify({"error": "Run not found", "code": "RUN_NOT_FOUND"}), 404
        return jsonify(run.to_dict())

    @bp.route("/runs/<rid>/advance", methods=["POST"])
    def advance_stage(rid: str) -> Any:
        """Advance a run to the next stage."""
        body = request.get_json(silent=True) or {}
        try:
            stage = PipelineStage(body.get("stage", ""))
            status = PipelineStatus(body.get("status", ""))
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_ENUM"}), 400
        try:
            run = mgr.advance_stage(
                run_id=rid,
                stage=stage,
                status=status,
                logs=body.get("logs", ""),
                artifacts=body.get("artifacts"),
                duration=float(body.get("duration", 0)),
            )
        except KeyError:
            return jsonify({"error": "Run not found", "code": "RUN_NOT_FOUND"}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_STATE"}), 409
        return jsonify(run.to_dict())

    @bp.route("/runs/<rid>/approve", methods=["POST"])
    def approve_run(rid: str) -> Any:
        """Approve a manual gate."""
        body = request.get_json(silent=True) or {}
        try:
            run = mgr.approve_run(rid, approved_by=body.get("approved_by", ""))
        except KeyError:
            return jsonify({"error": "Run not found", "code": "RUN_NOT_FOUND"}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc), "code": "APPROVAL_NOT_REQUIRED"}), 409
        return jsonify(run.to_dict())

    @bp.route("/runs/<rid>/cancel", methods=["POST"])
    def cancel_run(rid: str) -> Any:
        """Cancel a running pipeline."""
        try:
            run = mgr.cancel_run(rid)
        except KeyError:
            return jsonify({"error": "Run not found", "code": "RUN_NOT_FOUND"}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_STATE"}), 409
        return jsonify(run.to_dict())

    @bp.route("/runs/<rid>/artifacts", methods=["GET"])
    def get_run_artifacts(rid: str) -> Any:
        """Get artifacts for a run."""
        arts = mgr.get_run_artifacts(rid)
        return jsonify([a.to_dict() for a in arts])

    # -- Artifact endpoints ------------------------------------------------

    @bp.route("/artifacts", methods=["POST"])
    def register_artifact() -> Any:
        """Register a new build artifact."""
        body = request.get_json(silent=True) or {}
        try:
            art = mgr.register_artifact(
                run_id=body.get("run_id", ""),
                name=body.get("name", ""),
                artifact_type=body.get("artifact_type", ""),
                size_bytes=int(body.get("size_bytes", 0)),
                checksum_sha256=body.get("checksum_sha256", ""),
                storage_path=body.get("storage_path", ""),
                metadata=body.get("metadata"),
            )
        except KeyError as exc:
            return jsonify({"error": str(exc), "code": "RUN_NOT_FOUND"}), 404
        return jsonify(art.to_dict()), 201

    @bp.route("/artifacts/<aid>", methods=["GET"])
    def get_artifact(aid: str) -> Any:
        """Get artifact details."""
        art = mgr.get_artifact(aid)
        if art is None:
            return jsonify({"error": "Artifact not found", "code": "ARTIFACT_NOT_FOUND"}), 404
        return jsonify(art.to_dict())

    require_blueprint_auth(bp)
    return bp

# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Computer Vision Pipeline Manager — CVP-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Chain computer-vision models into sequential pipelines: detect → classify →
track → alert.  Each stage in a pipeline wraps a pluggable model backend
(local or cloud).  The manager handles pipeline lifecycle, frame routing,
result aggregation, and alerting.

Classes: StageKind/PipelineStatus/AlertSeverity/FrameFormat (enums),
ModelStage/PipelineConfig/FrameInput/DetectionResult/ClassificationResult/
TrackingResult/AlertResult/PipelineRunResult/PipelineStats (dataclasses),
ComputerVisionPipeline (thread-safe engine).
``create_cvp_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via
capped_append; no external dependencies beyond stdlib + Flask.  Actual CV
inference is pluggable — the engine ships with a built-in stub detector
so that all logic is testable without GPU or network access.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

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
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

try:
    from thread_safe_operations import capped_append, capped_append_paired
except ImportError:

    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)
try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)


# -- Enums ------------------------------------------------------------------


class StageKind(str, Enum):
    """Type of processing stage in a CV pipeline."""
    detect = "detect"
    classify = "classify"
    track = "track"
    alert = "alert"
    preprocess = "preprocess"
    postprocess = "postprocess"


class PipelineStatus(str, Enum):
    """Lifecycle status of a pipeline."""
    draft = "draft"
    active = "active"
    paused = "paused"
    archived = "archived"


class AlertSeverity(str, Enum):
    """Severity of a pipeline alert."""
    info = "info"
    warning = "warning"
    critical = "critical"


class FrameFormat(str, Enum):
    """Supported frame input formats."""
    raw_rgb = "raw_rgb"
    jpeg = "jpeg"
    png = "png"
    base64 = "base64"


# -- Data models ------------------------------------------------------------


@dataclass
class ModelStage:
    """One stage in a CV pipeline."""
    stage_id: str
    kind: str
    model_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    confidence_threshold: float = 0.5
    enabled: bool = True
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)


@dataclass
class PipelineConfig:
    """Definition of a full CV pipeline."""
    pipeline_id: str
    name: str
    stages: List[ModelStage] = field(default_factory=list)
    status: str = "draft"
    description: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        d = asdict(self)
        return d


@dataclass
class FrameInput:
    """A single frame submitted for processing."""
    frame_id: str
    data: str
    format: str = "base64"
    width: int = 0
    height: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dict."""
        return asdict(self)


@dataclass
class DetectionResult:
    """Result from a detection stage."""
    detection_id: str
    label: str
    confidence: float
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    stage_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise."""
        return asdict(self)


@dataclass
class ClassificationResult:
    """Result from a classification stage."""
    class_name: str
    confidence: float
    source_detection_id: str = ""
    stage_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise."""
        return asdict(self)


@dataclass
class TrackingResult:
    """Result from a tracking stage."""
    track_id: str
    label: str
    frame_count: int = 1
    last_bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    velocity: Tuple[float, float] = (0.0, 0.0)
    stage_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise."""
        return asdict(self)


@dataclass
class AlertResult:
    """Alert raised by a pipeline."""
    alert_id: str
    severity: str = "info"
    message: str = ""
    source_stage_id: str = ""
    pipeline_id: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise."""
        return asdict(self)


@dataclass
class PipelineRunResult:
    """Aggregated result of running a frame through a pipeline."""
    run_id: str
    pipeline_id: str
    frame_id: str
    detections: List[Dict[str, Any]] = field(default_factory=list)
    classifications: List[Dict[str, Any]] = field(default_factory=list)
    trackings: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    stages_executed: int = 0
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise."""
        return asdict(self)


@dataclass
class PipelineStats:
    """Aggregate statistics for the CVP engine."""
    total_pipelines: int = 0
    active_pipelines: int = 0
    total_runs: int = 0
    total_detections: int = 0
    total_alerts: int = 0
    avg_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise."""
        return asdict(self)


# -- Built-in stub detector -------------------------------------------------


def _builtin_detect(frame_data: str, config: Dict[str, Any]) -> List[DetectionResult]:
    """Keyword-based stub detector for testing without real CV models."""
    results: List[DetectionResult] = []
    text = str(frame_data).lower()
    patterns = {
        "person": 0.92, "car": 0.88, "dog": 0.85,
        "cat": 0.83, "fire": 0.95, "smoke": 0.90,
    }
    for label, conf in patterns.items():
        if label in text:
            det = DetectionResult(
                detection_id=uuid.uuid4().hex[:12],
                label=label,
                confidence=conf,
                bbox=(10.0, 20.0, 100.0, 150.0),
            )
            results.append(det)
    return results


def _builtin_classify(detections: List[DetectionResult],
                      config: Dict[str, Any]) -> List[ClassificationResult]:
    """Stub classifier: refines detection labels."""
    results: List[ClassificationResult] = []
    mapping = {
        "person": "pedestrian", "car": "vehicle", "dog": "animal",
        "cat": "animal", "fire": "hazard", "smoke": "hazard",
    }
    for det in detections:
        class_name = mapping.get(det.label, det.label)
        results.append(ClassificationResult(
            class_name=class_name,
            confidence=det.confidence * 0.95,
            source_detection_id=det.detection_id,
        ))
    return results


def _builtin_track(detections: List[DetectionResult],
                   config: Dict[str, Any]) -> List[TrackingResult]:
    """Stub tracker: assigns stable IDs to detections."""
    results: List[TrackingResult] = []
    for det in detections:
        tid = hashlib.sha256(det.label.encode()).hexdigest()[:8]
        results.append(TrackingResult(
            track_id=f"trk-{tid}",
            label=det.label,
            frame_count=1,
            last_bbox=det.bbox,
        ))
    return results


def _builtin_alert(detections: List[DetectionResult],
                   classifications: List[ClassificationResult],
                   config: Dict[str, Any]) -> List[AlertResult]:
    """Stub alerter: raise alerts for hazard detections above threshold."""
    results: List[AlertResult] = []
    threshold = config.get("alert_threshold", 0.85)
    hazard_classes = config.get("hazard_labels", ["fire", "smoke", "hazard"])
    for cls in classifications:
        if cls.class_name in hazard_classes and cls.confidence >= threshold:
            results.append(AlertResult(
                alert_id=uuid.uuid4().hex[:12],
                severity="critical" if cls.confidence >= 0.9 else "warning",
                message=f"Hazard detected: {cls.class_name} "
                        f"(confidence={cls.confidence:.2f})",
                source_stage_id=cls.stage_id,
            ))
    return results


# -- Engine -----------------------------------------------------------------


class ComputerVisionPipeline:
    """Thread-safe CV pipeline manager.

    Create pipelines with ordered stages (detect → classify → track → alert),
    submit frames for processing, collect results, and manage alerts.
    """

    def __init__(self, max_history: int = 10_000) -> None:
        """Initialise the CVP engine."""
        self._lock = threading.Lock()
        self._pipelines: Dict[str, PipelineConfig] = {}
        self._run_history: List[PipelineRunResult] = []
        self._alerts: List[AlertResult] = []
        self._max_history = max_history
        self._total_runs = 0
        self._total_detections = 0
        self._total_duration_ms = 0.0

    # -- Pipeline CRUD ------------------------------------------------------

    def create_pipeline(self, name: str, description: str = "",
                        stages: Optional[List[Dict[str, Any]]] = None) -> PipelineConfig:
        """Create a new CV pipeline with optional stages."""
        pid = uuid.uuid4().hex[:12]
        stage_objs = self._build_stages(stages or [])
        cfg = PipelineConfig(
            pipeline_id=pid, name=name, description=description,
            stages=stage_objs, status="draft",
        )
        with self._lock:
            self._pipelines[pid] = cfg
        logger.info("Pipeline created: %s (%s)", pid, name)
        return cfg

    def _build_stages(self, raw: List[Dict[str, Any]]) -> List[ModelStage]:
        """Parse raw stage dicts into ModelStage objects."""
        result: List[ModelStage] = []
        for s in raw:
            result.append(ModelStage(
                stage_id=s.get("stage_id", uuid.uuid4().hex[:8]),
                kind=_enum_val(s.get("kind", "detect")),
                model_name=s.get("model_name", "builtin"),
                config=s.get("config", {}),
                confidence_threshold=float(s.get("confidence_threshold", 0.5)),
                enabled=s.get("enabled", True),
            ))
        return result

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineConfig]:
        """Return a pipeline by ID or None."""
        with self._lock:
            return self._pipelines.get(pipeline_id)

    def list_pipelines(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all pipelines, optionally filtered by status."""
        with self._lock:
            pipes = list(self._pipelines.values())
        if status:
            sv = _enum_val(status)
            pipes = [p for p in pipes if p.status == sv]
        return [p.to_dict() for p in pipes]

    def update_pipeline_status(self, pipeline_id: str,
                               status: Union[str, PipelineStatus]) -> Optional[PipelineConfig]:
        """Update a pipeline's status."""
        sv = _enum_val(status)
        if sv not in {e.value for e in PipelineStatus}:
            return None
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                return None
            p.status = sv
            p.updated_at = _now()
        return p

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline. Returns True if it existed."""
        with self._lock:
            return self._pipelines.pop(pipeline_id, None) is not None

    def add_stage(self, pipeline_id: str, kind: Union[str, StageKind],
                  model_name: str = "builtin",
                  config: Optional[Dict[str, Any]] = None,
                  confidence_threshold: float = 0.5) -> Optional[ModelStage]:
        """Append a stage to an existing pipeline."""
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                return None
            stage = ModelStage(
                stage_id=uuid.uuid4().hex[:8],
                kind=_enum_val(kind),
                model_name=model_name,
                config=config or {},
                confidence_threshold=confidence_threshold,
            )
            p.stages.append(stage)
            p.updated_at = _now()
        return stage

    def remove_stage(self, pipeline_id: str, stage_id: str) -> bool:
        """Remove a stage from a pipeline by stage_id."""
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                return False
            before = len(p.stages)
            p.stages = [s for s in p.stages if s.stage_id != stage_id]
            if len(p.stages) < before:
                p.updated_at = _now()
                return True
        return False

    # -- Frame processing ---------------------------------------------------

    def process_frame(self, pipeline_id: str, frame_data: str,
                      frame_format: Union[str, FrameFormat] = "base64",
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[PipelineRunResult]:
        """Run a frame through all enabled stages of a pipeline."""
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p or p.status != "active":
                return None
            stages = [s for s in p.stages if s.enabled]

        frame = FrameInput(
            frame_id=uuid.uuid4().hex[:12], data=frame_data,
            format=_enum_val(frame_format), metadata=metadata or {},
        )
        return self._execute_pipeline(p, stages, frame)

    def _execute_pipeline(self, pipeline: PipelineConfig,
                          stages: List[ModelStage],
                          frame: FrameInput) -> PipelineRunResult:
        """Execute all stages and aggregate results."""
        import time
        t0 = time.monotonic()
        run_id = uuid.uuid4().hex[:12]
        detections: List[DetectionResult] = []
        classifications: List[ClassificationResult] = []
        trackings: List[TrackingResult] = []
        alerts: List[AlertResult] = []
        executed = 0

        for stage in stages:
            executed += 1
            kind = stage.kind
            if kind == "detect":
                dets = self._run_detect(stage, frame)
                detections.extend(dets)
            elif kind == "classify":
                cls = self._run_classify(stage, detections)
                classifications.extend(cls)
            elif kind == "track":
                trk = self._run_track(stage, detections)
                trackings.extend(trk)
            elif kind == "alert":
                alt = self._run_alert(stage, detections, classifications)
                alerts.extend(alt)

        elapsed = (time.monotonic() - t0) * 1000.0
        result = PipelineRunResult(
            run_id=run_id, pipeline_id=pipeline.pipeline_id,
            frame_id=frame.frame_id,
            detections=[d.to_dict() for d in detections],
            classifications=[c.to_dict() for c in classifications],
            trackings=[t.to_dict() for t in trackings],
            alerts=[a.to_dict() for a in alerts],
            stages_executed=executed, duration_ms=round(elapsed, 2),
        )
        self._record_run(result, alerts)
        return result

    def _run_detect(self, stage: ModelStage,
                    frame: FrameInput) -> List[DetectionResult]:
        """Run a detect stage."""
        dets = _builtin_detect(frame.data, stage.config)
        filtered = [d for d in dets
                     if d.confidence >= stage.confidence_threshold]
        for d in filtered:
            d.stage_id = stage.stage_id
        return filtered

    def _run_classify(self, stage: ModelStage,
                      detections: List[DetectionResult]) -> List[ClassificationResult]:
        """Run a classify stage."""
        cls = _builtin_classify(detections, stage.config)
        for c in cls:
            c.stage_id = stage.stage_id
        return cls

    def _run_track(self, stage: ModelStage,
                   detections: List[DetectionResult]) -> List[TrackingResult]:
        """Run a track stage."""
        trk = _builtin_track(detections, stage.config)
        for t in trk:
            t.stage_id = stage.stage_id
        return trk

    def _run_alert(self, stage: ModelStage,
                   detections: List[DetectionResult],
                   classifications: List[ClassificationResult]) -> List[AlertResult]:
        """Run an alert stage."""
        return _builtin_alert(detections, classifications, stage.config)

    def _record_run(self, result: PipelineRunResult,
                    alerts: List[AlertResult]) -> None:
        """Thread-safely record run results and alerts."""
        with self._lock:
            if not alerts:
                capped_append(self._run_history, result, self._max_history)
            else:
                capped_append_paired(
                    self._run_history, result,
                    self._alerts, alerts[0],
                    max_size=self._max_history,
                )
                for a in alerts[1:]:
                    capped_append(self._alerts, a, self._max_history)
            self._total_runs += 1
            self._total_detections += len(result.detections)
            self._total_duration_ms += result.duration_ms

    # -- Query --------------------------------------------------------------

    def get_run_history(self, pipeline_id: Optional[str] = None,
                       limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent pipeline run results."""
        with self._lock:
            runs = list(self._run_history)
        if pipeline_id:
            runs = [r for r in runs if r.pipeline_id == pipeline_id]
        return [r.to_dict() for r in runs[-limit:]]

    def get_alerts(self, severity: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent alerts, optionally filtered by severity."""
        with self._lock:
            alerts = list(self._alerts)
        if severity:
            sv = _enum_val(severity)
            alerts = [a for a in alerts if a.severity == sv]
        return [a.to_dict() for a in alerts[-limit:]]

    def clear_alerts(self) -> int:
        """Clear all stored alerts. Returns count cleared."""
        with self._lock:
            n = len(self._alerts)
            self._alerts.clear()
        return n

    def get_stats(self) -> PipelineStats:
        """Return aggregate CVP statistics."""
        with self._lock:
            total = len(self._pipelines)
            active = sum(1 for p in self._pipelines.values()
                         if p.status == "active")
            avg = (self._total_duration_ms / self._total_runs
                   if self._total_runs else 0.0)
        return PipelineStats(
            total_pipelines=total, active_pipelines=active,
            total_runs=self._total_runs,
            total_detections=self._total_detections,
            total_alerts=len(self._alerts),
            avg_duration_ms=round(avg, 2),
        )


# -- Wingman Protocol -------------------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """CVP-001 Wingman gate."""
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {"passed": False,
                "message": f"Length mismatch: storyline={len(storyline)} "
                           f"actuals={len(actuals)}"}
    mismatches: List[int] = []
    for i, (s, a) in enumerate(zip(storyline, actuals)):
        if s != a:
            mismatches.append(i)
    if mismatches:
        return {"passed": False,
                "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}


# -- Causality Sandbox gating -----------------------------------------------

def gate_cvp_in_sandbox(context: dict) -> dict:
    """CVP-001 Causality Sandbox gate."""
    required_keys = {"pipeline_id", "frame_data"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("pipeline_id"):
        return {"passed": False, "message": "pipeline_id must be non-empty"}
    if not context.get("frame_data"):
        return {"passed": False, "message": "frame_data must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "frame_data_len": len(str(context["frame_data"]))}


# -- Flask helpers ----------------------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}


def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"Missing required field: {k}",
                            "code": "MISSING_FIELD"}), 400
    return None


def _not_found(msg: str) -> Any:
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404


# -- Blueprint factory ------------------------------------------------------

def create_cvp_api(engine: ComputerVisionPipeline) -> Any:
    """Create a Flask Blueprint with CVP REST endpoints."""
    bp = Blueprint("cvp", __name__, url_prefix="/api")
    _register_pipeline_routes(bp, engine)
    _register_stage_routes(bp, engine)
    _register_process_routes(bp, engine)
    _register_query_routes(bp, engine)
    _register_stats_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp


def _register_pipeline_routes(bp: Any, eng: ComputerVisionPipeline) -> None:
    """Register pipeline CRUD endpoints."""

    @bp.route("/cvp/pipelines", methods=["POST"])
    def create_pipeline() -> Any:
        body = _api_body()
        err = _api_need(body, "name")
        if err:
            return err
        p = eng.create_pipeline(
            name=body["name"],
            description=body.get("description", ""),
            stages=body.get("stages", []),
        )
        return jsonify(p.to_dict()), 201

    @bp.route("/cvp/pipelines", methods=["GET"])
    def list_pipelines() -> Any:
        status = request.args.get("status")
        return jsonify(eng.list_pipelines(status=status)), 200

    @bp.route("/cvp/pipelines/<pipeline_id>", methods=["GET"])
    def get_pipeline(pipeline_id: str) -> Any:
        p = eng.get_pipeline(pipeline_id)
        if not p:
            return _not_found("Pipeline not found")
        return jsonify(p.to_dict()), 200

    @bp.route("/cvp/pipelines/<pipeline_id>/status", methods=["PUT"])
    def update_status(pipeline_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        p = eng.update_pipeline_status(pipeline_id, body["status"])
        if not p:
            return _not_found("Pipeline not found or invalid status")
        return jsonify(p.to_dict()), 200

    @bp.route("/cvp/pipelines/<pipeline_id>", methods=["DELETE"])
    def delete_pipeline(pipeline_id: str) -> Any:
        if eng.delete_pipeline(pipeline_id):
            return jsonify({"deleted": pipeline_id}), 200
        return _not_found("Pipeline not found")


def _register_stage_routes(bp: Any, eng: ComputerVisionPipeline) -> None:
    """Register stage management endpoints."""

    @bp.route("/cvp/pipelines/<pid>/stages", methods=["POST"])
    def add_stage(pid: str) -> Any:
        body = _api_body()
        err = _api_need(body, "kind")
        if err:
            return err
        s = eng.add_stage(
            pipeline_id=pid,
            kind=body["kind"],
            model_name=body.get("model_name", "builtin"),
            config=body.get("config", {}),
            confidence_threshold=float(body.get("confidence_threshold", 0.5)),
        )
        if not s:
            return _not_found("Pipeline not found")
        return jsonify(s.to_dict()), 201

    @bp.route("/cvp/pipelines/<pid>/stages/<sid>", methods=["DELETE"])
    def remove_stage(pid: str, sid: str) -> Any:
        if eng.remove_stage(pid, sid):
            return jsonify({"removed": sid}), 200
        return _not_found("Pipeline or stage not found")


def _register_process_routes(bp: Any, eng: ComputerVisionPipeline) -> None:
    """Register frame processing endpoints."""

    @bp.route("/cvp/process", methods=["POST"])
    def process_frame() -> Any:
        body = _api_body()
        err = _api_need(body, "pipeline_id", "frame_data")
        if err:
            return err
        result = eng.process_frame(
            pipeline_id=body["pipeline_id"],
            frame_data=body["frame_data"],
            frame_format=body.get("frame_format", "base64"),
            metadata=body.get("metadata", {}),
        )
        if not result:
            return _not_found("Pipeline not found or not active")
        return jsonify(result.to_dict()), 200


def _register_query_routes(bp: Any, eng: ComputerVisionPipeline) -> None:
    """Register history and alert query endpoints."""

    @bp.route("/cvp/history", methods=["GET"])
    def get_history() -> Any:
        pid = request.args.get("pipeline_id")
        limit = int(request.args.get("limit", 50))
        return jsonify(eng.get_run_history(pipeline_id=pid, limit=limit)), 200

    @bp.route("/cvp/alerts", methods=["GET"])
    def get_alerts() -> Any:
        sev = request.args.get("severity")
        limit = int(request.args.get("limit", 100))
        return jsonify(eng.get_alerts(severity=sev, limit=limit)), 200

    @bp.route("/cvp/alerts", methods=["DELETE"])
    def clear_alerts() -> Any:
        n = eng.clear_alerts()
        return jsonify({"cleared": n}), 200


def _register_stats_routes(bp: Any, eng: ComputerVisionPipeline) -> None:
    """Register stats and health endpoints."""

    @bp.route("/cvp/stats", methods=["GET"])
    def stats() -> Any:
        return jsonify(eng.get_stats().to_dict()), 200

    @bp.route("/cvp/health", methods=["GET"])
    def health() -> Any:
        st = eng.get_stats()
        return jsonify({
            "status": "healthy",
            "module": "CVP-001",
            "pipelines": st.total_pipelines,
            "active_pipelines": st.active_pipelines,
        }), 200

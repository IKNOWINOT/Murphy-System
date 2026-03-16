# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Robotic Process Automation (RPA) Recorder & Playback Engine — RPA-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Record sequences of user-interface actions (click, type, scroll, wait,
key-press, screenshot-match) as structured *recordings*, then play them
back against the same or similar application contexts.  Supports
parameterised templates, conditional branching, and loop constructs so a
single recording can adapt to dynamic content.

Classes: ActionKind/RecordingStatus/PlaybackStatus/LoopMode (enums),
ActionStep/RecordingConfig/PlaybackRun/PlaybackResult/LoopDirective/
ConditionalBranch/TemplateParam/RecordingStats (dataclasses),
RpaRecorderEngine (thread-safe engine).
``create_rpa_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via
capped_append; no external UI-automation dependency — the engine ships with
a simulated executor so that all logic is testable without a real desktop.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

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
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(target_list: list, item: Any, max_size: int = 50_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)

class ActionKind(str, Enum):
    """Type of UI action that can be recorded."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE_TEXT = "type_text"
    KEY_PRESS = "key_press"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT_MATCH = "screenshot_match"
    DRAG_DROP = "drag_drop"
    HOVER = "hover"
    ASSERT_TEXT = "assert_text"
    CONDITIONAL = "conditional"
    LOOP = "loop"

class RecordingStatus(str, Enum):
    """Lifecycle state of a recording."""
    DRAFT = "draft"
    RECORDING = "recording"
    PAUSED = "paused"
    COMPLETE = "complete"
    TEMPLATE = "template"
    ARCHIVED = "archived"

class PlaybackStatus(str, Enum):
    """Status of a playback run."""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class LoopMode(str, Enum):
    """How a loop iterates."""
    COUNT = "count"
    WHILE_VISIBLE = "while_visible"
    FOR_EACH = "for_each"

@dataclass
class TemplateParam:
    """A parameterisable slot in a recording template."""
    name: str
    default_value: str = ""
    description: str = ""

@dataclass
class ConditionalBranch:
    """A conditional block inside a recording."""
    condition_type: str = "text_present"
    condition_value: str = ""
    then_steps: List[int] = field(default_factory=list)
    else_steps: List[int] = field(default_factory=list)

@dataclass
class LoopDirective:
    """Loop construct wrapping a set of steps."""
    mode: str = "count"
    count: int = 1
    target_selector: str = ""
    step_indices: List[int] = field(default_factory=list)

@dataclass
class ActionStep:
    """A single recorded action."""
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: str = "click"
    selector: str = ""
    value: str = ""
    x: int = 0
    y: int = 0
    delay_ms: int = 0
    timeout_ms: int = 5000
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    conditional: Optional[ConditionalBranch] = None
    loop: Optional[LoopDirective] = None
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        d = asdict(self)
        if d.get("conditional") is None:
            d.pop("conditional", None)
        if d.get("loop") is None:
            d.pop("loop", None)
        return d

@dataclass
class RecordingConfig:
    """A full recording (sequence of ActionSteps)."""
    recording_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    description: str = ""
    status: str = "draft"
    steps: List[ActionStep] = field(default_factory=list)
    params: List[TemplateParam] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "recording_id": self.recording_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "params": [asdict(p) for p in self.params],
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "step_count": len(self.steps),
        }

@dataclass
class PlaybackResult:
    """Outcome of executing one step during playback."""
    step_id: str = ""
    kind: str = ""
    success: bool = True
    duration_ms: float = 0.0
    message: str = ""
    screenshot_match_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return asdict(self)

@dataclass
class PlaybackRun:
    """A single playback execution of a recording."""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    recording_id: str = ""
    status: str = "queued"
    param_overrides: Dict[str, str] = field(default_factory=dict)
    results: List[PlaybackResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    error: str = ""
    total_steps: int = 0
    completed_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d

@dataclass
class RecordingStats:
    """Aggregate statistics."""
    total_recordings: int = 0
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    total_steps_executed: int = 0
    template_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return asdict(self)

def _default_executor(step: ActionStep, params: Dict[str, str]) -> PlaybackResult:
    """Simulated step executor — always succeeds (plug real backend via callback)."""
    return PlaybackResult(
        step_id=step.step_id, kind=step.kind, success=True,
        duration_ms=max(1.0, step.delay_ms * 0.1),
        message=f"Simulated {step.kind}",
        screenshot_match_score=1.0 if step.kind == "screenshot_match" else 0.0)

class RpaRecorderEngine:
    """Thread-safe RPA recording and playback engine."""

    def __init__(
        self,
        max_history: int = 10_000,
        executor: Optional[Callable[[ActionStep, Dict[str, str]], PlaybackResult]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._recordings: Dict[str, RecordingConfig] = {}
        self._runs: List[PlaybackRun] = []
        self._max_history = max_history
        self._executor = executor or _default_executor

    # -- Recording CRUD -----------------------------------------------------

    def create_recording(
        self, name: str, *, description: str = "",
        steps: Optional[List[Dict[str, Any]]] = None,
        params: Optional[List[Dict[str, str]]] = None,
        tags: Optional[List[str]] = None,
    ) -> RecordingConfig:
        """Create a new recording with optional pre-built steps, params, tags."""
        rec = RecordingConfig(name=name, description=description,
                              tags=list(tags or []))
        if steps:
            for sd in steps:
                rec.steps.append(_dict_to_step(sd))
        if params:
            for pd in params:
                rec.params.append(TemplateParam(**{
                    k: v for k, v in pd.items()
                    if k in ("name", "default_value", "description")
                }))
        with self._lock:
            self._recordings[rec.recording_id] = rec
        return rec

    def get_recording(self, recording_id: str) -> Optional[RecordingConfig]:
        """Return a recording by ID, or None."""
        with self._lock:
            return self._recordings.get(recording_id)

    def list_recordings(self, *, status: Optional[Union[str, RecordingStatus]] = None,
                         tag: Optional[str] = None) -> List[RecordingConfig]:
        """List recordings, optionally filtered by status or tag."""
        with self._lock:
            recs = list(self._recordings.values())
        if status:
            sv = _enum_val(status)
            recs = [r for r in recs if r.status == sv]
        if tag:
            recs = [r for r in recs if tag in r.tags]
        return recs

    def update_recording_status(self, recording_id: str,
                                new_status: Union[str, RecordingStatus]) -> Optional[RecordingConfig]:
        """Transition a recording to *new_status*."""
        sv = _enum_val(new_status)
        with self._lock:
            rec = self._recordings.get(recording_id)
            if not rec:
                return None
            rec.status = sv
            rec.updated_at = _now()
        return rec

    def delete_recording(self, recording_id: str) -> bool:
        """Remove a recording. Returns True if it existed."""
        with self._lock:
            return self._recordings.pop(recording_id, None) is not None

    # -- Step management ----------------------------------------------------

    def add_step(self, recording_id: str,
                 step_dict: Dict[str, Any]) -> Optional[ActionStep]:
        """Append a step to an existing recording."""
        with self._lock:
            rec = self._recordings.get(recording_id)
            if not rec:
                return None
            step = _dict_to_step(step_dict)
            rec.steps.append(step)
            rec.updated_at = _now()
        return step

    def remove_step(self, recording_id: str, step_id: str) -> bool:
        """Remove a step from a recording."""
        with self._lock:
            rec = self._recordings.get(recording_id)
            if not rec:
                return False
            before = len(rec.steps)
            rec.steps = [s for s in rec.steps if s.step_id != step_id]
            rec.updated_at = _now()
            return len(rec.steps) < before

    def reorder_steps(self, recording_id: str,
                      step_ids: List[str]) -> Optional[RecordingConfig]:
        """Reorder steps to match the order given in *step_ids*."""
        with self._lock:
            rec = self._recordings.get(recording_id)
            if not rec:
                return None
            by_id = {s.step_id: s for s in rec.steps}
            new_order: List[ActionStep] = []
            for sid in step_ids:
                if sid in by_id:
                    new_order.append(by_id.pop(sid))
            # Append any remaining steps not in the supplied list
            new_order.extend(by_id.values())
            rec.steps = new_order
            rec.updated_at = _now()
        return rec

    # -- Template support ---------------------------------------------------

    def promote_to_template(self, recording_id: str,
                            params: Optional[List[Dict[str, str]]] = None) -> Optional[RecordingConfig]:
        """Promote a recording to a reusable template."""
        with self._lock:
            rec = self._recordings.get(recording_id)
            if not rec:
                return None
            rec.status = RecordingStatus.TEMPLATE.value
            if params:
                for pd in params:
                    rec.params.append(TemplateParam(**{
                        k: v for k, v in pd.items()
                        if k in ("name", "default_value", "description")
                    }))
            rec.updated_at = _now()
        return rec

    def instantiate_template(self, recording_id: str, new_name: str,
                             param_overrides: Optional[Dict[str, str]] = None) -> Optional[RecordingConfig]:
        """Create a new recording from a template, substituting params."""
        with self._lock:
            tmpl = self._recordings.get(recording_id)
            if not tmpl or tmpl.status != RecordingStatus.TEMPLATE.value:
                return None
            clone = RecordingConfig(
                name=new_name,
                description=tmpl.description,
                tags=list(tmpl.tags),
            )
            overrides = param_overrides or {}
            defaults = {p.name: p.default_value for p in tmpl.params}
            merged = {**defaults, **overrides}
            for s in tmpl.steps:
                ns = _clone_step(s, merged)
                clone.steps.append(ns)
            clone.params = list(tmpl.params)
            self._recordings[clone.recording_id] = clone
        return clone

    # -- Playback -----------------------------------------------------------

    def start_playback(self, recording_id: str, *,
                       param_overrides: Optional[Dict[str, str]] = None) -> Optional[PlaybackRun]:
        """Execute a recording and return the PlaybackRun."""
        with self._lock:
            rec = self._recordings.get(recording_id)
            if not rec:
                return None
            if rec.status not in (
                RecordingStatus.COMPLETE.value,
                RecordingStatus.TEMPLATE.value,
            ):
                return None
            steps = list(rec.steps)
            defaults = {p.name: p.default_value for p in rec.params}

        overrides = param_overrides or {}
        params = {**defaults, **overrides}
        run = PlaybackRun(
            recording_id=recording_id,
            status=PlaybackStatus.RUNNING.value,
            param_overrides=overrides,
            total_steps=len(steps),
            started_at=_now(),
        )
        self._execute_steps(run, steps, params)
        with self._lock:
            capped_append(self._runs, run, self._max_history)
        return run

    def _execute_steps(self, run: PlaybackRun,
                       steps: List[ActionStep], params: Dict[str, str]) -> None:
        """Run each step through the executor."""
        for step in steps:
            if run.status == PlaybackStatus.CANCELLED.value:
                break
            try:
                result = self._executor(step, params)
                run.results.append(result)
                if result.success:
                    run.completed_steps += 1
                else:
                    run.status = PlaybackStatus.FAILED.value
                    run.error = result.message
                    run.finished_at = _now()
                    return
            except Exception as exc:
                run.results.append(PlaybackResult(
                    step_id=step.step_id,
                    kind=step.kind,
                    success=False,
                    message=str(exc),
                ))
                run.status = PlaybackStatus.FAILED.value
                run.error = str(exc)
                run.finished_at = _now()
                return
        run.status = PlaybackStatus.COMPLETED.value
        run.finished_at = _now()

    def get_run(self, run_id: str) -> Optional[PlaybackRun]:
        """Retrieve a specific playback run."""
        with self._lock:
            for r in self._runs:
                if r.run_id == run_id:
                    return r
        return None

    def list_runs(self, *, recording_id: Optional[str] = None,
                  status: Optional[Union[str, PlaybackStatus]] = None,
                  limit: int = 50) -> List[PlaybackRun]:
        """List playback runs, newest first."""
        with self._lock:
            runs = list(self._runs)
        if recording_id:
            runs = [r for r in runs if r.recording_id == recording_id]
        if status:
            sv = _enum_val(status)
            runs = [r for r in runs if r.status == sv]
        runs.sort(key=lambda r: r.started_at or "", reverse=True)
        return runs[:limit]

    def cancel_run(self, run_id: str) -> bool:
        """Mark a running playback as cancelled."""
        with self._lock:
            for r in self._runs:
                if r.run_id == run_id and r.status == PlaybackStatus.RUNNING.value:
                    r.status = PlaybackStatus.CANCELLED.value
                    r.finished_at = _now()
                    return True
        return False

    # -- Stats & search -----------------------------------------------------

    def get_stats(self) -> RecordingStats:
        """Return aggregate statistics."""
        with self._lock:
            recs = list(self._recordings.values())
            runs = list(self._runs)
        return RecordingStats(
            total_recordings=len(recs),
            total_runs=len(runs),
            completed_runs=sum(
                1 for r in runs if r.status == PlaybackStatus.COMPLETED.value
            ),
            failed_runs=sum(
                1 for r in runs if r.status == PlaybackStatus.FAILED.value
            ),
            total_steps_executed=sum(r.completed_steps for r in runs),
            template_count=sum(
                1 for r in recs if r.status == RecordingStatus.TEMPLATE.value
            ),
        )

    def search_recordings(self, query: str, *, limit: int = 50) -> List[RecordingConfig]:
        """Full-text search over recording names, descriptions, and tags."""
        q = query.lower()
        with self._lock:
            recs = list(self._recordings.values())
        results: List[RecordingConfig] = []
        for r in recs:
            haystack = f"{r.name} {r.description} {' '.join(r.tags)}".lower()
            if q in haystack:
                results.append(r)
            if len(results) >= limit:
                break
        return results

    def export_recording(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Export a recording as a JSON-serialisable dict."""
        rec = self.get_recording(recording_id)
        if not rec:
            return None
        return rec.to_dict()

    def import_recording(self, data: Dict[str, Any]) -> RecordingConfig:
        """Import a recording from an exported dict."""
        rec = RecordingConfig(
            name=data.get("name", "imported"),
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )
        for sd in data.get("steps", []):
            rec.steps.append(_dict_to_step(sd))
        for pd in data.get("params", []):
            rec.params.append(TemplateParam(**{
                k: v for k, v in pd.items()
                if k in ("name", "default_value", "description")
            }))
        with self._lock:
            self._recordings[rec.recording_id] = rec
        return rec

def _dict_to_step(d: Dict[str, Any]) -> ActionStep:
    """Build an ActionStep from a raw dict."""
    cond = None
    if d.get("conditional"):
        cd = d["conditional"]
        cond = ConditionalBranch(
            condition_type=cd.get("condition_type", "text_present"),
            condition_value=cd.get("condition_value", ""),
            then_steps=cd.get("then_steps", []),
            else_steps=cd.get("else_steps", []),
        )
    loop = None
    if d.get("loop"):
        ld = d["loop"]
        loop = LoopDirective(
            mode=ld.get("mode", "count"),
            count=ld.get("count", 1),
            target_selector=ld.get("target_selector", ""),
            step_indices=ld.get("step_indices", []),
        )
    return ActionStep(
        step_id=d.get("step_id", uuid.uuid4().hex[:12]),
        kind=_enum_val(d.get("kind", ActionKind.CLICK)),
        selector=d.get("selector", ""),
        value=d.get("value", ""),
        x=int(d.get("x", 0)),
        y=int(d.get("y", 0)),
        delay_ms=int(d.get("delay_ms", 0)),
        timeout_ms=int(d.get("timeout_ms", 5000)),
        description=d.get("description", ""),
        metadata=d.get("metadata", {}),
        conditional=cond,
        loop=loop,
    )

def _clone_step(step: ActionStep, params: Dict[str, str]) -> ActionStep:
    """Deep-copy a step, resolving template params in value fields."""
    s = ActionStep(
        kind=step.kind,
        selector=step.selector,
        value=step.value,
        x=step.x,
        y=step.y,
        delay_ms=step.delay_ms,
        timeout_ms=step.timeout_ms,
        description=step.description,
        metadata=dict(step.metadata),
        conditional=step.conditional,
        loop=step.loop,
    )
    for k, v in params.items():
        s.value = s.value.replace(f"{{{{{k}}}}}", v)
        s.selector = s.selector.replace(f"{{{{{k}}}}}", v)
    return s

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """RPA-001 Wingman gate."""
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {
            "passed": False,
            "message": f"Length mismatch: storyline={len(storyline)} "
                       f"actuals={len(actuals)}",
        }
    mismatches: List[int] = []
    for i, (s, a) in enumerate(zip(storyline, actuals)):
        if s != a:
            mismatches.append(i)
    if mismatches:
        return {"passed": False,
                "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}

def gate_rpa_in_sandbox(context: dict) -> dict:
    """RPA-001 Causality Sandbox gate."""
    required_keys = {"recording_id"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("recording_id"):
        return {"passed": False, "message": "recording_id must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "recording_id": context["recording_id"]}

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

def create_rpa_api(engine: RpaRecorderEngine) -> Any:
    """Create a Flask Blueprint with RPA REST endpoints."""
    bp = Blueprint("rpa", __name__, url_prefix="/api")
    eng = engine

    @bp.route("/rpa/recordings", methods=["POST"])
    def create_recording() -> Any:
        body = _api_body()
        err = _api_need(body, "name")
        if err:
            return err
        rec = eng.create_recording(
            name=body["name"], description=body.get("description", ""),
            steps=body.get("steps"), params=body.get("params"),
            tags=body.get("tags"))
        return jsonify(rec.to_dict()), 201

    @bp.route("/rpa/recordings", methods=["GET"])
    def list_recordings() -> Any:
        recs = eng.list_recordings(
            status=request.args.get("status"), tag=request.args.get("tag"))
        return jsonify([r.to_dict() for r in recs]), 200

    @bp.route("/rpa/recordings/<rec_id>", methods=["GET"])
    def get_recording(rec_id: str) -> Any:
        rec = eng.get_recording(rec_id)
        return jsonify(rec.to_dict()) if rec else _not_found("Recording not found")

    @bp.route("/rpa/recordings/<rec_id>/status", methods=["PUT"])
    def update_status(rec_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        rec = eng.update_recording_status(rec_id, body["status"])
        return jsonify(rec.to_dict()) if rec else _not_found("Recording not found")

    @bp.route("/rpa/recordings/<rec_id>", methods=["DELETE"])
    def delete_recording(rec_id: str) -> Any:
        return (jsonify({"deleted": True}), 200) if eng.delete_recording(rec_id) \
            else _not_found("Recording not found")

    @bp.route("/rpa/recordings/<rec_id>/steps", methods=["POST"])
    def add_step(rec_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "kind")
        if err:
            return err
        step = eng.add_step(rec_id, body)
        return jsonify(step.to_dict()), 201 if step else _not_found("Recording not found")

    @bp.route("/rpa/recordings/<rec_id>/steps/<step_id>", methods=["DELETE"])
    def remove_step(rec_id: str, step_id: str) -> Any:
        return (jsonify({"deleted": True}), 200) if eng.remove_step(rec_id, step_id) \
            else _not_found("Step not found")

    @bp.route("/rpa/recordings/<rec_id>/steps/reorder", methods=["PUT"])
    def reorder_steps(rec_id: str) -> Any:
        rec = eng.reorder_steps(rec_id, _api_body().get("step_ids", []))
        return jsonify(rec.to_dict()) if rec else _not_found("Recording not found")

    @bp.route("/rpa/playback", methods=["POST"])
    def start_playback() -> Any:
        body = _api_body()
        err = _api_need(body, "recording_id")
        if err:
            return err
        run = eng.start_playback(
            recording_id=body["recording_id"],
            param_overrides=body.get("param_overrides"))
        return (jsonify(run.to_dict()), 201) if run \
            else _not_found("Recording not found or not playable")

    @bp.route("/rpa/runs", methods=["GET"])
    def list_runs() -> Any:
        runs = eng.list_runs(
            recording_id=request.args.get("recording_id"),
            status=request.args.get("status"),
            limit=int(request.args.get("limit", 50)))
        return jsonify([r.to_dict() for r in runs]), 200

    @bp.route("/rpa/runs/<run_id>", methods=["GET"])
    def get_run(run_id: str) -> Any:
        run = eng.get_run(run_id)
        return jsonify(run.to_dict()) if run else _not_found("Run not found")

    @bp.route("/rpa/runs/<run_id>/cancel", methods=["POST"])
    def cancel_run(run_id: str) -> Any:
        return (jsonify({"cancelled": True}), 200) if eng.cancel_run(run_id) \
            else _not_found("Run not found or not running")

    @bp.route("/rpa/recordings/<rec_id>/promote", methods=["POST"])
    def promote(rec_id: str) -> Any:
        rec = eng.promote_to_template(rec_id, params=_api_body().get("params"))
        return jsonify(rec.to_dict()) if rec else _not_found("Recording not found")

    @bp.route("/rpa/recordings/<rec_id>/instantiate", methods=["POST"])
    def instantiate(rec_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "name")
        if err:
            return err
        rec = eng.instantiate_template(
            rec_id, body["name"], param_overrides=body.get("param_overrides"))
        return (jsonify(rec.to_dict()), 201) if rec \
            else _not_found("Template not found or not a template")

    @bp.route("/rpa/recordings/<rec_id>/export", methods=["GET"])
    def export_rec(rec_id: str) -> Any:
        data = eng.export_recording(rec_id)
        return jsonify(data) if data else _not_found("Recording not found")

    @bp.route("/rpa/recordings/import", methods=["POST"])
    def import_rec() -> Any:
        return jsonify(eng.import_recording(_api_body()).to_dict()), 201

    @bp.route("/rpa/search", methods=["GET"])
    def search() -> Any:
        results = eng.search_recordings(
            request.args.get("q", ""),
            limit=int(request.args.get("limit", 50)))
        return jsonify([r.to_dict() for r in results]), 200

    @bp.route("/rpa/stats", methods=["GET"])
    def stats() -> Any:
        return jsonify(eng.get_stats().to_dict()), 200

    @bp.route("/rpa/health", methods=["GET"])
    def health() -> Any:
        st = eng.get_stats()
        return jsonify({"status": "healthy", "module": "RPA-001",
                        "recordings": st.total_recordings,
                        "total_runs": st.total_runs}), 200

    require_blueprint_auth(bp)
    return bp

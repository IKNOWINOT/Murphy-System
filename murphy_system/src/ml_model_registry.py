# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Machine Learning Model Registry — MLR-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Register, version, deploy, and A/B-test ML models.  Track model lifecycle
from draft through production with full version history, deployment records,
and traffic-splitting experiments.  Thread-safe bounded storage ensures
safe concurrent access without unbounded memory growth.

Classes: ModelStatus/ModelFramework/DeploymentTarget/VersionStatus (enums),
ModelVersion/Model/DeploymentRecord/ABTestConfig (dataclasses),
MLModelRegistry (thread-safe engine).
``create_mlr_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via capped_append;
no external dependencies beyond stdlib + Flask.
"""
from __future__ import annotations

import logging
import random
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

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
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)


# -- Enums ------------------------------------------------------------------

class ModelStatus(str, Enum):
    """ModelStatus enumeration."""
    draft = "draft"; staging = "staging"; production = "production"
    archived = "archived"; deprecated = "deprecated"

class ModelFramework(str, Enum):
    """ModelFramework enumeration."""
    pytorch = "pytorch"; tensorflow = "tensorflow"; sklearn = "sklearn"
    onnx = "onnx"; custom = "custom"

class DeploymentTarget(str, Enum):
    """DeploymentTarget enumeration."""
    local = "local"; cloud = "cloud"; edge = "edge"; hybrid = "hybrid"

class VersionStatus(str, Enum):
    """VersionStatus enumeration."""
    active = "active"; inactive = "inactive"; rollback_target = "rollback_target"

# -- Dataclasses ------------------------------------------------------------

@dataclass
class ModelVersion:
    """A single versioned snapshot of an ML model."""
    version_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    model_id: str = ""
    version_number: str = "1.0.0"
    framework: ModelFramework = ModelFramework.custom
    artifact_path: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: VersionStatus = VersionStatus.inactive
    created_at: str = field(default_factory=_now)
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["framework"] = _enum_val(self.framework)
        d["status"] = _enum_val(self.status)
        return d


@dataclass
class Model:
    """Top-level model record."""
    model_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    owner: str = ""
    framework: ModelFramework = ModelFramework.custom
    status: ModelStatus = ModelStatus.draft
    versions: List[ModelVersion] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["framework"] = _enum_val(self.framework)
        d["status"] = _enum_val(self.status)
        d["versions"] = [v.to_dict() for v in self.versions]
        return d


@dataclass
class DeploymentRecord:
    """Tracks a model deployment to a target environment."""
    deployment_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    model_id: str = ""
    version_id: str = ""
    target: DeploymentTarget = DeploymentTarget.local
    status: str = "pending"
    deployed_at: str = field(default_factory=_now)
    configuration: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["target"] = _enum_val(self.target)
        return d


@dataclass
class ABTestConfig:
    """Configuration for an A/B traffic-split experiment."""
    test_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    model_id: str = ""
    version_a_id: str = ""
    version_b_id: str = ""
    traffic_split_a: float = 0.5
    status: str = "draft"
    created_at: str = field(default_factory=_now)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


# -- Bounded-append helper --------------------------------------------------

def _capped(lst: list, item: Any, cap: int = 500) -> None:
    """Local bounded append — delegates to imported capped_append."""
    capped_append(lst, item, cap)


# -- MLModelRegistry --------------------------------------------------------

class MLModelRegistry:
    """Thread-safe ML model registry with bounded storage."""

    def __init__(self, max_models: int = 10_000,
                 max_versions_per_model: int = 100) -> None:
        self._lock = threading.Lock()
        self._models: Dict[str, Model] = {}
        self._deployments: Dict[str, DeploymentRecord] = {}
        self._ab_tests: Dict[str, ABTestConfig] = {}
        self._max_models = max_models
        self._max_versions = max_versions_per_model
        self._model_order: List[str] = []
        self._deploy_order: List[str] = []
        self._test_order: List[str] = []

    # -- Model CRUD ---------------------------------------------------------

    def register_model(self, name: str, description: str, owner: str,
                       framework: Union[str, ModelFramework],
                       tags: Optional[List[str]] = None) -> Model:
        """Register a new model in the registry."""
        fw = ModelFramework(framework) if not isinstance(framework, ModelFramework) else framework
        with self._lock:
            if len(self._models) >= self._max_models:
                oldest = self._model_order[0]
                del self._models[oldest]
                self._model_order.pop(0)
            m = Model(name=name, description=description, owner=owner,
                      framework=fw, tags=tags or [])
            self._models[m.model_id] = m
            _capped(self._model_order, m.model_id, self._max_models)
            return m

    def get_model(self, model_id: str) -> Optional[Model]:
        """Return a model by ID, or None."""
        with self._lock:
            return self._models.get(model_id)

    def list_models(self, status: Optional[str] = None,
                    framework: Optional[str] = None,
                    owner: Optional[str] = None,
                    tag: Optional[str] = None) -> List[Model]:
        """List models with optional filters."""
        with self._lock:
            return list(self._filter_models(status, framework, owner, tag))

    def _filter_models(self, status: Optional[str], framework: Optional[str],
                       owner: Optional[str], tag: Optional[str]) -> List[Model]:
        out: List[Model] = []
        for m in self._models.values():
            if status and _enum_val(m.status) != status:
                continue
            if framework and _enum_val(m.framework) != framework:
                continue
            if owner and m.owner != owner:
                continue
            if tag and tag not in m.tags:
                continue
            out.append(m)
        return out

    def update_model(self, model_id: str, **fields: Any) -> Optional[Model]:
        """Update mutable fields on an existing model."""
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return None
            self._apply_model_fields(m, fields)
            m.updated_at = _now()
            return m

    @staticmethod
    def _apply_model_fields(m: Model, fields: Dict[str, Any]) -> None:
        for k in ("name", "description", "owner", "tags"):
            if k in fields:
                setattr(m, k, fields[k])
        if "status" in fields:
            m.status = ModelStatus(fields["status"])
        if "framework" in fields:
            m.framework = ModelFramework(fields["framework"])

    def delete_model(self, model_id: str) -> bool:
        """Remove a model and all its versions."""
        with self._lock:
            if model_id not in self._models:
                return False
            del self._models[model_id]
            if model_id in self._model_order:
                self._model_order.remove(model_id)
            return True

    # -- Version management -------------------------------------------------

    def add_version(self, model_id: str, version_number: str,
                    framework: Union[str, ModelFramework], artifact_path: str,
                    metrics: Optional[Dict[str, float]] = None,
                    parameters: Optional[Dict[str, Any]] = None,
                    description: str = "",
                    tags: Optional[List[str]] = None) -> Optional[ModelVersion]:
        """Add a new version to an existing model."""
        fw = ModelFramework(framework) if not isinstance(framework, ModelFramework) else framework
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return None
            if len(m.versions) >= self._max_versions:
                m.versions.pop(0)
            v = ModelVersion(
                model_id=model_id, version_number=version_number,
                framework=fw, artifact_path=artifact_path,
                metrics=metrics or {}, parameters=parameters or {},
                description=description, tags=tags or [],
            )
            _capped(m.versions, v, self._max_versions)
            m.updated_at = _now()
            return v

    def get_version(self, model_id: str,
                    version_id: str) -> Optional[ModelVersion]:
        """Return a specific version of a model."""
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return None
            return self._find_version(m, version_id)

    @staticmethod
    def _find_version(m: Model, version_id: str) -> Optional[ModelVersion]:
        for v in m.versions:
            if v.version_id == version_id:
                return v
        return None

    def list_versions(self, model_id: str,
                      status: Optional[str] = None) -> List[ModelVersion]:
        """List versions of a model with optional status filter."""
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return []
            if not status:
                return list(m.versions)
            return [v for v in m.versions if _enum_val(v.status) == status]

    def promote_version(self, model_id: str, version_id: str) -> bool:
        """Promote a version to active, demoting all others to inactive."""
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return False
            target = self._find_version(m, version_id)
            if not target:
                return False
            for v in m.versions:
                if v.status == VersionStatus.active:
                    v.status = VersionStatus.inactive
            target.status = VersionStatus.active
            m.updated_at = _now()
            return True

    def rollback_version(self, model_id: str, version_id: str) -> bool:
        """Mark a version as the rollback target."""
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return False
            target = self._find_version(m, version_id)
            if not target:
                return False
            target.status = VersionStatus.rollback_target
            m.updated_at = _now()
            return True

    # -- Deployment ---------------------------------------------------------

    def deploy_model(self, model_id: str, version_id: str,
                     target: Union[str, DeploymentTarget],
                     configuration: Optional[Dict[str, Any]] = None
                     ) -> Optional[DeploymentRecord]:
        """Create a deployment record for a model version."""
        tgt = DeploymentTarget(target) if not isinstance(target, DeploymentTarget) else target
        with self._lock:
            m = self._models.get(model_id)
            if not m or not self._find_version(m, version_id):
                return None
            rec = DeploymentRecord(
                model_id=model_id, version_id=version_id,
                target=tgt, configuration=configuration or {},
            )
            self._deployments[rec.deployment_id] = rec
            _capped(self._deploy_order, rec.deployment_id, 10_000)
            return rec

    def get_deployment(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Return a deployment record by ID."""
        with self._lock:
            return self._deployments.get(deployment_id)

    def list_deployments(self, model_id: Optional[str] = None,
                         status: Optional[str] = None
                         ) -> List[DeploymentRecord]:
        """List deployments with optional filters."""
        with self._lock:
            out: List[DeploymentRecord] = []
            for d in self._deployments.values():
                if model_id and d.model_id != model_id:
                    continue
                if status and d.status != status:
                    continue
                out.append(d)
            return out

    def _set_deployment_status(self, deployment_id: str, st: str) -> bool:
        d = self._deployments.get(deployment_id)
        if not d:
            return False
        d.status = st
        return True

    def complete_deployment(self, deployment_id: str) -> bool:
        """Mark a deployment as active."""
        with self._lock:
            return self._set_deployment_status(deployment_id, "active")

    def fail_deployment(self, deployment_id: str) -> bool:
        """Mark a deployment as failed."""
        with self._lock:
            return self._set_deployment_status(deployment_id, "failed")

    def rollback_deployment(self, deployment_id: str) -> bool:
        """Mark a deployment as rolled back."""
        with self._lock:
            return self._set_deployment_status(deployment_id, "rolled_back")

    # -- A/B Testing --------------------------------------------------------

    def create_ab_test(self, model_id: str, version_a_id: str,
                       version_b_id: str,
                       traffic_split_a: float = 0.5
                       ) -> Optional[ABTestConfig]:
        """Create a new A/B test configuration."""
        with self._lock:
            m = self._models.get(model_id)
            if not m:
                return None
            if not self._find_version(m, version_a_id):
                return None
            if not self._find_version(m, version_b_id):
                return None
            split = max(0.0, min(1.0, traffic_split_a))
            t = ABTestConfig(
                model_id=model_id, version_a_id=version_a_id,
                version_b_id=version_b_id, traffic_split_a=split,
            )
            self._ab_tests[t.test_id] = t
            _capped(self._test_order, t.test_id, 10_000)
            return t

    def get_ab_test(self, test_id: str) -> Optional[ABTestConfig]:
        """Return an A/B test by ID."""
        with self._lock:
            return self._ab_tests.get(test_id)

    def start_ab_test(self, test_id: str) -> bool:
        """Transition an A/B test to running."""
        with self._lock:
            t = self._ab_tests.get(test_id)
            if not t or t.status != "draft":
                return False
            t.status = "running"
            return True

    def complete_ab_test(self, test_id: str,
                         metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Complete an A/B test with final metrics."""
        with self._lock:
            t = self._ab_tests.get(test_id)
            if not t or t.status != "running":
                return False
            t.status = "completed"
            if metrics:
                t.metrics = metrics
            return True

    def route_ab_traffic(self, test_id: str) -> Optional[str]:
        """Return the version_id to serve based on the traffic split."""
        with self._lock:
            t = self._ab_tests.get(test_id)
            if not t or t.status != "running":
                return None
            if random.random() < t.traffic_split_a:  # noqa: S311
                return t.version_a_id
            return t.version_b_id

    # -- Stats --------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregate registry statistics."""
        with self._lock:
            total_versions = sum(len(m.versions) for m in self._models.values())
            status_counts: Dict[str, int] = {}
            for m in self._models.values():
                sv = _enum_val(m.status)
                status_counts[sv] = status_counts.get(sv, 0) + 1
            deploy_counts: Dict[str, int] = {}
            for d in self._deployments.values():
                deploy_counts[d.status] = deploy_counts.get(d.status, 0) + 1
            return {
                "total_models": len(self._models),
                "total_versions": total_versions,
                "total_deployments": len(self._deployments),
                "total_ab_tests": len(self._ab_tests),
                "model_status_breakdown": status_counts,
                "deployment_status_breakdown": deploy_counts,
            }


# -- Wingman pair validation ------------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """MLR-001 Wingman gate.

    Validate that storyline and actuals lists are non-empty, equal-length,
    and each pair matches.  Returns a pass/fail dict with diagnostics.
    """
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

def gate_mlr_in_sandbox(context: dict) -> dict:
    """MLR-001 Causality Sandbox gate.

    Verify that the provided context contains the required keys for an
    MLR action and that the values are acceptable within the sandbox.
    """
    required_keys = {"model_name", "framework", "owner"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("model_name"):
        return {"passed": False, "message": "model_name must be non-empty"}
    allowed_frameworks = {f.value for f in ModelFramework}
    if context["framework"] not in allowed_frameworks:
        return {"passed": False,
                "message": f"Framework '{context['framework']}' not in "
                           f"{sorted(allowed_frameworks)}"}
    return {"passed": True, "message": "Sandbox gate passed",
            "model_name": context["model_name"]}


# -- Flask helpers ----------------------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}


def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "MLR_MISSING"}), 400
    return None


def _not_found(msg: str = "Not found") -> Any:
    return jsonify({"error": msg, "code": "MLR_404"}), 404


# -- Flask Blueprint factory ------------------------------------------------

def create_mlr_api(engine: MLModelRegistry) -> Any:
    """Create a Flask Blueprint exposing ML model registry endpoints.

    All routes live under ``/api/mlr/`` and return JSON with an error
    envelope ``{"error": "…", "code": "MLR_*"}`` on failure.
    """
    if not _HAS_FLASK:
        return Blueprint("mlr_api", __name__)  # type: ignore[call-arg]
    bp = Blueprint("mlr_api", __name__, url_prefix="/api")
    _register_health_routes(bp, engine)
    _register_model_routes(bp, engine)
    _register_version_routes(bp, engine)
    _register_deployment_routes(bp, engine)
    _register_ab_test_routes(bp, engine)
    _register_stats_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp


def _register_health_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register health-check endpoint."""

    @bp.route("/mlr/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "healthy", "module": "MLR-001"})


def _register_model_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register model CRUD endpoints."""

    @bp.route("/mlr/models", methods=["POST"])
    def register_model() -> Any:
        b = _api_body()
        err = _api_need(b, "name", "description", "owner", "framework")
        if err:
            return err
        try:
            fw = ModelFramework(b["framework"])
        except ValueError:
            return jsonify({"error": "Invalid framework",
                            "code": "MLR_INVALID"}), 400
        m = eng.register_model(
            b["name"], b["description"], b["owner"], fw,
            tags=b.get("tags", []),
        )
        return jsonify(m.to_dict()), 201

    @bp.route("/mlr/models", methods=["GET"])
    def list_models() -> Any:
        a = request.args
        models = eng.list_models(
            status=a.get("status"), framework=a.get("framework"),
            owner=a.get("owner"), tag=a.get("tag"),
        )
        return jsonify([m.to_dict() for m in models])

    @bp.route("/mlr/models/<model_id>", methods=["GET"])
    def get_model(model_id: str) -> Any:
        m = eng.get_model(model_id)
        if not m:
            return _not_found("Model not found")
        return jsonify(m.to_dict())

    @bp.route("/mlr/models/<model_id>", methods=["DELETE"])
    def delete_model(model_id: str) -> Any:
        if not eng.delete_model(model_id):
            return _not_found("Model not found")
        return jsonify({"deleted": True}), 200


def _register_version_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register model-version endpoints."""

    @bp.route("/mlr/models/<model_id>/versions", methods=["POST"])
    def add_version(model_id: str) -> Any:
        b = _api_body()
        err = _api_need(b, "version_number", "framework", "artifact_path")
        if err:
            return err
        try:
            fw = ModelFramework(b["framework"])
        except ValueError:
            return jsonify({"error": "Invalid framework",
                            "code": "MLR_INVALID"}), 400
        v = eng.add_version(
            model_id, b["version_number"], fw, b["artifact_path"],
            metrics=b.get("metrics"), parameters=b.get("parameters"),
            description=b.get("description", ""), tags=b.get("tags"),
        )
        if not v:
            return _not_found("Model not found")
        return jsonify(v.to_dict()), 201

    @bp.route("/mlr/models/<model_id>/versions", methods=["GET"])
    def list_versions(model_id: str) -> Any:
        st = request.args.get("status")
        vs = eng.list_versions(model_id, status=st)
        return jsonify([v.to_dict() for v in vs])

    @bp.route("/mlr/models/<model_id>/versions/<version_id>",
              methods=["GET"])
    def get_version(model_id: str, version_id: str) -> Any:
        v = eng.get_version(model_id, version_id)
        if not v:
            return _not_found("Version not found")
        return jsonify(v.to_dict())

    @bp.route("/mlr/models/<model_id>/versions/<version_id>/promote",
              methods=["POST"])
    def promote_version(model_id: str, version_id: str) -> Any:
        if not eng.promote_version(model_id, version_id):
            return _not_found("Model or version not found")
        return jsonify({"promoted": True})

    @bp.route("/mlr/models/<model_id>/versions/<version_id>/rollback",
              methods=["POST"])
    def rollback_version(model_id: str, version_id: str) -> Any:
        if not eng.rollback_version(model_id, version_id):
            return _not_found("Model or version not found")
        return jsonify({"rollback_target_set": True})


def _register_deployment_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register deployment CRUD endpoints."""

    @bp.route("/mlr/deployments", methods=["POST"])
    def deploy_model() -> Any:
        b = _api_body()
        err = _api_need(b, "model_id", "version_id", "target")
        if err:
            return err
        try:
            tgt = DeploymentTarget(b["target"])
        except ValueError:
            return jsonify({"error": "Invalid target",
                            "code": "MLR_INVALID"}), 400
        rec = eng.deploy_model(
            b["model_id"], b["version_id"], tgt,
            configuration=b.get("configuration"),
        )
        if not rec:
            return _not_found("Model or version not found")
        return jsonify(rec.to_dict()), 201

    @bp.route("/mlr/deployments", methods=["GET"])
    def list_deployments() -> Any:
        a = request.args
        ds = eng.list_deployments(
            model_id=a.get("model_id"), status=a.get("status"),
        )
        return jsonify([d.to_dict() for d in ds])

    @bp.route("/mlr/deployments/<deployment_id>", methods=["GET"])
    def get_deployment(deployment_id: str) -> Any:
        d = eng.get_deployment(deployment_id)
        if not d:
            return _not_found("Deployment not found")
        return jsonify(d.to_dict())

    _register_deployment_action_routes(bp, eng)


def _register_deployment_action_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register deployment status-transition endpoints."""

    @bp.route("/mlr/deployments/<deployment_id>/complete", methods=["POST"])
    def complete_deployment(deployment_id: str) -> Any:
        if not eng.complete_deployment(deployment_id):
            return _not_found("Deployment not found")
        return jsonify({"completed": True})

    @bp.route("/mlr/deployments/<deployment_id>/fail", methods=["POST"])
    def fail_deployment(deployment_id: str) -> Any:
        if not eng.fail_deployment(deployment_id):
            return _not_found("Deployment not found")
        return jsonify({"failed": True})

    @bp.route("/mlr/deployments/<deployment_id>/rollback", methods=["POST"])
    def rollback_deployment(deployment_id: str) -> Any:
        if not eng.rollback_deployment(deployment_id):
            return _not_found("Deployment not found")
        return jsonify({"rolled_back": True})


def _register_ab_test_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register A/B test endpoints."""

    @bp.route("/mlr/ab-tests", methods=["POST"])
    def create_ab_test() -> Any:
        b = _api_body()
        err = _api_need(b, "model_id", "version_a_id", "version_b_id")
        if err:
            return err
        t = eng.create_ab_test(
            b["model_id"], b["version_a_id"], b["version_b_id"],
            traffic_split_a=float(b.get("traffic_split_a", 0.5)),
        )
        if not t:
            return _not_found("Model or version not found")
        return jsonify(t.to_dict()), 201

    @bp.route("/mlr/ab-tests/<test_id>", methods=["GET"])
    def get_ab_test(test_id: str) -> Any:
        t = eng.get_ab_test(test_id)
        if not t:
            return _not_found("A/B test not found")
        return jsonify(t.to_dict())

    @bp.route("/mlr/ab-tests/<test_id>/start", methods=["POST"])
    def start_ab_test(test_id: str) -> Any:
        if not eng.start_ab_test(test_id):
            return _not_found("A/B test not found or not in draft")
        return jsonify({"started": True})

    @bp.route("/mlr/ab-tests/<test_id>/complete", methods=["POST"])
    def complete_ab_test(test_id: str) -> Any:
        b = _api_body()
        if not eng.complete_ab_test(test_id, metrics=b.get("metrics")):
            return _not_found("A/B test not found or not running")
        return jsonify({"completed": True})

    @bp.route("/mlr/ab-tests/<test_id>/route", methods=["POST"])
    def route_ab_traffic(test_id: str) -> Any:
        vid = eng.route_ab_traffic(test_id)
        if not vid:
            return _not_found("A/B test not found or not running")
        return jsonify({"version_id": vid})


def _register_stats_routes(bp: Any, eng: MLModelRegistry) -> None:
    """Register stats endpoint."""

    @bp.route("/mlr/stats", methods=["GET"])
    def get_stats() -> Any:
        return jsonify(eng.get_stats())

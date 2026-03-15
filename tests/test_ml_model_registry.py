# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for ml_model_registry — MLR-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable MLRRecord with cause / effect / lesson annotations.
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

from ml_model_registry import (  # noqa: E402
    ABTestConfig,
    DeploymentRecord,
    DeploymentTarget,
    MLModelRegistry,
    Model,
    ModelFramework,
    ModelStatus,
    ModelVersion,
    VersionStatus,
    create_mlr_api,
    gate_mlr_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class MLRRecord:
    """One MLR check record."""

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


_RESULTS: List[MLRRecord] = []


def record(
    check_id: str,
    desc: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(
        MLRRecord(
            check_id=check_id,
            description=desc,
            expected=expected,
            actual=actual,
            passed=ok,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    return ok


# -- Helpers ---------------------------------------------------------------


def _eng() -> MLModelRegistry:
    return MLModelRegistry()


def _eng_with_model() -> tuple:
    """Return engine + one registered model."""
    eng = _eng()
    m = eng.register_model("resnet50", "Image classifier", "alice", "pytorch", ["cv"])
    return eng, m


def _eng_with_version() -> tuple:
    """Return engine + model + one version."""
    eng, m = _eng_with_model()
    v = eng.add_version(
        m.model_id, "1.0.0", "pytorch", "/models/resnet50.pt",
        {"accuracy": 0.95, "f1": 0.93}, {"epochs": 50, "lr": 0.001},
        "Initial release", ["prod-ready"],
    )
    return eng, m, v


def _eng_with_deployment() -> tuple:
    """Return engine + model + version + deployment."""
    eng, m, v = _eng_with_version()
    d = eng.deploy_model(m.model_id, v.version_id, "local", {"gpu": True})
    return eng, m, v, d


def _eng_with_ab_test() -> tuple:
    """Return engine + model + 2 versions + ab test."""
    eng, m, v1 = _eng_with_version()
    v2 = eng.add_version(
        m.model_id, "2.0.0", "pytorch", "/models/resnet50_v2.pt",
        {"accuracy": 0.97}, {}, "Improved", [],
    )
    t = eng.create_ab_test(m.model_id, v1.version_id, v2.version_id, 0.6)
    return eng, m, v1, v2, t


# =====================================================================
# 1. Enum tests
# =====================================================================


def test_mlr001_model_status_enum():
    ok = record(
        "MLR-001", "ModelStatus has expected values",
        True,
        all(hasattr(ModelStatus, v) for v in ["draft", "staging", "production", "archived", "deprecated"]),
        cause="Enum values defined", effect="Status tracking works", lesson="Enumerate all lifecycle states",
    )
    assert ok


def test_mlr002_model_framework_enum():
    ok = record(
        "MLR-002", "ModelFramework has expected values",
        True,
        all(hasattr(ModelFramework, v) for v in ["pytorch", "tensorflow", "sklearn", "onnx", "custom"]),
    )
    assert ok


def test_mlr003_deployment_target_enum():
    ok = record(
        "MLR-003", "DeploymentTarget has expected values",
        True,
        all(hasattr(DeploymentTarget, v) for v in ["local", "cloud", "edge", "hybrid"]),
    )
    assert ok


def test_mlr004_version_status_enum():
    ok = record(
        "MLR-004", "VersionStatus has expected values",
        True,
        all(hasattr(VersionStatus, v) for v in ["active", "inactive", "rollback_target"]),
    )
    assert ok


# =====================================================================
# 2. Dataclass tests
# =====================================================================


def test_mlr005_model_version_dataclass():
    v = ModelVersion(
        version_id="v1", model_id="m1", version_number="1.0.0",
        framework=ModelFramework.pytorch, artifact_path="/a.pt",
        metrics={"acc": 0.9}, parameters={"lr": 0.01},
        status=VersionStatus.active, created_at="now", description="test",
        tags=["t1"],
    )
    ok = record("MLR-005", "ModelVersion dataclass fields", "v1", v.version_id)
    assert ok


def test_mlr006_model_dataclass():
    m = Model(
        model_id="m1", name="test", description="d", owner="o",
        framework=ModelFramework.sklearn, status=ModelStatus.draft,
        versions=[], created_at="now", updated_at="now", tags=["t"],
    )
    ok = record("MLR-006", "Model dataclass fields", "test", m.name)
    assert ok


def test_mlr007_deployment_record_dataclass():
    d = DeploymentRecord(
        deployment_id="d1", model_id="m1", version_id="v1",
        target=DeploymentTarget.cloud, status="pending",
        deployed_at="now", configuration={"k": "v"},
    )
    ok = record("MLR-007", "DeploymentRecord dataclass", "cloud", d.target.value)
    assert ok


def test_mlr008_ab_test_config_dataclass():
    t = ABTestConfig(
        test_id="t1", model_id="m1", version_a_id="va", version_b_id="vb",
        traffic_split_a=0.5, status="draft", created_at="now", metrics={},
    )
    ok = record("MLR-008", "ABTestConfig dataclass", 0.5, t.traffic_split_a)
    assert ok


# =====================================================================
# 3. Model CRUD
# =====================================================================


def test_mlr009_register_model():
    eng, m = _eng_with_model()
    ok = record("MLR-009", "Register model returns Model", "resnet50", m.name)
    assert ok


def test_mlr010_get_model():
    eng, m = _eng_with_model()
    got = eng.get_model(m.model_id)
    ok = record("MLR-010", "Get model by ID", m.model_id, got.model_id)
    assert ok


def test_mlr011_get_model_nonexistent():
    eng = _eng()
    got = eng.get_model("bad-id")
    ok = record("MLR-011", "Get nonexistent model returns None", True, got is None)
    assert ok


def test_mlr012_list_models():
    eng = _eng()
    eng.register_model("a", "d", "o", "pytorch", [])
    eng.register_model("b", "d", "o", "sklearn", [])
    models = eng.list_models()
    ok = record("MLR-012", "List all models", 2, len(models))
    assert ok


def test_mlr013_list_models_filter_framework():
    eng = _eng()
    eng.register_model("a", "d", "o", "pytorch", [])
    eng.register_model("b", "d", "o", "sklearn", [])
    models = eng.list_models(framework="pytorch")
    ok = record("MLR-013", "Filter models by framework", 1, len(models))
    assert ok


def test_mlr014_list_models_filter_owner():
    eng = _eng()
    eng.register_model("a", "d", "alice", "pytorch", [])
    eng.register_model("b", "d", "bob", "pytorch", [])
    models = eng.list_models(owner="bob")
    ok = record("MLR-014", "Filter models by owner", 1, len(models))
    assert ok


def test_mlr015_list_models_filter_tag():
    eng = _eng()
    eng.register_model("a", "d", "o", "pytorch", ["cv", "prod"])
    eng.register_model("b", "d", "o", "pytorch", ["nlp"])
    models = eng.list_models(tag="cv")
    ok = record("MLR-015", "Filter models by tag", 1, len(models))
    assert ok


def test_mlr016_list_models_filter_status():
    eng = _eng()
    eng.register_model("a", "d", "o", "pytorch", [])
    models = eng.list_models(status="draft")
    ok = record("MLR-016", "Filter models by status", 1, len(models))
    assert ok


def test_mlr017_update_model():
    eng, m = _eng_with_model()
    updated = eng.update_model(m.model_id, description="Updated desc")
    ok = record("MLR-017", "Update model description", "Updated desc", updated.description)
    assert ok


def test_mlr018_update_model_nonexistent():
    eng = _eng()
    result = eng.update_model("bad-id", description="x")
    ok = record("MLR-018", "Update nonexistent model returns None", True, result is None)
    assert ok


def test_mlr019_delete_model():
    eng, m = _eng_with_model()
    ok1 = eng.delete_model(m.model_id)
    ok2 = eng.get_model(m.model_id) is None
    ok = record("MLR-019", "Delete model", True, ok1 and ok2)
    assert ok


def test_mlr020_delete_model_nonexistent():
    eng = _eng()
    ok = record("MLR-020", "Delete nonexistent model", False, eng.delete_model("bad"))
    assert ok


# =====================================================================
# 4. Version management
# =====================================================================


def test_mlr021_add_version():
    eng, m, v = _eng_with_version()
    ok = record("MLR-021", "Add version returns ModelVersion", "1.0.0", v.version_number)
    assert ok


def test_mlr022_add_version_bad_model():
    eng = _eng()
    v = eng.add_version("bad-id", "1.0", "pytorch", "/x", {}, {}, "", [])
    ok = record("MLR-022", "Add version to bad model returns None", True, v is None)
    assert ok


def test_mlr023_get_version():
    eng, m, v = _eng_with_version()
    got = eng.get_version(m.model_id, v.version_id)
    ok = record("MLR-023", "Get version by ID", v.version_id, got.version_id)
    assert ok


def test_mlr024_get_version_nonexistent():
    eng, m = _eng_with_model()
    got = eng.get_version(m.model_id, "bad-v")
    ok = record("MLR-024", "Get nonexistent version returns None", True, got is None)
    assert ok


def test_mlr025_list_versions():
    eng, m, v1 = _eng_with_version()
    eng.add_version(m.model_id, "2.0.0", "pytorch", "/b.pt", {}, {}, "v2", [])
    versions = eng.list_versions(m.model_id)
    ok = record("MLR-025", "List versions", 2, len(versions))
    assert ok


def test_mlr026_list_versions_filter_status():
    eng, m, v = _eng_with_version()
    eng.add_version(m.model_id, "2.0.0", "pytorch", "/b.pt", {}, {}, "v2", [])
    # Promote v1 to active, v2 stays inactive
    eng.promote_version(m.model_id, v.version_id)
    active = eng.list_versions(m.model_id, status="active")
    ok = record("MLR-026", "List versions filter by status", 1, len(active))
    assert ok


def test_mlr027_promote_version():
    eng, m, v = _eng_with_version()
    result = eng.promote_version(m.model_id, v.version_id)
    got = eng.get_version(m.model_id, v.version_id)
    ok = record("MLR-027", "Promote version sets active", "active", got.status.value if hasattr(got.status, 'value') else got.status)
    assert ok


def test_mlr028_promote_demotes_others():
    eng, m, v1 = _eng_with_version()
    v2 = eng.add_version(m.model_id, "2.0.0", "pytorch", "/b.pt", {}, {}, "", [])
    eng.promote_version(m.model_id, v1.version_id)
    eng.promote_version(m.model_id, v2.version_id)
    v1_got = eng.get_version(m.model_id, v1.version_id)
    status_val = v1_got.status.value if hasattr(v1_got.status, 'value') else v1_got.status
    ok = record("MLR-028", "Promoting new version demotes old", "inactive", status_val)
    assert ok


def test_mlr029_rollback_version():
    eng, m, v = _eng_with_version()
    eng.promote_version(m.model_id, v.version_id)
    result = eng.rollback_version(m.model_id, v.version_id)
    got = eng.get_version(m.model_id, v.version_id)
    status_val = got.status.value if hasattr(got.status, 'value') else got.status
    ok = record("MLR-029", "Rollback sets rollback_target", "rollback_target", status_val)
    assert ok


def test_mlr030_rollback_nonexistent():
    eng, m = _eng_with_model()
    ok = record("MLR-030", "Rollback nonexistent version", False, eng.rollback_version(m.model_id, "bad"))
    assert ok


def test_mlr031_version_metrics():
    eng, m, v = _eng_with_version()
    ok = record("MLR-031", "Version stores metrics", 0.95, v.metrics.get("accuracy"))
    assert ok


def test_mlr032_version_parameters():
    eng, m, v = _eng_with_version()
    ok = record("MLR-032", "Version stores parameters", 50, v.parameters.get("epochs"))
    assert ok


# =====================================================================
# 5. Deployment
# =====================================================================


def test_mlr033_deploy_model():
    eng, m, v, d = _eng_with_deployment()
    ok = record("MLR-033", "Deploy creates pending record", "pending", d.status)
    assert ok


def test_mlr034_deploy_bad_model():
    eng = _eng()
    d = eng.deploy_model("bad", "bad", "local", {})
    ok = record("MLR-034", "Deploy bad model returns None", True, d is None)
    assert ok


def test_mlr035_get_deployment():
    eng, m, v, d = _eng_with_deployment()
    got = eng.get_deployment(d.deployment_id)
    ok = record("MLR-035", "Get deployment by ID", d.deployment_id, got.deployment_id)
    assert ok


def test_mlr036_get_deployment_nonexistent():
    eng = _eng()
    ok = record("MLR-036", "Get nonexistent deployment", True, eng.get_deployment("bad") is None)
    assert ok


def test_mlr037_list_deployments():
    eng, m, v, d1 = _eng_with_deployment()
    d2 = eng.deploy_model(m.model_id, v.version_id, "cloud", {})
    deps = eng.list_deployments()
    ok = record("MLR-037", "List all deployments", 2, len(deps))
    assert ok


def test_mlr038_list_deployments_filter_model():
    eng, m, v, d = _eng_with_deployment()
    deps = eng.list_deployments(model_id=m.model_id)
    ok = record("MLR-038", "Filter deployments by model", 1, len(deps))
    assert ok


def test_mlr039_list_deployments_filter_status():
    eng, m, v, d = _eng_with_deployment()
    eng.complete_deployment(d.deployment_id)
    deps = eng.list_deployments(status="active")
    ok = record("MLR-039", "Filter deployments by status", 1, len(deps))
    assert ok


def test_mlr040_complete_deployment():
    eng, m, v, d = _eng_with_deployment()
    result = eng.complete_deployment(d.deployment_id)
    got = eng.get_deployment(d.deployment_id)
    ok = record("MLR-040", "Complete deployment sets active", "active", got.status)
    assert ok


def test_mlr041_fail_deployment():
    eng, m, v, d = _eng_with_deployment()
    eng.fail_deployment(d.deployment_id)
    got = eng.get_deployment(d.deployment_id)
    ok = record("MLR-041", "Fail deployment sets failed", "failed", got.status)
    assert ok


def test_mlr042_rollback_deployment():
    eng, m, v, d = _eng_with_deployment()
    eng.complete_deployment(d.deployment_id)
    eng.rollback_deployment(d.deployment_id)
    got = eng.get_deployment(d.deployment_id)
    ok = record("MLR-042", "Rollback deployment sets rolled_back", "rolled_back", got.status)
    assert ok


def test_mlr043_complete_nonexistent_deployment():
    eng = _eng()
    ok = record("MLR-043", "Complete nonexistent deployment", False, eng.complete_deployment("bad"))
    assert ok


def test_mlr044_deploy_target_value():
    eng, m, v, d = _eng_with_deployment()
    target_val = d.target.value if hasattr(d.target, 'value') else d.target
    ok = record("MLR-044", "Deployment target is local", "local", target_val)
    assert ok


# =====================================================================
# 6. A/B Testing
# =====================================================================


def test_mlr045_create_ab_test():
    eng, m, v1, v2, t = _eng_with_ab_test()
    ok = record("MLR-045", "Create A/B test", "draft", t.status)
    assert ok


def test_mlr046_create_ab_test_bad_model():
    eng = _eng()
    t = eng.create_ab_test("bad", "va", "vb", 0.5)
    ok = record("MLR-046", "Create A/B test bad model", True, t is None)
    assert ok


def test_mlr047_get_ab_test():
    eng, m, v1, v2, t = _eng_with_ab_test()
    got = eng.get_ab_test(t.test_id)
    ok = record("MLR-047", "Get A/B test by ID", t.test_id, got.test_id)
    assert ok


def test_mlr048_get_ab_test_nonexistent():
    eng = _eng()
    ok = record("MLR-048", "Get nonexistent A/B test", True, eng.get_ab_test("bad") is None)
    assert ok


def test_mlr049_start_ab_test():
    eng, m, v1, v2, t = _eng_with_ab_test()
    eng.start_ab_test(t.test_id)
    got = eng.get_ab_test(t.test_id)
    ok = record("MLR-049", "Start A/B test sets running", "running", got.status)
    assert ok


def test_mlr050_complete_ab_test():
    eng, m, v1, v2, t = _eng_with_ab_test()
    eng.start_ab_test(t.test_id)
    eng.complete_ab_test(t.test_id, {"winner": "v1", "p_value": 0.03})
    got = eng.get_ab_test(t.test_id)
    ok = record("MLR-050", "Complete A/B test", "completed", got.status)
    assert ok


def test_mlr051_complete_ab_test_stores_metrics():
    eng, m, v1, v2, t = _eng_with_ab_test()
    eng.start_ab_test(t.test_id)
    eng.complete_ab_test(t.test_id, {"winner": "a"})
    got = eng.get_ab_test(t.test_id)
    ok = record("MLR-051", "Complete A/B test stores metrics", "a", got.metrics.get("winner"))
    assert ok


def test_mlr052_route_ab_traffic():
    eng, m, v1, v2, t = _eng_with_ab_test()
    eng.start_ab_test(t.test_id)
    routed = eng.route_ab_traffic(t.test_id)
    valid_ids = {v1.version_id, v2.version_id}
    ok = record("MLR-052", "Route A/B traffic returns valid version", True, routed in valid_ids)
    assert ok


def test_mlr053_route_ab_traffic_not_running():
    eng, m, v1, v2, t = _eng_with_ab_test()
    routed = eng.route_ab_traffic(t.test_id)
    ok = record("MLR-053", "Route A/B traffic when not running returns None", True, routed is None)
    assert ok


def test_mlr054_ab_traffic_split_distribution():
    """Verify traffic split roughly matches configured ratio over many calls."""
    eng, m, v1, v2, t = _eng_with_ab_test()
    eng.start_ab_test(t.test_id)
    count_a = 0
    n = 200
    for _ in range(n):
        if eng.route_ab_traffic(t.test_id) == v1.version_id:
            count_a += 1
    ratio = count_a / n
    # split_a is 0.6, allow 0.4-0.8 range
    ok = record("MLR-054", "Traffic split roughly 60/40", True, 0.4 <= ratio <= 0.8,
                cause="Random routing with 0.6 split", effect="A gets ~60% traffic",
                lesson="Statistical test needs wide tolerance")
    assert ok


def test_mlr055_start_nonexistent_ab_test():
    eng = _eng()
    ok = record("MLR-055", "Start nonexistent A/B test", False, eng.start_ab_test("bad"))
    assert ok


# =====================================================================
# 7. Stats
# =====================================================================


def test_mlr056_stats_empty():
    eng = _eng()
    s = eng.get_stats()
    ok = record("MLR-056", "Stats on empty registry", 0, s["total_models"])
    assert ok


def test_mlr057_stats_populated():
    eng, m, v, d = _eng_with_deployment()
    s = eng.get_stats()
    ok = record("MLR-057", "Stats total_models", 1, s["total_models"])
    ok2 = record("MLR-057b", "Stats total_versions", 1, s["total_versions"])
    ok3 = record("MLR-057c", "Stats total_deployments", 1, s["total_deployments"])
    assert ok and ok2 and ok3


# =====================================================================
# 8. Wingman pair validation
# =====================================================================


def test_mlr058_wingman_valid():
    r = validate_wingman_pair(["a", "b"], ["a", "b"])
    ok = record("MLR-058", "Wingman valid pair passes", True, r["passed"])
    assert ok


def test_mlr059_wingman_empty_storyline():
    r = validate_wingman_pair([], ["a"])
    ok = record("MLR-059", "Wingman empty storyline fails", False, r["passed"])
    assert ok


def test_mlr060_wingman_empty_actuals():
    r = validate_wingman_pair(["a"], [])
    ok = record("MLR-060", "Wingman empty actuals fails", False, r["passed"])
    assert ok


def test_mlr061_wingman_length_mismatch():
    r = validate_wingman_pair(["a", "b"], ["a"])
    ok = record("MLR-061", "Wingman length mismatch fails", False, r["passed"])
    assert ok


# =====================================================================
# 9. Sandbox gating
# =====================================================================


def test_mlr062_sandbox_valid():
    ctx = {"model_name": "mymodel", "framework": "pytorch", "owner": "alice"}
    r = gate_mlr_in_sandbox(ctx)
    ok = record("MLR-062", "Sandbox valid context passes", True, r["passed"])
    assert ok


def test_mlr063_sandbox_missing_key():
    ctx = {"model_name": "mymodel"}
    r = gate_mlr_in_sandbox(ctx)
    ok = record("MLR-063", "Sandbox missing key fails", False, r["passed"])
    assert ok


def test_mlr064_sandbox_empty_model_name():
    ctx = {"model_name": "", "framework": "pytorch", "owner": "alice"}
    r = gate_mlr_in_sandbox(ctx)
    ok = record("MLR-064", "Sandbox empty model_name fails", False, r["passed"])
    assert ok


def test_mlr065_sandbox_bad_framework():
    ctx = {"model_name": "m", "framework": "unknown_fw", "owner": "alice"}
    r = gate_mlr_in_sandbox(ctx)
    ok = record("MLR-065", "Sandbox bad framework fails", False, r["passed"])
    assert ok


# =====================================================================
# 10. Flask API tests
# =====================================================================


def _make_client():
    """Create a Flask test client with the MLR blueprint."""
    from flask import Flask
    eng = MLModelRegistry()
    app = Flask(__name__)
    app.register_blueprint(create_mlr_api(eng))
    return app.test_client(), eng


def test_mlr066_api_health():
    client, _ = _make_client()
    resp = client.get("/api/mlr/health")
    ok = record("MLR-066", "API health returns 200", 200, resp.status_code)
    assert ok


def test_mlr067_api_register_model():
    client, _ = _make_client()
    resp = client.post("/api/mlr/models", json={
        "name": "bert", "description": "NLP model", "owner": "bob",
        "framework": "pytorch", "tags": ["nlp"],
    })
    ok = record("MLR-067", "API register model returns 201", 201, resp.status_code)
    data = resp.get_json()
    ok2 = record("MLR-067b", "Response has model_id", True, "model_id" in data)
    assert ok and ok2


def test_mlr068_api_register_model_missing_field():
    client, _ = _make_client()
    resp = client.post("/api/mlr/models", json={"name": "x"})
    ok = record("MLR-068", "API missing fields returns 400", 400, resp.status_code)
    assert ok


def test_mlr069_api_list_models():
    client, eng = _make_client()
    eng.register_model("a", "d", "o", "pytorch", [])
    resp = client.get("/api/mlr/models")
    ok = record("MLR-069", "API list models returns 200", 200, resp.status_code)
    data = resp.get_json()
    ok2 = record("MLR-069b", "Returns list of models", 1, len(data.get("models", data) if isinstance(data, dict) else data))
    assert ok and ok2


def test_mlr070_api_get_model():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    resp = client.get(f"/api/mlr/models/{m.model_id}")
    ok = record("MLR-070", "API get model returns 200", 200, resp.status_code)
    assert ok


def test_mlr071_api_get_model_404():
    client, _ = _make_client()
    resp = client.get("/api/mlr/models/bad-id")
    ok = record("MLR-071", "API get missing model returns 404", 404, resp.status_code)
    assert ok


def test_mlr072_api_delete_model():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    resp = client.delete(f"/api/mlr/models/{m.model_id}")
    ok = record("MLR-072", "API delete model returns 200", 200, resp.status_code)
    assert ok


def test_mlr073_api_add_version():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    resp = client.post(f"/api/mlr/models/{m.model_id}/versions", json={
        "version_number": "1.0.0", "framework": "pytorch",
        "artifact_path": "/m.pt", "metrics": {"acc": 0.9},
        "parameters": {}, "description": "v1", "tags": [],
    })
    ok = record("MLR-073", "API add version returns 201", 201, resp.status_code)
    assert ok


def test_mlr074_api_list_versions():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    resp = client.get(f"/api/mlr/models/{m.model_id}/versions")
    ok = record("MLR-074", "API list versions returns 200", 200, resp.status_code)
    assert ok


def test_mlr075_api_promote_version():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    resp = client.post(f"/api/mlr/models/{m.model_id}/versions/{v.version_id}/promote")
    ok = record("MLR-075", "API promote version returns 200", 200, resp.status_code)
    assert ok


def test_mlr076_api_rollback_version():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    eng.promote_version(m.model_id, v.version_id)
    resp = client.post(f"/api/mlr/models/{m.model_id}/versions/{v.version_id}/rollback")
    ok = record("MLR-076", "API rollback version returns 200", 200, resp.status_code)
    assert ok


def test_mlr077_api_deploy():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    resp = client.post("/api/mlr/deployments", json={
        "model_id": m.model_id, "version_id": v.version_id,
        "target": "local", "configuration": {},
    })
    ok = record("MLR-077", "API deploy returns 201", 201, resp.status_code)
    assert ok


def test_mlr078_api_list_deployments():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    eng.deploy_model(m.model_id, v.version_id, "local", {})
    resp = client.get("/api/mlr/deployments")
    ok = record("MLR-078", "API list deployments returns 200", 200, resp.status_code)
    assert ok


def test_mlr079_api_complete_deployment():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    d = eng.deploy_model(m.model_id, v.version_id, "local", {})
    resp = client.post(f"/api/mlr/deployments/{d.deployment_id}/complete")
    ok = record("MLR-079", "API complete deployment returns 200", 200, resp.status_code)
    assert ok


def test_mlr080_api_create_ab_test():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v1 = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    v2 = eng.add_version(m.model_id, "2.0", "pytorch", "/b", {}, {}, "", [])
    resp = client.post("/api/mlr/ab-tests", json={
        "model_id": m.model_id, "version_a_id": v1.version_id,
        "version_b_id": v2.version_id, "traffic_split_a": 0.5,
    })
    ok = record("MLR-080", "API create A/B test returns 201", 201, resp.status_code)
    assert ok


def test_mlr081_api_start_ab_test():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v1 = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    v2 = eng.add_version(m.model_id, "2.0", "pytorch", "/b", {}, {}, "", [])
    t = eng.create_ab_test(m.model_id, v1.version_id, v2.version_id, 0.5)
    resp = client.post(f"/api/mlr/ab-tests/{t.test_id}/start")
    ok = record("MLR-081", "API start A/B test returns 200", 200, resp.status_code)
    assert ok


def test_mlr082_api_route_ab_traffic():
    client, eng = _make_client()
    m = eng.register_model("a", "d", "o", "pytorch", [])
    v1 = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    v2 = eng.add_version(m.model_id, "2.0", "pytorch", "/b", {}, {}, "", [])
    t = eng.create_ab_test(m.model_id, v1.version_id, v2.version_id, 0.5)
    eng.start_ab_test(t.test_id)
    resp = client.post(f"/api/mlr/ab-tests/{t.test_id}/route")
    ok = record("MLR-082", "API route A/B traffic returns 200", 200, resp.status_code)
    assert ok


def test_mlr083_api_stats():
    client, _ = _make_client()
    resp = client.get("/api/mlr/stats")
    ok = record("MLR-083", "API stats returns 200", 200, resp.status_code)
    assert ok


# =====================================================================
# 11. Thread safety
# =====================================================================


def test_mlr084_concurrent_register():
    """100 concurrent model registrations should all succeed."""
    eng = _eng()
    errors = []

    def _register(i: int) -> None:
        try:
            eng.register_model(f"model-{i}", "d", "o", "pytorch", [])
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=_register, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = record("MLR-084", "100 concurrent registrations, 0 errors", 0, len(errors))
    ok2 = record("MLR-084b", "All 100 models registered", 100, len(eng.list_models()))
    assert ok and ok2


def test_mlr085_concurrent_versions():
    """50 concurrent version additions to same model."""
    eng, m = _eng_with_model()
    errors = []

    def _add_ver(i: int) -> None:
        try:
            eng.add_version(m.model_id, f"{i}.0.0", "pytorch", f"/m{i}.pt", {}, {}, "", [])
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=_add_ver, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = record("MLR-085", "50 concurrent versions, 0 errors", 0, len(errors))
    ok2 = record("MLR-085b", "All 50 versions added", 50, len(eng.list_versions(m.model_id)))
    assert ok and ok2


# =====================================================================
# 12. Edge cases
# =====================================================================


def test_mlr086_empty_name_model():
    eng = _eng()
    m = eng.register_model("", "d", "o", "pytorch", [])
    ok = record("MLR-086", "Model with empty name still registers", True, m is not None)
    assert ok


def test_mlr087_long_description():
    eng = _eng()
    long_desc = "x" * 10000
    m = eng.register_model("m", long_desc, "o", "pytorch", [])
    ok = record("MLR-087", "Long description accepted", 10000, len(m.description))
    assert ok


def test_mlr088_version_with_empty_metrics():
    eng, m = _eng_with_model()
    v = eng.add_version(m.model_id, "1.0", "pytorch", "/a", {}, {}, "", [])
    ok = record("MLR-088", "Version with empty metrics", 0, len(v.metrics))
    assert ok


def test_mlr089_multiple_deployments_same_version():
    eng, m, v = _eng_with_version()
    d1 = eng.deploy_model(m.model_id, v.version_id, "local", {})
    d2 = eng.deploy_model(m.model_id, v.version_id, "cloud", {})
    ok = record("MLR-089", "Multiple deployments same version", 2, len(eng.list_deployments()))
    assert ok


def test_mlr090_model_capacity_limit():
    """Verify engine respects max_models cap."""
    eng = MLModelRegistry(max_models=5)
    for i in range(5):
        eng.register_model(f"m{i}", "d", "o", "pytorch", [])
    # 6th should still not crash (capped_append handles overflow)
    m6 = eng.register_model("m6", "d", "o", "pytorch", [])
    ok = record("MLR-090", "Model cap handles overflow gracefully", True, m6 is not None)
    assert ok

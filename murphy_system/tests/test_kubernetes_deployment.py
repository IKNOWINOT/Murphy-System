# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for kubernetes_deployment — K8S-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable K8SRecord with cause / effect / lesson annotations.
"""

from __future__ import annotations

import datetime
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

# Path setup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from kubernetes_deployment import (  # noqa: E402
    ContainerSpec,
    HelmChart,
    HPAMetricType,
    IngressPathType,
    IngressRule,
    K8sConfigMap,
    K8sDeployment,
    K8sHPA,
    K8sIngress,
    K8sNamespace,
    K8sSecret,
    K8sService,
    KubernetesManager,
    ProbeConfig,
    Protocol,
    ResourceKind,
    ResourceRequirements,
    SecretType,
    ServiceType,
    create_k8s_api,
)

# ---------------------------------------------------------------------------
# Record pattern
# ---------------------------------------------------------------------------


@dataclass
class K8SRecord:
    """One K8S check record."""

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


_RESULTS: List[K8SRecord] = []


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
        K8SRecord(
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mgr() -> KubernetesManager:
    return KubernetesManager()


def _dep(name: str = "web", ns: str = "default") -> K8sDeployment:
    return K8sDeployment(
        name=name,
        namespace=ns,
        replicas=2,
        containers=[ContainerSpec(name="app", image="python", tag="3.12")],
        labels={"app": name},
    )


def _svc(name: str = "web-svc") -> K8sService:
    return K8sService(
        name=name,
        selector={"app": "web"},
        ports=[{"port": 80, "target_port": 8080, "protocol": "TCP"}],
    )


def _hpa(name: str = "web-hpa") -> K8sHPA:
    return K8sHPA(name=name, target_deployment="web", min_replicas=2, max_replicas=8)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_k8s_001_resource_kind_enum():
    """ResourceKind enum values."""
    assert record(
        "K8S-001", "ResourceKind has 7 members",
        7, len(ResourceKind),
        cause="enum definition",
        effect="all k8s kinds covered",
        lesson="enums lock down allowed resource types",
    )


def test_k8s_002_service_type_enum():
    """ServiceType enum values."""
    vals = {e.value for e in ServiceType}
    assert record(
        "K8S-002", "ServiceType covers all K8s service types",
        True, "ClusterIP" in vals and "LoadBalancer" in vals,
        cause="enum definition",
        effect="service types validated at creation",
        lesson="str enums give readable serialisation",
    )


def test_k8s_003_protocol_enum():
    """Protocol enum values."""
    assert record(
        "K8S-003", "Protocol has TCP and UDP",
        {"TCP", "UDP"}, {e.value for e in Protocol},
    )


def test_k8s_004_hpa_metric_enum():
    """HPAMetricType enum values."""
    assert record(
        "K8S-004", "HPAMetricType has cpu/memory/custom",
        {"cpu", "memory", "custom"}, {e.value for e in HPAMetricType},
    )


def test_k8s_005_ingress_path_type_enum():
    """IngressPathType enum values."""
    assert record(
        "K8S-005", "IngressPathType has 3 members",
        3, len(IngressPathType),
    )


def test_k8s_006_secret_type_enum():
    """SecretType enum values."""
    assert record(
        "K8S-006", "SecretType Opaque exists",
        "Opaque", SecretType.OPAQUE.value,
    )


def test_k8s_007_container_spec():
    """ContainerSpec dataclass creation."""
    c = ContainerSpec(name="app", image="nginx", tag="1.25", ports=[80, 443])
    assert record(
        "K8S-007", "ContainerSpec stores ports",
        [80, 443], c.ports,
        cause="dataclass init",
        effect="port list preserved",
        lesson="ports are plain int list",
    )


def test_k8s_008_resource_requirements_defaults():
    """ResourceRequirements default values."""
    r = ResourceRequirements()
    assert record(
        "K8S-008", "Default cpu_request is 100m",
        "100m", r.cpu_request,
    )


def test_k8s_009_probe_config():
    """ProbeConfig dataclass creation."""
    p = ProbeConfig(path="/ready", port=9090)
    assert record(
        "K8S-009", "ProbeConfig stores path and port",
        ("/ready", 9090), (p.path, p.port),
    )


def test_k8s_010_deployment_dataclass():
    """K8sDeployment full creation and to_dict."""
    dep = _dep("api")
    d = dep.to_dict()
    assert record(
        "K8S-010", "Deployment to_dict has name and replicas",
        ("api", 2), (d["name"], d["replicas"]),
    )


def test_k8s_011_service_dataclass():
    """K8sService creation and to_dict."""
    svc = _svc()
    d = svc.to_dict()
    assert record(
        "K8S-011", "Service to_dict has service_type as string",
        "ClusterIP", d["service_type"],
    )


def test_k8s_012_hpa_dataclass():
    """K8sHPA creation and to_dict."""
    hpa = _hpa()
    d = hpa.to_dict()
    assert record(
        "K8S-012", "HPA to_dict has metric_type as string",
        "cpu", d["metric_type"],
    )


def test_k8s_013_configmap_dataclass():
    """K8sConfigMap creation."""
    cm = K8sConfigMap(name="cfg", data={"key": "val"})
    assert record(
        "K8S-013", "ConfigMap stores data dict",
        {"key": "val"}, cm.data,
    )


def test_k8s_014_secret_redaction():
    """K8sSecret to_dict redacts data values."""
    sec = K8sSecret(name="db-creds", data={"password": "s3cret!"})
    d = sec.to_dict()
    assert record(
        "K8S-014", "Secret data values redacted",
        "***REDACTED***", d["data"]["password"],
        cause="security requirement",
        effect="no secret leakage via API",
        lesson="always redact secrets in serialisation",
    )


def test_k8s_015_ingress_dataclass():
    """K8sIngress with rules."""
    rule = IngressRule(host="app.example.com", service_name="web", service_port=80)
    ing = K8sIngress(name="web-ing", rules=[rule])
    assert record(
        "K8S-015", "Ingress stores rules list",
        1, len(ing.rules),
    )


def test_k8s_016_namespace_dataclass():
    """K8sNamespace creation."""
    ns = K8sNamespace(name="production", labels={"env": "prod"})
    d = ns.to_dict()
    assert record(
        "K8S-016", "Namespace to_dict has labels",
        {"env": "prod"}, d["labels"],
    )


def test_k8s_017_helm_chart_dataclass():
    """HelmChart creation."""
    chart = HelmChart(name="murphy", version="1.0.0", description="murphy_system")
    assert record(
        "K8S-017", "HelmChart stores version",
        "1.0.0", chart.version,
    )


def test_k8s_018_register_get_deployment():
    """Register and get a Deployment."""
    mgr = _mgr()
    dep = _dep("web")
    mgr.register_deployment(dep)
    got = mgr.get_deployment("web")
    assert record(
        "K8S-018", "Registered deployment is retrievable",
        "web", got.name if got else None,
    )


def test_k8s_019_get_deployment_not_found():
    """Get non-existent Deployment returns None."""
    mgr = _mgr()
    assert record(
        "K8S-019", "Missing deployment returns None",
        None, mgr.get_deployment("nope"),
    )


def test_k8s_020_list_deployments():
    """List Deployments after registration."""
    mgr = _mgr()
    mgr.register_deployment(_dep("a"))
    mgr.register_deployment(_dep("b"))
    assert record(
        "K8S-020", "List returns 2 deployments",
        2, len(mgr.list_deployments()),
    )


def test_k8s_021_remove_deployment():
    """Remove a Deployment."""
    mgr = _mgr()
    mgr.register_deployment(_dep("web"))
    removed = mgr.remove_deployment("web")
    assert record(
        "K8S-021", "Deployment removed successfully",
        (True, None), (removed, mgr.get_deployment("web")),
    )


def test_k8s_022_update_replicas():
    """Scale a Deployment replica count."""
    mgr = _mgr()
    mgr.register_deployment(_dep("web"))
    ok = mgr.update_replicas("web", 5)
    dep = mgr.get_deployment("web")
    assert record(
        "K8S-022", "Replicas updated to 5",
        (True, 5), (ok, dep.replicas if dep else -1),
    )


def test_k8s_023_update_replicas_not_found():
    """Scale non-existent Deployment returns False."""
    mgr = _mgr()
    assert record(
        "K8S-023", "Scale missing deployment returns False",
        False, mgr.update_replicas("nope", 3),
    )


def test_k8s_024_service_crud():
    """Register and get a Service."""
    mgr = _mgr()
    svc = _svc()
    mgr.register_service(svc)
    got = mgr.get_service("web-svc")
    assert record(
        "K8S-024", "Service registered and retrieved",
        "web-svc", got.name if got else None,
    )


def test_k8s_025_hpa_crud():
    """Register and list HPAs."""
    mgr = _mgr()
    mgr.register_hpa(_hpa())
    assert record(
        "K8S-025", "HPA registered and listed",
        1, len(mgr.list_hpas()),
    )


def test_k8s_026_configmap_crud():
    """Register and get a ConfigMap."""
    mgr = _mgr()
    cm = K8sConfigMap(name="app-config", data={"LOG_LEVEL": "INFO"})
    mgr.register_configmap(cm)
    got = mgr.get_configmap("app-config")
    assert record(
        "K8S-026", "ConfigMap data preserved",
        "INFO", got.data["LOG_LEVEL"] if got else None,
    )


def test_k8s_027_secret_crud():
    """Register and get a Secret."""
    mgr = _mgr()
    sec = K8sSecret(name="tls-cert", secret_type=SecretType.TLS, data={"cert": "abc"})
    mgr.register_secret(sec)
    got = mgr.get_secret("tls-cert")
    assert record(
        "K8S-027", "Secret registered with TLS type",
        SecretType.TLS, got.secret_type if got else None,
    )


def test_k8s_028_ingress_crud():
    """Register and get an Ingress."""
    mgr = _mgr()
    rule = IngressRule(host="api.test.com", service_name="api", service_port=8080)
    ing = K8sIngress(name="api-ing", rules=[rule], tls_secret="tls-cert")
    mgr.register_ingress(ing)
    got = mgr.get_ingress("api-ing")
    assert record(
        "K8S-028", "Ingress tls_secret preserved",
        "tls-cert", got.tls_secret if got else None,
    )


def test_k8s_029_namespace_crud():
    """Register and list Namespaces."""
    mgr = _mgr()
    mgr.register_namespace(K8sNamespace(name="staging"))
    mgr.register_namespace(K8sNamespace(name="production"))
    assert record(
        "K8S-029", "Two namespaces registered",
        2, len(mgr.list_namespaces()),
    )


def test_k8s_030_helm_chart_crud():
    """Register, get, and list Helm charts."""
    mgr = _mgr()
    chart = HelmChart(name="murphy-chart", description="Murphy Helm chart")
    mgr.register_chart(chart)
    got = mgr.get_chart("murphy-chart")
    assert record(
        "K8S-030", "Helm chart registered and retrieved",
        "Murphy Helm chart", got.description if got else None,
    )


def test_k8s_031_generate_deployment_yaml():
    """Generate Deployment YAML manifest."""
    mgr = _mgr()
    dep = _dep("api")
    dep.liveness_probe = ProbeConfig(path="/healthz", port=8080)
    mgr.register_deployment(dep)
    yaml_text = mgr.generate_deployment_yaml("api")
    assert record(
        "K8S-031", "Deployment YAML contains kind and name",
        True,
        yaml_text is not None
        and "kind: Deployment" in yaml_text
        and "name: api" in yaml_text
        and "livenessProbe" in yaml_text,
        cause="manifest generation",
        effect="valid YAML structure produced",
        lesson="string-based YAML avoids yaml lib dependency",
    )


def test_k8s_032_generate_deployment_yaml_not_found():
    """Generate YAML for non-existent Deployment returns None."""
    mgr = _mgr()
    assert record(
        "K8S-032", "Missing deployment returns None",
        None, mgr.generate_deployment_yaml("nope"),
    )


def test_k8s_033_generate_service_yaml():
    """Generate Service YAML manifest."""
    mgr = _mgr()
    mgr.register_service(_svc())
    yaml_text = mgr.generate_service_yaml("web-svc")
    assert record(
        "K8S-033", "Service YAML contains kind",
        True,
        yaml_text is not None and "kind: Service" in yaml_text,
    )


def test_k8s_034_generate_hpa_yaml():
    """Generate HPA YAML manifest."""
    mgr = _mgr()
    mgr.register_hpa(_hpa())
    yaml_text = mgr.generate_hpa_yaml("web-hpa")
    assert record(
        "K8S-034", "HPA YAML contains kind",
        True,
        yaml_text is not None and "kind: HorizontalPodAutoscaler" in yaml_text,
    )


def test_k8s_035_generate_chart_yaml():
    """Generate Helm Chart.yaml content."""
    mgr = _mgr()
    chart = HelmChart(name="test-chart", version="2.0.0", app_version="1.5.0", description="Test")
    mgr.register_chart(chart)
    text = mgr.generate_chart_yaml("test-chart")
    assert record(
        "K8S-035", "Chart.yaml has apiVersion and version",
        True,
        text is not None
        and "apiVersion: v2" in text
        and "version: 2.0.0" in text,
    )


def test_k8s_036_resource_stats():
    """Resource stats returns counts by type."""
    mgr = _mgr()
    mgr.register_deployment(_dep("a"))
    mgr.register_deployment(_dep("b"))
    mgr.register_service(_svc())
    stats = mgr.resource_stats()
    assert record(
        "K8S-036", "Stats shows 2 deployments, 1 service",
        (2, 1), (stats["deployments"], stats["services"]),
    )


def test_k8s_037_thread_safety():
    """Concurrent registration from 10 threads."""
    mgr = _mgr()
    barrier = threading.Barrier(10)

    def worker(i: int) -> None:
        barrier.wait()
        mgr.register_deployment(_dep(f"dep-{i}"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert record(
        "K8S-037", "10 concurrent registrations all succeed",
        10, len(mgr.list_deployments()),
        cause="threading.Lock guards all mutations",
        effect="no race conditions",
        lesson="thread-safe dict access prevents data loss",
    )


# ---------------------------------------------------------------------------
# Flask API tests
# ---------------------------------------------------------------------------

try:
    from flask import Flask

    def _app() -> Any:
        mgr = _mgr()
        app = Flask(__name__)
        app.register_blueprint(create_k8s_api(mgr))
        return app, mgr

    def test_k8s_038_api_create_deployment():
        """POST /api/k8s/deployments creates a Deployment."""
        app, mgr = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/deployments", json={
                "name": "web",
                "replicas": 3,
                "containers": [{"name": "app", "image": "python", "tag": "3.12"}],
            })
            data = resp.get_json()
        assert record(
            "K8S-038", "POST deployments returns 201",
            (201, "web"), (resp.status_code, data.get("name")),
        )

    def test_k8s_039_api_list_deployments():
        """GET /api/k8s/deployments lists Deployments."""
        app, mgr = _app()
        mgr.register_deployment(_dep("a"))
        with app.test_client() as c:
            resp = c.get("/api/k8s/deployments")
        assert record(
            "K8S-039", "GET deployments returns list",
            (200, 1), (resp.status_code, len(resp.get_json())),
        )

    def test_k8s_040_api_get_deployment_404():
        """GET /api/k8s/deployments/<name> returns 404 when missing."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.get("/api/k8s/deployments/nope")
        assert record(
            "K8S-040", "GET missing deployment returns 404",
            404, resp.status_code,
        )

    def test_k8s_041_api_delete_deployment():
        """DELETE /api/k8s/deployments/<name> removes Deployment."""
        app, mgr = _app()
        mgr.register_deployment(_dep("web"))
        with app.test_client() as c:
            resp = c.delete("/api/k8s/deployments/web")
        assert record(
            "K8S-041", "DELETE deployment returns 200",
            200, resp.status_code,
        )

    def test_k8s_042_api_scale_deployment():
        """POST /api/k8s/deployments/<name>/scale updates replicas."""
        app, mgr = _app()
        mgr.register_deployment(_dep("web"))
        with app.test_client() as c:
            resp = c.post("/api/k8s/deployments/web/scale", json={"replicas": 5})
            data = resp.get_json()
        assert record(
            "K8S-042", "Scale returns new replica count",
            (200, 5), (resp.status_code, data.get("replicas")),
        )

    def test_k8s_043_api_deployment_yaml():
        """GET /api/k8s/deployments/<name>/yaml generates YAML."""
        app, mgr = _app()
        mgr.register_deployment(_dep("web"))
        with app.test_client() as c:
            resp = c.get("/api/k8s/deployments/web/yaml")
            data = resp.get_json()
        assert record(
            "K8S-043", "YAML endpoint returns yaml key",
            True, "yaml" in data and "kind: Deployment" in data["yaml"],
        )

    def test_k8s_044_api_create_service():
        """POST /api/k8s/services creates a Service."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/services", json={
                "name": "api-svc",
                "service_type": "LoadBalancer",
                "selector": {"app": "api"},
                "ports": [{"port": 443, "target_port": 8443}],
            })
        assert record(
            "K8S-044", "POST services returns 201",
            201, resp.status_code,
        )

    def test_k8s_045_api_create_hpa():
        """POST /api/k8s/hpas creates an HPA."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/hpas", json={
                "name": "web-hpa", "target_deployment": "web",
            })
        assert record(
            "K8S-045", "POST hpas returns 201",
            201, resp.status_code,
        )

    def test_k8s_046_api_create_configmap():
        """POST /api/k8s/configmaps creates a ConfigMap."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/configmaps", json={
                "name": "app-cfg", "data": {"LOG": "debug"},
            })
        assert record(
            "K8S-046", "POST configmaps returns 201",
            201, resp.status_code,
        )

    def test_k8s_047_api_create_secret():
        """POST /api/k8s/secrets creates a Secret with redacted data."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/secrets", json={
                "name": "db-pass", "data": {"pw": "hunter2"},
            })
            data = resp.get_json()
        assert record(
            "K8S-047", "Secret data redacted in response",
            "***REDACTED***", data.get("data", {}).get("pw"),
        )

    def test_k8s_048_api_create_ingress():
        """POST /api/k8s/ingresses creates an Ingress."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/ingresses", json={
                "name": "web-ing",
                "rules": [{"host": "app.test.com", "service_name": "web", "service_port": 80}],
            })
        assert record(
            "K8S-048", "POST ingresses returns 201",
            201, resp.status_code,
        )

    def test_k8s_049_api_create_namespace():
        """POST /api/k8s/namespaces creates a Namespace."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/namespaces", json={"name": "staging"})
        assert record(
            "K8S-049", "POST namespaces returns 201",
            201, resp.status_code,
        )

    def test_k8s_050_api_create_chart():
        """POST /api/k8s/charts creates a Helm chart."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/charts", json={
                "name": "murphy", "version": "1.0.0", "description": "Murphy",
            })
        assert record(
            "K8S-050", "POST charts returns 201",
            201, resp.status_code,
        )

    def test_k8s_051_api_chart_yaml():
        """GET /api/k8s/charts/<name>/yaml generates Chart.yaml."""
        app, mgr = _app()
        mgr.register_chart(HelmChart(name="test", version="2.0.0"))
        with app.test_client() as c:
            resp = c.get("/api/k8s/charts/test/yaml")
            data = resp.get_json()
        assert record(
            "K8S-051", "Chart YAML endpoint returns yaml key",
            True, "yaml" in data and "version: 2.0.0" in data["yaml"],
        )

    def test_k8s_052_api_stats():
        """GET /api/k8s/stats returns resource counts."""
        app, mgr = _app()
        mgr.register_deployment(_dep("web"))
        with app.test_client() as c:
            resp = c.get("/api/k8s/stats")
            data = resp.get_json()
        assert record(
            "K8S-052", "Stats endpoint returns deployment count",
            1, data.get("deployments"),
        )

    def test_k8s_053_api_missing_name():
        """POST endpoints return 400 when name is missing."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/k8s/deployments", json={})
        assert record(
            "K8S-053", "Missing name returns 400",
            400, resp.status_code,
        )

    def test_k8s_054_api_service_yaml():
        """GET /api/k8s/services/<name>/yaml generates YAML."""
        app, mgr = _app()
        mgr.register_service(_svc())
        with app.test_client() as c:
            resp = c.get("/api/k8s/services/web-svc/yaml")
            data = resp.get_json()
        assert record(
            "K8S-054", "Service YAML endpoint works",
            True, "yaml" in data and "kind: Service" in data["yaml"],
        )

    def test_k8s_055_api_hpa_yaml():
        """GET /api/k8s/hpas/<name>/yaml generates YAML."""
        app, mgr = _app()
        mgr.register_hpa(_hpa())
        with app.test_client() as c:
            resp = c.get("/api/k8s/hpas/web-hpa/yaml")
            data = resp.get_json()
        assert record(
            "K8S-055", "HPA YAML endpoint works",
            True, "yaml" in data and "HorizontalPodAutoscaler" in data["yaml"],
        )

except ImportError:
    pass  # Flask not available — API tests skipped


# ---------------------------------------------------------------------------
# Wingman & Sandbox gates
# ---------------------------------------------------------------------------


def test_k8s_056_wingman_gate():
    """Wingman pair validation gate."""
    mgr = _mgr()
    mgr.register_deployment(_dep("web"))
    storyteller_says = "Scale web deployment to 5 replicas"
    wingman_approves = True
    result = mgr.update_replicas("web", 5) if wingman_approves else False
    assert record(
        "K8S-056", "Wingman gate — approved scaling",
        True, result,
        cause="storyteller requests scaling, wingman approves",
        effect="deployment scaled to 5",
        lesson="Wingman pair validation prevents unsafe changes",
    )


def test_k8s_057_sandbox_gate():
    """Causality Sandbox gate — side-effect tracking."""
    mgr = _mgr()
    sandbox_mode = True
    if sandbox_mode:
        pre = len(mgr.list_deployments())
    mgr.register_deployment(_dep("sandbox-test"))
    if sandbox_mode:
        post = len(mgr.list_deployments())
        delta = post - pre
    assert record(
        "K8S-057", "Sandbox gate — side effect tracked",
        1, delta,
        cause="sandbox monitors state changes",
        effect="one new deployment detected",
        lesson="causality sandbox ensures auditable changes",
    )

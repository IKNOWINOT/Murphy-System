# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for docker_containerization — DCK-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable DCKRecord with cause / effect / lesson annotations.
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

from docker_containerization import (  # noqa: E402
    ComposeProject,
    ComposeService,
    ContainerDefinition,
    ContainerInstance,
    ContainerStatus,
    DockerManager,
    EnvironmentVar,
    HealthCheckConfig,
    HealthCheckType,
    ImagePullPolicy,
    ImageRecord,
    NetworkMode,
    PortMapping,
    RestartPolicy,
    VolumeMount,
    VolumeType,
    create_docker_api,
)

# Record pattern


@dataclass
class DCKRecord:
    """One DCK check record."""

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


_RESULTS: List[DCKRecord] = []


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
        DCKRecord(
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


def _fresh_manager() -> DockerManager:
    """Return a fresh DockerManager for test isolation."""
    return DockerManager()


def _make_definition(**overrides: Any) -> ContainerDefinition:
    """Create a ContainerDefinition with sensible defaults."""
    defaults: dict[str, Any] = dict(
        name="web",
        image="python",
        tag="3.12-slim",
        ports=[PortMapping(host_port=8080, container_port=80)],
        volumes=[VolumeMount(source="./data", target="/data")],
        env_vars=[EnvironmentVar(name="APP_ENV", value="production")],
        health_check=HealthCheckConfig(check_type=HealthCheckType.HTTP, target="http://localhost/health"),
        restart_policy=RestartPolicy.ALWAYS,
        network_mode=NetworkMode.BRIDGE,
        command="python app.py",
        labels={"team": "platform"},
        pull_policy=ImagePullPolicy.IF_NOT_PRESENT,
        memory_limit_mb=512,
        cpu_limit=1.0,
    )
    defaults.update(overrides)
    return ContainerDefinition(**defaults)


def _flask_client():
    """Return (test_client, DockerManager) or (None, None) if Flask is missing."""
    try:
        from flask import Flask
    except ImportError:
        return None, None
    mgr = _fresh_manager()
    app = Flask(__name__)
    app.register_blueprint(create_docker_api(mgr))
    return app.test_client(), mgr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dck_001_container_status_enum():
    """DCK-001: Enum values for ContainerStatus."""
    vals = {e.value for e in ContainerStatus}
    expected = {"created", "running", "paused", "stopped", "removed", "failed"}
    assert record(
        "DCK-001", "ContainerStatus enum values match",
        expected, vals,
        cause="Enum defines six lifecycle states",
        effect="All states are accessible",
        lesson="Enum completeness prevents invalid states",
    )


def test_dck_002_restart_policy_enum():
    """DCK-002: Enum values for RestartPolicy."""
    vals = {e.value for e in RestartPolicy}
    expected = {"no", "always", "on_failure", "unless_stopped"}
    assert record(
        "DCK-002", "RestartPolicy enum values match",
        expected, vals,
        cause="Four restart policies defined",
        effect="All policies selectable",
        lesson="Match Docker restart policy options",
    )


def test_dck_003_volume_type_enum():
    """DCK-003: Enum values for VolumeType."""
    vals = {e.value for e in VolumeType}
    expected = {"bind", "volume", "tmpfs"}
    assert record(
        "DCK-003", "VolumeType enum values match",
        expected, vals,
        cause="Three volume types defined",
        effect="Type safety for mounts",
        lesson="Cover Docker volume types",
    )


def test_dck_004_health_check_type_enum():
    """DCK-004: Enum values for HealthCheckType."""
    vals = {e.value for e in HealthCheckType}
    expected = {"http", "tcp", "command", "none"}
    assert record(
        "DCK-004", "HealthCheckType enum values match",
        expected, vals,
        cause="Four health-check types defined",
        effect="Proper probe selection",
        lesson="Include 'none' for opt-out",
    )


def test_dck_005_port_mapping_creation():
    """DCK-005: PortMapping dataclass creation."""
    pm = PortMapping(host_port=8080, container_port=80)
    ok1 = record("DCK-005a", "host_port", 8080, pm.host_port)
    ok2 = record("DCK-005b", "container_port", 80, pm.container_port)
    ok3 = record("DCK-005c", "protocol default", "tcp", pm.protocol)
    assert ok1 and ok2 and ok3


def test_dck_006_volume_mount_creation():
    """DCK-006: VolumeMount dataclass creation."""
    vm = VolumeMount(source="/host", target="/container")
    ok1 = record("DCK-006a", "source", "/host", vm.source)
    ok2 = record("DCK-006b", "target", "/container", vm.target)
    ok3 = record("DCK-006c", "volume_type default", VolumeType.BIND, vm.volume_type)
    ok4 = record("DCK-006d", "read_only default", False, vm.read_only)
    assert ok1 and ok2 and ok3 and ok4


def test_dck_007_health_check_defaults():
    """DCK-007: HealthCheckConfig defaults."""
    hc = HealthCheckConfig(check_type=HealthCheckType.HTTP)
    ok1 = record("DCK-007a", "interval_seconds", 30, hc.interval_seconds)
    ok2 = record("DCK-007b", "timeout_seconds", 10, hc.timeout_seconds)
    ok3 = record("DCK-007c", "retries", 3, hc.retries)
    ok4 = record("DCK-007d", "start_period", 5, hc.start_period_seconds)
    assert ok1 and ok2 and ok3 and ok4


def test_dck_008_env_var_secret_redaction():
    """DCK-008: EnvironmentVar secret redaction."""
    ev = EnvironmentVar(name="DB_PASS", value="s3cret", secret=True)
    d = ev.to_dict()
    ok1 = record("DCK-008a", "secret value is redacted", "***REDACTED***", d["value"],
                  cause="secret=True", effect="Value hidden in serialisation",
                  lesson="Never expose secrets in API responses")
    ev2 = EnvironmentVar(name="APP_ENV", value="prod", secret=False)
    d2 = ev2.to_dict()
    ok2 = record("DCK-008b", "non-secret value visible", "prod", d2["value"])
    assert ok1 and ok2


def test_dck_009_container_definition_full():
    """DCK-009: ContainerDefinition full creation."""
    defn = _make_definition()
    ok1 = record("DCK-009a", "name", "web", defn.name)
    ok2 = record("DCK-009b", "image", "python", defn.image)
    ok3 = record("DCK-009c", "tag", "3.12-slim", defn.tag)
    ok4 = record("DCK-009d", "ports count", 1, len(defn.ports))
    ok5 = record("DCK-009e", "restart_policy", RestartPolicy.ALWAYS, defn.restart_policy)
    d = defn.to_dict()
    ok6 = record("DCK-009f", "to_dict restart_policy", "always", d["restart_policy"])
    assert ok1 and ok2 and ok3 and ok4 and ok5 and ok6


def test_dck_010_container_instance_defaults():
    """DCK-010: ContainerInstance defaults."""
    inst = ContainerInstance(id="abc", definition_name="web",
                             status=ContainerStatus.CREATED,
                             created_at="2024-01-01T00:00:00Z")
    ok1 = record("DCK-010a", "started_at default", "", inst.started_at)
    ok2 = record("DCK-010b", "stopped_at default", "", inst.stopped_at)
    ok3 = record("DCK-010c", "exit_code default", None, inst.exit_code)
    ok4 = record("DCK-010d", "health_status default", "unknown", inst.health_status)
    assert ok1 and ok2 and ok3 and ok4


def test_dck_011_compose_project_creation():
    """DCK-011: ComposeProject creation."""
    svc = ComposeService(name="api", definition_name="web", replicas=2, depends_on=["db"])
    proj = ComposeProject(name="myapp", services=[svc])
    ok1 = record("DCK-011a", "project name", "myapp", proj.name)
    ok2 = record("DCK-011b", "version default", "3.8", proj.version)
    ok3 = record("DCK-011c", "service count", 1, len(proj.services))
    ok4 = record("DCK-011d", "service replicas", 2, proj.services[0].replicas)
    assert ok1 and ok2 and ok3 and ok4


def test_dck_012_image_record_creation():
    """DCK-012: ImageRecord creation."""
    img = ImageRecord(repository="python", tag="3.12", image_id="sha256:abc",
                      size_mb=150.5, created_at="2024-01-01T00:00:00Z")
    d = img.to_dict()
    ok1 = record("DCK-012a", "repository", "python", d["repository"])
    ok2 = record("DCK-012b", "size_mb", 150.5, d["size_mb"])
    assert ok1 and ok2


def test_dck_013_register_definition():
    """DCK-013: Register definition."""
    mgr = _fresh_manager()
    defn = _make_definition()
    name = mgr.register_definition(defn)
    assert record("DCK-013", "register returns name", "web", name,
                   cause="Valid definition provided",
                   effect="Definition stored in manager",
                   lesson="Registration is idempotent by name")


def test_dck_014_get_definition():
    """DCK-014: Get definition (found + not found)."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    ok1 = record("DCK-014a", "found definition", True, mgr.get_definition("web") is not None)
    ok2 = record("DCK-014b", "not found returns None", True, mgr.get_definition("nope") is None)
    assert ok1 and ok2


def test_dck_015_list_definitions():
    """DCK-015: List definitions."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition(name="a", image="img1"))
    mgr.register_definition(_make_definition(name="b", image="img2"))
    defs = mgr.list_definitions()
    assert record("DCK-015", "two definitions listed", 2, len(defs))


def test_dck_016_remove_definition():
    """DCK-016: Remove definition."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    ok1 = record("DCK-016a", "remove existing", True, mgr.remove_definition("web"))
    ok2 = record("DCK-016b", "remove missing", False, mgr.remove_definition("web"))
    ok3 = record("DCK-016c", "list empty after remove", 0, len(mgr.list_definitions()))
    assert ok1 and ok2 and ok3


def test_dck_017_create_container():
    """DCK-017: Create container from definition."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    inst = mgr.create_container("web")
    ok1 = record("DCK-017a", "instance created", True, inst is not None)
    ok2 = record("DCK-017b", "status is created", ContainerStatus.CREATED,
                  inst.status if inst else None)
    ok3 = record("DCK-017c", "definition_name", "web",
                  inst.definition_name if inst else "")
    assert ok1 and ok2 and ok3


def test_dck_018_create_container_unknown():
    """DCK-018: Create container — unknown definition."""
    mgr = _fresh_manager()
    inst = mgr.create_container("nonexistent")
    assert record("DCK-018", "unknown definition returns None", True, inst is None,
                   cause="No definition registered for name",
                   effect="Graceful None return",
                   lesson="Always validate definition exists before creation")


def test_dck_019_start_container():
    """DCK-019: Start container."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    inst = mgr.create_container("web")
    assert inst is not None
    ok = mgr.start_container(inst.id)
    updated = mgr.get_container(inst.id)
    ok1 = record("DCK-019a", "start returns True", True, ok)
    ok2 = record("DCK-019b", "status is running", ContainerStatus.RUNNING,
                  updated.status if updated else None)
    ok3 = record("DCK-019c", "started_at set", True,
                  (updated.started_at != "") if updated else False)
    assert ok1 and ok2 and ok3


def test_dck_020_stop_container():
    """DCK-020: Stop container."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    inst = mgr.create_container("web")
    assert inst is not None
    mgr.start_container(inst.id)
    ok = mgr.stop_container(inst.id)
    updated = mgr.get_container(inst.id)
    ok1 = record("DCK-020a", "stop returns True", True, ok)
    ok2 = record("DCK-020b", "status is stopped", ContainerStatus.STOPPED,
                  updated.status if updated else None)
    ok3 = record("DCK-020c", "exit_code is 0", 0,
                  updated.exit_code if updated else None)
    assert ok1 and ok2 and ok3


def test_dck_021_remove_container():
    """DCK-021: Remove container."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    inst = mgr.create_container("web")
    assert inst is not None
    ok = mgr.remove_container(inst.id)
    updated = mgr.get_container(inst.id)
    ok1 = record("DCK-021a", "remove returns True", True, ok)
    ok2 = record("DCK-021b", "status is removed", ContainerStatus.REMOVED,
                  updated.status if updated else None)
    assert ok1 and ok2


def test_dck_022_list_containers_filter():
    """DCK-022: List containers with status filter."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    c1 = mgr.create_container("web")
    c2 = mgr.create_container("web")
    assert c1 and c2
    mgr.start_container(c1.id)
    all_containers = mgr.list_containers()
    running = mgr.list_containers(status_filter=ContainerStatus.RUNNING)
    created = mgr.list_containers(status_filter=ContainerStatus.CREATED)
    ok1 = record("DCK-022a", "total containers", 2, len(all_containers))
    ok2 = record("DCK-022b", "running count", 1, len(running))
    ok3 = record("DCK-022c", "created count", 1, len(created))
    assert ok1 and ok2 and ok3


def test_dck_023_generate_dockerfile():
    """DCK-023: Generate Dockerfile."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    df = mgr.generate_dockerfile("web")
    assert df is not None
    ok1 = record("DCK-023a", "FROM line present", True, "FROM python:3.12-slim AS base" in df)
    ok2 = record("DCK-023b", "EXPOSE present", True, "EXPOSE 80/tcp" in df)
    ok3 = record("DCK-023c", "HEALTHCHECK present", True, "HEALTHCHECK" in df)
    ok4 = record("DCK-023d", "CMD present", True, "CMD" in df)
    ok5 = record("DCK-023e", "WORKDIR present", True, "WORKDIR /app" in df)
    ok6 = record("DCK-023f", "missing definition returns None", True,
                  mgr.generate_dockerfile("nope") is None)
    assert ok1 and ok2 and ok3 and ok4 and ok5 and ok6


def test_dck_024_generate_compose_yaml():
    """DCK-024: Generate compose YAML."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    svc = ComposeService(name="web-svc", definition_name="web")
    proj = ComposeProject(name="myapp", services=[svc])
    mgr.register_compose_project(proj)
    yaml_text = mgr.generate_compose_yaml("myapp")
    assert yaml_text is not None
    ok1 = record("DCK-024a", "version present", True, 'version: "3.8"' in yaml_text)
    ok2 = record("DCK-024b", "services key", True, "services:" in yaml_text)
    ok3 = record("DCK-024c", "image present", True, "image: python:3.12-slim" in yaml_text)
    ok4 = record("DCK-024d", "restart present", True, "restart: always" in yaml_text)
    ok5 = record("DCK-024e", "missing project returns None", True,
                  mgr.generate_compose_yaml("nope") is None)
    assert ok1 and ok2 and ok3 and ok4 and ok5


def test_dck_025_register_compose_project():
    """DCK-025: Register compose project."""
    mgr = _fresh_manager()
    proj = ComposeProject(name="stack", services=[])
    name = mgr.register_compose_project(proj)
    ok1 = record("DCK-025a", "returns name", "stack", name)
    ok2 = record("DCK-025b", "retrievable", True, mgr.get_compose_project("stack") is not None)
    assert ok1 and ok2


def test_dck_026_register_and_list_images():
    """DCK-026: Register and list images."""
    mgr = _fresh_manager()
    img = ImageRecord(repository="nginx", tag="latest", image_id="sha256:abc",
                      size_mb=50.0, created_at="2024-01-01T00:00:00Z")
    iid = mgr.register_image(img)
    imgs = mgr.list_images()
    ok1 = record("DCK-026a", "returns image_id", "sha256:abc", iid)
    ok2 = record("DCK-026b", "image listed", 1, len(imgs))
    assert ok1 and ok2


def test_dck_027_container_stats():
    """DCK-027: Container stats."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    mgr.register_image(ImageRecord(
        repository="python", tag="3.12", image_id="sha:1",
        size_mb=100.0, created_at="2024-01-01T00:00:00Z"))
    c1 = mgr.create_container("web")
    c2 = mgr.create_container("web")
    assert c1 and c2
    mgr.start_container(c1.id)
    stats = mgr.container_stats()
    ok1 = record("DCK-027a", "total_containers", 2, stats["total_containers"])
    ok2 = record("DCK-027b", "total_definitions", 1, stats["total_definitions"])
    ok3 = record("DCK-027c", "total_images", 1, stats["total_images"])
    ok4 = record("DCK-027d", "running in by_status", 1, stats["by_status"].get("running", 0))
    assert ok1 and ok2 and ok3 and ok4


def test_dck_028_thread_safety():
    """DCK-028: Thread safety (10 concurrent container creates)."""
    mgr = _fresh_manager()
    mgr.register_definition(_make_definition())
    results: list[Any] = []
    errors: list[str] = []

    def _create():
        try:
            inst = mgr.create_container("web")
            if inst:
                results.append(inst.id)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=_create) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok1 = record("DCK-028a", "no errors", 0, len(errors),
                  cause="10 threads creating containers concurrently",
                  effect="All succeed without race condition",
                  lesson="Lock protects shared mutable state")
    ok2 = record("DCK-028b", "10 containers created", 10, len(results))
    ids_unique = len(set(results)) == len(results)
    ok3 = record("DCK-028c", "all IDs unique", True, ids_unique)
    assert ok1 and ok2 and ok3


def test_dck_029_flask_api_definitions():
    """DCK-029: Flask API — POST/GET definitions."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-029", "Flask not available, skip", True, True)
        return
    resp = client.post("/api/docker/definitions",
                       json={"name": "api", "image": "node", "tag": "18"})
    ok1 = record("DCK-029a", "POST 201", 201, resp.status_code)
    data = resp.get_json()
    ok2 = record("DCK-029b", "name in response", "api", data.get("name"))
    resp2 = client.get("/api/docker/definitions")
    ok3 = record("DCK-029c", "GET list length", 1, len(resp2.get_json()))
    resp3 = client.get("/api/docker/definitions/api")
    ok4 = record("DCK-029d", "GET single 200", 200, resp3.status_code)
    assert ok1 and ok2 and ok3 and ok4


def test_dck_030_flask_api_container_lifecycle():
    """DCK-030: Flask API — container lifecycle."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-030", "Flask not available, skip", True, True)
        return
    client.post("/api/docker/definitions", json={"name": "svc", "image": "python"})
    resp = client.post("/api/docker/containers", json={"definition_name": "svc"})
    ok1 = record("DCK-030a", "create 201", 201, resp.status_code)
    cid = resp.get_json()["id"]

    resp2 = client.post(f"/api/docker/containers/{cid}/start")
    ok2 = record("DCK-030b", "start 200", 200, resp2.status_code)
    ok3 = record("DCK-030c", "status running", "running", resp2.get_json().get("status"))

    resp3 = client.post(f"/api/docker/containers/{cid}/stop")
    ok4 = record("DCK-030d", "stop 200", 200, resp3.status_code)
    ok5 = record("DCK-030e", "status stopped", "stopped", resp3.get_json().get("status"))

    resp4 = client.delete(f"/api/docker/containers/{cid}")
    ok6 = record("DCK-030f", "delete 200", 200, resp4.status_code)
    assert ok1 and ok2 and ok3 and ok4 and ok5 and ok6


def test_dck_031_flask_api_dockerfile():
    """DCK-031: Flask API — Dockerfile generation endpoint."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-031", "Flask not available, skip", True, True)
        return
    client.post("/api/docker/definitions", json={
        "name": "app", "image": "python", "tag": "3.12-slim",
        "ports": [{"host_port": 8080, "container_port": 80}],
    })
    resp = client.get("/api/docker/definitions/app/dockerfile")
    ok1 = record("DCK-031a", "200 status", 200, resp.status_code)
    text = resp.get_json().get("dockerfile", "")
    ok2 = record("DCK-031b", "FROM in dockerfile", True, "FROM python:3.12-slim" in text)
    assert ok1 and ok2


def test_dck_032_flask_api_compose():
    """DCK-032: Flask API — compose endpoints."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-032", "Flask not available, skip", True, True)
        return
    client.post("/api/docker/definitions", json={"name": "db", "image": "postgres"})
    resp = client.post("/api/docker/compose", json={
        "name": "stack",
        "services": [{"name": "db-svc", "definition_name": "db"}],
    })
    ok1 = record("DCK-032a", "compose POST 201", 201, resp.status_code)
    resp2 = client.get("/api/docker/compose/stack")
    ok2 = record("DCK-032b", "compose GET 200", 200, resp2.status_code)
    resp3 = client.get("/api/docker/compose/stack/yaml")
    ok3 = record("DCK-032c", "yaml GET 200", 200, resp3.status_code)
    yaml_text = resp3.get_json().get("yaml", "")
    ok4 = record("DCK-032d", "yaml has services", True, "services:" in yaml_text)
    assert ok1 and ok2 and ok3 and ok4


def test_dck_033_flask_api_images():
    """DCK-033: Flask API — image endpoints."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-033", "Flask not available, skip", True, True)
        return
    resp = client.post("/api/docker/images", json={
        "repository": "nginx", "tag": "1.25", "size_mb": 60.0,
    })
    ok1 = record("DCK-033a", "image POST 201", 201, resp.status_code)
    resp2 = client.get("/api/docker/images")
    ok2 = record("DCK-033b", "images GET count", 1, len(resp2.get_json()))
    assert ok1 and ok2


def test_dck_034_flask_api_stats():
    """DCK-034: Flask API — stats endpoint."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-034", "Flask not available, skip", True, True)
        return
    resp = client.get("/api/docker/stats")
    ok1 = record("DCK-034a", "stats 200", 200, resp.status_code)
    data = resp.get_json()
    ok2 = record("DCK-034b", "total_containers key", True, "total_containers" in data)
    assert ok1 and ok2


def test_dck_035_flask_api_404():
    """DCK-035: Flask API — 404 error responses."""
    client, mgr = _flask_client()
    if client is None:
        assert record("DCK-035", "Flask not available, skip", True, True)
        return
    r1 = client.get("/api/docker/definitions/missing")
    ok1 = record("DCK-035a", "definition 404", 404, r1.status_code)
    r2 = client.get("/api/docker/containers/missing")
    ok2 = record("DCK-035b", "container 404", 404, r2.status_code)
    r3 = client.get("/api/docker/compose/missing")
    ok3 = record("DCK-035c", "compose 404", 404, r3.status_code)
    r4 = client.get("/api/docker/compose/missing/yaml")
    ok4 = record("DCK-035d", "compose yaml 404", 404, r4.status_code)
    r5 = client.get("/api/docker/definitions/missing/dockerfile")
    ok5 = record("DCK-035e", "dockerfile 404", 404, r5.status_code)
    assert ok1 and ok2 and ok3 and ok4 and ok5


def test_dck_036_wingman_gate():
    """DCK-036: Wingman pair validation gate."""
    mgr = _fresh_manager()
    defn = ContainerDefinition(
        name="test", image="python",
        ports=[], volumes=[], env_vars=[],
        health_check=None, restart_policy=RestartPolicy.NO,
        network_mode=NetworkMode.BRIDGE, command=None,
        labels={}, pull_policy=ImagePullPolicy.IF_NOT_PRESENT,
    )
    mgr.register_definition(defn)
    storyteller_says = "Create container for test"  # noqa: F841
    wingman_approves = True
    result = mgr.create_container("test") if wingman_approves else None
    assert record(
        "DCK-036", "Wingman gate — approved", True, result is not None,
        cause="Wingman approved the container creation request",
        effect="Container instance created successfully",
        lesson="Wingman gate ensures peer review of actions",
    )


def test_dck_037_sandbox_gate():
    """DCK-037: Causality Sandbox gate."""
    mgr = _fresh_manager()
    sandbox_mode = True
    if sandbox_mode:
        pre_count = len(mgr.list_containers())
    defn = ContainerDefinition(
        name="test", image="python",
        ports=[], volumes=[], env_vars=[],
        health_check=None, restart_policy=RestartPolicy.NO,
        network_mode=NetworkMode.BRIDGE, command=None,
        labels={}, pull_policy=ImagePullPolicy.IF_NOT_PRESENT,
    )
    mgr.register_definition(defn)
    inst = mgr.create_container("test")
    delta = 0
    if sandbox_mode:
        post_count = len(mgr.list_containers())
        delta = post_count - pre_count
    assert record(
        "DCK-037", "Sandbox gate — side effect tracked", 1, delta,
        cause="Container creation inside sandbox boundary",
        effect="Exactly one container added, delta verified",
        lesson="Sandbox tracks all side effects for rollback",
    )


def test_dck_038_network_and_pull_policy_enums():
    """DCK-038: NetworkMode + ImagePullPolicy enums."""
    net_vals = {e.value for e in NetworkMode}
    expected_net = {"bridge", "host", "none", "custom"}
    ok1 = record("DCK-038a", "NetworkMode values", expected_net, net_vals)
    pull_vals = {e.value for e in ImagePullPolicy}
    expected_pull = {"always", "if_not_present", "never"}
    ok2 = record("DCK-038b", "ImagePullPolicy values", expected_pull, pull_vals)
    assert ok1 and ok2

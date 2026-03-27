# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Docker Containerization Manager — DCK-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Programmatic Docker container management for the Murphy System — container
definitions, lifecycle control, Dockerfile generation, Compose project
management, image tracking, and health-check configuration.

Classes: ContainerStatus/ImagePullPolicy/RestartPolicy/VolumeType/
HealthCheckType/NetworkMode (enums), PortMapping/VolumeMount/HealthCheckConfig/
EnvironmentVar/ContainerDefinition/ContainerInstance/ComposeService/
ComposeProject/ImageRecord (dataclasses), DockerManager (thread-safe manager).
``create_docker_api(manager)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state guarded by threading.Lock; instance/image lists
bounded via capped_append (CWE-770); secret env vars redacted in serialisation.
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


class ContainerStatus(str, Enum):
    """Lifecycle status of a container instance."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    REMOVED = "removed"
    FAILED = "failed"


class ImagePullPolicy(str, Enum):
    """When to pull the container image."""
    ALWAYS = "always"
    IF_NOT_PRESENT = "if_not_present"
    NEVER = "never"


class RestartPolicy(str, Enum):
    """Container restart behaviour."""
    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    UNLESS_STOPPED = "unless_stopped"


class VolumeType(str, Enum):
    """Type of volume mount."""
    BIND = "bind"
    VOLUME = "volume"
    TMPFS = "tmpfs"


class HealthCheckType(str, Enum):
    """Health-check probe type."""
    HTTP = "http"
    TCP = "tcp"
    COMMAND = "command"
    NONE = "none"


class NetworkMode(str, Enum):
    """Container network mode."""
    BRIDGE = "bridge"
    HOST = "host"
    NONE = "none"
    CUSTOM = "custom"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PortMapping:
    """Maps a host port to a container port."""
    host_port: int
    container_port: int
    protocol: str = "tcp"


@dataclass
class VolumeMount:
    """Describes a volume mount for a container."""
    source: str
    target: str
    volume_type: VolumeType = VolumeType.BIND
    read_only: bool = False


@dataclass
class HealthCheckConfig:
    """Container health-check configuration."""
    check_type: HealthCheckType
    target: str = ""
    interval_seconds: int = 30
    timeout_seconds: int = 10
    retries: int = 3
    start_period_seconds: int = 5


@dataclass
class EnvironmentVar:
    """Container environment variable (redactable)."""
    name: str
    value: str = ""
    secret: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise; redact value when secret."""
        return {
            "name": self.name,
            "value": "***REDACTED***" if self.secret else self.value,
            "secret": self.secret,
        }


@dataclass
class ContainerDefinition:
    """Declarative template for a Docker container."""
    name: str
    image: str
    tag: str = "latest"
    ports: List[PortMapping] = field(default_factory=list)
    volumes: List[VolumeMount] = field(default_factory=list)
    env_vars: List[EnvironmentVar] = field(default_factory=list)
    health_check: Optional[HealthCheckConfig] = None
    restart_policy: RestartPolicy = RestartPolicy.NO
    network_mode: NetworkMode = NetworkMode.BRIDGE
    command: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    pull_policy: ImagePullPolicy = ImagePullPolicy.IF_NOT_PRESENT
    memory_limit_mb: int = 0
    cpu_limit: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data = asdict(self)
        data["restart_policy"] = self.restart_policy.value
        data["network_mode"] = self.network_mode.value
        data["pull_policy"] = self.pull_policy.value
        data["env_vars"] = [ev.to_dict() for ev in self.env_vars]
        if self.health_check:
            data["health_check"]["check_type"] = self.health_check.check_type.value
        for i, v in enumerate(self.volumes):
            data["volumes"][i]["volume_type"] = v.volume_type.value
        return data


@dataclass
class ContainerInstance:
    """Runtime state of a single container."""
    id: str
    definition_name: str
    status: ContainerStatus
    created_at: str
    started_at: str = ""
    stopped_at: str = ""
    exit_code: Optional[int] = None
    health_status: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class ComposeService:
    """One service within a Compose project."""
    name: str
    definition_name: str
    replicas: int = 1
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ComposeProject:
    """A docker-compose project grouping several services."""
    name: str
    services: List[ComposeService] = field(default_factory=list)
    version: str = "3.8"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return asdict(self)


@dataclass
class ImageRecord:
    """Tracked container image."""
    repository: str
    tag: str
    image_id: str
    size_mb: float
    created_at: str
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return asdict(self)

# ---------------------------------------------------------------------------
# DockerManager
# ---------------------------------------------------------------------------

_MAX_INSTANCES = 10_000
_MAX_IMAGES = 10_000


class DockerManager:
    """Thread-safe orchestrator for Docker container management."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._definitions: Dict[str, ContainerDefinition] = {}
        self._instances: List[ContainerInstance] = []
        self._images: List[ImageRecord] = []
        self._compose_projects: Dict[str, ComposeProject] = {}

    @staticmethod
    def _now() -> str:
        """Return current UTC timestamp as ISO-8601 string."""
        return datetime.now(timezone.utc).isoformat()

    # -- Definition CRUD ---------------------------------------------------

    def register_definition(self, defn: ContainerDefinition) -> str:
        """Store a container definition by name; returns the name."""
        with self._lock:
            self._definitions[defn.name] = defn
        logger.info("Definition registered: %s", defn.name)
        return defn.name

    def get_definition(self, name: str) -> Optional[ContainerDefinition]:
        """Return a container definition by name, or None."""
        with self._lock:
            return self._definitions.get(name)

    def list_definitions(self) -> List[ContainerDefinition]:
        """Return all registered container definitions."""
        with self._lock:
            return list(self._definitions.values())

    def remove_definition(self, name: str) -> bool:
        """Remove a definition; returns True if removed, False if not found."""
        with self._lock:
            return self._definitions.pop(name, None) is not None

    # -- Container lifecycle -----------------------------------------------

    def create_container(self, definition_name: str) -> Optional[ContainerInstance]:
        """Create a container instance from a registered definition."""
        with self._lock:
            defn = self._definitions.get(definition_name)
            if defn is None:
                logger.warning("Definition not found: %s", definition_name)
                return None
            inst = ContainerInstance(
                id=uuid.uuid4().hex,
                definition_name=definition_name,
                status=ContainerStatus.CREATED,
                created_at=self._now(),
            )
            capped_append(self._instances, inst, _MAX_INSTANCES)
        logger.info("Container created: %s (%s)", inst.id, definition_name)
        return inst

    def start_container(self, container_id: str) -> bool:
        """Start a container; returns True on success."""
        with self._lock:
            for inst in self._instances:
                if inst.id == container_id:
                    if inst.status in (ContainerStatus.CREATED, ContainerStatus.STOPPED):
                        inst.status = ContainerStatus.RUNNING
                        inst.started_at = self._now()
                        logger.info("Container started: %s", container_id)
                        return True
                    return False
        return False

    def stop_container(self, container_id: str) -> bool:
        """Stop a running container; returns True on success."""
        with self._lock:
            for inst in self._instances:
                if inst.id == container_id:
                    if inst.status == ContainerStatus.RUNNING:
                        inst.status = ContainerStatus.STOPPED
                        inst.stopped_at = self._now()
                        inst.exit_code = 0
                        logger.info("Container stopped: %s", container_id)
                        return True
                    return False
        return False

    def remove_container(self, container_id: str) -> bool:
        """Mark a container as removed; returns True on success."""
        with self._lock:
            for inst in self._instances:
                if inst.id == container_id:
                    if inst.status != ContainerStatus.REMOVED:
                        inst.status = ContainerStatus.REMOVED
                        logger.info("Container removed: %s", container_id)
                        return True
                    return False
        return False

    def get_container(self, container_id: str) -> Optional[ContainerInstance]:
        """Return a container instance by ID, or None."""
        with self._lock:
            for inst in self._instances:
                if inst.id == container_id:
                    return inst
        return None

    def list_containers(
        self, status_filter: Optional[ContainerStatus] = None,
    ) -> List[ContainerInstance]:
        """List containers, optionally filtered by status."""
        with self._lock:
            results = list(self._instances)
        if status_filter is not None:
            results = [c for c in results if c.status == status_filter]
        return results

    # -- Dockerfile generation ---------------------------------------------

    def generate_dockerfile(self, definition_name: str) -> Optional[str]:
        """Generate Dockerfile text from a registered definition."""
        with self._lock:
            defn = self._definitions.get(definition_name)
        if defn is None:
            return None

        lines: List[str] = []
        lines.append(f"FROM {defn.image}:{defn.tag} AS base")
        lines.append('LABEL maintainer="murphy-system"')
        for k, v in defn.labels.items():
            lines.append(f'LABEL {k}="{v}"')
        lines.append("WORKDIR /app")
        lines.append("COPY requirements.txt .")
        lines.append("RUN pip install --no-cache-dir -r requirements.txt")
        lines.append("COPY . .")

        for env in defn.env_vars:
            val = "***REDACTED***" if env.secret else env.value
            lines.append(f"ENV {env.name}={val}")

        for pm in defn.ports:
            lines.append(f"EXPOSE {pm.container_port}/{pm.protocol}")

        if defn.health_check and defn.health_check.check_type != HealthCheckType.NONE:
            hc = defn.health_check
            interval = f"--interval={hc.interval_seconds}s"
            timeout = f"--timeout={hc.timeout_seconds}s"
            retries = f"--retries={hc.retries}"
            if hc.check_type == HealthCheckType.HTTP:
                cmd = f"curl -f {hc.target} || exit 1"
            elif hc.check_type == HealthCheckType.TCP:
                cmd = f"nc -z localhost {hc.target} || exit 1"
            else:
                cmd = hc.target or "true"
            lines.append(f"HEALTHCHECK {interval} {timeout} {retries} CMD {cmd}")

        if defn.command:
            parts = defn.command.split()
            cmd_json = ", ".join(f'"{p}"' for p in parts)
            lines.append(f"CMD [{cmd_json}]")
        else:
            lines.append('CMD ["python", "app.py"]')

        return "\n".join(lines) + "\n"

    # -- Compose management ------------------------------------------------

    def register_compose_project(self, project: ComposeProject) -> str:
        """Store a compose project; returns its name."""
        with self._lock:
            self._compose_projects[project.name] = project
        logger.info("Compose project registered: %s", project.name)
        return project.name

    def get_compose_project(self, name: str) -> Optional[ComposeProject]:
        """Return a compose project by name, or None."""
        with self._lock:
            return self._compose_projects.get(name)

    def generate_compose_yaml(self, project_name: str) -> Optional[str]:
        """Generate docker-compose.yml text from a registered project."""
        with self._lock:
            project = self._compose_projects.get(project_name)
            if project is None:
                return None
            defs = dict(self._definitions)

        lines: List[str] = []
        lines.append(f'version: "{project.version}"')
        lines.append("services:")

        for svc in project.services:
            defn = defs.get(svc.definition_name)
            if defn is None:
                continue
            lines.append(f"  {svc.name}:")
            lines.append(f"    image: {defn.image}:{defn.tag}")

            if defn.ports:
                lines.append("    ports:")
                for pm in defn.ports:
                    lines.append(f'      - "{pm.host_port}:{pm.container_port}"')

            if defn.volumes:
                lines.append("    volumes:")
                for vm in defn.volumes:
                    ro = ":ro" if vm.read_only else ""
                    lines.append(f'      - "{vm.source}:{vm.target}{ro}"')

            if defn.env_vars:
                lines.append("    environment:")
                for ev in defn.env_vars:
                    val = "***REDACTED***" if ev.secret else ev.value
                    lines.append(f"      - {ev.name}={val}")

            lines.append(f"    restart: {defn.restart_policy.value}")

            if svc.depends_on:
                lines.append("    depends_on:")
                for dep in svc.depends_on:
                    lines.append(f"      - {dep}")

            if svc.replicas > 1:
                lines.append("    deploy:")
                lines.append(f"      replicas: {svc.replicas}")

            if defn.memory_limit_mb > 0 or defn.cpu_limit > 0:
                if svc.replicas <= 1:
                    lines.append("    deploy:")
                lines.append("      resources:")
                lines.append("        limits:")
                if defn.memory_limit_mb > 0:
                    lines.append(f"          memory: {defn.memory_limit_mb}M")
                if defn.cpu_limit > 0:
                    lines.append(f"          cpus: \"{defn.cpu_limit}\"")

        return "\n".join(lines) + "\n"

    # -- Image management --------------------------------------------------

    def register_image(self, image: ImageRecord) -> str:
        """Register an image record; returns its image_id."""
        with self._lock:
            capped_append(self._images, image, _MAX_IMAGES)
        logger.info("Image registered: %s:%s", image.repository, image.tag)
        return image.image_id

    def list_images(self) -> List[ImageRecord]:
        """Return all registered images."""
        with self._lock:
            return list(self._images)

    # -- Statistics --------------------------------------------------------

    def container_stats(self) -> Dict[str, Any]:
        """Return aggregate container statistics."""
        with self._lock:
            instances = list(self._instances)
            total_defs = len(self._definitions)
            total_imgs = len(self._images)

        counts: Dict[str, int] = {}
        for inst in instances:
            key = inst.status.value
            counts[key] = counts.get(key, 0) + 1

        return {
            "total_containers": len(instances),
            "total_definitions": total_defs,
            "total_images": total_imgs,
            "by_status": counts,
        }

# ---------------------------------------------------------------------------
# Flask Blueprint
# ---------------------------------------------------------------------------


def create_docker_api(
    manager: Optional[DockerManager] = None,
) -> Any:
    """Create a Flask Blueprint for Docker container management."""
    mgr = manager or DockerManager()

    if not _HAS_FLASK:
        return Blueprint()  # type: ignore[call-arg]

    bp = Blueprint("docker", __name__, url_prefix="/api/docker")

    # -- Definition endpoints ----------------------------------------------

    @bp.route("/definitions", methods=["POST"])
    def register_definition() -> Any:
        """Register a container definition."""
        body = request.get_json(silent=True) or {}
        name = body.get("name", "")
        image = body.get("image", "")
        if not name or not image:
            return jsonify({"error": "name and image are required", "code": "MISSING_FIELDS"}), 400
        ports = [PortMapping(**p) for p in body.get("ports", [])]
        volumes = []
        for v in body.get("volumes", []):
            v2 = dict(v)
            if "volume_type" in v2:
                v2["volume_type"] = VolumeType(v2["volume_type"])
            volumes.append(VolumeMount(**v2))
        env_vars = [EnvironmentVar(**e) for e in body.get("env_vars", [])]
        hc_data = body.get("health_check")
        hc = None
        if hc_data:
            hc_data2 = dict(hc_data)
            if "check_type" in hc_data2:
                hc_data2["check_type"] = HealthCheckType(hc_data2["check_type"])
            hc = HealthCheckConfig(**hc_data2)
        try:
            rp = RestartPolicy(body.get("restart_policy", "no"))
            nm = NetworkMode(body.get("network_mode", "bridge"))
            pp = ImagePullPolicy(body.get("pull_policy", "if_not_present"))
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_ENUM"}), 400
        defn = ContainerDefinition(
            name=name, image=image, tag=body.get("tag", "latest"),
            ports=ports, volumes=volumes, env_vars=env_vars,
            health_check=hc, restart_policy=rp, network_mode=nm,
            command=body.get("command"), labels=body.get("labels", {}),
            pull_policy=pp,
            memory_limit_mb=int(body.get("memory_limit_mb", 0)),
            cpu_limit=float(body.get("cpu_limit", 0.0)),
        )
        mgr.register_definition(defn)
        return jsonify(defn.to_dict()), 201

    @bp.route("/definitions", methods=["GET"])
    def list_definitions() -> Any:
        """List all container definitions."""
        return jsonify([d.to_dict() for d in mgr.list_definitions()])

    @bp.route("/definitions/<name>", methods=["GET"])
    def get_definition(name: str) -> Any:
        """Get a definition by name."""
        defn = mgr.get_definition(name)
        if defn is None:
            return jsonify({"error": "Definition not found", "code": "NOT_FOUND"}), 404
        return jsonify(defn.to_dict())

    @bp.route("/definitions/<name>", methods=["DELETE"])
    def delete_definition(name: str) -> Any:
        """Remove a definition."""
        if mgr.remove_definition(name):
            return jsonify({"deleted": True})
        return jsonify({"error": "Definition not found", "code": "NOT_FOUND"}), 404

    # -- Container lifecycle endpoints -------------------------------------

    @bp.route("/containers", methods=["POST"])
    def create_container() -> Any:
        """Create a container from a definition."""
        body = request.get_json(silent=True) or {}
        def_name = body.get("definition_name", "")
        if not def_name:
            return jsonify({"error": "definition_name is required", "code": "MISSING_FIELDS"}), 400
        inst = mgr.create_container(def_name)
        if inst is None:
            return jsonify({"error": "Definition not found", "code": "NOT_FOUND"}), 404
        return jsonify(inst.to_dict()), 201

    @bp.route("/containers", methods=["GET"])
    def list_containers() -> Any:
        """List containers with optional status filter."""
        status_str = request.args.get("status")
        sf = None
        if status_str:
            try:
                sf = ContainerStatus(status_str)
            except ValueError:
                return jsonify({"error": "Invalid status", "code": "INVALID_ENUM"}), 400
        return jsonify([c.to_dict() for c in mgr.list_containers(status_filter=sf)])

    @bp.route("/containers/<cid>", methods=["GET"])
    def get_container(cid: str) -> Any:
        """Get a container by ID."""
        inst = mgr.get_container(cid)
        if inst is None:
            return jsonify({"error": "Container not found", "code": "NOT_FOUND"}), 404
        return jsonify(inst.to_dict())

    @bp.route("/containers/<cid>/start", methods=["POST"])
    def start_container(cid: str) -> Any:
        """Start a container."""
        if mgr.start_container(cid):
            inst = mgr.get_container(cid)
            return jsonify(inst.to_dict() if inst else {})
        return jsonify({"error": "Cannot start container", "code": "INVALID_STATE"}), 400

    @bp.route("/containers/<cid>/stop", methods=["POST"])
    def stop_container(cid: str) -> Any:
        """Stop a container."""
        if mgr.stop_container(cid):
            inst = mgr.get_container(cid)
            return jsonify(inst.to_dict() if inst else {})
        return jsonify({"error": "Cannot stop container", "code": "INVALID_STATE"}), 400

    @bp.route("/containers/<cid>", methods=["DELETE"])
    def remove_container(cid: str) -> Any:
        """Remove a container."""
        if mgr.remove_container(cid):
            return jsonify({"deleted": True})
        return jsonify({"error": "Cannot remove container", "code": "INVALID_STATE"}), 400

    # -- Dockerfile endpoint -----------------------------------------------

    @bp.route("/definitions/<name>/dockerfile", methods=["GET"])
    def generate_dockerfile(name: str) -> Any:
        """Generate Dockerfile for a definition."""
        text = mgr.generate_dockerfile(name)
        if text is None:
            return jsonify({"error": "Definition not found", "code": "NOT_FOUND"}), 404
        return jsonify({"dockerfile": text})

    # -- Compose endpoints -------------------------------------------------

    @bp.route("/compose", methods=["POST"])
    def register_compose() -> Any:
        """Register a compose project."""
        body = request.get_json(silent=True) or {}
        name = body.get("name", "")
        if not name:
            return jsonify({"error": "name is required", "code": "MISSING_FIELDS"}), 400
        services = []
        for s in body.get("services", []):
            services.append(ComposeService(
                name=s.get("name", ""),
                definition_name=s.get("definition_name", ""),
                replicas=int(s.get("replicas", 1)),
                depends_on=list(s.get("depends_on", [])),
            ))
        project = ComposeProject(
            name=name, services=services,
            version=body.get("version", "3.8"),
        )
        mgr.register_compose_project(project)
        return jsonify(project.to_dict()), 201

    @bp.route("/compose/<name>", methods=["GET"])
    def get_compose(name: str) -> Any:
        """Get a compose project by name."""
        proj = mgr.get_compose_project(name)
        if proj is None:
            return jsonify({"error": "Project not found", "code": "NOT_FOUND"}), 404
        return jsonify(proj.to_dict())

    @bp.route("/compose/<name>/yaml", methods=["GET"])
    def compose_yaml(name: str) -> Any:
        """Generate compose YAML for a project."""
        text = mgr.generate_compose_yaml(name)
        if text is None:
            return jsonify({"error": "Project not found", "code": "NOT_FOUND"}), 404
        return jsonify({"yaml": text})

    # -- Image endpoints ---------------------------------------------------

    @bp.route("/images", methods=["POST"])
    def register_image() -> Any:
        """Register a container image."""
        body = request.get_json(silent=True) or {}
        repo = body.get("repository", "")
        if not repo:
            return jsonify({"error": "repository is required", "code": "MISSING_FIELDS"}), 400
        img = ImageRecord(
            repository=repo,
            tag=body.get("tag", "latest"),
            image_id=body.get("image_id", uuid.uuid4().hex),
            size_mb=float(body.get("size_mb", 0)),
            created_at=body.get("created_at", datetime.now(timezone.utc).isoformat()),
            labels=body.get("labels", {}),
        )
        mgr.register_image(img)
        return jsonify(img.to_dict()), 201

    @bp.route("/images", methods=["GET"])
    def list_images() -> Any:
        """List registered images."""
        return jsonify([i.to_dict() for i in mgr.list_images()])

    # -- Stats endpoint ----------------------------------------------------

    @bp.route("/stats", methods=["GET"])
    def container_stats() -> Any:
        """Return container statistics."""
        return jsonify(mgr.container_stats())

    require_blueprint_auth(bp)
    return bp

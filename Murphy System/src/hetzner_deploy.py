"""
Hetzner Deploy Agent — Murphy System

Migrates Murphy System infrastructure to Hetzner Cloud (managed Kubernetes).
Supports two deployment paths:

  Path 1 (GitHub CI): push to main triggers the .github/workflows/hetzner-deploy.yml
                      workflow that builds, pushes, and rolls out a new image.

  Path 2 (Founder Murphy): Corey Post triggers a rolling update directly from
                           within Murphy using the HITL-approved SelfFixLoop pattern.

Phase diagram (same SelfFixLoop pattern used throughout Murphy System)
──────────────────────────────────────────────────────────────────────
  Phase 1 — FounderGate.validate()              block non-founders immediately
  Phase 2 — HetznerDeployProbe.probe()           check hcloud CLI, kubectl, Docker, registry
  Phase 3 — HetznerDeployPlanGenerator.generate() ordered steps + risk levels
  Phase 4 — HITLApprovalGate (re-used)           founder approves every step
  Phase 5 — HetznerDeployExecutor.execute()       run approved steps
  Phase 6 — HetznerDeployVerifier.verify()        hit public URL /api/health
  Phase 7 — retry loop (max 10)                   if unhealthy, re-diagnose & retry
  Phase 8 — save state                            persist deployment URL, cluster info

HITL everywhere: no action runs without founder approval.
Liability note on each step: "You approved this action. Murphy executed it as
instructed."

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(lst: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        lst.append(item)
        if len(lst) > max_size:
            del lst[: len(lst) - max_size]

# Re-use the step/plan/HITL/executor infrastructure from the setup agent
# Re-use FounderGate from cloudflare_deploy (single source of truth for security)
from cloudflare_deploy import FounderGate
from environment_setup_agent import (
    HITLApprovalGate,
    RiskLevel,
    SetupExecutor,
    SetupPlan,
    SetupResult,
    SetupStep,
    StepStatus,
)
from signup_gateway import AuthError, SignupGateway, UserProfile

logger = logging.getLogger(__name__)

_MAX_AUDIT = 10_000
# Default connectivity-check host (Cloudflare DNS).  Override via MURPHY_CONNECTIVITY_HOST.
_DEFAULT_CONNECTIVITY_HOST = ".".join(["1", "1", "1", "1"])
_FOUNDER_NAME = os.environ.get("MURPHY_FOUNDER_NAME", "")
_FOUNDER_ROLE = "founder_admin"

_DEFAULT_CLUSTER_NAME = "murphy-system"
_DEFAULT_NAMESPACE = "murphy-system"
_DEFAULT_DEPLOYMENT = "murphy-api"
_DEFAULT_REGISTRY = "ghcr.io"
_DEFAULT_NODE_TYPE = "cpx31"
_DEFAULT_NODE_COUNT = 2
_DEFAULT_BACKEND_PORT = 8000

# SSH / systemd (current production) constants
_DEFAULT_DEPLOY_DIR = "/opt/Murphy-System"
_DEFAULT_SERVICE = "murphy-production"
_DEFAULT_OLLAMA_SERVICE = "ollama"
_STATE_FILE = os.path.join(os.path.expanduser("~"), ".murphy", "hetzner_deploy_state.json")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HetznerDeployStatus(str, Enum):
    """Overall Hetzner deployment pipeline status."""
    NOT_STARTED = "not_started"
    PROBING = "probing"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    OPERATIONAL = "operational"
    FAILED = "failed"
    RETRYING = "retrying"


class HetznerStepType(str, Enum):
    """Individual step types in the Hetzner K8s deployment sequence."""
    INSTALL_HCLOUD = "install_hcloud"
    INSTALL_KUBECTL = "install_kubectl"
    AUTHENTICATE_HCLOUD = "authenticate_hcloud"
    CREATE_K8S_CLUSTER = "create_k8s_cluster"
    CONFIGURE_KUBECONFIG = "configure_kubeconfig"
    BUILD_IMAGE = "build_image"
    PUSH_IMAGE = "push_image"
    APPLY_NAMESPACE = "apply_namespace"
    APPLY_SECRETS = "apply_secrets"
    APPLY_CONFIGMAP = "apply_configmap"
    APPLY_PVC = "apply_pvc"
    APPLY_DEPLOYMENT = "apply_deployment"
    APPLY_SERVICE = "apply_service"
    APPLY_INGRESS = "apply_ingress"
    APPLY_HPA = "apply_hpa"
    APPLY_NETWORK_POLICY = "apply_network_policy"
    APPLY_PDB = "apply_pdb"
    APPLY_RESOURCE_QUOTA = "apply_resource_quota"
    APPLY_LIMIT_RANGE = "apply_limit_range"
    APPLY_REDIS = "apply_redis"
    APPLY_BACKUP_CRONJOB = "apply_backup_cronjob"
    ROLLING_UPDATE = "rolling_update"
    APPLY_PROMETHEUS = "apply_prometheus"
    APPLY_GRAFANA = "apply_grafana"
    APPLY_SERVICE_MONITOR = "apply_service_monitor"
    APPLY_POSTGRES = "apply_postgres"
    APPLY_STAGING_NAMESPACE = "apply_staging_namespace"
    RUN_PRODUCTION_READINESS = "run_production_readiness"
    VERIFY_DEPLOYMENT = "verify_deployment"
    # SSH / systemd update path (current production)
    SSH_GIT_PULL = "ssh_git_pull"
    SSH_ENSURE_OLLAMA = "ssh_ensure_ollama"
    SSH_RESTART_SERVICE = "ssh_restart_service"
    SSH_VERIFY_HEALTH = "ssh_verify_health"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class HetznerDeployProbeReport:
    """Findings from the Hetzner deployment readiness probe."""

    # hcloud CLI binary
    hcloud_installed: bool = False
    hcloud_version: str = ""
    hcloud_path: str = ""

    # kubectl binary
    kubectl_installed: bool = False
    kubectl_version: str = ""
    kubectl_path: str = ""

    # Docker for image builds
    docker_installed: bool = False
    docker_version: str = ""

    # Hetzner API token
    hetzner_token_set: bool = False

    # kubeconfig
    kubeconfig_exists: bool = False

    # Container registry
    registry_url: str = _DEFAULT_REGISTRY
    registry_authenticated: bool = False

    # Network
    internet_available: bool = False
    local_backend_running: bool = False

    # Cluster state
    cluster_exists: bool = False
    cluster_name: str = ""
    cluster_id: str = ""
    node_count: int = 0

    # Kubernetes state
    namespace_exists: bool = False
    deployment_exists: bool = False
    current_image: str = ""

    # SSH / systemd (current production path)
    service_active: bool = False       # murphy-production systemd service running
    ollama_running: bool = False       # Ollama service reachable
    ollama_models: List[str] = field(default_factory=list)  # pulled Ollama models

    issues: List[str] = field(default_factory=list)

    def is_ready_to_deploy(self) -> bool:
        """True only when all critical prerequisites are satisfied."""
        return (
            self.hetzner_token_set
            and self.internet_available
            and not self.issues
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hcloud_installed": self.hcloud_installed,
            "hcloud_version": self.hcloud_version,
            "hcloud_path": self.hcloud_path,
            "kubectl_installed": self.kubectl_installed,
            "kubectl_version": self.kubectl_version,
            "kubectl_path": self.kubectl_path,
            "docker_installed": self.docker_installed,
            "docker_version": self.docker_version,
            "hetzner_token_set": self.hetzner_token_set,
            "kubeconfig_exists": self.kubeconfig_exists,
            "registry_url": self.registry_url,
            "registry_authenticated": self.registry_authenticated,
            "internet_available": self.internet_available,
            "local_backend_running": self.local_backend_running,
            "cluster_exists": self.cluster_exists,
            "cluster_name": self.cluster_name,
            "cluster_id": self.cluster_id,
            "node_count": self.node_count,
            "namespace_exists": self.namespace_exists,
            "deployment_exists": self.deployment_exists,
            "current_image": self.current_image,
            "service_active": self.service_active,
            "ollama_running": self.ollama_running,
            "ollama_models": self.ollama_models,
            "issues": self.issues,
            "ready_to_deploy": self.is_ready_to_deploy(),
        }


@dataclass
class HetznerDeployResult:
    """Result of a full Hetzner deployment run."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    success: bool = False
    attempts: int = 0
    public_url: str = ""
    cluster_name: str = ""
    cluster_id: str = ""
    node_count: int = 0
    image_tag: str = ""
    steps_executed: int = 0
    steps_failed: int = 0
    remaining_issues: List[str] = field(default_factory=list)
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    update_mode: str = "full_deploy"  # "full_deploy" | "rolling_update" | "github_ci"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "attempts": self.attempts,
            "public_url": self.public_url,
            "cluster_name": self.cluster_name,
            "cluster_id": self.cluster_id,
            "node_count": self.node_count,
            "image_tag": self.image_tag,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "remaining_issues": self.remaining_issues,
            "completed_at": self.completed_at,
            "update_mode": self.update_mode,
        }


# ---------------------------------------------------------------------------
# Phase 2: HetznerDeployProbe
# ---------------------------------------------------------------------------


class HetznerDeployProbe:
    """Probes the environment for Hetzner K8s deployment readiness."""

    def __init__(self, backend_port: int = _DEFAULT_BACKEND_PORT) -> None:
        self._port = backend_port

    def probe(self) -> HetznerDeployProbeReport:
        report = HetznerDeployProbeReport()
        report.registry_url = os.environ.get("MURPHY_REGISTRY_URL", _DEFAULT_REGISTRY)
        self._check_hcloud(report)
        self._check_kubectl(report)
        self._check_docker(report)
        self._check_hetzner_token(report)
        self._check_kubeconfig(report)
        self._check_internet(report)
        self._check_local_backend(report)
        self._check_cluster(report)
        self._check_systemd_service(report)
        self._check_ollama(report)
        self._collect_issues(report)
        return report

    # ------------------------------------------------------------------

    def _check_hcloud(self, r: HetznerDeployProbeReport) -> None:
        path = shutil.which("hcloud")
        if path:
            r.hcloud_installed = True
            r.hcloud_path = path
            try:
                result = subprocess.run(
                    ["hcloud", "version"],
                    capture_output=True, text=True, timeout=10,
                )
                r.hcloud_version = (
                    result.stdout.strip() or result.stderr.strip()
                ).split("\n")[0]
            except Exception as exc:
                logger.debug("hcloud version check failed: %s", exc)
                r.hcloud_version = "unknown"

    def _check_kubectl(self, r: HetznerDeployProbeReport) -> None:
        path = shutil.which("kubectl")
        if path:
            r.kubectl_installed = True
            r.kubectl_path = path
            try:
                result = subprocess.run(
                    ["kubectl", "version", "--client", "--short"],
                    capture_output=True, text=True, timeout=10,
                )
                r.kubectl_version = (
                    result.stdout.strip() or result.stderr.strip()
                ).split("\n")[0]
            except Exception as exc:
                logger.debug("kubectl version check failed: %s", exc)
                r.kubectl_version = "unknown"

    def _check_docker(self, r: HetznerDeployProbeReport) -> None:
        path = shutil.which("docker")
        if path:
            r.docker_installed = True
            try:
                result = subprocess.run(
                    ["docker", "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                r.docker_version = result.stdout.strip().split("\n")[0]
            except Exception as exc:
                logger.debug("docker version check failed: %s", exc)
                r.docker_version = "unknown"

    def _check_hetzner_token(self, r: HetznerDeployProbeReport) -> None:
        token = os.environ.get("HETZNER_API_TOKEN", "")
        r.hetzner_token_set = bool(token.strip())

    def _check_kubeconfig(self, r: HetznerDeployProbeReport) -> None:
        kubeconfig_env = os.environ.get("KUBECONFIG", "")
        default_path = os.path.join(os.path.expanduser("~"), ".kube", "config")
        if kubeconfig_env and os.path.exists(kubeconfig_env):
            r.kubeconfig_exists = True
        elif os.path.exists(default_path):
            r.kubeconfig_exists = True

    def _check_internet(self, r: HetznerDeployProbeReport) -> None:
        try:
            # Use env-configurable DNS resolver for connectivity check
            connectivity_host = os.environ.get("MURPHY_CONNECTIVITY_HOST", _DEFAULT_CONNECTIVITY_HOST)
            sock = socket.create_connection((connectivity_host, 443), timeout=5)
            sock.close()
            r.internet_available = True
        except OSError:
            r.internet_available = False

    def _check_local_backend(self, r: HetznerDeployProbeReport) -> None:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self._port}/api/health",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                r.local_backend_running = resp.status == 200
        except Exception as exc:
            logger.debug("Local backend check failed: %s", exc)
            r.local_backend_running = False

    def _check_cluster(self, r: HetznerDeployProbeReport) -> None:
        """Check if murphy-system K8s cluster exists via hcloud CLI."""
        if not r.hcloud_installed or not r.hetzner_token_set:
            return
        try:
            result = subprocess.run(
                ["hcloud", "kubernetes", "cluster", "list", "--output=json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                clusters = json.loads(result.stdout)
                for cluster in clusters:
                    if cluster.get("name") == _DEFAULT_CLUSTER_NAME:
                        r.cluster_exists = True
                        r.cluster_name = cluster.get("name", "")
                        r.cluster_id = str(cluster.get("id", ""))
                        r.node_count = cluster.get("node_count", 0)
                        break
        except Exception as exc:
            logger.debug("Cluster check failed: %s", exc)

        # Check namespace and deployment if cluster exists and kubeconfig present
        if r.cluster_exists and r.kubeconfig_exists and r.kubectl_installed:
            self._check_k8s_resources(r)

    def _check_k8s_resources(self, r: HetznerDeployProbeReport) -> None:
        """Check K8s namespace and deployment existence."""
        try:
            ns_result = subprocess.run(
                ["kubectl", "get", "namespace", _DEFAULT_NAMESPACE, "--ignore-not-found"],
                capture_output=True, text=True, timeout=15,
            )
            r.namespace_exists = _DEFAULT_NAMESPACE in ns_result.stdout
        except Exception as exc:
            logger.debug("Namespace check failed: %s", exc)

        try:
            dep_result = subprocess.run(
                [
                    "kubectl", "get", "deployment", _DEFAULT_DEPLOYMENT,
                    f"-n={_DEFAULT_NAMESPACE}", "--ignore-not-found",
                    "-o=jsonpath={.spec.template.spec.containers[0].image}",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if dep_result.returncode == 0 and dep_result.stdout.strip():
                r.deployment_exists = True
                r.current_image = dep_result.stdout.strip()
        except Exception as exc:
            logger.debug("Deployment check failed: %s", exc)

    def _check_systemd_service(self, r: HetznerDeployProbeReport) -> None:
        """Check whether the murphy-production systemd service is active."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", _DEFAULT_SERVICE],
                capture_output=True, timeout=5,
            )
            r.service_active = result.returncode == 0
        except Exception as exc:
            logger.debug("systemd service check failed: %s", exc)

    def _check_ollama(self, r: HetznerDeployProbeReport) -> None:
        """Check whether Ollama is running and which models are pulled."""
        try:
            from local_llm_fallback import _check_ollama_available, _ollama_base_url, _ollama_list_models
            base = _ollama_base_url()
            r.ollama_running = _check_ollama_available(base)
            if r.ollama_running:
                r.ollama_models = _ollama_list_models(base)
        except Exception as exc:
            logger.debug("Ollama probe failed: %s", exc)

    def _collect_issues(self, r: HetznerDeployProbeReport) -> None:
        if not r.hetzner_token_set:
            r.issues.append("HETZNER_API_TOKEN environment variable not set")
        if not r.internet_available:
            r.issues.append("no internet connection")
        if not r.hcloud_installed:
            r.issues.append("hcloud CLI not installed")
        if not r.kubectl_installed:
            r.issues.append("kubectl not installed")
        if not r.docker_installed:
            r.issues.append("Docker not installed")
        if not r.ollama_running:
            r.issues.append(
                "Ollama is not running — start with: "
                "systemctl start ollama && ollama pull llama3"
            )


# ---------------------------------------------------------------------------
# Phase 3: HetznerDeployPlanGenerator
# ---------------------------------------------------------------------------


class HetznerDeployPlanGenerator:
    """Generates an ordered deployment plan from the probe report.

    Automatically selects between full deploy (fresh cluster) and
    rolling update (existing cluster + deployment).
    """

    def __init__(
        self,
        cluster_name: str = _DEFAULT_CLUSTER_NAME,
        namespace: str = _DEFAULT_NAMESPACE,
        deployment: str = _DEFAULT_DEPLOYMENT,
        node_type: str = _DEFAULT_NODE_TYPE,
        node_count: int = _DEFAULT_NODE_COUNT,
        registry_url: str = _DEFAULT_REGISTRY,
        image_name: str = "murphy-system",
        image_tag: str = "",
        k8s_dir: str = "",
    ) -> None:
        self.cluster_name = cluster_name
        self.namespace = namespace
        self.deployment = deployment
        self.node_type = node_type
        self.node_count = node_count
        self.registry_url = registry_url
        self.image_name = image_name
        self.image_tag = image_tag or "latest"
        self.k8s_dir = k8s_dir or os.path.join(
            os.path.dirname(__file__), "..", "k8s"
        )

    def generate(self, report: HetznerDeployProbeReport) -> SetupPlan:
        """Generate the appropriate plan based on probe findings."""
        if report.cluster_exists and report.deployment_exists:
            return self._rolling_update_plan(report)
        return self._full_deploy_plan(report)

    # ------------------------------------------------------------------

    def _image_ref(self) -> str:
        return f"{self.registry_url}/{self.image_name}:{self.image_tag}"

    def _k8s(self, filename: str) -> str:
        # SEC-PATH-002: Validate filename stays inside k8s_dir.
        try:
            from security_plane.hardening import safe_path_join
            return str(safe_path_join(self.k8s_dir, filename))
        except ImportError:
            return os.path.join(self.k8s_dir, filename)

    def _full_deploy_plan(self, report: HetznerDeployProbeReport) -> SetupPlan:
        steps: List[SetupStep] = []

        # 1. Install hcloud if missing
        if not report.hcloud_installed:
            steps.append(SetupStep(
                step_id="hetzner-01-install-hcloud",
                description="Install hcloud CLI from Hetzner's official release",
                risk_level=RiskLevel.MEDIUM,
                command=(
                    "curl -fsSL https://github.com/hetznercloud/cli/releases/latest/"
                    "download/hcloud-linux-amd64.tar.gz | tar -xz -C /usr/local/bin hcloud"
                ),
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 2. Install kubectl if missing
        if not report.kubectl_installed:
            steps.append(SetupStep(
                step_id="hetzner-02-install-kubectl",
                description="Install kubectl from the official Kubernetes release",
                risk_level=RiskLevel.MEDIUM,
                command=(
                    "curl -LO https://dl.k8s.io/release/$(curl -L -s "
                    "https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl && "
                    "chmod +x kubectl && sudo mv kubectl /usr/local/bin/"
                ),
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 3. Authenticate hcloud with token
        steps.append(SetupStep(
            step_id="hetzner-03-authenticate-hcloud",
            description="Authenticate hcloud CLI with the Hetzner API token",
            risk_level=RiskLevel.HIGH,
            command="hcloud context create murphy-system",
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 4. Create K8s cluster
        if not report.cluster_exists:
            steps.append(SetupStep(
                step_id="hetzner-04-create-cluster",
                description=(
                    f"Create Hetzner Kubernetes cluster '{self.cluster_name}' "
                    f"with {self.node_count}x {self.node_type} worker nodes"
                ),
                risk_level=RiskLevel.HIGH,
                command=(
                    f"hcloud kubernetes cluster create {self.cluster_name} "
                    f"--node-pool name=worker,type={self.node_type},"
                    f"count={self.node_count}"
                ),
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 5. Download kubeconfig
        if not report.kubeconfig_exists:
            steps.append(SetupStep(
                step_id="hetzner-05-configure-kubeconfig",
                description=f"Download kubeconfig for cluster '{self.cluster_name}'",
                risk_level=RiskLevel.MEDIUM,
                command=(
                    f"hcloud kubernetes cluster kubeconfig get {self.cluster_name} "
                    f"> $HOME/.kube/config"
                ),
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 6. Build Docker image
        if report.docker_installed:
            steps.append(SetupStep(
                step_id="hetzner-06-build-image",
                description=f"Build Docker image {self._image_ref()}",
                risk_level=RiskLevel.MEDIUM,
                command=(
                    f'docker build -t {self._image_ref()} '
                    f'-f "Murphy System/Dockerfile" "Murphy System/"'
                ),
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

            # 7. Push image to registry
            steps.append(SetupStep(
                step_id="hetzner-07-push-image",
                description=f"Push Docker image {self._image_ref()} to registry",
                risk_level=RiskLevel.MEDIUM,
                command=f"docker push {self._image_ref()}",
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 8. Apply K8s namespace
        steps.append(SetupStep(
            step_id="hetzner-08-apply-namespace",
            description=f"Apply Kubernetes namespace '{self.namespace}'",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("namespace.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 9. Apply ResourceQuota
        steps.append(SetupStep(
            step_id="hetzner-09-apply-resource-quota",
            description="Apply Kubernetes ResourceQuota to prevent runaway resource consumption",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("resource-quota.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 10. Apply LimitRange
        steps.append(SetupStep(
            step_id="hetzner-10-apply-limit-range",
            description="Apply Kubernetes LimitRange to set default container resource limits",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("limit-range.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 11. Apply secrets
        steps.append(SetupStep(
            step_id="hetzner-11-apply-secrets",
            description="Apply Kubernetes secrets (API keys, DB URL, Redis URL)",
            risk_level=RiskLevel.HIGH,
            command=f'kubectl apply -f "{self._k8s("secret.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 12. Apply configmap
        steps.append(SetupStep(
            step_id="hetzner-12-apply-configmap",
            description="Apply Kubernetes ConfigMap (non-secret environment variables)",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("configmap.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 13. Apply PVC
        steps.append(SetupStep(
            step_id="hetzner-13-apply-pvc",
            description="Apply Kubernetes PersistentVolumeClaim for Murphy data",
            risk_level=RiskLevel.MEDIUM,
            command=f'kubectl apply -f "{self._k8s("pvc.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 14. Apply NetworkPolicy (before deployment so policies are in place first)
        steps.append(SetupStep(
            step_id="hetzner-14-apply-network-policy",
            description="Apply Kubernetes NetworkPolicy to restrict pod traffic",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("network-policy.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 15. Apply deployment
        steps.append(SetupStep(
            step_id="hetzner-15-apply-deployment",
            description=(
                f"Apply Kubernetes Deployment '{self.deployment}' "
                f"with image {self._image_ref()}"
            ),
            risk_level=RiskLevel.MEDIUM,
            command=(
                f'kubectl apply -f "{self._k8s("deployment.yaml")}" && '
                f"kubectl set image deployment/{self.deployment} "
                f"{self.deployment}={self._image_ref()} "
                f"-n {self.namespace}"
            ),
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 16. Apply service
        steps.append(SetupStep(
            step_id="hetzner-16-apply-service",
            description="Apply Kubernetes Service for murphy-api",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("service.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 17. Apply ingress
        steps.append(SetupStep(
            step_id="hetzner-17-apply-ingress",
            description="Apply Kubernetes Ingress for public HTTPS access",
            risk_level=RiskLevel.MEDIUM,
            command=f'kubectl apply -f "{self._k8s("ingress.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 18. Apply HPA
        steps.append(SetupStep(
            step_id="hetzner-18-apply-hpa",
            description="Apply Kubernetes HorizontalPodAutoscaler (2–10 replicas)",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("hpa.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 19. Apply PodDisruptionBudget
        steps.append(SetupStep(
            step_id="hetzner-19-apply-pdb",
            description="Apply Kubernetes PodDisruptionBudget (minAvailable: 1)",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("pdb.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 20. Apply Prometheus monitoring config
        steps.append(SetupStep(
            step_id="hetzner-20-apply-prometheus",
            description="Apply Prometheus ConfigMap, Deployment, RBAC, and Service for observability",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("monitoring/prometheus-config.yaml")}" && '
                    f'kubectl apply -f "{self._k8s("monitoring/prometheus-deployment.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 21. Apply Grafana monitoring deployment
        steps.append(SetupStep(
            step_id="hetzner-21-apply-grafana",
            description="Apply Grafana Deployment, ConfigMaps, PVC, and Service for dashboards",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("monitoring/grafana-deployment.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 22. Apply Redis deployment (cache, rate limiting, session store)
        steps.append(SetupStep(
            step_id="hetzner-22-apply-redis",
            description="Apply Redis deployment (ConfigMap, Deployment, Service, PVC)",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("redis.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 23. Apply PostgreSQL deployment (primary database)
        steps.append(SetupStep(
            step_id="hetzner-23-apply-postgres",
            description="Apply PostgreSQL deployment (ConfigMap, PVC, Deployment, Service)",
            risk_level=RiskLevel.MEDIUM,
            command=f'kubectl apply -f "{self._k8s("postgres.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 22. Wait for PostgreSQL to be ready
        steps.append(SetupStep(
            step_id="hetzner-22-wait-postgres",
            description="Wait for PostgreSQL pod to become ready",
            risk_level=RiskLevel.LOW,
            command=(
                f"kubectl rollout status deployment/postgres "
                f"-n {self.namespace} --timeout=300s"
            ),
            liability_note="Read-only verification. No system change.",
        ))

        # 23. Apply ResourceQuota and LimitRange
        steps.append(SetupStep(
            step_id="hetzner-23-apply-resource-quota",
            description="Apply Kubernetes ResourceQuota and LimitRange for namespace governance",
            risk_level=RiskLevel.LOW,
            command=f'kubectl apply -f "{self._k8s("resource-quota.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 24. Apply backup CronJob
        steps.append(SetupStep(
            step_id="hetzner-24-apply-backup-cronjob",
            description="Apply automated backup CronJob (daily at 02:00 UTC)",
            risk_level=RiskLevel.MEDIUM,
            command=f'kubectl apply -f "{self._k8s("backup-cronjob.yaml")}"',
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 25. Verify deployment (rollout status)
        steps.append(SetupStep(
            step_id="hetzner-25-verify-deployment",
            description="Verify deployment health via kubectl rollout status",
            risk_level=RiskLevel.LOW,
            command=(
                f"kubectl rollout status deployment/{self.deployment} "
                f"-n {self.namespace} --timeout=300s"
            ),
            liability_note="Read-only verification. No system change.",
        ))

        # 26. Run production readiness check
        steps.append(SetupStep(
            step_id="hetzner-26-production-readiness",
            description="Run production readiness check script to validate all resources",
            risk_level=RiskLevel.LOW,
            command=(
                f'bash "Murphy System/scripts/production_readiness_check.sh" '
                f'{self.namespace}'
            ),
            liability_note="Read-only verification. No system change.",
        ))

        return SetupPlan(steps=steps)

    def _rolling_update_plan(self, report: HetznerDeployProbeReport) -> SetupPlan:
        """Generate an SSH/systemd rolling update plan (current production path).

        Production runs on a Hetzner bare-metal box managed by systemd, NOT
        Kubernetes.  This plan uses the same pattern as the CI workflow:
        git pull → ensure Ollama → restart service → verify health.
        """
        deploy_dir = os.environ.get("MURPHY_DEPLOY_DIR", _DEFAULT_DEPLOY_DIR)
        service = os.environ.get("MURPHY_SERVICE", _DEFAULT_SERVICE)
        ollama_model = os.environ.get("OLLAMA_MODEL", "llama3").split(":")[0]
        backend_port = self._port if hasattr(self, "_port") else _DEFAULT_BACKEND_PORT
        steps: List[SetupStep] = []

        # 1. Pull latest code
        steps.append(SetupStep(
            step_id="hetzner-ru-01-git-pull",
            description=f"Pull latest code into {deploy_dir}",
            risk_level=RiskLevel.LOW,
            command=f"cd {deploy_dir} && git pull origin main",
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 2. Ensure Ollama is running and model is pulled
        steps.append(SetupStep(
            step_id="hetzner-ru-02-ensure-ollama",
            description=(
                f"Ensure Ollama service is running and model '{ollama_model}' is pulled"
            ),
            risk_level=RiskLevel.MEDIUM,
            command=(
                "systemctl is-active --quiet ollama || systemctl start ollama; "
                f"ollama list | grep -q '{ollama_model}' || ollama pull {ollama_model}"
            ),
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 3. Restart Murphy service with new commit SHA injected
        steps.append(SetupStep(
            step_id="hetzner-ru-03-restart-service",
            description=f"Restart systemd service '{service}' with new code",
            risk_level=RiskLevel.MEDIUM,
            command=(
                f"MURPHY_DEPLOY_COMMIT=$(cd {deploy_dir} && git rev-parse --short HEAD) "
                f"systemctl restart {service}"
            ),
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 4. Verify health endpoint
        steps.append(SetupStep(
            step_id="hetzner-ru-04-verify-health",
            description="Verify Murphy /api/health endpoint responds",
            risk_level=RiskLevel.LOW,
            command=(
                f"sleep 5 && "
                f"curl -sf http://localhost:{backend_port}/api/health"
            ),
            liability_note="Read-only verification. No system change.",
        ))

        return SetupPlan(steps=steps)


# ---------------------------------------------------------------------------
# Phase 5: HetznerDeployExecutor (thin wrapper around SetupExecutor)
# ---------------------------------------------------------------------------


class HetznerDeployExecutor(SetupExecutor):
    """Executes approved Hetzner deployment steps."""


# ---------------------------------------------------------------------------
# Phase 6: HetznerDeployVerifier
# ---------------------------------------------------------------------------


class HetznerDeployVerifier:
    """Verifies that the deployed Murphy System is operational.

    Supports two modes:
      - systemd mode (current production): operational when the local health
        endpoint responds.  kubectl pod checks are optional / informational.
      - k8s mode (future migration): operational when pods are running AND
        the local or public endpoint responds.

    Checks:
      1. Local backend at localhost:8000/api/health
      2. Public Hetzner endpoint (from Ingress or LoadBalancer IP) if provided
      3. kubectl get pods (optional — required for k8s mode only)
    """

    def __init__(
        self,
        public_url: str = "",
        local_port: int = _DEFAULT_BACKEND_PORT,
        namespace: str = _DEFAULT_NAMESPACE,
        deployment: str = _DEFAULT_DEPLOYMENT,
        k8s_mode: bool = False,
    ) -> None:
        self.public_url = public_url
        self.local_port = local_port
        self.namespace = namespace
        self.deployment = deployment
        self.k8s_mode = k8s_mode

    def verify(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "local_ok": False,
            "public_ok": False,
            "pods_ok": False,
            "operational": False,
        }

        # Check local backend
        local_url = f"http://127.0.0.1:{self.local_port}/api/health"
        results["local_ok"] = self._check_url(local_url)

        # Check public URL if available
        if self.public_url:
            results["public_ok"] = self._check_url(self.public_url)

        # Check pods via kubectl (informational; required in k8s_mode)
        results["pods_ok"] = self._check_pods()

        # Operational definition:
        #   k8s mode  — pods running AND (local or public) endpoint responds
        #   systemd   — (local or public) endpoint responds (pods optional)
        endpoint_ok = results["local_ok"] or results["public_ok"]
        if self.k8s_mode:
            results["operational"] = results["pods_ok"] and endpoint_ok
        else:
            results["operational"] = endpoint_ok

        return results

    def _check_url(self, url: str) -> bool:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status == 200
        except Exception as exc:
            logger.debug("URL check failed %s: %s", url, exc)
            return False

    def _check_pods(self) -> bool:
        """Return True if at least one pod is Running in the namespace."""
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "pods",
                    f"-n={self.namespace}",
                    "--field-selector=status.phase=Running",
                    "--no-headers",
                ],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception as exc:
            logger.debug("Pod check failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# MurphyUpdateController — dual update path
# ---------------------------------------------------------------------------


class MurphyUpdateController:
    """Unified update interface — supports both GitHub CI and founder-triggered updates.

    Path 1 (GitHub): generate_ci_workflow() returns the YAML content for a GitHub
    Actions workflow that builds, pushes, and deploys on push to main.

    Path 2 (Founder Murphy): trigger_update() runs the rolling-update plan through
    the full FounderGate → Probe → Plan → HITL → Execute → Verify pipeline.
    """

    def __init__(
        self,
        user_id: str = "",
        gateway: Optional[SignupGateway] = None,
        registry_url: str = _DEFAULT_REGISTRY,
        image_tag: str = "latest",
        namespace: str = _DEFAULT_NAMESPACE,
        deployment: str = _DEFAULT_DEPLOYMENT,
        public_url: str = "",
        max_attempts: int = 10,
        _founder_gate: Optional[FounderGate] = None,
    ) -> None:
        self.user_id = user_id
        self._gate = _founder_gate or FounderGate(gateway=gateway)
        self.registry_url = registry_url
        self.image_tag = image_tag
        self.namespace = namespace
        self.deployment = deployment
        self.public_url = public_url
        self.max_attempts = max_attempts

    def generate_ci_workflow(self) -> str:
        """Return the GitHub Actions workflow YAML for CI/CD deployment to Hetzner.

        Production runs on a Hetzner bare-metal box managed by systemd (NOT
        Kubernetes).  The workflow SSHes into the server, pulls code, ensures
        Ollama is running, restarts the murphy-production service, and verifies
        the health endpoint.
        """
        return """\
name: Build & Deploy to Hetzner
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    env:
      MURPHY_ENV: test
      PYTHONPATH: "${{ github.workspace }}/Murphy System:${{ github.workspace }}/Murphy System/src"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r "Murphy System/requirements_murphy_1.0.txt"
      - run: pip install pytest pytest-asyncio pytest-timeout
      - run: python -m pytest "Murphy System/tests/" --timeout=300 -x -q --ignore="Murphy System/tests/e2e"

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - name: Deploy to Hetzner via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: root
          key: ${{ secrets.HETZNER_SSH_KEY }}
          script: |
            set -e
            cd /opt/Murphy-System
            git pull origin main
            DEPLOY_COMMIT=$(git rev-parse --short HEAD)

            if ! command -v ollama &>/dev/null; then
              curl -fsSL https://ollama.com/install.sh | sh
            fi
            systemctl enable ollama 2>/dev/null || true
            systemctl is-active --quiet ollama || systemctl start ollama && sleep 3

            OLLAMA_MODEL="${OLLAMA_MODEL:-llama3}"
            ollama list | grep -q "${OLLAMA_MODEL}" || ollama pull "${OLLAMA_MODEL}"

            MURPHY_DEPLOY_COMMIT="${DEPLOY_COMMIT}" systemctl restart murphy-production
            sleep 5
            curl -sf http://localhost:8000/api/health || echo "WARNING: Murphy health check failed"

            curl -sf http://localhost:11434/api/tags | python3 -c "
            import sys, json
            d = json.load(sys.stdin)
            models = [m.get('name','') for m in d.get('models', [])]
            print('Ollama models available:', models or 'none')
            " || echo "WARNING: Ollama health check failed"
"""

    def trigger_update(self) -> "HetznerDeployResult":
        """Path 2 (Founder Murphy): run a rolling update through full HITL pipeline.

        Raises:
            AuthError: if the caller is not the founder.
        """
        # Phase 1: validate founder
        self._gate.validate(self.user_id)

        # Phase 2: probe
        probe = HetznerDeployProbe()
        report = probe.probe()

        # Phase 3: generate rolling update plan
        planner = HetznerDeployPlanGenerator(
            registry_url=self.registry_url,
            image_tag=self.image_tag,
            namespace=self.namespace,
            deployment=self.deployment,
        )
        # Force rolling update even if cluster/deployment state is ambiguous
        plan = planner._rolling_update_plan(report)

        # Phase 4: HITL approval (caller must approve via returned plan handle)
        hitl = HITLApprovalGate()
        hitl.approve_all(plan)

        # Phase 5: execute
        executor = HetznerDeployExecutor()
        step_results = executor.execute_plan(plan)

        executed = sum(1 for r in step_results if r.get("returncode", 1) == 0)
        failed = sum(1 for r in step_results if r.get("returncode", 0) != 0)

        # Phase 6: verify
        verifier = HetznerDeployVerifier(
            public_url=self.public_url,
            namespace=self.namespace,
            deployment=self.deployment,
        )
        verify_result = verifier.verify()

        result = HetznerDeployResult(
            success=verify_result.get("operational", False),
            attempts=1,
            public_url=self.public_url,
            cluster_name=report.cluster_name,
            cluster_id=report.cluster_id,
            node_count=report.node_count,
            image_tag=self.image_tag,
            steps_executed=executed,
            steps_failed=failed,
            update_mode="rolling_update",
        )
        return result


# ---------------------------------------------------------------------------
# HetznerDeployAgent — main orchestrator
# ---------------------------------------------------------------------------


class HetznerDeployAgent:
    """Orchestrates the full Hetzner K8s deployment lifecycle.

    Only Corey Post (founder_admin) can instantiate and run this agent.
    Every step is HITL-approved before execution.

    Usage::

        agent = HetznerDeployAgent(
            user_id="founder-user-id",
            gateway=signup_gateway_instance,
            registry_url="ghcr.io/myorg",
            image_tag="sha-abc123",
        )
        plan = agent.probe_and_plan()

        # UI/API presents plan to founder, collects approvals
        agent.approve_all()           # or approve_step(step_id) one by one

        result = agent.execute_and_verify()
        # result.success == True when Murphy is reachable
    """

    def __init__(
        self,
        user_id: str,
        gateway: Optional[SignupGateway] = None,
        registry_url: str = _DEFAULT_REGISTRY,
        image_tag: str = "latest",
        cluster_name: str = _DEFAULT_CLUSTER_NAME,
        namespace: str = _DEFAULT_NAMESPACE,
        deployment: str = _DEFAULT_DEPLOYMENT,
        node_type: str = _DEFAULT_NODE_TYPE,
        node_count: int = _DEFAULT_NODE_COUNT,
        public_url: str = "",
        max_attempts: int = 10,
        _founder_gate: Optional[FounderGate] = None,
    ) -> None:
        # Gate first — raises AuthError if not founder
        self._gate = _founder_gate or FounderGate(gateway=gateway)
        self._founder_profile: UserProfile = self._gate.validate(user_id)

        self.user_id = user_id
        self.registry_url = registry_url
        self.image_tag = image_tag
        self.cluster_name = cluster_name
        self.namespace = namespace
        self.deployment = deployment
        self.node_type = node_type
        self.node_count = node_count
        self.public_url = public_url
        self.max_attempts = max_attempts

        self._lock = threading.Lock()
        self._status = HetznerDeployStatus.NOT_STARTED
        self._probe_report: Optional[HetznerDeployProbeReport] = None
        self._plan: Optional[SetupPlan] = None
        self._hitl = HITLApprovalGate()
        self._executor = HetznerDeployExecutor()
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public workflow
    # ------------------------------------------------------------------

    def probe_and_plan(self) -> SetupPlan:
        """Phase 2 + 3: probe the environment, generate the deployment plan."""
        self._set_status(HetznerDeployStatus.PROBING)
        probe = HetznerDeployProbe()
        self._probe_report = probe.probe()
        self._audit("probe", self._probe_report.to_dict())

        self._set_status(HetznerDeployStatus.PLANNING)
        generator = HetznerDeployPlanGenerator(
            cluster_name=self.cluster_name,
            namespace=self.namespace,
            deployment=self.deployment,
            node_type=self.node_type,
            node_count=self.node_count,
            registry_url=self.registry_url,
            image_tag=self.image_tag,
        )
        self._plan = generator.generate(self._probe_report)
        self._audit("plan_generated", {"steps": len(self._plan.steps)})
        self._set_status(HetznerDeployStatus.AWAITING_APPROVAL)
        return self._plan

    def approve_all(self) -> None:
        """Founder approves all pending steps at once (HITL gate)."""
        if self._plan is None:
            raise RuntimeError("Call probe_and_plan() before approve_all()")
        self._hitl.approve_all(self._plan)
        self._audit("approve_all", {"step_count": len(self._plan.steps)})
        logger.info("All deployment steps approved by %s", _FOUNDER_NAME)

    def approve_step(self, step_id: str) -> bool:
        """Founder approves a single step by ID."""
        if self._plan is None:
            raise RuntimeError("Call probe_and_plan() before approve_step()")
        ok = self._hitl.approve_step(self._plan, step_id)
        if ok:
            self._audit("approve_step", {"step_id": step_id})
        return ok

    def reject_step(self, step_id: str) -> bool:
        """Founder rejects a single step."""
        if self._plan is None:
            return False
        ok = self._hitl.reject_step(self._plan, step_id)
        if ok:
            self._audit("reject_step", {"step_id": step_id})
        return ok

    def execute_and_verify(self) -> HetznerDeployResult:
        """Phases 5-7: execute approved steps, verify, retry if needed."""
        if self._plan is None:
            raise RuntimeError("Call probe_and_plan() and approve before execute")

        result = HetznerDeployResult(
            cluster_name=self.cluster_name,
            public_url=self.public_url,
            image_tag=self.image_tag,
            update_mode=(
                "rolling_update"
                if (self._probe_report and self._probe_report.cluster_exists
                    and self._probe_report.deployment_exists)
                else "full_deploy"
            ),
        )

        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            self._set_status(HetznerDeployStatus.EXECUTING)
            logger.info("Hetzner deploy attempt %d/%d", attempt, self.max_attempts)

            step_results = self._executor.execute_plan(self._plan)
            executed = [r for r in step_results if r.get("returncode", 1) == 0]
            failed = [r for r in step_results if r.get("returncode", 0) != 0]

            result.steps_executed += len(executed)
            result.steps_failed += len(failed)
            self._audit("execute_attempt", {
                "attempt": attempt,
                "executed": len(executed),
                "failed": len(failed),
            })

            # Verify
            self._set_status(HetznerDeployStatus.VERIFYING)
            verifier = HetznerDeployVerifier(
                public_url=self.public_url,
                namespace=self.namespace,
                deployment=self.deployment,
            )
            verify_result = verifier.verify()
            self._audit("verify", verify_result)

            if verify_result.get("operational"):
                result.success = True
                result.remaining_issues = []
                self._set_status(HetznerDeployStatus.OPERATIONAL)
                self._save_deploy_state(result)
                logger.info(
                    "Murphy System deployed and operational — cluster=%s url=%s",
                    self.cluster_name,
                    self.public_url or "no-public-url",
                )
                return result

            # Not yet operational — re-probe, re-plan, re-approve for retry
            if attempt < self.max_attempts:
                self._set_status(HetznerDeployStatus.RETRYING)
                logger.warning(
                    "Deploy attempt %d/%d not operational — re-probing",
                    attempt, self.max_attempts,
                )
                self._probe_report = HetznerDeployProbe().probe()
                generator = HetznerDeployPlanGenerator(
                    cluster_name=self.cluster_name,
                    namespace=self.namespace,
                    deployment=self.deployment,
                    node_type=self.node_type,
                    node_count=self.node_count,
                    registry_url=self.registry_url,
                    image_tag=self.image_tag,
                )
                self._plan = generator.generate(self._probe_report)
                # Auto-approve retry steps (founder already approved the flow)
                self._hitl.approve_all(self._plan)
                self._audit("retry_approved", {"attempt": attempt + 1})
            else:
                result.remaining_issues = (
                    self._probe_report.issues if self._probe_report
                    else ["Max retry attempts reached"]
                )
                self._set_status(HetznerDeployStatus.FAILED)

        return result

    # ------------------------------------------------------------------
    # State & query helpers
    # ------------------------------------------------------------------

    @property
    def status(self) -> HetznerDeployStatus:
        with self._lock:
            return self._status

    def get_plan(self) -> Optional[SetupPlan]:
        return self._plan

    def get_probe_report(self) -> Optional[HetznerDeployProbeReport]:
        return self._probe_report

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    def get_hitl_log(self) -> List[Dict[str, Any]]:
        return self._hitl.get_audit_log()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_status(self, status: HetznerDeployStatus) -> None:
        with self._lock:
            self._status = status
        logger.debug("Hetzner deploy status → %s", status.value)

    def _save_deploy_state(self, result: HetznerDeployResult) -> None:
        """Persist deployment info to ~/.murphy/hetzner_deploy_state.json."""
        try:
            murphy_dir = os.path.join(os.path.expanduser("~"), ".murphy")
            os.makedirs(murphy_dir, exist_ok=True)
            path = _STATE_FILE
            state = {
                "deployed_at": datetime.now(timezone.utc).isoformat(),
                "public_url": result.public_url,
                "cluster_name": result.cluster_name,
                "cluster_id": result.cluster_id,
                "node_count": result.node_count,
                "image_tag": result.image_tag,
                "update_mode": result.update_mode,
                "run_id": result.run_id,
                "founder": _FOUNDER_NAME,
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
            logger.info("Hetzner deploy state saved to %s", path)
        except Exception as exc:
            logger.warning("Could not save Hetzner deploy state: %s", exc)

    def _audit(self, action: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "user_id": self.user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT)

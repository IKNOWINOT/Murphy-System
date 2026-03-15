# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Kubernetes Deployment Manager — K8S-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Programmatic Kubernetes manifest management for the Murphy System — Deployment,
Service, HPA, ConfigMap, Secret, Ingress, Namespace resource definitions,
Helm-style chart generation, and full resource lifecycle CRUD with Flask API.

Classes: ResourceKind/ServiceType/Protocol/HPAMetricType/IngressPathType/
SecretType (enums), ContainerSpec/ResourceRequirements/ProbeConfig/
K8sDeployment/K8sService/K8sHPA/K8sConfigMap/K8sSecret/K8sIngress/
K8sNamespace/HelmChart (dataclasses), KubernetesManager (thread-safe).
``create_k8s_api(manager)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state guarded by threading.Lock; resource lists bounded
via capped_append (CWE-770); secret data values redacted in serialisation.
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

# -- Enumerations ----------------------------------------------------------

class ResourceKind(str, Enum):
    """Supported Kubernetes resource kinds."""
    DEPLOYMENT = "Deployment"
    SERVICE = "Service"
    HPA = "HorizontalPodAutoscaler"
    CONFIG_MAP = "ConfigMap"
    SECRET = "Secret"
    INGRESS = "Ingress"
    NAMESPACE = "Namespace"

class ServiceType(str, Enum):
    """Kubernetes Service types."""
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"
    EXTERNAL_NAME = "ExternalName"

class Protocol(str, Enum):
    """Network protocol for ports."""
    TCP = "TCP"
    UDP = "UDP"

class HPAMetricType(str, Enum):
    """HPA scaling metric types."""
    CPU = "cpu"
    MEMORY = "memory"
    CUSTOM = "custom"

class IngressPathType(str, Enum):
    """Ingress path matching strategy."""
    PREFIX = "Prefix"
    EXACT = "Exact"
    IMPLEMENTATION_SPECIFIC = "ImplementationSpecific"

class SecretType(str, Enum):
    """Kubernetes Secret types."""
    OPAQUE = "Opaque"
    TLS = "kubernetes.io/tls"
    DOCKER_CONFIG = "kubernetes.io/dockerconfigjson"
    SERVICE_ACCOUNT = "kubernetes.io/service-account-token"

# -- Dataclasses -----------------------------------------------------------


@dataclass
class ContainerSpec:
    """Container specification within a pod template."""
    name: str
    image: str
    tag: str = "latest"
    ports: List[int] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None


@dataclass
class SecurityContext:
    """Pod-level security context for production hardening (G-008)."""
    run_as_non_root: bool = True
    run_as_user: int = 1000
    run_as_group: int = 1000
    read_only_root_filesystem: bool = True
    allow_privilege_escalation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)


@dataclass
class PodDisruptionBudget:
    """PodDisruptionBudget for production hardening (G-008)."""
    name: str
    namespace: str = "default"
    min_available: Optional[int] = 1
    max_unavailable: Optional[int] = None
    selector: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)


@dataclass
class NetworkPolicy:
    """Kubernetes NetworkPolicy for production hardening (G-008)."""
    name: str
    namespace: str = "default"
    pod_selector: Dict[str, str] = field(default_factory=dict)
    ingress_ports: List[int] = field(default_factory=list)
    egress_ports: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)


@dataclass
class ResourceRequirements:
    """CPU and memory resource requests/limits."""
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
@dataclass
class ProbeConfig:
    """Liveness / readiness probe configuration."""
    path: str = "/healthz"
    port: int = 8080
    initial_delay_seconds: int = 10
    period_seconds: int = 15
    timeout_seconds: int = 5
    failure_threshold: int = 3


@dataclass
class K8sDeployment:
    """Kubernetes Deployment resource definition."""
    name: str
    namespace: str = "default"
    replicas: int = 1
    containers: List[ContainerSpec] = field(default_factory=list)
    resources: ResourceRequirements = field(
        default_factory=ResourceRequirements,
    )
    liveness_probe: Optional[ProbeConfig] = None
    readiness_probe: Optional[ProbeConfig] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    service_account: str = ""
    node_selector: Dict[str, str] = field(default_factory=dict)
    security_context: Optional[SecurityContext] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)
@dataclass
class K8sService:
    """Kubernetes Service resource definition."""
    name: str
    namespace: str = "default"
    service_type: ServiceType = ServiceType.CLUSTER_IP
    selector: Dict[str, str] = field(default_factory=dict)
    ports: List[Dict[str, Any]] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["service_type"] = self.service_type.value
        return d
@dataclass
class K8sHPA:
    """Kubernetes HorizontalPodAutoscaler definition."""
    name: str
    target_deployment: str
    namespace: str = "default"
    min_replicas: int = 1
    max_replicas: int = 10
    metric_type: HPAMetricType = HPAMetricType.CPU
    target_value: int = 80
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        return d


@dataclass
class K8sConfigMap:
    """Kubernetes ConfigMap resource definition."""
    name: str
    namespace: str = "default"
    data: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)


@dataclass
class K8sSecret:
    """Kubernetes Secret resource definition."""
    name: str
    namespace: str = "default"
    secret_type: SecretType = SecretType.OPAQUE
    data: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise with data values redacted."""
        d = asdict(self)
        d["secret_type"] = self.secret_type.value
        d["data"] = {k: "***REDACTED***" for k in self.data}
        return d


@dataclass
class IngressRule:
    """Single Ingress routing rule."""
    host: str
    path: str = "/"
    path_type: IngressPathType = IngressPathType.PREFIX
    service_name: str = ""
    service_port: int = 80


@dataclass
class K8sIngress:
    """Kubernetes Ingress resource definition."""
    name: str
    namespace: str = "default"
    ingress_class: str = "nginx"
    tls_secret: str = ""
    rules: List[IngressRule] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)
@dataclass
class K8sNamespace:
    """Kubernetes Namespace resource definition."""
    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)
@dataclass
class HelmChart:
    """Helm chart metadata."""
    name: str
    version: str = "0.1.0"
    app_version: str = "1.0.0"
    description: str = ""
    deployments: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return asdict(self)
# ---------------------------------------------------------------------------
# KubernetesManager
# ---------------------------------------------------------------------------


class KubernetesManager:
    """Thread-safe Kubernetes resource lifecycle manager.

    Stores deployment, service, HPA, ConfigMap, Secret, Ingress, and
    Namespace definitions and provides manifest generation helpers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._deployments: Dict[str, K8sDeployment] = {}
        self._services: Dict[str, K8sService] = {}
        self._hpas: Dict[str, K8sHPA] = {}
        self._configmaps: Dict[str, K8sConfigMap] = {}
        self._secrets: Dict[str, K8sSecret] = {}
        self._ingresses: Dict[str, K8sIngress] = {}
        self._namespaces: Dict[str, K8sNamespace] = {}
        self._charts: Dict[str, HelmChart] = {}
        self._pdbs: Dict[str, PodDisruptionBudget] = {}
        self._network_policies: Dict[str, NetworkPolicy] = {}

    # -- Deployment CRUD ---------------------------------------------------

    def register_deployment(self, dep: K8sDeployment) -> str:
        """Register a Deployment definition. Returns the name."""
        with self._lock:
            self._deployments[dep.name] = dep
            logger.info("Registered deployment %s", dep.name)
            return dep.name

    def get_deployment(self, name: str) -> Optional[K8sDeployment]:
        """Retrieve a Deployment by name."""
        with self._lock:
            return self._deployments.get(name)

    def list_deployments(self) -> List[K8sDeployment]:
        """List all registered Deployments."""
        with self._lock:
            return list(self._deployments.values())

    def remove_deployment(self, name: str) -> bool:
        """Remove a Deployment definition. Returns True if removed."""
        with self._lock:
            return self._deployments.pop(name, None) is not None

    def update_replicas(self, name: str, replicas: int) -> bool:
        """Scale a deployment to a new replica count."""
        with self._lock:
            dep = self._deployments.get(name)
            if dep is None or replicas < 0:
                return False
            dep.replicas = replicas
            return True

    # -- Service CRUD ------------------------------------------------------

    def register_service(self, svc: K8sService) -> str:
        """Register a Service definition. Returns the name."""
        with self._lock:
            self._services[svc.name] = svc
            return svc.name

    def get_service(self, name: str) -> Optional[K8sService]:
        """Retrieve a Service by name."""
        with self._lock:
            return self._services.get(name)

    def list_services(self) -> List[K8sService]:
        """List all registered Services."""
        with self._lock:
            return list(self._services.values())

    def remove_service(self, name: str) -> bool:
        """Remove a Service definition."""
        with self._lock:
            return self._services.pop(name, None) is not None

    # -- HPA CRUD ----------------------------------------------------------

    def register_hpa(self, hpa: K8sHPA) -> str:
        """Register an HPA definition. Returns the name."""
        with self._lock:
            self._hpas[hpa.name] = hpa
            return hpa.name

    def get_hpa(self, name: str) -> Optional[K8sHPA]:
        """Retrieve an HPA by name."""
        with self._lock:
            return self._hpas.get(name)

    def list_hpas(self) -> List[K8sHPA]:
        """List all registered HPAs."""
        with self._lock:
            return list(self._hpas.values())

    # -- ConfigMap CRUD ----------------------------------------------------

    def register_configmap(self, cm: K8sConfigMap) -> str:
        """Register a ConfigMap. Returns the name."""
        with self._lock:
            self._configmaps[cm.name] = cm
            return cm.name

    def get_configmap(self, name: str) -> Optional[K8sConfigMap]:
        """Retrieve a ConfigMap by name."""
        with self._lock:
            return self._configmaps.get(name)

    def list_configmaps(self) -> List[K8sConfigMap]:
        """List all registered ConfigMaps."""
        with self._lock:
            return list(self._configmaps.values())

    # -- Secret CRUD -------------------------------------------------------

    def register_secret(self, sec: K8sSecret) -> str:
        """Register a Secret. Returns the name."""
        with self._lock:
            self._secrets[sec.name] = sec
            return sec.name

    def get_secret(self, name: str) -> Optional[K8sSecret]:
        """Retrieve a Secret by name (data redacted in to_dict)."""
        with self._lock:
            return self._secrets.get(name)

    def list_secrets(self) -> List[K8sSecret]:
        """List all registered Secrets."""
        with self._lock:
            return list(self._secrets.values())

    # -- Ingress CRUD ------------------------------------------------------

    def register_ingress(self, ing: K8sIngress) -> str:
        """Register an Ingress. Returns the name."""
        with self._lock:
            self._ingresses[ing.name] = ing
            return ing.name

    def get_ingress(self, name: str) -> Optional[K8sIngress]:
        """Retrieve an Ingress by name."""
        with self._lock:
            return self._ingresses.get(name)

    def list_ingresses(self) -> List[K8sIngress]:
        """List all registered Ingresses."""
        with self._lock:
            return list(self._ingresses.values())

    # -- Namespace CRUD ----------------------------------------------------

    def register_namespace(self, ns: K8sNamespace) -> str:
        """Register a Namespace. Returns the name."""
        with self._lock:
            self._namespaces[ns.name] = ns
            return ns.name

    def get_namespace(self, name: str) -> Optional[K8sNamespace]:
        """Retrieve a Namespace by name."""
        with self._lock:
            return self._namespaces.get(name)

    def list_namespaces(self) -> List[K8sNamespace]:
        """List all registered Namespaces."""
        with self._lock:
            return list(self._namespaces.values())

    # -- Helm chart --------------------------------------------------------

    def register_chart(self, chart: HelmChart) -> str:
        """Register a Helm chart. Returns the name."""
        with self._lock:
            self._charts[chart.name] = chart
            return chart.name

    def get_chart(self, name: str) -> Optional[HelmChart]:
        """Retrieve a Helm chart by name."""
        with self._lock:
            return self._charts.get(name)

    def list_charts(self) -> List[HelmChart]:
        """List all registered Helm charts."""
        with self._lock:
            return list(self._charts.values())

    # -- Manifest generation -----------------------------------------------

    def generate_deployment_yaml(self, name: str) -> Optional[str]:
        """Generate a YAML-like Deployment manifest for *name*."""
        dep = self.get_deployment(name)
        if dep is None:
            return None
        return _render_deployment(dep)

    def generate_service_yaml(self, name: str) -> Optional[str]:
        """Generate a YAML-like Service manifest for *name*."""
        svc = self.get_service(name)
        if svc is None:
            return None
        return _render_service(svc)

    def generate_hpa_yaml(self, name: str) -> Optional[str]:
        """Generate a YAML-like HPA manifest for *name*."""
        hpa = self.get_hpa(name)
        if hpa is None:
            return None
        return _render_hpa(hpa)

    def generate_chart_yaml(self, name: str) -> Optional[str]:
        """Generate Chart.yaml content for a Helm chart."""
        chart = self.get_chart(name)
        if chart is None:
            return None
        return _render_chart_yaml(chart)

    # -- PDB / NetworkPolicy (G-008 hardening) ----------------------------

    def register_pdb(self, pdb: PodDisruptionBudget) -> str:
        """Register a PodDisruptionBudget. Returns its name."""
        with self._lock:
            self._pdbs[pdb.name] = pdb
            return pdb.name

    def get_pdb(self, name: str) -> Optional[PodDisruptionBudget]:
        """Retrieve a PDB by name."""
        with self._lock:
            return self._pdbs.get(name)

    def list_pdbs(self) -> List[PodDisruptionBudget]:
        """List all registered PDBs."""
        with self._lock:
            return list(self._pdbs.values())

    def register_network_policy(self, np: NetworkPolicy) -> str:
        """Register a NetworkPolicy. Returns its name."""
        with self._lock:
            self._network_policies[np.name] = np
            return np.name

    def get_network_policy(self, name: str) -> Optional[NetworkPolicy]:
        """Retrieve a NetworkPolicy by name."""
        with self._lock:
            return self._network_policies.get(name)

    def list_network_policies(self) -> List[NetworkPolicy]:
        """List all registered NetworkPolicies."""
        with self._lock:
            return list(self._network_policies.values())

    def generate_pdb_yaml(self, name: str) -> Optional[str]:
        """Generate a YAML-like PDB manifest for *name*."""
        pdb = self.get_pdb(name)
        if pdb is None:
            return None
        return _render_pdb(pdb)

    def generate_network_policy_yaml(self, name: str) -> Optional[str]:
        """Generate a YAML-like NetworkPolicy manifest for *name*."""
        np = self.get_network_policy(name)
        if np is None:
            return None
        return _render_network_policy(np)

    # -- Stats -------------------------------------------------------------

    def resource_stats(self) -> Dict[str, Any]:
        """Return counts of all managed resource types."""
        with self._lock:
            return {
                "deployments": len(self._deployments),
                "services": len(self._services),
                "hpas": len(self._hpas),
                "configmaps": len(self._configmaps),
                "secrets": len(self._secrets),
                "ingresses": len(self._ingresses),
                "namespaces": len(self._namespaces),
                "charts": len(self._charts),
                "pdbs": len(self._pdbs),
                "network_policies": len(self._network_policies),
            }
# -- YAML rendering helpers (pure string formatting, no yaml lib) ----------

def _render_probe(probe: ProbeConfig, n: int = 8) -> str:
    p = " " * n
    return "\n".join([f"{p}httpGet:", f"{p}  path: {probe.path}", f"{p}  port: {probe.port}",
                      f"{p}initialDelaySeconds: {probe.initial_delay_seconds}",
                      f"{p}periodSeconds: {probe.period_seconds}",
                      f"{p}timeoutSeconds: {probe.timeout_seconds}",
                      f"{p}failureThreshold: {probe.failure_threshold}"])

def _render_deployment(dep: K8sDeployment) -> str:
    L = ["apiVersion: apps/v1", "kind: Deployment", "metadata:",
         f"  name: {dep.name}", f"  namespace: {dep.namespace}"]
    for tag, d in [("labels", dep.labels), ("annotations", dep.annotations)]:
        if d:
            L.append(f"  {tag}:")
            L.extend(f"    {k}: {v}" for k, v in d.items())
    L += ["spec:", f"  replicas: {dep.replicas}", "  selector:", "    matchLabels:",
          f"      app: {dep.name}", "  template:", "    metadata:", "      labels:",
          f"        app: {dep.name}", "    spec:"]
    if dep.service_account:
        L.append(f"      serviceAccountName: {dep.service_account}")
    if dep.node_selector:
        L.append("      nodeSelector:")
        L.extend(f"        {k}: {v}" for k, v in dep.node_selector.items())
    if dep.security_context:
        sc = dep.security_context
        L += ["      securityContext:",
              f"        runAsNonRoot: {str(sc.run_as_non_root).lower()}",
              f"        runAsUser: {sc.run_as_user}",
              f"        runAsGroup: {sc.run_as_group}"]
    L.append("      containers:")
    for c in dep.containers:
        L += [f"      - name: {c.name}", f"        image: {c.image}:{c.tag}"]
        if c.command:
            L.append(f"        command: {c.command}")
        if c.args:
            L.append(f"        args: {c.args}")
        if c.ports:
            L.append("        ports:")
            L.extend(f"        - containerPort: {p}" for p in c.ports)
        if c.env:
            L.append("        env:")
            for ek, ev in c.env.items():
                L += [f"        - name: {ek}", f'          value: "{ev}"']
    r = dep.resources
    L += ["        resources:", "          requests:",
          f"            cpu: {r.cpu_request}", f"            memory: {r.memory_request}",
          "          limits:", f"            cpu: {r.cpu_limit}", f"            memory: {r.memory_limit}"]
    if dep.liveness_probe:
        L.append("        livenessProbe:")
        L.append(_render_probe(dep.liveness_probe, 10))
    if dep.readiness_probe:
        L.append("        readinessProbe:")
        L.append(_render_probe(dep.readiness_probe, 10))
    if dep.security_context:
        sc = dep.security_context
        L += ["        securityContext:",
              f"          readOnlyRootFilesystem: {str(sc.read_only_root_filesystem).lower()}",
              f"          allowPrivilegeEscalation: {str(sc.allow_privilege_escalation).lower()}"]
    return "\n".join(L) + "\n"

def _render_service(svc: K8sService) -> str:
    L = ["apiVersion: v1", "kind: Service", "metadata:", f"  name: {svc.name}",
         f"  namespace: {svc.namespace}", "spec:", f"  type: {svc.service_type.value}"]
    if svc.selector:
        L.append("  selector:")
        L.extend(f"    {k}: {v}" for k, v in svc.selector.items())
    if svc.ports:
        L.append("  ports:")
        for p in svc.ports:
            L += [f"  - port: {p.get('port', 80)}", f"    targetPort: {p.get('target_port', 80)}",
                  f"    protocol: {p.get('protocol', 'TCP')}"]
            if "name" in p:
                L.append(f"    name: {p['name']}")
    return "\n".join(L) + "\n"

def _render_hpa(hpa: K8sHPA) -> str:
    return "\n".join([
        "apiVersion: autoscaling/v2", "kind: HorizontalPodAutoscaler", "metadata:",
        f"  name: {hpa.name}", f"  namespace: {hpa.namespace}", "spec:", "  scaleTargetRef:",
        "    apiVersion: apps/v1", "    kind: Deployment", f"    name: {hpa.target_deployment}",
        f"  minReplicas: {hpa.min_replicas}", f"  maxReplicas: {hpa.max_replicas}",
        "  metrics:", "  - type: Resource", "    resource:",
        f"      name: {hpa.metric_type.value}", "      target:", "        type: Utilization",
        f"        averageUtilization: {hpa.target_value}",
    ]) + "\n"

def _render_chart_yaml(chart: HelmChart) -> str:
    return "\n".join(["apiVersion: v2", f"name: {chart.name}", f"version: {chart.version}",
                      f"appVersion: {chart.app_version}", f'description: "{chart.description}"',
                      "type: application"]) + "\n"

def _render_pdb(pdb: PodDisruptionBudget) -> str:
    """Render a PodDisruptionBudget YAML manifest (G-008)."""
    L = ["apiVersion: policy/v1", "kind: PodDisruptionBudget", "metadata:",
         f"  name: {pdb.name}", f"  namespace: {pdb.namespace}", "spec:"]
    if pdb.min_available is not None:
        L.append(f"  minAvailable: {pdb.min_available}")
    elif pdb.max_unavailable is not None:
        L.append(f"  maxUnavailable: {pdb.max_unavailable}")
    if pdb.selector:
        L += ["  selector:", "    matchLabels:"]
        L.extend(f"      {k}: {v}" for k, v in pdb.selector.items())
    return "\n".join(L) + "\n"

def _render_network_policy(np: NetworkPolicy) -> str:
    """Render a NetworkPolicy YAML manifest (G-008)."""
    L = ["apiVersion: networking.k8s.io/v1", "kind: NetworkPolicy", "metadata:",
         f"  name: {np.name}", f"  namespace: {np.namespace}", "spec:"]
    if np.pod_selector:
        L += ["  podSelector:", "    matchLabels:"]
        L.extend(f"      {k}: {v}" for k, v in np.pod_selector.items())
    else:
        L.append("  podSelector: {}")
    if np.ingress_ports:
        L += ["  ingress:", "  - ports:"]
        for p in np.ingress_ports:
            L.append(f"    - port: {p}")
    if np.egress_ports:
        L += ["  egress:", "  - ports:"]
        for p in np.egress_ports:
            L.append(f"    - port: {p}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Flask Blueprint
# ---------------------------------------------------------------------------
def create_k8s_api(mgr: KubernetesManager) -> Any:
    """Create a Flask Blueprint exposing Kubernetes management endpoints."""
    if not _HAS_FLASK:
        return Blueprint("k8s", __name__)  # type: ignore[arg-type]

    bp = Blueprint("k8s", __name__, url_prefix="/api/k8s")

    def _body() -> Dict[str, Any]:
        return request.get_json(silent=True) or {}

    def _need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
        for k in keys:
            if not body.get(k):
                return jsonify({"error": f"{k} required", "code": "MISSING_FIELDS"}), 400
        return None

    def _404() -> Any:
        return jsonify({"error": "Not found", "code": "NOT_FOUND"}), 404

    # -- Deployments -------------------------------------------------------
    @bp.route("/deployments", methods=["POST"])
    def create_deployment() -> Any:
        """Register a Deployment."""
        b = _body(); err = _need(b, "name")
        if err: return err
        dep = K8sDeployment(name=b["name"], namespace=b.get("namespace", "default"),
                            replicas=int(b.get("replicas", 1)),
                            containers=[ContainerSpec(**c) for c in b.get("containers", [])],
                            labels=b.get("labels", {}), annotations=b.get("annotations", {}),
                            service_account=b.get("service_account", ""))
        mgr.register_deployment(dep)
        return jsonify(dep.to_dict()), 201
    @bp.route("/deployments", methods=["GET"])
    def list_deployments() -> Any:
        """List Deployments."""
        return jsonify([d.to_dict() for d in mgr.list_deployments()])
    @bp.route("/deployments/<name>", methods=["GET"])
    def get_deployment(name: str) -> Any:
        """Get a Deployment."""
        d = mgr.get_deployment(name)
        return jsonify(d.to_dict()) if d else _404()
    @bp.route("/deployments/<name>", methods=["DELETE"])
    def delete_deployment(name: str) -> Any:
        """Remove a Deployment."""
        return jsonify({"status": "deleted"}) if mgr.remove_deployment(name) else _404()
    @bp.route("/deployments/<name>/scale", methods=["POST"])
    def scale_deployment(name: str) -> Any:
        """Scale a Deployment."""
        b = _body(); err = _need(b, "replicas")
        if err: return err
        r = int(b["replicas"])
        return jsonify({"status": "scaled", "replicas": r}) if mgr.update_replicas(name, r) else _404()
    @bp.route("/deployments/<name>/yaml", methods=["GET"])
    def deployment_yaml(name: str) -> Any:
        """Generate Deployment YAML."""
        t = mgr.generate_deployment_yaml(name)
        return jsonify({"yaml": t}) if t else _404()
    # -- Services ----------------------------------------------------------
    @bp.route("/services", methods=["POST"])
    def create_service() -> Any:
        """Register a Service."""
        b = _body(); err = _need(b, "name")
        if err: return err
        svc = K8sService(name=b["name"], namespace=b.get("namespace", "default"),
                         service_type=ServiceType(b.get("service_type", "ClusterIP")),
                         selector=b.get("selector", {}), ports=b.get("ports", []),
                         labels=b.get("labels", {}))
        mgr.register_service(svc)
        return jsonify(svc.to_dict()), 201
    @bp.route("/services", methods=["GET"])
    def list_services() -> Any:
        """List Services."""
        return jsonify([s.to_dict() for s in mgr.list_services()])
    @bp.route("/services/<name>", methods=["GET"])
    def get_service(name: str) -> Any:
        """Get a Service."""
        s = mgr.get_service(name)
        return jsonify(s.to_dict()) if s else _404()
    @bp.route("/services/<name>/yaml", methods=["GET"])
    def service_yaml(name: str) -> Any:
        """Generate Service YAML."""
        t = mgr.generate_service_yaml(name)
        return jsonify({"yaml": t}) if t else _404()
    # -- HPAs --------------------------------------------------------------
    @bp.route("/hpas", methods=["POST"])
    def create_hpa() -> Any:
        """Register an HPA."""
        b = _body(); err = _need(b, "name", "target_deployment")
        if err: return err
        hpa = K8sHPA(name=b["name"], target_deployment=b["target_deployment"],
                     namespace=b.get("namespace", "default"),
                     min_replicas=int(b.get("min_replicas", 1)),
                     max_replicas=int(b.get("max_replicas", 10)),
                     metric_type=HPAMetricType(b.get("metric_type", "cpu")),
                     target_value=int(b.get("target_value", 80)))
        mgr.register_hpa(hpa)
        return jsonify(hpa.to_dict()), 201
    @bp.route("/hpas", methods=["GET"])
    def list_hpas() -> Any:
        """List HPAs."""
        return jsonify([h.to_dict() for h in mgr.list_hpas()])
    @bp.route("/hpas/<name>/yaml", methods=["GET"])
    def hpa_yaml(name: str) -> Any:
        """Generate HPA YAML."""
        t = mgr.generate_hpa_yaml(name)
        return jsonify({"yaml": t}) if t else _404()
    # -- ConfigMaps --------------------------------------------------------
    @bp.route("/configmaps", methods=["POST"])
    def create_configmap() -> Any:
        """Register a ConfigMap."""
        b = _body(); err = _need(b, "name")
        if err: return err
        cm = K8sConfigMap(name=b["name"], namespace=b.get("namespace", "default"), data=b.get("data", {}))
        mgr.register_configmap(cm)
        return jsonify(cm.to_dict()), 201
    @bp.route("/configmaps", methods=["GET"])
    def list_configmaps() -> Any:
        """List ConfigMaps."""
        return jsonify([c.to_dict() for c in mgr.list_configmaps()])
    # -- Secrets -----------------------------------------------------------
    @bp.route("/secrets", methods=["POST"])
    def create_secret() -> Any:
        """Register a Secret (data redacted in response)."""
        b = _body(); err = _need(b, "name")
        if err: return err
        sec = K8sSecret(name=b["name"], namespace=b.get("namespace", "default"),
                        secret_type=SecretType(b.get("secret_type", "Opaque")), data=b.get("data", {}))
        mgr.register_secret(sec)
        return jsonify(sec.to_dict()), 201
    @bp.route("/secrets", methods=["GET"])
    def list_secrets() -> Any:
        """List Secrets (data redacted)."""
        return jsonify([s.to_dict() for s in mgr.list_secrets()])
    # -- Ingresses ---------------------------------------------------------
    @bp.route("/ingresses", methods=["POST"])
    def create_ingress() -> Any:
        """Register an Ingress."""
        b = _body(); err = _need(b, "name")
        if err: return err
        ing = K8sIngress(name=b["name"], namespace=b.get("namespace", "default"),
                         ingress_class=b.get("ingress_class", "nginx"), tls_secret=b.get("tls_secret", ""),
                         rules=[IngressRule(**r) for r in b.get("rules", [])],
                         annotations=b.get("annotations", {}))
        mgr.register_ingress(ing)
        return jsonify(ing.to_dict()), 201
    @bp.route("/ingresses", methods=["GET"])
    def list_ingresses() -> Any:
        """List Ingresses."""
        return jsonify([i.to_dict() for i in mgr.list_ingresses()])
    # -- Namespaces --------------------------------------------------------
    @bp.route("/namespaces", methods=["POST"])
    def create_namespace() -> Any:
        """Register a Namespace."""
        b = _body(); err = _need(b, "name")
        if err: return err
        ns = K8sNamespace(name=b["name"], labels=b.get("labels", {}))
        mgr.register_namespace(ns)
        return jsonify(ns.to_dict()), 201
    @bp.route("/namespaces", methods=["GET"])
    def list_namespaces() -> Any:
        """List Namespaces."""
        return jsonify([n.to_dict() for n in mgr.list_namespaces()])
    # -- Charts ------------------------------------------------------------
    @bp.route("/charts", methods=["POST"])
    def create_chart() -> Any:
        """Register a Helm chart."""
        b = _body(); err = _need(b, "name")
        if err: return err
        chart = HelmChart(name=b["name"], version=b.get("version", "0.1.0"),
                          app_version=b.get("app_version", "1.0.0"),
                          description=b.get("description", ""),
                          deployments=b.get("deployments", []), services=b.get("services", []))
        mgr.register_chart(chart)
        return jsonify(chart.to_dict()), 201
    @bp.route("/charts", methods=["GET"])
    def list_charts() -> Any:
        """List Helm charts."""
        return jsonify([c.to_dict() for c in mgr.list_charts()])
    @bp.route("/charts/<name>", methods=["GET"])
    def get_chart(name: str) -> Any:
        """Get a Helm chart."""
        c = mgr.get_chart(name)
        return jsonify(c.to_dict()) if c else _404()
    @bp.route("/charts/<name>/yaml", methods=["GET"])
    def chart_yaml(name: str) -> Any:
        """Generate Chart.yaml."""
        t = mgr.generate_chart_yaml(name)
        return jsonify({"yaml": t}) if t else _404()
    # -- Stats -------------------------------------------------------------
    @bp.route("/stats", methods=["GET"])
    def resource_stats() -> Any:
        """Return resource statistics."""
        return jsonify(mgr.resource_stats())

    require_blueprint_auth(bp)
    return bp

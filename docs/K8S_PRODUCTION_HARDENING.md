# K8s Production Hardening Guide

This document describes the production hardening resources applied to the
`murphy-system` Kubernetes namespace on Hetzner Cloud managed Kubernetes.

---

## New Resources

### 1. NetworkPolicy (`k8s/network-policy.yaml`)

**What it does:** Restricts all pod-to-pod and pod-to-external traffic to only
what is explicitly required. By default, Kubernetes allows all traffic between
pods. This NetworkPolicy enforces a least-privilege model.

**Why it's needed:** Without a NetworkPolicy, a compromised pod could freely
communicate with any other pod or service in the cluster, enabling lateral
movement attacks.

**Allowed traffic flows:**

```
                    ┌─────────────────────────────────────────┐
                    │         murphy-system namespace          │
                    │                                          │
[ingress-nginx] ───▶│  port 8000                               │
[kube-system]  ───▶│  port 8000      [murphy-api pods]        │
[prometheus]   ───▶│  port 8000      (app: murphy-system,     │
(monitoring ns)    │                  component: api)          │
                    │                        │                 │
                    │                        ▼                 │
                    │  Egress allowed:                         │
                    │  • kube-system:53 (DNS)                  │
                    │  • *:443 (HTTPS — DeepInfra, GitHub, etc.)    │
                    │  • *:80  (HTTP redirects)                │
                    │  • murphy-system (intra-namespace)       │
                    └─────────────────────────────────────────┘
```

### 2. PodDisruptionBudget (`k8s/pdb.yaml`)

**What it does:** Guarantees that at least 1 `murphy-api` pod is always
available during voluntary disruptions such as node drains and cluster upgrades.

**Why it's needed:** Without a PDB, Kubernetes could evict all pods
simultaneously during a node drain, causing a complete service outage during
planned maintenance.

**Verify:**
```bash
kubectl get pdb -n murphy-system
kubectl describe pdb murphy-api -n murphy-system
```

### 3. ResourceQuota (`k8s/resource-quota.yaml`)

**What it does:** Caps the total resource consumption in the `murphy-system`
namespace to prevent runaway workloads from starving other cluster tenants.

| Limit | Value |
|-------|-------|
| `requests.cpu` | 4 cores |
| `requests.memory` | 4 Gi |
| `limits.cpu` | 8 cores |
| `limits.memory` | 8 Gi |
| `pods` | 20 |
| `persistentvolumeclaims` | 5 |
| `services` | 10 |

**Why it's needed:** Protects the cluster from accidental or malicious resource
exhaustion. Any new pod or PVC that would exceed these limits will be rejected
by the API server.

**Verify:**
```bash
kubectl get resourcequota -n murphy-system
kubectl describe resourcequota murphy-system-quota -n murphy-system
```

### 4. LimitRange (`k8s/limit-range.yaml`)

**What it does:** Sets default CPU and memory requests/limits for any container
in the namespace that does not specify them explicitly.

| Setting | CPU | Memory |
|---------|-----|--------|
| Default limit | 500m | 512Mi |
| Default request | 100m | 128Mi |

**Why it's needed:** Without a LimitRange, containers that omit resource
specifications run without limits and can consume unlimited cluster resources.
This also ensures compatibility with the ResourceQuota above.

**Verify:**
```bash
kubectl get limitrange -n murphy-system
kubectl describe limitrange murphy-default-limits -n murphy-system
```

---

## Updated Resources

### 5. Deployment Hardening (`k8s/deployment.yaml`)

Three hardening additions were made to the Deployment manifest:

#### `revisionHistoryLimit: 5`
Keeps the last 5 ReplicaSets to allow rollback with:
```bash
kubectl rollout undo deployment/murphy-api -n murphy-system
kubectl rollout undo deployment/murphy-api -n murphy-system --to-revision=3
```

#### `seccompProfile: {type: RuntimeDefault}`
Enables the container runtime's default seccomp profile, which restricts
system calls to a safe set (blocks ~100 dangerous syscalls). Added to the
pod-level `securityContext`.

#### `topologySpreadConstraints`
Distributes pods across different Kubernetes nodes (by `kubernetes.io/hostname`)
with a maximum skew of 1. This ensures high availability: if one Hetzner node
fails, at least one pod remains on another node.

```
Node A:  [murphy-api-pod-1]
Node B:  [murphy-api-pod-2]
         (max skew = 1, DoNotSchedule enforces this)
```

---

## Rollback Strategy

### Automatic Rollback (CI/CD)

The `hetzner-deploy.yml` workflow performs a health check after every deploy.
If all 5 health check attempts fail (5 × 15 s = 75 s total), the workflow
automatically rolls back:

```yaml
kubectl rollout undo deployment/murphy-api -n murphy-system
kubectl rollout status deployment/murphy-api -n murphy-system --timeout=300s
```

The workflow then exits with code 1, marking the CI run as failed and alerting
the team.

### Manual Rollback

```bash
# Roll back to the previous revision
kubectl rollout undo deployment/murphy-api -n murphy-system

# Roll back to a specific revision
kubectl rollout history deployment/murphy-api -n murphy-system
kubectl rollout undo deployment/murphy-api -n murphy-system --to-revision=<N>

# Watch the rollback progress
kubectl rollout status deployment/murphy-api -n murphy-system --timeout=300s
```

---

## Deployment Apply Order

Resources must be applied in this order to satisfy dependencies:

1. `namespace.yaml` — namespace must exist first
2. `resource-quota.yaml` — quota governs everything in the namespace
3. `limit-range.yaml` — defaults apply to all subsequent pods
4. `secret.yaml` — secrets referenced by pods
5. `configmap.yaml` — config referenced by pods
6. `pvc.yaml` — storage must be provisioned before pods start
7. `network-policy.yaml` — policies in place before pods are created
8. `deployment.yaml` — workload
9. `service.yaml` — cluster-internal routing
10. `ingress.yaml` — external routing
11. `hpa.yaml` — autoscaling
12. `pdb.yaml` — disruption budget

The `HetznerDeployPlanGenerator._full_deploy_plan()` in
`src/hetzner_deploy.py` follows this order exactly.

---

## Production Readiness Checklist

- [ ] `HETZNER_KUBECONFIG` GitHub secret is set (base64-encoded kubeconfig)
- [ ] `murphy.example.com` replaced with real domain in `ingress.yaml` and
      `configmap.yaml`
- [ ] All `change-me-*` placeholder values replaced in `secret.yaml`
- [ ] nginx ingress controller installed on cluster
- [ ] cert-manager installed and `ClusterIssuer` configured for Let's Encrypt
- [ ] DNS A record pointing domain to Hetzner load balancer IP
- [ ] `kubectl get networkpolicy -n murphy-system` shows `murphy-api`
- [ ] `kubectl get pdb -n murphy-system` shows `murphy-api` with
      `ALLOWED DISRUPTIONS` ≥ 1
- [ ] `kubectl get resourcequota -n murphy-system` shows quota in place
- [ ] `kubectl get limitrange -n murphy-system` shows limit range in place
- [ ] `kubectl rollout status deployment/murphy-api -n murphy-system` shows
      `successfully rolled out`
- [ ] Health endpoint reachable: `curl https://<domain>/api/health`

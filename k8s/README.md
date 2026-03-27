# Murphy System Kubernetes Manifests

> **Audit Date:** 2026-03-27  
> **Addresses:** G-002 (K8s manifests audit)

---

## Manifest Inventory

| File | Purpose | Status |
|------|---------|--------|
| `namespace.yaml` | Murphy namespace | ✅ Complete |
| `configmap.yaml` | Environment configuration | ✅ Complete |
| `secret.yaml` | Sensitive credentials | ✅ Complete |
| `deployment.yaml` | Murphy API deployment | ✅ Complete |
| `service.yaml` | ClusterIP service | ✅ Complete |
| `ingress.yaml` | Ingress with TLS | ✅ Complete |
| `hpa.yaml` | Horizontal Pod Autoscaler | ✅ Complete |
| `pdb.yaml` | Pod Disruption Budget | ✅ Complete |
| `pvc.yaml` | Persistent Volume Claim | ✅ Complete |
| `postgres.yaml` | PostgreSQL StatefulSet | ✅ Complete |
| `redis.yaml` | Redis deployment | ✅ Complete |
| `network-policy.yaml` | Network security | ✅ Complete |
| `resource-quota.yaml` | Resource limits | ✅ Complete |
| `limit-range.yaml` | Container limits | ✅ Complete |
| `backup-cronjob.yaml` | Database backups | ✅ Complete |
| `kustomization.yaml` | Kustomize config | ✅ Complete |

---

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `monitoring/` | Prometheus/Grafana configs |
| `staging/` | Staging environment overrides |

---

## Deployment

### Quick Start (Development)

```bash
# Create namespace and apply all manifests
kubectl apply -k k8s/

# Check status
kubectl get pods -n murphy
kubectl get svc -n murphy
```

### Production Deployment

```bash
# Set required secrets first
kubectl create secret generic murphy-secrets -n murphy \
  --from-literal=POSTGRES_PASSWORD=<password> \
  --from-literal=DEEPINFRA_API_KEY=<key> \
  --from-literal=TOGETHER_API_KEY=<key>

# Apply manifests
kubectl apply -k k8s/

# Verify deployment
kubectl rollout status deployment/murphy-api -n murphy
```

---

## Security Checklist

- [x] Network policies restrict pod-to-pod traffic
- [x] Secrets stored in Kubernetes secrets (not configmaps)
- [x] Resource limits prevent resource exhaustion
- [x] Pod disruption budget ensures availability
- [x] Ingress configured with TLS
- [x] Service accounts with minimal permissions

---

## Scaling

The HPA (Horizontal Pod Autoscaler) is configured to:
- Minimum replicas: 2
- Maximum replicas: 10
- CPU target: 70%
- Memory target: 80%

```bash
# Check HPA status
kubectl get hpa -n murphy

# Manual scale
kubectl scale deployment murphy-api -n murphy --replicas=5
```

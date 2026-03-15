# Murphy System — Production Checklist

<!-- Copyright © 2020 Inoni Limited Liability Company — License: BSL-1.1 -->

This checklist covers all steps required to deploy Murphy System to production on Hetzner K8s and verify it is operating correctly.

---

## K8s Resources Inventory

All resources below must be present in the `murphy-system` namespace before go-live:

| Resource | Kind | File |
|---|---|---|
| `murphy-system` | Namespace | `namespace.yaml` |
| `murphy-api` | Deployment | `deployment.yaml` |
| `murphy-api` | Service | `service.yaml` |
| `murphy-api` | Ingress | `ingress.yaml` |
| `murphy-api` | HorizontalPodAutoscaler | `hpa.yaml` |
| `murphy-config` | ConfigMap | `configmap.yaml` |
| `murphy-secrets` | Secret | `secret.yaml` |
| `murphy-data` | PersistentVolumeClaim | `pvc.yaml` |
| `murphy-api` | NetworkPolicy | `network-policy.yaml` |
| `murphy-redis` | NetworkPolicy | `network-policy.yaml` |
| `murphy-backup` | NetworkPolicy | `network-policy.yaml` |
| `murphy-api` | PodDisruptionBudget | `pdb.yaml` |
| `murphy-system-quota` | ResourceQuota | `resource-quota.yaml` |
| `murphy-system-limits` | LimitRange | `resource-quota.yaml` |
| `murphy-redis` (ConfigMap) | ConfigMap | `redis.yaml` |
| `murphy-redis` | Deployment | `redis.yaml` |
| `murphy-redis` | Service | `redis.yaml` |
| `murphy-redis-data` | PersistentVolumeClaim | `redis.yaml` |
| `murphy-backup` | CronJob | `backup-cronjob.yaml` |
| `murphy-backup-storage` | PersistentVolumeClaim | `backup-cronjob.yaml` |

---

## Pre-Deployment Checklist

- [ ] **Secrets populated**: All placeholder values in `secret.yaml` replaced with real secrets
  - `DATABASE_URL` — PostgreSQL connection string
  - `REDIS_URL` — Redis connection string (e.g. `redis://:password@murphy-redis:6379/0`)
  - `GROQ_API_KEY` — Groq API key
  - `JWT_SECRET` — generated with `openssl rand -hex 32`
  - `ENCRYPTION_KEY` — generated with `openssl rand -hex 32`
  - `GITHUB_TOKEN` — GitHub PAT with `repo` + `packages` scopes
  - `MURPHY_API_KEYS` — comma-separated list of valid API keys
  - `MURPHY_CREDENTIAL_MASTER_KEY` — generated with `openssl rand -hex 32`
  - `REDIS_PASSWORD` — generated with `openssl rand -hex 16`
- [ ] **Domain DNS configured**: `murphy.example.com` (and staging subdomain) pointing to the cluster ingress IP
- [ ] **TLS certificate ready**: cert-manager or pre-provisioned certificate in place for HTTPS
- [ ] **GHCR access**: `GITHUB_TOKEN` secret set in GitHub Actions for image push/pull
- [ ] **Hetzner kubeconfig**: `HETZNER_KUBECONFIG` secret (base64-encoded) set in GitHub Actions
- [ ] **ConfigMap reviewed**: `MURPHY_CORS_ORIGINS` updated to real domain(s)
- [ ] **Storage class available**: Hetzner CSI driver installed and `hcloud-volumes` storage class present

---

## Deploy Commands

### Production (full deploy via Kustomize)
```bash
kubectl apply -k "Murphy System/k8s/"
```

### Production (rolling image update via CI/CD)
Push to `main` branch — GitHub Actions handles build, push, and rolling update automatically.

### Staging
```bash
kubectl apply -k "Murphy System/k8s/staging/"
```

### Manual full apply (step-by-step)
```bash
kubectl apply -f "Murphy System/k8s/namespace.yaml"
kubectl apply -f "Murphy System/k8s/configmap.yaml"
kubectl apply -f "Murphy System/k8s/secret.yaml"
kubectl apply -f "Murphy System/k8s/pvc.yaml"
kubectl apply -f "Murphy System/k8s/redis.yaml"
kubectl apply -f "Murphy System/k8s/resource-quota.yaml"
kubectl apply -f "Murphy System/k8s/deployment.yaml"
kubectl apply -f "Murphy System/k8s/service.yaml"
kubectl apply -f "Murphy System/k8s/ingress.yaml"
kubectl apply -f "Murphy System/k8s/hpa.yaml"
kubectl apply -f "Murphy System/k8s/network-policy.yaml"
kubectl apply -f "Murphy System/k8s/pdb.yaml"
kubectl apply -f "Murphy System/k8s/backup-cronjob.yaml"
```

---

## Post-Deployment Verification

Run the automated check:
```bash
./Murphy\ System/scripts/production_readiness_check.sh murphy-system
```

Or verify manually:

- [ ] **Health endpoint responds**: `curl -sf https://murphy.example.com/api/health` returns `{"status": "ok", ...}`
- [ ] **Metrics scraping**: `curl -sf https://murphy.example.com/metrics` contains `murphy_requests_total`
- [ ] **Grafana accessible**: Grafana dashboard loads and shows Murphy metrics
- [ ] **Backup CronJob scheduled**: `kubectl get cronjob murphy-backup -n murphy-system`
- [ ] **Redis connected**: `kubectl exec -n murphy-system deploy/murphy-redis -- redis-cli ping` returns `PONG`
- [ ] **PostgreSQL connected**: `kubectl exec -n murphy-system deploy/postgres -- pg_isready -U murphy -d murphy_db` returns `accepting connections`
- [ ] **PostgreSQL PVC bound**: `kubectl get pvc postgres-data -n murphy-system` shows `Bound`
- [ ] **HPA active**: `kubectl get hpa murphy-api -n murphy-system` shows current/desired replicas
- [ ] **PDB enforced**: `kubectl get pdb murphy-api -n murphy-system` shows `1` allowed disruptions
- [ ] **ResourceQuota applied**: `kubectl describe resourcequota murphy-system-quota -n murphy-system`

---

## Rollback Procedure

### Rolling back the API deployment
```bash
# Undo the most recent rollout
kubectl rollout undo deployment/murphy-api -n murphy-system

# Check rollout history
kubectl rollout history deployment/murphy-api -n murphy-system

# Roll back to a specific revision
kubectl rollout undo deployment/murphy-api -n murphy-system --to-revision=<N>
```

### Rolling back Redis
Redis is stateful; do NOT rollback the image without evaluating data compatibility first.
```bash
# Check Redis pod logs before any rollback
kubectl logs -n murphy-system deploy/murphy-redis --tail=100
```

---

## Scaling Guidance

### HPA configuration
Murphy API auto-scales between 2 and 10 replicas based on CPU utilisation (target 70%).
The HPA is defined in `hpa.yaml`.

### Manual scaling
```bash
# Scale API to a specific replica count (temporarily overrides HPA)
kubectl scale deployment/murphy-api -n murphy-system --replicas=5

# View current HPA status
kubectl get hpa murphy-api -n murphy-system -w
```

---

## Backup Verification

### Trigger a manual backup
```bash
kubectl create job --from=cronjob/murphy-backup manual-backup-$(date +%s) -n murphy-system
```

### Check backup status
```bash
# Watch the backup job
kubectl get jobs -n murphy-system -w

# View backup job logs
kubectl logs -n murphy-system -l component=backup --tail=50
```

### Verify backup files
```bash
# Exec into backup pod (while running) or use a debug pod
kubectl exec -n murphy-system -it <backup-pod-name> -- ls -lh /backups/
```

### Restore procedure
1. Stop the API to prevent writes: `kubectl scale deployment/murphy-api -n murphy-system --replicas=0`
2. Start a restore job using the backup image:
   ```bash
   kubectl run restore-$(date +%s) \
     --image=murphy-system:latest \
     --restart=Never \
     -n murphy-system \
     --env="MURPHY_ENV=production" \
     --command -- python -c "
   import sys; sys.path.insert(0, '/app/src')
   from backup_disaster_recovery import BackupManager, LocalStorageBackend
   from pathlib import Path
   backend = LocalStorageBackend(Path('/backups'))
   mgr = BackupManager(backend, project_root=Path('/app'))
   result = mgr.restore_backup('<backup-id>')
   print(result)
   "
   ```
3. Restart the API: `kubectl scale deployment/murphy-api -n murphy-system --replicas=2`
4. Verify health: `curl -sf https://murphy.example.com/api/health`

---

## Related Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE.md) — full deployment walkthrough
- [Maintenance Guide](../documentation/deployment/MAINTENANCE.md) — PostgreSQL backup, Redis AOF, routine ops

# Enterprise Scaling Guide

Enterprise-grade scaling patterns for multi-tenant Murphy System deployments,
cluster management, and high availability. This is a summary — for full details see
[Deployment Scaling](../deployment/SCALING.md).

---

## Scaling Model

Murphy System follows a **stateless API tier + stateful data tier** architecture:

- **API tier** (FastAPI / uvicorn) — stateless; any instance can serve any request.
- **Data tier** — PostgreSQL (persistent) + Redis (cache / rate-limit counters).

Scale the API tier **horizontally** (add replicas). Scale the data tier
**vertically** first, then add read replicas.

---

## Resource Requirements

| Deployment | vCPU | RAM | Notes |
|------------|------|-----|-------|
| Development / single user | 1 | 1 GB | Single uvicorn worker |
| Small team (≤ 10 tenants) | 2 | 4 GB | 2–4 workers |
| Mid-scale (≤ 100 tenants) | 4 | 8 GB | 4–8 workers, Redis required |
| Enterprise (100+ tenants) | 8+ | 16+ GB | Kubernetes recommended |

---

## Horizontal Scaling

### Multi-Worker uvicorn

```bash
uvicorn src.runtime.app:create_app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker Compose

```yaml
services:
  murphy:
    image: murphy-system:v1.0.0
    deploy:
      replicas: 4
    environment:
      DATABASE_URL: postgres://...
      REDIS_URL: redis://...
```

### Kubernetes

Use a `Deployment` with `HorizontalPodAutoscaler` targeting CPU utilisation:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 70
```

---

## Multi-Tenant Considerations

- Each tenant's `max_concurrent_tasks` (default 10) caps parallel work per workspace.
- `budget_limit` (default $10,000) prevents runaway costs.
- Isolation level (`strict` / `standard` / `shared`) affects resource sharing.
- The audit log is bounded at 10,000 entries per tenant (CWE-770 mitigation).

---

## High Availability

1. Run **≥ 2 API replicas** behind a load balancer.
2. Use PostgreSQL streaming replication or a managed HA service.
3. Deploy Redis in sentinel or cluster mode.
4. Enable health-check probes (`/health`) in your orchestrator.

---

## Cache Layer

Set `REDIS_URL` to enable:

- Response caching for repeated queries.
- Rate-limit counter storage (shared across workers).
- Session data for multi-instance deployments.

---

## Performance Targets

| Metric | Target |
|--------|--------|
| API throughput | ≥ 1,000 req/s (multi-worker) |
| Gate evaluation | ≥ 70,000 ops/s |
| Control plane operations | ≥ 1,200 ops/s |
| Integration pipeline | < 300 s per repo |

See [Performance](PERFORMANCE.md) for measured baselines and tuning advice.

---

## See Also

- [Enterprise Overview](ENTERPRISE_OVERVIEW.md)
- [Deployment Scaling](../deployment/SCALING.md)
- [Performance](PERFORMANCE.md)

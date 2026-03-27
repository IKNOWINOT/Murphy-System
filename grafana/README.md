# Murphy System Grafana Dashboards

> **Audit Date:** 2026-03-27  
> **Addresses:** G-005 (Grafana dashboard audit)

---

## Dashboard Inventory

| Dashboard | File | Panels | Status |
|-----------|------|--------|--------|
| System Overview | `dashboards/murphy-system-overview.json` | 12 | ✅ Complete |

---

## Provisioning

| Type | Directory | Status |
|------|-----------|--------|
| Dashboards | `provisioning/dashboards/` | ✅ Configured |
| Datasources | `provisioning/datasources/` | ✅ Configured |

---

## Panels in Overview Dashboard

1. **API Health** - Health check success rate
2. **Request Rate** - Requests per second
3. **Response Time** - p50, p95, p99 latency
4. **Error Rate** - 4xx and 5xx errors
5. **Active Sessions** - Current user sessions
6. **LLM Requests** - AI/LLM API calls
7. **Database Connections** - PostgreSQL pool
8. **Redis Operations** - Cache hit/miss
9. **Memory Usage** - Container memory
10. **CPU Usage** - Container CPU
11. **Pod Status** - Kubernetes pod health
12. **Recent Alerts** - Active Prometheus alerts

---

## Access

```bash
# Local development
docker compose up -d grafana
# Access at http://localhost:3000
# Default: admin/admin

# Production
# Via Ingress at https://grafana.murphy.systems
```

---

## Adding New Dashboards

1. Create JSON in `dashboards/`
2. Provisioning auto-loads from that directory
3. Or import via Grafana UI → Export JSON

---

## Alert Rules

Alert rules are managed in Prometheus, not Grafana.
See `prometheus.yml` and `prometheus-rules/` for alerting configuration.

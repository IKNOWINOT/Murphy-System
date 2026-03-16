# Murphy System — Monitoring Guide

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1 (Business Source License 1.1)
-->

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Overview

Murphy System ships a unified observability stack: **`src/metrics.py`** is the single canonical metrics module. All counters, gauges, and histograms flow through it; the `/metrics` endpoint exposes them in Prometheus text format for Grafana and alert evaluation.

### Unified metrics architecture

```
             HTTP requests
                   │
                   ▼
        _TraceIdMiddleware  (src/runtime/app.py)
          ├─ inc_counter("murphy_requests_total", ...)
          └─ observe_histogram("murphy_request_duration_seconds", ...)
                   │
                   ▼
          ┌─────────────────────────────┐
          │      src/metrics.py         │  ← single source of truth
          │  _counters / _gauges /      │
          │  _histograms / _module_health│
          └─────────────┬───────────────┘
                        │
          ┌─────────────┴──────────────────────────────┐
          │                                            │
    GET /metrics                           GET /api/health?deep=true
  (Prometheus text format)              (aggregates registered modules)
          │
    Prometheus scrapes → Grafana dashboards + alert rules
```

`src/prometheus_metrics_exporter.py` (Flask Blueprint) also bridges its
`/metrics` output with `src/metrics.py` so both surfaces share the same data.

| Component | Purpose |
|-----------|---------|
| `src/metrics.py` | **Canonical** in-process counters, gauges, histograms, health aggregation |
| `src/prometheus_metrics_exporter.py` | Flask Blueprint — bridges to `src/metrics.py` |
| `src/runtime/app.py` | FastAPI app — mounts `/metrics`, wires `_TraceIdMiddleware` |
| `prometheus.yml` | Scrape config (local Docker Compose) |
| `prometheus-rules/murphy-alerts.yml` | Alert rules (error rate, latency, resources, LLM, queue) |
| `grafana/provisioning/` | Auto-provisioned datasource and dashboard |
| `grafana/dashboards/murphy-system-overview.json` | "Murphy System — Production Overview" dashboard |
| `k8s/monitoring/` | Kubernetes Prometheus + Grafana deployments |

---

## Accessing Dashboards

### Local (Docker Compose)

Start the full stack:

```bash
cd "Murphy System"
cp .env.example .env
docker compose up -d
```

Then start the static UI server in a second terminal:

```bash
cd "Murphy System"
python -m http.server 8090
```

**Backend Services:**

| Service | URL | Notes |
|---------|-----|-------|
| Murphy API | <http://localhost:8000> | FastAPI backend |
| API Docs | <http://localhost:8000/docs> | Swagger UI |
| Prometheus | <http://localhost:9090> | Metrics & alert rules |
| Grafana | <http://localhost:3000> | Dashboards — **admin / admin** |

**UI Pages:**

| Page | URL | Role |
|------|-----|------|
| Landing Page | <http://localhost:8090/murphy_landing_page.html?apiPort=8000> | Public entry point |
| Onboarding Wizard | <http://localhost:8090/onboarding_wizard.html?apiPort=8000> | Zero-jargon setup |
| Unified Hub | <http://localhost:8090/terminal_unified.html?apiPort=8000> | Admin / all-roles hub |
| Architect Terminal | <http://localhost:8090/terminal_architect.html?apiPort=8000> | System architect |
| Enhanced Terminal | <http://localhost:8090/terminal_enhanced.html?apiPort=8000> | Power-user terminal |
| Integrated Terminal | <http://localhost:8090/terminal_integrated.html?apiPort=8000> | Operations manager |
| Worker Terminal | <http://localhost:8090/terminal_worker.html?apiPort=8000> | Delivery worker |
| Orchestrator Terminal | <http://localhost:8090/terminal_orchestrator.html?apiPort=8000> | Orchestration overview |
| Costs Terminal | <http://localhost:8090/terminal_costs.html?apiPort=8000> | Finance / budget |
| Org Chart Terminal | <http://localhost:8090/terminal_orgchart.html?apiPort=8000> | HR / org structure |
| Integrations Terminal | <http://localhost:8090/terminal_integrations.html?apiPort=8000> | DevOps / platform |
| Workflow Canvas | <http://localhost:8090/workflow_canvas.html?apiPort=8000> | Visual workflow designer |
| System Visualizer | <http://localhost:8090/system_visualizer.html?apiPort=8000> | Topology viewer |
| Production Wizard | <http://localhost:8090/production_wizard.html?apiPort=8000> | PROD-001 lifecycle wizard |
| Matrix Integration | <http://localhost:8090/matrix_integration.html?apiPort=8000> | Matrix bridge & HITL |
| Compliance Dashboard | <http://localhost:8090/compliance_dashboard.html?apiPort=8000> | Compliance / audit |
| Workspace | <http://localhost:8090/workspace.html?apiPort=8000> | Personal workspace |
| Pricing | <http://localhost:8090/pricing.html?apiPort=8000> | Plans & pricing |
| Sign Up | <http://localhost:8090/signup.html?apiPort=8000> | User registration |
| Smoke Test Tool | <http://localhost:8090/murphy-smoke-test.html?apiPort=8000> | API smoke tests |
| Observability Dashboard | <http://localhost:8090/strategic/gap_closure/observability/dashboard.html?apiPort=8000> | Observability metrics |
| Community Portal | <http://localhost:8090/strategic/gap_closure/community/community_portal.html?apiPort=8000> | Community collaboration |
| Workflow Builder | <http://localhost:8090/strategic/gap_closure/lowcode/workflow_builder_ui.html?apiPort=8000> | Low-code builder |

### Kubernetes (Hetzner Production)

Port-forward Prometheus and Grafana to your local machine:

```bash
# Prometheus
kubectl port-forward service/prometheus 9090:9090 -n murphy-system &

# Grafana
kubectl port-forward service/grafana 3000:3000 -n murphy-system &
```

Then open <http://localhost:9090> and <http://localhost:3000>.

Or use the verification script to check everything and print the full URL directory:

```bash
bash "Murphy System/scripts/verify_monitoring.sh" --namespace murphy-system --port-forward
```

---

## Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `murphy_requests_total` | Counter | Total HTTP requests, labelled by `status` |
| `murphy_request_duration_seconds` | Histogram | Request latency (buckets: 5ms–10s) |
| `murphy_errors_total` | Counter | Total errors encountered |
| `murphy_active_connections` | Gauge | Currently active connections |
| `murphy_uptime_seconds` | Gauge | Seconds since process start |
| `murphy_response_size_bytes` | Summary | Response body size distribution |
| `murphy_task_queue_depth` | Gauge | Current task queue depth |
| `murphy_llm_calls_total` | Counter | LLM API calls, labelled by `provider` and `status` |
| `murphy_confidence_score` | Histogram | Confidence score distribution by `domain` |

Register custom metrics via the API:

```bash
POST /api/metrics/register
{
  "name": "my_custom_metric",
  "description": "My custom counter",
  "type": "counter"
}
```

---

## Module Health Registration

Key subsystems register a health callback on startup so `GET /api/health?deep=true` can aggregate their status:

| Module | Registered Name | Health key |
|--------|----------------|------------|
| EventBackbone / IntegrationBus | `event_backbone` | `status: ok \| error` |
| Database (DATABASE_URL or stub) | `database` | `status: ok \| stub \| error` |
| LLM provider | `llm_provider` | `status: ok \| unavailable` |
| Security Plane | `security_plane` | `status: ok \| not_configured` |

Register additional modules in application code:

```python
from src import metrics

metrics.register_module_health(
    "my_subsystem",
    lambda: {"status": "ok", "queue_depth": 0},
)
```

---

## Alert Rules Validation

All metrics referenced in `prometheus-rules/murphy-alerts.yml` and the Grafana dashboard are
emitted by the Murphy API. The table below maps each metric to its source and confirms no
mismatches remain.

| Metric | Prometheus name | Emitted by | Notes |
|--------|----------------|-----------|-------|
| `murphy_requests_total` | Counter | `_TraceIdMiddleware` → `src/metrics.py` + `prometheus_client` Counter `murphy_requests` | `_total` suffix added by prometheus_client |
| `murphy_request_duration_seconds` | Histogram | `_TraceIdMiddleware` → `src/metrics.py` + `prometheus_client` Histogram | `_bucket/_sum/_count` suffixes added automatically |
| `murphy_llm_calls_total` | Counter | `prometheus_client` Counter `murphy_llm_calls` with `["provider", "status"]` labels | `status` label required by `MurphyLLMCallFailures` alert rule `{status="error"}` |
| `murphy_task_queue_depth` | Gauge | Seeded at 0 on startup; update via `metrics.set_gauge("murphy_task_queue_depth", n)` | |
| `murphy_uptime_seconds` | Gauge | `prometheus_client` Gauge updated on every request via `_update_uptime()`; also in `src/metrics.py` fallback | Grafana "API Uptime" panel |
| `murphy_confidence_score` | Histogram | `prometheus_client` Histogram with `["domain"]` label | Grafana "Confidence Score Distribution" panel; increment from inference paths |
| `murphy_response_size_bytes` | Histogram | `_TraceIdMiddleware` → `prometheus_client` Histogram with `["endpoint"]` label | Grafana "Response Size Distribution" panel |

A validation test in `tests/test_alert_rules_validation.py` enforces that every metric
referenced in alert rules and the Grafana dashboard is registered.

---



| Alert | Severity | Condition | Action |
|-------|----------|-----------|--------|
| `MurphyAPIDown` | 🔴 critical | `up{job="murphy-api"} == 0` for 1m | Check pod status; restart deployment |
| `MurphyHighErrorRate` | 🟡 warning | >5% of requests returning 5xx for 5m | Review application logs; check upstream dependencies |
| `MurphyHighLatency` | 🟡 warning | p95 latency >2s for 5m | Check DB/Redis performance; review slow endpoints |
| `MurphyPodRestarting` | 🟡 warning | >3 restarts in 1h | Check OOM kills; review resource limits |
| `MurphyHighMemoryUsage` | 🟡 warning | >80% memory limit for 5m | Scale horizontally or raise memory limit |
| `MurphyHighCPUUsage` | 🟡 warning | >80% CPU limit for 5m | Scale horizontally or raise CPU limit |
| `MurphyLLMCallFailures` | 🟡 warning | >10% LLM call error rate for 5m | Check API keys and LLM provider status |
| `MurphyTaskQueueBacklog` | 🟡 warning | Queue depth >100 for 10m | Scale workers or investigate blocking tasks |

**Runbook reference:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## SLO Recording Rules

Two recording rules are pre-configured:

| Rule | Expression |
|------|------------|
| `murphy:availability:ratio_30d` | 30-day availability (target: 99.9%) |
| `murphy:latency:p99_5m` | Rolling p99 latency (target: <5s) |

Query them in Prometheus:

```promql
murphy:availability:ratio_30d
murphy:latency:p99_5m
```

---

## Silencing Alerts

**Via Prometheus Alertmanager** (if configured):

```bash
# Silence MurphyAPIDown for 2 hours
amtool silence add alertname="MurphyAPIDown" --duration=2h --comment="Planned maintenance"
```

**Via Grafana UI:** Navigate to Alerting → Silence → New Silence.

---

## Adding Custom Metrics

1. **Register via API:**

   ```bash
   curl -X POST http://localhost:8000/api/metrics/register \
     -H "Content-Type: application/json" \
     -d '{"name":"my_metric","description":"My metric","type":"counter"}'
   ```

2. **Increment/set via API:**

   ```bash
   curl -X POST http://localhost:8000/api/metrics/increment \
     -H "Content-Type: application/json" \
     -d '{"name":"my_metric","labels":{"env":"prod"}}'
   ```

3. **View raw metrics:** <http://localhost:8000/metrics>

4. **View JSON format:** <http://localhost:8000/api/metrics/json>

---

## Related Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — Hetzner K8s deployment
- [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md) — System architecture
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — Full API reference
- [CONTRIBUTING.md](CONTRIBUTING.md) — Development setup & UI page index
- [SCALING.md](../documentation/deployment/SCALING.md) — Scaling guide

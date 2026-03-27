# Maintenance Guide

Operational maintenance procedures for the Murphy System — log rotation, health monitoring, backup, upgrades, and troubleshooting.

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Table of Contents

1. [Routine Maintenance Schedule](#1-routine-maintenance-schedule)
2. [Health Checks and Monitoring](#2-health-checks-and-monitoring)
3. [Log Management](#3-log-management)
4. [Backup Procedures](#4-backup-procedures)
5. [Upgrade Procedures](#5-upgrade-procedures)
6. [Alerting](#6-alerting)
7. [Troubleshooting Common Issues](#7-troubleshooting-common-issues)
8. [Emergency Procedures](#8-emergency-procedures)

---

## 1. Routine Maintenance Schedule

| Frequency | Task |
|-----------|------|
| Daily | Review error logs; check `/api/health`; verify queue depth |
| Weekly | Rotate logs; review Prometheus dashboards; check disk usage |
| Monthly | Audit API key list; review rate-limit configuration; test backup restore |
| Per release | Run full test suite; review CHANGELOG; validate `.env` against `.env.example` |

---

## 2. Health Checks and Monitoring

### Liveness probe

```bash
curl -sf http://localhost:8000/api/health | python -m json.tool
```

Expected:
```json
{"status": "ok", "version": "1.0.0", "uptime_seconds": 86400}
```

A non-200 response or connection refused means the process is down.

### System status

```bash
curl -s http://localhost:8000/api/status \
  -H "Authorization: Bearer ${MURPHY_KEY}" | python -m json.tool
```

Key fields to monitor:

| Field | Healthy value | Action if unhealthy |
|-------|--------------|---------------------|
| `status` | `"operational"` | Check error log; restart if needed |
| `modules_loaded` | ≥ 620 | Check startup log for import errors |
| `llm_enabled` | `true` (if LLM required) | Verify `DEEPINFRA_API_KEY` / provider key |
| `active_gates` | includes `security`, `compliance` | Check gate configuration |

### Orchestrator queue depth

Rising `queued_tasks` indicates the workers cannot keep up. Check:

```bash
curl -s http://localhost:8000/api/orchestrator/status \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

If `queued_tasks > 50`, add workers (see [Scaling Guide](SCALING.md)).

### Docker Compose health

```bash
docker compose ps          # check state = healthy / running
docker compose logs -f --tail=100 murphy-api
```

### Kubernetes health

```bash
kubectl -n murphy get pods
kubectl -n murphy describe pod <pod-name>
kubectl -n murphy logs <pod-name> --tail=100
```

---

## 3. Log Management

### Log locations

| Deployment | Access log | Error log |
|------------|-----------|-----------|
| Local (uvicorn) | stdout | stdout |
| Docker Compose | `docker compose logs murphy-api` | same |
| Gunicorn | `/app/logs/access.log` | `/app/logs/error.log` |
| Kubernetes | `kubectl logs` | same |

### Log rotation with logrotate

Create `/etc/logrotate.d/murphy`:

```
/app/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 murphy murphy
    postrotate
        # Signal Gunicorn to reopen log files
        kill -USR1 $(cat /var/run/murphy.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
```

Test:

```bash
sudo logrotate --debug /etc/logrotate.d/murphy
```

### Structured log parsing

Murphy emits JSON log lines at `INFO` and above. Parse with `jq`:

```bash
# Last 100 errors
tail -n 1000 /app/logs/error.log | jq 'select(.level == "ERROR")'

# Slow requests (>2s)
tail -n 10000 /app/logs/access.log | jq 'select(.duration_ms > 2000)'
```

### Log level configuration

```bash
# .env
LOG_LEVEL=INFO    # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

Switch to `DEBUG` temporarily to trace a specific issue, then revert. Debug logging is verbose and should not be left on in production.

---

## 4. Backup Procedures

### PostgreSQL

**Automated daily dump:**

```bash
#!/usr/bin/env bash
# /etc/cron.daily/murphy-backup
set -euo pipefail

BACKUP_DIR=/var/backups/murphy
DATE=$(date +%Y%m%d_%H%M%S)
PGPASSWORD="${POSTGRES_PASSWORD}" \
  pg_dump -h localhost -U murphy murphy \
  | gzip > "${BACKUP_DIR}/murphy_${DATE}.sql.gz"

# Retain 30 days
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +30 -delete
echo "Backup completed: murphy_${DATE}.sql.gz"
```

**Docker Compose backup:**

```bash
docker compose exec postgres \
  pg_dump -U murphy murphy | gzip > murphy_backup_$(date +%Y%m%d).sql.gz
```

### Restore from backup

```bash
gunzip -c murphy_backup_20260307.sql.gz \
  | psql -h localhost -U murphy murphy
```

### Murphy data directory

The `/app/data` directory contains module state, concept graphs, and session data. Back it up alongside the database:

```bash
tar -czf murphy_data_$(date +%Y%m%d).tar.gz /app/data
```

### Redis

For non-critical caches (rate-limit counters) Redis does not require backup. If you store session state in Redis, enable AOF persistence:

```bash
# redis.conf
appendonly yes
appendfsync everysec
```

---

## 5. Upgrade Procedures

### Standard upgrade (patch / minor)

```bash
# 1. Pull new code
cd "Murphy System"
git pull origin main

# 2. Activate virtual environment
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows

# 3. Install / update dependencies
pip install -r requirements_murphy_1.0.txt

# 4. Run tests
python -m pytest --timeout=60 -v --tb=short

# 5. Restart the server
#    Graceful restart preserves in-flight requests
kill -HUP $(cat /var/run/murphy.pid)
# or
docker compose restart murphy-api
```

### Zero-downtime rolling upgrade (Docker Compose / k8s)

**Docker Compose:**
```bash
docker compose build murphy-api
docker compose up -d --no-deps murphy-api
```

**Kubernetes:**
```bash
kubectl -n murphy set image deployment/murphy-api \
  murphy-api=murphy-system:1.0.1

# Watch rollout
kubectl -n murphy rollout status deployment/murphy-api
```

### Database migrations

If a release includes schema changes, run migrations **before** deploying the new application binary:

```bash
# Apply migrations (example using Alembic)
alembic upgrade head

# Then deploy the new binary
docker compose up -d --no-deps murphy-api
```

### Rollback

```bash
# Docker Compose — roll back to previous image
docker compose up -d --no-deps murphy-api \
  --image murphy-system:1.0.0

# Kubernetes
kubectl -n murphy rollout undo deployment/murphy-api
```

---

## 6. Alerting

### Prometheus alert rules (`alerts.yml`)

```yaml
groups:
  - name: murphy
    rules:
      - alert: MurphyDown
        expr: up{job="murphy"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Murphy API is unreachable"

      - alert: HighErrorRate
        expr: |
          rate(murphy_requests_total{status=~"5.."}[5m])
          / rate(murphy_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Error rate > 5% for 5 minutes"

      - alert: HighQueueDepth
        expr: murphy_task_queue_depth > 100
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Orchestrator queue depth > 100"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(murphy_request_latency_seconds_bucket{endpoint="/api/execute"}[5m])
          ) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p95 execute latency > 5s"
```

### Minimal uptime check (no Prometheus)

```bash
# cron — every 5 minutes
*/5 * * * * curl -sf http://localhost:8000/api/health || \
  echo "Murphy API DOWN at $(date)" | mail -s "ALERT: Murphy" ops@yourdomain.com
```

---

## 7. Troubleshooting Common Issues

### Server does not start

**Symptom:** `Address already in use`

```bash
# Find process using port 8000
lsof -i :8000
kill <PID>
```

**Symptom:** `ModuleNotFoundError`

```bash
# Verify virtual environment is activated
which python   # should point to venv/bin/python
pip install -r requirements_murphy_1.0.txt
```

**Symptom:** `ImportError` for a specific module

```bash
# Run the import test (thin entry point delegates to src/runtime/)
python -c "from src.runtime.app import create_app; create_app()"
# Review traceback for the failing dependency
```

### Authentication errors (401)

1. Confirm `MURPHY_ENV=production` is set (development mode skips auth).
2. Verify `MURPHY_API_KEYS` contains the key being used.
3. Check that the `Authorization: Bearer <key>` header is sent correctly — no extra whitespace.

### LLM not responding (503)

```bash
# Check LLM configuration
curl -s http://localhost:8000/api/llm/configure \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

- `key_configured: false` → set the correct API key via `POST /api/llm/configure` or `.env`.
- `key_configured: true` but still 503 → the provider is rate-limiting you; add more keys via `DEEPINFRA_API_KEYS`.

### Rate limit errors (429)

Reduce your request rate, or raise `MURPHY_RATE_LIMIT` / `MURPHY_EXECUTE_RATE_LIMIT` in `.env` and restart.

### PostgreSQL connection refused

```bash
# Docker Compose
docker compose ps postgres
docker compose logs postgres | tail -20
docker compose restart postgres
```

### Redis connection refused

```bash
docker compose ps redis
docker compose restart redis
```

### High memory usage

```bash
# Identify top processes
ps aux --sort=-%mem | head -10

# Check per-worker RSS
ps -o pid,rss,comm -p $(pgrep -d, -f murphy_system_1.0_runtime)
```

If RSS grows unboundedly, set Gunicorn `--max-requests` to recycle workers periodically:

```bash
gunicorn ... --max-requests 1000 --max-requests-jitter 100
```

### Disk full

```bash
df -h /app
du -sh /app/logs/*
```

Run log rotation manually:

```bash
sudo logrotate -f /etc/logrotate.d/murphy
```

---

## 8. Emergency Procedures

### Immediate shutdown

```bash
# Graceful
docker compose stop murphy-api

# Force kill (last resort)
docker compose kill murphy-api
```

### Disable LLM to reduce load

```bash
# Hot-disable LLM provider without restart
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"provider": "local", "api_key": ""}'
```

Tasks submitted with `use_llm: true` will fall back to deterministic routing.

### API key compromise

1. Immediately remove the compromised key from `MURPHY_API_KEYS` in `.env`.
2. Restart the server to reload the key list.
3. Rotate any downstream secrets that may have been exposed.
4. Review audit logs for suspicious `audit_id` records.

---

## See Also

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Scaling](SCALING.md)
- [Configuration](CONFIGURATION.md)

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

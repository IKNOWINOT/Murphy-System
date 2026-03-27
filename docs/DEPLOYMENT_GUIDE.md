# Murphy System — Deployment Guide

**Version:** 1.0.0  
**License:** BSL 1.1

---

## Overview

Murphy System can be deployed in three modes:

1. **Local development** — bare Python, no containers
2. **Docker single-container** — containerised, recommended for staging
3. **Docker Compose** — multi-service with monitoring, recommended for production

---

## Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.12 |
| RAM | 2 GB | 8 GB |
| CPU | 2 cores | 4 cores |
| Disk | 1 GB | 10 GB |
| OS | Linux / macOS / Windows | Ubuntu 22.04 LTS |

---

## Local Development

```bash
# 1. Clone
git clone https://github.com/IKNOWINOT/Murphy-System
cd "murphy_system"

# 2. Create virtualenv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements_murphy_1.0.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set at minimum: GROQ_API_KEY

# 5. Start the server
python murphy_system_1.0_runtime.py

# 6. Verify
curl http://localhost:8000/api/health
```

The optional TUI terminal:
```bash
python murphy_terminal.py
```

---

## Docker Deployment

### Build and run

```bash
cd "murphy_system"

# Build image
docker build -t murphy-system:1.0.0 .

# Run with env file
docker run -d \
  --name murphy \
  --env-file .env \
  -p 8000:8000 \
  --restart unless-stopped \
  murphy-system:1.0.0
```

### Health check

```bash
docker exec murphy curl -s http://localhost:8000/api/health
```

### Logs

```bash
docker logs -f murphy
```

### Stop and remove

```bash
docker stop murphy && docker rm murphy
```

---

## Docker Compose (Production)

```bash
cd "murphy_system"
cp .env.example .env   # fill in secrets
docker compose up -d
```

Services started by `docker-compose.yml`:

| Service | Port | Description |
|---|---|---|
| `murphy` | 8000 | FastAPI application server |
| `redis` | 6379 | Task queue / rate-limit store |
| `prometheus` | 9090 | Metrics scraping |
| `grafana` | 3000 | Dashboards |

---

## Environment Variable Reference

All variables are read at startup.  Variables marked **required** will cause the
server to refuse to start if unset.

### Core

| Variable | Required | Default | Description |
|---|---|---|---|
| `MURPHY_ENV` | ❌ | `production` | Deployment environment (`development`, `staging`, `production`) |
| `MURPHY_API_URL` | ❌ | `http://localhost:8000` | Public-facing base URL |
| `MURPHY_SECRET_KEY` | ✅ | — | 32+ char secret used for token signing |
| `MURPHY_LOG_LEVEL` | ❌ | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MURPHY_WORKERS` | ❌ | `4` | Number of Uvicorn worker processes |
| `MURPHY_PORT` | ❌ | `8000` | Server listen port |
| `MURPHY_HOST` | ❌ | `127.0.0.1` | Server listen address (use 0.0.0.0 to expose on all interfaces) |

### LLM Integration

| Variable | Required | Default | Description |
|---|---|---|---|
| `MURPHY_LLM_PROVIDER` | ❌ | `groq` | Active LLM provider (`groq`, `openai`, `anthropic`, `local`) |
| `GROQ_API_KEY` | ❌ | — | Groq API key (required for LLM features) |
| `OPENAI_API_KEY` | ❌ | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | ❌ | — | Anthropic Claude API key |
| `LOCAL_LLM_URL` | ❌ | `http://localhost:11434` | URL for local Ollama instance |
| `LLM_TIMEOUT_SECONDS` | ❌ | `30` | Per-request LLM timeout |
| `LLM_MAX_TOKENS` | ❌ | `4096` | Max tokens per LLM response |

### Security

| Variable | Required | Default | Description |
|---|---|---|---|
| `MURPHY_CORS_ORIGINS` | ❌ | `http://localhost:*` | Comma-separated allowed CORS origins |
| `MURPHY_RATE_LIMIT` | ❌ | `100/minute` | Default rate limit (anonymous users) |
| `MURPHY_AUTH_RATE_LIMIT` | ❌ | `1000/minute` | Rate limit for authenticated users |
| `MURPHY_JWT_EXPIRY_HOURS` | ❌ | `24` | JWT token expiry in hours |
| `MURPHY_PII_DETECTION` | ❌ | `true` | Enable PII detection in logs |

### Persistence

| Variable | Required | Default | Description |
|---|---|---|---|
| `MURPHY_DATA_DIR` | ❌ | `./data` | Path for durable JSON storage |
| `MURPHY_CHECKPOINT_DIR` | ❌ | `./checkpoints` | Path for pipeline checkpoints |

### External Services

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_TOKEN` | ❌ | — | GitHub PAT for repository integrations |
| `SLACK_BOT_TOKEN` | ❌ | — | Slack bot token for notifications |
| `STRIPE_API_KEY` | ❌ | — | Stripe key for billing integration |
| `SENDGRID_API_KEY` | ❌ | — | SendGrid key for email |
| `REDIS_URL` | ❌ | `redis://localhost:6379` | Redis URL for task queue |

---

## Security Checklist (Pre-Deployment)

Run through the following before going to production:

- [ ] `MURPHY_SECRET_KEY` is set to a cryptographically random 32+ character string
- [ ] `MURPHY_ENV=production` is set
- [ ] CORS origins are restricted to known domains (not `*`)
- [ ] TLS/HTTPS is terminated at the load balancer or reverse proxy
- [ ] Docker image is built from a pinned base image (not `latest`)
- [ ] `.env` file is not committed to source control (confirm `.gitignore` includes it)
- [ ] API keys are stored in a secrets manager (e.g., AWS Secrets Manager, Vault), not plaintext
- [ ] Container runs as a non-root user (`USER murphy` in Dockerfile)
- [ ] Rate limiting is enabled and tested
- [ ] PII detection logging is enabled (`MURPHY_PII_DETECTION=true`)
- [ ] `pip-audit` passes with zero critical vulnerabilities
- [ ] `bandit` static analysis passes with no high-severity findings
- [ ] All endpoints behind auth are tested with missing/invalid tokens (expect 401)
- [ ] Monitoring and alerting are configured (see below)

---

## Monitoring and Alerting

### Prometheus Metrics

Murphy exposes a `/metrics` endpoint in Prometheus format.  Key metrics:

| Metric | Type | Description |
|---|---|---|
| `murphy_requests_total` | Counter | Total HTTP requests by path, method, status |
| `murphy_request_duration_seconds` | Histogram | Request latency distribution |
| `murphy_llm_calls_total` | Counter | LLM API calls by provider and result |
| `murphy_gate_evaluations_total` | Counter | Gate evaluations by gate name and result |
| `murphy_active_tasks` | Gauge | Currently executing tasks |
| `murphy_queue_depth` | Gauge | Tasks waiting to execute |

### Recommended Alerts

| Alert | Condition | Severity |
|---|---|---|
| High error rate | `rate(murphy_requests_total{status=~"5.."}[5m]) > 0.05` | Critical |
| LLM degraded | `rate(murphy_llm_calls_total{result="error"}[5m]) > 0.2` | Warning |
| Gate fail spike | `rate(murphy_gate_evaluations_total{result="fail"}[5m]) > 0.3` | Warning |
| Queue backup | `murphy_queue_depth > 50` | Warning |
| Process down | `up{job="murphy"} == 0` | Critical |

### Grafana Dashboard

Import the pre-built dashboard from `monitoring/grafana-dashboard.json`:

1. Open Grafana → `+` → Import
2. Upload `monitoring/grafana-dashboard.json`
3. Select the Prometheus data source
4. Click Import

---

## Backup and Recovery

### What to back up

| Path | Frequency | Description |
|---|---|---|
| `data/` | Daily | Durable JSON storage (task history, state) |
| `checkpoints/` | After each pipeline run | Pipeline checkpoints for recovery |
| `.env` | On change | Configuration (store securely, not in git) |

### Backup script (example)

```bash
#!/bin/bash
BACKUP_DIR="/backups/murphy-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r data/ "$BACKUP_DIR/data"
cp -r checkpoints/ "$BACKUP_DIR/checkpoints"
echo "Backup complete: $BACKUP_DIR"
```

### Recovery

To restore from backup:

```bash
docker stop murphy
cp -r /backups/murphy-YYYYMMDD-HHmmSS/data ./data
cp -r /backups/murphy-YYYYMMDD-HHmmSS/checkpoints ./checkpoints
docker start murphy
```

For pipeline checkpoints, the self-fix loop automatically detects interrupted
pipelines on startup and resumes from the last checkpoint.  No manual
intervention is required unless `data/` is corrupted.

---

## Kubernetes (k8s/)

Kubernetes manifests are in `k8s/`.  These are provided as a starting point and
**require security review and hardening before production use** — particularly
the `Secrets` manifests (replace with your secrets management solution) and
`NetworkPolicy` rules.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml       # populate first!
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*

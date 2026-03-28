# Murphy System — Operational Runbooks

**Version:** 1.0  
**Last updated:** 2026-03-24  
**License:** BSL 1.1

These runbooks provide step-by-step procedures for common operational scenarios.
Use the [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) for initial setup.

---

## Table of Contents

1. [Incident Response](#incident-response)
2. [Common Troubleshooting](#common-troubleshooting)
3. [Scaling Procedures](#scaling-procedures)
4. [Monitoring Alert Response](#monitoring-alert-response)
5. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
6. [Blackstart (Cold-Start) Recovery](#blackstart-cold-start-recovery)

---

## Incident Response

### Severity Levels

| Level | Description | Response Time | Example |
|---|---|---|---|
| SEV-1 | Complete outage — service unavailable to all users | < 15 minutes | Process down, DB unreachable |
| SEV-2 | Partial outage — major feature unavailable | < 30 minutes | LLM failing, auth broken |
| SEV-3 | Degraded — non-critical feature failing | < 2 hours | Monitoring gaps, slow queries |
| SEV-4 | Minor — cosmetic or inconvenient | Next sprint | Typos, minor UX issues |

### SEV-1 Response Procedure

1. **Acknowledge** the alert within 5 minutes.
2. **Assess** impact: How many users are affected? What is failing?
3. **Communicate** a status update to stakeholders (Slack `#murphy-incidents`).
4. **Diagnose**:
   ```bash
   # Quick system overview
   sudo systemctl status murphy-production ollama nginx
   docker compose -f docker-compose.hetzner.yml ps

   # Check logs (last 100 lines)
   sudo journalctl -u murphy-production -n 100 --no-pager

   # Check health
   curl -s http://localhost:8000/api/health | python3 -m json.tool
   ```
5. **Resolve** using the relevant troubleshooting section below.
6. **Verify** the health endpoint returns `{"status": "healthy"}`.
7. **Post-incident review** within 48 hours — update this runbook with findings.

---

## Common Troubleshooting

### Service won't start

**Symptoms:** `systemctl status murphy-production` shows `failed` or `activating (auto-restart)`.

**Diagnosis:**
```bash
sudo journalctl -u murphy-production -n 50 --no-pager
python3 -c "from src.deployment_readiness import DeploymentReadinessChecker; r = DeploymentReadinessChecker().run_all(); [print(f['name'], f['detail']) for f in r['failures']]"
```

**Common causes and fixes:**

| Cause | Fix |
|---|---|
| Missing env var | Set missing var in `/etc/murphy-production/environment` then `systemctl restart murphy-production` |
| Database unreachable | `docker compose -f docker-compose.hetzner.yml restart murphy-postgres` |
| Redis unreachable | `docker compose -f docker-compose.hetzner.yml restart murphy-redis` |
| Port 8000 in use | `sudo fuser -k 8000/tcp` |
| Syntax error in code | Check logs for `SyntaxError` / `ImportError`; rollback if needed: `bash scripts/rollback.sh` |
| Disk full | `df -h /`; clean logs: `sudo journalctl --vacuum-size=500M` |

---

### High memory usage

**Symptoms:** Server load > 90%, OOM kills, slow responses.

**Diagnosis:**
```bash
# Top processes
ps aux --sort=-%mem | head -20

# Memory usage by container
docker stats --no-stream

# Murphy process memory
ps -o pid,rss,comm -p $(pgrep -f murphy_system)
```

**Fixes:**
```bash
# Restart Murphy to release memory (if gradual leak)
sudo systemctl restart murphy-production

# Reduce worker count in /etc/murphy-production/environment:
# MURPHY_WORKERS=2

# Clear Redis cache if bloated
docker exec murphy-redis redis-cli FLUSHDB
```

---

### Slow response times

**Symptoms:** API requests taking > 5 seconds; Grafana shows elevated P95 latency.

**Diagnosis:**
```bash
# Check system load
uptime; vmstat 1 5

# Check DB slow queries
docker exec -it murphy-postgres psql -U murphy -c \
  "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Check Redis latency
docker exec murphy-redis redis-cli --latency-history -i 1
```

**Fixes:**
```bash
# Enable/verify Redis cache is running
docker exec murphy-redis redis-cli ping  # should return PONG

# Restart if LLM is hanging
sudo systemctl restart ollama

# Scale up if traffic is the cause (see Scaling Procedures)
```

---

### Database connection issues

**Symptoms:** Logs show `OperationalError: could not connect to server` or `FATAL: max_connections`.

**Diagnosis:**
```bash
# Check PostgreSQL status
docker compose -f docker-compose.hetzner.yml ps murphy-postgres

# Check connection count
docker exec murphy-postgres psql -U murphy -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Test direct connection
docker exec murphy-postgres psql -U murphy -c "SELECT 1;"
```

**Fixes:**
```bash
# Restart PostgreSQL (non-destructive)
docker compose -f docker-compose.hetzner.yml restart murphy-postgres

# If connections are exhausted, restart Murphy to reset pool
sudo systemctl restart murphy-production

# Increase max_connections (edit config and restart):
# Add to docker-compose.hetzner.yml under postgres:
#   command: postgres -c max_connections=200
```

---

### LLM not responding

**Symptoms:** Chat / AI features fail; logs show `LLM timeout` or `connection refused to :11434`.

**Diagnosis:**
```bash
# Check Ollama status
systemctl status ollama
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# Check if model is loaded
ollama list
```

**Fixes:**
```bash
# Restart Ollama
sudo systemctl restart ollama

# Pull model if missing
ollama pull phi3

# Fall back to external API (if DeepInfra key is set):
# In /etc/murphy-production/environment:
# MURPHY_LLM_PROVIDER=deepinfra
# DEEPINFRA_API_KEY=gsk_...
sudo systemctl restart murphy-production
```

---

### SSL certificate expiry

**Symptoms:** Browser shows cert expired; `curl` returns SSL error.

**Diagnosis:**
```bash
# Check expiry date
echo | openssl s_client -servername murphy.systems -connect murphy.systems:443 2>/dev/null \
  | openssl x509 -noout -dates

# Check certbot status
certbot certificates
```

**Fix:**
```bash
# Renew (Let's Encrypt renews automatically, but force if needed)
certbot renew --force-renewal
systemctl reload nginx
```

---

## Scaling Procedures

### Vertical scaling (more CPU / RAM)

Applicable when: consistently high CPU or memory usage on a single server.

1. In Hetzner Cloud console: Server → Actions → Resize
2. Choose the next server type (e.g., CPX31 → CPX51)
3. After resize, verify the service restarted correctly:
   ```bash
   sudo systemctl status murphy-production
   curl https://murphy.systems/api/health
   ```

### Horizontal scaling (Kubernetes)

Manually increase replicas:
```bash
kubectl -n murphy-system scale deployment/murphy-api --replicas=4
kubectl -n murphy-system rollout status deployment/murphy-api
```

Adjust HPA limits (`k8s/hpa.yaml`):
```yaml
minReplicas: 4   # increase minimum if traffic is consistently high
maxReplicas: 20  # increase maximum for traffic spikes
```

Apply and verify:
```bash
kubectl apply -f k8s/hpa.yaml
kubectl -n murphy-system get hpa murphy-api
```

### Database scaling

For read-heavy load, add a read replica:
```bash
# In k8s/postgres.yaml, add a StatefulSet for a PostgreSQL read replica
# or switch to a managed PostgreSQL service (e.g., Hetzner Managed Databases)
# Update DATABASE_URL to point read queries to the replica
```

### Cache scaling

If Redis is a bottleneck:
```bash
# Increase Redis memory limit in docker-compose.hetzner.yml:
# murphy-redis:
#   command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
docker compose -f docker-compose.hetzner.yml up -d murphy-redis
```

---

## Monitoring Alert Response

### Alert: High error rate (5xx responses > 5%)

```
alert: HighErrorRate
condition: rate(murphy_requests_total{status=~"5.."}[5m]) > 0.05
```

**Response:**
1. Check recent logs: `sudo journalctl -u murphy-production -n 100 --no-pager`
2. Look for Python exceptions or unhandled errors
3. Check if a recent deployment caused the issue: `git log --oneline -5`
4. If related to a deploy: `bash scripts/rollback.sh`

---

### Alert: LLM degraded (error rate > 20%)

```
alert: LLMDegraded
condition: rate(murphy_llm_calls_total{result="error"}[5m]) > 0.2
```

**Response:**
1. Check Ollama: `systemctl status ollama`
2. If Ollama is down, restart: `sudo systemctl restart ollama`
3. If the onboard LLM has GPU/memory issues, switch to external API:
   ```bash
   # Temporarily set MURPHY_LLM_PROVIDER=deepinfra in the environment file
   sudo systemctl restart murphy-production
   ```

---

### Alert: Queue backup (queue depth > 50)

```
alert: QueueBackup
condition: murphy_queue_depth > 50
```

**Response:**
1. Check if workers are processing: `sudo journalctl -u murphy-production | grep "task processed"`
2. If workers are stuck, restart: `sudo systemctl restart murphy-production`
3. If traffic surge, scale up replicas (see Scaling Procedures)

---

### Alert: Process down

```
alert: ProcessDown
condition: up{job="murphy"} == 0
```

**Response:**
1. Start the service: `sudo systemctl start murphy-production`
2. If it won't start, see "Service won't start" troubleshooting above
3. If all else fails, run blackstart: see next section

---

## Backup and Disaster Recovery

### Recovery Point Objective (RPO): 1 hour
### Recovery Time Objective (RTO): 30 minutes

### List available backups

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
for m in mgr.list_backups():
    print(m.backup_id, m.backup_type, m.status, m.created_at, f'{m.size_bytes}b')
"
```

### Create an on-demand backup (before major changes)

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, BackupType, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
m = mgr.create_backup(BackupType.FULL.value)
print('Backup:', m.backup_id, m.status)
"
```

### Restore from a backup

```bash
# Stop service first
sudo systemctl stop murphy-production

# Restore
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
result = mgr.restore_backup('<backup-id>')
print('Status:', result.status)
print('Restored:', result.components_restored)
if result.errors:
    print('Errors:', result.errors)
"

# Start service
sudo systemctl start murphy-production

# Verify
curl -s http://localhost:8000/api/health
```

### Verify backup integrity (without restoring)

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
ok = mgr.verify_backup_integrity('<backup-id>')
print('Integrity OK:', ok)
"
```

---

## Blackstart (Cold-Start) Recovery

Use when: the system is completely unresponsive and normal restart procedures fail.

### Prerequisite check

```bash
# Verify basic infrastructure
ping -c 3 1.1.1.1              # Internet connectivity
docker info                     # Docker daemon running
systemctl status postgresql     # DB running (if native install)
docker compose -f docker-compose.hetzner.yml ps  # Docker services
```

### Step-by-step blackstart

```bash
# 1. Stop everything cleanly
sudo systemctl stop murphy-production 2>/dev/null || true

# 2. Bring up support services
docker compose -f docker-compose.hetzner.yml up -d
sleep 10

# 3. Run the blackstart sequence
python3 -c "
import sys; sys.path.insert(0, 'src')
from blackstart_controller import BlackstartController, BlackstartPhase
ctrl = BlackstartController()
seq = ctrl.blackstart()
print('Final phase:', seq.current_phase.value)
for e in seq.errors:
    print('Error:', e)
if seq.current_phase == BlackstartPhase.OPERATIONAL:
    print('Blackstart SUCCEEDED')
else:
    print('Blackstart DEGRADED — check errors above')
"

# 4. Start the service
sudo systemctl start murphy-production

# 5. Verify
curl -s http://localhost:8000/api/health
```

### Restore to last known stable state (with checkpoint)

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from blackstart_controller import BlackstartController
ctrl = BlackstartController()
result = ctrl.restore_to_stable()
print('Restored:', result['restored'])
print('Checkpoint:', result['checkpoint_id'])
print('Blackstart seq:', result['blackstart_sequence_id'])
"
```

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*

# Murphy System — Deployment Guide

**Version:** 1.0  
**Last updated:** 2026-03-24  
**License:** BSL 1.1

> **Canonical detailed reference:** [documentation/deployment/DEPLOYMENT_GUIDE.md](documentation/deployment/DEPLOYMENT_GUIDE.md)  
> **Configuration reference:** [documentation/deployment/CONFIGURATION.md](documentation/deployment/CONFIGURATION.md)  
> **Scaling guide:** [documentation/deployment/SCALING.md](documentation/deployment/SCALING.md)  
> **Maintenance guide:** [documentation/deployment/MAINTENANCE.md](documentation/deployment/MAINTENANCE.md)  
> **Operational runbooks:** [docs/RUNBOOKS.md](docs/RUNBOOKS.md)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Hetzner Server Provisioning](#hetzner-server-provisioning)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [DNS and Cloudflare Setup](#dns-and-cloudflare-setup)
7. [SSL/TLS Certificate Configuration](#ssltls-certificate-configuration)
8. [Post-Deployment Verification Checklist](#post-deployment-verification-checklist)
9. [Rollback Procedures](#rollback-procedures)
10. [Backup and Disaster Recovery](#backup-and-disaster-recovery)

---

## Prerequisites

### Software Requirements

| Tool | Minimum | Purpose |
|---|---|---|
| Python | 3.10 | Runtime |
| Docker | 24.0 | Containerisation |
| Docker Compose | 2.20 | Multi-service orchestration |
| kubectl | 1.28 | Kubernetes management |
| hcloud CLI | 1.40 | Hetzner Cloud management |
| git | 2.40 | Repository management |
| nginx | 1.24 | Reverse proxy / TLS termination |
| certbot | 2.6 | Let's Encrypt TLS certificates |

### Server Requirements

| Environment | RAM | CPU | Disk | OS |
|---|---|---|---|---|
| Development | 4 GB | 2 cores | 20 GB | Any Linux / macOS |
| Staging | 8 GB | 4 cores | 40 GB | Ubuntu 22.04 LTS |
| Production (Hetzner CPX31) | 8 GB | 4 vCPU | 160 GB | Ubuntu 22.04 LTS |
| Production (HA, CPX51) | 16 GB | 8 vCPU | 240 GB | Ubuntu 22.04 LTS |

### Required Secrets

Generate all secrets before deployment:

```bash
# Run the built-in secret generator
bash scripts/generate_secrets.sh
```

| Secret | Env Variable | Generation |
|---|---|---|
| App secret key | `MURPHY_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| JWT secret | `MURPHY_JWT_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| Credential master key | `MURPHY_CREDENTIAL_MASTER_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| API key(s) | `MURPHY_API_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| DB password | `POSTGRES_PASSWORD` | `python -c "import secrets; print(secrets.token_urlsafe(24))"` |
| Grafana password | `GRAFANA_ADMIN_PASSWORD` | `python -c "import secrets; print(secrets.token_urlsafe(24))"` |

---

## Environment Setup

### 1. Clone and configure

```bash
git clone https://github.com/IKNOWINOT/Murphy-System /opt/Murphy-System
cd /opt/Murphy-System
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_murphy_1.0.txt
```

### 2. Create the environment file

```bash
cp config/murphy-production.environment.example /etc/murphy-production/environment
# Fill in all required values — see CONFIGURATION.md for full reference
nano /etc/murphy-production/environment
chmod 600 /etc/murphy-production/environment
```

### 3. Key environment variables

```bash
# Core
MURPHY_ENV=production
MURPHY_SECRET_KEY=<generated>
MURPHY_JWT_SECRET=<generated>
MURPHY_API_KEY=<generated>

# Database (PostgreSQL)
DATABASE_URL=postgresql://murphy:<password>@localhost:5432/murphy
POSTGRES_USER=murphy
POSTGRES_PASSWORD=<generated>
POSTGRES_DB=murphy

# Redis
REDIS_URL=redis://:<password>@localhost:6379/0
REDIS_PASSWORD=<generated>

# LLM
GROQ_API_KEY=gsk_...           # Free: https://console.groq.com/keys
OLLAMA_HOST=http://localhost:11434  # For onboard Ollama

# Email (optional, for notifications)
SMTP_HOST=mail.murphy.systems
SMTP_PORT=587
SMTP_USER=noreply@murphy.systems
SMTP_PASSWORD=<generated>

# Cloudflare (optional, for automated DNS)
CLOUDFLARE_API_TOKEN=<your-token>
CLOUDFLARE_ZONE_ID=<your-zone-id>
```

Full variable reference: [documentation/deployment/CONFIGURATION.md](documentation/deployment/CONFIGURATION.md)

### 4. Run the pre-flight check

```bash
bash scripts/preflight_check.sh
```

Expected output: all ✅ before proceeding to deployment.

---

## Docker Deployment

### Single-container (development / staging)

```bash
# Build
docker build -t murphy-system:1.0.0 .

# Run with env file
docker run -d \
  --name murphy \
  --env-file /etc/murphy-production/environment \
  -p 8000:8000 \
  --restart unless-stopped \
  murphy-system:1.0.0

# Verify
curl http://localhost:8000/api/health
```

### Full production stack (Hetzner / bare-metal)

The full production stack is managed via `docker-compose.hetzner.yml` for support
services (PostgreSQL, Redis, Prometheus, Grafana, mailserver) and a systemd unit
for the Murphy application itself.

```bash
# One-command full-stack load (recommended)
bash scripts/hetzner_load.sh

# Or bring up support services only
docker compose -f docker-compose.hetzner.yml up -d

# Check status
docker compose -f docker-compose.hetzner.yml ps
```

### Health check

```bash
# Application health
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Readiness gate (all subsystems)
curl -s http://localhost:8000/api/readiness | python3 -m json.tool
```

### Service management

```bash
# Murphy application
sudo systemctl start murphy-production
sudo systemctl stop murphy-production
sudo systemctl status murphy-production
sudo journalctl -u murphy-production -f

# Onboard LLM (Ollama)
sudo systemctl start ollama
sudo systemctl status ollama

# Support services
docker compose -f docker-compose.hetzner.yml restart
```

---

## Hetzner Server Provisioning

### Automated provisioning via hcloud CLI

```bash
# Install hcloud CLI
curl -fsSL https://pkg.hetzner.com/apt/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/hetzner.gpg
echo "deb [signed-by=/usr/share/keyrings/hetzner.gpg] https://pkg.hetzner.com/apt/stable /" | sudo tee /etc/apt/sources.list.d/hetzner.list
sudo apt-get update && sudo apt-get install -y hcloud-cli

# Authenticate
hcloud context create murphy-production

# Create server (CPX31 — 4 vCPU, 8 GB RAM, 160 GB SSD)
hcloud server create \
  --name murphy-production \
  --type cpx31 \
  --image ubuntu-22.04 \
  --location nbg1 \
  --ssh-key your-ssh-key-name \
  --user-data-from-file scripts/cloud-init.yml
```

### One-time server setup (SSH into the new server)

```bash
ssh root@<server-ip>

# 1. System update
apt-get update && apt-get upgrade -y

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# 3. Install nginx + certbot
apt-get install -y nginx certbot python3-certbot-nginx

# 4. Create murphy user
useradd -r -m -s /bin/false murphy

# 5. Clone repository
git clone https://github.com/IKNOWINOT/Murphy-System /opt/Murphy-System

# 6. Create production env file
mkdir -p /etc/murphy-production
cp /opt/Murphy-System/config/murphy-production.environment.example \
   /etc/murphy-production/environment
# Fill in all secrets:
nano /etc/murphy-production/environment
chmod 600 /etc/murphy-production/environment
chown murphy:murphy /etc/murphy-production/environment

# 7. Install systemd service
cp /opt/Murphy-System/config/systemd/murphy-production.service \
   /etc/systemd/system/murphy-production.service
systemctl daemon-reload
systemctl enable murphy-production

# 8. Install nginx vhost (edit server_name to your domain first)
cp /opt/Murphy-System/config/nginx/murphy-production.conf \
   /etc/nginx/sites-available/murphy-production
# Edit: server_name murphy.systems www.murphy.systems;
nano /etc/nginx/sites-available/murphy-production
ln -sf /etc/nginx/sites-available/murphy-production \
       /etc/nginx/sites-enabled/murphy-production
nginx -t && systemctl enable nginx

# 9. Install Ollama (onboard LLM)
curl -fsSL https://ollama.ai/install.sh | sh
systemctl enable ollama
ollama pull phi3

# 10. Full-stack load
bash /opt/Murphy-System/scripts/hetzner_load.sh
```

### Automated deployment via GitHub Actions

Push to `main` triggers `.github/workflows/hetzner-deploy.yml` which:
1. Builds the Docker image
2. Pushes to `ghcr.io/iknowinot/murphy-system`
3. SSHs into the Hetzner server
4. Runs `bash /opt/Murphy-System/scripts/hetzner_load.sh`

Required GitHub secrets:
- `HETZNER_SSH_KEY` — private SSH key for server access
- `HETZNER_SERVER_IP` — production server IP

---

## Kubernetes Deployment

All Kubernetes manifests live in `k8s/` with Kustomize overlays.

### Apply the full production stack

```bash
# Create namespace first
kubectl apply -f k8s/namespace.yaml

# Populate secrets (do NOT commit secret values to git)
kubectl create secret generic murphy-secrets \
  --namespace murphy-system \
  --from-literal=MURPHY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  --from-literal=MURPHY_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  --from-literal=MURPHY_CREDENTIAL_MASTER_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  --from-literal=MURPHY_API_KEYS="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  --from-literal=POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"

# Apply full stack via Kustomize
kubectl apply -k k8s/

# Watch rollout
kubectl -n murphy-system rollout status deployment/murphy-api

# Verify all pods are running
kubectl -n murphy-system get pods
```

### Resource summary

| Resource | Type | Replicas | CPU req/limit | Mem req/limit |
|---|---|---|---|---|
| `murphy-api` | Deployment | 2 (min) | 250m / 500m | 256Mi / 512Mi |
| `murphy-redis` | Deployment | 1 | 100m / 200m | 128Mi / 256Mi |
| `murphy-postgres` | StatefulSet | 1 | 250m / 500m | 256Mi / 512Mi |

### Horizontal Pod Autoscaler

HPA is configured in `k8s/hpa.yaml`:

```yaml
minReplicas: 2
maxReplicas: 10
# Scales up when CPU > 70% or Memory > 80%
```

```bash
# Check HPA status
kubectl -n murphy-system get hpa
kubectl -n murphy-system describe hpa murphy-api
```

### Rolling updates

```bash
# Update image
kubectl -n murphy-system set image deployment/murphy-api \
  murphy-api=ghcr.io/iknowinot/murphy-system/murphy-system:v1.0.1

# Watch rollout
kubectl -n murphy-system rollout status deployment/murphy-api --timeout=5m

# View rollout history
kubectl -n murphy-system rollout history deployment/murphy-api
```

---

## DNS and Cloudflare Setup

### Manual DNS configuration

Add these records to your DNS provider:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `<server-ip>` | 300 |
| A | `www` | `<server-ip>` | 300 |
| A | `mail` | `<server-ip>` | 300 |
| MX | `@` | `mail.murphy.systems` | 3600 |
| TXT | `@` | `v=spf1 ip4:<server-ip> -all` | 3600 |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@murphy.systems` | 3600 |

### Automated Cloudflare DNS (via cloudflare_deploy.py)

```bash
# Set required env vars
export CLOUDFLARE_API_TOKEN="your-api-token"
export CLOUDFLARE_ZONE_ID="your-zone-id"
export MURPHY_SERVER_IP="your-server-ip"

# Run the Cloudflare deploy agent
python src/cloudflare_deploy.py
```

The Cloudflare deploy agent:
1. Creates / updates A records for the apex and www subdomain
2. Configures mail DNS (MX, SPF, DKIM, DMARC)
3. Enables Cloudflare proxy (orange-cloud) for HTTP/HTTPS traffic
4. Configures page rules for HTTPS redirect
5. Sets security headers via Transform Rules

### Cloudflare security settings (recommended)

In the Cloudflare dashboard:

- **SSL/TLS**: Set to *Full (strict)*
- **Minimum TLS**: TLS 1.2
- **Always HTTPS**: Enabled
- **HTTP Strict Transport Security (HSTS)**: Enabled (max-age: 6 months)
- **Bot Fight Mode**: Enabled
- **Web Application Firewall**: Managed rules enabled
- **Rate Limiting**: Add rule: 100 requests/minute per IP to `/api/*`

---

## SSL/TLS Certificate Configuration

### Let's Encrypt (Hetzner / bare-metal)

```bash
# Obtain certificate (nginx must be running with the vhost configured)
certbot --nginx -d murphy.systems -d www.murphy.systems -d mail.murphy.systems \
  --non-interactive --agree-tos --email admin@murphy.systems

# Verify certificate
certbot certificates

# Test auto-renewal
certbot renew --dry-run

# Auto-renewal is installed automatically via /etc/cron.d/certbot
# Verify:
cat /etc/cron.d/certbot
```

### Kubernetes (cert-manager)

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Create ClusterIssuer for Let's Encrypt production
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@murphy.systems
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Update k8s/ingress.yaml to set your real domain:
#   spec.rules[0].host: murphy.systems
#   spec.tls[0].hosts[0]: murphy.systems
kubectl apply -f k8s/ingress.yaml

# Watch certificate issuance
kubectl -n murphy-system get certificate
kubectl -n murphy-system describe certificate murphy-tls
```

### Nginx TLS configuration (bare-metal reference)

The nginx vhost template at `config/nginx/murphy-production.conf` configures:

```nginx
ssl_certificate     /etc/letsencrypt/live/murphy.systems/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/murphy.systems/privkey.pem;
ssl_protocols       TLSv1.2 TLSv1.3;
ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:...;
ssl_prefer_server_ciphers off;
add_header Strict-Transport-Security "max-age=15768000" always;
```

---

## Post-Deployment Verification Checklist

Run the built-in readiness check first:

```bash
# Full automated check
bash scripts/production_readiness_check.sh

# Python-level readiness gate
python3 -c "
from src.deployment_readiness import DeploymentReadinessChecker
r = DeploymentReadinessChecker().run_all()
print('READY:', r['ready'])
for f in r.get('failures', []):
    print('FAIL:', f['name'], '-', f['detail'])
"
```

Then go through this checklist manually:

### Infrastructure

- [ ] Server is reachable via SSH: `ssh murphy@<server-ip>`
- [ ] Murphy API is running: `curl https://murphy.systems/api/health`
- [ ] PostgreSQL is running: `docker exec murphy-postgres pg_isready`
- [ ] Redis is running: `docker exec murphy-redis redis-cli ping`
- [ ] Ollama is running: `systemctl status ollama`
- [ ] Nginx is running: `systemctl status nginx`
- [ ] Prometheus is running: `curl http://localhost:9090/-/healthy`
- [ ] Grafana is running: `curl http://localhost:3000/api/health`
- [ ] All Docker containers are healthy: `docker compose -f docker-compose.hetzner.yml ps`

### Security

- [ ] HTTPS is enforced: `curl -I http://murphy.systems` → 301/302 redirect to HTTPS
- [ ] TLS certificate is valid: `curl -v https://murphy.systems/api/health 2>&1 | grep "SSL certificate"`
- [ ] Security headers present: check `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`
- [ ] `MURPHY_ENV=production` is set (auth is enforced)
- [ ] CORS is NOT set to wildcard `*`
- [ ] No default passwords remain (PostgreSQL, Grafana, Murphy founder account)
- [ ] No secrets are in git: `git log --all --full-history -- '*secrets*' '*password*'`

### Application

- [ ] Health endpoint returns `{"status": "healthy"}`: `curl https://murphy.systems/api/health`
- [ ] Readiness endpoint passes all gates: `curl https://murphy.systems/api/readiness`
- [ ] Authentication works: test login at `https://murphy.systems/login`
- [ ] Dashboard loads without errors: `https://murphy.systems/dashboard`
- [ ] Prometheus metrics are visible: `curl https://murphy.systems/metrics`
- [ ] Founder account is accessible and password has been changed from default

### Monitoring

- [ ] Grafana dashboards loaded (open `https://murphy.systems/grafana`)
- [ ] Alert rules are active in Prometheus
- [ ] Log aggregation is working: `sudo journalctl -u murphy-production -n 20`

### Backup

- [ ] First backup completed: `python3 -c "from src.backup_disaster_recovery import BackupManager, LocalStorageBackend; from pathlib import Path; mgr = BackupManager(LocalStorageBackend(Path('/tmp/bkp'))); m = mgr.create_backup(); print(m.status)"`
- [ ] Backup schedule is confirmed active
- [ ] Retention policy is confirmed (30 days default)

---

## Rollback Procedures

### Hetzner / bare-metal rollback

```bash
# Quick rollback to previous git commit
bash scripts/rollback.sh

# Rollback to a specific tag
bash scripts/rollback.sh --tag v1.0.0

# Rollback to a specific commit
bash scripts/rollback.sh --commit abc1234
```

The rollback script:
1. Stops the Murphy production service
2. Checks out the target commit / tag
3. Reinstalls dependencies (if `requirements_murphy_1.0.txt` changed)
4. Reloads nginx config
5. Restarts the Murphy production service
6. Verifies health endpoint responds with `200 OK`

### Kubernetes rollback

```bash
# Rollback to the previous deployment revision
kubectl -n murphy-system rollout undo deployment/murphy-api

# Rollback to a specific revision
kubectl -n murphy-system rollout undo deployment/murphy-api --to-revision=2

# Verify rollback
kubectl -n murphy-system rollout status deployment/murphy-api
kubectl -n murphy-system get pods
curl https://murphy.systems/api/health
```

### Database rollback (from backup)

If a database migration needs to be reversed:

---

## Database Migrations (Alembic)

Murphy System uses Alembic for database schema migrations.

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Check current migration status
alembic current

# View migration history
alembic history
```

The `POSTGRES_PASSWORD` environment variable is **required** for production deployments:

```
POSTGRES_PASSWORD=<strong-random-password>
```

Generate a secure password:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### Rolling Back Migrations

```bash
# Roll back one migration step
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision_id>
```

---

```bash
# List available backups
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
for m in mgr.list_backups():
    print(m.backup_id, m.backup_type, m.status, m.created_at)
"

# Restore from a specific backup
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
result = mgr.restore_backup('<backup-id>')
print(result.status, result.errors)
"
```

---

## Backup and Disaster Recovery

See [docs/RUNBOOKS.md](docs/RUNBOOKS.md) for full incident response and recovery procedures.

### RPO and RTO targets

| Metric | Target | Implementation |
|---|---|---|
| **RPO** (Recovery Point Objective) | 1 hour | Hourly automated backups |
| **RTO** (Recovery Time Objective) | 30 minutes | Automated restore + blackstart sequence |

### Automated backup schedule

The `BackupScheduler` in `src/backup_disaster_recovery.py` runs on the following schedule:

| Backup type | Frequency | Retention |
|---|---|---|
| Full | Every 6 hours | 30 days |
| Config only | Every 1 hour | 7 days |
| State only | Every 30 minutes | 3 days |

Start the scheduler:

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from backup_disaster_recovery import BackupManager, BackupScheduler, LocalStorageBackend
from pathlib import Path
mgr = BackupManager(LocalStorageBackend(Path('/opt/Murphy-System/backups')))
sched = BackupScheduler(mgr)
sched.start()
print('Backup scheduler running. Press Ctrl+C to stop.')
import time
try:
    while True: time.sleep(60)
except KeyboardInterrupt:
    sched.stop()
"
```

In production, the scheduler is started automatically by the Murphy runtime when `MURPHY_BACKUP_ENABLED=true` is set in the environment.

### Blackstart (cold-start) recovery

If the system is completely unresponsive:

```bash
# Run the blackstart sequence
python3 -c "
import sys; sys.path.insert(0, 'src')
from blackstart_controller import BlackstartController
ctrl = BlackstartController()
seq = ctrl.blackstart()
print('Blackstart result:', seq.current_phase.value)
for e in seq.errors:
    print('Error:', e)
"

# Or use the full restore-to-stable procedure
python3 -c "
import sys; sys.path.insert(0, 'src')
from blackstart_controller import BlackstartController
ctrl = BlackstartController()
result = ctrl.restore_to_stable()
print('Restored:', result['restored'])
"
```

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*

# Deployment Guide - Murphy System Runtime

**Complete deployment instructions for all environments**

---

## Table of Contents

1. [Overview](#overview)
2. [Deployment Modes](#deployment-modes)
3. [Development Deployment](#development-deployment)
4. [Staging Deployment](#staging-deployment)
5. [Production Deployment](#production-deployment)
6. [Enterprise Deployment](#enterprise-deployment)
7. [Cloud Deployment](#cloud-deployment)
8. [Monitoring and Maintenance](#monitoring-and-maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Murphy System Runtime supports multiple deployment modes to suit different use cases:

- **Development Mode**: Local development and testing
- **Staging Mode**: Pre-production testing
- **Production Mode**: Full production deployment
- **Enterprise Mode**: Large-scale enterprise deployment

Choose the deployment mode that best fits your requirements.

---

## Deployment Modes

### Development Mode

**Purpose**: Local development and testing

**Environment**:
- Single machine
- Minimal resources
- Debug logging enabled
- No persistence
- No monitoring

**Resources**:
- RAM: 4GB minimum, 8GB recommended
- CPU: 2 cores minimum
- Disk: 500MB free space

### Staging Mode

**Purpose**: Pre-production testing

**Environment**:
- Single or multiple machines
- Moderate resources
- Info logging enabled
- Basic persistence
- Basic monitoring

**Resources**:
- RAM: 8GB minimum, 16GB recommended
- CPU: 4 cores minimum
- Disk: 1GB free space

### Production Mode

**Purpose**: Full production deployment

**Environment**:
- Multiple machines or containers
- High resources
- Warn logging enabled
- Full persistence
- Comprehensive monitoring

**Resources**:
- RAM: 16GB minimum, 32GB recommended
- CPU: 8 cores minimum
- Disk: 2GB free space

### Enterprise Mode

**Purpose**: Large-scale enterprise deployment

**Environment**:
- Distributed systems
- High resources
- Error logging enabled
- Enterprise persistence
- Enterprise monitoring

**Resources**:
- RAM: 32GB minimum, 64GB recommended
- CPU: 16 cores minimum
- Disk: 5GB free space

---

## Development Deployment

### Step 1: Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements_murphy_1.0.txt
```

### Step 2: Configure Development Settings

Edit `config/murphy.yaml` to override development defaults:

```yaml
# config/murphy.yaml — development overrides
system:
  env: development

api:
  host: "localhost"
  port: 8000

logging:
  level: DEBUG
  format: text

cache:
  enabled: false
  ttl: 300
```

You can also override individual settings via environment variables (env vars always win over YAML):
```bash
export LOG_LEVEL=DEBUG
export MURPHY_ENV=development
```

### Step 3: Start the Server

```bash
# Start API server
python murphy_system_1.0_runtime.py

# Or start with an explicit environment override
MURPHY_ENV=development python murphy_system_1.0_runtime.py
```

### Step 4: Verify Deployment

```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Test system build
curl -X POST http://localhost:8000/api/system/build \
  -H "Content-Type: application/json" \
  -d '{"description": "Test system"}'
```

### Step 5: Start Development

You're now ready to develop and test!

---

## Staging Deployment

### Step 1: Prepare Environment

```bash
# Create staging directory
mkdir -p /opt/murphy-staging
cd /opt/murphy-staging

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements_murphy_1.0.txt
```

### Step 2: Configure Staging Settings

Edit `config/murphy.yaml` to set staging defaults (or use environment variables — env vars always win):

```yaml
# config/murphy.yaml — staging overrides
system:
  env: staging

api:
  host: "0.0.0.0"
  port: 8000

logging:
  level: INFO
  format: json
  file: "/var/log/murphy-staging.log"

cache:
  enabled: true
  ttl: 3600
```

For secrets and per-deployment values, use environment variables or a `.env` file — never the YAML file:
```bash
export MURPHY_ENV=staging
export DATABASE_URL=sqlite:////var/lib/murphy-staging/data.db
```

### Step 3: Set Up System Service

Create `/etc/systemd/system/murphy-staging.service`:

```ini
[Unit]
Description=Murphy System Runtime Staging Server
After=network.target

[Service]
Type=simple
User=murphy
Group=murphy
WorkingDirectory=/opt/murphy-staging
Environment="PATH=/opt/murphy-staging/venv/bin"
ExecStart=/opt/murphy-staging/venv/bin/python murphy_system_1.0_runtime.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Create user
sudo useradd -r -s /bin/false murphy

# Set permissions
sudo chown -R murphy:murphy /opt/murphy-staging
sudo mkdir -p /var/log/murphy-staging
sudo chown -R murphy:murphy /var/log/murphy-staging
sudo mkdir -p /var/lib/murphy-staging
sudo chown -R murphy:murphy /var/lib/murphy-staging

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable murphy-staging
sudo systemctl start murphy-staging

# Check status
sudo systemctl status murphy-staging
```

### Step 4: Configure Reverse Proxy (Optional)

If using nginx, create `/etc/nginx/sites-available/murphy-staging`:

```nginx
upstream murphy_staging {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name staging.yourdomain.com;

    location / {
        proxy_pass http://murphy_staging;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/murphy-staging /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 5: Verify Deployment

```bash
# Test health endpoint
curl http://staging.yourdomain.com/api/health

# Run load tests
python tests/test_load.py
```

---

## Production Deployment

### Step 1: Prepare Environment

```bash
# Create production directory
mkdir -p /opt/murphy-production
cd /opt/murphy-production

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install --no-cache-dir -r requirements_murphy_1.0.txt
```

### Step 2: Configure Production Settings

Edit `config/murphy.yaml` for production defaults:

```yaml
# config/murphy.yaml — production overrides
system:
  env: production

api:
  host: "0.0.0.0"
  port: 8000

logging:
  level: WARNING
  format: json
  file: "/var/log/murphy-production.log"
  backup_count: 30

cache:
  enabled: true
  ttl: 86400

safety:
  fail_closed: true
  governance_strict: true
```

> **Important:** Production secrets (`DATABASE_URL`, `MURPHY_API_KEYS`,
> `MURPHY_CREDENTIAL_MASTER_KEY`, `JWT_SECRET`) must **never** be stored in
> `config/murphy.yaml`. Use environment variables loaded from a secrets manager:
>
> ```bash
> # Docker Swarm secrets
> docker secret create murphy_api_key ./api_key.txt
>
> # Kubernetes secrets
> kubectl create secret generic murphy-secrets \
>   --from-literal=DATABASE_URL="postgresql://..."
>
> # HashiCorp Vault
> vault kv put secret/murphy DATABASE_URL="postgresql://..."
> ```

### Step 3: Set Up Database (PostgreSQL)

```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE murphy_production;
CREATE USER murphy_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE murphy_production TO murphy_user;
\q
```

Set the database connection in your environment file:

> **Security:** Never commit credentials to version control.  Use your
> platform's secrets manager (AWS Secrets Manager, HashiCorp Vault,
> Kubernetes Secrets, etc.) or a protected `.env` file with restricted
> permissions (`chmod 600`) that is listed in `.gitignore`.

```bash
export DATABASE_URL=postgresql://murphy_user:your_password@localhost:5432/murphy_production
export MURPHY_DB_MODE=live
export MURPHY_ENV=production
export MURPHY_AUTO_MIGRATE=false   # Migrate explicitly before each deploy
```

**Run Alembic migrations before starting the service:**

```bash
cd /opt/murphy-production/Murphy\ System
bash scripts/db_migrate.sh status   # Check current state
bash scripts/db_migrate.sh          # Apply all pending migrations
```

> **⚠️ Important:** Never run with `MURPHY_DB_MODE=stub` in production.
> Murphy System will raise a `RuntimeError` at startup if stub mode is
> detected in a `production` or `staging` environment.

> **Note:** `MURPHY_AUTO_MIGRATE=false` is the default in production and
> staging.  Always run `scripts/db_migrate.sh` explicitly as part of your
> deployment pipeline before restarting the service.

### Step 4: Set Up System Service

Create `/etc/systemd/system/murphy-production.service`:

```ini
[Unit]
Description=Murphy System Runtime Production Server
After=network.target postgresql.service

[Service]
Type=simple
User=murphy
Group=murphy
WorkingDirectory=/opt/murphy-production
Environment="PATH=/opt/murphy-production/venv/bin"
EnvironmentFile=/etc/murphy-production/environment
ExecStart=/opt/murphy-production/venv/bin/python murphy_system_1.0_runtime.py
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/murphy-production /var/lib/murphy-production

# Resource Limits
LimitNOFILE=65536
LimitNPROC=4096
MemoryLimit=4G

[Install]
WantedBy=multi-user.target
```

Create environment file `/etc/murphy-production/environment`:

```bash
MURPHY_SECRET_KEY=your-secret-key-here
MURPHY_DB_PASSWORD=your-database-password
MURPHY_SLACK_WEBHOOK=your-slack-webhook-url
```

Enable and start the service:

```bash
# Set permissions
sudo useradd -r -s /bin/false murphy
sudo chown -R murphy:murphy /opt/murphy-production
sudo mkdir -p /var/log/murphy-production
sudo chown -R murphy:murphy /var/log/murphy-production

# Set file permissions
sudo chmod 600 /etc/murphy-production/environment

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable murphy-production
sudo systemctl start murphy-production

# Check status
sudo systemctl status murphy-production
```

### Step 5: Configure Reverse Proxy (nginx)

Create `/etc/nginx/sites-available/murphy-production`:

```nginx
upstream murphy_production {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
    ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 10M;

    location / {
        proxy_pass http://murphy_production;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://murphy_production/api/health;
        access_log off;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/murphy-production /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6: Set Up Monitoring

Install and configure monitoring tools:

```bash
# Install Prometheus (optional)
sudo apt-get install prometheus

# Install Grafana (optional)
sudo apt-get install grafana

# Configure monitoring
# Add metrics endpoint to your monitoring system
```

### Step 7: Verify Deployment

```bash
# Test health endpoint
curl https://yourdomain.com/api/health

# Run integration tests
python tests/test_integration_corrected.py

# Run load tests
python tests/test_load.py

# Run stress tests
python tests/test_stress.py
```

---

## Enterprise Deployment

### Step 1: Architecture Design

Enterprise deployment typically uses:

- **Load Balancer**: nginx or HAProxy
- **Application Servers**: Multiple instances
- **Database**: PostgreSQL cluster
- **Cache**: Redis cluster
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK Stack or Splunk

### Step 2: High Availability Setup

Set up multiple instances:

```bash
# Instance 1
/opt/murphy-production-1

# Instance 2
/opt/murphy-production-2

# Instance 3
/opt/murphy-production-3
```

Configure load balancer:

```nginx
upstream murphy_cluster {
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
    server 10.0.1.12:8000;
}
```

### Step 3: Database Clustering

Set up PostgreSQL cluster:

```bash
# Primary
sudo -u postgres psql
CREATE DATABASE murphy_production;

# Replicas
# Configure streaming replication
```

### Step 4: Cache Clustering

Set up Redis cluster:

```bash
# Install Redis
sudo apt-get install redis-server

# Configure cluster
# Edit /etc/redis/redis.conf
cluster-enabled yes
cluster-config-file nodes.conf
```

### Step 5: Enterprise Monitoring

Set up comprehensive monitoring:

- **Application Metrics**: Prometheus
- **Log Aggregation**: ELK Stack
- **APM**: Datadog or New Relic
- **Alerting**: PagerDuty or OpsGenie

---

## Cloud Deployment

### AWS Deployment

#### Using EC2

```bash
# Launch EC2 instance
# Install dependencies
# Configure as production deployment

# Use Auto Scaling Group for scalability
# Use Load Balancer for distribution
```

#### Using ECS/Fargate

```bash
# Create task definition
{
  "family": "murphy-runtime",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "4096",
  "memory": "8192",
  "containerDefinitions": [
    {
      "name": "murphy-runtime",
      "image": "your-registry/murphy-runtime:v1.0.0",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ]
    }
  ]
}
```

### GCP Deployment

```bash
# Use Cloud Run
gcloud run deploy murphy-runtime \
  --image gcr.io/your-project/murphy-runtime \
  --platform managed \
  --region us-central1 \
  --memory 8Gi \
  --cpu 4
```

### Azure Deployment

```bash
# Use Container Instances
az container create \
  --resource-group myResourceGroup \
  --name murphy-runtime \
  --image your-registry/murphy-runtime:v1.0.0 \
  --cpu 4 \
  --memory 8 \
  --ports 8000
```

---

## Monitoring and Maintenance

### Health Checks

```bash
# Check service status
sudo systemctl status murphy-production

# Check logs
sudo journalctl -u murphy-production -f

# Check health endpoint
curl https://yourdomain.com/api/health
```

### Log Management

```bash
# View logs
tail -f /var/log/murphy-production.log

# Rotate logs
logrotate -f /etc/logrotate.d/murphy-production

# Archive logs
find /var/log/murphy-production -name "*.log" -mtime +30 -delete
```

### Backup Procedures

```bash
# Backup database
pg_dump -U murphy_user murphy_production > backup.sql

# Backup configuration
tar -czf config-backup.tar.gz /opt/murphy-production/config

# Schedule backups
crontab -e
# Add: 0 2 * * * /scripts/backup.sh
```

### Updates and Upgrades

```bash
# Stop service
sudo systemctl stop murphy-production

# Update code
cd /opt/murphy-production
git pull origin main

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements_murphy_1.0.txt

# Run migrations (if needed)
python scripts/migrate.py

# Start service
sudo systemctl start murphy-production
```

---

## Troubleshooting

### Service Won't Start

**Problem**: Service fails to start

**Solution**:
```bash
# Check logs
sudo journalctl -u murphy-production -n 50

# Check configuration (validate YAML syntax)
python -c "import yaml; yaml.safe_load(open('config/murphy.yaml'))"

# Check ports
sudo netstat -tuln | grep 8000
```

### High Memory Usage

**Problem**: Service consuming excessive memory

**Solution**:
```bash
# Check memory usage
ps aux | grep murphy

# Reduce cache TTL in config/murphy.yaml:
# cache:
#   ttl: 1800  # Reduce from 3600

# Or via environment variable (takes precedence):
export MURPHY_CACHE__TTL=1800

# Restart service
sudo systemctl restart murphy-production
```

### Slow Performance

**Problem**: Slow response times

**Solution**:
```bash
# Check system resources
htop

# Check database queries
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"

# Enable caching in config/murphy.yaml:
# cache:
#   enabled: true
#   ttl: 86400
```

### Database Connection Issues

**Problem**: Cannot connect to database

**Solution**:
```bash
# Check database status
sudo systemctl status postgresql

# Check connection
psql -U murphy_user -d murphy_production -h localhost

# Check firewall
sudo ufw status
```

---

## Next Steps

- [Configuration](CONFIGURATION.md) - Detailed configuration options
- [Scaling](SCALING.md) - Scaling strategies
- [Maintenance](MAINTENANCE.md) - Ongoing maintenance procedures

---

## Production Security Hardening Checklist

Before deploying to production, verify every item below:

### Credentials & Secrets

- [ ] `POSTGRES_PASSWORD` is set to a strong, random value (not the default)
- [ ] `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` are set (no defaults)
- [ ] `REDIS_PASSWORD` is set for authenticated Redis access
- [ ] `JWT_SECRET_KEY` is at least 32 characters and not a default value
- [ ] `MURPHY_API_KEYS` is set with production API key(s)
- [ ] `MURPHY_CREDENTIAL_MASTER_KEY` is set (Fernet key)
- [ ] `PAYPAL_WEBHOOK_SECRET` and `COINBASE_WEBHOOK_SECRET` are set
- [ ] No secrets are committed to source control (check `.gitignore`)

### Network Security

- [ ] PostgreSQL port (5432) is **not** exposed to the public internet
- [ ] Redis port (6379) is **not** exposed to the public internet
- [ ] Prometheus port (9090) is **not** exposed to the public internet
- [ ] Grafana (3000) is behind a reverse proxy with TLS
- [ ] Murphy API (8000) is behind a reverse proxy with TLS
- [ ] `MURPHY_CORS_ORIGINS` is set to your production domain(s) only (not `*`)

### Application Configuration

- [ ] `MURPHY_ENV` is set to `production` (authentication is enforced)
- [ ] `DATABASE_URL` points to PostgreSQL (not SQLite)
- [ ] Deployment readiness check passes: `curl /api/readiness`
- [ ] Health check endpoint is accessible: `curl /api/health`

### Monitoring

- [ ] Prometheus is collecting Murphy System metrics
- [ ] Grafana dashboards are configured and accessible
- [ ] Alert rules are configured for critical failures
- [ ] Log aggregation is operational

---

## Secrets Management

Production deployments **must not** store credentials in plaintext `.env` files.
Use one of the following approaches:

### Docker Secrets

```bash
# Create secrets from files
echo -n "my-api-key" | docker secret create murphy_api_key -
docker secret create murphy_credential_key ./fernet_key.txt

# Reference in docker-compose.yml
services:
  murphy-api:
    secrets:
      - murphy_api_key
      - murphy_credential_key
    environment:
      MURPHY_API_KEYS_FILE: /run/secrets/murphy_api_key
      MURPHY_CREDENTIAL_MASTER_KEY_FILE: /run/secrets/murphy_credential_key

secrets:
  murphy_api_key:
    external: true
  murphy_credential_key:
    external: true
```

### Kubernetes Secrets

```bash
# Create secrets
kubectl create secret generic murphy-secrets \
  --from-literal=api-key="$(openssl rand -base64 32)" \
  --from-literal=credential-master-key="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Reference in Pod spec (set via env vars)
env:
  - name: MURPHY_API_KEYS
    valueFrom:
      secretKeyRef:
        name: murphy-secrets
        key: api-key
  - name: MURPHY_CREDENTIAL_MASTER_KEY
    valueFrom:
      secretKeyRef:
        name: murphy-secrets
        key: credential-master-key
```

### HashiCorp Vault Integration

```bash
# Store secrets
vault kv put secret/murphy/production \
  api_key="$(openssl rand -base64 32)" \
  credential_master_key="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Read secrets (use Vault Agent or envconsul to inject into process env)
vault kv get -field=api_key secret/murphy/production
```

### Required Secrets

| Secret | Environment Variable | How to Generate |
|--------|---------------------|-----------------|
| API key(s) | `MURPHY_API_KEYS` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Credential master key | `MURPHY_CREDENTIAL_MASTER_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| JWT secret | `JWT_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**
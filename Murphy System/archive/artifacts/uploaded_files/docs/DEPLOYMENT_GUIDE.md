# Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Initial Setup](#initial-setup)
5. [Verification](#verification)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum Requirements:**
- **OS:** Ubuntu 20.04 LTS or Debian 11+
- **CPU:** 2 cores
- **RAM:** 4 GB
- **Disk:** 50 GB SSD
- **Network:** Static IP address

**Recommended Requirements:**
- **OS:** Ubuntu 22.04 LTS
- **CPU:** 4 cores
- **RAM:** 8 GB
- **Disk:** 100 GB SSD
- **Network:** Static IP with domain name

### Software Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    postgresql-15 \
    postgresql-contrib \
    nodejs \
    npm \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    nginx \
    certbot \
    python3-certbot-nginx
```

### Network Requirements

**Ports to Open:**
- 80 (HTTP)
- 443 (HTTPS)
- 5432 (PostgreSQL - internal only)
- 5678 (n8n - internal only)
- 8081 (Health Check - internal only)
- 8082 (Monitoring API - internal only)
- 8083 (Dashboards - internal only)

**Firewall Configuration:**
```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block direct access to internal services
sudo ufw deny 5432/tcp
sudo ufw deny 5678/tcp
sudo ufw deny 8081/tcp
sudo ufw deny 8082/tcp
sudo ufw deny 8083/tcp

# Enable firewall
sudo ufw enable
```

---

## Installation Steps

### Step 1: Create Application User

```bash
# Create automation user
sudo useradd -m -s /bin/bash automation
sudo usermod -aG sudo automation

# Switch to automation user
sudo su - automation
```

### Step 2: Install n8n

```bash
# Install n8n globally
sudo npm install -g n8n@2.4.7

# Verify installation
n8n --version
```

### Step 3: Setup PostgreSQL

```bash
# Switch to postgres user
sudo su - postgres

# Create database and user
psql << EOF
CREATE DATABASE automation_platform;
CREATE USER automation_user WITH ENCRYPTED PASSWORD 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE automation_platform TO automation_user;
\c automation_platform
GRANT ALL ON SCHEMA public TO automation_user;
EOF

# Exit postgres user
exit
```

### Step 4: Create Directory Structure

```bash
# Create application directories
sudo mkdir -p /opt/automation-platform
sudo chown -R automation:automation /opt/automation-platform

# Switch to automation user
sudo su - automation
cd /opt/automation-platform

# Create subdirectories
mkdir -p {config,scripts,storage/{documents,reports,logs},backups,workflows,server,dashboard,docs,tests}
```

### Step 5: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv /opt/automation-platform/venv

# Activate virtual environment
source /opt/automation-platform/venv/bin/activate

# Install dependencies
pip install psycopg2-binary flask flask-cors
```

### Step 6: Deploy Application Files

```bash
# Copy all files from workspace to /opt/automation-platform
# (Assuming files are in /workspace)

cd /opt/automation-platform

# Copy database schemas
cp /workspace/database/*.sql database/

# Copy workflows
cp -r /workspace/workflows/* workflows/

# Copy server files
cp /workspace/server/*.py server/

# Copy dashboard files
cp -r /workspace/dashboard/* dashboard/

# Copy scripts
cp /workspace/scripts/*.sh scripts/
cp /workspace/scripts/*.py scripts/

# Copy configuration
cp /workspace/config/.env.example config/.env

# Set permissions
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

### Step 7: Initialize Database

```bash
# Run database initialization scripts
cd /opt/automation-platform

# Create all tables
psql -U automation_user -d automation_platform -f database/schema.sql
psql -U automation_user -d automation_platform -f database/add_tasks_config_simple.sql
psql -U automation_user -d automation_platform -f database/add_security_tables.sql
psql -U automation_user -d automation_platform -f database/add_monitoring_tables.sql

# Verify tables
psql -U automation_user -d automation_platform -c "\dt"
```

### Step 8: Import Workflows

```bash
# Import workflows into n8n
cd /opt/automation-platform

# Import INTAKE_v1 workflows
python3 scripts/import_intake_workflows.py
python3 scripts/activate_intake_workflows.py

# Import DOCS_v1 workflows
python3 scripts/import_docs_workflows.py
python3 scripts/activate_docs_workflows.py

# Import TASKS_v1 workflows
python3 scripts/import_tasks_workflows.py
python3 scripts/activate_tasks_workflows.py

# Import SECURITY_v1 workflows
python3 scripts/import_security_workflows.py
python3 scripts/activate_security_workflows.py

# Import MONITOR_v1 workflows
python3 scripts/import_monitor_workflows.py
python3 scripts/activate_monitor_workflows.py
```

---

## Configuration

### Step 1: Configure Environment Variables

```bash
# Edit configuration file
cd /opt/automation-platform
nano config/.env
```

**Configuration Template:**
```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=automation_platform
POSTGRES_USER=automation_user
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
DB_ENCRYPTION_KEY=GENERATE_32_CHAR_KEY_HERE

# n8n Configuration
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_ENCRYPTION_KEY=GENERATE_32_CHAR_KEY_HERE
N8N_EDITOR_BASE_URL=http://your-domain.com
N8N_WEBHOOK_URL=http://your-domain.com

# Storage Configuration
LOCAL_STORAGE_PATH=/opt/automation-platform/storage

# Security Configuration
JWT_SECRET=GENERATE_32_CHAR_KEY_HERE
API_RATE_LIMIT=100

# Monitoring Configuration
LOG_LEVEL=info
LOG_RETENTION_DAYS=30
```

**Generate Secure Keys:**
```bash
# Generate encryption keys
openssl rand -base64 32

# Generate JWT secret
openssl rand -hex 32
```

### Step 2: Configure n8n

```bash
# Set n8n environment variables
export N8N_ENCRYPTION_KEY="your_encryption_key_here"
export N8N_BASIC_AUTH_ACTIVE=true
export N8N_BASIC_AUTH_USER=admin
export N8N_BASIC_AUTH_PASSWORD="CHANGE_THIS_PASSWORD"
export N8N_HOST=0.0.0.0
export N8N_PORT=5678
export N8N_PROTOCOL=http

# Save to profile
echo 'export N8N_ENCRYPTION_KEY="your_encryption_key_here"' >> ~/.bashrc
echo 'export N8N_BASIC_AUTH_ACTIVE=true' >> ~/.bashrc
echo 'export N8N_BASIC_AUTH_USER=admin' >> ~/.bashrc
echo 'export N8N_BASIC_AUTH_PASSWORD="CHANGE_THIS_PASSWORD"' >> ~/.bashrc
```

### Step 3: Configure Nginx Reverse Proxy

```bash
# Create nginx configuration
sudo nano /etc/nginx/sites-available/automation-platform
```

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # n8n
    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Monitoring Dashboard
    location /monitoring {
        proxy_pass http://localhost:8083;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Monitoring API
    location /api {
        proxy_pass http://localhost:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Health Check
    location /health {
        proxy_pass http://localhost:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Enable Configuration:**
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/automation-platform /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Step 4: Configure SSL/TLS

```bash
# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

---

## Initial Setup

### Step 1: Create Systemd Services

#### n8n Service

```bash
sudo nano /etc/systemd/system/n8n.service
```

```ini
[Unit]
Description=n8n Workflow Automation
After=network.target postgresql.service

[Service]
Type=simple
User=automation
WorkingDirectory=/opt/automation-platform
Environment="N8N_ENCRYPTION_KEY=your_encryption_key_here"
Environment="N8N_BASIC_AUTH_ACTIVE=true"
Environment="N8N_BASIC_AUTH_USER=admin"
Environment="N8N_BASIC_AUTH_PASSWORD=your_password_here"
ExecStart=/usr/bin/n8n start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Health Check Service

```bash
sudo nano /etc/systemd/system/health-check.service
```

```ini
[Unit]
Description=Health Check Server
After=network.target postgresql.service n8n.service

[Service]
Type=simple
User=automation
WorkingDirectory=/opt/automation-platform
ExecStart=/opt/automation-platform/venv/bin/python3 server/health_check.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Monitoring API Service

```bash
sudo nano /etc/systemd/system/monitoring-api.service
```

```ini
[Unit]
Description=Monitoring API Server
After=network.target postgresql.service

[Service]
Type=simple
User=automation
WorkingDirectory=/opt/automation-platform
ExecStart=/opt/automation-platform/venv/bin/python3 server/monitoring_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and Start Services:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable n8n
sudo systemctl enable health-check
sudo systemctl enable monitoring-api

# Start services
sudo systemctl start n8n
sudo systemctl start health-check
sudo systemctl start monitoring-api

# Check status
sudo systemctl status n8n
sudo systemctl status health-check
sudo systemctl status monitoring-api
```

### Step 2: Configure Backup Cron Job

```bash
# Edit crontab
crontab -e

# Add backup job (daily at 2 AM)
0 2 * * * /opt/automation-platform/scripts/backup.sh

# Add log cleanup (weekly on Sunday at 3 AM)
0 3 * * 0 find /opt/automation-platform/storage/logs -name "*.log" -mtime +7 -exec gzip {} \;
```

### Step 3: Create First Client

```bash
# Connect to database
psql -U automation_user -d automation_platform

# Insert client
INSERT INTO clients (client_name, client_slug, is_active, created_at)
VALUES ('Demo Client', 'demo-client', TRUE, NOW())
RETURNING client_id;

# Enable automation packs
INSERT INTO client_packs (client_id, pack_name, pack_version, is_enabled)
VALUES 
    (1, 'INTAKE_v1', '1.0.0', TRUE),
    (1, 'DOCS_v1', '1.0.0', TRUE),
    (1, 'TASKS_v1', '1.0.0', TRUE);

# Exit
\q
```

---

## Verification

### Step 1: Verify Services

```bash
# Check all services
sudo systemctl status postgresql
sudo systemctl status n8n
sudo systemctl status health-check
sudo systemctl status monitoring-api
sudo systemctl status nginx

# Check ports
sudo netstat -tulpn | grep -E "5432|5678|8081|8082|80|443"
```

### Step 2: Verify Health Endpoints

```bash
# System health
curl http://localhost:8081/health

# Monitoring API
curl http://localhost:8082/api/health

# n8n (should require auth)
curl http://localhost:5678/healthz
```

### Step 3: Verify Workflows

```bash
# Check active workflows in n8n database
sqlite3 /home/automation/.n8n/database.sqlite << EOF
SELECT name, active FROM workflow_entity WHERE active = 1;
EOF

# Check workflow executions in PostgreSQL
psql -U automation_user -d automation_platform -c "SELECT COUNT(*) FROM workflow_executions"
```

### Step 4: Test Workflow Execution

```bash
# Test lead capture (replace with actual webhook URL)
curl -X POST http://your-domain.com/webhook/intake-leads \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User",
    "company_name": "Test Company",
    "source": "api_test"
  }'

# Verify lead was created
psql -U automation_user -d automation_platform -c "SELECT * FROM leads WHERE email = 'test@example.com'"
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] All services configured and tested
- [ ] SSL/TLS certificates installed
- [ ] Firewall rules configured
- [ ] Backup system tested
- [ ] Monitoring dashboards accessible
- [ ] Database backups verified
- [ ] Environment variables secured
- [ ] Admin credentials changed
- [ ] Documentation reviewed
- [ ] Rollback plan prepared

### Deployment Steps

1. **Final Configuration Review**
   ```bash
   # Review all configuration files
   cat /opt/automation-platform/config/.env
   cat /etc/nginx/sites-available/automation-platform
   ```

2. **Security Hardening**
   ```bash
   # Change default passwords
   # Update encryption keys
   # Configure firewall
   # Enable fail2ban
   sudo apt install fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```

3. **Performance Tuning**
   ```bash
   # Optimize PostgreSQL
   sudo nano /etc/postgresql/15/main/postgresql.conf
   
   # Recommended settings:
   # shared_buffers = 2GB
   # effective_cache_size = 6GB
   # maintenance_work_mem = 512MB
   # checkpoint_completion_target = 0.9
   # wal_buffers = 16MB
   # default_statistics_target = 100
   # random_page_cost = 1.1
   # effective_io_concurrency = 200
   # work_mem = 10MB
   # min_wal_size = 1GB
   # max_wal_size = 4GB
   
   # Restart PostgreSQL
   sudo systemctl restart postgresql
   ```

4. **Enable Monitoring**
   ```bash
   # Verify monitoring is working
   curl http://localhost:8081/health
   curl http://localhost:8082/api/metrics
   
   # Access dashboards
   # http://your-domain.com/monitoring
   ```

5. **Final Testing**
   ```bash
   # Run integration tests
   cd /opt/automation-platform/tests
   python3 run_all_tests.py
   ```

### Post-Deployment

1. **Monitor System**
   - Check dashboards every hour for first 24 hours
   - Review logs for errors
   - Monitor resource usage

2. **Verify Backups**
   ```bash
   # Check backup was created
   ls -lh /opt/automation-platform/backups/
   
   # Test restore (on test system)
   ```

3. **Document Deployment**
   - Record deployment date and time
   - Document any issues encountered
   - Update runbooks if needed

---

## Troubleshooting

### Issue: Services Won't Start

**Check logs:**
```bash
sudo journalctl -u n8n -n 50
sudo journalctl -u health-check -n 50
sudo journalctl -u monitoring-api -n 50
```

**Common solutions:**
- Check environment variables
- Verify database connection
- Check file permissions
- Review configuration files

### Issue: Database Connection Failures

**Verify PostgreSQL:**
```bash
sudo systemctl status postgresql
sudo -u postgres psql -c "\l"
```

**Check connection:**
```bash
psql -U automation_user -d automation_platform -c "SELECT 1"
```

### Issue: Nginx Configuration Errors

**Test configuration:**
```bash
sudo nginx -t
```

**Check logs:**
```bash
sudo tail -f /var/log/nginx/error.log
```

### Issue: SSL Certificate Problems

**Renew certificate:**
```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

---

## Rollback Procedure

### If Deployment Fails

1. **Stop new services**
   ```bash
   sudo systemctl stop n8n
   sudo systemctl stop health-check
   sudo systemctl stop monitoring-api
   ```

2. **Restore database**
   ```bash
   psql -U postgres -d postgres -c "DROP DATABASE automation_platform"
   psql -U postgres -d postgres -c "CREATE DATABASE automation_platform"
   psql -U postgres -d automation_platform -f /opt/automation-platform/backups/latest_backup.sql
   ```

3. **Restore configuration**
   ```bash
   # Restore from backup
   cp /opt/automation-platform/backups/config_backup/.env /opt/automation-platform/config/.env
   ```

4. **Restart services**
   ```bash
   sudo systemctl start postgresql
   sudo systemctl start n8n
   sudo systemctl start health-check
   sudo systemctl start monitoring-api
   ```

---

## Support

**Documentation:**
- System Architecture: `/opt/automation-platform/docs/SYSTEM_ARCHITECTURE.md`
- Operations Manual: `/opt/automation-platform/docs/OPERATIONS_MANUAL.md`
- API Documentation: `/opt/automation-platform/docs/API_DOCUMENTATION.md`

**Contact:**
- Technical Support: support@automation-platform.com
- Emergency: emergency@automation-platform.com

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-29  
**Maintained By:** DevOps Team
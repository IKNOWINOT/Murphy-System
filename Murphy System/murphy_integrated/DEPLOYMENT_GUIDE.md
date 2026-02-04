# Murphy System - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Production Deployment](#production-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Configuration](#configuration)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **Python:** 3.11 or higher
- **RAM:** Minimum 4GB, recommended 8GB+
- **Disk Space:** 2GB minimum
- **OS:** Linux, macOS, or Windows

### Required Software
- Python 3.11+
- pip (Python package manager)
- Git (for version control)
- Optional: Docker, Kubernetes

---

## Local Development Setup

### 1. Clone/Extract the Repository
```bash
# If from zip
unzip murphy_integrated.zip
cd murphy_integrated

# If from git
git clone <repository-url>
cd murphy_integrated
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Verify installation
python tests/test_basic_imports.py
```

Expected output:
```
✓ UnifiedConfidenceEngine imported successfully
✓ IntegratedCorrectionSystem imported successfully
✓ IntegratedFormExecutor imported successfully
✓ IntegratedHITLMonitor imported successfully
✓ Form intake modules imported successfully

Results: 5/5 tests passed
```

### 4. Start the Server
```bash
# Start the integrated backend
python murphy_complete_backend_extended.py
```

Server will start on: **http://localhost:8000**

### 5. Access the UI
Open your browser and navigate to:
```
http://localhost:8000/murphy_ui_integrated.html
```

---

## Production Deployment

### 1. Prepare Production Environment

#### Update Configuration
Create `config_production.py`:
```python
# Production configuration
DEBUG = False
HOST = '0.0.0.0'
PORT = 8000
WORKERS = 4

# Security
SECRET_KEY = 'your-secret-key-here'
ALLOWED_ORIGINS = ['https://yourdomain.com']

# Database (if using)
DATABASE_URL = 'postgresql://user:pass@localhost/murphy'

# Logging
LOG_LEVEL = 'INFO'
LOG_FILE = '/var/log/murphy/murphy.log'
```

#### Set Environment Variables
```bash
export MURPHY_ENV=production
export MURPHY_SECRET_KEY=your-secret-key
export MURPHY_DATABASE_URL=postgresql://...
```

### 2. Use Production WSGI Server

#### Install Gunicorn
```bash
pip install gunicorn
```

#### Start with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/murphy/access.log \
  --error-logfile /var/log/murphy/error.log \
  murphy_complete_backend_extended:app
```

### 3. Setup Nginx Reverse Proxy

#### Install Nginx
```bash
# Ubuntu/Debian
sudo apt-get install nginx

# CentOS/RHEL
sudo yum install nginx
```

#### Configure Nginx
Create `/etc/nginx/sites-available/murphy`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Static files
    location /static {
        alias /path/to/murphy_integrated/static;
        expires 30d;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/murphy /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Setup SSL with Let's Encrypt
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 5. Create Systemd Service

Create `/etc/systemd/system/murphy.service`:
```ini
[Unit]
Description=Murphy System Integrated Backend
After=network.target

[Service]
Type=notify
User=murphy
Group=murphy
WorkingDirectory=/opt/murphy_integrated
Environment="PATH=/opt/murphy_integrated/venv/bin"
ExecStart=/opt/murphy_integrated/venv/bin/gunicorn \
    -w 4 \
    -b 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/murphy/access.log \
    --error-logfile /var/log/murphy/error.log \
    murphy_complete_backend_extended:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable murphy
sudo systemctl start murphy
sudo systemctl status murphy
```

---

## Docker Deployment

### 1. Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 murphy && \
    chown -R murphy:murphy /app
USER murphy

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/system/info')"

# Start application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "120", "murphy_complete_backend_extended:app"]
```

### 2. Create docker-compose.yml
```yaml
version: '3.8'

services:
  murphy:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MURPHY_ENV=production
      - MURPHY_SECRET_KEY=${MURPHY_SECRET_KEY}
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/system/info"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - murphy
    restart: unless-stopped

volumes:
  logs:
  data:
```

### 3. Build and Run
```bash
# Build image
docker build -t murphy-system:latest .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f murphy

# Stop
docker-compose down
```

---

## Kubernetes Deployment

### 1. Create Deployment
`murphy-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: murphy-system
  labels:
    app: murphy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: murphy
  template:
    metadata:
      labels:
        app: murphy
    spec:
      containers:
      - name: murphy
        image: murphy-system:latest
        ports:
        - containerPort: 8000
        env:
        - name: MURPHY_ENV
          value: "production"
        - name: MURPHY_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: murphy-secrets
              key: secret-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/system/info
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/system/info
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 2. Create Service
`murphy-service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: murphy-service
spec:
  selector:
    app: murphy
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 3. Create HorizontalPodAutoscaler
`murphy-hpa.yaml`:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: murphy-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: murphy-system
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 4. Deploy to Kubernetes
```bash
# Create namespace
kubectl create namespace murphy

# Create secrets
kubectl create secret generic murphy-secrets \
  --from-literal=secret-key=your-secret-key \
  -n murphy

# Apply configurations
kubectl apply -f murphy-deployment.yaml -n murphy
kubectl apply -f murphy-service.yaml -n murphy
kubectl apply -f murphy-hpa.yaml -n murphy

# Check status
kubectl get pods -n murphy
kubectl get svc -n murphy

# View logs
kubectl logs -f deployment/murphy-system -n murphy
```

---

## Configuration

### Environment Variables
```bash
# Application
MURPHY_ENV=production|development
MURPHY_DEBUG=false
MURPHY_HOST=0.0.0.0
MURPHY_PORT=8000

# Security
MURPHY_SECRET_KEY=your-secret-key
MURPHY_ALLOWED_ORIGINS=https://yourdomain.com

# Database (optional)
MURPHY_DATABASE_URL=postgresql://user:pass@host/db

# Logging
MURPHY_LOG_LEVEL=INFO|DEBUG|WARNING|ERROR
MURPHY_LOG_FILE=/var/log/murphy/murphy.log

# Performance
MURPHY_WORKERS=4
MURPHY_TIMEOUT=120
```

### Configuration File
Create `config.yaml`:
```yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  timeout: 120

security:
  secret_key: ${MURPHY_SECRET_KEY}
  allowed_origins:
    - https://yourdomain.com
  cors_enabled: true

logging:
  level: INFO
  file: /var/log/murphy/murphy.log
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

features:
  form_intake: true
  murphy_validation: true
  correction_capture: true
  shadow_agent: true
  hitl_monitor: true
```

---

## Monitoring

### 1. Health Checks
```bash
# System info
curl http://localhost:8000/api/system/info

# Correction statistics
curl http://localhost:8000/api/corrections/statistics

# HITL statistics
curl http://localhost:8000/api/hitl/statistics
```

### 2. Logging
```bash
# View logs
tail -f /var/log/murphy/murphy.log

# Search for errors
grep ERROR /var/log/murphy/murphy.log

# Monitor in real-time
journalctl -u murphy -f
```

### 3. Metrics (Prometheus)
Add to `murphy_complete_backend_extended.py`:
```python
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
task_counter = Counter('murphy_tasks_total', 'Total tasks executed')
task_duration = Histogram('murphy_task_duration_seconds', 'Task execution duration')

@app.route('/metrics')
def metrics():
    return generate_latest()
```

---

## Troubleshooting

### Server Won't Start
```bash
# Check port availability
sudo lsof -i :8000

# Check Python version
python --version

# Verify dependencies
pip list | grep -E "flask|pydantic|fastapi"

# Run import test
python tests/test_basic_imports.py
```

### Import Errors
```bash
# Verify all imports work
cd murphy_integrated
python tests/test_basic_imports.py

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### Performance Issues
```bash
# Increase workers
gunicorn -w 8 ...

# Increase timeout
gunicorn --timeout 300 ...

# Check system resources
htop
df -h
free -m
```

### Database Connection Issues
```bash
# Test database connection
python -c "import psycopg2; conn = psycopg2.connect('your-connection-string')"

# Check database logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

---

## Security Checklist

- [ ] Change default secret key
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Set up firewall rules
- [ ] Use environment variables for secrets
- [ ] Enable rate limiting
- [ ] Set up authentication
- [ ] Regular security updates
- [ ] Monitor access logs
- [ ] Backup data regularly

---

## Backup and Recovery

### Backup
```bash
# Backup data directory
tar -czf murphy-backup-$(date +%Y%m%d).tar.gz data/

# Backup database (if using)
pg_dump murphy_db > murphy-db-backup-$(date +%Y%m%d).sql
```

### Recovery
```bash
# Restore data
tar -xzf murphy-backup-20240101.tar.gz

# Restore database
psql murphy_db < murphy-db-backup-20240101.sql
```

---

## Support

For deployment issues:
1. Check logs: `/var/log/murphy/murphy.log`
2. Run diagnostics: `python tests/test_basic_imports.py`
3. Review documentation: `API_DOCUMENTATION.md`
4. Check system info: `curl http://localhost:8000/api/system/info`

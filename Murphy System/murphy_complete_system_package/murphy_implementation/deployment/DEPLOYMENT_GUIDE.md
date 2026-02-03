# Murphy System Deployment Guide

## Overview
This guide covers deploying Murphy System to production environments using Docker, Kubernetes, and cloud platforms.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [Post-Deployment](#post-deployment)

---

## Prerequisites

### Required Tools
- Docker 20.10+
- Kubernetes 1.24+ (for K8s deployment)
- kubectl CLI
- Python 3.11+
- Git

### Required Access
- Container registry access
- Kubernetes cluster access (for K8s deployment)
- Cloud provider credentials (for cloud deployment)
- Database credentials

### System Requirements
- **Minimum:** 4 CPU cores, 8GB RAM, 50GB storage
- **Recommended:** 8 CPU cores, 16GB RAM, 100GB storage
- **Production:** 16+ CPU cores, 32GB+ RAM, 500GB+ storage

---

## Local Development

### 1. Clone Repository

```bash
git clone https://github.com/your-org/murphy-system.git
cd murphy-system
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration
nano .env
```

**Required Environment Variables:**
```bash
MURPHY_ENV=development
MURPHY_DATA_DIR=/app/data
MURPHY_LOG_DIR=/app/logs
DATABASE_URL=postgresql://murphy:murphy@localhost:5432/murphy
REDIS_URL=redis://localhost:6379/0
API_KEY=your-development-api-key
```

### 4. Start Development Server

```bash
# Start dependencies (PostgreSQL, Redis)
docker-compose -f docker-compose.dev.yml up -d

# Run migrations
python -m murphy_implementation.migrations.run

# Start server
python -m murphy_implementation.main
```

**Access:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## Docker Deployment

### 1. Build Docker Image

```bash
# Build image
docker build -t murphy-system:latest -f murphy_implementation/deployment/Dockerfile .

# Verify image
docker images | grep murphy-system
```

### 2. Run with Docker Compose

```bash
cd murphy_implementation/deployment

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f murphy-api
```

**Services Started:**
- murphy-api (Port 8000)
- postgres (Port 5432)
- redis (Port 6379)
- prometheus (Port 9090)
- grafana (Port 3000)

### 3. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# API test
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/status
```

### 4. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Kubernetes Deployment

### 1. Prepare Cluster

```bash
# Create namespace
kubectl create namespace murphy-system

# Verify namespace
kubectl get namespaces
```

### 2. Configure Secrets

```bash
# Create secrets file
cat > secrets.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: murphy-secrets
  namespace: murphy-system
type: Opaque
stringData:
  database-url: "postgresql://murphy:YOUR_PASSWORD@postgres-service:5432/murphy"
  redis-url: "redis://redis-service:6379/0"
  api-key: "YOUR_API_KEY"
EOF

# Apply secrets
kubectl apply -f secrets.yaml

# Verify secrets
kubectl get secrets -n murphy-system
```

### 3. Deploy Application

```bash
cd murphy_implementation/deployment/kubernetes

# Apply namespace and config
kubectl apply -f namespace.yaml

# Deploy application
kubectl apply -f deployment.yaml

# Verify deployment
kubectl get deployments -n murphy-system
kubectl get pods -n murphy-system
```

### 4. Expose Service

```bash
# Get service details
kubectl get svc -n murphy-system

# Get external IP (for LoadBalancer)
kubectl get svc murphy-api-service -n murphy-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Port forward for testing (alternative)
kubectl port-forward -n murphy-system svc/murphy-api-service 8000:80
```

### 5. Configure Ingress (Optional)

```bash
# Create ingress
cat > ingress.yaml << EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: murphy-ingress
  namespace: murphy-system
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.murphy-system.com
    secretName: murphy-tls
  rules:
  - host: api.murphy-system.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: murphy-api-service
            port:
              number: 80
EOF

kubectl apply -f ingress.yaml
```

### 6. Monitor Deployment

```bash
# Watch rollout
kubectl rollout status deployment/murphy-api -n murphy-system

# Check logs
kubectl logs -n murphy-system -l app=murphy-api --tail=100 -f

# Check events
kubectl get events -n murphy-system --sort-by='.lastTimestamp'
```

---

## Cloud Deployment

### AWS Deployment

#### 1. Setup EKS Cluster

```bash
# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Create cluster
eksctl create cluster \
  --name murphy-production \
  --region us-west-2 \
  --nodegroup-name standard-workers \
  --node-type t3.xlarge \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10 \
  --managed
```

#### 2. Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig --name murphy-production --region us-west-2

# Verify connection
kubectl get nodes
```

#### 3. Setup RDS Database

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier murphy-production \
  --db-instance-class db.t3.large \
  --engine postgres \
  --master-username murphy \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 100 \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name murphy-subnet-group
```

#### 4. Setup ElastiCache Redis

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id murphy-production \
  --cache-node-type cache.t3.medium \
  --engine redis \
  --num-cache-nodes 1 \
  --security-group-ids sg-xxxxx
```

#### 5. Deploy to EKS

```bash
# Follow Kubernetes deployment steps above
# Update secrets with RDS and ElastiCache endpoints
```

### GCP Deployment

#### 1. Setup GKE Cluster

```bash
# Create cluster
gcloud container clusters create murphy-production \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 10
```

#### 2. Configure kubectl

```bash
# Get credentials
gcloud container clusters get-credentials murphy-production --zone us-central1-a

# Verify connection
kubectl get nodes
```

#### 3. Setup Cloud SQL

```bash
# Create PostgreSQL instance
gcloud sql instances create murphy-production \
  --database-version=POSTGRES_15 \
  --tier=db-n1-standard-4 \
  --region=us-central1
```

#### 4. Setup Memorystore Redis

```bash
# Create Redis instance
gcloud redis instances create murphy-production \
  --size=5 \
  --region=us-central1 \
  --redis-version=redis_6_x
```

#### 5. Deploy to GKE

```bash
# Follow Kubernetes deployment steps above
# Update secrets with Cloud SQL and Memorystore endpoints
```

### Azure Deployment

#### 1. Setup AKS Cluster

```bash
# Create resource group
az group create --name murphy-production --location eastus

# Create AKS cluster
az aks create \
  --resource-group murphy-production \
  --name murphy-production \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-cluster-autoscaler \
  --min-count 3 \
  --max-count 10 \
  --generate-ssh-keys
```

#### 2. Configure kubectl

```bash
# Get credentials
az aks get-credentials --resource-group murphy-production --name murphy-production

# Verify connection
kubectl get nodes
```

#### 3. Setup Azure Database for PostgreSQL

```bash
# Create PostgreSQL server
az postgres server create \
  --resource-group murphy-production \
  --name murphy-production \
  --location eastus \
  --admin-user murphy \
  --admin-password YOUR_PASSWORD \
  --sku-name GP_Gen5_4
```

#### 4. Setup Azure Cache for Redis

```bash
# Create Redis cache
az redis create \
  --resource-group murphy-production \
  --name murphy-production \
  --location eastus \
  --sku Standard \
  --vm-size c1
```

#### 5. Deploy to AKS

```bash
# Follow Kubernetes deployment steps above
# Update secrets with Azure Database and Cache endpoints
```

---

## Post-Deployment

### 1. Verify Deployment

```bash
# Health check
curl https://api.murphy-system.com/health

# API status
curl -H "X-API-Key: your-api-key" https://api.murphy-system.com/api/status

# Metrics
curl https://api.murphy-system.com/metrics
```

### 2. Setup Monitoring

```bash
# Access Grafana
kubectl port-forward -n murphy-system svc/grafana 3000:3000

# Login to Grafana (admin/admin)
# Import Murphy dashboard from grafana/dashboards/

# Access Prometheus
kubectl port-forward -n murphy-system svc/prometheus 9090:9090
```

### 3. Configure Alerts

```bash
# Verify alert rules
kubectl get prometheusrules -n murphy-system

# Test alerts
# Trigger a test alert to verify notification channels
```

### 4. Setup Backups

```bash
# Database backups
# Configure automated backups for PostgreSQL

# Volume backups
# Setup persistent volume snapshots

# Configuration backups
# Backup Kubernetes configurations
kubectl get all -n murphy-system -o yaml > murphy-backup.yaml
```

### 5. Load Testing

```bash
# Install k6
brew install k6  # macOS
# or download from https://k6.io/

# Run load test
k6 run load-test.js

# Monitor during load test
watch kubectl top pods -n murphy-system
```

### 6. Documentation

- Document deployment configuration
- Record credentials securely
- Create runbook for operations team
- Setup on-call rotation

---

## Rollback Procedures

### Quick Rollback

```bash
# Kubernetes rollback
kubectl rollout undo deployment/murphy-api -n murphy-system

# Verify rollback
kubectl rollout status deployment/murphy-api -n murphy-system
```

### Rollback to Specific Version

```bash
# View deployment history
kubectl rollout history deployment/murphy-api -n murphy-system

# Rollback to specific revision
kubectl rollout undo deployment/murphy-api -n murphy-system --to-revision=2
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n murphy-system

# Describe pod
kubectl describe pod murphy-api-xxx -n murphy-system

# Check logs
kubectl logs murphy-api-xxx -n murphy-system
```

### Database Connection Issues

```bash
# Test database connection
kubectl exec -n murphy-system murphy-api-xxx -- python -c "
import psycopg2
conn = psycopg2.connect('postgresql://murphy:password@postgres:5432/murphy')
print('Connection successful')
"
```

### High Memory Usage

```bash
# Check resource usage
kubectl top pods -n murphy-system

# Increase memory limits
kubectl set resources deployment murphy-api -n murphy-system --limits=memory=4Gi
```

---

## Security Checklist

- [ ] Secrets stored securely (not in code)
- [ ] TLS/SSL certificates configured
- [ ] Network policies applied
- [ ] RBAC configured
- [ ] API keys rotated regularly
- [ ] Database encrypted at rest
- [ ] Backups encrypted
- [ ] Audit logging enabled
- [ ] Security scanning automated
- [ ] Vulnerability patching scheduled

---

## Support

For deployment assistance:
- **Email:** devops@murphy-system.com
- **Slack:** #murphy-deployment
- **Documentation:** https://docs.murphy-system.com/deployment
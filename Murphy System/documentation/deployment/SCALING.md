# Scaling Guide

Scaling the Murphy System for enterprise workloads — horizontal scaling, load balancing, resource sizing, and performance tuning.

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Table of Contents

1. [Scaling Philosophy](#1-scaling-philosophy)
2. [Resource Requirements](#2-resource-requirements)
3. [Horizontal Scaling with Multiple Workers](#3-horizontal-scaling-with-multiple-workers)
4. [Load Balancer Configuration](#4-load-balancer-configuration)
5. [Docker Scaling](#5-docker-scaling)
6. [Kubernetes Scaling](#6-kubernetes-scaling)
7. [Database Scaling](#7-database-scaling)
8. [Cache Layer Scaling](#8-cache-layer-scaling)
9. [Rate Limit Tuning](#9-rate-limit-tuning)
10. [Performance Bottlenecks and Profiling](#10-performance-bottlenecks-and-profiling)

---

## 1. Scaling Philosophy

Murphy System follows a **stateless API tier + stateful data tier** model:

- The FastAPI runtime (`murphy_system_1.0_runtime.py`) is **stateless** — any instance can serve any request.
- State lives in **PostgreSQL** (persistent) and **Redis** (ephemeral cache / rate-limit counters).
- Scale the API tier horizontally (add workers/replicas). Scale the data tier vertically first, then with read replicas.

---

## 2. Resource Requirements

### Per-instance minimums

| Deployment target | vCPU | RAM | Disk | Notes |
|-------------------|------|-----|------|-------|
| Development | 2 | 4 GB | 10 GB | Single worker, SQLite |
| Staging | 4 | 8 GB | 20 GB | 2–4 workers, PostgreSQL |
| Production (small) | 8 | 16 GB | 50 GB | 4–8 workers, PG + Redis |
| Production (large) | 16 | 32 GB | 100 GB | 8–16 workers, PG HA + Redis cluster |
| Enterprise | 32+ | 64 GB+ | 200 GB+ | Distributed, k8s, auto-scale |

### Module registry memory

Murphy loads 620+ modules at start-up. Plan for **~150–300 MB** of base RSS before serving any request. Each concurrent LLM request adds ~50–200 MB depending on model context size.

### LLM proxy overhead

When `use_llm=true` tasks are routed to an external provider (DeepInfra, OpenAI, Anthropic), the bottleneck is the **external API latency**, not Murphy's CPU. A single Murphy worker can pipeline many concurrent LLM calls via asyncio. Start with 2 workers and monitor queue depth (`/api/orchestrator/status`).

---

## 3. Horizontal Scaling with Multiple Workers

Murphy is served by **Uvicorn** (development) or **Gunicorn + Uvicorn workers** (production).

### Uvicorn multi-process (simple)

```bash
uvicorn src.runtime.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
```

Rule of thumb: **`workers = 2 × CPU_cores + 1`**

### Gunicorn + Uvicorn workers (recommended for production)

```bash
gunicorn src.runtime.app:create_app \
  --worker-class uvicorn.workers.UvicornWorker \
  --factory \
  --workers 8 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  --keepalive 5 \
  --access-logfile /app/logs/access.log \
  --error-logfile  /app/logs/error.log
```

### Environment variables that affect worker behaviour

```bash
# Number of Uvicorn event-loop workers (overrides CLI --workers when set)
MURPHY_WORKERS=8

# Async task queue concurrency per worker
MURPHY_TASK_CONCURRENCY=20

# LLM request timeout (seconds)
MURPHY_LLM_TIMEOUT=30
```

---

## 4. Load Balancer Configuration

### Nginx (reverse proxy)

Install Nginx and create `/etc/nginx/sites-available/murphy`:

```nginx
upstream murphy_backend {
    least_conn;                         # send to least-busy worker
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
    server 127.0.0.1:8004;

    keepalive 64;                       # persistent upstream connections
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;

    location /api/health {
        proxy_pass http://murphy_backend;
        access_log off;
    }

    location / {
        proxy_pass http://murphy_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Connection "";   # enable keepalive to upstream

        proxy_connect_timeout 10s;
        proxy_send_timeout    120s;
        proxy_read_timeout    120s;

        # Rate limiting at the edge
        limit_req zone=murphy_api burst=50 nodelay;
    }
}

# Rate limit zone (define in http block)
# limit_req_zone $binary_remote_addr zone=murphy_api:10m rate=100r/m;
```

### HAProxy (alternative)

```haproxy
frontend murphy_front
    bind *:443 ssl crt /etc/ssl/murphy.pem
    default_backend murphy_back
    option forwardfor
    http-request set-header X-Forwarded-Proto https

backend murphy_back
    balance leastconn
    option httpchk GET /api/health
    http-check expect string "ok"
    server w1 127.0.0.1:8001 check inter 10s rise 2 fall 3
    server w2 127.0.0.1:8002 check inter 10s rise 2 fall 3
    server w3 127.0.0.1:8003 check inter 10s rise 2 fall 3
    server w4 127.0.0.1:8004 check inter 10s rise 2 fall 3
```

---

## 5. Docker Scaling

### Scale with Docker Compose

The `docker-compose.yml` in the project root defines the full stack. To run multiple API replicas:

```bash
# Scale murphy-api to 4 replicas
docker compose up -d --scale murphy-api=4
```

Add a load-balancer service (Nginx or Traefik) in `docker-compose.yml` to front the replicas:

```yaml
services:
  traefik:
    image: traefik:v3.0
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  murphy-api:
    build: .
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.murphy.rule=Host(`api.yourdomain.com`)"
      - "traefik.http.services.murphy.loadbalancer.server.port=8000"
    deploy:
      replicas: 4
    # ... rest of service definition
```

### Production compose override

Create `docker-compose.prod.yml`:

```yaml
services:
  murphy-api:
    restart: always
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: "4"
          memory: 8G
        reservations:
          cpus: "2"
          memory: 4G
    environment:
      MURPHY_ENV: production
      MURPHY_WORKERS: "4"
```

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 6. Kubernetes Scaling

### Deployment manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: murphy-api
  namespace: murphy
spec:
  replicas: 4
  selector:
    matchLabels:
      app: murphy-api
  template:
    metadata:
      labels:
        app: murphy-api
    spec:
      containers:
        - name: murphy-api
          image: murphy-system:1.0.0
          ports:
            - containerPort: 8000
          env:
            - name: MURPHY_ENV
              value: production
            - name: MURPHY_WORKERS
              value: "4"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: murphy-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: murphy-secrets
                  key: redis-url
          resources:
            requests:
              cpu: "2"
              memory: 4Gi
            limits:
              cpu: "4"
              memory: 8Gi
          livenessProbe:
            httpGet:
              path: /api/health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /api/health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: murphy-api-hpa
  namespace: murphy
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: murphy-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
```

### Service and Ingress

```yaml
apiVersion: v1
kind: Service
metadata:
  name: murphy-api
  namespace: murphy
spec:
  selector:
    app: murphy-api
  ports:
    - port: 80
      targetPort: 8000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: murphy-api
  namespace: murphy
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  rules:
    - host: api.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: murphy-api
                port:
                  number: 80
```

---

## 7. Database Scaling

### PostgreSQL

- **Development / staging:** single PostgreSQL 16 instance (docker-compose default).
- **Production:** PostgreSQL with a read replica. Point read-heavy reporting queries at the replica using two `DATABASE_URL` values.
- **High-availability:** Use a managed service (AWS RDS Multi-AZ, Google Cloud SQL HA, or Patroni self-hosted).

Connection pooling with PgBouncer (recommended for >50 concurrent workers):

```bash
# PgBouncer pool_mode=transaction reduces connection overhead
DATABASE_URL=postgresql://murphy:password@pgbouncer:5432/murphy
```

### SQLite (development only)

SQLite is the default when `DATABASE_URL` is unset. It is **not suitable for multi-worker deployments** — each Gunicorn/Uvicorn worker would open its own file handle and writes would serialize. Switch to PostgreSQL before running more than 1 worker.

---

## 8. Cache Layer Scaling

Redis is used for rate-limit counters, session cache, and LLM response caching.

- **Development:** single Redis 7 instance (docker-compose default).
- **Production:** Redis Sentinel (automatic failover) or Redis Cluster (sharding).
- **Managed options:** AWS ElastiCache, Google Memorystore, Upstash.

```bash
# Sentinel example
REDIS_URL=redis+sentinel://sentinel1:26379,sentinel2:26379/mymaster/0

# Redis Cluster example
REDIS_URL=redis://cluster-node1:6379?cluster=true
```

---

## 9. Rate Limit Tuning

Rate limits are set per environment variable and apply per IP for anonymous requests and per API key for authenticated ones.

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_RATE_LIMIT` | `1000` | Authenticated requests/minute |
| `MURPHY_ANON_RATE_LIMIT` | `100` | Anonymous requests/minute |
| `MURPHY_EXECUTE_RATE_LIMIT` | `60` | Requests/minute on `/api/execute` |
| `MURPHY_LLM_RATE_LIMIT` | `10` | Requests/minute on LLM configure |

Increase limits for high-throughput deployments:

```bash
# .env (production)
MURPHY_RATE_LIMIT=5000
MURPHY_EXECUTE_RATE_LIMIT=300
```

Rate limit headers are returned on every response:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 997
X-RateLimit-Reset: 1709790060
```

When Redis is configured, rate limit state is **shared across all workers**. Without Redis, each worker maintains its own counter — limits are effectively `limit × workers` from the client's perspective.

---

## 10. Performance Bottlenecks and Profiling

### Known bottlenecks

| Bottleneck | Symptom | Mitigation |
|------------|---------|------------|
| External LLM API latency | High `execution_time_ms`, queue depth rising | Use DeepInfra (fastest); add key rotation pool via `DEEPINFRA_API_KEYS` |
| Module load time | Slow first request per worker | Pre-warm workers with `/api/health` before adding to LB |
| SQLite contention | 500 errors under load | Migrate to PostgreSQL |
| Redis memory | OOM in Redis | Set `maxmemory` + `maxmemory-policy allkeys-lru` |
| Single event loop | CPU-bound tasks blocking async loop | Offload CPU tasks to `asyncio.run_in_executor` |

### Prometheus metrics

When `PROMETHEUS_PORT=9090` is set, Murphy exposes metrics at `/metrics`. Key metrics:

```
murphy_requests_total{endpoint, status}   # request counter
murphy_request_latency_seconds{endpoint}  # histogram
murphy_task_queue_depth                   # current orchestrator queue
murphy_llm_calls_total{provider, status}  # LLM call counter
murphy_confidence_score{domain}           # confidence distribution
```

Scrape configuration for `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: murphy
    static_configs:
      - targets: ["murphy-api:8000"]
    metrics_path: /metrics
    scrape_interval: 15s
```

### Quick load test

```bash
pip install locust

# locustfile.py
from locust import HttpUser, task, between

class MurphyUser(HttpUser):
    wait_time = between(1, 3)
    headers = {"Authorization": "Bearer murphy_key_abc123"}

    @task(3)
    def health(self):
        self.client.get("/api/health")

    @task(1)
    def execute(self):
        self.client.post(
            "/api/execute",
            json={"task": "Summarize sales data"},
            headers=self.headers,
        )

# Run
locust --host http://localhost:8000 -u 50 -r 5 --headless -t 60s
```

---

## See Also

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Configuration](CONFIGURATION.md)
- [Maintenance](MAINTENANCE.md)

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

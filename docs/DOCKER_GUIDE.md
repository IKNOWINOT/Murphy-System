# Murphy System — Docker Deployment Guide

> **Created:** 2026-03-27  
> **Addresses:** G-001 (Docker Compose documentation)

---

## Docker Compose Files

Murphy System includes three Docker Compose configurations:

| File | Purpose | Environment |
|------|---------|-------------|
| `docker-compose.yml` | Local development | Development |
| `docker-compose.murphy.yml` | Murphy-specific config | Staging |
| `docker-compose.hetzner.yml` | Production on Hetzner | Production |

---

## Quick Start (Development)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your API keys
nano .env

# 3. Start all services
docker compose up -d

# 4. Check health
curl http://localhost:8000/api/health
```

---

## Configuration Files Detail

### `docker-compose.yml` (Development)

**Services:**
- `murphy-api` — Main FastAPI application (port 8000)
- `postgres` — PostgreSQL database (port 5432)
- `redis` — Redis cache/session store (port 6379)
- `prometheus` — Metrics collection (port 9090)
- `grafana` — Dashboards (port 3000)

**Usage:**
```bash
docker compose up -d
docker compose logs -f murphy-api
docker compose down
```

### `docker-compose.murphy.yml` (Staging)

**Additional features:**
- Murphy-specific environment variables
- Integration with murphy.systems domain
- Matrix homeserver integration

**Usage:**
```bash
docker compose -f docker-compose.murphy.yml up -d
```

### `docker-compose.hetzner.yml` (Production)

**Features:**
- Optimized for Hetzner Cloud deployment
- TLS termination via Traefik
- Automatic certificate renewal
- Health checks with restart policies
- Resource limits configured

**Usage:**
```bash
# On Hetzner server
docker compose -f docker-compose.hetzner.yml up -d
```

---

## Required Environment Variables

### Mandatory (will fail without these)

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Database password |
| `DEEPINFRA_API_KEY` | Primary LLM provider |
| `TOGETHER_API_KEY` | Secondary LLM provider |

### Recommended

| Variable | Description | Default |
|----------|-------------|---------|
| `MURPHY_ENV` | Environment mode | `development` |
| `MURPHY_PORT` | API port | `8000` |
| `MURPHY_DB_MODE` | Database mode | `stub` |
| `REDIS_PASSWORD` | Redis auth | (none) |
| `GRAFANA_ADMIN_PASSWORD` | Grafana login | `admin` |

---

## Health Checks

All containers include health checks:

```bash
# Check Murphy API
curl http://localhost:8000/api/health

# Check all container health
docker compose ps

# View health check logs
docker inspect murphy-api | jq '.[0].State.Health'
```

---

## Production Security Checklist

- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Set strong `REDIS_PASSWORD`
- [ ] Set strong `GRAFANA_ADMIN_PASSWORD`
- [ ] Do NOT expose ports 5432, 6379, 9090 publicly
- [ ] Use reverse proxy (nginx/Traefik) with TLS
- [ ] Enable rate limiting in reverse proxy
- [ ] Set `MURPHY_ENV=production`
- [ ] Set `MURPHY_DB_MODE=live`
- [ ] Set `E2EE_STUB_ALLOWED=false`

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs murphy-api

# Check environment
docker compose config

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Database connection failed

```bash
# Check postgres is running
docker compose ps postgres

# Check postgres logs
docker compose logs postgres

# Test connection
docker compose exec postgres psql -U murphy -d murphy_db
```

### Health check failing

```bash
# Check container status
docker inspect murphy-api | jq '.[0].State.Health'

# Check API logs
docker compose logs murphy-api --tail 100

# Test manually
docker compose exec murphy-api curl localhost:8000/api/health
```

# Murphy System — Kubernetes Deployment Guide

**Copyright © 2020 Inoni Limited Liability Company — BSL-1.1**

## Overview

The `k8s/` directory contains production-ready Kubernetes manifests for deploying
Murphy System on any Kubernetes cluster (≥ v1.26).

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Namespace: murphy-system                           │
│                                                     │
│  ┌──────────────┐   ┌──────────┐   ┌────────────┐  │
│  │ murphy-api   │──▶│ postgres │   │ redis      │  │
│  │ (2 replicas) │   │ (1 rep)  │   │ (1 rep)    │  │
│  └──────┬───────┘   └──────────┘   └────────────┘  │
│         │                                           │
│  ┌──────┴───────┐   ┌────────────┐                  │
│  │ prometheus   │──▶│ grafana    │                  │
│  │ (monitoring) │   │ (dashbrd)  │                  │
│  └──────────────┘   └────────────┘                  │
│                                                     │
│  NetworkPolicy: api ↔ postgres, api ↔ redis only    │
│  Ingress: TLS via cert-manager + nginx              │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Kubernetes cluster** ≥ v1.26
2. **kubectl** configured with cluster access
3. **cert-manager** installed (for TLS — optional for dev)
4. **nginx-ingress-controller** (or adapt `ingress.yaml` for your controller)
5. **Container image** pushed to `ghcr.io/iknowinot/murphy-system/murphy-system:v1.0.0`

## Quick Start — Production

```bash
# 1. Edit secrets (REQUIRED — all placeholders must be replaced)
#    Encode values: echo -n "your-value" | base64
vi k8s/secret.yaml

# 2. Update ingress hostname
sed -i 's/murphy.example.com/your-domain.com/g' k8s/ingress.yaml

# 3. Apply via Kustomize
kubectl apply -k k8s/
```

## Quick Start — Staging

```bash
# Staging uses reduced resources (1 replica, lower limits)
kubectl apply -k k8s/staging/
```

## Manifest Reference

| File | Purpose |
|------|---------|
| `namespace.yaml` | Creates `murphy-system` namespace |
| `configmap.yaml` | Non-sensitive configuration (env, ports, paths) |
| `secret.yaml` | Sensitive credentials (DB, Redis, API keys, JWT) |
| `deployment.yaml` | Murphy API deployment (2 replicas, rolling update) |
| `service.yaml` | ClusterIP service for internal routing |
| `ingress.yaml` | External access with TLS + security headers |
| `hpa.yaml` | Horizontal Pod Autoscaler (2–10 replicas, CPU/memory) |
| `pdb.yaml` | PodDisruptionBudget (minAvailable: 1) |
| `pvc.yaml` | Persistent storage for Murphy data (10Gi) |
| `postgres.yaml` | PostgreSQL 16 deployment + service + PVC |
| `redis.yaml` | Redis 7.2 deployment + service + PVC + config |
| `network-policy.yaml` | Network isolation (api, redis, postgres, backup) |
| `resource-quota.yaml` | Namespace resource limits |
| `limit-range.yaml` | Default container resource constraints |
| `backup-cronjob.yaml` | Daily backup CronJob (2:00 AM UTC) |
| `kustomization.yaml` | Kustomize base configuration |

### Monitoring (`monitoring/`)

| File | Purpose |
|------|---------|
| `prometheus-config.yaml` | Prometheus scrape config + alert rules |
| `prometheus-deployment.yaml` | Prometheus deployment + RBAC + service |
| `grafana-deployment.yaml` | Grafana deployment with provisioned datasources |
| `service-monitor.yaml` | Optional ServiceMonitor for Prometheus Operator |

### Staging (`staging/`)

| File | Purpose |
|------|---------|
| `kustomization.yaml` | Overlay patches: 1 replica, lower resources, DEBUG logging |
| `namespace.yaml` | Creates `murphy-staging` namespace |

## Security Hardening

The manifests include comprehensive security measures:

- **Pod Security**: `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, all capabilities dropped
- **Network Policies**: Strict ingress/egress rules — postgres and redis only accept connections from the API pod
- **Secrets**: All credentials stored in Kubernetes Secrets (base64-encoded placeholders — replace before deploying)
- **Resource Limits**: LimitRange + ResourceQuota prevent runaway resource consumption
- **TLS**: Ingress configured for cert-manager automatic certificate provisioning
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy

## Health Probes

| Service | Liveness | Readiness |
|---------|----------|-----------|
| murphy-api | `GET /api/health` | `GET /api/health` |
| postgres | `pg_isready -U murphy -d murphy_db` | same |
| redis | `redis-cli -a $REDIS_PASSWORD ping` | same |
| prometheus | `GET /-/healthy` | `GET /-/ready` |
| grafana | `GET /api/health` | same |

The Murphy API health endpoint supports a deep check: `GET /api/health?deep=true`
returns 503 if any critical subsystem (database, Redis, filesystem) is unhealthy.

## Secrets Management

**⚠️ CRITICAL**: The `secret.yaml` file contains base64-encoded placeholder values.
ALL values must be replaced before deploying to any environment.

For production deployments, consider:
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [HashiCorp Vault](https://www.vaultproject.io/)

Generate secure values:
```bash
# Database password
openssl rand -hex 16

# JWT secret
openssl rand -hex 32

# Encryption key
openssl rand -hex 32

# Encode for secret.yaml
echo -n "your-generated-value" | base64
```

## Backup & Recovery

The `backup-cronjob.yaml` runs daily at 2:00 AM UTC:
- Backs up Murphy data directory and state
- Stores backups on a dedicated 20Gi PVC (`murphy-backup-storage`)
- Retains 7 successful job histories
- 30-minute timeout per backup run
- Automatic cleanup of expired backups

## Monitoring

Prometheus scrapes the Murphy API at `/metrics` (port 8000) every 15 seconds.
Built-in alert rules:
- **MurphyAPIDown**: API unreachable for > 1 minute (critical)
- **MurphyHighErrorRate**: > 5% 5xx errors over 5 minutes (warning)
- **MurphyHighLatency**: p95 latency > 2 seconds (warning)
- **MurphyPodRestarting**: > 3 restarts in 1 hour (warning)
- **MurphyHighMemoryUsage**: > 80% memory limit (warning)
- **MurphyHighCPUUsage**: > 80% CPU limit (warning)
- **MurphyLLMCallFailures**: > 10% LLM call failures (warning)
- **MurphyTaskQueueBacklog**: Queue depth > 100 for 10 minutes (warning)

## Scaling

The HPA automatically scales murphy-api between 2 and 10 replicas based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)

Manual scaling:
```bash
kubectl scale deployment murphy-api -n murphy-system --replicas=5
```
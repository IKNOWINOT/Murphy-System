# Configuration Guide

How to configure the Murphy System for development, staging, and production deployments.

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Table of Contents

1. [Configuration Overview](#1-configuration-overview)
2. [Core Environment Variables](#2-core-environment-variables)
3. [LLM Provider Configuration](#3-llm-provider-configuration)
4. [Database Configuration](#4-database-configuration)
5. [Cache Configuration](#5-cache-configuration)
6. [Security Configuration](#6-security-configuration)
7. [Rate Limiting Configuration](#7-rate-limiting-configuration)
8. [Integration Configuration](#8-integration-configuration)
9. [Monitoring and Logging Configuration](#9-monitoring-and-logging-configuration)
10. [Per-environment Profiles](#10-per-environment-profiles)

---

## 1. Configuration Overview

All runtime configuration is supplied through **environment variables**. The canonical reference is `.env.example` in the `Murphy System/` directory.

**Setup:**
```bash
cd "Murphy System"
cp .env.example .env
# Edit .env with your values
```

The `setup_and_start.sh` (Linux/macOS) and `setup_and_start.bat` (Windows) scripts will create the virtual environment, install dependencies from `requirements_murphy_1.0.txt`, and source `.env` automatically.

> **Security:** Never commit `.env` to version control. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, GitHub Actions secrets) for production values.

---

## 2. Core Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MURPHY_VERSION` | No | `1.0.0` | Runtime version tag (informational) |
| `MURPHY_ENV` | ❌ | `production` | Deployment environment: `development`, `staging`, `production` |
| `MURPHY_PORT` | No | `8000` | TCP port the API server listens on |
| `MURPHY_WORKERS` | No | auto | Number of Uvicorn/Gunicorn worker processes |
| `MURPHY_TASK_CONCURRENCY` | No | `20` | Max concurrent async tasks per worker |
| `DEBUG` | No | `false` | Enables verbose debug logging |
| `AUTO_RELOAD` | No | `true` | Hot-reload on source changes (development only) |
| `ENABLE_CORS` | No | `true` | Enable CORS middleware |
| `MURPHY_CORS_ORIGINS` | No | localhost origins | Comma-separated list of allowed CORS origins |

### MURPHY_ENV behaviour

| Value | Auth enforced | CORS | Log level | Notes |
|-------|--------------|------|-----------|-------|
| `development` | Optional | Permissive (localhost) | DEBUG | All endpoints accessible without API key |
| `staging` | Required | Restricted | INFO | Full auth; mirrors production |
| `production` | Required | Strict allowlist | WARNING | All security controls active |

> **Important:** `MURPHY_ENV=development` disables API key enforcement. Never use this setting on an internet-facing server.

---

## 3. LLM Provider Configuration

At least one LLM API key is required for tasks that use `use_llm: true`.

### Provider selection

```bash
# Auto-detect from whichever key is present, or explicitly set:
MURPHY_LLM_PROVIDER=groq          # groq | openai | anthropic | local
```

### Groq (recommended — free tier available)

```bash
GROQ_API_KEY=gsk_your_key_here

# Optional: key pool for load balancing / rate-limit rotation
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
```

Get a free key at <https://console.groq.com/keys>. Groq is the recommended provider for getting started — it offers the lowest latency and a generous free tier.

Default model: `llama3-70b-8192`

### OpenAI

```bash
OPENAI_API_KEY=sk-your_key_here
```

Default model: `gpt-4o`

### Anthropic

```bash
ANTHROPIC_API_KEY=sk-ant-your_key_here
```

Default model: `claude-3-5-sonnet-20241022`

### Local / offline mode

Set `MURPHY_LLM_PROVIDER=local` to disable all external LLM calls. Tasks will use the deterministic Aristotle engine and Wulfrum fuzzy-match engine only.

### Aristotle and Wulfrum (optional external engines)

```bash
ARISTOTLE_API_KEY=your_aristotle_key
ARISTOTLE_API_URL=https://api.aristotle.example.com/v1/analyze

WULFRUM_API_KEY=your_wulfrum_key
WULFRUM_API_URL=https://api.wulfrum.example.com/v1/validate
```

### Hot-reload LLM configuration

You can change the LLM provider at runtime without restarting the server:

```bash
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-new-key"}'
```

---

## 4. Database Configuration

### SQLite (default — zero configuration)

When `DATABASE_URL` is not set, Murphy automatically creates `murphy_system.db` in the working directory. Suitable for development and single-process deployments only.

```bash
# Explicit SQLite path (optional)
DATABASE_URL=sqlite:///./murphy_system.db
```

### PostgreSQL (recommended for production)

```bash
DATABASE_URL=postgresql://username:password@localhost:5432/murphy
```

Docker Compose sets this automatically when both services are running:

```bash
DATABASE_URL=postgresql://murphy:murphy@postgres:5432/murphy
```

Create the database:

```bash
psql -U postgres -c "CREATE DATABASE murphy;"
psql -U postgres -c "CREATE USER murphy WITH PASSWORD 'murphy';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE murphy TO murphy;"
```

### MySQL

```bash
DATABASE_URL=mysql://username:password@localhost:3306/murphy
```

---

## 5. Cache Configuration

### In-memory (default — zero configuration)

When `REDIS_URL` is not set, Murphy uses a process-local in-memory cache. Rate-limit counters are not shared between workers.

### Redis (recommended for multi-worker and production)

```bash
REDIS_URL=redis://localhost:6379/0

# With password
REDIS_URL=redis://:your_password@localhost:6379/0

# Redis Sentinel
REDIS_URL=redis+sentinel://sentinel1:26379,sentinel2:26379/mymaster/0
```

Docker Compose sets this automatically:

```bash
REDIS_URL=redis://redis:6379/0
```

---

## 6. Security Configuration

### API key authentication

```bash
# Comma-separated list of valid API keys
MURPHY_API_KEYS=murphy_key_abc123,murphy_key_def456

# Generate a secure key
python -c "import secrets; print('murphy_' + secrets.token_hex(24))"
```

Keys are accepted as `Authorization: Bearer <key>` or `X-API-Key: <key>`. In production, rotate keys regularly and use a secrets manager.

### JWT secret

Used internally for session tokens. Generate a strong random value:

```bash
JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### Encryption key

Used for encrypting sensitive data at rest:

```bash
ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

> Store `JWT_SECRET` and `ENCRYPTION_KEY` in a secrets manager — not in `.env` files checked into version control.

### CORS configuration

```bash
# Development (defaults to localhost origins)
MURPHY_CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Production — list only your actual frontend origins
MURPHY_CORS_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
```

Never use `*` as a CORS origin in production — it disables the same-origin protection provided by browsers.

### HTTPS / TLS

Murphy itself serves HTTP. TLS termination should be handled by the reverse proxy (Nginx, HAProxy, or a cloud load balancer). See the [Deployment Guide](DEPLOYMENT_GUIDE.md) for Nginx TLS configuration.

---

## 7. Rate Limiting Configuration

```bash
# Authenticated requests per minute
MURPHY_RATE_LIMIT=1000

# Anonymous requests per minute (no API key)
MURPHY_ANON_RATE_LIMIT=100

# /api/execute requests per minute per user
MURPHY_EXECUTE_RATE_LIMIT=60

# /api/llm/configure requests per minute per user
MURPHY_LLM_RATE_LIMIT=10
```

Rate limit state is shared across workers when Redis is configured. Without Redis, limits apply per worker process.

Response headers on every API call:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 997
X-RateLimit-Reset: 1709790060
```

---

## 8. Integration Configuration

The following integrations are optional. Leave them unset if not needed.

### GitHub

```bash
GITHUB_TOKEN=ghp_your_token_here
```

### Payment processing

```bash
# Stripe
STRIPE_API_KEY=sk_live_your_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_key

# PayPal
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_client_secret
```

### Email

```bash
# SendGrid
SENDGRID_API_KEY=SG.your_key

# AWS SES
AWS_SES_ACCESS_KEY=your_access_key
AWS_SES_SECRET_KEY=your_secret_key
AWS_SES_REGION=us-east-1

# Twilio (SMS)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
```

### CRM

```bash
# Salesforce
SALESFORCE_CLIENT_ID=your_client_id
SALESFORCE_CLIENT_SECRET=your_client_secret
SALESFORCE_USERNAME=you@company.com
SALESFORCE_PASSWORD=your_password

# HubSpot
HUBSPOT_API_KEY=your_key

# Pipedrive
PIPEDRIVE_API_TOKEN=your_token
```

### Social media

```bash
TWITTER_API_KEY=your_key
TWITTER_API_SECRET=your_secret
TWITTER_ACCESS_TOKEN=your_token
TWITTER_ACCESS_SECRET=your_secret

LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_secret
```

---

## 9. Monitoring and Logging Configuration

```bash
# Log level
LOG_LEVEL=INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL

# Debug mode (verbose output — development only)
DEBUG=false

# Sentry (error tracking)
SENTRY_DSN=https://your_dsn@sentry.io/project_id

# Prometheus metrics endpoint
PROMETHEUS_PORT=9090
```

Docker Compose includes Prometheus (port 9090) and Grafana (port 3000) by default. Grafana default credentials: `admin` / `admin`.

---

## 10. Per-environment Profiles

Use separate `.env` files per environment and pass them explicitly, or use the `MURPHY_ENV` variable to switch behaviour.

### Development `.env` (minimal)

```bash
MURPHY_ENV=development
GROQ_API_KEY=gsk_your_key
LOG_LEVEL=DEBUG
DEBUG=true
AUTO_RELOAD=true
```

### Staging `.env`

```bash
MURPHY_ENV=staging
GROQ_API_KEY=gsk_your_key
MURPHY_API_KEYS=murphy_staging_key_abc123
DATABASE_URL=postgresql://murphy:password@postgres:5432/murphy_staging
REDIS_URL=redis://redis:6379/0
JWT_SECRET=<generated>
ENCRYPTION_KEY=<generated>
MURPHY_CORS_ORIGINS=https://staging.yourdomain.com
LOG_LEVEL=INFO
DEBUG=false
```

### Production `.env`

```bash
MURPHY_ENV=production
GROQ_API_KEY=gsk_prod_key
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
MURPHY_API_KEYS=murphy_prod_key_abc,murphy_prod_key_def
DATABASE_URL=postgresql://murphy:strong_password@pg-primary:5432/murphy
REDIS_URL=redis://:redis_password@redis-primary:6379/0
JWT_SECRET=<64-char hex from secrets manager>
ENCRYPTION_KEY=<64-char hex from secrets manager>
MURPHY_CORS_ORIGINS=https://app.yourdomain.com
MURPHY_RATE_LIMIT=5000
MURPHY_EXECUTE_RATE_LIMIT=300
LOG_LEVEL=WARNING
DEBUG=false
AUTO_RELOAD=false
SENTRY_DSN=https://your_dsn@sentry.io/id
PROMETHEUS_PORT=9090
```

---

## See Also

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Scaling](SCALING.md)
- [Installation](../getting_started/INSTALLATION.md)

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

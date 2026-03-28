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
11. [MFM Configuration](#11-mfm-murphy-foundation-model-configuration)
12. [Matrix Bridge Configuration](#12-matrix-bridge-configuration)
13. [Third-party Integration Variables](#13-third-party-integration-variables)
14. [Backend Mode Controls](#14-backend-mode-controls)
15. [Docker Compose Credentials](#15-docker-compose-credentials)
16. [Response and Logging Controls](#16-response-and-logging-controls)

---

## 1. Configuration Overview

Murphy System supports two complementary configuration mechanisms. **Environment variables always take precedence** (twelve-factor app style).

### YAML Configuration Files (recommended starting point)

The `config/` directory contains YAML files that supply sensible defaults for all runtime settings:

| File | Purpose |
|------|---------|
| `config/murphy.yaml` | Main system defaults — LLM provider, confidence thresholds, safety levels, logging, tenant limits, self-learning |
| `config/engines.yaml` | Engine defaults — domain engines, swarm parameters, learning engine settings, gate parameters |
| `config/murphy.yaml.example` | Fully-annotated reference for `murphy.yaml` |
| `config/engines.yaml.example` | Fully-annotated reference for `engines.yaml` |
| `config/config_loader.py` | Loader that reads YAML files and applies env-var overrides |

Edit the YAML files to change defaults:
```bash
cd "Murphy System"
nano config/murphy.yaml    # LLM provider, thresholds, logging, tenant settings
nano config/engines.yaml   # Swarm size, gate parameters, orchestrator timeouts
```

### Environment Variables (overrides)

Environment variables (set in your shell or `.env`) **always override YAML values**:

```bash
# Legacy flat names (well-known shortcuts):
export MURPHY_LLM_PROVIDER=deepinfra
export LOG_LEVEL=DEBUG
export CONFIDENCE_THRESHOLD=0.90

# Namespaced names (MURPHY_<SECTION>__<KEY>):
export MURPHY_API__PORT=9000
export MURPHY_THRESHOLDS__CONFIDENCE=0.90
```

The `.env` file approach:
```bash
cp .env.example .env
# Edit .env with your values
```

The `setup_and_start.sh` (Linux/macOS) and `setup_and_start.bat` (Windows) scripts will create the virtual environment, install dependencies from `requirements_murphy_1.0.txt`, and source `.env` automatically.

> **Security:** Never commit `.env` to version control. Never store secrets (API keys, passwords) in YAML files. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, GitHub Actions secrets) for production values.

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
MURPHY_LLM_PROVIDER=deepinfra          # deepinfra | openai | anthropic | local
```

### DeepInfra (recommended — free tier available)

```bash
DEEPINFRA_API_KEY=gsk_your_key_here

# Optional: key pool for load balancing / rate-limit rotation
DEEPINFRA_API_KEYS=gsk_key1,gsk_key2,gsk_key3
```

Get a free key at <https://console.deepinfra.com/keys>. DeepInfra is the recommended provider for getting started — it offers the lowest latency and a generous free tier.

Default model: `meta-llama/Meta-Llama-3.1-70B-Instruct`

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
DEEPINFRA_API_KEY=gsk_your_key
LOG_LEVEL=DEBUG
DEBUG=true
AUTO_RELOAD=true
```

### Staging `.env`

```bash
MURPHY_ENV=staging
DEEPINFRA_API_KEY=gsk_your_key
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
DEEPINFRA_API_KEY=gsk_prod_key
DEEPINFRA_API_KEYS=gsk_key1,gsk_key2,gsk_key3
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

## 11. MFM (Murphy Foundation Model) Configuration

The Murphy Foundation Model subsystem is disabled by default and can be
progressively enabled as training data accumulates.

| Variable | Default | Description |
|----------|---------|-------------|
| `MFM_ENABLED` | `false` | Enable the MFM subsystem |
| `MFM_MODE` | `disabled` | `disabled` \| `collecting` \| `shadow` \| `canary` \| `production` |
| `MFM_BASE_MODEL` | `microsoft/Phi-3-mini-4k-instruct` | Base model for fine-tuning |
| `MFM_CHECKPOINT_DIR` | `./checkpoints/mfm` | Where to store model checkpoints |
| `MFM_TRACE_DIR` | `./data/action_traces` | Where to store action traces for training |
| `MFM_RETRAIN_THRESHOLD` | `10000` | Number of traces before triggering auto-retrain |
| `MFM_SHADOW_MIN_ACCURACY` | `0.80` | Minimum accuracy required before promoting from shadow |
| `MFM_CANARY_TRAFFIC_PERCENT` | `10` | Percentage of live traffic routed to the canary model |
| `MFM_DEVICE` | `auto` | Compute device: `cuda` \| `cpu` \| `auto` |

### MFM Modes

| Mode | Behaviour |
|------|-----------|
| `disabled` | MFM is completely inactive; all inference uses the configured LLM provider |
| `collecting` | Traces are collected and stored; no inference changes |
| `shadow` | MFM runs in parallel with the primary LLM; results are logged but not served |
| `canary` | `MFM_CANARY_TRAFFIC_PERCENT`% of requests are routed to MFM |
| `production` | All inference uses the fine-tuned MFM |

---

## 12. Matrix Bridge Configuration

Required to enable the Murphy ↔ Matrix homeserver integration
(see `src/matrix_bridge/`).  Install the SDK with:
`pip install 'matrix-nio[e2e]'`

| Variable | Required | Description |
|----------|----------|-------------|
| `MATRIX_HOMESERVER_URL` | Yes | URL of the Matrix homeserver (e.g. `https://matrix.example.com`) |
| `MATRIX_BOT_USER` | Yes | Matrix user ID for the Murphy bot (e.g. `@murphy:example.com`) |
| `MATRIX_BOT_TOKEN` | Yes (or password) | Access token for the bot account |
| `MATRIX_BOT_PASSWORD` | Yes (or token) | Password for the bot account |
| `MATRIX_DEVICE_ID` | No | Stable device ID for E2EE session resumption |
| `MATRIX_E2E_ENABLED` | `false` | Enable end-to-end encryption |
| `MATRIX_HOMESERVER_DOMAIN` | No | Matrix server domain (derived from URL if omitted) |
| `MATRIX_AUTO_CREATE_ROOMS` | `true` | Automatically create missing subsystem rooms |
| `MATRIX_SPACE_NAME` | `Murphy System` | Display name for the Matrix space |
| `MATRIX_ADMIN_USERS` | No | Comma-separated Matrix user IDs with admin rights |
| `MATRIX_CB_THRESHOLD` | `5` | Circuit-breaker failure threshold before opening |
| `MATRIX_CB_TIMEOUT` | `60` | Seconds the circuit breaker stays open |
| `E2EE_STUB_ALLOWED` | `true` | Allow stub E2EE ciphertext in dev/test (`false` in production) |

### Webhook Receiver

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_HOST` | `0.0.0.0` | Bind address for the webhook receiver |
| `WEBHOOK_PORT` | `8765` | Port for the webhook receiver |
| `WEBHOOK_SECRET_GITHUB` | — | HMAC secret for verifying GitHub webhooks |
| `WEBHOOK_SECRET_STRIPE` | — | HMAC secret for verifying Stripe webhooks |

---

## 13. Third-party Integration Variables

### Payment Processing

| Variable | Provider | Description |
|----------|----------|-------------|
| `PAYPAL_CLIENT_ID` | PayPal | OAuth client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal | OAuth client secret |
| `PAYPAL_WEBHOOK_SECRET` | PayPal | Webhook HMAC secret |
| `COINBASE_WEBHOOK_SECRET` | Coinbase Commerce | Webhook HMAC secret |
| `STRIPE_API_KEY` | Stripe (optional) | Secret key — **not used by default; PayPal/Coinbase are primary** |
| `STRIPE_PUBLISHABLE_KEY` | Stripe (optional) | Publishable key |

### Email and Messaging

| Variable | Provider | Description |
|----------|----------|-------------|
| `SENDGRID_API_KEY` | SendGrid | API key for transactional email |
| `AWS_SES_ACCESS_KEY` | AWS SES | IAM access key |
| `AWS_SES_SECRET_KEY` | AWS SES | IAM secret key |
| `AWS_SES_REGION` | AWS SES | Region (e.g. `us-east-1`) |
| `TWILIO_ACCOUNT_SID` | Twilio | Account SID for SMS |
| `TWILIO_AUTH_TOKEN` | Twilio | Auth token |
| `TWILIO_PHONE_NUMBER` | Twilio | Sender phone number |

### CRM

| Variable | Provider | Description |
|----------|----------|-------------|
| `SALESFORCE_CLIENT_ID` | Salesforce | Connected App client ID |
| `SALESFORCE_CLIENT_SECRET` | Salesforce | Connected App client secret |
| `SALESFORCE_USERNAME` | Salesforce | Login username |
| `SALESFORCE_PASSWORD` | Salesforce | Login password |
| `HUBSPOT_API_KEY` | HubSpot | Private app API key |
| `PIPEDRIVE_API_TOKEN` | Pipedrive | Personal API token |

### Social Media

| Variable | Provider | Description |
|----------|----------|-------------|
| `TWITTER_API_KEY` | Twitter/X | API key (consumer key) |
| `TWITTER_API_SECRET` | Twitter/X | API secret |
| `TWITTER_ACCESS_TOKEN` | Twitter/X | OAuth access token |
| `TWITTER_ACCESS_SECRET` | Twitter/X | OAuth access token secret |
| `LINKEDIN_CLIENT_ID` | LinkedIn | OAuth app client ID |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn | OAuth app client secret |
| `FACEBOOK_APP_ID` | Facebook | App ID |
| `FACEBOOK_APP_SECRET` | Facebook | App secret |
| `FACEBOOK_ACCESS_TOKEN` | Facebook | Page access token |

### Analytics and Content Management

| Variable | Provider | Description |
|----------|----------|-------------|
| `GOOGLE_ANALYTICS_ID` | Google Analytics | Measurement / UA ID |
| `GOOGLE_ANALYTICS_KEY` | Google Analytics | Service account key |
| `WORDPRESS_URL` | WordPress | Site base URL |
| `WORDPRESS_USERNAME` | WordPress | Admin username |
| `WORDPRESS_PASSWORD` | WordPress | Application password |
| `MEDIUM_ACCESS_TOKEN` | Medium | Integration token |

### Version Control

| Variable | Provider | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | GitHub | Personal Access Token — required for private repos and higher rate limits |

---

## 14. Backend Mode Controls

These variables control whether stub/simulated backends are permitted.
In `production` and `staging`, stubs are **rejected at startup** unless
the relevant variable is explicitly set.

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_DB_MODE` | `live` | `live` = real SQLAlchemy DB; `stub` = in-memory (rejected in staging/production) |
| `MURPHY_AUTO_MIGRATE` | `true` (dev) | `true` = apply Alembic migrations on startup; `false` = manual |
| `MURPHY_DB_POOL_SIZE` | `5` | SQLAlchemy connection pool size (PostgreSQL/MySQL) |
| `MURPHY_DB_MAX_OVERFLOW` | `10` | Max extra connections above pool size |
| `MURPHY_POOL_MODE` | `real` | `real` = httpx pools; `simulated` = in-memory stubs (rejected in staging/production) |
| `MURPHY_EMAIL_REQUIRED` | `true` (staging/prod) | `true` = a real email backend is required; `false` = allow fallback to mock |
| `MURPHY_ENABLED_PROTOCOLS` | `` | Comma-separated industrial protocols to enforce (e.g. `bacnet,modbus,opcua`) |
| `E2EE_STUB_ALLOWED` | `true` | Allow stub E2EE ciphertext — set `false` in production |

---

## 15. Docker Compose Credentials

These variables are **required** when starting the system with `docker compose up`.

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | PostgreSQL superuser password — **change from default** |
| `GRAFANA_ADMIN_USER` | Grafana admin username (default: `admin`) |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password — **change from default** |
| `REDIS_PASSWORD` | Redis AUTH password (optional but recommended for production) |

Generate strong passwords:
```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

---

## 16. Response and Logging Controls

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_MAX_RESPONSE_SIZE_MB` | `10` | Maximum API response size in MB; larger responses return `413` |
| `MURPHY_LOG_FORMAT` | `text` (dev) / `json` (prod) | `text` = human-readable; `json` = structured JSON lines for log aggregators |
| `AUTO_RELOAD` | `true` | Hot-reload on code changes (development only) |
| `ENABLE_CORS` | `true` | Enable CORS headers |
| `MURPHY_CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins — **never use `*` in production** |
| `DEBUG` | `false` | Enable verbose debug output |

---

## See Also

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Scaling](SCALING.md)
- [Installation](../getting_started/INSTALLATION.md)

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

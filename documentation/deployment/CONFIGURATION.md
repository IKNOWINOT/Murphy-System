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
11. [Murphy Foundation Model (MFM)](#11-murphy-foundation-model-mfm)
12. [Matrix Integration](#12-matrix-integration)
13. [Backend Modes](#13-backend-modes-beta-hardening)
14. [Complete Variable Index](#14-complete-variable-index)

---

## 1. Configuration Overview

All runtime configuration is supplied through **environment variables**. The canonical reference is `.env.example` in the repository root.

**Setup:**
```bash
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
| `MURPHY_ENV` | **Yes** (staging/prod) | `production` | Deployment environment: `development`, `staging`, `production` |
| `MURPHY_PORT` | No | `8000` | TCP port the API server listens on |
| `MURPHY_WORKERS` | No | auto | Number of Uvicorn/Gunicorn worker processes |
| `MURPHY_TASK_CONCURRENCY` | No | `20` | Max concurrent async tasks per worker |
| `MURPHY_PERSISTENCE_DIR` | No | `.murphy_persistence` | Directory for JSON state snapshots |
| `MURPHY_LLM_PROVIDER` | No | `local` | LLM provider: `local`, `deepinfra`, `together`, `openai`, `anthropic` |
| `DEBUG` | No | `false` | Enables verbose debug logging |
| `AUTO_RELOAD` | No | `true` | Hot-reload on source changes (development only) |
| `ENABLE_CORS` | No | `true` | Enable CORS middleware |
| `MURPHY_CORS_ORIGINS` | No | localhost origins | Comma-separated list of allowed CORS origins |
| `LOG_LEVEL` | No | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `MURPHY_LOG_FORMAT` | No | `text` (dev) / `json` (prod) | Log format: `text` (human-readable) or `json` (ELK/Datadog) |
| `MURPHY_MAX_RESPONSE_SIZE_MB` | No | `10` | Max response size in MB; responses above this return HTTP 413 |

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
MURPHY_LLM_PROVIDER=deepinfra      # deepinfra | together | openai | anthropic | local
```

### DeepInfra (recommended primary — ~80% of calls)

```bash
DEEPINFRA_API_KEY=di_your_key_here

# Optional: key pool for load balancing
DEEPINFRA_API_KEYS=di_key1,di_key2,di_key3
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPINFRA_API_KEY` | No | — | Primary DeepInfra API key |
| `DEEPINFRA_API_KEYS` | No | — | Comma-separated key pool for load balancing |

Get a key at <https://deepinfra.com/>. DeepInfra is the recommended primary provider — it offers the best price-to-performance ratio.

Primary models: `meta-llama/Meta-Llama-3.1-70B-Instruct` (high-quality), `mistralai/Mixtral-8x7B-Instruct-v0.1` (high-context)

### Together AI (overflow safety net — ~20% of calls)

```bash
TOGETHER_API_KEY=your_key_here
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TOGETHER_API_KEY` | No | — | Together AI API key |

Get a key at <https://api.together.xyz/>. Together AI is used as overflow when DeepInfra is rate-limited or unavailable.

Default model: `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo`

### OpenAI

```bash
OPENAI_API_KEY=sk-your_key_here
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | — | OpenAI API key |

Default model: `gpt-4o`

### Anthropic

```bash
ANTHROPIC_API_KEY=sk-ant-your_key_here
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | No | — | Anthropic Claude API key |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARISTOTLE_API_KEY` | No | — | API key for the Aristotle deterministic engine |
| `ARISTOTLE_API_URL` | No | — | Base URL for the Aristotle API |
| `WULFRUM_API_KEY` | No | — | API key for the Wulfrum fuzzy-match engine |
| `WULFRUM_API_URL` | No | — | Base URL for the Wulfrum API |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | SQLite auto | SQLAlchemy connection URL |
| `POSTGRES_PASSWORD` | Docker only | — | PostgreSQL password (used by `docker-compose.yml`) |
| `MURPHY_DB_MODE` | No | `live` | `stub` (dev/test in-memory) or `live` (real DB). `stub` rejected in staging/production. |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | — | Redis connection URL for caching and session storage |
| `MURPHY_REDIS_URL` | No | — | Redis URL for multi-worker rate-limit state sharing |
| `REDIS_PASSWORD` | Docker only | — | Redis password (used by `docker-compose.yml`) |
| `MURPHY_POOL_MODE` | No | `real` | `simulated` (dev/test stub pools) or `real` (httpx pools). `simulated` rejected in staging/production. |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MURPHY_API_KEYS` | staging/prod | — | Comma-separated list of valid API keys for request auth |
| `MURPHY_API_KEY` | No | — | Single API key alias (same as first entry in `MURPHY_API_KEYS`) |
| `MURPHY_CREDENTIAL_MASTER_KEY` | staging/prod | ephemeral | Fernet AES-128-CBC key for encrypting credentials at rest |
| `JWT_SECRET` | No | — | Secret for JWT session tokens — use a secrets manager |
| `ENCRYPTION_KEY` | No | — | 64-char hex key for encrypting sensitive data at rest |
| `E2EE_STUB_ALLOWED` | No | `false` (prod) | Allow Matrix E2EE stub ciphertext (`true`/`false`) |
| `GRAFANA_ADMIN_USER` | Docker only | `admin` | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | Docker only | — | Grafana admin password (used by `docker-compose.yml`) |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MURPHY_RATE_LIMIT` | No | `1000` | Max authenticated requests per minute |
| `MURPHY_ANON_RATE_LIMIT` | No | `100` | Max anonymous (no API key) requests per minute |
| `MURPHY_EXECUTE_RATE_LIMIT` | No | `60` | Max `/api/execute` calls per minute per user |
| `MURPHY_LLM_RATE_LIMIT` | No | `10` | Max `/api/llm/configure` calls per minute per user |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | No | — | Personal access token for private repo integration and higher rate limits |

```bash
GITHUB_TOKEN=ghp_your_token_here
```

### Payment processing

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STRIPE_API_KEY` | No | — | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | No | — | Stripe publishable (frontend) key |
| `PAYPAL_CLIENT_ID` | No | — | PayPal OAuth2 client ID |
| `PAYPAL_CLIENT_SECRET` | No | — | PayPal OAuth2 client secret |
| `PAYPAL_WEBHOOK_SECRET` | No | — | PayPal webhook signature validation secret |
| `COINBASE_WEBHOOK_SECRET` | No | — | Coinbase Commerce webhook signature secret |

```bash
# Stripe
STRIPE_API_KEY=sk_live_your_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_key

# PayPal
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_client_secret
PAYPAL_WEBHOOK_SECRET=your_paypal_webhook_secret

# Coinbase Commerce (crypto payments)
COINBASE_WEBHOOK_SECRET=your_coinbase_webhook_secret
```

### Email

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENDGRID_API_KEY` | No | — | SendGrid API key for transactional email |
| `AWS_SES_ACCESS_KEY` | No | — | AWS access key for SES email |
| `AWS_SES_SECRET_KEY` | No | — | AWS secret key for SES email |
| `AWS_SES_REGION` | No | `us-east-1` | AWS region for SES |
| `TWILIO_ACCOUNT_SID` | No | — | Twilio account SID for SMS |
| `TWILIO_AUTH_TOKEN` | No | — | Twilio auth token for SMS |
| `TWILIO_PHONE_NUMBER` | No | — | Outbound Twilio phone number (E.164 format) |
| `MURPHY_EMAIL_REQUIRED` | No | `true` (prod) | If `true`, raises `RuntimeError` at startup when no real email backend is configured |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SALESFORCE_CLIENT_ID` | No | — | Salesforce connected app client ID |
| `SALESFORCE_CLIENT_SECRET` | No | — | Salesforce connected app client secret |
| `SALESFORCE_USERNAME` | No | — | Salesforce login username |
| `SALESFORCE_PASSWORD` | No | — | Salesforce login password |
| `HUBSPOT_API_KEY` | No | — | HubSpot private app API key |
| `PIPEDRIVE_API_TOKEN` | No | — | Pipedrive personal API token |

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TWITTER_API_KEY` | No | — | Twitter/X API key |
| `TWITTER_API_SECRET` | No | — | Twitter/X API secret |
| `TWITTER_ACCESS_TOKEN` | No | — | Twitter/X access token |
| `TWITTER_ACCESS_SECRET` | No | — | Twitter/X access token secret |
| `LINKEDIN_CLIENT_ID` | No | — | LinkedIn OAuth2 client ID |
| `LINKEDIN_CLIENT_SECRET` | No | — | LinkedIn OAuth2 client secret |
| `FACEBOOK_APP_ID` | No | — | Facebook/Meta app ID |
| `FACEBOOK_APP_SECRET` | No | — | Facebook/Meta app secret |
| `FACEBOOK_ACCESS_TOKEN` | No | — | Facebook/Meta page access token |

```bash
TWITTER_API_KEY=your_key
TWITTER_API_SECRET=your_secret
TWITTER_ACCESS_TOKEN=your_token
TWITTER_ACCESS_SECRET=your_secret

LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_secret

FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_ACCESS_TOKEN=your_page_token
```

### Analytics

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_ANALYTICS_ID` | No | — | Google Analytics Tracking ID (UA-XXXXXXXX or G-XXXXXXXX) |
| `GOOGLE_ANALYTICS_KEY` | No | — | Google Analytics service account key |

### Content Management

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WORDPRESS_URL` | No | — | WordPress site URL (e.g. `https://yourblog.com`) |
| `WORDPRESS_USERNAME` | No | — | WordPress admin username |
| `WORDPRESS_PASSWORD` | No | — | WordPress application password (not login password) |
| `MEDIUM_ACCESS_TOKEN` | No | — | Medium integration token for publishing posts |

---

## 9. Monitoring and Logging Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `MURPHY_LOG_FORMAT` | No | `text` | Log format: `text` (human-readable) or `json` (ELK/Datadog/CloudWatch) |
| `DEBUG` | No | `false` | Verbose debug output (development only) |
| `SENTRY_DSN` | No | — | Sentry DSN for error tracking and alerting |
| `PROMETHEUS_PORT` | No | `9090` | Port to expose Prometheus `/metrics` endpoint |

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
DEEPINFRA_API_KEY=di_your_key
LOG_LEVEL=DEBUG
DEBUG=true
AUTO_RELOAD=true
```

### Staging `.env`

```bash
MURPHY_ENV=staging
DEEPINFRA_API_KEY=di_your_key
TOGETHER_API_KEY=your_together_key
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
DEEPINFRA_API_KEY=di_prod_key
DEEPINFRA_API_KEYS=di_key1,di_key2,di_key3
TOGETHER_API_KEY=together_overflow_key
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

## 11. Murphy Foundation Model (MFM)

The MFM subsystem fine-tunes an on-device model from production action traces. All variables default to disabled.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MFM_ENABLED` | No | `false` | Enable the MFM subsystem |
| `MFM_MODE` | No | `disabled` | Operating mode: `disabled`, `collecting`, `shadow`, `canary`, `production` |
| `MFM_BASE_MODEL` | No | `microsoft/Phi-3-mini-4k-instruct` | HuggingFace model ID used as fine-tuning base |
| `MFM_CHECKPOINT_DIR` | No | `./checkpoints/mfm` | Directory where fine-tuned checkpoints are stored |
| `MFM_TRACE_DIR` | No | `./data/action_traces` | Directory where action traces are recorded |
| `MFM_RETRAIN_THRESHOLD` | No | `10000` | Number of traces before automatic retraining is triggered |
| `MFM_SHADOW_MIN_ACCURACY` | No | `0.80` | Minimum shadow-mode accuracy required before promotion |
| `MFM_CANARY_TRAFFIC_PERCENT` | No | `10` | Percentage of traffic routed to the canary model |
| `MFM_DEVICE` | No | `auto` | Inference device: `cuda`, `cpu`, or `auto` |

### MFM mode progression

```
disabled → collecting → shadow → canary → production
```

Promote using `POST /api/mfm/promote`. Roll back with `POST /api/mfm/rollback`.

---

## 12. Matrix Integration

Required for the Murphy Matrix bridge (`src/matrix_bridge/`). Install the SDK with:
```bash
pip install 'matrix-nio[e2e]'
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MATRIX_HOMESERVER_URL` | Matrix only | — | Homeserver URL (e.g. `https://matrix.example.com`) |
| `MATRIX_BOT_USER` | Matrix only | — | Bot Matrix user ID (e.g. `@murphy:example.com`) |
| `MATRIX_BOT_TOKEN` | Matrix only | — | Bot access token |
| `MATRIX_BOT_PASSWORD` | Matrix only | — | Bot login password (alternative to token) |
| `MATRIX_DEVICE_ID` | No | — | Device ID for E2EE session restoration |
| `MATRIX_E2E_ENABLED` | No | `false` | Enable end-to-end encryption for Matrix rooms |
| `MATRIX_HOMESERVER_DOMAIN` | Matrix only | — | Homeserver domain (e.g. `example.com`) |
| `MATRIX_AUTO_CREATE_ROOMS` | No | `true` | Automatically create rooms listed in the registry |
| `MATRIX_SPACE_NAME` | No | `Murphy System` | Name of the Murphy Matrix Space |
| `MATRIX_ADMIN_USERS` | No | — | Comma-separated admin Matrix user IDs |
| `MATRIX_CB_THRESHOLD` | No | `5` | Number of failures before the circuit breaker opens |
| `MATRIX_CB_TIMEOUT` | No | `60` | Seconds before a tripped circuit breaker enters half-open state |
| `WEBHOOK_HOST` | No | `0.0.0.0` | Webhook receiver bind host |
| `WEBHOOK_PORT` | No | `8765` | Webhook receiver port |
| `WEBHOOK_SECRET_GITHUB` | No | — | HMAC secret for validating GitHub webhook payloads |
| `WEBHOOK_SECRET_STRIPE` | No | — | HMAC secret for validating Stripe webhook payloads |
| `E2EE_STUB_ALLOWED` | No | `false` | Allow stub E2EE ciphertext (dev/test only) |

---

## 13. Backend Modes (Beta Hardening)

These variables control whether stub/simulated backends are permitted. In `staging`/`production`, stub modes are rejected at startup.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MURPHY_DB_MODE` | No | `live` | `stub` (deterministic in-memory, dev/test) or `live` (real SQLAlchemy). Rejected in staging/production. |
| `MURPHY_POOL_MODE` | No | `real` | `simulated` (in-memory stub pools) or `real` (httpx.AsyncClient). Rejected in staging/production. |
| `MURPHY_EMAIL_REQUIRED` | No | `true` (prod/staging) | `true` = real backend required; `false` = fallback to warning-only mode |
| `MURPHY_ENABLED_PROTOCOLS` | No | `""` | Comma-separated list of required industrial protocols (`bacnet`, `modbus`, `opcua`). Raises `ImportError` at startup if listed and library is absent. |

---

## 14. Complete Variable Index

Quick-reference table of all 96 variables. Required columns: **C** = Core, **S** = Staging/Prod required, **D** = Docker Compose only, **O** = Optional.

| Variable | Type | Section |
|----------|------|---------|
| `ANTHROPIC_API_KEY` | O | §3 LLM |
| `ARISTOTLE_API_KEY` | O | §3 LLM |
| `ARISTOTLE_API_URL` | O | §3 LLM |
| `AUTO_RELOAD` | O | §2 Core |
| `AWS_SES_ACCESS_KEY` | O | §8 Email |
| `AWS_SES_REGION` | O | §8 Email |
| `AWS_SES_SECRET_KEY` | O | §8 Email |
| `COINBASE_WEBHOOK_SECRET` | O | §8 Payment |
| `DATABASE_URL` | O | §4 Database |
| `DEBUG` | O | §2 Core |
| `E2EE_STUB_ALLOWED` | O | §12 Matrix |
| `ENABLE_CORS` | O | §2 Core |
| `ENCRYPTION_KEY` | S | §6 Security |
| `FACEBOOK_ACCESS_TOKEN` | O | §8 Social |
| `FACEBOOK_APP_ID` | O | §8 Social |
| `FACEBOOK_APP_SECRET` | O | §8 Social |
| `GITHUB_TOKEN` | O | §8 GitHub |
| `GOOGLE_ANALYTICS_ID` | O | §8 Analytics |
| `GOOGLE_ANALYTICS_KEY` | O | §8 Analytics |
| `GRAFANA_ADMIN_PASSWORD` | D | §6 Security |
| `GRAFANA_ADMIN_USER` | D | §6 Security |
| `DEEPINFRA_API_KEY` | O | §3 LLM |
| `DEEPINFRA_API_KEYS` | O | §3 LLM |
| `TOGETHER_API_KEY` | O | §3 LLM |
| `HUBSPOT_API_KEY` | O | §8 CRM |
| `JWT_SECRET` | S | §6 Security |
| `LINKEDIN_CLIENT_ID` | O | §8 Social |
| `LINKEDIN_CLIENT_SECRET` | O | §8 Social |
| `LOG_LEVEL` | O | §9 Monitoring |
| `MATRIX_ADMIN_USERS` | O | §12 Matrix |
| `MATRIX_AUTO_CREATE_ROOMS` | O | §12 Matrix |
| `MATRIX_BOT_PASSWORD` | O | §12 Matrix |
| `MATRIX_BOT_TOKEN` | O | §12 Matrix |
| `MATRIX_BOT_USER` | O | §12 Matrix |
| `MATRIX_CB_THRESHOLD` | O | §12 Matrix |
| `MATRIX_CB_TIMEOUT` | O | §12 Matrix |
| `MATRIX_DEVICE_ID` | O | §12 Matrix |
| `MATRIX_E2E_ENABLED` | O | §12 Matrix |
| `MATRIX_HOMESERVER_DOMAIN` | O | §12 Matrix |
| `MATRIX_HOMESERVER_URL` | O | §12 Matrix |
| `MATRIX_SPACE_NAME` | O | §12 Matrix |
| `MEDIUM_ACCESS_TOKEN` | O | §8 Content |
| `MFM_BASE_MODEL` | O | §11 MFM |
| `MFM_CANARY_TRAFFIC_PERCENT` | O | §11 MFM |
| `MFM_CHECKPOINT_DIR` | O | §11 MFM |
| `MFM_DEVICE` | O | §11 MFM |
| `MFM_ENABLED` | O | §11 MFM |
| `MFM_MODE` | O | §11 MFM |
| `MFM_RETRAIN_THRESHOLD` | O | §11 MFM |
| `MFM_SHADOW_MIN_ACCURACY` | O | §11 MFM |
| `MFM_TRACE_DIR` | O | §11 MFM |
| `MURPHY_ANON_RATE_LIMIT` | O | §7 Rate Limiting |
| `MURPHY_API_KEY` | S | §6 Security |
| `MURPHY_API_KEYS` | S | §6 Security |
| `MURPHY_CB_THRESHOLD` | O | §12 Matrix |
| `MURPHY_CORS_ORIGINS` | O | §2 Core |
| `MURPHY_CREDENTIAL_MASTER_KEY` | S | §6 Security |
| `MURPHY_DB_MODE` | O | §13 Backend Modes |
| `MURPHY_EMAIL_REQUIRED` | O | §13 Backend Modes |
| `MURPHY_ENABLED_PROTOCOLS` | O | §13 Backend Modes |
| `MURPHY_ENV` | **C** | §2 Core |
| `MURPHY_EXECUTE_RATE_LIMIT` | O | §7 Rate Limiting |
| `MURPHY_LLM_PROVIDER` | O | §2 Core |
| `MURPHY_LLM_RATE_LIMIT` | O | §7 Rate Limiting |
| `MURPHY_LOG_FORMAT` | O | §9 Monitoring |
| `MURPHY_MAX_RESPONSE_SIZE_MB` | O | §2 Core |
| `MURPHY_PERSISTENCE_DIR` | O | §2 Core |
| `MURPHY_POOL_MODE` | O | §13 Backend Modes |
| `MURPHY_PORT` | O | §2 Core |
| `MURPHY_RATE_LIMIT` | O | §7 Rate Limiting |
| `MURPHY_REDIS_URL` | O | §5 Cache |
| `MURPHY_TASK_CONCURRENCY` | O | §2 Core |
| `MURPHY_VERSION` | O | §2 Core |
| `MURPHY_WORKERS` | O | §2 Core |
| `OPENAI_API_KEY` | O | §3 LLM |
| `PAYPAL_CLIENT_ID` | O | §8 Payment |
| `PAYPAL_CLIENT_SECRET` | O | §8 Payment |
| `PAYPAL_WEBHOOK_SECRET` | O | §8 Payment |
| `PIPEDRIVE_API_TOKEN` | O | §8 CRM |
| `POSTGRES_PASSWORD` | D | §4 Database |
| `PROMETHEUS_PORT` | O | §9 Monitoring |
| `REDIS_PASSWORD` | D | §5 Cache |
| `REDIS_URL` | O | §5 Cache |
| `SALESFORCE_CLIENT_ID` | O | §8 CRM |
| `SALESFORCE_CLIENT_SECRET` | O | §8 CRM |
| `SALESFORCE_PASSWORD` | O | §8 CRM |
| `SALESFORCE_USERNAME` | O | §8 CRM |
| `SENDGRID_API_KEY` | O | §8 Email |
| `SENTRY_DSN` | O | §9 Monitoring |
| `STRIPE_API_KEY` | O | §8 Payment |
| `STRIPE_PUBLISHABLE_KEY` | O | §8 Payment |
| `TWILIO_ACCOUNT_SID` | O | §8 Email |
| `TWILIO_AUTH_TOKEN` | O | §8 Email |
| `TWILIO_PHONE_NUMBER` | O | §8 Email |
| `TWITTER_API_KEY` | O | §8 Social |
| `TWITTER_API_SECRET` | O | §8 Social |
| `TWITTER_ACCESS_SECRET` | O | §8 Social |
| `TWITTER_ACCESS_TOKEN` | O | §8 Social |
| `WEBHOOK_HOST` | O | §12 Matrix |
| `WEBHOOK_PORT` | O | §12 Matrix |
| `WEBHOOK_SECRET_GITHUB` | O | §12 Matrix |
| `WEBHOOK_SECRET_STRIPE` | O | §12 Matrix |
| `WORDPRESS_PASSWORD` | O | §8 Content |
| `WORDPRESS_URL` | O | §8 Content |
| `WORDPRESS_USERNAME` | O | §8 Content |
| `WULFRUM_API_KEY` | O | §3 LLM |
| `WULFRUM_API_URL` | O | §3 LLM |

**Key:** C = Core (always set), S = Required in staging/production, D = Docker Compose only, O = Optional

---

## See Also

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Scaling](SCALING.md)
- [Installation](../getting_started/INSTALLATION.md)

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

# GitHub Secrets Checklist

All secrets are configured in **Settings → Secrets and variables → Actions** on the GitHub repository.

---

## Hetzner Deploy (`hetzner-deploy.yml`)

| Secret | Required | Description | How to obtain |
|---|---|---|---|
| `HETZNER_HOST` | ✅ Required | IP address or hostname of the Hetzner VPS | Hetzner Cloud Console → Server → IPv4 |
| `HETZNER_SSH_KEY` | ✅ Required | Private SSH key for root login to the Hetzner VPS | Generate: `ssh-keygen -t ed25519 -C "murphy-deploy"` — add public key to server's `authorized_keys` |

---

## Production Deploy (`deploy.yml`)

This workflow is **manual-only** (`workflow_dispatch`) and requires the `production` environment to be configured in GitHub (Settings → Environments).

| Secret | Required | Description | How to obtain |
|---|---|---|---|
| `DEPLOY_HOST` | ✅ Required | Production server hostname or IP | Hetzner Cloud Console |
| `DEPLOY_USER` | ✅ Required | SSH username (e.g. `root`) | Server configuration |
| `DEPLOY_PASSWORD` | ✅ Required | SSH password (prefer key-based auth when possible) | Server configuration |

---

## Application Secrets (set in GitHub and injected at deploy time)

These are written to `/etc/murphy-production/environment` during deploy.

| Secret | Required | Description | How to generate |
|---|---|---|---|
| `MURPHY_SECRET_KEY` | ✅ Required | Flask/FastAPI session signing key | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MURPHY_JWT_SECRET` | ✅ Required | JWT signing secret | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | ✅ Required | Data encryption key (Fernet) | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `MURPHY_API_KEY` | ✅ Required | Internal API authentication key | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `POSTGRES_PASSWORD` | ✅ Required | PostgreSQL database password | `python -c "import secrets; print(secrets.token_urlsafe(24))"` |
| `REDIS_PASSWORD` | ✅ Required | Redis authentication password | `python -c "import secrets; print(secrets.token_urlsafe(24))"` |
| `GRAFANA_ADMIN_PASSWORD` | ✅ Required | Grafana admin UI password | Choose a strong password |
| `SMTP_PASSWORD` | ⚠️ Optional | SMTP email sending password | Your mail provider's app password |

---

## Optional / External Service Secrets

These enable additional integrations but are not required for core operation.

| Secret | Description | Provider |
|---|---|---|
| `GROQ_API_KEY` | LLM inference via Groq (faster/cheaper than OpenAI) | [console.groq.com](https://console.groq.com) |
| `OPENAI_API_KEY` | OpenAI GPT models | [platform.openai.com](https://platform.openai.com) |
| `STRIPE_SECRET_KEY` | Payment processing | [dashboard.stripe.com](https://dashboard.stripe.com) |
| `SENTRY_DSN` | Error tracking | [sentry.io](https://sentry.io) |

---

## Quick Setup Script

Run `scripts/generate_secrets.sh` to generate all required secret values at once:

```bash
bash scripts/generate_secrets.sh
```

This outputs a `.env`-style block you can copy into GitHub Secrets one by one.

---

## Deploy Dependency Order

Before the deploy workflows will succeed, ensure:

1. ☐ Hetzner VPS provisioned (CX21 or larger, Ubuntu 24.04)
2. ☐ SSH key added to server's `authorized_keys`
3. ☐ `/opt/Murphy-System` cloned on the server (main branch): `git clone -b main https://github.com/IKNOWINOT/Murphy-System /opt/Murphy-System`
4. ☐ `HETZNER_HOST` and `HETZNER_SSH_KEY` secrets added to GitHub
5. ☐ All application secrets (`MURPHY_SECRET_KEY`, etc.) added to GitHub
6. ☐ `production` environment created in GitHub (Settings → Environments) for manual approval gate

# Murphy System — GitHub Secrets Reference

All sensitive credentials for Murphy System are stored as **GitHub Actions Secrets**
and are never committed to the repository.

> Settings → Secrets and variables → Actions

---

## Secrets by Category

### Deployment

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Hetzner VPS IP address (e.g. `5.78.41.114`) |
| `DEPLOY_USER` | SSH login username (typically `root`) |
| `DEPLOY_PASSWORD` | SSH password for the VPS |

### Core Application

| Secret | Description |
|--------|-------------|
| `MURPHY_SECRET_KEY` | Flask/FastAPI session signing key (48-byte URL-safe token) |
| `MURPHY_JWT_SECRET` | JWT token signing secret (64-char hex string) |
| `ENCRYPTION_KEY` | Data-at-rest encryption key (64-char hex string) |
| `MURPHY_API_KEY` | API authentication key (prefixed `mk_`) |

### Database & Cache

| Secret | Description |
|--------|-------------|
| `POSTGRES_PASSWORD` | PostgreSQL `murphy` user password |
| `REDIS_PASSWORD` | Redis AUTH password |

### Monitoring

| Secret | Description |
|--------|-------------|
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin user password |

### Email

| Secret | Description |
|--------|-------------|
| `SMTP_PASSWORD` | SMTP authentication password for outbound mail |

### Optional / Future

These secrets are not currently required but are referenced in the environment
template for future use. Add them to GitHub Secrets when you are ready to
enable the corresponding integrations.

| Secret | Description |
|--------|-------------|
| `GROQ_API_KEY` | Groq cloud LLM API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API key |
| `MATRIX_ACCESS_TOKEN` | Matrix homeserver access token |
| `MATRIX_PASSWORD` | Matrix account password |
| `SENDGRID_API_KEY` | SendGrid transactional email API key |
| `PAYPAL_CLIENT_ID` | PayPal client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal client secret |
| `COINBASE_COMMERCE_API_KEY` | Coinbase Commerce API key |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret |

---

## How to Add or Update a Secret

1. Go to **Settings → Secrets and variables → Actions** in the GitHub repository.
2. Click **New repository secret** to add, or the **pencil icon (✏️)** to update.
3. Enter the secret **Name** (exact match, case-sensitive).
4. Paste the secret **Value** (no surrounding quotes).
5. Click **Add secret** / **Update secret**.

---

## How to Generate New Secret Values

Run these commands on any Linux/macOS terminal or on your server:

```bash
# MURPHY_SECRET_KEY (48-byte URL-safe token)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# POSTGRES_PASSWORD (strong random password)
openssl rand -base64 24

# REDIS_PASSWORD
openssl rand -base64 24

# GRAFANA_ADMIN_PASSWORD
openssl rand -base64 16

# MURPHY_JWT_SECRET (64-char hex)
python3 -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY (64-char hex)
python3 -c "import secrets; print(secrets.token_hex(32))"

# MURPHY_API_KEY (prefixed mk_)
python3 -c "import secrets; print('mk_' + secrets.token_hex(24))"

# SMTP_PASSWORD
openssl rand -base64 16
```

Or use the convenience script included in the repository:

```bash
bash scripts/generate_secrets.sh
```

---

## Additional Required Secrets (app.py — undocumented until now)

The following env vars are read directly by `src/runtime/app.py` and were
missing from the list above.  Add them to `/etc/murphy-production/environment`
and to the GitHub Actions secrets for the deploy workflow.

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/murphy` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `MATRIX_HOMESERVER_URL` | Matrix homeserver URL | `https://matrix.murphy.systems` |
| `OLLAMA_HOST` | Ollama inference server URL | `http://localhost:11434` |
| `MURPHY_API_KEYS` | Comma-separated API key list (multi-key auth) | `key1,key2` |
| `MURPHY_FOUNDER_EMAIL` | Founder account email (seeded at startup) | `cpost@murphy.systems` |
| `MURPHY_FOUNDER_PASSWORD` | Founder account password (change after first login) | *(generate with `scripts/generate_secrets.sh`)* |
| `MURPHY_OAUTH_GOOGLE_SECRET` | Google OAuth client secret | *(from Google Cloud Console)* |

---

## Where Secrets Are Used

The deploy workflow (`.github/workflows/deploy.yml`) writes all secrets to the
production environment file on the server:

```
/etc/murphy-production/environment
```

This file has permissions `600` (readable only by root) and is **never** committed
to the repository (listed in `.gitignore`).

The systemd `murphy-production.service` reads that file via
`EnvironmentFile=/etc/murphy-production/environment`, and
`docker-compose.hetzner.yml` sources it for the support containers
(PostgreSQL, Redis, Grafana, etc.).

---

## Security Notes

- **Never** hardcode secrets in source files, config templates, or Docker images.
- **Never** commit `config/mail/postfix-accounts.cf` — it is generated at deploy time by `scripts/mail_setup.sh`.
- Rotate secrets immediately if any are exposed (leaked in logs, a PR, etc.).
- Use `chmod 600 /etc/murphy-production/environment` to protect the env file on the server.

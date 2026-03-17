# scripts/ — Murphy System Bootstrap & Operations

Runnable scripts for production bootstrap, secret generation, and auth
verification.  All scripts assume they are run from the **repository root**.

---

## `bootstrap_founder.py`

Creates the founder (god-user) account and an optional test worker account
via `SignupGateway`.  Run **once** on first deployment.

```bash
python scripts/bootstrap_founder.py \
    --email founder@yourdomain.com \
    --name "Your Name" \
    --org-name "Your Organisation" \
    --test-email testuser@yourdomain.com
```

**Arguments**

| Argument | Default | Description |
|----------|---------|-------------|
| `--email` | `founder@murphy.local` | Founder email address |
| `--name` | `Murphy Founder` | Founder display name |
| `--org-name` | `Murphy System` | Organisation to create |
| `--test-email` | *(none)* | Optional second account (joins same org, role=worker) |

**Output** — prints `FOUNDER_USER_ID`, `ORG_ID`, and optionally
`TEST_USER_ID`.  Save these in your operator runbook.

---

## `generate_secrets.sh`

Generates all required production secrets and prints them ready to paste
into `.env`.

```bash
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh            # print to stdout
./scripts/generate_secrets.sh >> .env    # append to .env
```

**Secrets generated**

| Variable | Description |
|----------|-------------|
| `MURPHY_API_KEYS` | Comma-separated founder + test API keys |
| `FOUNDER_API_KEY` | Founder key (also inside `MURPHY_API_KEYS`) |
| `TEST_API_KEY` | Test key (also inside `MURPHY_API_KEYS`) |
| `MURPHY_CREDENTIAL_MASTER_KEY` | Fernet key for credential encryption |
| `MURPHY_JWT_SECRET` | Hex token for JWT signing |
| `ENCRYPTION_KEY` | Hex token for general encryption |
| `POSTGRES_PASSWORD` | URL-safe random password |
| `REDIS_PASSWORD` | URL-safe random password |
| `GRAFANA_ADMIN_PASSWORD` | URL-safe random password |

> ⚠️ **Never commit `.env` to version control.**

---

## `test_production_auth.sh`

End-to-end auth smoke test.  Verifies that:

- Health endpoints (`/health`, `/healthz`, `/ready`) return **200** without a key.
- Non-health endpoints return **401** when no key is supplied.
- An invalid key returns **401**.
- A valid founder key via `Authorization: Bearer` returns **200**.
- A valid founder key via `X-API-Key` returns **200**.
- A valid test key also returns **200** via both header styles.

```bash
chmod +x scripts/test_production_auth.sh

# Using environment variables:
MURPHY_URL=http://localhost:5000 \
FOUNDER_KEY=founder_abc123       \
TEST_KEY=test_xyz456             \
./scripts/test_production_auth.sh

# Or positional arguments:
./scripts/test_production_auth.sh http://localhost:5000 founder_abc123 test_xyz456
```

Exit code `0` = all tests passed, `1` = one or more failures.

---

## Other scripts

| Script | Description |
|--------|-------------|
| `preflight_check.sh` | Pre-deployment environment validation |
| `production_readiness_check.sh` | Full production readiness scan |
| `security_audit.py` | Python security audit runner |
| `generate_secrets.sh` | Production secret generation *(new)* |
| `bootstrap_founder.py` | Founder account bootstrap *(new)* |
| `test_production_auth.sh` | Auth smoke tests *(new)* |

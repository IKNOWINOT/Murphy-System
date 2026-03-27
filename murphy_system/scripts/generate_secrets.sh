#!/usr/bin/env bash
# generate_secrets.sh — Murphy System
#
# Generates all required production secrets and prints them ready to paste
# into your .env file.
#
# Requirements:
#   - Python 3 (for Fernet key generation and secrets module)
#   - openssl (for hex tokens; ships with macOS and most Linux distros)
#
# Usage:
#   chmod +x scripts/generate_secrets.sh
#   ./scripts/generate_secrets.sh
#   ./scripts/generate_secrets.sh >> .env   # append to existing .env
#   ./scripts/generate_secrets.sh --production  # write all secrets to /etc/murphy-production/environment
#
# WARNING: Output contains sensitive secrets. Handle with care.
# Do NOT commit the generated .env to version control.

set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Secret Generator

Generates all required production secrets for the Murphy System and prints
them in .env format ready to use.

Usage:
  $(basename "$0") [OPTIONS]

Options:
  -h, --help       Show this help message and exit
  --version        Show version information
  -o, --output     Output directly to .env file (creates backup if exists)
  --json           Output in JSON format instead of .env
  --production     Write complete production secrets to /etc/murphy-production/environment
  --force          Overwrite existing env file (only used with --production)

Generated secrets:
  • MURPHY_SECRET_KEY             Application secret key (token_urlsafe 48)
  • MURPHY_API_KEYS              Comma-separated API keys (founder + test)
  • FOUNDER_API_KEY              Individual founder key
  • TEST_API_KEY                 Individual test key
  • MURPHY_CREDENTIAL_MASTER_KEY Fernet encryption key for credentials
  • MURPHY_JWT_SECRET            JWT signing secret
  • ENCRYPTION_KEY               General encryption key
  • POSTGRES_USER                PostgreSQL username (murphy)
  • POSTGRES_PASSWORD            PostgreSQL database password
  • POSTGRES_DB                  PostgreSQL database name (murphy)
  • POSTGRES_PORT                PostgreSQL port (5432)
  • DATABASE_URL                 Full PostgreSQL connection string
  • REDIS_PASSWORD               Redis cache password
  • REDIS_URL                    Full Redis connection string
  • GRAFANA_ADMIN_USER           Grafana admin username (admin)
  • GRAFANA_ADMIN_PASSWORD       Grafana admin password
  • OLLAMA_HOST                  Ollama LLM host (http://localhost:11434)
  • SMTP_HOST                    SMTP server host (localhost)
  • SMTP_PORT                    SMTP server port (587)
  • SMTP_USER                    SMTP username
  • SMTP_PASSWORD                SMTP password
  • MURPHY_MAIL_HOSTNAME         Mail server hostname
  • MURPHY_MAIL_DOMAIN           Mail domain

Examples:
  $(basename "$0")                        # Print secrets to stdout
  $(basename "$0") >> .env               # Append to .env file
  $(basename "$0") -o                    # Write directly to .env
  $(basename "$0") --json                # Output as JSON
  $(basename "$0") --production          # Write to /etc/murphy-production/environment
  $(basename "$0") --production --force  # Overwrite existing env file

Security:
  ⚠️  Never commit generated secrets to version control
  ⚠️  Store .env files securely with restricted permissions

EOF
  exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
OUTPUT_TO_FILE=false
JSON_FORMAT=false
PRODUCTION_MODE=false
FORCE_OVERWRITE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    --version)
      echo "Murphy System Secret Generator v1.1.0"
      exit 0
      ;;
    -o|--output)
      OUTPUT_TO_FILE=true
      shift
      ;;
    --json)
      JSON_FORMAT=true
      shift
      ;;
    --production)
      PRODUCTION_MODE=true
      shift
      ;;
    --force)
      FORCE_OVERWRITE=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Helper: require a command
# ---------------------------------------------------------------------------
need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' not found. Please install it and re-run." >&2
    exit 1
  }
}

need python3
need openssl

# ---------------------------------------------------------------------------
# Helper: generate a Fernet key (32-byte URL-safe base64)
# ---------------------------------------------------------------------------
fernet_key() {
  python3 - <<'PYEOF'
try:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
except ImportError:
    import base64, os
    print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PYEOF
}

# ---------------------------------------------------------------------------
# Helper: generate a URL-safe random token
# ---------------------------------------------------------------------------
urlsafe_token() {
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

# ---------------------------------------------------------------------------
# Helper: generate a hex token
# ---------------------------------------------------------------------------
hex_token() {
  python3 -c "import secrets; print(secrets.token_hex(32))"
}

# ---------------------------------------------------------------------------
# Helper: generate a simple random API key (prefix + hex)
# ---------------------------------------------------------------------------
api_key() {
  local prefix="${1:-mk}"
  echo "${prefix}_$(python3 -c "import secrets; print(secrets.token_hex(24))")"
}

# ---------------------------------------------------------------------------
# --production mode: write complete env file to /etc/murphy-production/environment
# ---------------------------------------------------------------------------
if [ "$PRODUCTION_MODE" = true ]; then
  PROD_ENV_DIR="/etc/murphy-production"
  PROD_ENV_FILE="${PROD_ENV_DIR}/environment"

  # Refuse to overwrite unless --force is also passed
  if [ -f "$PROD_ENV_FILE" ] && [ "$FORCE_OVERWRITE" = false ]; then
    echo "ERROR: ${PROD_ENV_FILE} already exists." >&2
    echo "Pass --force to overwrite it, or back it up first." >&2
    exit 1
  fi

  # Create directory if it doesn't exist
  mkdir -p "$PROD_ENV_DIR"

  # Generate all secret values up-front so DATABASE_URL and REDIS_URL
  # reference the same passwords as their individual variables.
  MURPHY_SECRET_KEY_VAL="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
  FOUNDER_KEY="$(api_key founder)"
  TEST_KEY="$(api_key test)"
  CRED_MASTER_KEY="$(fernet_key)"
  JWT_SECRET="$(hex_token)"
  ENC_KEY="$(hex_token)"
  PG_PASSWORD="$(urlsafe_token)"
  REDIS_PASSWORD_VAL="$(urlsafe_token)"
  GRAFANA_PASSWORD="$(urlsafe_token)"
  SMTP_PASSWORD_VAL="$(urlsafe_token)"

  cat > "$PROD_ENV_FILE" <<ENVEOF
# Murphy System — Production Environment
# Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
# WARNING: Keep this file secret. Never commit to version control.

# ── Murphy Application ────────────────────────────────────────────────────────
MURPHY_SECRET_KEY=${MURPHY_SECRET_KEY_VAL}
MURPHY_API_KEYS=${FOUNDER_KEY},${TEST_KEY}
FOUNDER_API_KEY=${FOUNDER_KEY}
TEST_API_KEY=${TEST_KEY}

# ── Encryption / Auth ─────────────────────────────────────────────────────────
MURPHY_CREDENTIAL_MASTER_KEY=${CRED_MASTER_KEY}
MURPHY_JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENC_KEY}

# ── PostgreSQL ────────────────────────────────────────────────────────────────
POSTGRES_USER=murphy
POSTGRES_PASSWORD=${PG_PASSWORD}
POSTGRES_DB=murphy
POSTGRES_PORT=5432
DATABASE_URL=postgresql://murphy:${PG_PASSWORD}@localhost:5432/murphy

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_PASSWORD=${REDIS_PASSWORD_VAL}
REDIS_URL=redis://:${REDIS_PASSWORD_VAL}@localhost:6379/0

# ── Grafana ───────────────────────────────────────────────────────────────────
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}

# ── Ollama (onboard LLM) ──────────────────────────────────────────────────────
OLLAMA_HOST=http://localhost:11434

# ── SMTP / Mail ───────────────────────────────────────────────────────────────
SMTP_HOST=localhost
SMTP_PORT=587
SMTP_USER=murphy@murphy.systems
SMTP_PASSWORD=${SMTP_PASSWORD_VAL}
MURPHY_MAIL_HOSTNAME=mail.murphy.systems
MURPHY_MAIL_DOMAIN=murphy.systems
ENVEOF

  chmod 600 "$PROD_ENV_FILE"
  echo "✅ Production secrets written to ${PROD_ENV_FILE} (mode 600)" >&2
  exit 0
fi

# ---------------------------------------------------------------------------
# Default mode: generate all secrets and print to stdout
# ---------------------------------------------------------------------------
echo "# Murphy System — Generated Production Secrets"
echo "# Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "# WARNING: Keep this file secret. Never commit to version control."
echo ""

FOUNDER_KEY="$(api_key founder)"
TEST_KEY="$(api_key test)"

echo "# API keys — comma-separated (founder key first, then additional keys)"
echo "MURPHY_API_KEYS=${FOUNDER_KEY},${TEST_KEY}"
echo ""
echo "# Individual keys for testing scripts"
echo "FOUNDER_API_KEY=${FOUNDER_KEY}"
echo "TEST_API_KEY=${TEST_KEY}"
echo ""

echo "# Credential encryption master key (Fernet)"
echo "MURPHY_CREDENTIAL_MASTER_KEY=$(fernet_key)"
echo ""

echo "# JWT signing secret"
echo "MURPHY_JWT_SECRET=$(hex_token)"
echo ""

echo "# General encryption key"
echo "ENCRYPTION_KEY=$(hex_token)"
echo ""

echo "# PostgreSQL"
echo "POSTGRES_PASSWORD=$(urlsafe_token)"
echo ""

echo "# Redis"
echo "REDIS_PASSWORD=$(urlsafe_token)"
echo ""

echo "# Grafana"
echo "GRAFANA_ADMIN_PASSWORD=$(urlsafe_token)"
echo ""

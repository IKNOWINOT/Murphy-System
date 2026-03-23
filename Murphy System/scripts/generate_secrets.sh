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
  -h, --help     Show this help message and exit
  --version      Show version information
  -o, --output   Output directly to .env file (creates backup if exists)
  --json         Output in JSON format instead of .env

Generated secrets:
  • MURPHY_API_KEYS              Comma-separated API keys (founder + test)
  • FOUNDER_API_KEY              Individual founder key
  • TEST_API_KEY                 Individual test key
  • MURPHY_CREDENTIAL_MASTER_KEY Fernet encryption key for credentials
  • MURPHY_JWT_SECRET            JWT signing secret
  • ENCRYPTION_KEY               General encryption key
  • POSTGRES_PASSWORD            PostgreSQL database password
  • REDIS_PASSWORD               Redis cache password
  • GRAFANA_ADMIN_PASSWORD       Grafana admin password

Examples:
  $(basename "$0")                 # Print secrets to stdout
  $(basename "$0") >> .env         # Append to .env file
  $(basename "$0") -o              # Write directly to .env
  $(basename "$0") --json          # Output as JSON

Security:
  ⚠️  Never commit generated secrets to version control
  ⚠️  Store .env files securely with restricted permissions

EOF
  exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
OUTPUT_TO_FILE=false
JSON_FORMAT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    --version)
      echo "Murphy System Secret Generator v1.0.0"
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
# Generate all secrets
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

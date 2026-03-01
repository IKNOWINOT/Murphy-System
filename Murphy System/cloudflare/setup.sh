#!/usr/bin/env bash
# Murphy System — Cloudflare Infrastructure Setup
# Run this from the cloudflare/ directory:
#   cd "Murphy System/cloudflare" && bash setup.sh
#
# Prerequisites:
#   1. Node.js 18+ installed
#   2. npm install (run first to install wrangler)
#   3. wrangler login (authenticate with Cloudflare)

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }
step() { echo -e "\n${BOLD}━━━ $1 ━━━${NC}"; }

# Verify we're in the right directory
if [ ! -f "wrangler.toml" ]; then
  err "Run this script from the cloudflare/ directory."
  err "  cd \"Murphy System/cloudflare\" && bash setup.sh"
  exit 1
fi

# Verify wrangler is available
if ! npx wrangler --version &>/dev/null; then
  err "wrangler not found. Run 'npm install' first."
  exit 1
fi

echo -e "${BOLD}Murphy System — Cloudflare Infrastructure Setup${NC}"
echo "This script will create all Cloudflare resources and run D1 migrations."
echo ""

# ─────────────────────────────────────────────
step "Step 1: Create D1 Database"
# ─────────────────────────────────────────────

# Check if database already exists
EXISTING_DB=$(npx wrangler d1 list 2>/dev/null | grep "murphy-system-db" || true)

if [ -n "$EXISTING_DB" ]; then
  warn "D1 database 'murphy-system-db' already exists."
  DB_ID=$(echo "$EXISTING_DB" | awk '{print $1}')
  log "Using existing database_id: $DB_ID"
else
  echo "Creating D1 database..."
  CREATE_OUTPUT=$(npx wrangler d1 create murphy-system-db 2>&1)
  echo "$CREATE_OUTPUT"
  DB_ID=$(echo "$CREATE_OUTPUT" | grep -oP 'database_id\s*=\s*"\K[^"]+' || true)

  if [ -z "$DB_ID" ]; then
    err "Could not extract database_id from output. Please extract it manually and update wrangler.toml."
    echo "$CREATE_OUTPUT"
    echo ""
    read -rp "Paste the database_id here: " DB_ID
  fi
  log "Created D1 database with id: $DB_ID"
fi

# Update wrangler.toml with the actual database_id
if grep -q "REPLACE_WITH_ACTUAL_D1_DATABASE_ID" wrangler.toml; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/REPLACE_WITH_ACTUAL_D1_DATABASE_ID/$DB_ID/" wrangler.toml
  else
    sed -i "s/REPLACE_WITH_ACTUAL_D1_DATABASE_ID/$DB_ID/" wrangler.toml
  fi
  log "Updated wrangler.toml with database_id"
else
  warn "wrangler.toml already has a database_id set."
fi

# ─────────────────────────────────────────────
step "Step 2: Create R2 Bucket"
# ─────────────────────────────────────────────

EXISTING_R2=$(npx wrangler r2 bucket list 2>/dev/null | grep "murphy-agent-artifacts" || true)
if [ -n "$EXISTING_R2" ]; then
  warn "R2 bucket 'murphy-agent-artifacts' already exists."
else
  npx wrangler r2 bucket create murphy-agent-artifacts
  log "Created R2 bucket: murphy-agent-artifacts"
fi

# ─────────────────────────────────────────────
step "Step 3: Create Queue"
# ─────────────────────────────────────────────

EXISTING_Q=$(npx wrangler queues list 2>/dev/null | grep "murphy-hitl-approvals" || true)
if [ -n "$EXISTING_Q" ]; then
  warn "Queue 'murphy-hitl-approvals' already exists."
else
  npx wrangler queues create murphy-hitl-approvals
  log "Created queue: murphy-hitl-approvals"
fi

# ─────────────────────────────────────────────
step "Step 4: Run D1 Migrations"
# ─────────────────────────────────────────────

echo "Running migration: migrations/0001_initial.sql"
npx wrangler d1 execute murphy-system-db --file=migrations/0001_initial.sql --remote
log "D1 migrations complete!"

# ─────────────────────────────────────────────
step "Step 5: Store Secrets"
# ─────────────────────────────────────────────

echo "Now storing secrets via 'wrangler secret put'."
echo "Each secret will be prompted interactively (values are NOT echoed)."
echo ""

SECRETS=(
  "JWT_SECRET"
  "STRIPE_SECRET_KEY"
  "STRIPE_PUBLISHABLE_KEY"
  "STRIPE_WEBHOOK_SECRET"
  "SERVICE_TOKEN"
  "FOUNDER_ASSIGNMENT_SECRET"
  "LLM_PROVIDER_KEYS_JSON"
)

for SECRET_NAME in "${SECRETS[@]}"; do
  echo ""
  echo -e "${BOLD}$SECRET_NAME${NC}"
  case "$SECRET_NAME" in
    JWT_SECRET)              echo "  JWT signing secret (any strong random string)" ;;
    STRIPE_SECRET_KEY)       echo "  Stripe secret key (sk_test_... or sk_live_...)" ;;
    STRIPE_PUBLISHABLE_KEY)  echo "  Stripe publishable key (pk_test_... or pk_live_...)" ;;
    STRIPE_WEBHOOK_SECRET)   echo "  Stripe webhook signing secret (whsec_...)" ;;
    SERVICE_TOKEN)           echo "  Internal service-to-service auth token" ;;
    FOUNDER_ASSIGNMENT_SECRET) echo "  Founder role assignment secret" ;;
    LLM_PROVIDER_KEYS_JSON)  echo "  Optional JSON of platform-default LLM keys (press Enter for empty)" ;;
  esac

  read -rp "  Enter value (or press Enter to skip): " -s SECRET_VALUE
  echo ""

  if [ -n "$SECRET_VALUE" ]; then
    echo "$SECRET_VALUE" | npx wrangler secret put "$SECRET_NAME"
    log "Stored $SECRET_NAME"
  else
    warn "Skipped $SECRET_NAME (you can set it later with: npx wrangler secret put $SECRET_NAME)"
  fi
done

# ─────────────────────────────────────────────
step "Setup Complete!"
# ─────────────────────────────────────────────

echo ""
echo -e "${GREEN}All Cloudflare resources are ready.${NC}"
echo ""
echo "Next steps:"
echo "  1. Deploy the worker:    npm run deploy"
echo "  2. Run locally:          npm run dev"
echo "  3. Type-check:           npm run typecheck"
echo ""
echo "Your D1 database_id: $DB_ID"
echo ""

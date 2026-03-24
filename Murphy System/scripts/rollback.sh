#!/usr/bin/env bash
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Deployment Rollback Script
#
# Rolls back the Murphy production service to a previous git commit or tag
# and verifies the health endpoint afterwards.
#
# Usage:
#   bash scripts/rollback.sh                   # rollback to previous commit (HEAD~1)
#   bash scripts/rollback.sh --tag v1.0.0      # rollback to a specific tag
#   bash scripts/rollback.sh --commit abc1234  # rollback to a specific commit
#   bash scripts/rollback.sh --help

set -euo pipefail

# ── Constants ─────────────────────────────────────────────────────────────────
SCRIPT_VERSION="1.0.0"
DEPLOY_DIR="${MURPHY_DEPLOY_DIR:-/opt/Murphy-System}"
SERVICE="${MURPHY_SERVICE:-murphy-production}"
HEALTH_URL="${MURPHY_HEALTH_URL:-http://localhost:8000/api/health}"
HEALTH_RETRIES=12          # 12 × 5s = 60 seconds max wait
HEALTH_INTERVAL=5

# Colour output
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[rollback] $*${NC}"; }
success() { echo -e "${GREEN}[rollback] ✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}[rollback] ⚠️  $*${NC}"; }
die()     { echo -e "${RED}[rollback] ❌ $*${NC}" >&2; exit 1; }

# ── Help / version ────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Deployment Rollback Script v${SCRIPT_VERSION}

Stops the Murphy production service, checks out the target revision,
reinstalls dependencies if requirements changed, and restarts the service.

Usage:
  $(basename "$0") [OPTIONS]

Options:
  --tag <tag>        Roll back to a specific git tag (e.g. v1.0.0)
  --commit <sha>     Roll back to a specific git commit SHA
  --target <ref>     Roll back to any git ref (tag, branch, SHA)
  --no-restart       Check out the revision but do not restart the service
  --dry-run          Print what would happen without making any changes
  -h, --help         Show this help message and exit
  --version          Show version information and exit

Environment variables:
  MURPHY_DEPLOY_DIR  Deployment directory (default: /opt/Murphy-System)
  MURPHY_SERVICE     Systemd service name (default: murphy-production)
  MURPHY_HEALTH_URL  Health endpoint URL (default: http://localhost:8000/api/health)

Examples:
  $(basename "$0")                   # Roll back to the previous commit
  $(basename "$0") --tag v1.0.0      # Roll back to the v1.0.0 tag
  $(basename "$0") --commit abc1234  # Roll back to a specific SHA
  $(basename "$0") --dry-run         # Show what would happen, no changes

Exit codes:
  0  Rollback succeeded and health check passed
  1  Rollback failed or health check did not recover

EOF
  exit 0
}

# ── Argument parsing ──────────────────────────────────────────────────────────
TARGET_REF=""
NO_RESTART=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)      shift; TARGET_REF="$1" ;;
    --commit)   shift; TARGET_REF="$1" ;;
    --target)   shift; TARGET_REF="$1" ;;
    --no-restart) NO_RESTART=true ;;
    --dry-run)  DRY_RUN=true ;;
    -h|--help)  show_help ;;
    --version)  echo "Murphy System Rollback v${SCRIPT_VERSION}"; exit 0 ;;
    *)          die "Unknown option: $1. Use --help for usage." ;;
  esac
  shift
done

# Default: roll back to HEAD~1
if [[ -z "$TARGET_REF" ]]; then
  TARGET_REF="HEAD~1"
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
run() {
  if $DRY_RUN; then
    echo -e "${YELLOW}[dry-run] $*${NC}"
  else
    eval "$@"
  fi
}

wait_for_health() {
  info "Waiting for health endpoint to respond (max $((HEALTH_RETRIES * HEALTH_INTERVAL))s)…"
  for i in $(seq 1 "$HEALTH_RETRIES"); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
      success "Health endpoint responded OK"
      return 0
    fi
    echo -n "."
    sleep "$HEALTH_INTERVAL"
  done
  echo ""
  return 1
}

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [[ ! -d "$DEPLOY_DIR/.git" ]] && ! $DRY_RUN; then
  die "$DEPLOY_DIR is not a git repository"
fi

# Capture the current HEAD for the audit log
CURRENT_REF="$(cd "$DEPLOY_DIR" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
info "Current HEAD: $CURRENT_REF"
info "Rolling back to: $TARGET_REF"

if $DRY_RUN; then
  warn "DRY RUN — no changes will be made"
fi

# ── Step 1: Stop the service ──────────────────────────────────────────────────
info "Step 1/5 — Stopping $SERVICE…"
if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
  run "systemctl stop '$SERVICE'"
  success "$SERVICE stopped"
else
  warn "$SERVICE was not running (continuing anyway)"
fi

# ── Step 2: Check out the target revision ────────────────────────────────────
info "Step 2/5 — Checking out $TARGET_REF…"
run "cd '$DEPLOY_DIR' && git fetch --tags origin 2>/dev/null || true"
run "cd '$DEPLOY_DIR' && git checkout '$TARGET_REF'"
NEW_REF="$(cd "$DEPLOY_DIR" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
success "Checked out $NEW_REF"

# ── Step 3: Reinstall dependencies if requirements changed ───────────────────
info "Step 3/5 — Checking if requirements changed…"
if $DRY_RUN; then
  warn "[dry-run] Would reinstall requirements if changed"
elif git -C "$DEPLOY_DIR" diff --name-only "$CURRENT_REF" "$NEW_REF" 2>/dev/null | grep -q "requirements"; then
  info "requirements file changed — reinstalling dependencies…"
  run "cd '$DEPLOY_DIR' && source venv/bin/activate && pip install -q -r requirements_murphy_1.0.txt"
  success "Dependencies reinstalled"
else
  success "Requirements unchanged — skipping reinstall"
fi

# ── Step 4: Reload nginx config ───────────────────────────────────────────────
info "Step 4/5 — Reloading nginx…"
if systemctl is-active --quiet nginx 2>/dev/null; then
  run "nginx -t && systemctl reload nginx"
  success "nginx reloaded"
else
  warn "nginx not running — skipping reload"
fi

# ── Step 5: Restart the service ───────────────────────────────────────────────
if $NO_RESTART; then
  warn "--no-restart flag set — skipping service start"
  success "Rollback to $NEW_REF complete (service not restarted)"
  exit 0
fi

info "Step 5/5 — Starting $SERVICE…"
run "systemctl start '$SERVICE'"
success "$SERVICE started"

if ! $DRY_RUN; then
  if wait_for_health; then
    success "Rollback complete — service is healthy at $NEW_REF"
  else
    die "Health check failed after rollback to $NEW_REF — manual intervention required"
  fi
else
  warn "[dry-run] Skipped health check"
  success "Dry-run complete — rollback to $TARGET_REF would have succeeded"
fi

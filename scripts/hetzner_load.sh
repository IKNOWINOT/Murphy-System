#!/usr/bin/env bash
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Hetzner Load Script
#
# Pulls the latest code, reloads the environment, updates dependencies,
# ensures Ollama is running, and restarts the Murphy System service on
# the Hetzner production server.
#
# Run this on the Hetzner box as root (or a user with sudo + systemctl rights):
#
#   bash /opt/Murphy-System/scripts/hetzner_load.sh
#
# Usage:
#   ./scripts/hetzner_load.sh [OPTIONS]
#
# Options:
#   -h, --help         Show this help message and exit
#   --version          Show version information
#   --skip-deps        Skip pip dependency update (faster restart)
#   --skip-ollama      Skip Ollama check/pull
#   --no-health-check  Skip post-restart health check
#
# Exit code: 0 on success, 1 on failure.

set -euo pipefail

# ── Help / version ────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Hetzner Load Script

Pulls the latest code, reloads the environment, updates dependencies,
ensures Ollama is running, and restarts the Murphy System service.

Usage:
  $(basename "$0") [OPTIONS]

Options:
  -h, --help         Show this help message and exit
  --version          Show version information
  --skip-deps        Skip pip dependency update (faster restart)
  --skip-ollama      Skip Ollama check/pull
  --no-health-check  Skip post-restart health check

Examples:
  $(basename "$0")                    # Full load: pull code + deps + restart
  $(basename "$0") --skip-deps        # Pull code + restart (skip pip install)
  $(basename "$0") --skip-ollama      # Skip Ollama model check
  $(basename "$0") --no-health-check  # Skip health verification

One-liner (from anywhere on the server):
  bash /opt/Murphy-System/scripts/hetzner_load.sh

EOF
  exit 0
}

# ── Defaults ──────────────────────────────────────────────────────────────────
REPO_DIR="${MURPHY_REPO_DIR:-/opt/Murphy-System}"
SERVICE_NAME="${MURPHY_SERVICE:-murphy-production}"
VENV_DIR="${MURPHY_VENV:-${REPO_DIR}/venv}"
REQUIREMENTS_FILE="${MURPHY_REQUIREMENTS:-${REPO_DIR}/requirements_murphy_1.0.txt}"
OLLAMA_MODEL="${OLLAMA_MODEL:-phi3}"
MURPHY_PORT="${MURPHY_PORT:-8000}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

SKIP_DEPS=false
SKIP_OLLAMA=false
SKIP_HEALTH=false

# ── Parse arguments ───────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    -h|--help)         show_help ;;
    --version)         echo "Murphy System Hetzner Load Script v1.0.0"; exit 0 ;;
    --skip-deps)       SKIP_DEPS=true ;;
    --skip-ollama)     SKIP_OLLAMA=true ;;
    --no-health-check) SKIP_HEALTH=true ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Run '$(basename "$0") --help' for usage." >&2
      exit 1
      ;;
  esac
done

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓ $*${NC}"; }
info() { echo -e "${BLUE}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
fail() { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "  ☠  ════════════════════════════════════════════════  ☠"
echo "       💀  M U R P H Y   H E T Z N E R   L O A D   💀     "
echo "  ☠  ════════════════════════════════════════════════  ☠"
echo ""

# ── 1. Pull latest code ───────────────────────────────────────────────────────
info "Step 1 — Pulling latest code from origin/main ..."
if [ ! -d "$REPO_DIR/.git" ]; then
  fail "Repository not found at ${REPO_DIR}. Set MURPHY_REPO_DIR or clone first."
fi
cd "$REPO_DIR"
git pull origin main
DEPLOY_COMMIT=$(git rev-parse --short HEAD)
ok "Code updated — commit ${DEPLOY_COMMIT}"

# ── 2. Update dependencies ────────────────────────────────────────────────────
if [ "$SKIP_DEPS" = false ]; then
  info "Step 2 — Updating Python dependencies ..."
  if [ -f "${VENV_DIR}/bin/pip" ]; then
    "${VENV_DIR}/bin/pip" install --quiet --upgrade -r "$REQUIREMENTS_FILE"
    ok "Dependencies updated (venv: ${VENV_DIR})"
  elif command -v pip3 &>/dev/null; then
    pip3 install --quiet --upgrade -r "$REQUIREMENTS_FILE"
    ok "Dependencies updated (system pip3)"
  else
    warn "No pip found — skipping dependency update"
  fi
else
  info "Step 2 — Skipping dependency update (--skip-deps)"
fi

# ── 3. Ensure Ollama is installed and running ─────────────────────────────────
if [ "$SKIP_OLLAMA" = false ]; then
  info "Step 3 — Checking Ollama ..."
  if ! command -v ollama &>/dev/null; then
    info "Ollama not found — installing ..."
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama installed"
  fi

  systemctl enable ollama 2>/dev/null || true
  if ! systemctl is-active --quiet ollama; then
    info "Starting Ollama service ..."
    systemctl start ollama
    sleep 3
  fi
  ok "Ollama service running"

  if ! ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL}"; then
    info "Pulling Ollama model: ${OLLAMA_MODEL} ..."
    ollama pull "${OLLAMA_MODEL}"
    ok "Ollama model '${OLLAMA_MODEL}' ready"
  else
    ok "Ollama model '${OLLAMA_MODEL}' already present"
  fi
else
  info "Step 3 — Skipping Ollama check (--skip-ollama)"
fi

# ── 4. Restart Murphy service ─────────────────────────────────────────────────
info "Step 4 — Restarting ${SERVICE_NAME} (commit ${DEPLOY_COMMIT}) ..."
MURPHY_DEPLOY_COMMIT="${DEPLOY_COMMIT}" systemctl restart "${SERVICE_NAME}"
ok "${SERVICE_NAME} restarted"

# ── 5. Health check ───────────────────────────────────────────────────────────
if [ "$SKIP_HEALTH" = false ]; then
  info "Step 5 — Waiting for Murphy to come up ..."
  sleep 5
  if curl -sf "http://localhost:${MURPHY_PORT}/api/health" >/dev/null 2>&1; then
    ok "Murphy health check passed (http://localhost:${MURPHY_PORT}/api/health)"
  else
    warn "Murphy health check failed — check logs with: journalctl -u ${SERVICE_NAME} -n 50"
  fi

  if [ "$SKIP_OLLAMA" = false ]; then
    if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
      ok "Ollama health check passed (http://localhost:${OLLAMA_PORT}/api/tags)"
    else
      warn "Ollama health check failed — check: systemctl status ollama"
    fi
  fi
else
  info "Step 5 — Skipping health check (--no-health-check)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "  ☠  ════════════════════════════════════════════════  ☠"
echo -e "       ${GREEN}💀  MURPHY LOADED — commit ${DEPLOY_COMMIT}  💀${NC}     "
echo "  ☠  ════════════════════════════════════════════════  ☠"
echo ""

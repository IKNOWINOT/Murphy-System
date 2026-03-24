#!/usr/bin/env bash
# scripts/self_setup.sh — Idempotent server setup for Murphy System.
#
# Designed to be run on a fresh or existing Hetzner VPS running Ubuntu.
# Safe to re-run at any time; all steps are idempotent.
#
# Usage:
#   bash scripts/self_setup.sh [--help] [--version] [--dry-run]
#
# Copyright © 2020 Inoni LLC — Creator: Corey Post | License: BSL 1.1

set -euo pipefail

SCRIPT_VERSION="1.0.0"
LOG_FILE="/var/log/murphy-setup.log"
APP_DIR="/opt/Murphy-System"
ENV_DIR="/etc/murphy-production"
VENV_DIR="${APP_DIR}/venv"
SYSTEMD_SRC="${APP_DIR}/config/systemd/murphy-production.service"
SYSTEMD_DEST="/etc/systemd/system/murphy-production.service"
COMPOSE_FILE="${APP_DIR}/docker-compose.hetzner.yml"
DRY_RUN=false

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Self Setup Script v${SCRIPT_VERSION}

Idempotent server setup: installs dependencies, sets up Python venv,
configures systemd, and starts all services.

Usage:
  $(basename "$0") [OPTIONS]

Options:
  -h, --help     Show this help message and exit
  --version      Show version information and exit
  --dry-run      Print what would be done without making changes

Prerequisites:
  • Ubuntu 20.04+ (runs as root or with sudo)
  • /opt/Murphy-System repository cloned
  • /etc/murphy-production/environment written by the deploy workflow

Examples:
  $(basename "$0")           # Full idempotent setup
  $(basename "$0") --dry-run # Preview actions only

EOF
  exit 0
}

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)    show_help ;;
    --version)    echo "Murphy System Self Setup v${SCRIPT_VERSION}"; exit 0 ;;
    --dry-run)    DRY_RUN=true; shift ;;
    *)            echo "Unknown option: $1" >&2; echo "Use --help for usage." >&2; exit 1 ;;
  esac
done

# ── Logging ───────────────────────────────────────────────────────────────────
log() {
  local level="$1"; shift
  local msg="[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [${level}] $*"
  echo "${msg}"
  if [[ "$DRY_RUN" == false ]]; then
    echo "${msg}" >> "${LOG_FILE}" 2>/dev/null || true
  fi
}

info()    { log INFO    "$*"; }
success() { log OK      "$*"; }
warn()    { log WARN    "$*"; }
run_cmd() {
  if [[ "$DRY_RUN" == true ]]; then
    log DRY-RUN "$*"
  else
    info "Running: $*"
    "$@"
  fi
}

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Murphy System — Server Self Setup v${SCRIPT_VERSION}             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
[[ "$DRY_RUN" == true ]] && echo "  *** DRY RUN — no changes will be made ***"
echo ""

# ── 1. Ensure required directories ───────────────────────────────────────────
info "Step 1: Ensuring required directories exist..."
run_cmd mkdir -p "${ENV_DIR}"
run_cmd mkdir -p "${APP_DIR}"
success "Directories OK."

# ── 2. System dependencies ────────────────────────────────────────────────────
info "Step 2: Checking system dependencies..."

install_if_missing() {
  local pkg="$1"
  if dpkg -s "${pkg}" &>/dev/null; then
    info "  ${pkg} already installed — skipping."
  else
    warn "  ${pkg} not found — installing..."
    run_cmd apt-get install -y "${pkg}"
  fi
}

if [[ "$DRY_RUN" == false ]]; then
  apt-get update -q
fi

for pkg in python3 python3-pip python3-venv python3-dev \
           nginx curl git build-essential libpq-dev; do
  install_if_missing "${pkg}"
done

# Docker
if command -v docker &>/dev/null; then
  info "  docker already installed — skipping."
else
  warn "  docker not found — installing via convenience script..."
  if [[ "$DRY_RUN" == false ]]; then
    curl -fsSL https://get.docker.com | sh
  else
    log DRY-RUN "curl -fsSL https://get.docker.com | sh"
  fi
fi

# docker compose (v2 plugin)
if docker compose version &>/dev/null 2>&1; then
  info "  docker compose (v2) already available — skipping."
else
  warn "  docker compose v2 plugin not found — installing..."
  run_cmd apt-get install -y docker-compose-plugin
fi

success "System dependencies OK."

# ── 3. Python virtual environment ─────────────────────────────────────────────
info "Step 3: Setting up Python virtual environment at ${VENV_DIR}..."

if [[ ! -d "${VENV_DIR}" ]]; then
  info "  Creating new venv..."
  run_cmd python3 -m venv "${VENV_DIR}"
else
  info "  Venv already exists — updating pip only."
fi

run_cmd "${VENV_DIR}/bin/pip" install --quiet --upgrade pip

# Prefer requirements_murphy_1.0.txt, fall back to requirements.txt
if [[ -f "${APP_DIR}/requirements_murphy_1.0.txt" ]]; then
  REQS="${APP_DIR}/requirements_murphy_1.0.txt"
elif [[ -f "${APP_DIR}/requirements.txt" ]]; then
  REQS="${APP_DIR}/requirements.txt"
else
  warn "  No requirements file found — skipping pip install."
  REQS=""
fi

if [[ -n "${REQS}" ]]; then
  info "  Installing dependencies from ${REQS}..."
  run_cmd "${VENV_DIR}/bin/pip" install --quiet -r "${REQS}"
fi

success "Python environment OK."

# ── 4. Systemd service ────────────────────────────────────────────────────────
info "Step 4: Installing systemd service..."

if [[ -f "${SYSTEMD_SRC}" ]]; then
  if ! diff -q "${SYSTEMD_SRC}" "${SYSTEMD_DEST}" &>/dev/null; then
    info "  Copying updated systemd service file..."
    run_cmd cp "${SYSTEMD_SRC}" "${SYSTEMD_DEST}"
  else
    info "  Systemd service file unchanged — skipping copy."
  fi
else
  warn "  ${SYSTEMD_SRC} not found — skipping systemd service install."
fi

run_cmd systemctl daemon-reload
success "Systemd OK."

# ── 5. Start / restart murphy-production ──────────────────────────────────────
info "Step 5: Restarting murphy-production service..."
if systemctl is-enabled murphy-production &>/dev/null; then
  run_cmd systemctl restart murphy-production
else
  warn "  murphy-production not enabled — enabling and starting..."
  run_cmd systemctl enable murphy-production
  run_cmd systemctl start murphy-production
fi
success "murphy-production service OK."

# ── 6. Docker containers ──────────────────────────────────────────────────────
info "Step 6: Starting Docker containers..."
if [[ -f "${COMPOSE_FILE}" ]]; then
  run_cmd docker compose -f "${COMPOSE_FILE}" up -d
  success "Docker containers started."
else
  warn "  ${COMPOSE_FILE} not found — skipping docker compose."
fi

# ── 7. Health checks ──────────────────────────────────────────────────────────
info "Step 7: Running health checks..."

if [[ "$DRY_RUN" == false ]]; then
  HEALTH_MAX_RETRIES=12
  HEALTH_DELAY=5
  HEALTH_OK=false
  for i in $(seq 1 ${HEALTH_MAX_RETRIES}); do
    if curl -sf "http://localhost:8000/api/health" &>/dev/null; then
      HEALTH_OK=true
      break
    fi
    info "  Waiting for murphy-production to be healthy (attempt ${i}/${HEALTH_MAX_RETRIES})..."
    sleep ${HEALTH_DELAY}
  done

  if [[ "$HEALTH_OK" == true ]]; then
    success "Health check passed — murphy-production is healthy."
  else
    warn "Health check did not pass within $((HEALTH_MAX_RETRIES * HEALTH_DELAY))s — service may still be starting."
  fi
else
  log DRY-RUN "curl -sf http://localhost:8000/api/health"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Self setup complete!                                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
info "Log file: ${LOG_FILE}"

#!/usr/bin/env bash
# ============================================================================
# Murphy System — ONE-BUTTON RUN
#
# Usage:  bash run.sh
#
# This script does everything needed to launch Murphy in one step:
#   1. Checks Python 3.10+
#   2. Creates a virtual environment (if needed)
#   3. Installs core dependencies (~30 seconds, not the heavy ML stack)
#   4. Generates a minimal .env in development mode
#   5. Starts the production server with ALL features (landing page, forge,
#      deliverable generation, auth, dashboard, etc.)
#   6. Prints the URL to open in your browser
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL 1.1
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${BLUE}ℹ ${NC}$*"; }
ok()    { echo -e "${GREEN}✓ ${NC}$*"; }
warn()  { echo -e "${YELLOW}⚠ ${NC}$*"; }
fail()  { echo -e "${RED}✗ ${NC}$*"; exit 1; }

# ---- locate repo root -------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

if [ ! -f "$REPO_ROOT/murphy_production_server.py" ]; then
    fail "murphy_production_server.py not found. Run this script from the repo root."
fi

# ---- banner ------------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║          💀  Murphy System — One-Button Run  💀              ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ---- 1. Python check --------------------------------------------------------
MIN_PYTHON="3.10"
version_ge() { printf '%s\n%s' "$2" "$1" | sort -V -C; }

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    fail "Python 3.10+ is required. Install from https://python.org/downloads"
fi

PY_VER=$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if ! version_ge "$PY_VER" "$MIN_PYTHON"; then
    fail "Python $MIN_PYTHON+ required (found $PY_VER)."
fi
ok "Python $PY_VER"

# ---- 2. Virtual environment --------------------------------------------------
VENV_DIR="$REPO_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment…"
    $PY -m venv "$VENV_DIR" || fail "Failed to create venv"
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/Scripts/activate"
else
    fail "Cannot activate venv — missing activate script."
fi
ok "Virtual environment active"

# ---- 3. Install dependencies ------------------------------------------------
info "Installing core dependencies (this takes ~30 seconds the first time)…"
pip install --upgrade pip -q 2>/dev/null || true

# Install core deps (fast): just enough to run the server
pip install -q -r "$REPO_ROOT/requirements_core.txt" 2>&1 | grep -v "already satisfied" || true

# Ensure bcrypt is available for auth
pip install -q bcrypt 2>&1 | grep -v "already satisfied" || true

# Ensure starlette middleware is available (comes with fastapi but be explicit)
pip install -q python-multipart 2>&1 | grep -v "already satisfied" || true

ok "Dependencies installed"

# ---- 4. .env configuration --------------------------------------------------
if [ ! -f "$REPO_ROOT/.env" ]; then
    cat > "$REPO_ROOT/.env" <<'ENVEOF'
# Murphy System — Auto-generated .env for development
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=8000
MURPHY_LLM_PROVIDER=local
LOG_LEVEL=INFO
ENVEOF
    ok "Created .env (development mode, onboard LLM — no API key needed)"
else
    ok ".env exists — using your configuration"
fi

# Also ensure Murphy System/ subdir has one (some imports look there)
MURPHY_DIR="$REPO_ROOT/Murphy System"
if [ -d "$MURPHY_DIR" ] && [ ! -f "$MURPHY_DIR/.env" ]; then
    cp "$REPO_ROOT/.env" "$MURPHY_DIR/.env" 2>/dev/null || true
fi

# Create runtime directories
mkdir -p "$REPO_ROOT/logs" "$REPO_ROOT/data" "$REPO_ROOT/.murphy_persistence" 2>/dev/null || true

# ---- 5. Launch ---------------------------------------------------------------
MURPHY_PORT="${MURPHY_PORT:-8000}"

echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓  Ready! Starting Murphy System on port ${MURPHY_PORT}${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Landing Page:${NC}  ${BLUE}http://localhost:${MURPHY_PORT}/${NC}"
echo -e "  ${BOLD}Forge Demo:${NC}    ${BLUE}http://localhost:${MURPHY_PORT}/landing${NC}  (scroll to \"Build Something\")"
echo -e "  ${BOLD}API Docs:${NC}      ${BLUE}http://localhost:${MURPHY_PORT}/docs${NC}  (Swagger interactive docs)"
echo ""
echo -e "  ${CYAN}To test the deliverable forge:${NC}"
echo -e "    1. Open ${BLUE}http://localhost:${MURPHY_PORT}/${NC} in your browser"
echo -e "    2. Scroll to the \"Build Something\" / forge section"
echo -e "    3. Type a query like: ${BOLD}create a compliance automation plan${NC}"
echo -e "    4. Click the Build button and watch the agent swarm work"
echo -e "    5. Download the generated deliverable"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Try to open browser (best-effort, non-blocking)
if command -v xdg-open >/dev/null 2>&1; then
    (sleep 3 && xdg-open "http://localhost:${MURPHY_PORT}/" >/dev/null 2>&1) &
elif command -v open >/dev/null 2>&1; then
    (sleep 3 && open "http://localhost:${MURPHY_PORT}/" >/dev/null 2>&1) &
fi

cd "$REPO_ROOT"
$PY murphy_production_server.py

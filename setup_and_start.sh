#!/usr/bin/env bash
# ============================================================================
# Murphy System — One-Step Setup & Start
#
# Usage (from repo root):
#   bash setup_and_start.sh
#
# Or from any directory:
#   bash /path/to/Murphy-System/setup_and_start.sh
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL 1.1
# ============================================================================
# NOTE: We intentionally do NOT use `set -euo pipefail` here.
# On Windows/MINGW64 (Git Bash), pip writes warnings to stderr which causes
# `pipefail` to treat them as errors, silently killing the script after Step 2.
# All critical failures are caught with explicit `|| fail "..."` guards instead.

# ---- colors ----------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${BLUE}ℹ ${NC}$*"; }
ok()    { echo -e "${GREEN}✓ ${NC}$*"; }
warn()  { echo -e "${YELLOW}⚠ ${NC}$*"; }
fail()  { echo -e "${RED}✗ ${NC}$*"; exit 1; }
step()  { echo -e "\n${CYAN}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"; }

TOTAL_STEPS=5

# ---- banner ----------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║            💀  Murphy System — Setup & Start  💀             ║${NC}"
echo -e "${CYAN}${BOLD}║              One-Step Install & Launch                       ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ---- locate repo root ------------------------------------------------------
# Work whether invoked from the repo root or via an absolute path to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/murphy_system_1.0_runtime.py" ]; then
    REPO_ROOT="$SCRIPT_DIR"
else
    fail "Cannot locate Murphy System files. Run this script from the repository root."
fi

MURPHY_DIR="$REPO_ROOT"

if [ ! -f "$MURPHY_DIR/murphy_system_1.0_runtime.py" ]; then
    fail "murphy_system_1.0_runtime.py not found in '$MURPHY_DIR'.\n   Please run from the Murphy-System repository root."
fi

info "Repository root: $REPO_ROOT"

# ---- step 1: prerequisites -------------------------------------------------
step 1 "Checking prerequisites"

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
    fail "Python $MIN_PYTHON+ required (found $PY_VER). Upgrade at https://python.org/downloads"
fi
ok "Python $PY_VER"

if ! $PY -m pip --version >/dev/null 2>&1; then
    warn "pip not found — attempting bootstrap"
    $PY -m ensurepip --default-pip 2>/dev/null || fail "Cannot find pip. Install it first."
fi
ok "pip available"

# ---- step 2: virtual environment -------------------------------------------
step 2 "Setting up Python virtual environment"

VENV_DIR="$MURPHY_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    info "Reusing existing virtual environment at $VENV_DIR"
else
    info "Creating virtual environment…"
    $PY -m venv "$VENV_DIR"
fi

# Activate – works on POSIX (bin/activate) and MINGW64/Git-Bash on Windows (Scripts/activate)
# shellcheck disable=SC1091
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    fail "Cannot find venv activate script in '$VENV_DIR'."
fi
pip --version >/dev/null 2>&1 || fail "venv activation failed — pip not found in venv"
pip install --upgrade pip -q 2>/dev/null || true
ok "Virtual environment ready and activated"

# ---- step 3: install dependencies ------------------------------------------
step 3 "Installing all dependencies (this may take 1-3 minutes)"

cd "$MURPHY_DIR"

# Install from the comprehensive requirements file first (has everything)
if [ -f requirements_murphy_1.0.txt ]; then
    info "Installing from requirements_murphy_1.0.txt…"
    pip install -q -r requirements_murphy_1.0.txt 2>&1 | grep -v "already satisfied" || true
fi

# Also install from the base requirements.txt if it exists and differs
if [ -f requirements.txt ]; then
    pip install -q -r requirements.txt 2>&1 | grep -v "already satisfied" || true
fi

# Ensure extras that users commonly need are present
pip install -q watchdog matplotlib 2>&1 | grep -v "already satisfied" || true

ok "All dependencies installed"
# NOTE: pip may report dependency conflicts for optional packages (e.g. weasyprint/tinycss2).
# These are non-fatal — Murphy falls back to alternative renderers automatically.

# ---- step 4: configuration -------------------------------------------------
step 4 "Configuring Murphy"

MURPHY_PORT="${MURPHY_PORT:-8000}"

if [ ! -f "$MURPHY_DIR/.env" ]; then
    cat > "$MURPHY_DIR/.env" <<ENVEOF
# Murphy System 1.0 — Auto-generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=${MURPHY_PORT}

# LLM provider — set to 'groq', 'openai', or 'anthropic' once you add a key below
# Defaults to 'local' (onboard LLM, no API key required)
MURPHY_LLM_PROVIDER=local

# The onboard LLM works without any API key.
# Add an external key below for enhanced quality (optional).
# GROQ_API_KEY=gsk_your_key_here
ENVEOF
    ok "Created default .env (onboard LLM active — no key required)"
else
    ok ".env already exists — keeping your configuration"
fi

# Create runtime directories
mkdir -p logs data modules sessions repositories .murphy_persistence/images
ok "Runtime directories ready"

# ---- step 5: launch --------------------------------------------------------
step 5 "Ready to start Murphy System"

echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓  All requirements installed${NC}"
echo -e "${GREEN}${BOLD}  ✓  Virtual environment activated${NC}"
echo -e "${GREEN}${BOLD}  ✓  Configuration ready${NC}"
echo -e "${GREEN}${BOLD}  ✓  Ready to run!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}API Docs:${NC}    ${BLUE}http://localhost:${MURPHY_PORT}/docs${NC}"
echo -e "  ${BOLD}Health:${NC}      ${BLUE}http://localhost:${MURPHY_PORT}/api/health${NC}"
echo -e "  ${BOLD}Status:${NC}      ${BLUE}http://localhost:${MURPHY_PORT}/api/status${NC}"
echo ""

# Determine Unified Terminal URL (primary multi-role hub, absolute file path)
TERMINAL_HTML="$MURPHY_DIR/terminal_unified.html"
if [ ! -f "$TERMINAL_HTML" ]; then
    # Fall back to Architect Terminal if Unified Terminal is not present
    TERMINAL_HTML="$MURPHY_DIR/terminal_architect.html"
fi
if [ -f "$TERMINAL_HTML" ]; then
    # Encode spaces for display; other special characters are rare in typical
    # repository paths and the URL is informational only (not machine-processed).
    TERMINAL_URL="file://$(printf '%s' "$TERMINAL_HTML" | sed 's| |%20|g')"
else
    TERMINAL_URL="http://localhost:${MURPHY_PORT}/docs"
fi

# Offer choice: backend server vs terminal UI
if [ -f "$MURPHY_DIR/murphy_terminal.py" ]; then
    echo -e "${CYAN}How would you like to start Murphy?${NC}"
    echo -e "  ${BOLD}1)${NC} Start backend server  (API + all web dashboards in browser)"
    echo -e "  ${BOLD}2)${NC} Start terminal UI     (interactive natural-language terminal in shell)"
    echo ""
    read -r -p "Enter choice [1]: " LAUNCH_CHOICE
    LAUNCH_CHOICE="${LAUNCH_CHOICE:-1}"
else
    LAUNCH_CHOICE="1"
fi

echo ""
cd "$MURPHY_DIR"

# Helper: health-check retry loop — waits up to 30 seconds for backend to be ready
_wait_for_backend() {
    local port="$1"
    local retries=10
    local delay=3
    info "Waiting for backend on port ${port}…"
    for i in $(seq 1 $retries); do
        if curl -sf "http://localhost:${port}/api/health" >/dev/null 2>&1; then
            ok "Backend is up at http://localhost:${port}"
            return 0
        fi
        sleep "$delay"
    done
    warn "Backend did not respond within $((retries * delay))s — it may still be starting up"
    return 1
}

case "$LAUNCH_CHOICE" in
    2)
        echo -e "${CYAN}🚀 Launching Murphy Terminal UI…${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""
        $PY murphy_terminal.py
        ;;
    *)
        echo -e "${CYAN}🚀 Starting Murphy System backend on port ${MURPHY_PORT}…${NC}"
        echo -e "${GREEN}${BOLD}→ Open the Unified Terminal (Admin / Multi-role hub) in your browser:${NC}"
        echo -e "  ${BLUE}${TERMINAL_URL}${NC}"
        echo -e "${GREEN}→ Other web interfaces (role-specific terminals, canvas, visualiser, etc.):${NC}"
        echo -e "  ${BLUE}file://$(printf '%s' "$MURPHY_DIR" | sed 's| |%20|g')/murphy_landing_page.html${NC}"
        echo -e "  ${BLUE}file://$(printf '%s' "$MURPHY_DIR" | sed 's| |%20|g')/terminal_architect.html${NC}"
        echo -e "  ${BLUE}http://localhost:${MURPHY_PORT}/docs${NC}  (Swagger API docs)"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""
        $PY murphy_system_1.0_runtime.py &
        _BACKEND_PID=$!
        _wait_for_backend "${MURPHY_PORT}" || true
        wait "$_BACKEND_PID"
        ;;
esac

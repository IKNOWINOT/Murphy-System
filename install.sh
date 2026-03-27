#!/usr/bin/env bash
# ============================================================================
# Murphy System — One-Line Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash
#
# Or with a custom install directory:
#   curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash -s -- /opt/murphy
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
# ============================================================================
# ============================================================================
# SECURITY NOTE: Always inspect scripts before piping to bash.
# To review first:  curl -fsSL <URL> -o install.sh && less install.sh && bash install.sh
# ============================================================================
set -euo pipefail

# ---- configuration ---------------------------------------------------------
REPO="IKNOWINOT/Murphy-System"
BRANCH="main"
INSTALL_DIR="${1:-$HOME/murphy-system}"
MURPHY_PORT="${MURPHY_PORT:-8000}"
MIN_PYTHON="3.10"

# ---- colours ---------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

banner() {
cat <<'EOF'

  ███╗   ███╗██╗   ██╗██████╗ ██████╗ ██╗  ██╗██╗   ██╗
  ████╗ ████║██║   ██║██╔══██╗██╔══██╗██║  ██║╚██╗ ██╔╝
  ██╔████╔██║██║   ██║██████╔╝██████╔╝███████║ ╚████╔╝
  ██║╚██╔╝██║██║   ██║██╔══██╗██╔═══╝ ██╔══██║  ╚██╔╝
  ██║ ╚═╝ ██║╚██████╔╝██║  ██║██║     ██║  ██║   ██║
  ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝   ╚═╝
  Universal AI Automation System — One-Line Installer

EOF
}

info()  { echo -e "${BLUE}ℹ ${NC}$*"; }
ok()    { echo -e "${GREEN}✓ ${NC}$*"; }
warn()  { echo -e "${YELLOW}⚠ ${NC}$*"; }
fail()  { echo -e "${RED}✗ ${NC}$*"; exit 1; }
step()  { echo -e "\n${CYAN}[$1/6]${NC} ${BOLD}$2${NC}"; }

# ---- helpers ---------------------------------------------------------------
version_ge() {               # $1 >= $2  (semver-lite)
  printf '%s\n%s' "$2" "$1" | sort -V -C
}

command_exists() { command -v "$1" >/dev/null 2>&1; }

# ---- pre-flight checks ----------------------------------------------------
banner

step 1 "Checking prerequisites"

# Python
if command_exists python3; then
  PY=python3
elif command_exists python; then
  PY=python
else
  fail "Python 3.10+ is required. Install from https://python.org/downloads"
fi

PY_VER=$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if ! version_ge "$PY_VER" "$MIN_PYTHON"; then
  fail "Python $MIN_PYTHON+ required (found $PY_VER). Upgrade at https://python.org/downloads"
fi
ok "Python $PY_VER"

# pip
if ! $PY -m pip --version >/dev/null 2>&1; then
  warn "pip not found — attempting bootstrap"
  $PY -m ensurepip --default-pip 2>/dev/null || fail "Cannot find pip. Install it first."
fi
ok "pip available"

# git (needed for clone)
if ! command_exists git; then
  fail "git is required. Install it: https://git-scm.com/downloads"
fi
ok "git available"

# ---- download --------------------------------------------------------------
step 2 "Downloading Murphy System"

if [ -d "$INSTALL_DIR/Murphy System" ]; then
  warn "Existing installation found at $INSTALL_DIR"
  info "Pulling latest changes…"
  (cd "$INSTALL_DIR" && git pull --ff-only 2>/dev/null) || true
else
  info "Cloning repository → ${INSTALL_DIR}"
  git clone --depth 1 -b "$BRANCH" "https://github.com/${REPO}.git" "$INSTALL_DIR" 2>&1 | tail -1
fi
ok "Murphy System downloaded to ${INSTALL_DIR}"

# ---- virtual-env -----------------------------------------------------------
step 3 "Setting up Python environment"

VENV_DIR="$INSTALL_DIR/murphy_system/venv"
if [ ! -d "$VENV_DIR" ]; then
  $PY -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q 2>/dev/null
ok "Virtual environment ready"

# ---- dependencies ----------------------------------------------------------
step 4 "Installing dependencies (this may take 1-2 minutes)"

cd "$INSTALL_DIR/Murphy System"
pip install -q fastapi uvicorn pydantic aiohttp httpx rich pyyaml python-dotenv 2>&1 | \
  grep -v "already satisfied" || true

# Install from requirements if present
if [ -f requirements_murphy_1.0.txt ]; then
  pip install -q -r requirements_murphy_1.0.txt 2>&1 | \
    grep -v "already satisfied" || true
fi

# Install the murphy-system package in editable mode so that
# "from src.xxx import yyy" imports work correctly without sys.path hacks.
pip install -q -e . 2>&1 | grep -v "already satisfied" || true

ok "Dependencies installed"

# ---- configuration ---------------------------------------------------------
step 5 "Configuring Murphy"

if [ ! -f .env ]; then
  cat > .env <<ENVEOF
# Murphy System 1.0 — Auto-generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=${MURPHY_PORT}

# The onboard LLM works without any API key.
# Add an external key below for enhanced quality (optional).
# GROQ_API_KEY=gsk_your_key_here
ENVEOF
  ok "Created default .env  (onboard LLM active — no key required)"
else
  ok ".env already exists — keeping your configuration"
fi

# Create runtime directories
mkdir -p logs data modules sessions repositories .murphy_persistence/images
ok "Runtime directories ready"

# ---- CLI wrapper -----------------------------------------------------------
step 6 "Installing 'murphy' CLI"

CLI_BIN="$INSTALL_DIR/murphy_system/murphy"
cat > "$CLI_BIN" <<'CLIFEOF'
#!/usr/bin/env bash
# Murphy System CLI — quick commands
set -euo pipefail

MURPHY_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$MURPHY_DIR"

# Activate venv if present
if [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# Load .env
if [ -f .env ]; then
  set -a; source .env 2>/dev/null; set +a
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

usage() {
cat <<USAGE
${CYAN}Murphy System 1.0 — CLI${NC}

${BOLD}USAGE${NC}
  murphy <command> [options]

${BOLD}COMMANDS${NC}
  ${GREEN}start${NC}       Start Murphy System (port ${MURPHY_PORT:-8000})
  ${GREEN}stop${NC}        Stop Murphy System
  ${GREEN}status${NC}      Check if Murphy is running
  ${GREEN}health${NC}      Query /api/health
  ${GREEN}info${NC}        Show system info
  ${GREEN}logs${NC}        Tail Murphy logs
  ${GREEN}update${NC}      Pull latest version
  ${GREEN}help${NC}        Show this help

${BOLD}EXAMPLES${NC}
  murphy start          # Start in foreground
  murphy start -d       # Start in background (daemon)
  murphy status         # Check health
  murphy stop           # Stop background daemon
USAGE
}

case "${1:-help}" in
  start)
    shift
    DAEMON=false
    if [[ "${1:-}" == "-d" || "${1:-}" == "--daemon" ]]; then
      DAEMON=true
    fi
    echo -e "${CYAN}🚀 Starting Murphy System 1.0 on port ${MURPHY_PORT:-8000}…${NC}"
    if $DAEMON; then
      nohup python3 murphy_system_1.0_runtime.py > logs/murphy.log 2>&1 &
      echo $! > .murphy.pid
      sleep 2
      if kill -0 "$(cat .murphy.pid)" 2>/dev/null; then
        echo -e "${GREEN}✓ Murphy running in background (PID $(cat .murphy.pid))${NC}"
        echo -e "  Logs: ${BLUE}tail -f $MURPHY_DIR/logs/murphy.log${NC}"
        echo -e "  API:  ${BLUE}http://localhost:${MURPHY_PORT:-8000}/docs${NC}"
      else
        echo -e "${RED}✗ Failed to start. Check logs/murphy.log${NC}"
        exit 1
      fi
    else
      echo -e "  API Docs:  ${BLUE}http://localhost:${MURPHY_PORT:-8000}/docs${NC}"
      echo -e "  Health:    ${BLUE}http://localhost:${MURPHY_PORT:-8000}/api/health${NC}"
      echo -e "  Status:    ${BLUE}http://localhost:${MURPHY_PORT:-8000}/api/status${NC}"
      echo ""
      python3 murphy_system_1.0_runtime.py
    fi
    ;;
  stop)
    if [ -f .murphy.pid ]; then
      PID=$(cat .murphy.pid)
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm -f .murphy.pid
        echo -e "${GREEN}✓ Murphy stopped (PID $PID)${NC}"
      else
        rm -f .murphy.pid
        echo -e "${YELLOW}⚠ Process already stopped${NC}"
      fi
    else
      echo -e "${YELLOW}⚠ No PID file found. Murphy may not be running.${NC}"
    fi
    ;;
  status)
    PORT="${MURPHY_PORT:-8000}"
    if curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
      RESP=$(curl -sf "http://localhost:$PORT/api/health")
      echo -e "${GREEN}✓ Murphy is running on port $PORT${NC}"
      echo "  $RESP"
    else
      echo -e "${YELLOW}⚠ Murphy is not responding on port $PORT${NC}"
      if [ -f .murphy.pid ] && kill -0 "$(cat .murphy.pid)" 2>/dev/null; then
        echo -e "  Process is alive (PID $(cat .murphy.pid)) — may still be starting"
      fi
    fi
    ;;
  health)
    PORT="${MURPHY_PORT:-8000}"
    curl -sf "http://localhost:$PORT/api/health" 2>/dev/null | python3 -m json.tool 2>/dev/null || \
      echo -e "${RED}✗ Cannot reach http://localhost:$PORT/api/health${NC}"
    ;;
  info)
    PORT="${MURPHY_PORT:-8000}"
    curl -sf "http://localhost:$PORT/api/info" 2>/dev/null | python3 -m json.tool 2>/dev/null || \
      echo -e "${RED}✗ Cannot reach http://localhost:$PORT/api/info${NC}"
    ;;
  logs)
    if [ -f logs/murphy.log ]; then
      tail -f logs/murphy.log
    else
      echo -e "${YELLOW}⚠ No log file yet. Start Murphy first.${NC}"
    fi
    ;;
  update)
    echo -e "${BLUE}Pulling latest Murphy System…${NC}"
    cd "$MURPHY_DIR/.."
    git pull --ff-only
    cd "$MURPHY_DIR"
    pip install -q -r requirements_murphy_1.0.txt 2>/dev/null || true
    echo -e "${GREEN}✓ Updated to latest version${NC}"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo -e "${RED}Unknown command: $1${NC}"
    usage
    exit 1
    ;;
esac
CLIFEOF

chmod +x "$CLI_BIN"

# Create symlink in a PATH-visible location
LINK_DIR="$HOME/.local/bin"
mkdir -p "$LINK_DIR"
ln -sf "$CLI_BIN" "$LINK_DIR/murphy" 2>/dev/null || true

ok "CLI installed — run ${BOLD}murphy help${NC} to see commands"

# ---- done! -----------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓  Murphy System installed successfully!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Install location:${NC}  $INSTALL_DIR/Murphy System"
echo -e "  ${BOLD}Start Murphy:${NC}      ${CYAN}murphy start${NC}"
echo -e "  ${BOLD}Start as daemon:${NC}   ${CYAN}murphy start -d${NC}"
echo -e "  ${BOLD}Check status:${NC}      ${CYAN}murphy status${NC}"
echo -e "  ${BOLD}View help:${NC}         ${CYAN}murphy help${NC}"
echo ""
echo -e "  ${BOLD}API Documentation:${NC} ${BLUE}http://localhost:${MURPHY_PORT}/docs${NC}"
echo -e "  ${BOLD}Health Check:${NC}      ${BLUE}http://localhost:${MURPHY_PORT}/api/health${NC}"
echo ""
echo -e "  ${YELLOW}Note:${NC} The onboard LLM works out of the box — no API key needed."
echo -e "  ${YELLOW}Tip:${NC}  Add ~/.local/bin to your PATH if 'murphy' isn't found:"
echo -e "        ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
echo ""
echo -e "  ${GREEN}Happy automating! 🚀${NC}"
echo ""

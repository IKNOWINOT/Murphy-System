#!/usr/bin/env bash
# ==============================================================================
# Murphy System — Runtime Mode Switcher
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL 1.1
#
# Usage:
#   bash scripts/switch_runtime.sh tiered
#   bash scripts/switch_runtime.sh monolith
#
# This script updates MURPHY_RUNTIME_MODE in .env (or creates a minimal .env)
# and explains the implications of each mode.
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${BLUE}ℹ ${NC}$*"; }
ok()    { echo -e "${GREEN}✓ ${NC}$*"; }
warn()  { echo -e "${YELLOW}⚠ ${NC}$*"; }
fail()  { echo -e "${RED}✗ ${NC}$*"; exit 1; }

# ── Locate repo root ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# ── Usage check ──────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Runtime Mode Switcher

Switches between monolith and tiered runtime modes for the Murphy System.

Usage:
  $(basename "$0") [OPTIONS] <mode>

Arguments:
  mode    Runtime mode: 'monolith' or 'tiered'

Options:
  -h, --help     Show this help message and exit
  --version      Show version information
  --dry-run      Show what would change without making changes

Modes:
  monolith    All modules loaded at startup (default, safe fallback)
              • Higher memory usage but maximum compatibility
              • The original, proven boot path

  tiered      On-demand module loading based on team capabilities
              • Only modules needed by your team profile are loaded
              • Memory footprint is significantly reduced
              • Falls back to monolith if boot fails
              • Requires: src/runtime/tiered_orchestrator.py

Examples:
  $(basename "$0") monolith         # Switch to monolith mode
  $(basename "$0") tiered           # Switch to tiered mode
  $(basename "$0") --dry-run tiered # Preview tiered switch
  $(basename "$0") --help           # Show this help

After switching:
  Restart the server to apply: python -m src.runtime.boot

EOF
  exit 0
}

# Handle help/version before mode check
case "${1:-}" in
  -h|--help)
    show_help
    ;;
  --version)
    echo "Murphy System Runtime Switcher v1.0.0"
    exit 0
    ;;
esac

if [ $# -ne 1 ]; then
    echo -e "${CYAN}${BOLD}Murphy System — Runtime Mode Switcher${NC}"
    echo ""
    echo "  Usage: bash scripts/switch_runtime.sh <mode>"
    echo ""
    echo "  Modes:"
    echo "    monolith   All modules loaded at startup (default, safe fallback)"
    echo "    tiered     On-demand module loading based on team capabilities"
    echo ""
    echo "  Use --help for more information"
    # Show current mode if .env exists
    if [ -f "$ENV_FILE" ]; then
        CURRENT=$(grep -E '^MURPHY_RUNTIME_MODE=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || echo "monolith")
        echo -e "  Current mode: ${BOLD}${CURRENT:-monolith}${NC}"
    fi
    exit 1
fi

NEW_MODE="${1,,}"  # lowercase

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ "$NEW_MODE" != "monolith" && "$NEW_MODE" != "tiered" ]]; then
    fail "Unknown mode '$NEW_MODE'. Choose 'monolith' or 'tiered'."
fi

# ── Show banner ───────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║        Murphy System — Runtime Mode Switcher             ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Current mode ─────────────────────────────────────────────────────────────
CURRENT_MODE="monolith"
if [ -f "$ENV_FILE" ]; then
    CURRENT_MODE=$(grep -E '^MURPHY_RUNTIME_MODE=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || echo "monolith")
    CURRENT_MODE="${CURRENT_MODE:-monolith}"
fi

info "Current mode : ${BOLD}${CURRENT_MODE}${NC}"
info "Switching to : ${BOLD}${NEW_MODE}${NC}"
echo ""

if [ "$CURRENT_MODE" = "$NEW_MODE" ]; then
    ok "Already in ${NEW_MODE} mode — no change needed."
    exit 0
fi

# ── Mode-specific warnings ────────────────────────────────────────────────────
if [ "$NEW_MODE" = "tiered" ]; then
    echo -e "${YELLOW}${BOLD}What tiered mode means:${NC}"
    echo "  • Only modules needed by your team profile are loaded at startup."
    echo "  • Memory footprint is significantly reduced."
    echo "  • If boot fails for any reason, the system falls back to monolith automatically."
    echo "  • You can manually load/unload packs via:"
    echo "      POST /api/runtime/packs/{name}/load"
    echo "      POST /api/runtime/packs/{name}/unload"
    echo "  • To define which capabilities your team needs, create:"
    echo "      data/team_profile.json  with a 'capabilities' list."
    echo ""
    warn "Make sure src/runtime/tiered_orchestrator.py and runtime_packs/registry.py"
    warn "are present. If not, the system will fall back to monolith."
else
    echo -e "${YELLOW}${BOLD}What monolith mode means:${NC}"
    echo "  • All modules are loaded at startup."
    echo "  • Higher memory usage but maximum compatibility."
    echo "  • The original, proven boot path."
    echo ""
fi

# ── Update .env ───────────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    warn ".env not found — creating minimal .env"
    echo "MURPHY_RUNTIME_MODE=${NEW_MODE}" > "$ENV_FILE"
    ok "Created $ENV_FILE with MURPHY_RUNTIME_MODE=${NEW_MODE}"
elif grep -qE '^MURPHY_RUNTIME_MODE=' "$ENV_FILE"; then
    # Replace existing line (portable sed for Linux & macOS)
    sed -i.bak "s|^MURPHY_RUNTIME_MODE=.*|MURPHY_RUNTIME_MODE=${NEW_MODE}|" "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
    ok "Updated MURPHY_RUNTIME_MODE=${NEW_MODE} in .env"
else
    echo "" >> "$ENV_FILE"
    echo "MURPHY_RUNTIME_MODE=${NEW_MODE}" >> "$ENV_FILE"
    ok "Added MURPHY_RUNTIME_MODE=${NEW_MODE} to .env"
fi

echo ""
ok "Switch complete. ${BOLD}Restart the server to apply the new runtime mode.${NC}"
echo ""
echo -e "  To start:  ${CYAN}python -m src.runtime.boot${NC}"
echo -e "  To revert: ${CYAN}bash scripts/switch_runtime.sh ${CURRENT_MODE}${NC}"
echo ""

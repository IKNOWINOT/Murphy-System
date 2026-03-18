#!/usr/bin/env bash
# ==============================================================================
# Murphy System — Runtime Status Diagnostic
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL 1.1
#
# Usage:
#   bash scripts/runtime_status.sh
#   bash scripts/runtime_status.sh --port 9000
#
# Shows:
#   • Configured runtime mode (from .env or environment)
#   • In tiered mode: loaded vs unloaded packs
#   • Memory usage estimate (monolith vs tiered)
#   • Live health endpoint response (if server is running)
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${BLUE}ℹ ${NC}$*"; }
ok()    { echo -e "${GREEN}✓ ${NC}$*"; }
warn()  { echo -e "${YELLOW}⚠ ${NC}$*"; }
err()   { echo -e "${RED}✗ ${NC}$*"; }

# ── Parse args ────────────────────────────────────────────────────────────────
PORT="${MURPHY_PORT:-8000}"
while [[ $# -gt 0 ]]; do
    case $1 in
        --port|-p) PORT="$2"; shift 2 ;;
        *) echo "Usage: $0 [--port PORT]"; exit 1 ;;
    esac
done

# ── Locate repo root ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║        Murphy System — Runtime Status                    ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Read .env ────────────────────────────────────────────────────────────────
RUNTIME_MODE="monolith"
if [ -f "$ENV_FILE" ]; then
    # Source safely: only export MURPHY_* variables
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^MURPHY_ ]] && export "$key"="${value}" 2>/dev/null || true
    done < <(grep -E '^MURPHY_' "$ENV_FILE" || true)
    RUNTIME_MODE="${MURPHY_RUNTIME_MODE:-monolith}"
fi

echo -e "  Runtime mode : ${BOLD}${RUNTIME_MODE}${NC}"
echo -e "  Config file  : ${ENV_FILE}"
echo ""

# ── Mode description ──────────────────────────────────────────────────────────
if [ "$RUNTIME_MODE" = "tiered" ]; then
    echo -e "  ${CYAN}Tiered mode${NC}: modules are loaded on-demand based on team capabilities."
    echo "  Memory footprint is reduced — only needed packs are active."

    # Check team profile
    PROFILE_PATH="$REPO_ROOT/data/team_profile.json"
    if [ -f "$PROFILE_PATH" ]; then
        ok "Team profile found: $PROFILE_PATH"
        if command -v python3 &>/dev/null; then
            CAPS=$(python3 -c "
import json, sys
try:
    d = json.load(open('$PROFILE_PATH'))
    caps = d.get('capabilities', [])
    print(', '.join(caps) if caps else '(none)')
except Exception as e:
    print('(could not parse: ' + str(e) + ')')
" 2>/dev/null || echo "(python3 unavailable)")
            info "Requested capabilities: ${CAPS}"
        fi
    else
        warn "No team profile at data/team_profile.json — all packs will be loaded."
        warn "Create that file with a 'capabilities' list to enable selective loading."
    fi

    echo ""
    # Memory estimate
    echo -e "  ${BOLD}Memory estimate (rough):${NC}"
    echo "    Monolith  : ~2 GB (all modules loaded)"
    echo "    Tiered    : ~200–500 MB (depending on active packs)"
    echo ""
else
    echo -e "  ${CYAN}Monolith mode${NC}: all modules loaded at startup."
    echo "  Maximum compatibility — the original proven boot path."
    echo ""
    echo -e "  ${BOLD}Memory estimate (rough):${NC}"
    echo "    Monolith  : ~2 GB (all modules loaded)"
    echo ""
    info "To switch to tiered mode: bash scripts/switch_runtime.sh tiered"
fi

# ── Live server check ─────────────────────────────────────────────────────────
echo -e "  ${BOLD}Live server check (http://localhost:${PORT}):${NC}"

if command -v curl &>/dev/null; then
    HTTP_RESPONSE=$(curl -s -o /tmp/_murphy_health.json -w "%{http_code}" \
        --connect-timeout 3 --max-time 5 \
        "http://localhost:${PORT}/api/health" 2>/dev/null || echo "000")

    if [ "$HTTP_RESPONSE" = "200" ]; then
        ok "Server is responding (HTTP ${HTTP_RESPONSE})"
        HEALTH_BODY=$(cat /tmp/_murphy_health.json 2>/dev/null || echo "")
        if [ -n "$HEALTH_BODY" ]; then
            info "Health response: ${HEALTH_BODY}"
        fi

        # In tiered mode, also query /api/runtime/packs
        if [ "$RUNTIME_MODE" = "tiered" ]; then
            echo ""
            PACKS_RESPONSE=$(curl -s -o /tmp/_murphy_packs.json -w "%{http_code}" \
                --connect-timeout 3 --max-time 5 \
                "http://localhost:${PORT}/api/runtime/packs" 2>/dev/null || echo "000")
            if [ "$PACKS_RESPONSE" = "200" ]; then
                echo -e "  ${BOLD}Pack status:${NC}"
                if command -v python3 &>/dev/null; then
                    python3 -c "
import json, sys
try:
    d = json.load(open('/tmp/_murphy_packs.json'))
    packs = d.get('packs', {})
    for name, info in sorted(packs.items()):
        status = info.get('status', '?')
        symbol = '✓' if status == 'loaded' else ('✗' if status == 'failed' else '○')
        print(f'    {symbol} {name:20s}  [{status}]')
except Exception as e:
    print('    (could not parse response: ' + str(e) + ')')
" 2>/dev/null || cat /tmp/_murphy_packs.json
                fi
            else
                warn "Could not reach /api/runtime/packs (HTTP ${PACKS_RESPONSE})"
            fi
        fi
    elif [ "$HTTP_RESPONSE" = "000" ]; then
        warn "Server is NOT running on port ${PORT}."
        info "Start it with: python -m src.runtime.boot"
    else
        warn "Server returned HTTP ${HTTP_RESPONSE} on /api/health"
    fi
else
    warn "curl not available — skipping live check."
fi

echo ""
echo -e "  ${BOLD}Switch runtime mode:${NC}"
echo "    bash scripts/switch_runtime.sh monolith"
echo "    bash scripts/switch_runtime.sh tiered"
echo ""

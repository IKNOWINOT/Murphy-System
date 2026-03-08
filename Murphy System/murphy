#!/usr/bin/env bash
# Murphy System CLI — quick commands
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
set -euo pipefail
MURPHY_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$MURPHY_DIR"
[ -f venv/bin/activate ] && source venv/bin/activate 2>/dev/null || true
[ -f .env ] && { set -a; source .env 2>/dev/null; set +a; } || true
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
usage() {
  echo ""
  echo -e "${CYAN}Murphy System 1.0 — CLI${NC}"
  echo ""
  echo -e "${BOLD}USAGE${NC}"
  echo "  murphy <command> [options]"
  echo ""
  echo -e "${BOLD}COMMANDS${NC}"
  echo -e "  ${GREEN}start${NC}       Start Murphy System (port ${MURPHY_PORT:-8000})"
  echo -e "  ${GREEN}stop${NC}        Stop Murphy System"
  echo -e "  ${GREEN}status${NC}      Check if Murphy is running"
  echo -e "  ${GREEN}health${NC}      Query /api/health"
  echo -e "  ${GREEN}info${NC}        Show system info"
  echo -e "  ${GREEN}logs${NC}        Tail Murphy logs"
  echo -e "  ${GREEN}update${NC}      Pull latest version"
  echo -e "  ${GREEN}help${NC}        Show this help"
  echo ""
  echo -e "${BOLD}EXAMPLES${NC}"
  echo "  murphy start          # Start in foreground"
  echo "  murphy start -d       # Start in background (daemon)"
  echo "  murphy status         # Check health"
  echo "  murphy stop           # Stop background daemon"
  echo ""
}
case "${1:-help}" in
  start)
    shift || true
    DAEMON=false
    [[ "${1:-}" == "-d" || "${1:-}" == "--daemon" ]] && DAEMON=true
    echo -e "${CYAN}🚀 Starting Murphy System 1.0 on port ${MURPHY_PORT:-8000}…${NC}"
    if $DAEMON; then
      mkdir -p logs
      nohup python3 murphy_system_1.0_runtime.py > logs/murphy.log 2>&1 &
      BGPID=$!
      echo "$BGPID" > .murphy.pid
      sleep 3
      if ps -p "$BGPID" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Murphy running in background (PID $BGPID)${NC}"
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
      MPID=$(cat .murphy.pid)
      if ps -p "$MPID" > /dev/null 2>&1; then
        kill "$MPID" 2>/dev/null || true
        rm -f .murphy.pid
        echo -e "${GREEN}✓ Murphy stopped (PID $MPID)${NC}"
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
    [ -f logs/murphy.log ] && tail -f logs/murphy.log || \
      echo -e "${YELLOW}⚠ No log file yet. Start Murphy first.${NC}"
    ;;
  update)
    echo -e "${BLUE}Pulling latest Murphy System…${NC}"
    (cd "$MURPHY_DIR/.." && git pull --ff-only 2>/dev/null) || true
    pip install -q -r requirements_murphy_1.0.txt 2>/dev/null || true
    echo -e "${GREEN}✓ Updated to latest version${NC}"
    ;;
  help|--help|-h) usage ;;
  *) echo -e "${RED}Unknown command: $1${NC}"; usage; exit 1 ;;
esac

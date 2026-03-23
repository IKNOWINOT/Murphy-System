#!/usr/bin/env bash
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Hetzner Full-Stack Load Script
#
# Brings up the COMPLETE Murphy production environment on the Hetzner server,
# including every subsystem and the glue (nginx, env file) that ties them
# together into a single working platform.
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  WHAT THIS SCRIPT STARTS                                                │
# │                                                                         │
# │  ① Code & deps    git pull + pip install (latest code & packages)      │
# │                                                                         │
# │  ② Environment    Audit /etc/murphy-production/environment:             │
# │                   DATABASE_URL, REDIS_URL, OLLAMA_HOST,                 │
# │                   SMTP_HOST, MATRIX_HOMESERVER_URL, MURPHY_SECRET_KEY   │
# │                                                                         │
# │  ③ Nginx          Reverse proxy / TLS termination                       │
# │                   Routes all traffic into one URL space:                │
# │                   /  + /ui/ + /static/ → Murphy API :8000              │
# │                   /api/                → Murphy API :8000              │
# │                   /grafana/            → Grafana      :3000            │
# │                   /mail/               → Roundcube    :8443            │
# │                   /metrics             → Murphy API   :8000            │
# │                                                                         │
# │  ④ Onboard LLM    ollama (systemd) — phi3 / llama3                    │
# │                                                                         │
# │  ⑤ Docker stack   docker compose up -d (all containers):               │
# │                   • murphy-postgres  PostgreSQL      :5432              │
# │                   • murphy-redis     Redis           :6379              │
# │                   • murphy-prometheus Prometheus     :9090              │
# │                   • murphy-grafana   Grafana         :3000              │
# │                   • murphy-mailserver Postfix+Dovecot :25/:587/:993     │
# │                   • murphy-webmail   Roundcube       :8443              │
# │                                                                         │
# │  ⑥ Mail setup     scripts/mail_setup.sh (mailbox provisioning)         │
# │                                                                         │
# │  ⑦ Murphy app     murphy-production (systemd) — FastAPI + StaticFiles  │
# │                   Serves:                                               │
# │                   • REST API  (/api/*)                                  │
# │                   • Website   (/ui/* + /static/* + murphy_landing_page) │
# │                   • Matrix IM bridge (runs inside Murphy process)       │
# │                   • Slack / Twilio IM integrations (runs inside Murphy) │
# │                   • Metrics  (/metrics)                                 │
# │                                                                         │
# │  ⑧ Health checks  Every subsystem verified before exit                 │
# └─────────────────────────────────────────────────────────────────────────┘
#
# Run on the Hetzner box as root (or a user with systemctl + docker rights):
#
#   bash /opt/Murphy-System/scripts/hetzner_load.sh
#
# Exit code: 0 on success, 1 on critical failure.

set -euo pipefail

# ── Help / version ────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Hetzner Full-Stack Load Script

Brings the COMPLETE Murphy production environment up-to-date and running.
Covers every subsystem — LLM, database, cache, mail, IM, monitoring,
the website, and the nginx glue that links them all together.

Usage:
  $(basename "$0") [OPTIONS]

Options:
  -h, --help           Show this help message and exit
  --version            Show version information
  --skip-pull          Skip git pull (use current code on disk)
  --skip-deps          Skip pip dependency update (faster restart)
  --skip-env-audit     Skip environment file completeness check
  --skip-nginx         Skip nginx vhost check and reload
  --skip-ollama        Skip Ollama (onboard LLM) check/pull
  --skip-docker        Skip Docker Compose services
  --skip-mail-setup    Skip post-boot mailbox provisioning
  --no-health-check    Skip post-start health checks

What gets started (in order):
  1. git pull origin main
  2. pip install --upgrade (Python dependencies)
  3. Environment file audit (warn on missing connection vars)
  4. nginx  — reverse proxy / TLS / website routing
  5. ollama — onboard LLM  (systemd)
  6. docker compose up -d  — postgres, redis, prometheus, grafana,
                             murphy-mailserver (Postfix+Dovecot),
                             murphy-webmail (Roundcube)
  7. scripts/mail_setup.sh — mailbox provisioning
  8. murphy-production     — Murphy app (systemd):
                             REST API, website, Matrix IM bridge,
                             Slack/Twilio integrations, metrics
  9. Health checks on every subsystem

Environment overrides:
  MURPHY_REPO_DIR      Repo path             (default: /opt/Murphy-System)
  MURPHY_SERVICE       systemd service name  (default: murphy-production)
  MURPHY_VENV          Python virtualenv     (default: \$REPO_DIR/venv)
  MURPHY_COMPOSE_FILE  docker-compose file   (default: \$REPO_DIR/docker-compose.yml)
  MURPHY_ENV_FILE      Murphy env file       (default: /etc/murphy-production/environment)
  NGINX_SITE_NAME      nginx site name       (default: murphy-production)
  OLLAMA_MODEL         LLM model to ensure   (default: phi3)
  MURPHY_PORT          Murphy port           (default: 8000)
  OLLAMA_PORT          Ollama port           (default: 11434)
  GRAFANA_PORT         Grafana port          (default: 3000)
  PROMETHEUS_PORT      Prometheus port       (default: 9090)
  MURPHY_WEBMAIL_PORT  Roundcube port        (default: 8443)

Examples:
  $(basename "$0")                     # Full load — all subsystems
  $(basename "$0") --skip-deps         # Skip pip (code-only change)
  $(basename "$0") --skip-docker       # Docker already running
  $(basename "$0") --skip-ollama       # Ollama already healthy
  OLLAMA_MODEL=llama3 $(basename "$0") # Use llama3 instead of phi3

One-liner (from anywhere on the server):
  bash /opt/Murphy-System/scripts/hetzner_load.sh

EOF
  exit 0
}

# ── Defaults ──────────────────────────────────────────────────────────────────
REPO_DIR="${MURPHY_REPO_DIR:-/opt/Murphy-System}"
SERVICE_NAME="${MURPHY_SERVICE:-murphy-production}"
VENV_DIR="${MURPHY_VENV:-${REPO_DIR}/venv}"
REQUIREMENTS_FILE="${REPO_DIR}/requirements_murphy_1.0.txt"
COMPOSE_FILE="${MURPHY_COMPOSE_FILE:-${REPO_DIR}/docker-compose.yml}"
MURPHY_ENV_FILE="${MURPHY_ENV_FILE:-/etc/murphy-production/environment}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-murphy-production}"
OLLAMA_MODEL="${OLLAMA_MODEL:-phi3}"
MURPHY_PORT="${MURPHY_PORT:-8000}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
WEBMAIL_PORT="${MURPHY_WEBMAIL_PORT:-8443}"

SKIP_PULL=false
SKIP_DEPS=false
SKIP_ENV_AUDIT=false
SKIP_NGINX=false
SKIP_OLLAMA=false
SKIP_DOCKER=false
SKIP_MAIL_SETUP=false
SKIP_HEALTH=false

# ── Parse arguments ───────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    -h|--help)          show_help ;;
    --version)          echo "Murphy System Hetzner Load Script v3.0.0"; exit 0 ;;
    --skip-pull)        SKIP_PULL=true ;;
    --skip-deps)        SKIP_DEPS=true ;;
    --skip-env-audit)   SKIP_ENV_AUDIT=true ;;
    --skip-nginx)       SKIP_NGINX=true ;;
    --skip-ollama)      SKIP_OLLAMA=true ;;
    --skip-docker)      SKIP_DOCKER=true ;;
    --skip-mail-setup)  SKIP_MAIL_SETUP=true ;;
    --no-health-check)  SKIP_HEALTH=true ;;
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
CYAN='\033[0;36m'
NC='\033[0m'

ok()      { echo -e "${GREEN}  ✓ $*${NC}"; }
info()    { echo -e "${BLUE}  ▶ $*${NC}"; }
section() { echo -e "\n${CYAN}══ $* ${NC}"; }
warn()    { echo -e "${YELLOW}  ⚠ WARNING: $*${NC}"; }
fail()    { echo -e "${RED}  ✗ FATAL: $*${NC}" >&2; exit 1; }

# Helper: ensure a systemd service is enabled and active
ensure_service() {
  local svc="$1"
  local label="${2:-$1}"
  if ! systemctl is-enabled --quiet "$svc" 2>/dev/null; then
    systemctl enable "$svc" 2>/dev/null || true
  fi
  if ! systemctl is-active --quiet "$svc" 2>/dev/null; then
    info "Starting ${label} ..."
    systemctl start "$svc"
    sleep 2
  fi
  ok "${label} is running"
}

# Helper: HTTP health probe (non-fatal)
http_check() {
  local label="$1"
  local url="$2"
  if curl -sf --max-time 5 "$url" >/dev/null 2>&1; then
    ok "${label}"
    return 0
  else
    warn "${label} not responding at ${url}"
    return 1
  fi
}

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo "    💀  M U R P H Y   H E T Z N E R   F U L L - S T A C K   L O A D"
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo ""

# ── Preflight ─────────────────────────────────────────────────────────────────
section "Preflight"
[ -d "${REPO_DIR}/.git" ] || fail "Repository not found at ${REPO_DIR}. Set MURPHY_REPO_DIR or clone first."
command -v docker &>/dev/null   || fail "Docker not installed. Install Docker Engine first."
docker compose version &>/dev/null 2>&1 || fail "docker compose v2 not available. Install the Compose plugin."
ok "Preflight checks passed"
cd "$REPO_DIR"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Pull latest code
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 1 — Code Update"
if [ "$SKIP_PULL" = false ]; then
  info "git pull origin main ..."
  git pull origin main
  ok "Code updated"
else
  info "Skipping git pull (--skip-pull)"
fi
DEPLOY_COMMIT=$(git rev-parse --short HEAD)
ok "Active commit: ${DEPLOY_COMMIT}"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Python dependencies
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 2 — Python Dependencies"
if [ "$SKIP_DEPS" = false ]; then
  if [ -f "${VENV_DIR}/bin/pip" ]; then
    info "pip install --upgrade (venv) ..."
    "${VENV_DIR}/bin/pip" install --quiet --upgrade -r "$REQUIREMENTS_FILE"
    ok "Dependencies updated (venv: ${VENV_DIR})"
  elif command -v pip3 &>/dev/null; then
    info "pip3 install --upgrade (system) ..."
    pip3 install --quiet --upgrade -r "$REQUIREMENTS_FILE"
    ok "Dependencies updated (system pip3)"
  else
    warn "No pip found — skipping dependency update"
  fi
else
  info "Skipping pip install (--skip-deps)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Environment file audit
#   Checks that the env file Murphy reads at startup has all the connection
#   variables needed to reach every subsystem.
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 3 — Environment File Audit"
if [ "$SKIP_ENV_AUDIT" = false ]; then
  if [ -f "$MURPHY_ENV_FILE" ]; then
    ok "Env file found: ${MURPHY_ENV_FILE}"
    # Source it so we can inspect values
    set +u
    # shellcheck disable=SC1090
    . "$MURPHY_ENV_FILE" 2>/dev/null || true
    set -u

    # Core secrets
    [ -n "${MURPHY_SECRET_KEY:-}" ]          && ok "MURPHY_SECRET_KEY is set"   || warn "MURPHY_SECRET_KEY not set — sessions will be insecure (set in ${MURPHY_ENV_FILE})"

    # Database (Docker → Murphy)
    [ -n "${DATABASE_URL:-}" ]               && ok "DATABASE_URL is set"        || warn "DATABASE_URL not set — Murphy will run without persistent DB (set to: postgresql://murphy:<pass>@localhost:5432/murphy)"

    # Redis (Docker → Murphy)
    [ -n "${REDIS_URL:-}" ]                  && ok "REDIS_URL is set"           || warn "REDIS_URL not set — caching/sessions degraded (set to: redis://localhost:6379/0)"

    # Onboard LLM
    [ -n "${OLLAMA_HOST:-}" ]                && ok "OLLAMA_HOST is set"         || warn "OLLAMA_HOST not set — defaulting to http://localhost:11434"

    # Mail subsystem (Docker mailserver → Murphy SMTP integration)
    [ -n "${SMTP_HOST:-}" ]                  && ok "SMTP_HOST is set"           || warn "SMTP_HOST not set — outbound email disabled (set to: localhost)"
    [ -n "${SMTP_USER:-}" ]                  && ok "SMTP_USER is set"           || warn "SMTP_USER not set — set to a mailbox address (e.g. murphy@murphy.systems)"
    [ -n "${SMTP_PASSWORD:-}" ]              && ok "SMTP_PASSWORD is set"       || warn "SMTP_PASSWORD not set — SMTP auth disabled"

    # IM / Matrix bridge
    [ -n "${MATRIX_HOMESERVER_URL:-}" ]      && ok "MATRIX_HOMESERVER_URL is set" || warn "MATRIX_HOMESERVER_URL not set — Matrix IM bridge will be inactive"
    [ -n "${MATRIX_ACCESS_TOKEN:-}" ]        && ok "MATRIX_ACCESS_TOKEN is set"   || warn "MATRIX_ACCESS_TOKEN not set — Matrix IM bridge will be inactive"
    [ -n "${MATRIX_USER_ID:-}" ]             && ok "MATRIX_USER_ID is set"        || warn "MATRIX_USER_ID not set — Matrix IM bridge will be inactive"
  else
    warn "Env file not found at ${MURPHY_ENV_FILE}"
    warn "Murphy will start with defaults. Create the file to enable all subsystem connections."
    warn "See: documentation/deployment/DEPLOYMENT_GUIDE.md — 'Step 4: Set Up System Service'"
  fi
else
  info "Skipping environment audit (--skip-env-audit)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Nginx (reverse proxy — the glue that links everything together)
#   Nginx is the single entry point that routes external traffic to every
#   backend service.  All subsystems are reachable through one URL/IP.
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 4 — Nginx (Reverse Proxy — Website + API glue)"
if [ "$SKIP_NGINX" = false ]; then
  if command -v nginx &>/dev/null; then
    ensure_service nginx "Nginx"

    # Check the murphy vhost is linked
    NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
    NGINX_AVAIL="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
    if [ -f "$NGINX_ENABLED" ] || [ -L "$NGINX_ENABLED" ]; then
      ok "Nginx vhost '${NGINX_SITE_NAME}' is enabled"
    elif [ -f "$NGINX_AVAIL" ]; then
      info "Enabling nginx vhost '${NGINX_SITE_NAME}' ..."
      ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
      ok "Nginx vhost '${NGINX_SITE_NAME}' enabled"
    else
      warn "Nginx vhost '${NGINX_SITE_NAME}' not found in sites-available."
      warn "Create /etc/nginx/sites-available/${NGINX_SITE_NAME} to expose the website."
      warn "See: documentation/deployment/DEPLOYMENT_GUIDE.md — 'Step 5: Configure Reverse Proxy'"
    fi

    # Validate config and reload to pick up any changes
    if nginx -t -q 2>/dev/null; then
      systemctl reload nginx 2>/dev/null || true
      ok "Nginx config valid — reloaded"
    else
      warn "Nginx config test failed — NOT reloading (run: nginx -t)"
    fi
  else
    warn "Nginx not installed — website will not be externally reachable via port 80/443."
    warn "Install with: apt-get install nginx"
  fi
else
  info "Skipping nginx (--skip-nginx)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Onboard LLM (Ollama)
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 5 — Onboard LLM (Ollama)"
if [ "$SKIP_OLLAMA" = false ]; then
  if ! command -v ollama &>/dev/null; then
    info "Ollama not found — installing ..."
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama installed"
  fi
  ensure_service ollama "Ollama (systemd)"
  if ! ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL}"; then
    info "Pulling model '${OLLAMA_MODEL}' (this may take several minutes) ..."
    ollama pull "${OLLAMA_MODEL}"
    ok "Model '${OLLAMA_MODEL}' ready"
  else
    ok "Model '${OLLAMA_MODEL}' already present"
  fi
else
  info "Skipping Ollama (--skip-ollama)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Docker Compose subsystems
#   PostgreSQL, Redis, Prometheus, Grafana, Mailserver, Webmail
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 6 — Docker Compose Subsystems (DB · Cache · Monitoring · Mail)"
if [ "$SKIP_DOCKER" = false ]; then
  [ -f "$COMPOSE_FILE" ] || fail "docker-compose.yml not found at ${COMPOSE_FILE}. Set MURPHY_COMPOSE_FILE."

  info "Pulling latest Docker images ..."
  docker compose -f "$COMPOSE_FILE" pull --quiet 2>/dev/null \
    || warn "Some images could not be pulled (continuing with cached versions)"

  info "Starting all Docker Compose services ..."
  docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

  echo ""
  docker compose -f "$COMPOSE_FILE" ps \
    --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null \
    || docker compose -f "$COMPOSE_FILE" ps
  echo ""
  ok "Docker Compose services are up"
else
  info "Skipping Docker Compose (--skip-docker)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Mail provisioning (idempotent mailbox setup)
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 7 — Mail Provisioning (Postfix + Dovecot mailboxes)"
if [ "$SKIP_MAIL_SETUP" = false ]; then
  MAIL_SETUP="${REPO_DIR}/scripts/mail_setup.sh"
  if [ -f "$MAIL_SETUP" ]; then
    MAIL_STATUS=$(docker inspect \
      --format='{{.State.Health.Status}}' murphy-mailserver 2>/dev/null || echo "missing")
    if [ "$MAIL_STATUS" = "healthy" ]; then
      info "Running mail_setup.sh (mailbox provisioning) ..."
      bash "$MAIL_SETUP" || warn "mail_setup.sh reported errors — check mailboxes manually"
      ok "Mail provisioning complete"
    elif [ "$MAIL_STATUS" = "starting" ]; then
      warn "Mailserver is still starting — re-run mail_setup.sh manually when healthy:"
      warn "  docker inspect murphy-mailserver --format='{{.State.Health.Status}}'"
      warn "  bash ${MAIL_SETUP}"
    else
      warn "Mailserver container not healthy (status: ${MAIL_STATUS}) — skipping mail_setup.sh"
    fi
  else
    warn "scripts/mail_setup.sh not found — skipping mailbox provisioning"
  fi
else
  info "Skipping mail provisioning (--skip-mail-setup)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Murphy System application (systemd)
#   Serves: REST API · Website (static HTML) · Matrix IM bridge ·
#           Slack/Twilio integrations · Prometheus metrics endpoint
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 8 — Murphy System Application"
info "Restarting ${SERVICE_NAME} (commit: ${DEPLOY_COMMIT}) ..."
MURPHY_DEPLOY_COMMIT="${DEPLOY_COMMIT}" systemctl restart "${SERVICE_NAME}"
ok "${SERVICE_NAME} restarted"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Health checks (all subsystems)
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 9 — Health Checks"
if [ "$SKIP_HEALTH" = false ]; then
  info "Waiting 10 s for services to settle ..."
  sleep 10
  echo ""
  printf "  %-36s %s\n" "Subsystem" "Status"
  printf "  %-36s %s\n" "─────────────────────────────────" "────────"

  # ── Murphy API (FastAPI) ────────────────────────────────────────────────────
  http_check "Murphy API           :${MURPHY_PORT}" \
    "http://localhost:${MURPHY_PORT}/api/health"

  # ── Website (served by Murphy via nginx) ────────────────────────────────────
  if command -v nginx &>/dev/null && systemctl is-active --quiet nginx 2>/dev/null; then
    http_check "Website (nginx → Murphy)          " \
      "http://localhost/api/health" \
      || http_check "Website (nginx HTTPS)              " \
           "https://localhost/api/health" 2>/dev/null || true
  fi

  # ── Onboard LLM ─────────────────────────────────────────────────────────────
  if [ "$SKIP_OLLAMA" = false ]; then
    http_check "Ollama / Onboard LLM :${OLLAMA_PORT}" \
      "http://localhost:${OLLAMA_PORT}/api/tags"
  fi

  if [ "$SKIP_DOCKER" = false ]; then
    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    if docker exec murphy-postgres pg_isready -U murphy -d murphy \
        >/dev/null 2>&1; then
      ok "PostgreSQL (murphy-postgres)     — accepting connections"
    else
      warn "PostgreSQL not ready — docker logs murphy-postgres"
    fi

    # ── Redis ──────────────────────────────────────────────────────────────────
    if docker exec murphy-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
      ok "Redis      (murphy-redis)        — PONG"
    else
      warn "Redis not ready — docker logs murphy-redis"
    fi

    # ── Prometheus ────────────────────────────────────────────────────────────
    http_check "Prometheus           :${PROMETHEUS_PORT}" \
      "http://localhost:${PROMETHEUS_PORT}/-/healthy"

    # ── Grafana ───────────────────────────────────────────────────────────────
    http_check "Grafana              :${GRAFANA_PORT}" \
      "http://localhost:${GRAFANA_PORT}/api/health"

    # ── Mailserver SMTP ──────────────────────────────────────────────────────
    if docker exec murphy-mailserver \
        sh -c 'ss -lntp 2>/dev/null | grep -q ":25"' 2>/dev/null; then
      ok "Mail Server SMTP     :25          — listening"
    else
      warn "Mail SMTP not yet ready — docker logs murphy-mailserver"
    fi

    # ── Mailserver IMAP ──────────────────────────────────────────────────────
    if docker exec murphy-mailserver \
        sh -c 'ss -lntp 2>/dev/null | grep -q ":993"' 2>/dev/null; then
      ok "Mail Server IMAPS    :993         — listening"
    else
      warn "Mail IMAPS not yet ready — docker logs murphy-mailserver"
    fi

    # ── Roundcube Webmail ────────────────────────────────────────────────────
    http_check "Webmail / Roundcube  :${WEBMAIL_PORT}" \
      "http://localhost:${WEBMAIL_PORT}/"
  fi

  # ── Matrix bridge (in-app — check via Murphy API) ────────────────────────
  MATRIX_STATUS=$(curl -sf --max-time 5 \
    "http://localhost:${MURPHY_PORT}/api/matrix/status" 2>/dev/null || echo '{}')
  if echo "$MATRIX_STATUS" | grep -q '"connected":true'; then
    ok "Matrix IM bridge                  — connected"
  else
    HOMESERVER=$(echo "$MATRIX_STATUS" | \
      python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('homeserver','?'))" \
      2>/dev/null || echo "?")
    if [ -n "${MATRIX_ACCESS_TOKEN:-}" ]; then
      warn "Matrix IM bridge not connected (homeserver: ${HOMESERVER}) — check MATRIX_* env vars"
    else
      warn "Matrix IM bridge inactive — set MATRIX_ACCESS_TOKEN to enable IM integration"
    fi
  fi

  # ── Nginx ─────────────────────────────────────────────────────────────────
  if command -v nginx &>/dev/null; then
    if systemctl is-active --quiet nginx 2>/dev/null; then
      ok "Nginx (reverse proxy)             — active"
    else
      warn "Nginx is not active — systemctl start nginx"
    fi
  fi
  echo ""
else
  info "Skipping health checks (--no-health-check)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo -e "    ${GREEN}💀  MURPHY FULL-STACK LOADED — commit ${DEPLOY_COMMIT}  💀${NC}   "
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo ""
echo -e "  ${BLUE}Website (public):${NC}  https://<your-domain>/             (via nginx)"
echo -e "  ${BLUE}Murphy API:${NC}        http://localhost:${MURPHY_PORT}/api/health"
echo -e "  ${BLUE}Onboard LLM:${NC}       http://localhost:${OLLAMA_PORT}/api/tags"
echo -e "  ${BLUE}Grafana:${NC}           http://localhost:${GRAFANA_PORT}"
echo -e "  ${BLUE}Prometheus:${NC}        http://localhost:${PROMETHEUS_PORT}"
echo -e "  ${BLUE}Webmail:${NC}           http://localhost:${WEBMAIL_PORT}"
echo -e "  ${BLUE}Matrix bridge:${NC}     http://localhost:${MURPHY_PORT}/api/matrix/status"
echo ""
echo -e "  Logs:  ${YELLOW}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  Stack: ${YELLOW}docker compose -f ${COMPOSE_FILE} ps${NC}"
echo ""

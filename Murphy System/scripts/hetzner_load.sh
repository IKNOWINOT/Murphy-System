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
# │  ② Env audit      /etc/murphy-production/environment:                  │
# │                   DATABASE_URL, REDIS_URL, OLLAMA_HOST,                 │
# │                   SMTP_HOST, MATRIX_HOMESERVER_URL, MURPHY_SECRET_KEY   │
# │                   MATRIX_USER_ID / MATRIX_ACCESS_TOKEN (or BOT aliases) │
# │                                                                         │
# │  ③ Nginx          Reverse proxy / TLS — routes everything:             │
# │                   /  /ui/ /api/ /static/ /docs → Murphy API :8000       │
# │                   /grafana/                     → Grafana      :3000    │
# │                   /mail/                        → Roundcube    :8443    │
# │                   /metrics                      → Murphy API   :8000    │
# │                                                                         │
# │  ④ Onboard LLM    ollama (systemd) — phi3 / llama3                    │
# │                                                                         │
# │  ⑤ Docker stack   docker-compose.hetzner.yml:                          │
# │                   • murphy-postgres  PostgreSQL      :5432              │
# │                   • murphy-redis     Redis           :6379              │
# │                   • murphy-prometheus Prometheus     :9090              │
# │                   • murphy-grafana   Grafana         :3000              │
# │                   • murphy-mailserver Postfix+Dovecot :25/:587/:993     │
# │                   • murphy-webmail   Roundcube       :8443              │
# │                                                                         │
# │  ⑥ Mail setup     scripts/mail_setup.sh (mailbox provisioning)         │
# │                                                                         │
# │  ⑦ Murphy app     murphy-production (systemd):                         │
# │                   • REST API          /api/*                            │
# │                   • Website           / + /ui/* + /static/*             │
# │                   • Matrix IM bridge  (MATRIX_BOT_TOKEN / BOT_USER)     │
# │                   • Slack/Twilio IM   (runs inside Murphy process)      │
# │                   • Trading engine    /api/trading/* (paper + live)     │
# │                   • Game creation     /api/game/* + /ui/game-creation   │
# │                   • EQ mod system     src/eq/ (25 modules, 140 tasks)   │
# │                   • Metrics           /metrics                          │
# │                                                                         │
# │  ⑧ Health checks  Every subsystem verified                             │
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
Covers every subsystem: LLM, database, cache, mail, IM, monitoring,
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
  --repair             Force full rebuild: nuke venv, recreate env from template,
                       recreate Docker volumes (destructive — use when normal run fails)

What gets started (in order):
  1. git pull origin main
  2. pip install --upgrade (Python dependencies)
  3. Environment file audit (warn on missing connection vars)
  4. nginx              reverse proxy / TLS / website routing  [systemd]
  5. ollama             onboard LLM                            [systemd]
  6. docker-compose.hetzner.yml  support services:
       murphy-postgres  PostgreSQL
       murphy-redis     Redis
       murphy-prometheus Prometheus
       murphy-grafana   Grafana
       murphy-mailserver Postfix + Dovecot (SMTP/IMAP)
       murphy-webmail   Roundcube webmail
  7. scripts/mail_setup.sh       mailbox provisioning
  8. murphy-production  Murphy app (REST API + website + IM bridge) [systemd]
  9. Health checks on every subsystem

Environment overrides (shell variables):
  MURPHY_REPO_DIR      Repo path             (default: /opt/Murphy-System)
  MURPHY_SERVICE       systemd service name  (default: murphy-production)
  MURPHY_VENV          Python virtualenv     (default: \$REPO_DIR/venv)
  MURPHY_COMPOSE_FILE  Compose file          (default: \$REPO_DIR/docker-compose.hetzner.yml)
  MURPHY_ENV_FILE      Murphy env file       (default: /etc/murphy-production/environment)
  NGINX_SITE_NAME      nginx site name       (default: murphy-production)
  OLLAMA_MODEL         LLM model             (default: phi3)
  MURPHY_PORT          Murphy port           (default: 8000)
  OLLAMA_PORT          Ollama port           (default: 11434)
  GRAFANA_PORT         Grafana port          (default: 3000)
  PROMETHEUS_PORT      Prometheus port       (default: 9090)
  MURPHY_WEBMAIL_PORT  Roundcube port        (default: 8443)

Config templates (copy and fill in before first run):
  config/murphy-production.environment.example → /etc/murphy-production/environment
  config/nginx/murphy-production.conf          → /etc/nginx/sites-available/murphy-production
  config/systemd/murphy-production.service     → /etc/systemd/system/murphy-production.service

Examples:
  $(basename "$0")                     # Full load — all subsystems
  $(basename "$0") --skip-deps         # Skip pip (code-only change)
  $(basename "$0") --skip-docker       # Docker services already running
  $(basename "$0") --skip-ollama       # Ollama already healthy
  $(basename "$0") --repair            # Force full rebuild (broken venv, corrupt env, etc.)
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
# Prefer the pinned lockfile (fast, no resolution needed) over the loose
# requirements file.  Fall back to requirements_murphy_1.0.txt only when
# no lockfile exists (first install / --repair).
LOCKFILE="${REPO_DIR}/requirements.lock"
REQUIREMENTS_LOOSE="${REPO_DIR}/requirements_murphy_1.0.txt"
if [ -f "${LOCKFILE}" ]; then
  REQUIREMENTS_FILE="${LOCKFILE}"
else
  REQUIREMENTS_FILE="${REQUIREMENTS_LOOSE}"
fi
COMPOSE_FILE="${MURPHY_COMPOSE_FILE:-${REPO_DIR}/docker-compose.hetzner.yml}"
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
REPAIR=false

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
    --repair)           REPAIR=true ;;
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
warn()    { echo -e "${YELLOW}  ⚠ $*${NC}"; }
fail()    { echo -e "${RED}  ✗ FATAL: $*${NC}" >&2; exit 1; }

# ── Helpers ───────────────────────────────────────────────────────────────────

# Ensure a systemd service is enabled and active
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

# Audit a single env var: ok if set, warn if missing
audit_var() {
  local varname="$1"
  local hint="$2"
  local val
  val=$(printenv "$varname" 2>/dev/null || true)
  if [ -n "$val" ]; then
    ok "${varname} is set"
  else
    warn "${varname} not set — ${hint}"
  fi
}

# HTTP health probe (non-fatal — always returns 0 so set -e does not abort)
http_check() {
  local label="$1"
  local url="$2"
  if curl -sf --max-time 5 "$url" >/dev/null 2>&1; then
    ok "${label}"
  else
    warn "${label} not responding at ${url}"
  fi
  return 0
}

# HTTP health probe with retry — polls every INTERVAL seconds until the
# endpoint responds or MAX_WAIT seconds have elapsed.  Always returns 0.
wait_for_http() {
  local label="$1"
  local url="$2"
  local max_wait="${3:-60}"
  local interval="${4:-5}"
  local waited=0
  info "Waiting for ${label} (timeout: ${max_wait}s) ..."
  while [ "$waited" -lt "$max_wait" ]; do
    if curl -sf --max-time 5 "$url" >/dev/null 2>&1; then
      ok "${label}"
      return 0
    fi
    sleep "$interval"
    waited=$((waited + interval))
  done
  warn "${label} not responding after ${max_wait}s — check: journalctl -u ${SERVICE_NAME:-murphy-production} -n 50"
  return 0
}

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo "    M U R P H Y   H E T Z N E R   F U L L - S T A C K   L O A D"
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PREFLIGHT
# ═══════════════════════════════════════════════════════════════════════════════
section "☠"
[ -d "${REPO_DIR}/.git" ] \
  || fail "Repository not found at ${REPO_DIR}. Set MURPHY_REPO_DIR or clone first."
command -v docker &>/dev/null \
  || fail "Docker not installed. Install Docker Engine before running this script."
docker compose version &>/dev/null 2>&1 \
  || fail "docker compose v2 not available. Install the Compose plugin."
ok "Devils in the details...."
cd "$REPO_DIR"

# ── Preflight: disk space ──────────────────────────────────────────────────────
AVAIL_KB=$(df -k "${REPO_DIR}" 2>/dev/null | awk 'NR==2{print $4}' || echo "")
if [ -n "${AVAIL_KB}" ] && [ "${AVAIL_KB}" -lt 2097152 ]; then
  fail "Insufficient disk space: $((AVAIL_KB / 1024)) MB free on ${REPO_DIR} (need ≥ 2 GB). Free space first."
fi
ok "Disk space: $((${AVAIL_KB:-0} / 1024)) MB free on ${REPO_DIR}"

# ── Preflight: RAM ────────────────────────────────────────────────────────────
AVAIL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}' || echo "")
if [ -n "${AVAIL_RAM_MB}" ] && [ "${AVAIL_RAM_MB}" -lt 1024 ]; then
  warn "Low RAM: ${AVAIL_RAM_MB} MB available (pip + PyTorch + Ollama may OOM)"
else
  ok "RAM: ${AVAIL_RAM_MB:-?} MB available"
fi

# ── Preflight: stale lock files ───────────────────────────────────────────────
for _lockfile in /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock; do
  if [ -f "${_lockfile}" ]; then
    _lock_pid=$(lsof "${_lockfile}" 2>/dev/null | awk 'NR==2{print $2}' || echo "")
    if [ -z "${_lock_pid}" ] || ! kill -0 "${_lock_pid}" 2>/dev/null; then
      warn "Stale system lock file detected (not held by any process): ${_lockfile}"
    fi
  fi
done
unset _lockfile _lock_pid

# ── Preflight: key path ownership ─────────────────────────────────────────────
_murphy_user="${SUDO_USER:-$(id -un 2>/dev/null || echo root)}"
for _chkpath in "${REPO_DIR}" "${VENV_DIR}"; do
  if [ -e "${_chkpath}" ]; then
    _owner=$(stat -c '%U' "${_chkpath}" 2>/dev/null || echo "?")
    if [ "${_owner}" != "${_murphy_user}" ] && [ "${_owner}" != "root" ]; then
      warn "Path ${_chkpath} is owned by '${_owner}' (expected '${_murphy_user}' or root)"
    fi
  fi
done
unset _chkpath _owner _murphy_user

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Pull latest code
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 1 — Code Update"
if [ "$SKIP_PULL" = false ]; then
  # ── Remove stale git lock files ──────────────────────────────────────────────
  GIT_LOCK="${REPO_DIR}/.git/index.lock"
  if [ -f "${GIT_LOCK}" ]; then
    # .git/index.lock doesn't contain a PID — check if any git process is running
    if ! pgrep -x git &>/dev/null; then
      warn "Removing stale .git/index.lock (no git process running) ..."
      rm -f "${GIT_LOCK}"
      ok "Stale .git/index.lock removed"
    else
      warn ".git/index.lock exists and a git process is running — skipping removal"
    fi
  fi

  # ── Detect detached HEAD or wrong branch ─────────────────────────────────────
  _cur_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  if [ "${_cur_branch}" = "HEAD" ]; then
    warn "Detached HEAD detected — checking out main ..."
    git checkout main
    ok "Switched to main branch"
  elif [ "${_cur_branch}" != "main" ]; then
    warn "On branch '${_cur_branch}' (not main) — switching to main ..."
    git checkout main
    ok "Switched to main branch"
  fi
  unset _cur_branch

  # ── Stash dirty working tree ──────────────────────────────────────────────────
  if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    warn "Dirty working tree detected — stashing local changes ..."
    if ! git stash push -m "hetzner_load.sh auto-stash $(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null; then
      warn "git stash failed — attempting hard reset ..."
      git reset --hard HEAD 2>/dev/null || true
    fi
    ok "Local changes stashed (restore with: git stash pop)"
  fi

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

  # ── Helper: run pip install with heartbeat ticker and timeout ─────────────────
  _run_pip_install() {
    local extra_flags="${1:-}"
    local timeout_s=600
    local start elapsed
    start=$(date +%s)

    # When installing from a lockfile (exact pins), skip --upgrade to avoid
    # unnecessary resolution.  Only use --upgrade with the loose requirements file.
    local upgrade_flag="--upgrade"
    if [ "${REQUIREMENTS_FILE}" = "${LOCKFILE}" ]; then
      upgrade_flag=""
    fi

    # shellcheck disable=SC2086
    "${VENV_DIR}/bin/pip" install ${upgrade_flag} \
      --progress-bar off \
      ${extra_flags} \
      -r "${REQUIREMENTS_FILE}" \
      > /tmp/murphy-pip-install.log 2>&1 &
    local pid=$!

    while kill -0 "${pid}" 2>/dev/null; do
      sleep 30
      kill -0 "${pid}" 2>/dev/null || break
      elapsed=$(( $(date +%s) - start ))
      info "  still installing... ${elapsed}s elapsed"
      if [ "${elapsed}" -ge "${timeout_s}" ]; then
        warn "pip install timed out after ${timeout_s}s — killing"
        kill "${pid}" 2>/dev/null || true
        wait "${pid}" 2>/dev/null || true
        return 124
      fi
    done
    wait "${pid}"
  }

  # ── venv validation / creation / repair ──────────────────────────────────────
  VENV_OK=false
  if [ "${REPAIR}" = true ] && [ -d "${VENV_DIR}" ]; then
    warn "--repair: removing existing venv for full rebuild ..."
    rm -rf "${VENV_DIR}"
  fi

  if [ "${REPAIR}" = true ] && [ -f "${LOCKFILE}" ]; then
    warn "--repair: removing requirements.lock for full resolution ..."
    rm -f "${LOCKFILE}"
    REQUIREMENTS_FILE="${REQUIREMENTS_LOOSE}"
  fi

  if [ -d "${VENV_DIR}" ]; then
    if "${VENV_DIR}/bin/python" -c "import sys" &>/dev/null; then
      VENV_OK=true
      ok "venv OK: ${VENV_DIR}"
    else
      warn "venv corrupted (python -c 'import sys' failed) — rebuilding ..."
      rm -rf "${VENV_DIR}"
    fi
  else
    info "venv not found at ${VENV_DIR} — creating ..."
  fi

  if [ "${VENV_OK}" = false ]; then
    python3 -m venv "${VENV_DIR}" \
      || fail "python3 -m venv failed — install python3-venv first: apt install python3-venv"
    ok "venv created: ${VENV_DIR}"
  fi

  # ── Clean half-installed .dist-info dirs (no RECORD file) ────────────────────
  SITE_PKG=$("${VENV_DIR}/bin/python" -c \
    "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
  if [ -n "${SITE_PKG}" ] && [ -d "${SITE_PKG}" ]; then
    _orphaned=0
    while IFS= read -r -d '' _di; do
      if [ ! -f "${_di}/RECORD" ]; then
        warn "Removing half-installed package: $(basename "${_di}")"
        rm -rf "${_di}"
        _orphaned=$(( _orphaned + 1 ))
      fi
    done < <(find "${SITE_PKG}" -maxdepth 1 -name "*.dist-info" -print0 2>/dev/null)
    [ "${_orphaned}" -gt 0 ] && ok "Cleaned ${_orphaned} half-installed package(s)"
    unset _di _orphaned
  fi

  # ── Upgrade pip itself before tackling 190 packages ──────────────────────────
  info "Upgrading pip ..."
  "${VENV_DIR}/bin/pip" install --quiet --upgrade pip \
    || warn "pip self-upgrade failed — continuing with existing pip"

  # ── Install requirements ──────────────────────────────────────────────────────
  if [ ! -f "${REQUIREMENTS_FILE}" ]; then
    warn "Requirements file not found: ${REQUIREMENTS_FILE} — skipping dep install"
  else
    info "Using requirements file: ${REQUIREMENTS_FILE}"
    info "Installing requirements (may take 10-30 min on first install) ..."
    _pip_exit=0
    _run_pip_install || _pip_exit=$?

    if [ "${_pip_exit}" -eq 124 ]; then
      warn "pip timed out — clearing cache and retrying ..."
      "${VENV_DIR}/bin/pip" cache purge 2>/dev/null \
        || rm -rf ~/.cache/pip 2>/dev/null || true
      _pip_exit=0
      _run_pip_install "--no-cache-dir" || _pip_exit=$?
    fi

    if [ "${_pip_exit}" -ne 0 ]; then
      warn "pip install failed (exit ${_pip_exit}). Last 20 lines:"
      tail -20 /tmp/murphy-pip-install.log >&2 || true
      warn "Retrying with cache clear ..."
      "${VENV_DIR}/bin/pip" cache purge 2>/dev/null \
        || rm -rf ~/.cache/pip 2>/dev/null || true
      _run_pip_install "--no-cache-dir" \
        || fail "pip install failed after retry — check ${REQUIREMENTS_FILE} and network connectivity"
    fi

    ok "Dependencies updated (venv: ${VENV_DIR})"

    # ── Generate/update requirements.lock for future fast installs ──────────────
    info "Generating requirements.lock from installed packages ..."
    "${VENV_DIR}/bin/pip" freeze > "${LOCKFILE}" 2>/tmp/murphy-pip-freeze.log \
      && ok "requirements.lock updated ($(wc -l < "${LOCKFILE}") packages pinned)" \
      || warn "Failed to generate requirements.lock — next install may be slow"

    unset _pip_exit
  fi

  # ── Purge stale __pycache__ / .pyc (prevents bytecode import errors) ─────────
  info "Purging stale __pycache__ / .pyc files ..."
  find "${REPO_DIR}/src" -name '__pycache__' -type d \
    -exec rm -rf {} + 2>/dev/null || true
  find "${REPO_DIR}/src" -name '*.pyc' -type f \
    -delete 2>/dev/null || true
  ok "Bytecode cache cleared"

else
  info "Skipping pip install (--skip-deps)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Environment file audit
#   Checks that /etc/murphy-production/environment has all the connection
#   variables needed to reach every subsystem.  Warnings only — not fatal.
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 3 — Environment File Audit"
if [ "$SKIP_ENV_AUDIT" = false ]; then
  if [ ! -f "$MURPHY_ENV_FILE" ]; then
    info "No env file found — generating fresh production secrets..."
    bash "${REPO_DIR}/scripts/generate_secrets.sh" --production
  fi
  if [ -f "$MURPHY_ENV_FILE" ]; then
    ok "Env file found: ${MURPHY_ENV_FILE}"
    # Source the env file so audit_var can read it via printenv.
    # set +u is scoped narrowly to the source call only — the env file may
    # legitimately have unset variables which is exactly what we are auditing.
    set +u
    # shellcheck disable=SC1090,SC1091
    source "$MURPHY_ENV_FILE" 2>/dev/null || true
    set -u

    audit_var "MURPHY_SECRET_KEY"      "sessions will be insecure — generate: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
    audit_var "DATABASE_URL"           "Murphy runs without persistent DB — set to: postgresql://murphy:<pass>@localhost:5432/murphy"
    audit_var "REDIS_URL"              "caching/sessions degraded — set to: redis://:password@localhost:6379/0"
    audit_var "OLLAMA_HOST"            "defaulting to http://localhost:11434"
    audit_var "SMTP_HOST"              "outbound email disabled — set to: localhost (to use murphy-mailserver)"
    audit_var "SMTP_USER"              "SMTP auth disabled — set to a mailbox address e.g. murphy@murphy.systems"
    audit_var "SMTP_PASSWORD"          "SMTP auth disabled"
    audit_var "MATRIX_HOMESERVER_URL"  "Matrix IM bridge inactive (optional)"
    audit_var "MATRIX_ACCESS_TOKEN"    "Matrix IM bridge inactive (optional)"
    audit_var "MATRIX_USER_ID"         "Matrix IM bridge inactive (optional)"
    audit_var "MATRIX_BOT_TOKEN"       "Matrix client token alias missing — will be auto-populated from MATRIX_ACCESS_TOKEN"
    audit_var "MATRIX_BOT_USER"        "Matrix client user alias missing — will be auto-populated from MATRIX_USER_ID"

    # Sanitize: quote any values containing spaces that aren't already quoted
    if [ -f "$MURPHY_ENV_FILE" ]; then
      sed -i -E 's/^([A-Za-z_][A-Za-z0-9_]*)=([^"'"'"'].*[[:space:]].*)/\1="\2"/' "$MURPHY_ENV_FILE"
    fi

    # Auto-populate MATRIX_BOT_* aliases from MATRIX_* if missing
    if [ -f "$MURPHY_ENV_FILE" ]; then
      if grep -q "^MATRIX_ACCESS_TOKEN=" "$MURPHY_ENV_FILE" && ! grep -q "^MATRIX_BOT_TOKEN=" "$MURPHY_ENV_FILE"; then
        MATRIX_TOKEN_VAL=$(grep "^MATRIX_ACCESS_TOKEN=" "$MURPHY_ENV_FILE" | cut -d= -f2- | sed 's/^"\(.*\)"$/\1/')
        echo "MATRIX_BOT_TOKEN=\"${MATRIX_TOKEN_VAL}\"" >> "$MURPHY_ENV_FILE"
        ok "MATRIX_BOT_TOKEN auto-populated from MATRIX_ACCESS_TOKEN"
      fi
      if grep -q "^MATRIX_USER_ID=" "$MURPHY_ENV_FILE" && ! grep -q "^MATRIX_BOT_USER=" "$MURPHY_ENV_FILE"; then
        MATRIX_USER_VAL=$(grep "^MATRIX_USER_ID=" "$MURPHY_ENV_FILE" | cut -d= -f2- | sed 's/^"\(.*\)"$/\1/')
        echo "MATRIX_BOT_USER=\"${MATRIX_USER_VAL}\"" >> "$MURPHY_ENV_FILE"
        ok "MATRIX_BOT_USER auto-populated from MATRIX_USER_ID"
      fi
    fi

    # ── Syntax validation: every non-comment, non-blank line must be KEY=value ──
    _bad_lines=$(grep -vE '^\s*#|^\s*$|^[A-Za-z_][A-Za-z0-9_]*=' \
      "${MURPHY_ENV_FILE}" 2>/dev/null | wc -l)
    if [ "${_bad_lines}" -gt 0 ]; then
      warn "Env file has ${_bad_lines} malformed line(s) (not KEY=value):"
      grep -nvE '^\s*#|^\s*$|^[A-Za-z_][A-Za-z0-9_]*=' "${MURPHY_ENV_FILE}" \
        2>/dev/null | head -10 >&2 || true
      warn "This may indicate a truncated/corrupted env file."
      warn "  To regenerate: bash ${REPO_DIR}/scripts/generate_secrets.sh --production"
    else
      ok "Env file syntax OK"
    fi
    unset _bad_lines

    # ── CHANGEME placeholder detection ────────────────────────────────────────
    _changeme_count=$(grep -cE 'CHANGEME' "${MURPHY_ENV_FILE}" 2>/dev/null || echo 0)
    if [ "${_changeme_count}" -gt 0 ]; then
      warn "Env file still contains ${_changeme_count} CHANGEME placeholder(s) — fill in real values:"
      grep -nE 'CHANGEME' "${MURPHY_ENV_FILE}" 2>/dev/null | head -10 >&2 || true
    fi
    unset _changeme_count

    # ── Deduplicate keys (last value wins) ────────────────────────────────────
    _dedup_tmp=$(mktemp)
    tac "${MURPHY_ENV_FILE}" | awk -F= '
      /^[[:space:]]*#/ || /^[[:space:]]*$/ { print; next }
      /^[A-Za-z_][A-Za-z0-9_]*=/ { key=$1; if (!(key in seen)) { seen[key]=1; print }; next }
      { print }
    ' | tac > "${_dedup_tmp}"
    _orig_lines=$(wc -l < "${MURPHY_ENV_FILE}")
    _dedup_lines=$(wc -l < "${_dedup_tmp}")
    _removed=$(( _orig_lines - _dedup_lines ))
    if [ "${_removed}" -gt 0 ]; then
      cp "${_dedup_tmp}" "${MURPHY_ENV_FILE}"
      ok "Env file deduplicated: removed ${_removed} duplicate key(s) (last value kept)"
    fi
    rm -f "${_dedup_tmp}"
    unset _dedup_tmp _orig_lines _dedup_lines _removed
  else
    warn "Env file not found at ${MURPHY_ENV_FILE}"
    warn "Murphy will start with defaults. To enable all subsystem connections:"
    warn "  sudo mkdir -p /etc/murphy-production"
    warn "  sudo cp ${REPO_DIR}/config/murphy-production.environment.example \\"
    warn "          /etc/murphy-production/environment"
    warn "  sudo nano /etc/murphy-production/environment  # fill in real secrets"
    warn "  sudo chmod 600 /etc/murphy-production/environment"
  fi
else
  info "Skipping environment audit (--skip-env-audit)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Nginx (reverse proxy — the glue that links all services together)
#   Routes all external traffic through one URL space.
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 4 — Nginx (Reverse Proxy + Website Routing)"
if [ "$SKIP_NGINX" = false ]; then
  if command -v nginx &>/dev/null; then
    ensure_service nginx "Nginx"

    NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
    NGINX_AVAIL="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
    NGINX_TEMPLATE="${REPO_DIR}/config/nginx/murphy-production.conf"

    if [ -f "$NGINX_ENABLED" ] || [ -L "$NGINX_ENABLED" ]; then
      ok "Nginx vhost '${NGINX_SITE_NAME}' is enabled"
    elif [ -f "$NGINX_AVAIL" ]; then
      info "Enabling nginx vhost '${NGINX_SITE_NAME}' ..."
      ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
      ok "Nginx vhost '${NGINX_SITE_NAME}' enabled"
    elif [ -f "$NGINX_TEMPLATE" ]; then
      info "Installing nginx vhost from repo template ..."
      cp "$NGINX_TEMPLATE" "$NGINX_AVAIL"
      ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
      ok "Nginx vhost installed from ${NGINX_TEMPLATE}"
      warn "Review /etc/nginx/sites-available/${NGINX_SITE_NAME} and update server_name before going live"
    else
      warn "No nginx vhost found for '${NGINX_SITE_NAME}'."
      warn "Install with:"
      warn "  sudo cp ${REPO_DIR}/config/nginx/murphy-production.conf \\"
      warn "          /etc/nginx/sites-available/murphy-production"
      warn "  sudo ln -sf /etc/nginx/sites-available/murphy-production \\"
      warn "              /etc/nginx/sites-enabled/murphy-production"
    fi

    if nginx -t -q 2>/dev/null; then
      systemctl reload nginx 2>/dev/null || true
      ok "Nginx config valid — reloaded"
    else
      warn "Nginx config test failed — NOT reloading. Run: sudo nginx -t"
    fi
  else
    warn "Nginx not installed — website unreachable externally on ports 80/443"
    warn "Install: apt-get install nginx && cp config/nginx/murphy-production.conf /etc/nginx/sites-available/murphy-production"
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
# STEP 6 — Docker Compose support services
#   Uses docker-compose.hetzner.yml which contains ONLY support services
#   (no murphy-api container) so there is no port :8000 conflict with
#   the murphy-production systemd service.
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 6 — Docker Compose Support Services (DB · Cache · Monitoring · Mail)"
if [ "$SKIP_DOCKER" = false ]; then
  if [ ! -f "$COMPOSE_FILE" ]; then
    fail "Compose file not found: ${COMPOSE_FILE}. Set MURPHY_COMPOSE_FILE."
  fi

  # Build docker compose command with --env-file pointing to production secrets
  COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"
  if [ -f "$MURPHY_ENV_FILE" ]; then
    COMPOSE_CMD="${COMPOSE_CMD} --env-file ${MURPHY_ENV_FILE}"
  else
    warn "Env file ${MURPHY_ENV_FILE} not found — docker compose may fail on required vars"
  fi

  # Generate self-signed TLS certificates for mail server if they don't exist
  MAIL_KEY="${REPO_DIR}/config/mail/ssl/mail.murphy.systems-key.pem"
  MAIL_CERT="${REPO_DIR}/config/mail/ssl/mail.murphy.systems-cert.pem"
  MAIL_CA="${REPO_DIR}/config/mail/ssl/demoCA/cacert.pem"
  if [ ! -f "$MAIL_KEY" ] || [ ! -f "$MAIL_CERT" ] || [ ! -f "$MAIL_CA" ]; then
    info "Generating self-signed TLS certificates for mail server ..."
    mkdir -p "${REPO_DIR}/config/mail/ssl/demoCA"
    openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
      -keyout "$MAIL_KEY" -out "$MAIL_CERT" \
      -subj "/CN=${MURPHY_MAIL_HOSTNAME:-mail.murphy.systems}"
    cp "$MAIL_CERT" "$MAIL_CA"
    ok "Self-signed TLS certificates generated"
  fi

  info "Pulling latest Docker images ..."
  ${COMPOSE_CMD} pull --quiet 2>/dev/null \
    || warn "Some images could not be pulled (continuing with cached versions)"

  # ── Docker disk space check ───────────────────────────────────────────────────
  _docker_avail_kb=$(df -k /var/lib/docker 2>/dev/null | awk 'NR==2{print $4}' \
    || df -k / 2>/dev/null | awk 'NR==2{print $4}' || echo "")
  if [ -n "${_docker_avail_kb}" ] && [ "${_docker_avail_kb}" -lt 2097152 ]; then
    warn "Low disk space for Docker: $(( _docker_avail_kb / 1024 )) MB free — pruning unused resources ..."
    docker system prune -f 2>/dev/null || true
    ok "Docker system pruned"
  fi
  unset _docker_avail_kb

  # ── Port conflict detection ───────────────────────────────────────────────────
  for _port in 5432 6379 9090 3000 25 587 993; do
    if ss -ltnp 2>/dev/null | grep -q ":${_port}[[:space:]]" \
        || ss -ltnp 2>/dev/null | grep -q ":${_port}$"; then
      # Only warn if it's not already one of our docker containers
      if ! docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":${_port}->"; then
        _conflict=$(ss -ltnp 2>/dev/null | grep ":${_port}" | grep -oP '"[^"]+"' | head -1 || echo "unknown process")
        warn "Port ${_port} already in use by ${_conflict} — may conflict with Docker services"
      fi
    fi
  done
  unset _port _conflict

  # ── Detect containers stuck in restart loops ──────────────────────────────────
  _looping=$(docker ps --format '{{.Names}}\t{{.Status}}' 2>/dev/null \
    | grep -i "restarting" || true)
  if [ -n "${_looping}" ]; then
    warn "Containers in restart loop detected:"
    echo "${_looping}" | while IFS= read -r _line; do warn "  ${_line}"; done
    if [ "${REPAIR}" = true ]; then
      warn "--repair: stopping restart-looping containers ..."
      echo "${_looping}" | awk '{print $1}' | xargs docker stop 2>/dev/null || true
      echo "${_looping}" | awk '{print $1}' | xargs docker rm -f 2>/dev/null || true
      ok "Restart-looping containers removed"
    else
      warn "  Re-run with --repair to forcibly remove these containers (may lose data)"
    fi
  fi
  unset _looping _line

  # ── Bring down orphaned/renamed services before up ────────────────────────────
  if [ "${REPAIR}" = true ]; then
    info "--repair: running docker compose down --remove-orphans ..."
    ${COMPOSE_CMD} down --remove-orphans 2>/dev/null || true
  fi

  info "Starting all support services ..."
  ${COMPOSE_CMD} up -d --remove-orphans

  echo ""
  ${COMPOSE_CMD} ps \
    --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null \
    || ${COMPOSE_CMD} ps
  echo ""
  ok "Docker Compose support services are up"
else
  info "Skipping Docker Compose (--skip-docker)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Mail provisioning (idempotent mailbox setup via mail_setup.sh)
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
      info "Mailserver still starting — waiting up to 180 s for it to become healthy ..."
      MAIL_WAIT=0
      MAIL_WAIT_MAX=180
      while [ "$MAIL_WAIT" -lt "$MAIL_WAIT_MAX" ]; do
        sleep 10
        MAIL_WAIT=$((MAIL_WAIT + 10))
        MAIL_STATUS=$(docker inspect --format='{{.State.Health.Status}}' murphy-mailserver 2>/dev/null || echo "missing")
        if [ "$MAIL_STATUS" = "healthy" ]; then
          break
        fi
        info "Still waiting ... (${MAIL_WAIT}s / ${MAIL_WAIT_MAX}s, status: ${MAIL_STATUS})"
      done
      if [ "$MAIL_STATUS" = "healthy" ]; then
        info "Running mail_setup.sh (mailbox provisioning) ..."
        bash "$MAIL_SETUP" || warn "mail_setup.sh reported errors — check mailboxes manually"
        ok "Mail provisioning complete"
      else
        warn "Mailserver did not become healthy within ${MAIL_WAIT_MAX}s (status: ${MAIL_STATUS})"
        warn "  Re-run manually: bash ${MAIL_SETUP}"
      fi
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
#   Serves: REST API · Website (static HTML via FastAPI StaticFiles) ·
#           Matrix IM bridge · Slack/Twilio integrations · /metrics
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 8 — Murphy System Application (systemd)"
if ! systemctl list-unit-files "${SERVICE_NAME}.service" &>/dev/null \
    || systemctl list-unit-files "${SERVICE_NAME}.service" | grep -q "not-found"; then
  warn "systemd unit '${SERVICE_NAME}' not installed."
  warn "Install it with:"
  warn "  sudo cp ${REPO_DIR}/config/systemd/murphy-production.service \\"
  warn "          /etc/systemd/system/murphy-production.service"
  warn "  sudo systemctl daemon-reload && sudo systemctl enable murphy-production"
else
  # Write the current deploy commit into the environment file so systemd picks
  # it up on restart and /api/health?deep=true reports the correct SHA.
  # systemctl restart does NOT inherit the calling shell's env variables, so
  # a simple `MURPHY_DEPLOY_COMMIT=x systemctl restart ...` does nothing.
  if [ -f "$MURPHY_ENV_FILE" ]; then
    # Remove any existing MURPHY_DEPLOY_COMMIT line then append the new one
    sed -i '/^MURPHY_DEPLOY_COMMIT=/d' "$MURPHY_ENV_FILE"
    echo "MURPHY_DEPLOY_COMMIT=${DEPLOY_COMMIT}" >> "$MURPHY_ENV_FILE"
    ok "MURPHY_DEPLOY_COMMIT=${DEPLOY_COMMIT} written to ${MURPHY_ENV_FILE}"
  else
    warn "Env file not found at ${MURPHY_ENV_FILE} — MURPHY_DEPLOY_COMMIT not persisted"
  fi
  info "Restarting ${SERVICE_NAME} (commit: ${DEPLOY_COMMIT}) ..."
  systemctl restart "${SERVICE_NAME}"
  ok "${SERVICE_NAME} restarted"

  # ── Check installed unit file matches repo template ───────────────────────────
  _unit_installed="/etc/systemd/system/${SERVICE_NAME}.service"
  _unit_template="${REPO_DIR}/config/systemd/murphy-production.service"
  if [ -f "${_unit_installed}" ] && [ -f "${_unit_template}" ]; then
    if ! diff -q "${_unit_installed}" "${_unit_template}" &>/dev/null; then
      warn "Installed systemd unit differs from repo template — may be outdated"
      warn "  To update: sudo cp ${_unit_template} ${_unit_installed} && sudo systemctl daemon-reload"
    else
      ok "Systemd unit file is up to date"
    fi
  fi
  unset _unit_installed _unit_template

  # ── Journal disk usage warning ────────────────────────────────────────────────
  if command -v journalctl &>/dev/null; then
    _jinfo=$(journalctl --disk-usage 2>/dev/null || true)
    if [ -n "${_jinfo}" ]; then
      # Warn if journals consume ≥ 2 GiB (match "2 GiB", "2.5 GiB", "10 GiB", etc.)
      if echo "${_jinfo}" | grep -qE '[2-9][0-9]*(\.[0-9]+)?[[:space:]]+GiB|[1-9][0-9]{1,}(\.[0-9]+)?[[:space:]]+TiB'; then
        _jusage=$(echo "${_jinfo}" | grep -oE '[0-9.]+ [KMGT]iB' | head -1 || echo "large")
        warn "Journal logs consuming ${_jusage} of disk space"
        warn "  To limit: sudo journalctl --vacuum-size=500M"
      else
        _jusage=$(echo "${_jinfo}" | grep -oE '[0-9.]+ [KMGT]iB' | head -1 || echo "ok")
        ok "Journal size: ${_jusage}"
      fi
      unset _jinfo _jusage
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Health checks
# ═══════════════════════════════════════════════════════════════════════════════
section "Step 9 — Health Checks"
if [ "$SKIP_HEALTH" = false ]; then
  echo ""
  printf "  %-40s %s\n" "Subsystem" "Result"
  printf "  %-40s %s\n" "──────────────────────────────────────" "──────"

  # Murphy API — retry with up to 60 s so that a slow first-boot or a
  # systemd RestartSec=10 cycle does not produce a false failure.
  wait_for_http "Murphy API           :${MURPHY_PORT}" \
    "http://localhost:${MURPHY_PORT}/api/health" 60 5

  # Website through nginx (the public entry point)
  if command -v nginx &>/dev/null && systemctl is-active --quiet nginx 2>/dev/null; then
    http_check "Website via Nginx (port 80)" \
      "http://localhost/api/health" \
      || http_check "Website via Nginx (port 443)" \
           "https://localhost/api/health" 2>/dev/null || true
  fi

  # Onboard LLM
  if [ "$SKIP_OLLAMA" = false ]; then
    http_check "Ollama / Onboard LLM :${OLLAMA_PORT}" \
      "http://localhost:${OLLAMA_PORT}/api/tags" || true
  fi

  if [ "$SKIP_DOCKER" = false ]; then
    # PostgreSQL
    if docker exec murphy-postgres pg_isready -U murphy -d murphy \
        >/dev/null 2>&1; then
      ok "PostgreSQL (murphy-postgres)      — accepting connections"
    else
      warn "PostgreSQL not ready — check: docker logs murphy-postgres"
    fi

    # Redis — check Docker health status first (handles password-protected Redis)
    REDIS_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' murphy-redis 2>/dev/null || echo "unknown")
    if [ "$REDIS_HEALTH" = "healthy" ]; then
      ok "Redis      (murphy-redis)         — healthy"
    elif docker exec murphy-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
      ok "Redis      (murphy-redis)         — PONG"
    else
      warn "Redis not ready — check: docker logs murphy-redis"
    fi

    # Prometheus
    http_check "Prometheus           :${PROMETHEUS_PORT}" \
      "http://localhost:${PROMETHEUS_PORT}/-/healthy" || true

    # Grafana
    http_check "Grafana              :${GRAFANA_PORT}" \
      "http://localhost:${GRAFANA_PORT}/api/health" || true

    # Mailserver SMTP
    if docker exec murphy-mailserver \
        sh -c 'ss -lntp 2>/dev/null | grep -q ":25"' 2>/dev/null; then
      ok "Mail SMTP  (murphy-mailserver)    — :25 listening"
    else
      warn "Mail SMTP not ready — check: docker logs murphy-mailserver"
    fi

    # Mailserver IMAPS
    if docker exec murphy-mailserver \
        sh -c 'ss -lntp 2>/dev/null | grep -q ":993"' 2>/dev/null; then
      ok "Mail IMAPS (murphy-mailserver)    — :993 listening"
    else
      warn "Mail IMAPS not ready — check: docker logs murphy-mailserver"
    fi

    # Roundcube
    http_check "Webmail / Roundcube  :${WEBMAIL_PORT}" \
      "http://localhost:${WEBMAIL_PORT}/" || true
  fi

  # Matrix IM bridge (in-process — probe via Murphy API)
  MATRIX_JSON=$(curl -sf --max-time 5 \
    "http://localhost:${MURPHY_PORT}/api/matrix/status" 2>/dev/null || echo '{}')
  if echo "$MATRIX_JSON" | grep -q '"connected":true'; then
    ok "Matrix IM bridge                   — connected"
  else
    HOMESERVER=$(echo "$MATRIX_JSON" | \
      python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(d.get('homeserver','not configured'))" \
      2>/dev/null || echo "?")
    if [ -n "${MATRIX_ACCESS_TOKEN:-}" ]; then
      warn "Matrix IM bridge not connected (homeserver: ${HOMESERVER}) — check MATRIX_* vars"
    else
      warn "Matrix IM bridge inactive — set MATRIX_ACCESS_TOKEN to enable (optional)"
    fi
  fi

  # Nginx summary
  if command -v nginx &>/dev/null; then
    if systemctl is-active --quiet nginx 2>/dev/null; then
      ok "Nginx (reverse proxy)              — active"
    else
      warn "Nginx is not active — run: sudo systemctl start nginx"
    fi
  fi
  echo ""
else
  info "Skipping health checks (--no-health-check)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo -e "    ${GREEN}MURPHY FULL-STACK LOADED — commit ${DEPLOY_COMMIT}${NC}   "
echo "  ☠  ══════════════════════════════════════════════════════════════  ☠"
echo ""
echo -e "  ${BLUE}Website (public):${NC}    https://<your-domain>/            (nginx)"
echo -e "  ${BLUE}Murphy API:${NC}          http://localhost:${MURPHY_PORT}/api/health"
echo -e "  ${BLUE}Onboard LLM:${NC}         http://localhost:${OLLAMA_PORT}/api/tags"
echo -e "  ${BLUE}Grafana:${NC}             http://localhost:${GRAFANA_PORT}  (or /grafana/ via nginx)"
echo -e "  ${BLUE}Prometheus:${NC}          http://localhost:${PROMETHEUS_PORT}"
echo -e "  ${BLUE}Webmail:${NC}             http://localhost:${WEBMAIL_PORT}  (or /mail/ via nginx)"
echo -e "  ${BLUE}Matrix bridge:${NC}       http://localhost:${MURPHY_PORT}/api/matrix/status"
echo ""
echo -e "  App logs: ${YELLOW}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  Stack:    ${YELLOW}docker compose -f ${COMPOSE_FILE} ps${NC}"
echo ""

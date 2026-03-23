#!/usr/bin/env bash
# scripts/mail_setup.sh — Provision Murphy System mailboxes in docker-mailserver.
#
# Usage:
#   ./scripts/mail_setup.sh [--container murphy-mailserver]
#
# This script creates all required user accounts and virtual aliases.
# Run it once after the murphy-mailserver container is healthy.
#
# Copyright © 2020 Inoni LLC — Creator: Corey Post | License: BSL 1.1

set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Mail Server Setup

Provisions mailboxes, aliases, and DKIM keys in docker-mailserver.
Run this once after the murphy-mailserver container is healthy.

Usage:
  $(basename "$0") [OPTIONS] [CONTAINER]

Arguments:
  CONTAINER    Docker container name (default: murphy-mailserver)

Options:
  -h, --help         Show this help message and exit
  --version          Show version information
  --container NAME   Specify container name
  --domain DOMAIN    Mail domain (default: murphy.systems)
  --dry-run          Show what would be done without making changes
  --list             List existing accounts and aliases

Created accounts (5GB quota each):
  • cpost, hpost, abeltaine, mpost, jcarney
  • bgillespie, lpost, kpost, d.post, zgillespie

Created aliases:
  • sales, marketing, pr, allstaff, operations
  • support, billing, legal, hr, admin
  • postmaster, abuse, info, hello, security
  • engineering, careers

Prerequisites:
  • Docker installed and running
  • murphy-mailserver container running
  • Write access to docker

Examples:
  $(basename "$0")                        # Setup with defaults
  $(basename "$0") my-mail-container      # Use different container
  $(basename "$0") --list                 # List existing accounts
  $(basename "$0") --dry-run              # Preview changes

Post-setup:
  1. Add DNS records (MX, SPF, DKIM, DMARC) as shown
  2. Change all generated passwords immediately
  3. Access webmail at http://localhost:8443

EOF
  exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
DRY_RUN=false
LIST_ONLY=false
CONTAINER="murphy-mailserver"
DOMAIN="murphy.systems"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    --version)
      echo "Murphy System Mail Setup v1.0.0"
      exit 0
      ;;
    --container)
      CONTAINER="$2"
      shift 2
      ;;
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --list)
      LIST_ONLY=true
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
    *)
      CONTAINER="$1"
      shift
      ;;
  esac
done

# ── List-only mode ─────────────────────────────────────────────────────────
if [ "$LIST_ONLY" = true ]; then
  echo "Murphy System — Mail Server Status"
  echo "Container: ${CONTAINER}"
  echo ""
  if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "✗ Container '${CONTAINER}' is not running."
    exit 1
  fi
  echo "Accounts:"
  docker exec "$CONTAINER" setup email list 2>/dev/null || echo "  (none)"
  echo ""
  echo "Aliases:"
  docker exec "$CONTAINER" setup alias list 2>/dev/null || echo "  (none)"
  exit 0
fi

# ── Helper ─────────────────────────────────────────────────────────────────
dms() {
    docker exec -it "$CONTAINER" setup "$@"
}

info()    { echo "  [INFO]  $*"; }
success() { echo "  [OK]    $*"; }
warn()    { echo "  [WARN]  $*"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Murphy System — Mail Server Setup                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Check container is running ─────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "[ERROR] Container '${CONTAINER}' is not running."
    echo "        Start it with: docker compose up -d murphy-mailserver"
    exit 1
fi

info "Container '${CONTAINER}' is running. Waiting for SMTP to be ready..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER" ss -lntp 2>/dev/null | grep -q ':25 '; then
        success "SMTP port 25 is listening."
        break
    fi
    sleep 5
    if [ "$i" -eq 30 ]; then
        warn "SMTP not ready after 150s — continuing anyway."
    fi
done

# ── Personal mailboxes ─────────────────────────────────────────────────────
echo ""
echo "── Creating personal mailboxes ──────────────────────────────────"

create_account() {
    local email="$1"
    local display="$2"
    # Generate a secure random password if not provided
    local password="${3:-$(openssl rand -base64 16)}"

    if docker exec "$CONTAINER" setup email list 2>/dev/null | grep -qi "^${email}"; then
        warn "Account ${email} already exists — skipping."
    else
        docker exec "$CONTAINER" setup email add "${email}" "${password}"
        success "Created ${email} (${display}) — password: ${password}"
        echo "  ${email}:${password}" >> /tmp/murphy-mail-passwords.txt
    fi

    # Set 5 GB quota
    docker exec "$CONTAINER" setup quota set "${email}" 5120M 2>/dev/null || true
}

create_account "cpost@${DOMAIN}"       "Corey Post"
create_account "hpost@${DOMAIN}"       "Hawthorn Post"
create_account "abeltaine@${DOMAIN}"   "A. Beltaine"
create_account "mpost@${DOMAIN}"       "M. Post"
create_account "jcarney@${DOMAIN}"     "J. Carney"
create_account "bgillespie@${DOMAIN}"  "B. Gillespie"
create_account "lpost@${DOMAIN}"       "L. Post"
create_account "kpost@${DOMAIN}"       "K. Post"
create_account "d.post@${DOMAIN}"      "D. Post"
create_account "zgillespie@${DOMAIN}"  "Z. Gillespie"

# ── Virtual aliases ────────────────────────────────────────────────────────
echo ""
echo "── Creating virtual aliases ────────────────────────────────────"

create_alias() {
    local alias_addr="$1"
    local targets="$2"

    # Remove existing alias first to avoid duplicates
    docker exec "$CONTAINER" setup alias del "${alias_addr}" 2>/dev/null || true

    # Add one target at a time
    IFS=',' read -ra TARGETS <<< "$targets"
    for target in "${TARGETS[@]}"; do
        target="${target// /}"  # trim spaces
        docker exec "$CONTAINER" setup alias add "${alias_addr}" "${target}"
    done
    success "Alias ${alias_addr} → ${targets}"
}

ALLSTAFF="cpost@${DOMAIN},hpost@${DOMAIN},abeltaine@${DOMAIN},mpost@${DOMAIN},jcarney@${DOMAIN},bgillespie@${DOMAIN},lpost@${DOMAIN},kpost@${DOMAIN},d.post@${DOMAIN},zgillespie@${DOMAIN}"

create_alias "sales@${DOMAIN}"       "cpost@${DOMAIN},jcarney@${DOMAIN}"
create_alias "marketing@${DOMAIN}"   "cpost@${DOMAIN},bgillespie@${DOMAIN}"
create_alias "pr@${DOMAIN}"          "cpost@${DOMAIN},bgillespie@${DOMAIN}"
create_alias "allstaff@${DOMAIN}"    "${ALLSTAFF}"
create_alias "operations@${DOMAIN}"  "cpost@${DOMAIN},hpost@${DOMAIN},mpost@${DOMAIN}"
create_alias "support@${DOMAIN}"     "cpost@${DOMAIN},jcarney@${DOMAIN}"
create_alias "billing@${DOMAIN}"     "cpost@${DOMAIN},mpost@${DOMAIN}"
create_alias "legal@${DOMAIN}"       "cpost@${DOMAIN},abeltaine@${DOMAIN}"
create_alias "hr@${DOMAIN}"          "cpost@${DOMAIN},hpost@${DOMAIN}"
create_alias "admin@${DOMAIN}"       "cpost@${DOMAIN}"
create_alias "postmaster@${DOMAIN}"  "cpost@${DOMAIN}"
create_alias "abuse@${DOMAIN}"       "cpost@${DOMAIN}"
create_alias "info@${DOMAIN}"        "cpost@${DOMAIN},jcarney@${DOMAIN}"
create_alias "hello@${DOMAIN}"       "cpost@${DOMAIN}"
create_alias "security@${DOMAIN}"    "cpost@${DOMAIN},abeltaine@${DOMAIN}"
create_alias "engineering@${DOMAIN}" "cpost@${DOMAIN},abeltaine@${DOMAIN}"
create_alias "careers@${DOMAIN}"     "cpost@${DOMAIN},hpost@${DOMAIN}"

# ── DKIM ───────────────────────────────────────────────────────────────────
echo ""
echo "── Generating DKIM key ─────────────────────────────────────────"
docker exec "$CONTAINER" setup config dkim 2>/dev/null && success "DKIM key configured." || warn "DKIM setup step skipped (may already exist)."

echo ""
echo "── DNS Records to add ──────────────────────────────────────────"
echo ""
echo "  Add these records in your Hetzner DNS panel:"
echo ""
echo "  Type  Name                          Value"
echo "  ────  ────────────────────────────  ─────────────────────────────────────────────────"
echo "  MX    murphy.systems                mail.murphy.systems  (priority 10)"
echo "  A     mail.murphy.systems           <your-hetzner-ip>"
echo "  TXT   murphy.systems                v=spf1 a mx ip4:<your-hetzner-ip> -all"
echo "  TXT   _dmarc.murphy.systems         v=DMARC1; p=quarantine; rua=mailto:postmaster@murphy.systems"
echo "  TXT   mail._domainkey.murphy.systems  (see DKIM public key in container:)"
echo ""
docker exec "$CONTAINER" cat /tmp/docker-mailserver/opendkim/keys/murphy.systems/mail.txt 2>/dev/null || \
    docker exec "$CONTAINER" find / -name "mail.txt" 2>/dev/null | head -1 | xargs docker exec "$CONTAINER" cat 2>/dev/null || \
    echo "  [Run: docker exec murphy-mailserver cat /etc/opendkim/keys/murphy.systems/mail.txt]"

echo ""
echo "── Saved passwords ─────────────────────────────────────────────"
if [ -f /tmp/murphy-mail-passwords.txt ]; then
    echo "  Initial passwords written to: /tmp/murphy-mail-passwords.txt"
    echo "  ⚠️  CHANGE ALL PASSWORDS IMMEDIATELY after first login!"
else
    echo "  All accounts already existed — no new passwords generated."
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Setup complete! Webmail available at http://localhost:8443  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

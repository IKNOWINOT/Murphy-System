#!/usr/bin/env bash
# backup.sh — Murphy System
#
# Backs up all persistent Murphy System data to a timestamped directory.
# Safe to run while the stack is live (hot backups).
#
# Backed up:
#   • PostgreSQL database (hot dump via pg_dump)
#   • Murphy persistence JSON state files (.murphy_persistence/)
#   • Mailserver data volume
#   • Environment file (secrets)
#   • Grafana data volume
#   • Redis data volume
#
# Retention: 7 days (older backup directories are removed automatically)
#
# Usage:
#   bash /opt/Murphy-System/scripts/backup.sh
#
# Cron (nightly at 03:00):
#   0 3 * * * root /opt/Murphy-System/scripts/backup.sh >> /var/log/murphy-backup.log 2>&1

set -euo pipefail

BACKUP_ROOT="/opt/backups/murphy"
BACKUP_DIR="${BACKUP_ROOT}/$(date +%Y-%m-%d)"
REPO_DIR="${MURPHY_REPO_DIR:-/opt/Murphy-System}"
MURPHY_ENV_FILE="${MURPHY_ENV_FILE:-/etc/murphy-production/environment}"

mkdir -p "$BACKUP_DIR"

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting Murphy backup → ${BACKUP_DIR}"

# ── PostgreSQL ────────────────────────────────────────────────────────────────
echo "  → PostgreSQL..."
docker exec murphy-postgres pg_dump -U murphy murphy \
  | gzip > "${BACKUP_DIR}/postgres.sql.gz"
echo "     ✓ postgres.sql.gz"

# ── Murphy persistence (JSON state files) ─────────────────────────────────────
echo "  → Murphy persistence..."
if [ -d "${REPO_DIR}/.murphy_persistence" ]; then
  tar czf "${BACKUP_DIR}/murphy-persistence.tar.gz" \
    -C "$REPO_DIR" .murphy_persistence/
  echo "     ✓ murphy-persistence.tar.gz"
else
  echo "     (no .murphy_persistence directory — skipping)"
fi

# ── Mailserver data volume ────────────────────────────────────────────────────
echo "  → Mailserver data..."
docker run --rm \
  -v mailserver-data:/data \
  -v "${BACKUP_DIR}":/backup \
  alpine tar czf /backup/mailserver-data.tar.gz -C /data . 2>/dev/null \
  && echo "     ✓ mailserver-data.tar.gz" \
  || echo "     (mailserver-data volume not found — skipping)"

# ── Environment file (secrets) ────────────────────────────────────────────────
echo "  → Environment file..."
if [ -f "$MURPHY_ENV_FILE" ]; then
  cp "$MURPHY_ENV_FILE" "${BACKUP_DIR}/environment.bak"
  chmod 600 "${BACKUP_DIR}/environment.bak"
  echo "     ✓ environment.bak"
else
  echo "     (${MURPHY_ENV_FILE} not found — skipping)"
fi

# ── Grafana data volume ───────────────────────────────────────────────────────
echo "  → Grafana..."
docker run --rm \
  -v grafana-data:/data \
  -v "${BACKUP_DIR}":/backup \
  alpine tar czf /backup/grafana-data.tar.gz -C /data . 2>/dev/null \
  && echo "     ✓ grafana-data.tar.gz" \
  || echo "     (grafana-data volume not found — skipping)"

# ── Redis data volume ─────────────────────────────────────────────────────────
echo "  → Redis..."
docker run --rm \
  -v redis-data:/data \
  -v "${BACKUP_DIR}":/backup \
  alpine tar czf /backup/redis-data.tar.gz -C /data . 2>/dev/null \
  && echo "     ✓ redis-data.tar.gz" \
  || echo "     (redis-data volume not found — skipping)"

# ── Retention: prune backups older than 7 days ────────────────────────────────
echo "  → Pruning backups older than 7 days..."
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -mtime +7 -type d -exec rm -rf {} +
echo "     ✓ pruned"

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Backup complete → ${BACKUP_DIR}"
ls -lh "$BACKUP_DIR"

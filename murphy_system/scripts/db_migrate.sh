#!/usr/bin/env bash
# scripts/db_migrate.sh — Murphy System database migration helper
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Usage:
#   ./scripts/db_migrate.sh              # Apply all pending migrations
#   ./scripts/db_migrate.sh status       # Show current migration status
#   ./scripts/db_migrate.sh downgrade -1 # Revert the last migration
#   ./scripts/db_migrate.sh history      # Show migration history
#   ./scripts/db_migrate.sh stamp head   # Mark current DB as up-to-date
#
# Environment variables:
#   DATABASE_URL   — SQLAlchemy connection URL (required for live mode)
#   MURPHY_ENV     — Runtime environment (development|test|staging|production)
#
# The script must be run from the "murphy_system/" directory (project root).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# ── Validate environment ─────────────────────────────────────────────────────
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  ⚠️  WARNING: DATABASE_URL is not set                            ║"
  echo "║                                                                  ║"
  echo "║  Alembic will use the default from alembic.ini:                 ║"
  echo "║    sqlite:///murphy_logs.db                                      ║"
  echo "║                                                                  ║"
  echo "║  To use a real database, set DATABASE_URL before running:        ║"
  echo "║    export DATABASE_URL=postgresql://user:pass@host:5432/murphy   ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo ""
else
  echo "Using DATABASE_URL: ${DATABASE_URL//:*@/:***@}"
fi

COMMAND="${1:-upgrade}"
ARGS="${@:2}"

# Map shorthand commands
case "${COMMAND}" in
  up|upgrade)
    ALEMBIC_CMD="upgrade"
    ALEMBIC_ARGS="${ARGS:-head}"
    ;;
  down|downgrade)
    ALEMBIC_CMD="downgrade"
    ALEMBIC_ARGS="${ARGS:--1}"
    ;;
  status|current)
    ALEMBIC_CMD="current"
    ALEMBIC_ARGS=""
    ;;
  history)
    ALEMBIC_CMD="history"
    ALEMBIC_ARGS="${ARGS:---verbose}"
    ;;
  stamp)
    ALEMBIC_CMD="stamp"
    ALEMBIC_ARGS="${ARGS:-head}"
    ;;
  heads)
    ALEMBIC_CMD="heads"
    ALEMBIC_ARGS=""
    ;;
  branches)
    ALEMBIC_CMD="branches"
    ALEMBIC_ARGS=""
    ;;
  *)
    # Pass through any other alembic command verbatim
    ALEMBIC_CMD="${COMMAND}"
    ALEMBIC_ARGS="${ARGS}"
    ;;
esac

echo "Running: alembic ${ALEMBIC_CMD} ${ALEMBIC_ARGS}"
echo ""

# Run alembic with DATABASE_URL override so the ini default is never used
# in production accidentally.
if [[ -n "${DATABASE_URL:-}" ]]; then
  python -m alembic -x "db_url=${DATABASE_URL}" ${ALEMBIC_CMD} ${ALEMBIC_ARGS}
else
  python -m alembic ${ALEMBIC_CMD} ${ALEMBIC_ARGS}
fi

echo ""
echo "Done."

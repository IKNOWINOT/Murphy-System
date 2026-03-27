#!/bin/sh
# Murphy System — Production Docker Entrypoint
#
# Environment variables (with defaults):
#   MURPHY_AUTO_MIGRATE  — set to "true" to run Alembic migrations on startup
#   MURPHY_WORKERS       — number of uvicorn workers (defaults to nproc)
#   MURPHY_PORT          — port to listen on (default: 8000)
#   MURPHY_LOG_LEVEL     — uvicorn log level (default: warning)
#
# Copyright © 2020 Inoni Limited Liability Company
# License: BSL-1.1

set -e

# ---------------------------------------------------------------------------
# Worker count — default to number of CPU cores
# ---------------------------------------------------------------------------
MURPHY_WORKERS="${MURPHY_WORKERS:-$(nproc)}"
MURPHY_PORT="${MURPHY_PORT:-8000}"
MURPHY_LOG_LEVEL="${MURPHY_LOG_LEVEL:-warning}"

echo "[entrypoint] Murphy System starting"
echo "[entrypoint] Workers : ${MURPHY_WORKERS}"
echo "[entrypoint] Port    : ${MURPHY_PORT}"
echo "[entrypoint] Log lvl : ${MURPHY_LOG_LEVEL}"

# ---------------------------------------------------------------------------
# Optional database migrations
# ---------------------------------------------------------------------------
if [ "${MURPHY_AUTO_MIGRATE:-false}" = "true" ]; then
    echo "[entrypoint] Running Alembic migrations..."
    alembic upgrade head
    echo "[entrypoint] Migrations complete."
fi

# ---------------------------------------------------------------------------
# Start uvicorn with production settings
# ---------------------------------------------------------------------------
exec uvicorn src.runtime.app:create_app \
    --factory \
    --host 0.0.0.0 \
    --port "${MURPHY_PORT}" \
    --workers "${MURPHY_WORKERS}" \
    --log-level "${MURPHY_LOG_LEVEL}" \
    --no-access-log \
    --timeout-keep-alive 65

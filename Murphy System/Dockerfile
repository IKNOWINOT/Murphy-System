# Murphy System 1.0 - Production Dockerfile
# Multi-stage build for minimal image size
#
# Copyright © 2020 Inoni Limited Liability Company
# License: BSL-1.1

# ---------------------------------------------------------------------------
# Stage 1: Install Python dependencies in an isolated layer
# ---------------------------------------------------------------------------
# PROD-HARD-DOCKER-001 (audit G21): base image is unpinned by digest.
# Pinning to `python:3.12-slim@sha256:...` requires resolving the current
# digest from the registry under controlled-network conditions; deferred
# to the dependency-update PR that will also drive the murphy_1.0 floor
# bumps. Tracker: open follow-up issue.
FROM python:3.12-slim AS deps

WORKDIR /app

COPY requirements_murphy_1.0.txt .

# Install build tools needed for some wheels, then clean up
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && pip install --no-cache-dir -r requirements_murphy_1.0.txt \
    && apt-get purge -y gcc g++ \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Stage 2: Production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

WORKDIR /app

# Security: run as non-root user
# PROD-HARD-DOCKER-001 (audit G22): create user EARLY so subsequent COPY
# steps can use --chown=murphy:murphy and never write as root.
RUN groupadd -r murphy && useradd -r -g murphy -s /usr/sbin/nologin murphy

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Runtime system dependencies (curl for healthcheck)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
# PROD-HARD-DOCKER-001 (audit A16): runtime references alembic/, static/,
# templates/, config/, root *.html files (69 of them — _deps.py mounts 138
# routes from these), and murphy_ui/. Previously only src/ was copied, so
# every UI/migration/config path 404'd in the production image.
COPY --chown=murphy:murphy src/ ./src/
COPY --chown=murphy:murphy alembic/ ./alembic/
COPY --chown=murphy:murphy alembic.ini ./alembic.ini
COPY --chown=murphy:murphy static/ ./static/
COPY --chown=murphy:murphy templates/ ./templates/
COPY --chown=murphy:murphy config/ ./config/
COPY --chown=murphy:murphy murphy_ui/ ./murphy_ui/
COPY --chown=murphy:murphy murphy/ ./murphy/
COPY --chown=murphy:murphy *.html ./
COPY --chown=murphy:murphy setup.py requirements_murphy_1.0.txt ./
COPY --chown=murphy:murphy murphy_system_1.0_runtime.py ./
COPY --chown=murphy:murphy scripts/docker-entrypoint.sh ./docker-entrypoint.sh

# Create persistent data directories
# PROD-HARD-DOCKER-001 (audit A20): explicit chmod +x guards against
# tarball/zip clones that drop POSIX mode bits.
RUN mkdir -p /app/data /app/logs \
    && chown -R murphy:murphy /app \
    && chmod +x /app/docker-entrypoint.sh

# Environment configuration
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MURPHY_ENV=production
ENV MURPHY_PORT=8000
ENV MURPHY_DATA_DIR=/app/data
ENV MURPHY_LOG_DIR=/app/logs

USER murphy

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["/app/docker-entrypoint.sh"]

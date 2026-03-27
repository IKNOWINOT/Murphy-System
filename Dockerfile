# Murphy System 1.0 - Production Dockerfile
# Multi-stage build for minimal image size
#
# Copyright © 2020 Inoni Limited Liability Company
# License: BSL-1.1

# ---------------------------------------------------------------------------
# Stage 1: Install Python dependencies in an isolated layer
# ---------------------------------------------------------------------------
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
RUN groupadd -r murphy && useradd -r -g murphy -s /usr/sbin/nologin murphy

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Runtime system dependencies (curl for healthcheck)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY src/ ./src/
COPY setup.py pyproject.toml requirements_murphy_1.0.txt ./
COPY murphy_system_1.0_runtime.py ./

# murphy_production_server.py is kept for standalone/dev use;
# in Docker the unified server (create_app) includes its routes via production_router.
COPY murphy_production_server.py ./

# Dashboard and UI assets
COPY murphy_dashboard/ ./murphy_dashboard/

# Root-level HTML pages (51 files served via /ui/{page_name})
COPY *.html ./

# Root-level JS (auth, overlay) and CLI entry point
COPY murphy_auth.js murphy_overlay.js murphy ./

# Murphy System legacy directory (HTML pages, static assets, config)
# NOTE: Space in directory name requires careful quoting
COPY "Murphy System/" "./Murphy System/"

# Config directory
COPY config/ ./config/

# Environment configuration
COPY .env.example ./

# Create persistent data directories
RUN mkdir -p /app/data /app/logs \
    && chown -R murphy:murphy /app

# Environment configuration
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MURPHY_ENV=production
ENV MURPHY_PORT=8000
ENV MURPHY_DATA_DIR=/app/data
ENV MURPHY_LOG_DIR=/app/logs

USER murphy

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "murphy_system_1.0_runtime.py"]
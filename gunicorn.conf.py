# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: gunicorn.conf.py
Subsystem: Production Deployment
Purpose: Gunicorn configuration for running Murphy System in production
         behind a reverse proxy (nginx / Caddy / cloud LB).
Status: Production

Usage:
    gunicorn murphy_production_server:app -c gunicorn.conf.py

Environment variables:
    WEB_CONCURRENCY  — number of worker processes (default: 4)
    MURPHY_PORT      — listen port (default: 8000)
    MURPHY_ENV       — runtime environment (development|staging|production)
"""
from __future__ import annotations

import multiprocessing
import os

# ---------------------------------------------------------------------------
# Worker configuration
# ---------------------------------------------------------------------------
_default_workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
workers = int(os.environ.get("WEB_CONCURRENCY", _default_workers))
worker_class = "uvicorn.workers.UvicornWorker"
worker_tmp_dir = "/dev/shm"  # fast worker heartbeat via shared memory

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
bind = f"0.0.0.0:{os.environ.get('MURPHY_PORT', 8000)}"
backlog = 2048

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = 120          # kill worker if it doesn't respond within 120 s
graceful_timeout = 30  # give 30 s for in-flight requests on SIGTERM
keepalive = 5          # keep TCP connections open for 5 s between requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# ---------------------------------------------------------------------------
# Process naming
# ---------------------------------------------------------------------------
proc_name = "murphy-api"

# ---------------------------------------------------------------------------
# Server hooks
# ---------------------------------------------------------------------------

def on_starting(server):
    """Log startup info."""
    server.log.info(
        "Murphy System starting — %d workers, bind=%s, env=%s",
        workers,
        bind,
        os.environ.get("MURPHY_ENV", "development"),
    )


def worker_exit(server, worker):
    """Log worker exit for monitoring."""
    server.log.info("Worker %s (pid %d) exiting", worker, worker.pid)

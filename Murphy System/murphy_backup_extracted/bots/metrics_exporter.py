"""Prometheus metrics exporter."""
from __future__ import annotations

from prometheus_client import Counter, start_http_server

REQUEST_COUNT = Counter('requests_total', 'Total requests processed')

_started = False

def start_metrics_server(port: int = 8001) -> None:
    global _started
    if _started:
        return
    start_http_server(port)
    _started = True

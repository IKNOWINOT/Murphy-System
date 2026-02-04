"""Simple Flask dashboard summarizing task status."""
from __future__ import annotations

try:
    from flask import Flask, jsonify
except Exception:  # pragma: no cover - optional dependency
    Flask = None
    jsonify = None

if Flask:
    app = Flask(__name__)
else:
    app = None

task_status: dict[str, dict[str, float]] = {}

if app is not None:
    @app.route('/status')
    def status() -> str:
        """Return JSON status for tasks."""
        return jsonify(task_status)


def run_dashboard(port: int = 8000) -> None:
    """Run the dashboard web server."""
    if app is None:
        raise ImportError('Flask is required for the dashboard')
    app.run(port=port)

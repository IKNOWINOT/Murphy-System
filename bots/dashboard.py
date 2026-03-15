"""Simple Flask dashboard summarizing task status."""
from __future__ import annotations

try:
    from flask import Flask, jsonify
except Exception:  # pragma: no cover - optional dependency
    Flask = None
    jsonify = None

try:
    from flask_security import configure_secure_app
except Exception:  # pragma: no cover - optional dependency
    configure_secure_app = None

if Flask:
    app = Flask(__name__)
    if configure_secure_app:
        configure_secure_app(app, service_name="bots-dashboard")
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

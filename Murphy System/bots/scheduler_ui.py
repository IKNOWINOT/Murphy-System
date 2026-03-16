"""Simple scheduler UI using Flask."""
from __future__ import annotations

try:
    from flask import Flask, request, jsonify
except Exception:  # pragma: no cover - optional dependency
    Flask = None
    request = None
    jsonify = None

try:
    from flask_security import configure_secure_app
except Exception:  # pragma: no cover - optional dependency
    configure_secure_app = None

if Flask:
    app = Flask(__name__)
    if configure_secure_app:
        configure_secure_app(app, service_name="bots-scheduler-ui")
    tasks: list[str] = []

    @app.route('/tasks', methods=['GET', 'POST'])
    def manage_tasks():
        if request.method == 'POST':
            task = request.json.get('task')
            tasks.append(task)
        return jsonify(tasks)

    @app.route('/tasks/reorder', methods=['POST'])
    def reorder():
        order = request.json.get('order', [])
        reordered = [tasks[i] for i in order if i < len(tasks)]
        tasks.clear()
        tasks.extend(reordered)
        return jsonify(tasks)
else:
    app = None


def run_scheduler_ui(port: int = 5000) -> None:
    if app is None:
        raise ImportError('Flask is required for scheduler UI')
    app.run(port=port)

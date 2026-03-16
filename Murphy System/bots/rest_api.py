from __future__ import annotations

"""Simple REST API for interacting with bots."""

from typing import Any

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

from .plugin_loader import load_plugins

BOTS: dict[str, Any] = {}

def register_bot(name: str, bot: Any) -> None:
    BOTS[name] = bot

app: Flask | None

if Flask:
    app = Flask(__name__)
    if configure_secure_app:
        configure_secure_app(app, service_name="bots-api")

    @app.route('/bots/<bot_id>/action', methods=['POST'])
    def execute(bot_id: str) -> Any:
        payload = request.json or {}
        bot = BOTS.get(bot_id)
        if not bot:
            return jsonify({'error': 'unknown bot'}), 404
        if hasattr(bot, 'handle'):
            result = bot.handle(payload)
        elif callable(bot):
            result = bot(payload)
        else:
            result = {'error': 'invalid bot'}
        return jsonify(result)
else:
    app = None


def run_api(port: int = 8000) -> None:
    if app is None:
        raise ImportError('Flask required for REST API')
    load_plugins()  # ensure plugins loaded before handling requests
    app.run(port=port)

if __name__ == "__main__":
    run_api()

__all__ = ['run_api', 'register_bot', 'BOTS']

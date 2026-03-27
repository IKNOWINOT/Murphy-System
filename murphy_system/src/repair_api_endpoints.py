"""
Repair System REST API Endpoints for the Murphy System.

Design Label: ARCH-006 — Repair System REST API
Owner: Backend Team

Exposes the Autonomous Repair System, Innovation Farmer, and Generative
Knowledge Builder as a Flask REST API, following Murphy's existing API
patterns from bots/rest_api.py and module_compiler/api/endpoints.py.

Endpoints:
  POST /api/repair/run              — Trigger full repair cycle
  GET  /api/repair/status           — Current repair status
  GET  /api/repair/history          — Past repair reports
  GET  /api/repair/wiring           — Front-end to back-end wiring report
  POST /api/repair/reconcile        — Trigger reconciliation loop
  GET  /api/repair/immune-memory    — View immune system memory
  POST /api/repair/innovate         — Trigger innovation farming scan
  GET  /api/repair/proposals        — View feature proposals
  POST /api/repair/knowledge/build  — Build knowledge set for an industry
  GET  /api/repair/knowledge/<industry> — Get knowledge set
  GET  /api/repair/terminology      — Get terminology concordance map
  GET  /api/health                  — System health (extended)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from flask import Blueprint, Flask, jsonify, request
    _FLASK_AVAILABLE = True
except Exception as exc:
    Blueprint = None  # type: ignore[assignment,misc]
    Flask = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]
    _FLASK_AVAILABLE = False
    logger.debug("Flask not available: %s", exc)

try:
    from autonomous_repair_system import AutonomousRepairSystem, DiagnosisLayer
    _REPAIR_AVAILABLE = True
except Exception as exc:
    AutonomousRepairSystem = None  # type: ignore[assignment,misc]
    DiagnosisLayer = None  # type: ignore[assignment]
    _REPAIR_AVAILABLE = False
    logger.debug("AutonomousRepairSystem not available: %s", exc)

try:
    from innovation_farmer import InnovationFarmer
    _FARMER_AVAILABLE = True
except Exception as exc:
    InnovationFarmer = None  # type: ignore[assignment,misc]
    _FARMER_AVAILABLE = False
    logger.debug("InnovationFarmer not available: %s", exc)

try:
    from generative_knowledge_builder import GenerativeKnowledgeBuilder
    _KNOWLEDGE_AVAILABLE = True
except Exception as exc:
    GenerativeKnowledgeBuilder = None  # type: ignore[assignment,misc]
    _KNOWLEDGE_AVAILABLE = False
    logger.debug("GenerativeKnowledgeBuilder not available: %s", exc)

# ---------------------------------------------------------------------------
# Shared singletons — lazy-initialised on first request
# ---------------------------------------------------------------------------

_repair_system: Optional[Any] = None
_innovation_farmer: Optional[Any] = None
_knowledge_builder: Optional[Any] = None


def _get_repair_system() -> Optional[Any]:
    """Return or initialise the AutonomousRepairSystem singleton."""
    global _repair_system
    if _repair_system is None and _REPAIR_AVAILABLE:
        src_root = os.path.join(os.path.dirname(__file__))
        project_root = os.path.dirname(src_root)
        _repair_system = AutonomousRepairSystem(
            src_root=src_root,
            project_root=project_root,
        )
    return _repair_system


def _get_innovation_farmer() -> Optional[Any]:
    """Return or initialise the InnovationFarmer singleton."""
    global _innovation_farmer
    if _innovation_farmer is None and _FARMER_AVAILABLE:
        _innovation_farmer = InnovationFarmer()
    return _innovation_farmer


def _get_knowledge_builder() -> Optional[Any]:
    """Return or initialise the GenerativeKnowledgeBuilder singleton."""
    global _knowledge_builder
    if _knowledge_builder is None and _KNOWLEDGE_AVAILABLE:
        _knowledge_builder = GenerativeKnowledgeBuilder()
    return _knowledge_builder


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------

def _error_response(message: str, code: int = 500) -> Tuple[Any, int]:
    """Return a JSON error response."""
    return jsonify({"error": message}), code


def _unavailable(component: str) -> Tuple[Any, int]:
    """Return a 503 when a component is not available."""
    return _error_response(f"{component} is not available", 503)


# ---------------------------------------------------------------------------
# Blueprint / route registration
# ---------------------------------------------------------------------------

def create_repair_blueprint() -> Any:
    """Create and return a Flask Blueprint for the repair API.

    Returns:
        A configured Flask Blueprint, or None if Flask is not available.
    """
    if not _FLASK_AVAILABLE:
        logger.warning("Flask not available; repair API blueprint not created")
        return None

    bp = Blueprint("repair", __name__, url_prefix="/api/repair")

    @bp.route("/run", methods=["POST"])
    def run_repair() -> Any:
        """Trigger a full autonomous repair cycle."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        body = request.get_json(silent=True) or {}
        max_iterations = int(body.get("max_iterations", 20))
        try:
            report = repair.run_repair_cycle(max_iterations=max_iterations)
            return jsonify({"status": "ok", "report": report.to_dict()})
        except RuntimeError as exc:
            return _error_response(str(exc), 409)
        except Exception as exc:
            logger.error("Repair cycle error: %s", exc)
            return _error_response("Repair cycle failed", 500)

    @bp.route("/status", methods=["GET"])
    def repair_status() -> Any:
        """Return the current repair system status."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        health = repair.get_health()
        return jsonify(health)

    @bp.route("/history", methods=["GET"])
    def repair_history() -> Any:
        """Return all past repair reports."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        return jsonify({"reports": repair.get_reports()})

    @bp.route("/wiring", methods=["GET"])
    def wiring_report() -> Any:
        """Return the front-end to back-end wiring report."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        return jsonify({"wiring_issues": repair.get_wiring_report()})

    @bp.route("/reconcile", methods=["POST"])
    def reconcile() -> Any:
        """Trigger a reconciliation loop iteration."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        state = repair.trigger_reconciliation()
        return jsonify({"reconciliation_state": state.to_dict()})

    @bp.route("/immune-memory", methods=["GET"])
    def immune_memory() -> Any:
        """Return the immune system memory cells."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        return jsonify({"immune_memory": repair.get_immune_memory()})

    @bp.route("/proposals", methods=["GET"])
    def list_proposals() -> Any:
        """Return all generated repair proposals."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        return jsonify({"proposals": repair.get_proposals()})

    @bp.route("/terminology", methods=["GET"])
    def terminology_map() -> Any:
        """Return the terminology concordance map."""
        repair = _get_repair_system()
        if repair is None:
            return _unavailable("AutonomousRepairSystem")
        concordance = repair.get_terminology_concordance()
        return jsonify({"concordance": concordance})

    @bp.route("/innovate", methods=["POST"])
    def run_innovation_scan() -> Any:
        """Trigger an innovation farming scan."""
        farmer = _get_innovation_farmer()
        if farmer is None:
            return _unavailable("InnovationFarmer")
        try:
            report = farmer.run_innovation_scan()
            return jsonify({"status": "ok", "report": report.to_dict()})
        except Exception as exc:
            logger.error("Innovation scan error: %s", exc)
            return _error_response("Innovation scan failed", 500)

    @bp.route("/innovation/proposals", methods=["GET"])
    def innovation_proposals() -> Any:
        """Return all generated innovation feature proposals."""
        farmer = _get_innovation_farmer()
        if farmer is None:
            return _unavailable("InnovationFarmer")
        return jsonify({"proposals": farmer.get_proposals()})

    @bp.route("/knowledge/build", methods=["POST"])
    def build_knowledge() -> Any:
        """Build a knowledge set for a specified industry domain."""
        builder = _get_knowledge_builder()
        if builder is None:
            return _unavailable("GenerativeKnowledgeBuilder")
        body = request.get_json(silent=True) or {}
        industry = str(body.get("industry", "generic"))
        language = str(body.get("language", "python"))
        try:
            ks = builder.build_knowledge_set(industry=industry, language=language)
            return jsonify({"status": "ok", "knowledge_set": ks.to_dict()})
        except Exception as exc:
            logger.error("Knowledge build error: %s", exc)
            return _error_response("Knowledge build failed", 500)

    @bp.route("/knowledge/<industry>", methods=["GET"])
    def get_knowledge(industry: str) -> Any:
        """Return a previously-built knowledge set by industry name."""
        builder = _get_knowledge_builder()
        if builder is None:
            return _unavailable("GenerativeKnowledgeBuilder")
        ks = builder.get_knowledge_set(industry)
        if ks is None:
            return _error_response(f"No knowledge set found for '{industry}'", 404)
        return jsonify({"knowledge_set": ks.to_dict()})

    return bp


def create_health_blueprint() -> Any:
    """Create a Blueprint for the extended health endpoint.

    Returns:
        A configured Flask Blueprint, or None if Flask is not available.
    """
    if not _FLASK_AVAILABLE:
        return None

    bp = Blueprint("health_extended", __name__)

    @bp.route("/api/health", methods=["GET"])
    def health() -> Any:
        """Return extended system health including repair system status."""
        components: Dict[str, Any] = {
            "autonomous_repair_system": _REPAIR_AVAILABLE,
            "innovation_farmer": _FARMER_AVAILABLE,
            "knowledge_builder": _KNOWLEDGE_AVAILABLE,
            "flask": _FLASK_AVAILABLE,
        }

        repair = _get_repair_system()
        repair_health: Dict[str, Any] = {}
        if repair is not None:
            try:
                repair_health = repair.get_health()
            except Exception as exc:
                logger.debug("Repair health check failed: %s", exc)
                repair_health = {"error": str(exc)}

        return jsonify({
            "status": "ok",
            "components": components,
            "repair": repair_health,
        })

    return bp


def register_repair_api(app: Any) -> None:
    """Register repair API blueprints onto an existing Flask app.

    Args:
        app: A Flask application instance.
    """
    if not _FLASK_AVAILABLE:
        logger.warning("Flask not available; skipping repair API registration")
        return

    repair_bp = create_repair_blueprint()
    if repair_bp is not None:
        app.register_blueprint(repair_bp)

    health_bp = create_health_blueprint()
    if health_bp is not None:
        app.register_blueprint(health_bp)


def create_standalone_app() -> Optional[Any]:
    """Create a standalone Flask app exposing only the repair API.

    The returned app has security middleware applied (authentication,
    CORS allowlist, rate limiting, security headers) via
    ``configure_secure_app``.

    Returns:
        A Flask app, or None if Flask is not available.
    """
    if not _FLASK_AVAILABLE:
        logger.warning("Flask not available; cannot create standalone repair app")
        return None

    app = Flask(__name__)
    register_repair_api(app)

    # SEC-001/SEC-002/SEC-004: Apply security middleware (auth, CORS, rate-limit)
    try:
        from flask_security import configure_secure_app
        configure_secure_app(app, service_name="repair-api")
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "SECURITY: Failed to apply authentication/CORS/rate-limiting "
            "middleware: %s — API running WITHOUT security controls", exc,
        )

    return app


__all__ = [
    "create_repair_blueprint",
    "create_health_blueprint",
    "register_repair_api",
    "create_standalone_app",
]

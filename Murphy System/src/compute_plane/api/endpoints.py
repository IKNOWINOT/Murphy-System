"""
REST API Endpoints for Compute Service

Provides HTTP interface to the Deterministic Compute Plane.
"""

import logging
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS

from src.compute_plane.models.compute_request import ComputeRequest
from src.compute_plane.service import ComputeService
from flask_security import configure_secure_app, is_debug_mode

logger = logging.getLogger(__name__)


def create_app(compute_service: ComputeService = None) -> Flask:
    """
    Create Flask app for Compute Service API.

    Args:
        compute_service: ComputeService instance (creates new if None)

    Returns:
        Flask app
    """
    app = Flask(__name__)
    configure_secure_app(app, service_name="compute-plane")

    # Create or use provided service
    service = compute_service or ComputeService(enable_caching=True)

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint"""
        return jsonify({'status': 'healthy', 'service': 'compute-plane'})

    @app.route('/compute', methods=['POST'])
    def submit_computation():
        """
        Submit computation request.

        Request body:
        {
            "expression": "x**2 + 2*x + 1",
            "language": "sympy",
            "assumptions": {"x": "real"},
            "precision": 10,
            "timeout": 30,
            "metadata": {"operation": "simplify"}
        }

        Returns:
        {
            "request_id": "uuid",
            "status": "pending"
        }
        """
        try:
            data = request.get_json()

            # Create request
            compute_request = ComputeRequest(
                expression=data['expression'],
                language=data['language'],
                assumptions=data.get('assumptions', {}),
                precision=data.get('precision', 10),
                timeout=data.get('timeout', 30),
                metadata=data.get('metadata', {})
            )

            # Submit request
            request_id = service.submit_request(compute_request)

            return jsonify({
                'request_id': request_id,
                'status': 'pending'
            }), 202

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return jsonify({'error': str(exc)}), 400

    @app.route('/compute/<request_id>', methods=['GET'])
    def get_computation_result(request_id: str):
        """
        Get computation result.

        Returns:
        {
            "request_id": "uuid",
            "status": "SUCCESS",
            "result": "...",
            "derivation_steps": [...],
            "confidence_score": 0.95,
            "stability_estimate": 0.90,
            ...
        }
        """
        result = service.get_result(request_id)

        if result is None:
            return jsonify({
                'request_id': request_id,
                'status': 'pending'
            }), 202

        return jsonify(result.to_dict()), 200

    @app.route('/compute/<request_id>/steps', methods=['GET'])
    def get_derivation_steps(request_id: str):
        """
        Get derivation steps for computation.

        Returns:
        {
            "request_id": "uuid",
            "derivation_steps": [...]
        }
        """
        result = service.get_result(request_id)

        if result is None:
            return jsonify({'error': 'Request not found or still pending'}), 404

        return jsonify({
            'request_id': request_id,
            'derivation_steps': result.derivation_steps
        }), 200

    @app.route('/compute/validate', methods=['POST'])
    def validate_expression():
        """
        Validate expression syntax.

        Request body:
        {
            "expression": "x**2 + 2*x + 1",
            "language": "sympy"
        }

        Returns:
        {
            "is_valid": true,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        """
        try:
            data = request.get_json()

            validation = service.validate_expression(
                data['expression'],
                data['language']
            )

            return jsonify(validation), 200

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return jsonify({'error': str(exc)}), 400

    @app.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get service statistics.

        Returns:
        {
            "total_requests": 100,
            "completed": 95,
            "pending": 5,
            "success_rate": 0.95
        }
        """
        stats = service.get_statistics()
        return jsonify(stats), 200

    return app


if __name__ == '__main__':
    # Run standalone server
    app = create_app()
    app.run(host='0.0.0.0', port=8054, debug=is_debug_mode())

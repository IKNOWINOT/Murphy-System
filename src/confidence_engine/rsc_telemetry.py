"""
RSC Telemetry for Confidence Engine

Provides telemetry endpoint for Recursive Stability Controller integration.
"""

import logging

from flask import jsonify

logger = logging.getLogger(__name__)


def add_telemetry_endpoint(app, current_graph, verification_evidence_store):
    """
    Add telemetry endpoint to Confidence Engine.

    Args:
        app: Flask application
        current_graph: Current artifact graph
        verification_evidence_store: Verification evidence store
    """

    @app.route('/telemetry', methods=['GET'])
    def get_telemetry():
        """Get system telemetry for Recursive Stability Controller"""
        from .graph_analyzer import GraphAnalyzer
        from .murphy_calculator import MurphyCalculator

        # Analyze current graph
        analyzer = GraphAnalyzer(current_graph)
        contradictions = analyzer.detect_contradictions()

        # Calculate mean confidence from recent computations
        # For now, use a simple heuristic based on graph state
        mean_confidence = 0.7  # Default
        if len(current_graph.nodes) > 0:
            # Estimate based on contradiction rate
            contradiction_rate = len(contradictions) / max(len(current_graph.nodes), 1)
            mean_confidence = max(0.3, 1.0 - contradiction_rate)

        # Calculate Murphy index
        murphy_calc = MurphyCalculator()
        murphy_index = 0.0
        if len(current_graph.nodes) > 0:
            # Simplified Murphy calculation
            murphy_index = min(0.5, len(contradictions) * 0.1)

        # Count active verifications
        active_verifications = len([v for v in verification_evidence_store
                                   if isinstance(v, dict) and v.get('status') == 'pending'])

        # Calculate confidence trend (simplified)
        confidence_trend = 0.0  # Neutral for now

        return jsonify({
            'contradiction_count': len(contradictions),
            'mean_confidence': mean_confidence,
            'confidence_trend': confidence_trend,
            'murphy_index': murphy_index,
            'active_verifications': active_verifications,
            'verification_backlog': active_verifications,
            'total_artifacts': len(current_graph.nodes),
            'total_edges': len(current_graph.edges)
        })

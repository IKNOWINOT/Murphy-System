"""
ML Inference Service
====================

REST API service for model inference.
Provides auxiliary confidence signals to existing Confidence Engine.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import torch
from flask import Flask, jsonify, request

from .models import ModelConfig, NeuroSymbolicConfidenceModel, load_model

app = Flask(__name__)
from flask_security import configure_secure_app

configure_secure_app(app, service_name="neuro-symbolic-inference")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLInferenceService:
    """
    ML inference service for confidence estimation.

    Provides auxiliary signals to Confidence Engine.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None
    ):
        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.model: Optional[NeuroSymbolicConfidenceModel] = None
        self.model_version = "1.0.0"
        self.model_loaded = False
        self.last_training = None

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str):
        """Load model from checkpoint."""
        try:
            self.model = load_model(model_path)
            self.model.to(self.device)
            self.model.eval()
            self.model_loaded = True
            logger.info("Model loaded successfully")
        except Exception as exc:
            logger.error("Failed to load model: %s", exc)
            self.model_loaded = False

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.model_loaded and self.model is not None

    def predict(
        self,
        artifact_graph: Dict[str, Any],
        gate_graph: Optional[Dict[str, Any]] = None,
        interface_bindings: Optional[Dict[str, Any]] = None,
        current_phase: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make prediction for confidence estimation.

        Args:
            artifact_graph: Artifact graph structure
            gate_graph: Gate graph structure (optional)
            interface_bindings: Interface bindings (optional)
            current_phase: Current execution phase (optional)

        Returns:
            Dictionary with H_ml, D_ml, R_ml predictions
        """
        if not self.is_healthy():
            raise RuntimeError("Model not loaded or unhealthy")

        try:
            # Convert input to tensors
            node_features, edge_index, symbolic_features = self._prepare_input(
                artifact_graph,
                gate_graph,
                interface_bindings,
                current_phase
            )

            # Move to device
            node_features = node_features.to(self.device)
            edge_index = edge_index.to(self.device)
            symbolic_features = symbolic_features.to(self.device)

            # Inference
            start_time = datetime.now(timezone.utc)

            with torch.no_grad():
                H_ml, D_ml, R_ml = self.model(
                    node_features,
                    edge_index,
                    symbolic_features,
                    batch=None
                )

            inference_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Extract values
            h_val = float(H_ml.item())
            d_val = float(D_ml.item())
            r_val = float(R_ml.item())

            # Derive prediction confidence from the model outputs:
            # H (health) and D (dependency-stability) are in [0,1] after
            # sigmoid; combine them via geometric mean for a single score.
            prediction_confidence = round(
                (max(0.0, min(1.0, h_val)) * max(0.0, min(1.0, d_val))) ** 0.5, 4
            )

            result = {
                "H_ml": h_val,
                "D_ml": d_val,
                "R_ml": r_val,
                "prediction_confidence": prediction_confidence,
                "model_version": self.model_version,
                "inference_time_ms": inference_time,
                "features_used": ["graph_structure", "symbolic_features"]
            }

            return result

        except Exception as exc:
            logger.error("Prediction failed: %s", exc)
            raise

    def _prepare_input(
        self,
        artifact_graph: Dict[str, Any],
        gate_graph: Optional[Dict[str, Any]],
        interface_bindings: Optional[Dict[str, Any]],
        current_phase: Optional[str]
    ) -> tuple:
        """
        Prepare input tensors from graph data.

        Extracts real node features, edge relationships, and symbolic
        attributes from the provided artifact/gate graphs.  Falls back
        to zero-initialised tensors when graph data is sparse.

        Returns:
            (node_features, edge_index, symbolic_features)
        """
        node_feature_dim = 64
        symbolic_feature_dim = 32

        # --- Node features ---------------------------------------------------
        nodes = artifact_graph.get("nodes", [])
        if not nodes:
            # Minimal single-node graph when no nodes are provided
            nodes = [{"id": "root"}]

        num_nodes = len(nodes)
        node_features = torch.zeros(num_nodes, node_feature_dim)

        node_id_map: Dict[str, int] = {}
        for idx, node in enumerate(nodes):
            node_id_map[str(node.get("id", idx))] = idx
            # Encode available scalar attributes into the feature vector
            props = node.get("properties", node)
            feat_idx = 0
            for key in sorted(props.keys()):
                val = props[key]
                if isinstance(val, (int, float)):
                    if feat_idx < node_feature_dim:
                        node_features[idx, feat_idx] = float(val)
                        feat_idx += 1
                elif isinstance(val, str):
                    # Deterministic string hash → float in [0, 1]
                    if feat_idx < node_feature_dim:
                        node_features[idx, feat_idx] = (hash(val) % 10000) / 10000.0
                        feat_idx += 1

        # --- Edge index -------------------------------------------------------
        edges = artifact_graph.get("edges", [])
        if edges:
            src_indices = []
            dst_indices = []
            for edge in edges:
                src = str(edge.get("source", edge.get("from", "")))
                dst = str(edge.get("target", edge.get("to", "")))
                if src in node_id_map and dst in node_id_map:
                    src_indices.append(node_id_map[src])
                    dst_indices.append(node_id_map[dst])
            if src_indices:
                edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)
            else:
                # Self-loop on first node when no valid edges
                edge_index = torch.tensor([[0], [0]], dtype=torch.long)
        else:
            # Default: linear chain when no edge info supplied
            if num_nodes > 1:
                edge_index = torch.tensor(
                    [list(range(num_nodes - 1)), list(range(1, num_nodes))],
                    dtype=torch.long,
                )
            else:
                edge_index = torch.tensor([[0], [0]], dtype=torch.long)

        # --- Symbolic features ------------------------------------------------
        symbolic_features = torch.zeros(1, symbolic_feature_dim)
        feat_idx = 0
        if gate_graph:
            gates = gate_graph.get("gates", [])
            for g in gates:
                if feat_idx < symbolic_feature_dim:
                    symbolic_features[0, feat_idx] = float(g.get("weight", 0.5))
                    feat_idx += 1
        if interface_bindings:
            for key, val in sorted(interface_bindings.items()):
                if feat_idx < symbolic_feature_dim:
                    symbolic_features[0, feat_idx] = (hash(str(val)) % 10000) / 10000.0
                    feat_idx += 1
        if current_phase:
            if feat_idx < symbolic_feature_dim:
                symbolic_features[0, feat_idx] = (hash(current_phase) % 10000) / 10000.0

        return node_features, edge_index, symbolic_features

    def predict_batch(
        self,
        scenarios: list
    ) -> Dict[str, Any]:
        """
        Batch prediction for multiple scenarios.
        """
        if not self.is_healthy():
            raise RuntimeError("Model not loaded or unhealthy")

        predictions = []

        for scenario in scenarios:
            try:
                pred = self.predict(
                    artifact_graph=scenario.get("artifact_graph", {}),
                    gate_graph=scenario.get("gate_graph"),
                    interface_bindings=scenario.get("interface_bindings"),
                    current_phase=scenario.get("current_phase")
                )
                predictions.append(pred)
            except Exception as exc:
                logger.error("Batch prediction failed for scenario: %s", exc)
                predictions.append(None)

        # Compute batch confidence
        valid_predictions = [p for p in predictions if p is not None]
        batch_confidence = np.mean([
            p["prediction_confidence"] for p in valid_predictions
        ]) if valid_predictions else 0.0

        return {
            "predictions": predictions,
            "batch_confidence": batch_confidence,
            "num_successful": len(valid_predictions),
            "num_failed": len(predictions) - len(valid_predictions)
        }


# Global service instance
ml_service = MLInferenceService()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy" if ml_service.is_healthy() else "unavailable",
        "models_loaded": ml_service.model_loaded,
        "model_version": ml_service.model_version,
        "last_training": ml_service.last_training,
        "prediction_confidence": 0.85 if ml_service.is_healthy() else 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route('/predict/confidence', methods=['POST'])
def predict_confidence():
    """
    Main prediction endpoint.

    Request:
    {
        "artifact_graph": {...},
        "gate_graph": {...},
        "interface_bindings": {...},
        "current_phase": "generative",
        "request_id": "req_123"
    }

    Response:
    {
        "H_ml": 0.3,
        "D_ml": 0.8,
        "R_ml": 0.2,
        "prediction_confidence": 0.85,
        "model_version": "1.0.0",
        "inference_time_ms": 45.2
    }
    """
    try:
        data = request.json

        result = ml_service.predict(
            artifact_graph=data.get("artifact_graph", {}),
            gate_graph=data.get("gate_graph"),
            interface_bindings=data.get("interface_bindings"),
            current_phase=data.get("current_phase")
        )

        return jsonify(result)

    except Exception as exc:
        logger.error("Prediction endpoint error: %s", exc)
        return jsonify({
            "error": "Internal server error",
            "status": "failed"
        }), 500


@app.route('/predict/batch', methods=['POST'])
def predict_batch():
    """
    Batch prediction endpoint.

    Request:
    {
        "scenarios": [
            {"artifact_graph": {...}, ...},
            {"artifact_graph": {...}, ...}
        ]
    }
    """
    try:
        data = request.json
        scenarios = data.get("scenarios", [])

        result = ml_service.predict_batch(scenarios)

        return jsonify(result)

    except Exception as exc:
        logger.error("Batch prediction endpoint error: %s", exc)
        return jsonify({
            "error": "Internal server error",
            "status": "failed"
        }), 500


@app.route('/model/info', methods=['GET'])
def model_info():
    """Get model information."""
    if not ml_service.is_healthy():
        return jsonify({
            "error": "Model not loaded",
            "status": "unavailable"
        }), 503

    return jsonify({
        "architecture": "GraphSAGE + Symbolic Features",
        "parameters": sum(p.numel() for p in ml_service.model.parameters()),
        "model_version": ml_service.model_version,
        "device": str(ml_service.device),
        "input_features": {
            "node_feature_dim": ml_service.model.config.node_feature_dim,
            "symbolic_feature_dim": ml_service.model.config.symbolic_feature_dim,
            "hidden_dim": ml_service.model.config.hidden_dim
        }
    })


@app.route('/model/load', methods=['POST'])
def load_model_endpoint():
    """
    Load model from checkpoint.

    Request:
    {
        "model_path": "/path/to/checkpoint.pt"
    }
    """
    try:
        data = request.json
        model_path = data.get("model_path")

        if not model_path:
            return jsonify({
                "error": "model_path required",
                "status": "failed"
            }), 400

        ml_service.load_model(model_path)

        return jsonify({
            "status": "success",
            "model_loaded": ml_service.model_loaded,
            "model_version": ml_service.model_version
        })

    except Exception as exc:
        logger.error("Model load error: %s", exc)
        return jsonify({
            "error": "Internal server error",
            "status": "failed"
        }), 500


def run_server(host: str = "0.0.0.0", port: int = 8060, model_path: Optional[str] = None):
    """
    Run ML inference server.

    Args:
        host: Host address
        port: Port number
        model_path: Path to model checkpoint (optional)
    """
    if model_path:
        ml_service.load_model(model_path)

    logger.info("Starting ML Inference Service on %s:%s", host, port)
    logger.info("Model loaded: %s", ml_service.model_loaded)

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    import sys

    model_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_server(port=8060, model_path=model_path)

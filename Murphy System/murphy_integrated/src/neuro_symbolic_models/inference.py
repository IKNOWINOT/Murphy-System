"""
ML Inference Service
====================

REST API service for model inference.
Provides auxiliary confidence signals to existing Confidence Engine.
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from src.security_plane.middleware import AuthenticationMiddleware, SecurityMiddlewareConfig, SecurityContext
from src.config import settings


# Initialize Flask app
app = Flask(__name__)

# Configure CORS with specific origins from config
cors_origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else "*"
CORS(app, origins=cors_origins)

# Initialize security middleware
security_config = SecurityMiddlewareConfig(
    require_authentication=True,
    allow_human_auth=True,
    allow_machine_auth=True,
    enable_audit_logging=True
)
auth_middleware = AuthenticationMiddleware(security_config)

# Helper function to extract tenant_id from request
def get_tenant_id_from_request() -> str:
    &quot;&quot;&quot;Extract tenant_id from authenticated request context&quot;&quot;&quot;
    return request.headers.get('X-Tenant-ID', 'default')

# Authentication before_request hook
@app.before_request
def authenticate_request():
    &quot;&quot;&quot;Authenticate all incoming requests&quot;&quot;&quot;
    # Skip authentication for health checks
    if request.path == '/health':
        return None
    
    # Create security context
    context = SecurityContext()
    
    # Prepare request data for authentication
    request_data = {
        'auth_type': request.headers.get('X-Auth-Type'),
        'credentials': {
            'user_id': request.headers.get('X-User-ID'),
            'machine_id': request.headers.get('X-Machine-ID'),
            'token': request.headers.get('Authorization', '').replace('Bearer ', '')
        }
    }
    
    # Authenticate request
    if not auth_middleware.authenticate_request(request_data, context):
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please provide valid authentication credentials'
        }), 401
    
    # Store authenticated context in Flask g object
    g.authenticated = context.authenticated
    g.identity = context.identity
    g.tenant_id = get_tenant_id_from_request()
    
    return None

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
            logger.info(f"Loaded model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
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
            start_time = datetime.now()
            
            with torch.no_grad():
                H_ml, D_ml, R_ml = self.model(
                    node_features,
                    edge_index,
                    symbolic_features,
                    batch=None
                )
            
            inference_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Extract values
            result = {
                "H_ml": float(H_ml.item()),
                "D_ml": float(D_ml.item()),
                "R_ml": float(R_ml.item()),
                "prediction_confidence": 0.85,  # Placeholder - use ensemble for real confidence
                "model_version": self.model_version,
                "inference_time_ms": inference_time,
                "features_used": ["graph_structure", "symbolic_features"]
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
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
        
        Returns:
            (node_features, edge_index, symbolic_features)
        """
        # Simplified input preparation
        # In practice, parse actual graph structure
        
        # Create dummy node features
        num_nodes = 10
        node_feature_dim = 64
        node_features = torch.randn(num_nodes, node_feature_dim)
        
        # Create dummy edge index
        edge_index = torch.tensor([
            [0, 1, 2, 3, 4, 5, 6, 7, 8],
            [1, 2, 3, 4, 5, 6, 7, 8, 9]
        ], dtype=torch.long)
        
        # Create dummy symbolic features
        symbolic_feature_dim = 32
        symbolic_features = torch.randn(1, symbolic_feature_dim)
        
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
            except Exception as e:
                logger.error(f"Batch prediction failed for scenario: {e}")
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
        "timestamp": datetime.now().isoformat()
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
    
    except Exception as e:
        logger.error(f"Prediction endpoint error: {e}")
        return jsonify({
            "error": str(e),
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
    
    except Exception as e:
        logger.error(f"Batch prediction endpoint error: {e}")
        return jsonify({
            "error": str(e),
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
    
    except Exception as e:
        logger.error(f"Model load error: {e}")
        return jsonify({
            "error": str(e),
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
    
    logger.info(f"Starting ML Inference Service on {host}:{port}")
    logger.info(f"Model loaded: {ml_service.model_loaded}")
    
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    import sys
    
    model_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_server(port=8060, model_path=model_path)
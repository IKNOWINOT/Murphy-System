"""
REST API Endpoints for Compute Service

Provides HTTP interface to the Deterministic Compute Plane.
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
        
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
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
        
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
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
    app.run(host='0.0.0.0', port=8054, debug=True)
"""
Murphy System - Authentication Middleware
Flask decorators for authentication and authorization
"""

from functools import wraps
from flask import request, jsonify, g
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def require_auth(auth_system, roles: Optional[list] = None):
    """
    Decorator to require authentication for endpoints
    
    Args:
        auth_system: AuthenticationSystem instance
        roles: List of required roles (None = any authenticated user)
    
    Usage:
        @app.route('/api/protected')
        @require_auth(auth_system)
        def protected_endpoint():
            return jsonify({'user': g.user})
        
        @app.route('/api/admin')
        @require_auth(auth_system, roles=['admin'])
        def admin_endpoint():
            return jsonify({'message': 'Admin only'})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            
            if not auth_header:
                logger.warning("Authentication required: No Authorization header")
                return jsonify({
                    'success': False,
                    'error': 'authentication_required',
                    'message': 'Authentication required. Provide Bearer token in Authorization header.'
                }), 401
            
            # Extract token
            if not auth_header.startswith('Bearer '):
                logger.warning("Authentication failed: Invalid token format")
                return jsonify({
                    'success': False,
                    'error': 'invalid_token_format',
                    'message': 'Invalid token format. Use: Bearer <token>'
                }), 401
            
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Verify token
            is_valid, payload = auth_system.verify_token(token)
            
            if not is_valid or not payload:
                logger.warning("Authentication failed: Invalid token")
                return jsonify({
                    'success': False,
                    'error': 'invalid_token',
                    'message': 'Invalid or expired token'
                }), 401
            
            # Check role if specified
            if roles:
                user_role = payload.get('role')
                if user_role not in roles:
                    logger.warning(f"Authorization failed: User role '{user_role}' not in {roles}")
                    return jsonify({
                        'success': False,
                        'error': 'insufficient_permissions',
                        'message': f'Insufficient permissions. Required roles: {", ".join(roles)}'
                    }), 403
            
            # Store user info in Flask's g object
            g.user = {
                'username': payload.get('username'),
                'role': payload.get('role')
            }
            
            logger.info(f"Authenticated: {g.user['username']} (role: {g.user['role']})")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def optional_auth(auth_system):
    """
    Decorator for optional authentication
    Attaches user info to g.user if authenticated, but doesn't require it
    
    Args:
        auth_system: AuthenticationSystem instance
    
    Usage:
        @app.route('/api/public')
        @optional_auth(auth_system)
        def public_endpoint():
            if hasattr(g, 'user'):
                return jsonify({'user': g.user})
            return jsonify({'message': 'Anonymous'})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Try to authenticate, but don't require it
            auth_header = request.headers.get('Authorization')
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
                is_valid, payload = auth_system.verify_token(token)
                
                if is_valid and payload:
                    g.user = {
                        'username': payload.get('username'),
                        'role': payload.get('role')
                    }
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def rate_limit(limit: int, per: int = 60):
    """
    Decorator for rate limiting (simple implementation)
    
    Args:
        limit: Number of requests allowed
        per: Time period in seconds
    
    Usage:
        @app.route('/api/limited')
        @rate_limit(limit=10, per=60)
        def limited_endpoint():
            return jsonify({'message': 'Limited endpoint'})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Simple in-memory rate limiting (use Redis in production)
            if not hasattr(decorated_function, 'request_counts'):
                decorated_function.request_counts = {}
            
            ip = request.remote_addr
            current_time = int(__import__('time').time())
            
            # Clean old entries
            decorated_function.request_counts = {
                k: v for k, v in decorated_function.request_counts.items()
                if current_time - v['first_request'] < per
            }
            
            # Check rate limit
            if ip in decorated_function.request_counts:
                count = decorated_function.request_counts[ip]['count']
                if count >= limit:
                    logger.warning(f"Rate limit exceeded for IP: {ip}")
                    return jsonify({
                        'success': False,
                        'error': 'rate_limit_exceeded',
                        'message': f'Rate limit exceeded. Maximum {limit} requests per {per} seconds.'
                    }), 429
                decorated_function.request_counts[ip]['count'] += 1
            else:
                decorated_function.request_counts[ip] = {
                    'count': 1,
                    'first_request': current_time
                }
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def validate_input(validator_func):
    """
    Decorator for input validation
    
    Args:
        validator_func: Function that validates request data
    
    Usage:
        def validate_artifact_request(data):
            if not data.get('artifact_type'):
                raise ValueError('artifact_type is required')
        
        @app.route('/api/artifacts')
        @validate_input(validate_artifact_request)
        def create_artifact():
            return jsonify({'success': True})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get request data
                if request.method in ['POST', 'PUT']:
                    data = request.get_json() or {}
                else:
                    data = request.args.to_dict()
                
                # Validate using provided function
                validation_result = validator_func(data)
                
                if isinstance(validation_result, tuple):
                    # Validation function returned (is_valid, error_message)
                    is_valid, error_message = validation_result
                    if not is_valid:
                        logger.warning(f"Input validation failed: {error_message}")
                        return jsonify({
                            'success': False,
                            'error': 'validation_error',
                            'message': error_message
                        }), 400
                
                return f(*args, **kwargs)
                
            except ValueError as e:
                logger.warning(f"Input validation error: {e}")
                return jsonify({
                    'success': False,
                    'error': 'validation_error',
                    'message': str(e)
                }), 400
            except Exception as e:
                logger.error(f"Unexpected validation error: {e}")
                return jsonify({
                    'success': False,
                    'error': 'validation_error',
                    'message': 'Invalid input data'
                }), 400
        
        return decorated_function
    return decorator
# Input Validator Functions
def validate_login_request(data):
    """Validate login request data"""
    if not data:
        raise ValueError('Request body is required')
    if not data.get('username'):
        raise ValueError('username is required')
    if not isinstance(data.get('username'), str):
        raise ValueError('username must be a string')
    if len(data.get('username', '')) < 3:
        raise ValueError('username must be at least 3 characters')
    if not data.get('password'):
        raise ValueError('password is required')
    if not isinstance(data.get('password'), str):
        raise ValueError('password must be a string')
    if len(data.get('password', '')) < 6:
        raise ValueError('password must be at least 6 characters')

def validate_init_request(data):
    """Validate system initialization request"""
    if data and data.get('initialize') is not None:
        if not isinstance(data.get('initialize'), bool):
            raise ValueError('initialize must be a boolean')

def validate_artifact_request(data):
    """Validate artifact generation request"""
    if not data:
        raise ValueError('Request body is required')
    if not data.get('artifact_type'):
        raise ValueError('artifact_type is required')
    if not data.get('document_id'):
        raise ValueError('document_id is required')

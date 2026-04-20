"""
Module Compiler API Endpoints

REST API for module compilation, capability discovery, and registry management.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import os
import sys
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import logging

from module_compiler import ModuleCompiler, ModuleRegistry
from module_compiler.models.module_spec import ModuleSpec

logger = logging.getLogger(__name__)


def create_api() -> Blueprint:
    """
    Create Flask Blueprint for Module Compiler API.

    Returns:
        Flask Blueprint with all endpoints
    """
    api = Blueprint('module_compiler', __name__, url_prefix='/api/module-compiler')

    # Initialize compiler and registry
    compiler = ModuleCompiler()
    registry = ModuleRegistry()


    @api.route('/compile', methods=['POST'])
    def compile_module():
        """
        Compile a module from source path.

        POST /api/module-compiler/compile

        Request Body:
        {
            "source_path": "/workspace/bots/analysisbot.py",
            "requested_capabilities": ["analyze_scope"]  // optional
        }

        Response:
        {
            "status": "success",
            "module_id": "analysisbot-v1-abc123",
            "capabilities": [...],
            "verification_status": "passed",
            "is_partial": false
        }
        """
        try:
            data = request.get_json()

            if not data or 'source_path' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required field: source_path'
                }), 400

            source_path = data['source_path']
            requested_capabilities = data.get('requested_capabilities')

            # Validate source path exists
            if not os.path.exists(source_path):
                return jsonify({
                    'status': 'error',
                    'message': f'Source file not found: {source_path}'
                }), 404

            # Compile module
            module_spec = compiler.compile_module(
                source_path=source_path,
                requested_capabilities=requested_capabilities
            )

            # Register in registry
            registry.register(module_spec)

            # Return response
            return jsonify({
                'status': 'success',
                'module_id': module_spec.module_id,
                'source_path': module_spec.source_path,
                'version_hash': module_spec.version_hash,
                'capabilities': [
                    {
                        'name': cap.name,
                        'description': cap.description,
                        'deterministic': cap.is_deterministic(),
                        'requires_network': cap.requires_network(),
                        'timeout_seconds': cap.resource_profile.timeout_seconds
                    }
                    for cap in module_spec.capabilities
                ],
                'sandbox_profile': module_spec.sandbox_profile.to_dict(),
                'verification_status': module_spec.verification_status,
                'is_partial': module_spec.is_partial,
                'requires_manual_review': module_spec.requires_manual_review,
                'uncertainty_flags': module_spec.uncertainty_flags,
                'compiled_at': module_spec.compiled_at
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/compile-directory', methods=['POST'])
    def compile_directory():
        """
        Compile all modules in a directory.

        POST /api/module-compiler/compile-directory

        Request Body:
        {
            "directory_path": "/workspace/bots",
            "pattern": "*.py"  // optional, default: *.py
        }

        Response:
        {
            "status": "success",
            "compiled": 10,
            "failed": 2,
            "modules": [...]
        }
        """
        try:
            data = request.get_json()

            if not data or 'directory_path' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required field: directory_path'
                }), 400

            directory_path = data['directory_path']
            pattern = data.get('pattern', '*.py')

            # Validate directory exists
            if not os.path.isdir(directory_path):
                return jsonify({
                    'status': 'error',
                    'message': f'Directory not found: {directory_path}'
                }), 404

            # Compile all modules
            module_specs = compiler.compile_directory(directory_path, pattern)

            # Register all modules
            compiled = 0
            failed = 0
            for spec in module_specs:
                if registry.register(spec):
                    if not spec.is_partial:
                        compiled += 1
                    else:
                        failed += 1
                else:
                    failed += 1

            return jsonify({
                'status': 'success',
                'compiled': compiled,
                'failed': failed,
                'total': len(module_specs),
                'modules': [
                    {
                        'module_id': spec.module_id,
                        'capabilities': len(spec.capabilities),
                        'verification_status': spec.verification_status
                    }
                    for spec in module_specs
                ]
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/modules', methods=['GET'])
    def list_modules():
        """
        List all registered modules.

        GET /api/module-compiler/modules?deterministic=true&network=false

        Query Parameters:
        - deterministic: Filter by deterministic modules (true/false)
        - network: Filter by network requirement (true/false)
        - status: Filter by verification status (passed/failed/pending)

        Response:
        {
            "status": "success",
            "count": 10,
            "modules": [...]
        }
        """
        try:
            # Parse query parameters
            deterministic_only = request.args.get('deterministic', '').lower() == 'true'
            network_param = request.args.get('network', '')
            network_required = None if not network_param else network_param.lower() == 'true'
            verification_status = request.args.get('status')

            # Get modules
            modules = registry.list_modules(
                deterministic_only=deterministic_only,
                network_required=network_required,
                verification_status=verification_status
            )

            return jsonify({
                'status': 'success',
                'count': len(modules),
                'modules': modules
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/modules/<module_id>', methods=['GET'])
    def get_module(module_id: str):
        """
        Get detailed module specification.

        GET /api/module-compiler/modules/{module_id}

        Response:
        {
            "status": "success",
            "module": {...}
        }
        """
        try:
            module_spec = registry.get(module_id)

            if not module_spec:
                return jsonify({
                    'status': 'error',
                    'message': f'Module not found: {module_id}'
                }), 404

            return jsonify({
                'status': 'success',
                'module': module_spec.to_dict()
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/modules/<module_id>', methods=['DELETE'])
    def delete_module(module_id: str):
        """
        Remove module from registry.

        DELETE /api/module-compiler/modules/{module_id}

        Response:
        {
            "status": "success",
            "message": "Module removed"
        }
        """
        try:
            success = registry.remove(module_id)

            if not success:
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to remove module: {module_id}'
                }), 500

            return jsonify({
                'status': 'success',
                'message': f'Module removed: {module_id}'
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/capabilities', methods=['GET'])
    def search_capabilities():
        """
        Search for capabilities.

        GET /api/module-compiler/capabilities?q=analysis&deterministic=true

        Query Parameters:
        - q: Search query (substring match)
        - deterministic: Filter by deterministic capabilities (true/false)

        Response:
        {
            "status": "success",
            "count": 5,
            "capabilities": [...]
        }
        """
        try:
            query = request.args.get('q', '')
            deterministic_only = request.args.get('deterministic', '').lower() == 'true'

            if not query:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required parameter: q'
                }), 400

            results = registry.search_capabilities(query, deterministic_only)

            return jsonify({
                'status': 'success',
                'count': len(results),
                'query': query,
                'capabilities': results
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/capabilities/<capability_name>', methods=['GET'])
    def get_capability(capability_name: str):
        """
        Get detailed capability information.

        GET /api/module-compiler/capabilities/{capability_name}

        Response:
        {
            "status": "success",
            "capability": {...}
        }
        """
        try:
            capability = registry.get_capability(capability_name)

            if not capability:
                return jsonify({
                    'status': 'error',
                    'message': f'Capability not found: {capability_name}'
                }), 404

            return jsonify({
                'status': 'success',
                'capability': capability.to_dict()
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/stats', methods=['GET'])
    def get_stats():
        """
        Get registry statistics.

        GET /api/module-compiler/stats

        Response:
        {
            "status": "success",
            "stats": {...}
        }
        """
        try:
            stats = registry.get_stats()

            return jsonify({
                'status': 'success',
                'stats': stats
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500


    @api.route('/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.

        GET /api/module-compiler/health

        Response:
        {
            "status": "healthy",
            "compiler_version": "1.0.0",
            "registry_modules": 10
        }
        """
        try:
            stats = registry.get_stats()

            return jsonify({
                'status': 'healthy',
                'compiler_version': compiler.compiler_version,
                'registry_modules': stats['total_modules'],
                'registry_capabilities': stats['total_capabilities']
            }), 200

        except Exception as exc:
            logger.error("Caught exception: %s", exc, exc_info=True)
            return jsonify({
                'status': 'unhealthy',
                'error': 'Internal server error'
            }), 500


    return api


def create_standalone_app():
    """
    Create standalone Flask app for Module Compiler API.

    Returns:
        Flask application
    """
    from flask import Flask

    from flask_security import configure_secure_app, is_debug_mode

    app = Flask(__name__)
    configure_secure_app(app, service_name="module-compiler")

    # Register API blueprint
    api = create_api()
    app.register_blueprint(api)

    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            'service': 'Module Compiler API',
            'version': '1.0.0',
            'owner': 'INONI LLC / Corey Post',
            'endpoints': {
                'compile': 'POST /api/module-compiler/compile',
                'compile_directory': 'POST /api/module-compiler/compile-directory',
                'list_modules': 'GET /api/module-compiler/modules',
                'get_module': 'GET /api/module-compiler/modules/{id}',
                'delete_module': 'DELETE /api/module-compiler/modules/{id}',
                'search_capabilities': 'GET /api/module-compiler/capabilities?q=...',
                'get_capability': 'GET /api/module-compiler/capabilities/{name}',
                'stats': 'GET /api/module-compiler/stats',
                'health': 'GET /api/module-compiler/health'
            }
        })

    return app


if __name__ == '__main__':
    app = create_standalone_app()
    app.run(host='0.0.0.0', port=8053, debug=os.environ.get('FLASK_DEBUG', '0') == '1')

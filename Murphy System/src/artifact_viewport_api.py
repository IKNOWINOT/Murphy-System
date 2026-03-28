"""
Artifact Viewport REST API
============================

Flask blueprint providing REST endpoints for the Artifact Viewport service.
Mountable on any Murphy System Flask API server.

Endpoints:
- GET  /viewport/manifest/<artifact_id>   - Get content manifest (structure index)
- GET  /viewport/project/<artifact_id>    - Project viewport range onto artifact
- GET  /viewport/search/<artifact_id>     - Search within artifact content
- GET  /viewport/health                   - Viewport service health

Query Parameters (for /project):
- start_line: int (1-indexed, default 1)
- end_line: int (1-indexed, -1 = end, default 50)
- key_path: str (dot-separated path for structured content)
- depth: int (max nesting depth, default 3)
- section: str (named section to project)
- mode: str (head|tail|range, default range)
- num_lines: int (for head/tail mode, default 50)
"""

import re

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    # Minimal Flask Blueprint so module-level route decorators register correctly
    class _StubBlueprint:
        """No-op Blueprint stand-in when Flask is absent."""
        def route(self, *a, **kw):
            return lambda fn: fn
    Blueprint = _StubBlueprint  # type: ignore[misc,assignment]
    request = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
import logging
from typing import Optional

from artifact_viewport import (
    DEFAULT_VIEWPORT_LINES,
    MAX_VIEWPORT_LINES,
    ArtifactViewport,
    ViewportOrigin,
    ViewportRange,
)

logger = logging.getLogger(__name__)

# Create blueprint (stub when Flask is absent)
viewport_bp = Blueprint('viewport', __name__, url_prefix='/viewport') if _HAS_FLASK else Blueprint()

# Shared viewport service instance (set by mount_viewport_api)
_viewport: Optional[ArtifactViewport] = None

# Content resolver callback (set by mount_viewport_api)
_content_resolver = None

# Safe ID pattern
_SAFE_ID = re.compile(r'^[a-zA-Z0-9_\-.:]+$')
_MAX_ID_LEN = 256


def _validate_artifact_id(artifact_id: str):
    """Validate artifact_id format. Returns error response or None."""
    if not _SAFE_ID.match(artifact_id) or len(artifact_id) > _MAX_ID_LEN:
        return jsonify({'error': 'Invalid artifact_id'}), 400
    return None


def mount_viewport_api(app, viewport: ArtifactViewport, content_resolver=None):
    """
    Mount the viewport blueprint onto a Flask app.

    .. important::
        The parent ``app`` **must** already have security middleware applied
        via ``flask_security.configure_secure_app(app)`` before mounting.
        The blueprint inherits authentication, CORS, and rate-limiting
        from the host application.

    Args:
        app: Flask application
        viewport: ArtifactViewport service instance
        content_resolver: Callable(artifact_id, tenant_id, origin) -> content
            Function that resolves artifact_id to its raw content.
            If None, the API will require content in the request body.
    """
    global _viewport, _content_resolver
    _viewport = viewport
    _content_resolver = content_resolver
    app.register_blueprint(viewport_bp)


def _get_tenant_id() -> str:
    """Extract tenant ID from request headers."""
    return request.headers.get('X-Tenant-ID', 'default')


def _resolve_content(artifact_id: str, tenant_id: str, origin: ViewportOrigin):
    """Resolve artifact content using the registered resolver or request body."""
    if _content_resolver:
        result = _content_resolver(artifact_id, tenant_id, origin)
        if result is not None:
            return result
    # Fallback: expect content in query or POST body
    if request.is_json and request.json:
        return request.json.get('content')
    return None


def _parse_origin(origin_str: str) -> ViewportOrigin:
    """Parse origin string to enum, defaulting to WORKING."""
    try:
        return ViewportOrigin(origin_str)
    except ValueError:
        return ViewportOrigin.WORKING


@viewport_bp.route('/health', methods=['GET'])
def viewport_health():
    """Viewport service health check"""
    if not _viewport:
        return jsonify({'status': 'not_initialized'}), 503
    stats = _viewport.get_statistics()
    return jsonify({
        'status': 'healthy',
        'service': 'artifact_viewport',
        **stats,
    })


@viewport_bp.route('/manifest/<artifact_id>', methods=['GET', 'POST'])
def get_manifest(artifact_id: str):
    """
    Get content manifest for an artifact.

    Returns structural metadata: line count, sections, byte size, checksum.
    """
    if not _viewport:
        return jsonify({'error': 'Viewport service not initialized'}), 503
    invalid = _validate_artifact_id(artifact_id)
    if invalid:
        return invalid

    tenant_id = _get_tenant_id()
    origin = _parse_origin(request.args.get('origin', 'working'))
    content = _resolve_content(artifact_id, tenant_id, origin)

    if content is None:
        return jsonify({'error': 'Artifact content not found'}), 404

    manifest = _viewport.get_manifest(artifact_id, content, tenant_id, origin)
    return jsonify({'success': True, 'manifest': manifest.to_dict()})


@viewport_bp.route('/project/<artifact_id>', methods=['GET', 'POST'])
def project_viewport(artifact_id: str):
    """
    Project a viewport range onto artifact content.

    Query params:
        start_line (int): Start line (1-indexed, default 1)
        end_line (int): End line (-1 = end, default 50)
        key_path (str): Dot-separated path for structured content
        depth (int): Max nesting depth (default 3)
        section (str): Named section to project
        mode (str): head|tail|range (default range)
        num_lines (int): Lines for head/tail mode (default 50)
    """
    if not _viewport:
        return jsonify({'error': 'Viewport service not initialized'}), 503
    invalid = _validate_artifact_id(artifact_id)
    if invalid:
        return invalid

    tenant_id = _get_tenant_id()
    origin = _parse_origin(request.args.get('origin', 'working'))
    content = _resolve_content(artifact_id, tenant_id, origin)

    if content is None:
        return jsonify({'error': 'Artifact content not found'}), 404

    # Determine projection mode
    mode = request.args.get('mode', 'range')
    section = request.args.get('section')
    num_lines = min(
        int(request.args.get('num_lines', DEFAULT_VIEWPORT_LINES)),
        MAX_VIEWPORT_LINES,
    )

    if section:
        projection = _viewport.project_section(
            artifact_id, content, tenant_id, section, origin
        )
        if projection is None:
            return jsonify({'error': f'Section not found: {section}'}), 404
    elif mode == 'head':
        projection = _viewport.project_head(
            artifact_id, content, tenant_id, num_lines, origin
        )
    elif mode == 'tail':
        projection = _viewport.project_tail(
            artifact_id, content, tenant_id, num_lines, origin
        )
    else:
        start = int(request.args.get('start_line', 1))
        end = int(request.args.get('end_line', DEFAULT_VIEWPORT_LINES))
        key_path = request.args.get('key_path')
        depth = int(request.args.get('depth', 3))

        vrange = ViewportRange(
            start_line=start,
            end_line=end,
            key_path=key_path,
            depth=depth,
        )
        projection = _viewport.project(
            artifact_id, content, tenant_id, vrange, origin
        )

    return jsonify({'success': True, 'projection': projection.to_dict()})


@viewport_bp.route('/search/<artifact_id>', methods=['GET', 'POST'])
def search_artifact(artifact_id: str):
    """
    Search within artifact content.

    Query params:
        q (str): Search query (required)
        context_lines (int): Lines of context around matches (default 3)
    """
    if not _viewport:
        return jsonify({'error': 'Viewport service not initialized'}), 503
    invalid = _validate_artifact_id(artifact_id)
    if invalid:
        return invalid

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Missing search query (q parameter)'}), 400
    if len(query) > 500:
        return jsonify({'error': 'Search query too long'}), 400

    tenant_id = _get_tenant_id()
    origin = _parse_origin(request.args.get('origin', 'working'))
    context_lines = min(int(request.args.get('context_lines', 3)), 20)
    content = _resolve_content(artifact_id, tenant_id, origin)

    if content is None:
        return jsonify({'error': 'Artifact content not found'}), 404

    results = _viewport.search_content(
        artifact_id, content, tenant_id, query, context_lines, origin
    )

    return jsonify({
        'success': True,
        'query': query,
        'match_count': len(results),
        'matches': results,
    })

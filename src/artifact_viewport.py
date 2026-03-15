"""
Artifact Viewport Service
==========================

Range-based content inspection for Murphy System artifacts, intake documents,
and execution deliverables. Provides paginated, windowed access to large
content without loading entire artifacts into memory.

Terminology:
- Viewport: A bounded window into an artifact's content, defined by a range
- Content Manifest: Structural index of an artifact (line count, sections, byte size)
- Projection: The extracted slice of content within a viewport's range
- Artifact Locator: Composite key (tenant_id, memory_plane, artifact_id) for content resolution

Integration Points:
- Memory Artifact System (MAS): Inspects artifacts across all four memory planes
- Persistence Manager: Reads persisted documents, gate history, audit trails
- System Librarian: Retrieves transcripts and generated documentation
- Confidence Engine: Views artifact graph nodes and verification evidence

Security:
- Tenant-isolated: All viewport operations require and enforce tenant_id
- Read-only: Viewport never mutates content
- Auditable: Every viewport access is logged with caller identity
"""

import hashlib
import json
import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & CONFIGURATION
# ============================================================================

class ContentType(Enum):
    """Classification of viewable content"""
    TEXT = "text"                   # Plain text, markdown, code
    STRUCTURED = "structured"      # JSON/dict with nested keys
    TABULAR = "tabular"            # List of uniform records
    BINARY_METADATA = "binary_metadata"  # Non-text (only metadata viewable)


class ViewportOrigin(Enum):
    """Source plane where the artifact resides"""
    SANDBOX = "sandbox"
    WORKING = "working"
    CONTROL = "control"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"    # Persisted documents
    LIBRARIAN = "librarian"        # System-generated docs / transcripts


# Default viewport size when not specified
DEFAULT_VIEWPORT_LINES = 50
MAX_VIEWPORT_LINES = 500
MAX_CONTENT_RETURN_BYTES = 64 * 1024  # 64 KB per viewport response

# Access log bounds: trim to TRIM size when MAX is reached
MAX_ACCESS_LOG_ENTRIES = 10000
TRIMMED_ACCESS_LOG_ENTRIES = 5000


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ContentManifest:
    """
    Structural index of an artifact's content.

    Generated on first access and cached. Provides the metadata needed to
    construct viewport ranges without loading the full content.
    """
    artifact_id: str
    tenant_id: str
    content_type: ContentType
    total_lines: int
    total_bytes: int
    total_sections: int
    section_index: List[Dict[str, Any]]  # [{name, start_line, end_line}, ...]
    checksum: str                         # SHA-256 of raw content
    created_at: str
    origin: ViewportOrigin

    def to_dict(self) -> Dict[str, Any]:
        return {
            'artifact_id': self.artifact_id,
            'tenant_id': self.tenant_id,
            'content_type': self.content_type.value,
            'total_lines': self.total_lines,
            'total_bytes': self.total_bytes,
            'total_sections': self.total_sections,
            'section_index': self.section_index,
            'checksum': self.checksum,
            'created_at': self.created_at,
            'origin': self.origin.value,
        }


@dataclass
class ViewportRange:
    """
    Specifies the window boundaries for a content projection.

    For text content: start_line and end_line (1-indexed, inclusive).
    For structured content: key_path (dot-separated) and depth limit.
    """
    start_line: int = 1
    end_line: int = -1          # -1 means "to end of content"
    key_path: Optional[str] = None   # For structured content: "execution_graph.steps"
    depth: int = 3                    # Max nesting depth for structured projections


@dataclass
class ViewportProjection:
    """
    The result of applying a ViewportRange to an artifact's content.

    Contains the extracted slice plus navigation metadata.
    """
    artifact_id: str
    tenant_id: str
    content_type: ContentType
    lines: List[str]               # Numbered lines of the projection
    range_start: int               # Actual start line returned
    range_end: int                 # Actual end line returned
    total_lines: int               # Total lines in full content
    truncated: bool                # True if content was clipped to MAX_VIEWPORT_LINES
    checksum: str                  # Checksum of full content (for staleness detection)
    origin: ViewportOrigin

    def to_dict(self) -> Dict[str, Any]:
        return {
            'artifact_id': self.artifact_id,
            'tenant_id': self.tenant_id,
            'content_type': self.content_type.value,
            'lines': self.lines,
            'range_start': self.range_start,
            'range_end': self.range_end,
            'total_lines': self.total_lines,
            'truncated': self.truncated,
            'checksum': self.checksum,
            'origin': self.origin.value,
        }


# ============================================================================
# CONTENT SERIALIZERS
# ============================================================================

def _content_to_lines(content: Any) -> Tuple[List[str], ContentType]:
    """
    Normalize any artifact content into numbered text lines.

    Handles:
    - str: split by newlines
    - dict/list: pretty-print as JSON
    - other: repr() fallback
    """
    if isinstance(content, str):
        lines = content.split('\n')
        return lines, ContentType.TEXT
    elif isinstance(content, dict):
        text = json.dumps(content, indent=2, default=str)
        return text.split('\n'), ContentType.STRUCTURED
    elif isinstance(content, list):
        text = json.dumps(content, indent=2, default=str)
        return text.split('\n'), ContentType.TABULAR
    else:
        text = repr(content)
        return text.split('\n'), ContentType.TEXT


def _compute_checksum(content: Any) -> str:
    """Compute SHA-256 of serialized content."""
    if isinstance(content, str):
        raw = content.encode('utf-8')
    else:
        raw = json.dumps(content, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _build_section_index(lines: List[str], content_type: ContentType) -> List[Dict[str, Any]]:
    """
    Build a section index from content lines.

    For text: sections are delimited by markdown headers (# Header) or blank-line gaps.
    For structured: top-level keys become sections.
    """
    sections = []
    if content_type == ContentType.TEXT:
        current_section = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('#') or (stripped.startswith('===') and i > 0):
                if current_section:
                    current_section['end_line'] = i  # exclusive
                    sections.append(current_section)
                header = stripped.lstrip('#').strip() or f"Section {len(sections) + 1}"
                current_section = {'name': header, 'start_line': i + 1, 'end_line': len(lines)}
        if current_section:
            current_section['end_line'] = len(lines)
            sections.append(current_section)
    elif content_type == ContentType.STRUCTURED:
        # For JSON, map top-level keys to line ranges
        current_key = None
        key_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('"') and ':' in stripped and not line.startswith('    '):
                if current_key:
                    sections.append({
                        'name': current_key,
                        'start_line': key_start + 1,
                        'end_line': i
                    })
                current_key = stripped.split('"')[1]
                key_start = i
        if current_key:
            sections.append({
                'name': current_key,
                'start_line': key_start + 1,
                'end_line': len(lines)
            })

    # Fallback: if no sections detected, treat entire content as one section
    if not sections:
        sections = [{'name': 'content', 'start_line': 1, 'end_line': len(lines)}]

    return sections


def _extract_key_path(content: Any, key_path: str, depth: int = 3) -> Any:
    """
    Navigate into structured content by dot-separated key path.

    Example: _extract_key_path(data, "execution_graph.steps", depth=2)
    """
    if not key_path or not isinstance(content, dict):
        return content

    keys = key_path.split('.')
    current = content
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list):
            try:
                idx = int(key)
                current = current[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None

    # Truncate nested structures to requested depth
    return _truncate_depth(current, depth)


def _truncate_depth(obj: Any, depth: int) -> Any:
    """Truncate nested structures beyond a given depth."""
    if depth <= 0:
        if isinstance(obj, dict):
            return {k: f"<{type(v).__name__}>" for k, v in obj.items()}
        elif isinstance(obj, list):
            return f"<list[{len(obj)}]>"
        return obj
    if isinstance(obj, dict):
        return {k: _truncate_depth(v, depth - 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_depth(item, depth - 1) for item in obj]
    return obj


# ============================================================================
# ARTIFACT VIEWPORT SERVICE
# ============================================================================

class ArtifactViewport:
    """
    Range-based content inspection service for Murphy System artifacts.

    Provides windowed, read-only access to artifact content across all
    memory planes, persisted documents, and librarian-generated materials.

    Thread-safe. Tenant-isolated. Audit-logged.
    """

    def __init__(self):
        self._manifest_cache: Dict[str, ContentManifest] = {}
        self._lock = threading.Lock()
        self._access_log: List[Dict[str, Any]] = []

    # ── Manifest Operations ──────────────────────────────────────────

    def get_manifest(
        self,
        artifact_id: str,
        content: Any,
        tenant_id: str,
        origin: ViewportOrigin = ViewportOrigin.WORKING,
    ) -> ContentManifest:
        """
        Get or create a ContentManifest for an artifact.

        The manifest provides structural metadata (line count, sections,
        checksum) without returning the full content.
        """
        cache_key = f"{tenant_id}:{origin.value}:{artifact_id}"

        with self._lock:
            if cache_key in self._manifest_cache:
                cached = self._manifest_cache[cache_key]
                # Verify checksum hasn't changed
                current_checksum = _compute_checksum(content)
                if cached.checksum == current_checksum:
                    return cached

        # Build fresh manifest
        lines, content_type = _content_to_lines(content)
        checksum = _compute_checksum(content)
        section_index = _build_section_index(lines, content_type)

        manifest = ContentManifest(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content_type=content_type,
            total_lines=len(lines),
            total_bytes=sum(len(l.encode('utf-8')) for l in lines),
            total_sections=len(section_index),
            section_index=section_index,
            checksum=checksum,
            created_at=datetime.now(timezone.utc).isoformat(),
            origin=origin,
        )

        with self._lock:
            self._manifest_cache[cache_key] = manifest

        return manifest

    # ── Projection Operations ────────────────────────────────────────

    def project(
        self,
        artifact_id: str,
        content: Any,
        tenant_id: str,
        viewport_range: Optional[ViewportRange] = None,
        origin: ViewportOrigin = ViewportOrigin.WORKING,
    ) -> ViewportProjection:
        """
        Project a viewport range onto artifact content.

        Returns a windowed slice of the content as numbered lines,
        analogous to `view_range` parameters.

        Args:
            artifact_id: Unique artifact identifier
            content: The raw artifact content (str, dict, list)
            tenant_id: Tenant isolation key
            viewport_range: Optional range specification. Defaults to first DEFAULT_VIEWPORT_LINES.
            origin: Source memory plane

        Returns:
            ViewportProjection with the extracted content slice
        """
        if viewport_range is None:
            viewport_range = ViewportRange(start_line=1, end_line=DEFAULT_VIEWPORT_LINES)

        # Handle key_path extraction for structured content
        effective_content = content
        if viewport_range.key_path and isinstance(content, (dict, list)):
            extracted = _extract_key_path(content, viewport_range.key_path, viewport_range.depth)
            if extracted is not None:
                effective_content = extracted

        lines, content_type = _content_to_lines(effective_content)
        checksum = _compute_checksum(content)
        total_lines = len(lines)

        # Clamp range to valid bounds (1-indexed)
        start = max(1, viewport_range.start_line)
        end = viewport_range.end_line
        if end == -1 or end > total_lines:
            end = total_lines
        end = max(start, end)

        # Enforce max viewport size
        truncated = False
        if (end - start + 1) > MAX_VIEWPORT_LINES:
            end = start + MAX_VIEWPORT_LINES - 1
            truncated = True

        # Extract the slice (convert to 0-indexed for list access)
        selected = lines[start - 1:end]

        # Format as numbered lines: "N. content"
        numbered = [f"{start + i}. {line}" for i, line in enumerate(selected)]

        # Log access
        self._log_access(artifact_id, tenant_id, origin, start, end)

        return ViewportProjection(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content_type=content_type,
            lines=numbered,
            range_start=start,
            range_end=min(end, total_lines),
            total_lines=total_lines,
            truncated=truncated,
            checksum=checksum,
            origin=origin,
        )

    # ── Convenience Methods ──────────────────────────────────────────

    def project_section(
        self,
        artifact_id: str,
        content: Any,
        tenant_id: str,
        section_name: str,
        origin: ViewportOrigin = ViewportOrigin.WORKING,
    ) -> Optional[ViewportProjection]:
        """
        Project a named section of an artifact.

        Uses the section index from the manifest to determine the range.
        """
        manifest = self.get_manifest(artifact_id, content, tenant_id, origin)

        for section in manifest.section_index:
            if section['name'].lower() == section_name.lower():
                vrange = ViewportRange(
                    start_line=section['start_line'],
                    end_line=section['end_line'],
                )
                return self.project(artifact_id, content, tenant_id, vrange, origin)

        return None

    def project_head(
        self,
        artifact_id: str,
        content: Any,
        tenant_id: str,
        num_lines: int = DEFAULT_VIEWPORT_LINES,
        origin: ViewportOrigin = ViewportOrigin.WORKING,
    ) -> ViewportProjection:
        """Return the first N lines of an artifact."""
        return self.project(
            artifact_id, content, tenant_id,
            ViewportRange(start_line=1, end_line=num_lines),
            origin,
        )

    def project_tail(
        self,
        artifact_id: str,
        content: Any,
        tenant_id: str,
        num_lines: int = DEFAULT_VIEWPORT_LINES,
        origin: ViewportOrigin = ViewportOrigin.WORKING,
    ) -> ViewportProjection:
        """Return the last N lines of an artifact."""
        lines, _ = _content_to_lines(content)
        total = len(lines)
        start = max(1, total - num_lines + 1)
        return self.project(
            artifact_id, content, tenant_id,
            ViewportRange(start_line=start, end_line=total),
            origin,
        )

    def search_content(
        self,
        artifact_id: str,
        content: Any,
        tenant_id: str,
        query: str,
        context_lines: int = 3,
        origin: ViewportOrigin = ViewportOrigin.WORKING,
    ) -> List[Dict[str, Any]]:
        """
        Search within artifact content and return matching line ranges with context.

        Returns list of match results with surrounding context lines.
        """
        lines, content_type = _content_to_lines(content)
        results = []
        query_lower = query.lower()

        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = [
                    f"{start + j + 1}. {lines[start + j]}"
                    for j in range(end - start)
                ]
                results.append({
                    'match_line': i + 1,
                    'match_text': line.strip(),
                    'context': context,
                })

        self._log_access(artifact_id, tenant_id, origin, 0, 0, search_query=query)
        return results

    # ── Access Logging ───────────────────────────────────────────────

    def _log_access(
        self,
        artifact_id: str,
        tenant_id: str,
        origin: ViewportOrigin,
        start: int,
        end: int,
        search_query: Optional[str] = None,
    ):
        """Record viewport access for audit trail."""
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'artifact_id': artifact_id,
            'tenant_id': tenant_id,
            'origin': origin.value,
            'range': [start, end],
            'search_query': search_query,
        }
        with self._lock:
            self._access_log.append(entry)
            # Keep bounded
            if len(self._access_log) > MAX_ACCESS_LOG_ENTRIES:
                self._access_log = self._access_log[-TRIMMED_ACCESS_LOG_ENTRIES:]

    def get_access_log(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve viewport access log, optionally filtered by tenant."""
        with self._lock:
            entries = self._access_log
            if tenant_id:
                entries = [e for e in entries if e['tenant_id'] == tenant_id]
            return entries[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Return viewport service statistics."""
        with self._lock:
            return {
                'cached_manifests': len(self._manifest_cache),
                'total_accesses': len(self._access_log),
            }

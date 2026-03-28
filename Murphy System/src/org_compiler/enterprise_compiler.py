"""
Enterprise-Scale Role Template Compiler

Designed for large organizations with 12-30+ roles and 1000+ employees.

Features:
- Batch processing for multiple roles
- Parallel compilation
- Multi-level caching
- Pagination support
- Dependency graph management
- Streaming support
- Efficient indexing
- Memory optimization
"""

import hashlib
import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

import logging

from .schemas import (
    ArtifactType,
    AuthorityLevel,
    ComplianceConstraint,
    EscalationPath,
    HandoffEvent,
    OrgChartNode,
    ProcessFlow,
    RoleMetrics,
    RoleTemplate,
    WorkArtifact,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for compiled templates"""
    template: RoleTemplate
    timestamp: float
    dependencies: Set[str]
    ttl: int = 3600  # 1 hour default

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.timestamp > self.ttl


@dataclass
class PaginatedResult:
    """Paginated compilation result"""
    templates: List[RoleTemplate]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next_page: bool
    has_prev_page: bool


class CompilationCache:
    """Multi-level caching for compiled templates"""

    def __init__(self, max_l1_size: int = 100, max_l2_size: int = 1000, cache_ttl: int = 3600):
        self._l1_cache: Dict[str, CacheEntry] = {}  # Fast memory cache
        self._l2_cache: Dict[str, CacheEntry] = {}  # Larger memory cache
        self._l3_persistent: Dict[str, dict] = {}  # Simulated disk cache
        self._lock = threading.RLock()
        self._max_l1_size = max_l1_size
        self._max_l2_size = max_l2_size
        self._cache_ttl = cache_ttl

    def get(self, role_name: str) -> Optional[RoleTemplate]:
        """Get template from cache"""
        with self._lock:
            expired = False
            # Check L1 cache (fastest)
            if role_name in self._l1_cache:
                entry = self._l1_cache[role_name]
                if not entry.is_expired():
                    return entry.template
                else:
                    del self._l1_cache[role_name]
                    expired = True

            # Check L2 cache
            if role_name in self._l2_cache:
                entry = self._l2_cache[role_name]
                if not entry.is_expired():
                    # Promote to L1
                    self._add_to_l1(role_name, entry)
                    return entry.template
                else:
                    del self._l2_cache[role_name]
                    expired = True

            # If L1 or L2 had an expired entry, also remove from L3
            if expired:
                self._l3_persistent.pop(role_name, None)
                return None

            # Check L3 cache (simulated disk)
            if role_name in self._l3_persistent:
                template_dict = self._l3_persistent[role_name]
                template = self._dict_to_template(template_dict)
                if template:
                    self.set(role_name, template)
                    return template

            return None

    def set(self, role_name: str, template: RoleTemplate, ttl: Optional[int] = None):
        """Cache a template"""
        with self._lock:
            # Use provided TTL or default
            cache_ttl = ttl if ttl is not None else self._cache_ttl

            entry = CacheEntry(
                template=template,
                timestamp=time.time(),
                dependencies=set(),
                ttl=cache_ttl
            )

            self._add_to_l1(role_name, entry)
            self._add_to_l2(role_name, entry)

            # Simulate disk storage
            self._l3_persistent[role_name] = self._template_to_dict(template)

    def _add_to_l1(self, role_name: str, entry: CacheEntry):
        """Add to L1 cache with LRU eviction"""
        if len(self._l1_cache) >= self._max_l1_size:
            # Remove oldest entry
            oldest_key = min(self._l1_cache.keys(),
                           key=lambda k: self._l1_cache[k].timestamp)
            del self._l1_cache[oldest_key]

        self._l1_cache[role_name] = entry

    def _add_to_l2(self, role_name: str, entry: CacheEntry):
        """Add to L2 cache"""
        if len(self._l2_cache) >= self._max_l2_size:
            # Remove oldest entry
            oldest_key = min(self._l2_cache.keys(),
                           key=lambda k: self._l2_cache[k].timestamp)
            del self._l2_cache[oldest_key]

        self._l2_cache[role_name] = entry

    def invalidate(self, role_name: str):
        """Invalidate cache entry"""
        with self._lock:
            self._l1_cache.pop(role_name, None)
            self._l2_cache.pop(role_name, None)
            self._l3_persistent.pop(role_name, None)

    def clear(self):
        """Clear all caches"""
        with self._lock:
            self._l1_cache.clear()
            self._l2_cache.clear()
            self._l3_persistent.clear()

    def _template_to_dict(self, template: RoleTemplate) -> dict:
        """Convert template to dict for storage"""
        return {
            'role_id': template.role_id,
            'role_name': template.role_name,
            'responsibilities': template.responsibilities,
            'decision_authority': template.decision_authority.value,
            'input_artifacts': [a.value for a in template.input_artifacts],
            'output_artifacts': [a.value for a in template.output_artifacts],
            'escalation_paths': [
                {
                    'path_id': p.path_id,
                    'from_role': p.from_role,
                    'to_role': p.to_role,
                    'trigger_conditions': p.trigger_conditions,
                    'sla_hours': p.sla_hours,
                    'requires_human': p.requires_human,
                    'immutable': p.immutable
                }
                for p in template.escalation_paths
            ],
            'compliance_constraints': [
                {
                    'constraint_id': c.constraint_id,
                    'regulation': c.regulation,
                    'description': c.description,
                    'verification_required': c.verification_required,
                    'human_signoff_required': c.human_signoff_required,
                    'audit_trail_required': c.audit_trail_required
                }
                for c in template.compliance_constraints
            ],
            'requires_human_signoff': template.requires_human_signoff,
            'metrics': {
                'sla_targets': template.metrics.sla_targets,
                'quality_gates': template.metrics.quality_gates,
                'throughput_target': template.metrics.throughput_target,
                'error_rate_max': template.metrics.error_rate_max
            },
            'version': template.version,
            'created_at': template.created_at.isoformat(),
        }

    def _dict_to_template(self, data: dict) -> Optional[RoleTemplate]:
        """Convert dict to template"""
        try:
            # Convert escalation paths
            escalation_paths = []
            for p_data in data.get('escalation_paths', []):
                escalation_paths.append(EscalationPath(
                    path_id=p_data['path_id'],
                    from_role=p_data['from_role'],
                    to_role=p_data['to_role'],
                    trigger_conditions=p_data['trigger_conditions'],
                    sla_hours=p_data['sla_hours'],
                    requires_human=p_data['requires_human'],
                    immutable=p_data['immutable']
                ))

            # Convert compliance constraints
            compliance_constraints = []
            for c_data in data.get('compliance_constraints', []):
                compliance_constraints.append(ComplianceConstraint(
                    constraint_id=c_data['constraint_id'],
                    regulation=c_data['regulation'],
                    description=c_data['description'],
                    verification_required=c_data['verification_required'],
                    human_signoff_required=c_data['human_signoff_required'],
                    audit_trail_required=c_data['audit_trail_required']
                ))

            # Convert metrics
            metrics_data = data.get('metrics', {})
            metrics = RoleMetrics(
                sla_targets=metrics_data.get('sla_targets', {}),
                quality_gates=metrics_data.get('quality_gates', []),
                throughput_target=metrics_data.get('throughput_target'),
                error_rate_max=metrics_data.get('error_rate_max')
            )

            return RoleTemplate(
                role_id=data['role_id'],
                role_name=data['role_name'],
                responsibilities=data['responsibilities'],
                decision_authority=AuthorityLevel(data['decision_authority']),
                input_artifacts=[ArtifactType(a) for a in data.get('input_artifacts', [])],
                output_artifacts=[ArtifactType(a) for a in data.get('output_artifacts', [])],
                escalation_paths=escalation_paths,
                compliance_constraints=compliance_constraints,
                requires_human_signoff=data.get('requires_human_signoff', []),
                metrics=metrics,
                version=data['version'],
                created_at=datetime.fromisoformat(data['created_at']),
            )
        except (KeyError, ValueError) as exc:
            logger.debug("Suppressed exception: %s", exc)
            return None


class RoleIndex:
    """Index for fast role lookups"""

    def __init__(self):
        self._by_department: Dict[str, Set[str]] = defaultdict(set)
        self._by_team: Dict[str, Set[str]] = defaultdict(set)
        self._by_authority: Dict[AuthorityLevel, Set[str]] = defaultdict(set)
        self._by_reports_to: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()

    def index_role(self, role: OrgChartNode):
        """Index a role"""
        with self._lock:
            self._by_department[role.department].add(role.role_name)
            self._by_team[role.team].add(role.role_name)
            self._by_authority[role.authority_level].add(role.role_name)
            if role.reports_to:
                self._by_reports_to[role.reports_to].add(role.role_name)

    def query(self, criteria: Dict) -> Set[str]:
        """Query roles by criteria"""
        with self._lock:
            results = set()

            if 'department' in criteria:
                results |= self._by_department[criteria['department']]

            if 'team' in criteria:
                results |= self._by_team[criteria['team']]

            if 'authority_level' in criteria:
                results |= self._by_authority[criteria['authority_level']]

            if 'reports_to' in criteria:
                results |= self._by_reports_to[criteria['reports_to']]

            return results

    def remove_role(self, role_name: str):
        """Remove role from index"""
        with self._lock:
            for index in [self._by_department, self._by_team, self._by_authority, self._by_reports_to]:
                for key in index.keys():
                    index[key].discard(role_name)


class EnterpriseRoleTemplateCompiler:
    """
    Enterprise-grade compiler for large organizations

    Supports:
    - 12-30+ roles (small org)
    - 31-100 roles (medium org)
    - 101-500 roles (large org)
    - 500+ roles (enterprise)
    """

    def __init__(
        self,
        batch_size: int = 50,
        max_workers: int = 4,
        cache_ttl: int = 3600
    ):
        # Core data
        self.org_nodes: Dict[str, OrgChartNode] = {}
        self.process_flows: List[ProcessFlow] = []
        self.sop_data: Dict[str, Dict] = {}
        self.handoff_events: List[HandoffEvent] = []
        self.work_artifacts: List[WorkArtifact] = []

        # Enterprise features
        self._cache = CompilationCache()
        self._index = RoleIndex()
        self._dependency_graph: Optional[Any] = None

        # Performance settings
        self._batch_size = batch_size
        self._max_workers = max_workers
        self._cache_ttl = cache_ttl
        self._lock = threading.RLock()

        # Build dependency graph if networkx is available
        if NETWORKX_AVAILABLE:
            self._dependency_graph = nx.DiGraph()

    # ============================================================================
    # BATCH PROCESSING
    # ============================================================================

    def compile_batch(self, role_names: List[str]) -> Dict[str, RoleTemplate]:
        """Compile multiple roles in parallel"""
        results = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all compilation tasks using cached compile method
            future_to_role = {
                executor.submit(self.compile, role): role
                for role in role_names
            }

            # Collect results as they complete
            for future in as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    results[role] = future.result()
                except Exception as exc:
                    # Log error but continue
                    logger.info(f"Error compiling {role}: {exc}")
                    results[role] = None

        return results

    def compile_all_parallel(self) -> List[RoleTemplate]:
        """Compile all roles in parallel using batches"""
        role_names = list(self.org_nodes.keys())

        if not role_names:
            return []

        all_templates = []

        # Process in batches
        for i in range(0, len(role_names), self._batch_size):
            batch = role_names[i:i + self._batch_size]
            batch_results = self.compile_batch(batch)

            # Filter out failed compilations
            for role, template in batch_results.items():
                if template is not None:
                    all_templates.append(template)

        return all_templates

    # ============================================================================
    # PAGINATION
    # ============================================================================

    def compile_paginated(
        self,
        page: int = 1,
        page_size: int = 50,
        filter_criteria: Optional[Dict] = None
    ) -> PaginatedResult:
        """Compile roles with pagination"""

        # Filter roles
        if filter_criteria:
            filtered_names = list(self._index.query(filter_criteria))
        else:
            filtered_names = list(self.org_nodes.keys())

        total = len(filtered_names)

        # Calculate pagination
        start = (page - 1) * page_size
        end = start + page_size
        page_names = filtered_names[start:end]

        # Compile page
        templates = []
        for name in page_names:
            try:
                template = self.compile(name)
                if template:
                    templates.append(template)
            except Exception as exc:
                logger.info(f"Error compiling {name}: {exc}")

        total_pages = (total + page_size - 1) // page_size

        return PaginatedResult(
            templates=templates,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next_page=end < total,
            has_prev_page=page > 1
        )

    # ============================================================================
    # STREAMING
    # ============================================================================

    def compile_stream(self, role_names: Optional[List[str]] = None) -> Iterator[RoleTemplate]:
        """Stream compilation results"""

        if role_names is None:
            role_names = list(self.org_nodes.keys())

        for role_name in role_names:
            try:
                template = self.compile(role_name)
                if template:
                    yield template
            except Exception as exc:
                logger.info(f"Error compiling {role_name}: {exc}")
                yield None

    # ============================================================================
    # DEPENDENCY GRAPH
    # ============================================================================

    def build_dependency_graph(self) -> Optional[Any]:
        """Build dependency graph for all roles"""

        if not NETWORKX_AVAILABLE:
            logger.info("NetworkX not available, dependency graph disabled")
            return None

        graph = nx.DiGraph()

        # Add all roles as nodes
        for role_name in self.org_nodes.keys():
            graph.add_node(role_name)

        # Add edges for escalation paths (from org nodes)
        for role_name, role_node in self.org_nodes.items():
            if hasattr(role_node, 'escalation_paths'):
                for escalation_path in role_node.escalation_paths:
                    graph.add_edge(
                        role_name,
                        escalation_path.to_role,
                        relationship="escalation"
                    )

        # Add edges for handoffs
        for handoff in self.handoff_events:
            graph.add_edge(
                handoff.from_role,
                handoff.to_role,
                relationship="handoff"
            )

        self._dependency_graph = graph
        return graph

    def get_dependencies(self, role_name: str) -> Set[str]:
        """Get all dependencies for a role"""

        if not self._dependency_graph or not NETWORKX_AVAILABLE:
            return set()

        try:
            return set(nx.descendants(self._dependency_graph, role_name))
        except nx.NetworkXError:
            return set()

    # ============================================================================
    # DATA MANAGEMENT
    # ============================================================================

    def add_org_chart(self, nodes: List[OrgChartNode]):
        """Add organizational chart data with indexing"""
        with self._lock:
            for node in nodes:
                self.org_nodes[node.role_name] = node
                self._index.index_role(node)

    def add_process_flow(self, flow: ProcessFlow):
        """Add process flow data"""
        with self._lock:
            self.process_flows.append(flow)

    def add_sop_data(self, role_name: str, sop_data: Dict):
        """Add SOP data for a role"""
        with self._lock:
            self.sop_data[role_name] = sop_data

    def add_handoff_events(self, events: List[HandoffEvent]):
        """Add handoff event data"""
        with self._lock:
            self.handoff_events.extend(events)

    def add_work_artifacts(self, artifacts: List[WorkArtifact]):
        """Add work artifact data"""
        with self._lock:
            self.work_artifacts.extend(artifacts)

    # ============================================================================
    # CORE COMPILATION (inherited from base compiler)
    # ============================================================================

    def compile(self, role_name: str) -> RoleTemplate:
        """Compile a role template with caching"""

        # Check cache first
        cached = self._cache.get(role_name)
        if cached:
            return cached

        # Compile from scratch
        template = self._compile_role(role_name)

        # Cache the result
        if template:
            self._cache.set(role_name, template, ttl=self._cache_ttl)

        return template

    def _compile_role(self, role_name: str) -> RoleTemplate:
        """Compile a single role template"""

        # Get org chart node
        org_node = self.org_nodes.get(role_name)
        if not org_node:
            raise ValueError(f"Role '{role_name}' not found in org chart")

        # Create role ID
        role_id = hashlib.sha256(role_name.encode()).hexdigest()[:16]

        # Extract responsibilities from metadata or use defaults
        responsibilities = []
        if hasattr(org_node, 'metadata') and 'responsibilities' in org_node.metadata:
            responsibilities = org_node.metadata['responsibilities']
        else:
            responsibilities = [f"Manage {org_node.team}", f"Execute {org_node.department} operations"]

        # Create template
        template = RoleTemplate(
            role_id=role_id,
            role_name=role_name,
            responsibilities=responsibilities,
            decision_authority=org_node.authority_level,
            input_artifacts=self._extract_input_artifacts(role_name),
            output_artifacts=self._extract_output_artifacts(role_name),
            escalation_paths=self._map_escalation_paths(role_name),
            compliance_constraints=self._detect_compliance_constraints(role_name),
            requires_human_signoff=self._identify_signoff_requirements(role_name),
            metrics=RoleMetrics(
                sla_targets={
                    "response_time_hours": 24.0,
                    "quality_score": 0.95,
                    "throughput_per_hour": 10.0
                },
                quality_gates=["compliance_check", "authority_validation"],
                throughput_target=10.0,
                error_rate_max=0.05
            ),
            version="1.0",
            created_at=datetime.now(timezone.utc),
            source_documents=[],
            integrity_hash=self._calculate_integrity_hash(role_name)
        )

        return template

    def _extract_input_artifacts(self, role_name: str) -> List[ArtifactType]:
        """Extract input artifacts for a role"""
        # Find handoffs where this role receives artifacts
        input_types = set()
        for handoff in self.handoff_events:
            if handoff.to_role == role_name:
                input_types.add(handoff.artifact.artifact_type)
        return list(input_types)

    def _extract_output_artifacts(self, role_name: str) -> List[ArtifactType]:
        """Extract output artifacts for a role"""
        # Find handoffs where this role sends artifacts
        output_types = set()
        for handoff in self.handoff_events:
            if handoff.from_role == role_name:
                output_types.add(handoff.artifact.artifact_type)
        return list(output_types)

    def _map_escalation_paths(self, role_name: str) -> List[EscalationPath]:
        """Map escalation paths for a role"""
        # Create escalation path based on reports_to
        org_node = self.org_nodes.get(role_name)
        if org_node and org_node.reports_to:
            # Create escalation path to manager
            return [
                EscalationPath(
                    path_id=f"escalation_{role_name}_{org_node.reports_to}",
                    from_role=role_name,
                    to_role=org_node.reports_to,
                    trigger_conditions=["critical_decisions", "exceeding_authority"],
                    sla_hours=24,
                    requires_human=True,
                    immutable=True
                )
            ]
        return []

    def _detect_compliance_constraints(self, role_name: str) -> List[ComplianceConstraint]:
        """Detect compliance constraints for a role"""
        # This would typically check against governance presets
        # For now, return empty list
        return []

    def _identify_signoff_requirements(self, role_name: str) -> bool:
        """Identify if human signoff is required"""
        org_node = self.org_nodes.get(role_name)
        if org_node:
            # Higher authority levels typically require signoff
            return org_node.authority_level in [
                AuthorityLevel.HIGH,
                AuthorityLevel.EXECUTIVE
            ]
        return False

    def _calculate_integrity_hash(self, role_name: str) -> str:
        """Calculate integrity hash for role template"""
        org_node = self.org_nodes.get(role_name)
        if not org_node:
            return ""

        data = f"{role_name}{org_node.authority_level.value}{org_node.department}{org_node.team}"
        return hashlib.sha256(data.encode()).hexdigest()

    # ============================================================================
    # UTILITIES
    # ============================================================================

    def get_statistics(self) -> Dict:
        """Get compilation statistics"""
        return {
            'total_roles': len(self.org_nodes),
            'total_processes': len(self.process_flows),
            'total_handoffs': len(self.handoff_events),
            'total_artifacts': len(self.work_artifacts),
            'cache_size_l1': len(self._cache._l1_cache),
            'cache_size_l2': len(self._cache._l2_cache),
            'indexed_roles': sum(len(roles) for roles in self._index._by_department.values()),
        }

    def clear_cache(self):
        """Clear compilation cache"""
        self._cache.clear()

    def rebuild_index(self):
        """Rebuild role index"""
        self._index = RoleIndex()
        for node in self.org_nodes.values():
            self._index.index_role(node)


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_enterprise_compiler(
    batch_size: int = 50,
    max_workers: int = 4,
    cache_ttl: int = 3600
) -> EnterpriseRoleTemplateCompiler:
    """Create an enterprise compiler with default settings"""
    return EnterpriseRoleTemplateCompiler(
        batch_size=batch_size,
        max_workers=max_workers,
        cache_ttl=cache_ttl
    )

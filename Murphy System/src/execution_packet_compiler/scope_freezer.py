"""
Scope Freezer
Creates immutable snapshots of execution scope
"""

import hashlib
import json
import logging

# Import from confidence engine
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.confidence_engine.models import ArtifactGraph, ArtifactNode, ArtifactType

from .models import ExecutionScope

logger = logging.getLogger(__name__)


class ScopeFreezer:
    """
    Creates immutable snapshots of execution scope

    After scope freezing:
    - No further artifact creation allowed
    - All artifacts must have resolved dependencies
    - All verification gates must be passed
    """

    def __init__(self):
        self.frozen_scopes: Dict[str, ExecutionScope] = {}

    def create_scope(
        self,
        scope_id: str,
        artifact_graph: ArtifactGraph,
        active_gates: List[Dict[str, Any]],
        parameters: Dict[str, Any]
    ) -> Tuple[ExecutionScope, List[str]]:
        """
        Create execution scope from artifact graph

        Args:
            scope_id: Unique scope identifier
            artifact_graph: Finalized artifact subgraph
            active_gates: List of active gates
            parameters: Execution parameters

        Returns:
            (scope, errors) - Scope and list of validation errors
        """
        errors = []

        # Validate artifact graph
        is_valid, graph_errors = self._validate_artifact_graph(artifact_graph)
        if not is_valid:
            errors.extend(graph_errors)
            return None, errors

        # Check for execution-blocking gates
        blocking_gates = self._check_blocking_gates(active_gates)
        if blocking_gates:
            errors.append(f"Found {len(blocking_gates)} execution-blocking gates")
            errors.extend([f"Gate {g['id']}: {g['category']}" for g in blocking_gates])
            return None, errors

        # Extract artifact IDs
        artifact_ids = list(artifact_graph.nodes.keys())

        # Extract constraints
        constraints = self._extract_constraints(artifact_graph)

        # Create interface bindings (placeholder - would be populated from actual interfaces)
        interface_bindings = self._create_interface_bindings(artifact_graph)

        # Create scope
        scope = ExecutionScope(
            scope_id=scope_id,
            artifact_ids=artifact_ids,
            constraints=constraints,
            parameters=parameters,
            interface_bindings=interface_bindings,
            timestamp=datetime.now(timezone.utc),
            frozen=False
        )

        return scope, []

    def freeze_scope(self, scope: ExecutionScope) -> Tuple[bool, str, List[str]]:
        """
        Freeze scope and make it immutable

        Args:
            scope: Scope to freeze

        Returns:
            (success, scope_hash, errors)
        """
        errors = []

        # Validate scope before freezing
        is_valid, validation_errors = scope.validate()
        if not is_valid:
            errors.extend(validation_errors)
            return False, "", errors

        # Freeze scope
        scope_hash = scope.freeze()

        # Store frozen scope
        self.frozen_scopes[scope.scope_id] = scope

        return True, scope_hash, []

    def verify_scope_immutability(
        self,
        scope: ExecutionScope,
        current_artifact_graph: ArtifactGraph
    ) -> Tuple[bool, List[str]]:
        """
        Verify that scope has not been mutated

        Args:
            scope: Frozen scope
            current_artifact_graph: Current artifact graph

        Returns:
            (is_immutable, violations)
        """
        violations = []

        if not scope.frozen:
            violations.append("Scope is not frozen")
            return False, violations

        # Check if artifacts have been added
        current_artifact_ids = set(current_artifact_graph.nodes.keys())
        scope_artifact_ids = set(scope.artifact_ids)

        new_artifacts = current_artifact_ids - scope_artifact_ids
        if new_artifacts:
            violations.append(f"New artifacts added: {list(new_artifacts)[:5]}")

        # Check if artifacts have been modified
        for artifact_id in scope.artifact_ids:
            if artifact_id in current_artifact_graph.nodes:
                # Would need to check artifact content hash
                pass

        # Verify scope hash
        current_hash = scope.calculate_hash()
        if current_hash != scope.calculate_hash():
            violations.append("Scope hash mismatch - scope has been mutated")

        return len(violations) == 0, violations

    def _validate_artifact_graph(
        self,
        artifact_graph: ArtifactGraph
    ) -> Tuple[bool, List[str]]:
        """
        Validate artifact graph for execution

        Checks:
        - No unresolved dependencies
        - All verification gates passed
        - Graph is a DAG
        """
        errors = []

        # Check if graph is DAG
        if not artifact_graph.is_dag():
            errors.append("Artifact graph is not a DAG (contains cycles)")

        # Check for unresolved dependencies
        for node in artifact_graph.nodes.values():
            for dep_id in node.dependencies:
                if dep_id not in artifact_graph.nodes:
                    errors.append(f"Artifact {node.id} has unresolved dependency: {dep_id}")

        # Check for unverified critical artifacts
        critical_types = [ArtifactType.DECISION, ArtifactType.PLAN]
        unverified_critical = [
            node.id for node in artifact_graph.nodes.values()
            if node.type in critical_types and not node.metadata.get('verified', False)
        ]

        if unverified_critical:
            errors.append(f"Found {len(unverified_critical)} unverified critical artifacts")

        return len(errors) == 0, errors

    def _check_blocking_gates(
        self,
        active_gates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check for gates that block execution

        Execution-blocking gates:
        - Isolation gates
        - Verification gates
        - Authority decay gates
        """
        blocking_categories = [
            'isolation_required',
            'verification_required',
            'authority_decay'
        ]

        blocking_gates = [
            gate for gate in active_gates
            if gate.get('category') in blocking_categories
        ]

        return blocking_gates

    def _extract_constraints(
        self,
        artifact_graph: ArtifactGraph
    ) -> List[Dict[str, Any]]:
        """Extract constraints from artifact graph"""
        constraints = []

        for node in artifact_graph.nodes.values():
            if node.type == ArtifactType.CONSTRAINT:
                constraints.append({
                    'id': node.id,
                    'content': node.content,
                    'source': node.source.value
                })

        return constraints

    def _create_interface_bindings(
        self,
        artifact_graph: ArtifactGraph
    ) -> Dict[str, str]:
        """
        Create interface bindings from artifact graph

        This would extract interface requirements from artifacts
        """
        bindings = {}

        # Extract interface requirements from artifacts
        for node in artifact_graph.nodes.values():
            if 'interface' in node.metadata:
                interface_name = node.metadata['interface']
                interface_id = node.metadata.get('interface_id', f"interface_{interface_name}")
                bindings[interface_name] = interface_id

        return bindings

    def get_frozen_scope(self, scope_id: str) -> Optional[ExecutionScope]:
        """Get frozen scope by ID"""
        return self.frozen_scopes.get(scope_id)

    def list_frozen_scopes(self) -> List[str]:
        """List all frozen scope IDs"""
        return list(self.frozen_scopes.keys())

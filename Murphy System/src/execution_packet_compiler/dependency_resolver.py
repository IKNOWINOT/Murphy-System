"""
Dependency Resolver
Generates execution DAG with strict ordering
"""

import hashlib
import logging

# Import from confidence engine
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import ExecutionGraph, ExecutionScope, ExecutionStep, StepType

from src.confidence_engine.models import ArtifactGraph, ArtifactNode, ArtifactType

logger = logging.getLogger(__name__)


class DependencyResolver:
    """
    Generates execution DAG from artifact graph

    Rules:
    - Strict ordering (no branching without explicit gate)
    - All dependencies must be resolved
    - Only deterministic steps allowed
    """

    def __init__(self):
        self.step_counter = 0

    def resolve_dependencies(
        self,
        scope: ExecutionScope,
        artifact_graph: ArtifactGraph
    ) -> Tuple[ExecutionGraph, List[str]]:
        """
        Generate execution DAG from artifact graph

        Args:
            scope: Frozen execution scope
            artifact_graph: Artifact graph

        Returns:
            (execution_graph, errors)
        """
        errors = []

        # Verify scope is frozen
        if not scope.frozen:
            errors.append("Scope must be frozen before dependency resolution")
            return None, errors

        # Create execution graph
        graph_id = f"exec_graph_{scope.scope_id}"
        execution_graph = ExecutionGraph(graph_id=graph_id)

        # Get topological order of artifacts
        artifact_order = self._get_topological_order(artifact_graph)

        if not artifact_order:
            errors.append("Cannot determine execution order (graph may have cycles)")
            return None, errors

        # Convert artifacts to execution steps
        artifact_to_step = {}

        for artifact_id in artifact_order:
            artifact = artifact_graph.nodes[artifact_id]

            # Only convert executable artifacts
            if self._is_executable_artifact(artifact):
                step, step_errors = self._artifact_to_step(
                    artifact,
                    artifact_to_step,
                    scope
                )

                if step_errors:
                    errors.extend(step_errors)
                    continue

                if step:
                    execution_graph.add_step(step)
                    artifact_to_step[artifact_id] = step.step_id

        # Validate execution graph
        if not execution_graph.is_dag():
            errors.append("Generated execution graph is not a DAG")

        # Validate determinism
        is_det, det_errors = execution_graph.validate_determinism()
        if not is_det:
            errors.extend(det_errors)

        # Check for branching without gates
        branching_errors = self._check_branching(execution_graph)
        if branching_errors:
            errors.extend(branching_errors)

        return execution_graph, errors

    def _get_topological_order(
        self,
        artifact_graph: ArtifactGraph
    ) -> List[str]:
        """
        Get topological order of artifacts

        Returns:
            List of artifact IDs in execution order
        """
        if not artifact_graph.is_dag():
            return []

        in_degree = {node_id: 0 for node_id in artifact_graph.nodes}

        for node in artifact_graph.nodes.values():
            for dep_id in node.dependencies:
                if dep_id in in_degree:
                    in_degree[dep_id] += 1

        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            node = artifact_graph.nodes[node_id]
            for dep_id in node.dependencies:
                if dep_id in in_degree:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        queue.append(dep_id)

        return result if len(result) == len(artifact_graph.nodes) else []

    def _is_executable_artifact(self, artifact: ArtifactNode) -> bool:
        """
        Check if artifact represents an executable action

        Executable artifacts:
        - PLAN (contains execution steps)
        - DECISION (may trigger actions)
        """
        return artifact.type in [ArtifactType.PLAN, ArtifactType.DECISION]

    def _artifact_to_step(
        self,
        artifact: ArtifactNode,
        artifact_to_step: Dict[str, str],
        scope: ExecutionScope
    ) -> Tuple[Optional[ExecutionStep], List[str]]:
        """
        Convert artifact to execution step

        Args:
            artifact: Artifact to convert
            artifact_to_step: Mapping of artifact IDs to step IDs
            scope: Execution scope

        Returns:
            (step, errors)
        """
        errors = []

        # Generate step ID
        self.step_counter += 1
        step_id = f"step_{self.step_counter:04d}"

        # Determine step type from artifact content
        step_type = self._determine_step_type(artifact)

        if not step_type:
            errors.append(f"Cannot determine step type for artifact {artifact.id}")
            return None, errors

        # Extract inputs and outputs
        inputs = artifact.content.get('inputs', {})
        outputs = artifact.content.get('outputs', {})

        # Map artifact dependencies to step dependencies
        step_dependencies = []
        for dep_id in artifact.dependencies:
            if dep_id in artifact_to_step:
                step_dependencies.append(artifact_to_step[dep_id])

        # Get interface binding
        interface_binding = scope.interface_bindings.get(
            artifact.content.get('interface', ''),
            None
        )

        # Create step
        step = ExecutionStep(
            step_id=step_id,
            step_type=step_type,
            description=artifact.content.get('description', f"Execute {artifact.id}"),
            inputs=inputs,
            outputs=outputs,
            dependencies=step_dependencies,
            interface_binding=interface_binding,
            deterministic=True,
            verified=artifact.metadata.get('verified', False),
            metadata={
                'artifact_id': artifact.id,
                'artifact_type': artifact.type.value
            }
        )

        # Validate step determinism
        is_det, reason = step.validate_determinism()
        if not is_det:
            errors.append(f"Step {step_id}: {reason}")

        return step, errors

    def _determine_step_type(self, artifact: ArtifactNode) -> Optional[StepType]:
        """
        Determine execution step type from artifact

        Looks at artifact content and metadata to determine type
        """
        content = artifact.content

        # Check for explicit step type
        if 'step_type' in content:
            try:
                return StepType(content['step_type'])
            except ValueError as exc:
                logger.debug("Suppressed %s: %s", type(exc).__name__, exc)  # noqa: E501

        # Infer from content
        if 'api_endpoint' in content or 'api_call' in content:
            return StepType.API_CALL

        if 'math_expression' in content or 'calculation' in content:
            return StepType.MATH_MODULE

        if 'code' in content or 'script' in content:
            return StepType.CODE_BLOCK

        if 'actuator' in content or 'robot_command' in content:
            return StepType.ACTUATOR_COMMAND

        if 'transform' in content or 'data_processing' in content:
            return StepType.DATA_TRANSFORM

        # Default to data transform
        return StepType.DATA_TRANSFORM

    def _check_branching(
        self,
        execution_graph: ExecutionGraph
    ) -> List[str]:
        """
        Check for branching without explicit gates

        No branching allowed unless explicitly gated
        """
        errors = []

        for step_id, step in execution_graph.steps.items():
            dependents = execution_graph.edges.get(step_id, [])

            # If step has multiple dependents, check for branching gate
            if len(dependents) > 1:
                has_gate = step.metadata.get('branching_gate', False)

                if not has_gate:
                    errors.append(
                        f"Step {step_id} has {len(dependents)} dependents but no branching gate"
                    )

        return errors

    def optimize_execution_order(
        self,
        execution_graph: ExecutionGraph
    ) -> ExecutionGraph:
        """
        Optimize execution order for efficiency

        While maintaining dependencies, reorder steps for:
        - Parallel execution opportunities
        - Resource utilization
        - Latency minimization
        """
        # Get current execution order
        current_order = execution_graph.get_execution_order()

        if not current_order:
            return execution_graph

        # For now, return as-is
        # Future: implement optimization algorithms

        return execution_graph

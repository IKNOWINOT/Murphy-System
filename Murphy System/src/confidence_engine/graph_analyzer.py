"""
Graph Analysis Engine
Analyzes artifact graphs for structure, contradictions, and completeness
"""

import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

from .models import ArtifactGraph, ArtifactNode, ArtifactSource, ArtifactType

logger = logging.getLogger(__name__)


class GraphAnalyzer:
    """
    Analyzes artifact graphs for:
    - DAG validation
    - Contradiction detection
    - Graph entropy (exploration completeness)
    - Dependency analysis
    """

    def __init__(self):
        self.contradiction_patterns = self._load_contradiction_patterns()

    def _load_contradiction_patterns(self) -> List[Dict[str, Any]]:
        """Load patterns that indicate contradictions"""
        return [
            {
                'name': 'incompatible_constraints',
                'check': self._check_incompatible_constraints
            },
            {
                'name': 'conflicting_decisions',
                'check': self._check_conflicting_decisions
            },
            {
                'name': 'assumption_mismatch',
                'check': self._check_assumption_mismatch
            },
            {
                'name': 'circular_dependency',
                'check': self._check_circular_dependency
            }
        ]

    def validate_dag(self, graph: ArtifactGraph) -> Tuple[bool, List[str]]:
        """
        Validate that graph is a DAG (no cycles)

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check for cycles
        if not graph.is_dag():
            errors.append("Graph contains cycles - not a valid DAG")
            # Find cycle
            cycle = self._find_cycle(graph)
            if cycle:
                errors.append(f"Cycle detected: {' -> '.join(cycle)}")

        # Check for orphaned nodes
        orphans = self._find_orphans(graph)
        if orphans:
            errors.append(f"Found {len(orphans)} orphaned nodes with no path to roots")

        # Check for missing dependencies
        missing = self._find_missing_dependencies(graph)
        if missing:
            errors.append(f"Found {len(missing)} references to non-existent nodes")

        return len(errors) == 0, errors

    def _find_cycle(self, graph: ArtifactGraph) -> List[str]:
        """Find a cycle in the graph if one exists"""
        visited = set()
        rec_stack = []

        def dfs(node_id: str) -> List[str]:
            visited.add(node_id)
            rec_stack.append(node_id)

            for dependent_id in graph.edges.get(node_id, []):
                if dependent_id not in visited:
                    cycle = dfs(dependent_id)
                    if cycle:
                        return cycle
                elif dependent_id in rec_stack:
                    # Found cycle
                    cycle_start = rec_stack.index(dependent_id)
                    return rec_stack[cycle_start:] + [dependent_id]

            rec_stack.pop()
            return []

        for node_id in graph.nodes:
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle:
                    return cycle

        return []

    def _find_orphans(self, graph: ArtifactGraph) -> List[str]:
        """Find nodes with no path to any root"""
        roots = {node.id for node in graph.get_roots()}
        if not roots:
            return []

        reachable = set()

        def dfs(node_id: str):
            if node_id in reachable:
                return
            reachable.add(node_id)
            for dependent_id in graph.edges.get(node_id, []):
                dfs(dependent_id)

        # Start from all roots
        for root_id in roots:
            dfs(root_id)

        # Orphans are nodes not reachable from any root
        all_nodes = set(graph.nodes.keys())
        orphans = all_nodes - reachable
        return list(orphans)

    def _find_missing_dependencies(self, graph: ArtifactGraph) -> List[Tuple[str, str]]:
        """Find references to non-existent nodes"""
        missing = []
        for node_id, node in graph.nodes.items():
            for dep_id in node.dependencies:
                if dep_id not in graph.nodes:
                    missing.append((node_id, dep_id))
        return missing

    def detect_contradictions(self, graph: ArtifactGraph) -> List[Dict[str, Any]]:
        """
        Detect contradictions in the graph

        Returns:
            List of contradiction reports
        """
        contradictions = []

        for pattern in self.contradiction_patterns:
            conflicts = pattern['check'](graph)
            if conflicts:
                contradictions.extend([
                    {
                        'type': pattern['name'],
                        'severity': conflict.get('severity', 'medium'),
                        'nodes': conflict.get('nodes', []),
                        'description': conflict.get('description', '')
                    }
                    for conflict in conflicts
                ])

        return contradictions

    def _check_incompatible_constraints(self, graph: ArtifactGraph) -> List[Dict[str, Any]]:
        """Check for constraints that cannot be satisfied together"""
        conflicts = []
        constraints = [node for node in graph.nodes.values()
                      if node.type == ArtifactType.CONSTRAINT]

        # Simple heuristic: check for opposite constraints
        for i, c1 in enumerate(constraints):
            for c2 in constraints[i+1:]:
                if self._are_incompatible(c1, c2):
                    conflicts.append({
                        'severity': 'high',
                        'nodes': [c1.id, c2.id],
                        'description': f"Constraints {c1.id} and {c2.id} are incompatible"
                    })

        return conflicts

    def _are_incompatible(self, c1: ArtifactNode, c2: ArtifactNode) -> bool:
        """Check if two constraints are incompatible"""
        # Simple keyword-based check
        content1 = str(c1.content).lower()
        content2 = str(c2.content).lower()

        # Check for opposite keywords
        opposites = [
            ('must', 'must not'),
            ('required', 'forbidden'),
            ('allow', 'deny'),
            ('enable', 'disable')
        ]

        for pos, neg in opposites:
            if pos in content1 and neg in content2:
                return True
            if neg in content1 and pos in content2:
                return True

        return False

    def _check_conflicting_decisions(self, graph: ArtifactGraph) -> List[Dict[str, Any]]:
        """Check for decisions that conflict"""
        conflicts = []
        decisions = [node for node in graph.nodes.values()
                    if node.type == ArtifactType.DECISION]

        # Group decisions by topic
        by_topic = defaultdict(list)
        for decision in decisions:
            topic = decision.content.get('topic', 'unknown')
            by_topic[topic].append(decision)

        # Check for conflicts within same topic
        for topic, topic_decisions in by_topic.items():
            if len(topic_decisions) > 1:
                # Multiple decisions on same topic - potential conflict
                conflicts.append({
                    'severity': 'medium',
                    'nodes': [d.id for d in topic_decisions],
                    'description': f"Multiple decisions on topic '{topic}'"
                })

        return conflicts

    def _check_assumption_mismatch(self, graph: ArtifactGraph) -> List[Dict[str, Any]]:
        """Check for mismatched assumptions"""
        conflicts = []

        # Find all hypotheses (assumptions)
        hypotheses = [node for node in graph.nodes.values()
                     if node.type == ArtifactType.HYPOTHESIS]

        # Check for contradictory hypotheses
        for i, h1 in enumerate(hypotheses):
            for h2 in hypotheses[i+1:]:
                if self._are_contradictory_hypotheses(h1, h2):
                    conflicts.append({
                        'severity': 'high',
                        'nodes': [h1.id, h2.id],
                        'description': f"Hypotheses {h1.id} and {h2.id} contradict"
                    })

        return conflicts

    def _are_contradictory_hypotheses(self, h1: ArtifactNode, h2: ArtifactNode) -> bool:
        """Check if two hypotheses contradict"""
        # Simple check: look for negation keywords
        content1 = str(h1.content).lower()
        content2 = str(h2.content).lower()

        negations = ['not', 'no', 'never', 'cannot', 'impossible']

        # If one contains negation and they share keywords, likely contradictory
        has_negation_1 = any(neg in content1 for neg in negations)
        has_negation_2 = any(neg in content2 for neg in negations)

        if has_negation_1 != has_negation_2:
            # One has negation, other doesn't - check for shared keywords
            words1 = set(content1.split())
            words2 = set(content2.split())
            shared = words1 & words2
            if len(shared) > 3:  # Significant overlap
                return True

        return False

    def _check_circular_dependency(self, graph: ArtifactGraph) -> List[Dict[str, Any]]:
        """Check for circular dependencies"""
        if not graph.is_dag():
            cycle = self._find_cycle(graph)
            if cycle:
                return [{
                    'severity': 'critical',
                    'nodes': cycle,
                    'description': f"Circular dependency: {' -> '.join(cycle)}"
                }]
        return []

    def calculate_entropy(self, graph: ArtifactGraph) -> float:
        """
        Calculate graph entropy (exploration completeness)

        Higher entropy = more exploration, more uncertainty
        Lower entropy = more focused, more certainty

        Returns:
            Entropy value [0, 1]
        """
        if not graph.nodes:
            return 0.0

        # Calculate type distribution entropy
        type_counts = defaultdict(int)
        for node in graph.nodes.values():
            type_counts[node.type] += 1

        total = len(graph.nodes)
        type_entropy = 0.0
        for count in type_counts.values():
            if count > 0:
                p = count / total
                type_entropy -= p * math.log2(p)

        # Normalize by max possible entropy
        max_entropy = math.log2(len(ArtifactType))
        type_entropy = type_entropy / max_entropy if max_entropy > 0 else 0.0

        # Calculate source distribution entropy
        source_counts = defaultdict(int)
        for node in graph.nodes.values():
            source_counts[node.source] += 1

        source_entropy = 0.0
        for count in source_counts.values():
            if count > 0:
                p = count / total
                source_entropy -= p * math.log2(p)

        max_source_entropy = math.log2(len(ArtifactSource))
        source_entropy = source_entropy / max_source_entropy if max_source_entropy > 0 else 0.0

        # Calculate branching factor (avg children per node)
        branching_factors = [len(graph.edges.get(node_id, []))
                           for node_id in graph.nodes]
        avg_branching = sum(branching_factors) / (len(branching_factors) or 1) if branching_factors else 0
        branching_score = min(1.0, avg_branching / 5.0)  # Normalize to [0, 1]

        # Combine metrics
        entropy = (type_entropy + source_entropy + branching_score) / 3.0

        return entropy

    def analyze_dependencies(self, graph: ArtifactGraph) -> Dict[str, Any]:
        """
        Analyze dependency structure

        Returns:
            Analysis report with metrics
        """
        if not graph.nodes:
            return {
                'total_nodes': 0,
                'total_edges': 0,
                'avg_dependencies': 0.0,
                'max_depth': 0,
                'roots': [],
                'leaves': []
            }

        # Calculate metrics
        total_nodes = len(graph.nodes)
        total_edges = sum(len(deps) for deps in graph.edges.values())

        dependency_counts = [len(node.dependencies) for node in graph.nodes.values()]
        avg_dependencies = sum(dependency_counts) / (len(dependency_counts) or 1)

        # Calculate max depth
        max_depth = self._calculate_max_depth(graph)

        # Get roots and leaves
        roots = [node.id for node in graph.get_roots()]
        leaves = [node.id for node in graph.get_leaves()]

        return {
            'total_nodes': total_nodes,
            'total_edges': total_edges,
            'avg_dependencies': avg_dependencies,
            'max_depth': max_depth,
            'roots': roots,
            'leaves': leaves,
            'root_count': len(roots),
            'leaf_count': len(leaves)
        }

    def _calculate_max_depth(self, graph: ArtifactGraph) -> int:
        """Calculate maximum depth from roots to leaves"""
        if not graph.nodes:
            return 0

        depths = {}

        def calculate_depth(node_id: str) -> int:
            if node_id in depths:
                return depths[node_id]

            node = graph.nodes.get(node_id)
            if not node or not node.dependencies:
                depths[node_id] = 0
                return 0

            max_dep_depth = max(calculate_depth(dep_id)
                              for dep_id in node.dependencies
                              if dep_id in graph.nodes)
            depths[node_id] = max_dep_depth + 1
            return depths[node_id]

        for node_id in graph.nodes:
            calculate_depth(node_id)

        return max(depths.values()) if depths else 0

"""
Determinism Enforcer
Validates that all execution steps are deterministic
"""

import logging
import re
from typing import Any, Dict, List, Set, Tuple

from .models import ExecutionGraph, ExecutionStep, StepType

logger = logging.getLogger(__name__)


class DeterminismEnforcer:
    """
    Enforces determinism in execution steps

    DESIGN LAW: No LLM calls allowed

    Each step must be:
    - API call (deterministic endpoint)
    - Math module (e.g., Wolfram)
    - Verified code block
    - Actuator command

    No LLM calls, no generation, no sampling allowed
    """

    def __init__(self):
        # Keywords that indicate non-deterministic operations
        self.non_deterministic_keywords = [
            'llm', 'gpt', 'generate', 'creative', 'sample', 'random',
            'stochastic', 'probabilistic', 'infer', 'guess', 'estimate'
        ]

        # Keywords that indicate LLM usage
        self.llm_keywords = [
            'openai', 'anthropic', 'claude', 'chatgpt', 'gpt-3', 'gpt-4',
            'llama', 'palm', 'bard', 'completion', 'chat', 'prompt'
        ]

        # Allowed deterministic operations
        self.allowed_operations = {
            StepType.API_CALL: self._validate_api_call,
            StepType.MATH_MODULE: self._validate_math_module,
            StepType.CODE_BLOCK: self._validate_code_block,
            StepType.ACTUATOR_COMMAND: self._validate_actuator_command,
            StepType.DATA_TRANSFORM: self._validate_data_transform
        }

    def enforce_determinism(
        self,
        execution_graph: ExecutionGraph
    ) -> Tuple[bool, List[str]]:
        """
        Enforce determinism across all execution steps

        Args:
            execution_graph: Execution graph to validate

        Returns:
            (is_deterministic, violations)
        """
        violations = []

        # Validate each step
        for step in execution_graph.steps.values():
            is_det, step_violations = self.validate_step(step)

            if not is_det:
                violations.extend([
                    f"Step {step.step_id}: {violation}"
                    for violation in step_violations
                ])

        # Check for LLM calls in graph
        llm_calls = self._detect_llm_calls(execution_graph)
        if llm_calls:
            violations.extend([
                f"LLM call detected in step {step_id}"
                for step_id in llm_calls
            ])

        return len(violations) == 0, violations

    def validate_step(
        self,
        step: ExecutionStep
    ) -> Tuple[bool, List[str]]:
        """
        Validate that a single step is deterministic

        Args:
            step: Execution step to validate

        Returns:
            (is_deterministic, violations)
        """
        violations = []

        # Check step type
        if step.step_type not in self.allowed_operations:
            violations.append(f"Invalid step type: {step.step_type}")
            return False, violations

        # Use type-specific validator
        validator = self.allowed_operations[step.step_type]
        is_valid, type_violations = validator(step)

        if not is_valid:
            violations.extend(type_violations)

        # Check description for non-deterministic keywords
        desc_violations = self._check_description(step.description)
        if desc_violations:
            violations.extend(desc_violations)

        # Check inputs for non-deterministic values
        input_violations = self._check_inputs(step.inputs)
        if input_violations:
            violations.extend(input_violations)

        return len(violations) == 0, violations

    def _validate_api_call(
        self,
        step: ExecutionStep
    ) -> Tuple[bool, List[str]]:
        """Validate API call step"""
        violations = []

        # Check for required fields
        if 'endpoint' not in step.inputs and 'url' not in step.inputs:
            violations.append("API call missing endpoint/url")

        # Check for LLM API endpoints
        endpoint = step.inputs.get('endpoint', step.inputs.get('url', ''))
        if isinstance(endpoint, str):
            endpoint_lower = endpoint.lower()
            for keyword in self.llm_keywords:
                if keyword in endpoint_lower:
                    violations.append(f"LLM API endpoint detected: {keyword}")

        # Check for deterministic parameters
        if 'temperature' in step.inputs or 'top_p' in step.inputs:
            violations.append("Sampling parameters detected (temperature/top_p)")

        return len(violations) == 0, violations

    def _validate_math_module(
        self,
        step: ExecutionStep
    ) -> Tuple[bool, List[str]]:
        """Validate math module step"""
        violations = []

        # Check for required fields
        if 'expression' not in step.inputs and 'equation' not in step.inputs:
            violations.append("Math module missing expression/equation")

        # Math modules are inherently deterministic

        return len(violations) == 0, violations

    def _validate_code_block(
        self,
        step: ExecutionStep
    ) -> Tuple[bool, List[str]]:
        """Validate code block step"""
        violations = []

        # Check for required fields
        if 'code' not in step.inputs and 'script' not in step.inputs:
            violations.append("Code block missing code/script")

        # Check if code is verified
        if not step.verified:
            violations.append("Code block not verified")

        # Check code for non-deterministic operations
        code = step.inputs.get('code', step.inputs.get('script', ''))
        if isinstance(code, str):
            code_lower = code.lower()

            # Check for random operations
            if 'random' in code_lower or 'rand(' in code_lower:
                violations.append("Random operations detected in code")

            # Check for LLM calls
            for keyword in self.llm_keywords:
                if keyword in code_lower:
                    violations.append(f"LLM call detected in code: {keyword}")

        return len(violations) == 0, violations

    def _validate_actuator_command(
        self,
        step: ExecutionStep
    ) -> Tuple[bool, List[str]]:
        """Validate actuator command step"""
        violations = []

        # Check for required fields
        if 'command' not in step.inputs and 'action' not in step.inputs:
            violations.append("Actuator command missing command/action")

        # Actuator commands should be deterministic

        return len(violations) == 0, violations

    def _validate_data_transform(
        self,
        step: ExecutionStep
    ) -> Tuple[bool, List[str]]:
        """Validate data transform step"""
        violations = []

        # Check for required fields
        if 'transform' not in step.inputs and 'operation' not in step.inputs:
            violations.append("Data transform missing transform/operation")

        # Data transforms should be deterministic

        return len(violations) == 0, violations

    def _check_description(self, description: str) -> List[str]:
        """Check description for non-deterministic keywords"""
        violations = []

        description_lower = description.lower()

        for keyword in self.non_deterministic_keywords:
            if keyword in description_lower:
                violations.append(f"Non-deterministic keyword in description: {keyword}")

        return violations

    def _check_inputs(self, inputs: Dict[str, Any]) -> List[str]:
        """Check inputs for non-deterministic values"""
        violations = []

        # Convert inputs to string for checking
        inputs_str = str(inputs).lower()

        for keyword in self.non_deterministic_keywords:
            if keyword in inputs_str:
                violations.append(f"Non-deterministic keyword in inputs: {keyword}")

        return violations

    def _detect_llm_calls(
        self,
        execution_graph: ExecutionGraph
    ) -> List[str]:
        """
        Detect LLM calls in execution graph

        Returns:
            List of step IDs with LLM calls
        """
        llm_steps = []

        for step_id, step in execution_graph.steps.items():
            # Check step type
            if step.step_type == StepType.API_CALL:
                # Check endpoint
                endpoint = step.inputs.get('endpoint', step.inputs.get('url', ''))
                if isinstance(endpoint, str):
                    endpoint_lower = endpoint.lower()
                    for keyword in self.llm_keywords:
                        if keyword in endpoint_lower:
                            llm_steps.append(step_id)
                            break

            # Check description
            description_lower = step.description.lower()
            for keyword in self.llm_keywords:
                if keyword in description_lower:
                    llm_steps.append(step_id)
                    break

        return llm_steps

    def block_llm_calls(
        self,
        execution_graph: ExecutionGraph
    ) -> Tuple[ExecutionGraph, List[str]]:
        """
        Block LLM calls by removing them from execution graph

        Args:
            execution_graph: Execution graph

        Returns:
            (cleaned_graph, blocked_step_ids)
        """
        llm_steps = self._detect_llm_calls(execution_graph)

        if not llm_steps:
            return execution_graph, []

        # Remove LLM steps
        for step_id in llm_steps:
            if step_id in execution_graph.steps:
                del execution_graph.steps[step_id]

            # Remove from edges
            if step_id in execution_graph.edges:
                del execution_graph.edges[step_id]

            # Remove from dependencies
            for edges in execution_graph.edges.values():
                if step_id in edges:
                    edges.remove(step_id)

        return execution_graph, llm_steps

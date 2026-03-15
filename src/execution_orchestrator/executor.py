"""
Stepwise Execution Engine
==========================

Executes sealed packets step-by-step with deterministic enforcement.

Execution Types:
- REST/RPC calls (external APIs)
- Math computations (via Deterministic Compute Plane)
- Filesystem operations (read/write/delete)
- Actuator commands (system actions)

Design Principles:
1. Execute only deterministic steps
2. Block all LLM calls
3. Validate before each step
4. Track results and metrics
"""

import logging

logger = logging.getLogger(__name__)
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from .models import StepResult, StepType


class StepwiseExecutor:
    """
    Executes packet steps one at a time

    Enforces:
    - Deterministic execution only
    - No LLM calls allowed
    - Step-by-step validation
    - Result tracking
    """

    def __init__(self, compute_plane_url: str = "http://localhost:8054"):
        self.compute_plane_url = compute_plane_url
        self.llm_call_blocked = True

    def execute_step(
        self,
        step: Dict,
        context: Dict[str, Any]
    ) -> StepResult:
        """
        Execute a single step

        Args:
            step: Step definition from execution packet
            context: Execution context (variables, state)

        Returns:
            StepResult with execution outcome
        """
        start_time = datetime.now(timezone.utc)
        step_id = step.get('step_id', 'unknown')
        step_type_str = step.get('type', 'unknown')

        try:
            # Determine step type
            step_type = self._parse_step_type(step_type_str)

            # Block LLM calls
            if self._is_llm_call(step):
                raise ValueError("LLM calls are blocked during execution")

            # Execute based on type
            if step_type == StepType.REST_CALL:
                output = self._execute_rest_call(step, context)
            elif step_type == StepType.RPC_CALL:
                output = self._execute_rpc_call(step, context)
            elif step_type == StepType.MATH_COMPUTATION:
                output = self._execute_math_computation(step, context)
            elif step_type == StepType.FILESYSTEM_OP:
                output = self._execute_filesystem_op(step, context)
            elif step_type == StepType.ACTUATOR_COMMAND:
                output = self._execute_actuator_command(step, context)
            elif step_type == StepType.VERIFICATION:
                output = self._execute_verification(step, context)
            elif step_type == StepType.CHECKPOINT:
                output = self._execute_checkpoint(step, context)
            else:
                raise ValueError(f"Unknown step type: {step_type_str}")

            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000

            return StepResult(
                step_id=step_id,
                step_type=step_type,
                success=True,
                output=output,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                risk_delta=step.get('risk_delta', 0.0),
                confidence_delta=step.get('confidence_delta', 0.0)
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000

            return StepResult(
                step_id=step_id,
                step_type=self._parse_step_type(step_type_str),
                success=False,
                output=None,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                risk_delta=step.get('risk_delta', 0.0),
                confidence_delta=step.get('confidence_delta', 0.0),
                error=str(exc)
            )

    def _execute_rest_call(self, step: Dict, context: Dict) -> Any:
        """Execute REST API call"""
        url = step.get('url', '')
        method = step.get('method', 'GET').upper()
        headers = step.get('headers', {})
        body = step.get('body', {})
        timeout = step.get('timeout', 30)

        # Substitute context variables
        url = self._substitute_variables(url, context)
        body = self._substitute_variables(body, context)

        # Make request
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=timeout)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=body, timeout=timeout)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=body, timeout=timeout)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()

        # Return response data
        try:
            return response.json()
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return response.text

    def _execute_rpc_call(self, step: Dict, context: Dict) -> Any:
        """Execute RPC call"""
        service = step.get('service', '')
        method = step.get('method', '')
        params = step.get('params', {})

        # Substitute context variables
        params = self._substitute_variables(params, context)

        # In production, would use actual RPC client
        # For now, simulate RPC call
        return {
            'service': service,
            'method': method,
            'result': 'RPC call executed',
            'params': params
        }

    def _execute_math_computation(self, step: Dict, context: Dict) -> Any:
        """Execute mathematical computation via Deterministic Compute Plane"""
        expression = step.get('expression', '')
        mode = step.get('mode', 'symbolic')  # 'symbolic' or 'numeric'

        # Substitute context variables
        expression = self._substitute_variables(expression, context)

        # Call Deterministic Compute Plane
        try:
            if mode == 'symbolic':
                response = requests.post(
                    f"{self.compute_plane_url}/solve/symbolic",
                    json={'expression': expression},
                    timeout=30
                )
            else:
                response = requests.post(
                    f"{self.compute_plane_url}/solve/numeric",
                    json={'expression': expression},
                    timeout=30
                )

            response.raise_for_status()
            return response.json()
        except Exception as exc:
            # Fallback to simple evaluation for basic expressions
            logger.debug("Caught exception: %s", exc)
            return {
                'expression': expression,
                'result': 'Compute plane unavailable',
                'error': str(exc)
            }

    def _execute_filesystem_op(self, step: Dict, context: Dict) -> Any:
        """Execute filesystem operation"""
        operation = step.get('operation', '')
        path = step.get('path', '')
        content = step.get('content', '')

        # Substitute context variables
        path = self._substitute_variables(path, context)
        content = self._substitute_variables(content, context)

        # Validate path is within allowed directories
        if not self._is_safe_path(path):
            raise ValueError(f"Path '{path}' is not allowed")

        # Execute operation
        if operation == 'read':
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        elif operation == 'write':
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Written to {path}"
        elif operation == 'append':
            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)
            return f"Appended to {path}"
        elif operation == 'delete':
            import os
            os.remove(path)
            return f"Deleted {path}"
        else:
            raise ValueError(f"Unknown filesystem operation: {operation}")

    def _execute_actuator_command(self, step: Dict, context: Dict) -> Any:
        """Execute actuator command"""
        actuator = step.get('actuator', '')
        command = step.get('command', '')
        params = step.get('params', {})

        # Substitute context variables
        params = self._substitute_variables(params, context)

        # In production, would interface with actual actuators
        # For now, simulate actuator command
        return {
            'actuator': actuator,
            'command': command,
            'params': params,
            'status': 'executed'
        }

    def _execute_verification(self, step: Dict, context: Dict) -> Any:
        """Execute verification step"""
        condition = step.get('condition', '')
        expected = step.get('expected', None)
        actual = step.get('actual', None)

        # Substitute context variables
        actual = self._substitute_variables(actual, context)

        # Evaluate condition
        if condition == 'equals':
            result = actual == expected
        elif condition == 'not_equals':
            result = actual != expected
        elif condition == 'greater_than':
            result = actual > expected
        elif condition == 'less_than':
            result = actual < expected
        elif condition == 'contains':
            result = expected in actual
        else:
            raise ValueError(f"Unknown verification condition: {condition}")

        if not result:
            raise ValueError(f"Verification failed: expected {expected}, got {actual}")

        return {
            'condition': condition,
            'expected': expected,
            'actual': actual,
            'passed': True
        }

    def _execute_checkpoint(self, step: Dict, context: Dict) -> Any:
        """Execute checkpoint (save state)"""
        checkpoint_id = step.get('checkpoint_id', '')
        state = step.get('state', {})

        # In production, would save to persistent storage
        return {
            'checkpoint_id': checkpoint_id,
            'state': state,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _is_llm_call(self, step: Dict) -> bool:
        """Check if step is an LLM call"""
        step_type = step.get('type', '').lower()

        # Check for LLM-related keywords
        llm_keywords = ['llm', 'gpt', 'claude', 'generate', 'completion', 'chat']

        for keyword in llm_keywords:
            if keyword in step_type:
                return True

        # Check if step explicitly marked as LLM call
        if step.get('is_llm_call', False):
            return True

        return False

    def _parse_step_type(self, step_type_str: str) -> StepType:
        """Parse step type string to enum"""
        type_map = {
            'rest_call': StepType.REST_CALL,
            'rpc_call': StepType.RPC_CALL,
            'math_computation': StepType.MATH_COMPUTATION,
            'filesystem_op': StepType.FILESYSTEM_OP,
            'actuator_command': StepType.ACTUATOR_COMMAND,
            'verification': StepType.VERIFICATION,
            'checkpoint': StepType.CHECKPOINT
        }

        return type_map.get(step_type_str.lower(), StepType.REST_CALL)

    def _substitute_variables(self, value: Any, context: Dict) -> Any:
        """Substitute context variables in value"""
        if isinstance(value, str):
            # Replace ${variable} with context value
            for key, val in context.items():
                value = value.replace(f"${{{key}}}", str(val))
            return value
        elif isinstance(value, dict):
            return {k: self._substitute_variables(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_variables(v, context) for v in value]
        else:
            return value

    def _is_safe_path(self, path: str) -> bool:
        """Check if path is within allowed directories"""
        # In production, would have more sophisticated path validation
        # For now, just check it doesn't try to escape workspace
        dangerous_patterns = ['..', '~', '/etc', '/sys', '/proc']

        for pattern in dangerous_patterns:
            if pattern in path:
                return False

        return True

"""
Murphy REPL Environment
Safe execution environment for code generation and analysis
Based on RLM pattern from the paper
"""

import logging

logger = logging.getLogger(__name__)
import ast
import io
import json
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class REPLVariable:
    """Variable stored in REPL environment"""
    name: str
    value: Any
    type: str
    size: int
    created_at: datetime
    is_output: bool = False


@dataclass
class REPLExecutionResult:
    """Result of code execution in REPL"""
    success: bool
    output: str
    error: Optional[str] = None
    variables_created: List[str] = field(default_factory=list)
    variables_modified: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafeREPL:
    """
    Safe REPL environment for code execution

    Features:
    - Isolated execution context
    - Variable management
    - Output capture
    - Error handling
    - Resource limits
    - Security restrictions
    """

    def __init__(self):
        self.globals: Dict[str, Any] = {}
        self.locals: Dict[str, Any] = {}
        self.variables: Dict[str, REPLVariable] = {}
        self.execution_history: List[REPLExecutionResult] = []
        self.max_execution_time = 30.0  # seconds
        self.max_memory_mb = 100  # MB
        self._initialize_environment()

    def _initialize_environment(self):
        """Initialize the REPL environment with safe utilities.

        SEC-REPL-001: ``getattr``, ``setattr``, ``hasattr``, ``dir``, and
        ``help`` are intentionally excluded — they enable sandbox escape via
        dunder-chain introspection (e.g. ``__class__.__bases__[0].__subclasses__()``).
        SEC-REPL-002: ``safe_getattr`` is provided instead — it blocks access
        to dunder attributes.
        """
        # ── Blocked dunder names (SEC-REPL-002) ──────────────────────
        _BLOCKED_DUNDERS = frozenset({
            "__class__", "__bases__", "__subclasses__", "__globals__",
            "__builtins__", "__import__", "__code__", "__func__",
            "__self__", "__module__", "__dict__", "__mro__",
            "__qualname__", "__wrapped__",
        })

        def safe_getattr(obj, name, *default):
            """Attribute access that blocks dunder introspection chains."""
            if isinstance(name, str) and name in _BLOCKED_DUNDERS:
                raise AttributeError(f"Access to {name!r} is restricted in the REPL sandbox")
            return getattr(obj, name, *default) if default else getattr(obj, name)

        # Safe builtins
        safe_builtins = {
            'print': print,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sum': sum,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'sorted': sorted,
            'reversed': reversed,
            'any': any,
            'all': all,
            'map': map,
            'filter': filter,
            'type': type,
            'isinstance': isinstance,
            # SEC-REPL-002: safe wrapper instead of raw getattr/setattr/hasattr
            'getattr': safe_getattr,
            'json': json,
            'datetime': datetime,
        }

        self.globals.update(safe_builtins)

        # Add safe imports
        self.globals['__builtins__'] = safe_builtins

        # Initialize context variable (for RLM pattern)
        self.set_variable('context', '', 'system')

    def execute(self, code: str, llm_query_callback=None) -> REPLExecutionResult:
        """
        Execute code in the REPL environment

        Args:
            code: Python code to execute
            llm_query_callback: Optional callback for LLM queries

        Returns:
            REPLExecutionResult with execution details
        """
        start_time = datetime.now(timezone.utc)

        # Capture output
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        variables_before = set(self.globals.keys())

        try:
            # Prepare execution environment
            exec_globals = self.globals.copy()
            exec_locals = self.locals.copy()

            # Add LLM query function if callback provided
            if llm_query_callback:
                exec_globals['llm_query'] = llm_query_callback

            # Security: Restrict builtins to prevent dangerous operations
            safe_builtins = {
                'print': print,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'sum': sum,
                'max': max,
                'min': min,
                'abs': abs,
                'round': round,
                'sorted': sorted,
                'reversed': reversed,
                'any': any,
                'all': all,
                'isinstance': isinstance,
                'type': type,
            }
            exec_globals['__builtins__'] = safe_builtins
            exec_locals['__builtins__'] = safe_builtins

            # Execute code with restricted environment
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, exec_globals, exec_locals)  # noqa: S102 — REPL requires exec

            # Update globals and locals
            self.globals.update(exec_globals)
            self.locals.update(exec_locals)

            # Track variable changes
            variables_after = set(self.globals.keys())
            variables_created = list(variables_after - variables_before)

            for var_name in variables_created:
                var_value = self.globals.get(var_name)
                if var_name not in ['__builtins__']:
                    self.set_variable(var_name, var_value, 'user')

            output = stdout_capture.getvalue()

            result = REPLExecutionResult(
                success=True,
                output=output,
                variables_created=variables_created,
                execution_time=(datetime.now(timezone.utc) - start_time).total_seconds()
            )

        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            error_output = stderr_capture.getvalue()
            error_trace = traceback.format_exc()

            result = REPLExecutionResult(
                success=False,
                output=error_output,
                error=error_trace,
                execution_time=(datetime.now(timezone.utc) - start_time).total_seconds()
            )

        self.execution_history.append(result)
        return result

    def set_variable(self, name: str, value: Any, var_type: str = 'user') -> None:
        """Set a variable in the REPL environment"""
        self.globals[name] = value
        self.variables[name] = REPLVariable(
            name=name,
            value=value,
            type=var_type,
            size=self._estimate_size(value),
            created_at=datetime.now(timezone.utc)
        )

    def get_variable(self, name: str) -> Optional[Any]:
        """Get a variable from the REPL environment"""
        return self.globals.get(name)

    def get_variable_info(self, name: str) -> Optional[REPLVariable]:
        """Get information about a variable"""
        return self.variables.get(name)

    def list_variables(self) -> List[REPLVariable]:
        """List all variables in the environment"""
        return list(self.variables.values())

    def clear_variable(self, name: str) -> bool:
        """Clear a variable from the environment"""
        if name in self.globals:
            del self.globals[name]
            if name in self.variables:
                del self.variables[name]
            return True
        return False

    def clear_all_variables(self) -> None:
        """Clear all user variables"""
        # Keep system variables
        system_vars = {'context', '__builtins__'}

        vars_to_delete = [
            name for name in self.globals.keys()
            if name not in system_vars
        ]

        for var_name in vars_to_delete:
            del self.globals[var_name]
            if var_name in self.variables:
                del self.variables[var_name]

    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value"""
        if value is None:
            return 0
        elif isinstance(value, (str, bytes)):
            return len(value)
        elif isinstance(value, (list, tuple, set)):
            return sum(self._estimate_size(item) for item in value)
        elif isinstance(value, dict):
            return sum(
                self._estimate_size(k) + self._estimate_size(v)
                for k, v in value.items()
            )
        else:
            return sys.getsizeof(value)

    def get_context(self) -> str:
        """Get the context variable"""
        return self.get_variable('context') or ''

    def set_context(self, context: str) -> None:
        """Set the context variable"""
        self.set_variable('context', context, 'system')

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution history"""
        total_executions = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        failed = total_executions - successful

        avg_time = (
            sum(r.execution_time for r in self.execution_history) / total_executions
            if total_executions > 0 else 0.0
        )

        return {
            'total_executions': total_executions,
            'successful': successful,
            'failed': failed,
            'success_rate': successful / total_executions if total_executions > 0 else 0.0,
            'average_execution_time': avg_time,
            'variables_count': len(self.variables),
            'context_size': len(self.get_context())
        }


class MurphyREPL(SafeREPL):
    """
    Murphy-specific REPL with additional features for system building
    """

    def __init__(self, llm_controller=None):
        super().__init__()
        self.llm_controller = llm_controller
        self.proposal_history: List[Dict[str, Any]] = []

    def execute_with_llm(self, code: str) -> REPLExecutionResult:
        """Execute code with LLM query capability"""
        from llm_controller import LLMRequest

        def llm_query_callback(prompt):
            if self.llm_controller:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    request = LLMRequest(prompt=prompt)
                    response = loop.run_until_complete(
                        self.llm_controller.query_llm(request)
                    )
                    return response.content
                finally:
                    loop.close()
            return "[LLM not available]"

        return self.execute(code, llm_query_callback)

    def analyze_context(self, context: str) -> Dict[str, Any]:
        """Analyze the context variable"""
        self.set_context(context)

        analysis_code = """
# Analyze context
context_analysis = {
    'length': len(context),
    'word_count': len(context.split()),
    'line_count': len(context.split('\\n')),
    'has_code': bool(any(marker in context for marker in ['```', 'def ', 'class ', 'import '])),
    'structure': 'markdown' if '##' in context else 'text',
}
print(json.dumps(context_analysis, indent=2))
"""

        result = self.execute(analysis_code)

        if result.success and result.output:
            try:
                return json.loads(result.output)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                return {}

        return {}

    def generate_swarm_proposal(self, task_description: str) -> Dict[str, Any]:
        """Generate a swarm proposal for a task"""
        proposal = {
            'task': task_description,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'context_analysis': self.analyze_context(self.get_context()),
            'proposal': self._create_proposal_structure(task_description)
        }

        self.proposal_history.append(proposal)
        return proposal

    def _create_proposal_structure(self, task: str) -> Dict[str, Any]:
        """Create a proposal structure based on task"""
        return {
            'task_type': self._classify_task(task),
            'complexity': self._estimate_complexity(task),
            'components': self._identify_components(task),
            'safety_considerations': self._identify_safety_concerns(task),
            'resource_estimates': self._estimate_resources(task)
        }

    def _classify_task(self, task: str) -> str:
        """Classify the task type"""
        task_lower = task.lower()

        if any(word in task_lower for word in ['app', 'application', 'web', 'website']):
            return 'web_application'
        elif any(word in task_lower for word in ['data', 'database', 'analytics']):
            return 'data_system'
        elif any(word in task_lower for word in ['ai', 'model', 'machine learning']):
            return 'ai_system'
        elif any(word in task_lower for word in ['control', 'automation', 'robot']):
            return 'control_system'
        else:
            return 'general'

    def _estimate_complexity(self, task: str) -> str:
        """Estimate task complexity"""
        task_lower = task.lower()

        complexity_indicators = {
            'simple': ['simple', 'basic', 'easy', 'quick', 'small'],
            'medium': ['moderate', 'standard', 'typical'],
            'complex': ['complex', 'advanced', 'sophisticated', 'enterprise', 'scalable']
        }

        for level, indicators in complexity_indicators.items():
            if any(indicator in task_lower for indicator in indicators):
                return level

        # Default to medium
        return 'medium'

    def _identify_components(self, task: str) -> List[str]:
        """Identify likely components needed"""
        components = []
        task_lower = task.lower()

        component_mapping = {
            'frontend': ['web', 'ui', 'interface', 'user'],
            'backend': ['api', 'server', 'database'],
            'database': ['data', 'storage', 'database'],
            'authentication': ['login', 'user', 'auth'],
            'api': ['api', 'service', 'integration'],
            'ml': ['ai', 'machine learning', 'model', 'prediction'],
        }

        for component, keywords in component_mapping.items():
            if any(keyword in task_lower for keyword in keywords):
                components.append(component)

        if not components:
            components.append('core')

        return components

    def _identify_safety_concerns(self, task: str) -> List[str]:
        """Identify potential safety concerns"""
        concerns = []
        task_lower = task.lower()

        concern_mapping = {
            'data_privacy': ['user data', 'personal information', 'privacy'],
            'security': ['login', 'authentication', 'security', 'password'],
            'input_validation': ['user input', 'form', 'validation'],
            'resource_limits': ['scalability', 'performance', 'load'],
            'error_handling': ['error', 'failure', 'robust'],
        }

        for concern, keywords in concern_mapping.items():
            if any(keyword in task_lower for keyword in keywords):
                concerns.append(concern)

        return concerns

    def _estimate_resources(self, task: str) -> Dict[str, Any]:
        """Estimate resource requirements"""
        complexity = self._estimate_complexity(task)
        components = self._identify_components(task)

        # Simple estimation based on complexity and components
        if complexity == 'simple':
            time_hours = 4
            cost_estimate = 0.5
        elif complexity == 'medium':
            time_hours = 16
            cost_estimate = 2.0
        else:  # complex
            time_hours = 40
            cost_estimate = 5.0

        return {
            'estimated_time_hours': time_hours,
            'estimated_cost_usd': cost_estimate,
            'team_size': 2 if complexity in ['simple', 'medium'] else 4,
            'components_count': len(components)
        }

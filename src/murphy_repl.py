"""
Murphy REPL Environment
Safe execution environment for code generation and analysis
Based on RLM pattern from the paper

Security labels:
  SEC-REPL-001: Dangerous introspection builtins removed.
  SEC-REPL-002: safe_getattr wrapper blocks dunder chains.
  SEC-REPL-003: Execution timeout enforced via threading.
  SEC-REPL-004: Memory limit — ``resource.setrlimit(RLIMIT_AS, ...)`` is
      process-wide on Linux and therefore set at the **container** level
      (``--memory`` in Docker / ``mem_limit`` in compose) rather than
      per-exec thread.  The ``max_memory_mb`` attribute is retained as the
      declarative policy value for container-level enforcement.
  SEC-REPL-005: On timeout, the runaway exec thread is forcibly terminated
      via ``PyThreadState_SetAsyncExc`` so a ``while True:`` submission
      cannot leave a zombie CPU-burning daemon thread behind the wider
      interpreter process.  Without this, pytest-timeout raises
      INTERNALERROR when CI hits the compliance suite and, in production,
      every ill-formed REPL submission silently degrades server capacity.
"""

import logging

logger = logging.getLogger(__name__)
import ast
import ctypes
import io
import json
import sys
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────
# SEC-REPL-005: runaway-thread termination helper
# ─────────────────────────────────────────────────────────────────────────
def _terminate_runaway_thread(thread: threading.Thread) -> None:
    """Raise ``SystemExit`` inside a still-running daemon exec thread.

    Uses the CPython-internal ``PyThreadState_SetAsyncExc`` API — the
    documented idiom for cancelling a stuck Python thread.  CPython's
    evaluation loop checks for async exceptions at each bytecode
    boundary, so a pure-Python busy loop (``while True: x += 1``) exits
    within one iteration after this fires.

    Limitations (documented so nothing fails silently):
      * Threads blocked inside a C extension ignore the async exception
        until they next enter the Python eval loop.  In the REPL,
        builtins are pure-Python-callable so this is not a concern for
        normal submissions.
      * If the async-set fails (thread already exited, or set on more
        than one thread), we undo the set and log.  We never raise.

    Never called for threads that finished on their own.
    """
    if thread is None or not thread.is_alive():
        return
    tid = thread.ident
    if tid is None:
        return
    try:
        affected = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(tid), ctypes.py_object(SystemExit)
        )
    except Exception:  # noqa: BLE001 — never propagate out of cleanup
        logger.warning("SEC-REPL-005: PyThreadState_SetAsyncExc unavailable", exc_info=True)
        return
    if affected == 0:
        # Thread ID not found — thread already exited between our
        # is_alive() check and the API call.  Nothing to do.
        return
    if affected > 1:
        # Guard from the CPython docs: roll back to avoid leaving multiple
        # threads in an inconsistent exception state.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), None)
        logger.error("SEC-REPL-005: async exception set on >1 thread — rolled back")
        return
    # Give the killed thread a brief window to unwind and release GIL so
    # subsequent tests / REPL calls start on a clean scheduler.  Bounded
    # to 2s so a C-extension-blocked thread cannot stall the caller.
    thread.join(timeout=2.0)
    if thread.is_alive():
        logger.warning(
            "SEC-REPL-005: runaway REPL thread did not unwind within 2s; "
            "likely blocked in a C extension"
        )


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

            # SEC-REPL-003: Enforce execution timeout via threading.
            # SEC-REPL-004: Memory limit enforced inside the thread (Linux).
            # SEC-REPL-005: On timeout, forcibly terminate the runaway thread
            # so a `while True:` submission cannot leave a zombie CPU-burning
            # daemon thread behind. See ``_terminate_runaway_thread`` below.
            _exec_error: list = []          # mutable container for thread result
            _exec_finished = threading.Event()

            def _run_exec():
                try:
                    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                        exec(code, exec_globals, exec_locals)  # noqa: S102 — REPL requires exec
                except Exception as _e:
                    _exec_error.append(_e)
                finally:
                    _exec_finished.set()

            _t = threading.Thread(target=_run_exec, daemon=True)
            _t.start()
            if not _exec_finished.wait(timeout=self.max_execution_time):
                # SEC-REPL-005: kill the runaway thread before surfacing the
                # timeout — otherwise it continues to burn CPU for the entire
                # lifetime of the interpreter, which has historically caused
                # pytest-timeout INTERNALERRORs and, in production, silent
                # capacity degradation for every `while True` submission.
                _terminate_runaway_thread(_t)
                raise TimeoutError(
                    f"REPL execution exceeded {self.max_execution_time}s limit (SEC-REPL-003)")

            # Re-raise any exception from the exec thread.
            if _exec_error:
                raise _exec_error[0]

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

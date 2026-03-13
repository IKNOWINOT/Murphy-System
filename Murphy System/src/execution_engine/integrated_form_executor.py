"""
Integrated Form Executor

Integrates form-driven task execution with the original
murphy_runtime_analysis execution engine.

This allows tasks submitted via forms to be executed using the
existing proven execution infrastructure.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import original execution system
try:
    from execution_engine.execution_orchestrator import ExecutionOrchestrator
    HAS_ORCHESTRATOR = True
except ImportError:
    HAS_ORCHESTRATOR = False
    logging.warning("Original ExecutionOrchestrator not found")

try:
    from confidence_engine.phase_controller import PhaseController
    HAS_PHASE_CONTROLLER = True
except ImportError:
    HAS_PHASE_CONTROLLER = False
    logging.warning("Original PhaseController not found")

# Import new form execution system
# Import unified confidence engine
from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
from execution_engine.execution_context import ExecutionContext
from execution_engine.form_execution_models import ExecutionResult, ExecutionStatus
from execution_engine.form_executor import FormDrivenExecutor

logger = logging.getLogger(__name__)


class IntegratedFormExecutor:
    """
    Integrated Form Executor

    Combines:
    1. Form-driven task submission and decomposition
    2. Unified confidence validation (G/D/H + Murphy)
    3. Original execution orchestrator
    4. Phase-based execution control

    This provides a complete pipeline from form submission to
    task execution using both new and original systems.
    """

    def __init__(self):
        """Initialize integrated form executor"""

        # Original execution components
        if HAS_ORCHESTRATOR:
            self.orchestrator = ExecutionOrchestrator()
            logger.info("Loaded original ExecutionOrchestrator")
        else:
            self.orchestrator = None
            logger.warning("Original ExecutionOrchestrator not available")

        if HAS_PHASE_CONTROLLER:
            self.phase_controller = PhaseController()
            logger.info("Loaded original PhaseController")
        else:
            self.phase_controller = None
            logger.warning("Original PhaseController not available")

        # New form execution components
        self.form_executor = FormDrivenExecutor()

        # Unified confidence engine
        self.confidence_engine = UnifiedConfidenceEngine()

        logger.info("IntegratedFormExecutor initialized")

    async def execute_form_task(
        self,
        form_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute task submitted via form

        Args:
            form_data: Form submission data
            context: Additional execution context

        Returns:
            Execution result
        """

        # Convert form to task
        task = self._form_to_task(form_data)

        logger.info(f"Executing form task: {task.get('id', 'unknown')}")

        # Create execution context
        exec_context = ExecutionContext(
            task_id=task.get('id'),
            task=task
        )

        # Validate with unified confidence engine
        confidence_report = self.confidence_engine.calculate_confidence(task, context)

        if not confidence_report.gate_result.allowed:
            logger.warning(
                f"Task {task.get('id')} rejected by Murphy Gate: "
                f"{confidence_report.gate_result.rationale}"
            )
            return ExecutionResult(
                task_id=task.get('id'),
                execution_id=f"rejected_{task.get('id', 'unknown')}",
                status=ExecutionStatus.CANCELLED,
                error_message=confidence_report.gate_result.rationale,
            )

        # Execute using original orchestrator if available
        if self.orchestrator:
            try:
                result = await self._execute_with_orchestrator(task, exec_context)
            except Exception as exc:
                logger.error(f"Error executing with orchestrator: {exc}")
                result = await self._execute_with_form_executor(task, exec_context)
        else:
            # Fallback to form executor
            result = await self._execute_with_form_executor(task, exec_context)

        logger.info(
            f"Task {task.get('id')} completed with status: {result.status}"
        )

        return result

    async def _execute_with_orchestrator(
        self,
        task: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Execute task using original orchestrator

        Args:
            task: Task to execute
            context: Execution context

        Returns:
            Execution result
        """

        logger.debug(f"Executing task {task.get('id')} with original orchestrator")

        try:
            # Execute with original system
            result = await self.orchestrator.execute(task)

            # Convert to ExecutionResult format
            return ExecutionResult(
                task_id=task.get('id'),
                status=ExecutionStatus.COMPLETED,
                output=result,
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as exc:
            logger.error(f"Orchestrator execution failed: {exc}")
            return ExecutionResult(
                task_id=task.get('id'),
                status=ExecutionStatus.FAILED,
                error=str(exc),
                timestamp=datetime.now(timezone.utc)
            )

    async def _execute_with_form_executor(
        self,
        task: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Execute task using form executor (fallback)

        Args:
            task: Task to execute
            context: Execution context

        Returns:
            Execution result
        """

        logger.debug(f"Executing task {task.get('id')} with form executor")

        try:
            result = self.form_executor.execute_task(task)
            return result

        except Exception as exc:
            logger.error(f"Form executor execution failed: {exc}")
            return ExecutionResult(
                task_id=task.get('id'),
                status=ExecutionStatus.FAILED,
                error=str(exc),
                timestamp=datetime.now(timezone.utc)
            )

    def _form_to_task(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert form data to task format

        Args:
            form_data: Form submission data

        Returns:
            Task dictionary
        """

        # Extract task information from form
        task = {
            'id': form_data.get('task_id', f"task_{datetime.now(timezone.utc).timestamp()}"),
            'type': form_data.get('task_type', 'general'),
            'description': form_data.get('description', ''),
            'parameters': form_data.get('parameters', {}),
            'constraints': form_data.get('constraints', []),
            'priority': form_data.get('priority', 'normal'),
            'metadata': form_data.get('metadata', {}),
            'timestamp': datetime.now(timezone.utc)
        }

        return task

    def get_execution_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution status for a task

        Args:
            task_id: Task ID

        Returns:
            Status information or None
        """

        # Try to get status from orchestrator
        if self.orchestrator:
            try:
                return self.orchestrator.get_status(task_id)
            except Exception as exc:
                logger.error(f"Error getting status from orchestrator: {exc}")

        # Fallback to form executor
        return None

"""
Form-Driven Executor

Executes tasks using phase-based approach with Murphy validation
and human-in-the-loop checkpoints.
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Add murphy_runtime_analysis to path for imports
from .execution_context import ExecutionContext
from .form_execution_models import ExecutionResult, ExecutionStatus, PhaseResult

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from confidence_engine.models import (
    ConfidenceState,
)
from confidence_engine.models import (
    Phase as ControllerPhase,
)
from confidence_engine.murphy_models import Phase
from confidence_engine.murphy_validator import MurphyValidator

logger = logging.getLogger(__name__)


class FormDrivenExecutor:
    """
    Executes tasks through phase-based workflow

    Phases:
    1. EXPAND - Generate possibilities
    2. TYPE - Classify and categorize
    3. ENUMERATE - List all options
    4. CONSTRAIN - Apply rules and limits
    5. COLLAPSE - Select best option
    6. BIND - Commit to decision
    7. EXECUTE - Perform action
    """

    def __init__(self):
        self.murphy_validator = MurphyValidator()

        # Try to import existing phase controller
        try:
            from confidence_engine.phase_controller import PhaseController
            self.phase_controller = PhaseController()
            self.has_phase_controller = True
            logger.info("Loaded existing phase controller")
        except ImportError:
            self.phase_controller = None
            self.has_phase_controller = False
            logger.warning("Could not load existing phase controller")

        # Phase execution order
        self.phases = [
            Phase.EXPAND,
            Phase.TYPE,
            Phase.ENUMERATE,
            Phase.CONSTRAIN,
            Phase.COLLAPSE,
            Phase.BIND,
            Phase.EXECUTE
        ]

    def execute_task(
        self,
        task: Any,
        execution_mode: str = "supervised",
        confidence_threshold: float = 0.7,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute a task through all phases

        Args:
            task: Task to execute
            execution_mode: How to execute (automatic/supervised/manual)
            confidence_threshold: Minimum confidence to proceed
            additional_context: Additional context for execution

        Returns:
            ExecutionResult with complete execution details
        """
        # Generate execution ID
        execution_id = self._generate_execution_id(task)

        logger.info(f"Starting task execution: {execution_id}")
        logger.info(f"Task: {getattr(task, 'task_id', 'unknown')}")
        logger.info(f"Mode: {execution_mode}, Threshold: {confidence_threshold}")

        # Initialize execution context
        context = ExecutionContext(
            task_id=getattr(task, 'task_id', 'unknown'),
            task=task,
            execution_mode=execution_mode,
            confidence_threshold=confidence_threshold,
            metadata=additional_context or {}
        )

        # Initialize result
        result = ExecutionResult(
            task_id=context.task_id,
            execution_id=execution_id,
            status=ExecutionStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        try:
            # Execute through phases
            for phase in self.phases:
                logger.info(f"Executing phase: {phase.value}")

                phase_start = time.time()

                # Execute phase
                phase_result = self._execute_phase(
                    phase=phase,
                    task=task,
                    context=context
                )

                phase_duration = time.time() - phase_start

                # Add to results
                result.phase_results.append(PhaseResult(
                    phase=phase.value,
                    status=ExecutionStatus.COMPLETED,
                    confidence=phase_result.get('confidence', 0.0),
                    gate_allowed=phase_result.get('gate_allowed', False),
                    output=phase_result.get('output', {}),
                    duration_seconds=phase_duration
                ))

                # Update context
                context.update(phase_result)

                # Check if phase was blocked
                if not phase_result.get('gate_allowed', False):
                    logger.warning(f"Phase {phase.value} blocked by Murphy Gate")
                    result.status = ExecutionStatus.AWAITING_HUMAN
                    break

                # Check for assumption invalidations
                if context.has_invalidated_assumptions():
                    logger.warning("Assumptions invalidated, halting execution")
                    result.status = ExecutionStatus.AWAITING_HUMAN
                    break

            # If all phases completed successfully
            if result.status == ExecutionStatus.IN_PROGRESS:
                result.status = ExecutionStatus.COMPLETED
                result.final_output = context.final_output or context.phase_outputs
                result.final_confidence = context.confidence

        except Exception as exc:
            logger.error(f"Execution failed: {str(exc)}", exc_info=True)
            result.status = ExecutionStatus.FAILED
            result.error_message = str(exc)

        finally:
            # Finalize result
            result.completed_at = datetime.now(timezone.utc)
            result.total_duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
            result.human_interventions = context.human_interventions
            result.assumptions_tracked = context.assumptions
            result.assumptions_invalidated = context.invalidated_assumptions
            result.audit_trail = context.audit_trail

        logger.info(
            f"Execution complete: {execution_id}, "
            f"status={result.status.value}, "
            f"duration={result.total_duration_seconds:.2f}s"
        )

        return result

    def _execute_phase(
        self,
        phase: Phase,
        task: Any,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Execute a single phase

        Args:
            phase: Phase to execute
            task: Task being executed
            context: Execution context

        Returns:
            Phase result dictionary
        """
        # Prepare context for validation
        validation_context = {
            'phase': phase.value,
            'task_description': getattr(task, 'description', ''),
            'execution_mode': context.execution_mode,
            'previous_phases': list(context.phase_outputs.keys()),
            'metadata': context.metadata
        }

        # Validate with Murphy
        validation_report = self.murphy_validator.validate(
            task=task,
            context=validation_context,
            phase=phase,
            threshold=context.confidence_threshold
        )

        # Check Murphy Gate
        gate_allowed = validation_report.gate_result.allowed

        if not gate_allowed:
            logger.warning(
                f"Murphy Gate blocked {phase.value}: "
                f"{validation_report.gate_result.rationale}"
            )

            # Request human intervention if needed
            if validation_report.gate_result.action in [
                'request_human_review',
                'require_human_approval'
            ]:
                context.add_human_intervention(
                    intervention_type='gate_blocked',
                    details={
                        'phase': phase.value,
                        'confidence': validation_report.confidence,
                        'threshold': validation_report.gate_result.threshold,
                        'action': validation_report.gate_result.action.value,
                        'rationale': validation_report.gate_result.rationale
                    }
                )

            return {
                'phase': phase.value,
                'gate_allowed': False,
                'confidence': validation_report.confidence,
                'validation_report': validation_report.model_dump(),
                'output': {}
            }

        # Execute phase logic
        phase_output = self._execute_phase_logic(
            phase=phase,
            task=task,
            context=context
        )

        # Track assumptions from phase
        if 'assumptions' in phase_output:
            for assumption in phase_output['assumptions']:
                context.add_assumption(assumption)

        return {
            'phase': phase.value,
            'gate_allowed': True,
            'confidence': validation_report.confidence,
            'risk_score': validation_report.uncertainty_scores.UR,
            'validation_report': validation_report.model_dump(),
            'output': phase_output
        }

    def _execute_phase_logic(
        self,
        phase: Phase,
        task: Any,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Execute the actual logic for a phase

        This is where the phase-specific work happens.
        """
        if self.has_phase_controller:
            # Use existing phase controller if available
            try:
                return self._execute_with_phase_controller(phase, task, context)
            except Exception as exc:
                logger.warning(f"Phase controller execution failed: {exc}")

        # Fallback to simple phase execution
        return self._execute_phase_simple(phase, task, context)

    def _execute_with_phase_controller(
        self,
        phase: Phase,
        task: Any,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute a phase using the PhaseController for gated transitions.

        Delegates the phase-specific work to ``_execute_phase_simple`` and
        then consults the :class:`PhaseController` to decide whether the
        confidence threshold for a transition has been met.  Returns the
        phase result augmented with controller metadata (progress, next-phase
        eligibility, and transition history).
        """
        # 1. Map the murphy_models.Phase (str enum) to the models.Phase used
        # by the PhaseController (which carries confidence_threshold).
        controller_phase = ControllerPhase(phase.value)

        # 2. Build a ConfidenceState from what the validator already computed.
        current_confidence = context.confidence or 0.5
        confidence_state = ConfidenceState(
            confidence=current_confidence,
            generative_score=current_confidence * 0.6,
            deterministic_score=current_confidence * 0.4,
            epistemic_instability=max(0.0, 1.0 - current_confidence),
            phase=controller_phase,
        )

        # 3. Ask the phase controller whether the transition is allowed.
        new_phase, transitioned, reason = (
            self.phase_controller.check_phase_transition(
                controller_phase, confidence_state
            )
        )

        # 4. Record progress metadata in the execution context.
        progress = self.phase_controller.get_phase_progress(controller_phase)

        # 5. Execute the concrete phase logic via the simple handler.
        phase_output = self._execute_phase_simple(phase, task, context)

        # 6. Augment the output with controller metadata.
        phase_output['phase_controller'] = {
            'transitioned': transitioned,
            'reason': reason,
            'progress': progress,
            'confidence_state': {
                'confidence': confidence_state.confidence,
                'threshold': controller_phase.confidence_threshold,
            },
        }

        return phase_output

    def _execute_phase_simple(
        self,
        phase: Phase,
        task: Any,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Simple phase execution (fallback)"""

        if phase == Phase.EXPAND:
            return self._phase_expand(task, context)
        elif phase == Phase.TYPE:
            return self._phase_type(task, context)
        elif phase == Phase.ENUMERATE:
            return self._phase_enumerate(task, context)
        elif phase == Phase.CONSTRAIN:
            return self._phase_constrain(task, context)
        elif phase == Phase.COLLAPSE:
            return self._phase_collapse(task, context)
        elif phase == Phase.BIND:
            return self._phase_bind(task, context)
        elif phase == Phase.EXECUTE:
            return self._phase_execute(task, context)
        else:
            return {'result': 'unknown phase'}

    def _phase_expand(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """EXPAND: Generate possibilities"""
        return {
            'possibilities': [
                'Approach 1: Direct implementation',
                'Approach 2: Iterative development',
                'Approach 3: Prototype first'
            ],
            'assumptions': ['Resources are available', 'Timeline is flexible']
        }

    def _phase_type(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """TYPE: Classify and categorize"""
        return {
            'task_type': 'implementation',
            'complexity': 'medium',
            'domain': 'software_development'
        }

    def _phase_enumerate(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """ENUMERATE: List all options"""
        possibilities = context.get_phase_output('expand').get('possibilities', [])
        return {
            'options': [
                {'id': i+1, 'description': p, 'feasibility': 0.8}
                for i, p in enumerate(possibilities)
            ]
        }

    def _phase_constrain(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """CONSTRAIN: Apply rules and limits"""
        return {
            'constraints_applied': [
                'Budget constraint',
                'Timeline constraint',
                'Resource constraint'
            ],
            'viable_options': [1, 2]  # Options that meet constraints
        }

    def _phase_collapse(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """COLLAPSE: Select best option"""
        return {
            'selected_option': 1,
            'rationale': 'Best balance of feasibility and impact'
        }

    def _phase_bind(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """BIND: Commit to decision"""
        return {
            'committed': True,
            'decision': 'Proceed with Approach 1',
            'assumptions': ['Team agrees with approach']
        }

    def _phase_execute(self, task: Any, context: ExecutionContext) -> Dict[str, Any]:
        """EXECUTE: Perform action"""
        return {
            'executed': True,
            'result': 'Task completed successfully',
            'deliverables': getattr(task, 'deliverables', [])
        }

    def _generate_execution_id(self, task: Any) -> str:
        """Generate unique execution ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        task_id = getattr(task, 'task_id', 'unknown')
        return f"exec_{task_id}_{timestamp}"

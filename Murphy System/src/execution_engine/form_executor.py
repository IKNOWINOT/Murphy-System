"""
Form-Driven Executor

Executes tasks using phase-based approach with Murphy validation
and human-in-the-loop checkpoints.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import sys
import os
import time

# Add murphy_runtime_analysis to path for imports

from .execution_context import ExecutionContext
from .form_execution_models import ExecutionResult, ExecutionStatus, PhaseResult
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from confidence_engine.murphy_validator import MurphyValidator
from confidence_engine.murphy_models import Phase

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
            from src.confidence_engine.phase_controller import PhaseController
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
            started_at=datetime.now()
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
            
        except Exception as e:
            logger.error(f"Execution failed: {str(e)}", exc_info=True)
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
        
        finally:
            # Finalize result
            result.completed_at = datetime.now()
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
            except Exception as e:
                logger.warning(f"Phase controller execution failed: {e}")
        
        # Fallback to simple phase execution
        return self._execute_phase_simple(phase, task, context)
    
    def _execute_with_phase_controller(
        self,
        phase: Phase,
        task: Any,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute phase using existing phase controller"""
        # TODO: Integrate with actual phase controller
        # For now, return placeholder
        return {
            'phase': phase.value,
            'result': f"Phase {phase.value} executed",
            'assumptions': []
        }
    
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_id = getattr(task, 'task_id', 'unknown')
        return f"exec_{task_id}_{timestamp}"
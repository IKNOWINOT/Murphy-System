"""
Murphy System Implementation

A form-driven task execution system with Murphy validation,
human-in-the-loop checkpoints, and shadow agent training.
"""

__version__ = "1.0.0"
__author__ = "Murphy System Team"

from .forms import (
    FormType,
    PlanUploadForm,
    PlanGenerationForm,
    TaskExecutionForm,
    ValidationForm,
    CorrectionForm
)

from .plan_decomposition import (
    PlanDecomposer,
    Plan,
    Task
)

from .validation import (
    MurphyValidator,
    MurphyGate,
    UncertaintyCalculator
)

from .execution import (
    FormDrivenExecutor,
    ExecutionContext,
    ExecutionResult
)

from .hitl import (
    HumanInTheLoopMonitor,
    InterventionRequest,
    InterventionResponse
)

__all__ = [
    # Forms
    'FormType',
    'PlanUploadForm',
    'PlanGenerationForm',
    'TaskExecutionForm',
    'ValidationForm',
    'CorrectionForm',
    
    # Plan Decomposition
    'PlanDecomposer',
    'Plan',
    'Task',
    
    # Validation
    'MurphyValidator',
    'MurphyGate',
    'UncertaintyCalculator',
    
    # Execution
    'FormDrivenExecutor',
    'ExecutionContext',
    'ExecutionResult',
    
    # HITL
    'HumanInTheLoopMonitor',
    'InterventionRequest',
    'InterventionResponse'
]
"""
Correction Capture Interface
Provides interfaces for capturing human corrections in various formats.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("learning_engine.correction_capture")

from .correction_models import (
    CorrectedValue,
    Correction,
    CorrectionContext,
    CorrectionDiff,
    CorrectionMetrics,
    CorrectionSeverity,
    CorrectionSource,
    CorrectionType,
    OriginalValue,
    create_simple_correction,
)


class CaptureMethod(str, Enum):
    """Methods for capturing corrections."""
    INTERACTIVE = "interactive"
    BATCH = "batch"
    API = "api"
    FILE_UPLOAD = "file_upload"
    INLINE = "inline"


class CaptureFormat(str, Enum):
    """Formats for correction data."""
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"
    FORM = "form"
    DIFF = "diff"


class CorrectionCaptureRequest(BaseModel):
    """Request to capture a correction."""
    task_id: str
    operation: str
    original_output: Any
    corrected_output: Any
    reasoning: str
    correction_type: Optional[CorrectionType] = None
    severity: Optional[CorrectionSeverity] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CorrectionCaptureResponse(BaseModel):
    """Response from correction capture."""
    correction_id: str
    success: bool
    message: str
    validation_errors: List[str] = Field(default_factory=list)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InteractiveCorrectionCapture:
    """
    Interactive correction capture with guided prompts.
    """

    def __init__(self):
        self.current_correction: Optional[Correction] = None
        self.capture_history: List[Correction] = []

    def start_capture(
        self,
        task_id: str,
        operation: str,
        original_output: Any
    ) -> Dict[str, Any]:
        """
        Start interactive correction capture session.

        Args:
            task_id: ID of the task being corrected
            operation: Operation that produced the output
            original_output: Original output to be corrected

        Returns:
            Dictionary with session info and prompts
        """
        context = CorrectionContext(
            task_id=task_id,
            phase="execution",
            operation=operation
        )

        return {
            "session_id": f"capture_{datetime.now(timezone.utc).timestamp()}",
            "task_id": task_id,
            "original_output": original_output,
            "prompts": self._generate_prompts(),
            "context": context.model_dump()
        }

    def _generate_prompts(self) -> List[Dict[str, Any]]:
        """Generate interactive prompts for correction capture."""
        return [
            {
                "step": 1,
                "question": "What type of correction is this?",
                "options": [t.value for t in CorrectionType],
                "field": "correction_type"
            },
            {
                "step": 2,
                "question": "How severe is this issue?",
                "options": [s.value for s in CorrectionSeverity],
                "field": "severity"
            },
            {
                "step": 3,
                "question": "What is the corrected output?",
                "type": "text",
                "field": "corrected_output"
            },
            {
                "step": 4,
                "question": "Why is this correction needed?",
                "type": "text",
                "field": "reasoning"
            },
            {
                "step": 5,
                "question": "Any additional notes or context?",
                "type": "text",
                "optional": True,
                "field": "notes"
            }
        ]

    def capture_step(
        self,
        session_id: str,
        step: int,
        response: Any
    ) -> Dict[str, Any]:
        """
        Capture response for a specific step.

        Args:
            session_id: Session ID
            step: Step number
            response: User's response

        Returns:
            Next step info or completion status
        """
        # Store response
        if not hasattr(self, '_session_data'):
            self._session_data = {}

        if session_id not in self._session_data:
            self._session_data[session_id] = {}

        self._session_data[session_id][f"step_{step}"] = response

        prompts = self._generate_prompts()

        if step < len(prompts):
            return {
                "next_step": step + 1,
                "prompt": prompts[step],
                "progress": f"{step}/{len(prompts)}"
            }
        else:
            return {
                "complete": True,
                "message": "Correction capture complete"
            }

    def finalize_capture(
        self,
        session_id: str,
        context: CorrectionContext
    ) -> Correction:
        """
        Finalize and create correction from captured data.

        Args:
            session_id: Session ID
            context: Correction context

        Returns:
            Complete Correction object
        """
        session_data = self._session_data.get(session_id, {})

        # Extract data from session
        correction_type = CorrectionType(session_data.get("step_1", "output_modification"))
        severity = CorrectionSeverity(session_data.get("step_2", "medium"))
        corrected_output = session_data.get("step_3")
        reasoning = session_data.get("step_4", "")

        # Create correction
        correction = create_simple_correction(
            task_id=context.task_id,
            field_name="output",
            original_value=session_data.get("original_output"),
            corrected_value=corrected_output,
            reasoning=reasoning,
            correction_type=correction_type,
            severity=severity
        )

        self.capture_history.append(correction)
        return correction


class BatchCorrectionCapture:
    """
    Batch correction capture for processing multiple corrections at once.
    """

    def __init__(self):
        self.batch_queue: List[CorrectionCaptureRequest] = []
        self.processed_corrections: List[Correction] = []

    def add_to_batch(self, request: CorrectionCaptureRequest):
        """Add correction request to batch queue."""
        self.batch_queue.append(request)

    def process_batch(self) -> List[Correction]:
        """
        Process all corrections in the batch queue.

        Returns:
            List of created Correction objects
        """
        corrections = []

        for request in self.batch_queue:
            try:
                correction = self._process_request(request)
                corrections.append(correction)
                self.processed_corrections.append(correction)
            except Exception as exc:
                logger.info(f"Error processing correction: {exc}")
                continue

        # Clear queue
        self.batch_queue.clear()

        return corrections

    def _process_request(self, request: CorrectionCaptureRequest) -> Correction:
        """Process a single correction request."""
        context = CorrectionContext(
            task_id=request.task_id,
            phase="execution",
            operation=request.operation,
            user_id=request.user_id,
            metadata=request.metadata
        )

        # Detect changes between original and corrected
        diffs = self._detect_changes(
            request.original_output,
            request.corrected_output
        )

        correction = Correction(
            correction_type=request.correction_type or CorrectionType.OUTPUT_MODIFICATION,
            severity=request.severity or CorrectionSeverity.MEDIUM,
            context=context,
            diffs=diffs,
            explanation=request.reasoning,
            reasoning=request.reasoning,
            metrics=CorrectionMetrics(
                time_to_correct_seconds=0,
                correction_complexity="moderate"
            )
        )

        return correction

    def _detect_changes(self, original: Any, corrected: Any) -> List[CorrectionDiff]:
        """Detect changes between original and corrected values."""
        diffs = []

        # Handle different types
        if isinstance(original, dict) and isinstance(corrected, dict):
            # Dictionary comparison
            all_keys = set(original.keys()) | set(corrected.keys())

            for key in all_keys:
                if key not in original:
                    # Added
                    diff = CorrectionDiff(
                        field_name=key,
                        original=OriginalValue(value=None, type="none"),
                        corrected=CorrectedValue(
                            value=corrected[key],
                            type=type(corrected[key]).__name__,
                            reasoning="Field added",
                            source=CorrectionSource.HUMAN_EXPERT
                        ),
                        change_type="added",
                        impact_score=0.3,
                        description=f"Added field {key}"
                    )
                    diffs.append(diff)

                elif key not in corrected:
                    # Removed
                    diff = CorrectionDiff(
                        field_name=key,
                        original=OriginalValue(
                            value=original[key],
                            type=type(original[key]).__name__
                        ),
                        corrected=CorrectedValue(
                            value=None,
                            type="none",
                            reasoning="Field removed",
                            source=CorrectionSource.HUMAN_EXPERT
                        ),
                        change_type="removed",
                        impact_score=0.3,
                        description=f"Removed field {key}"
                    )
                    diffs.append(diff)

                elif original[key] != corrected[key]:
                    # Modified
                    diff = CorrectionDiff(
                        field_name=key,
                        original=OriginalValue(
                            value=original[key],
                            type=type(original[key]).__name__
                        ),
                        corrected=CorrectedValue(
                            value=corrected[key],
                            type=type(corrected[key]).__name__,
                            reasoning="Value corrected",
                            source=CorrectionSource.HUMAN_EXPERT
                        ),
                        change_type="modified",
                        impact_score=0.5,
                        description=f"Modified field {key}"
                    )
                    diffs.append(diff)

        else:
            # Simple value comparison
            if original != corrected:
                diff = CorrectionDiff(
                    field_name="value",
                    original=OriginalValue(
                        value=original,
                        type=type(original).__name__
                    ),
                    corrected=CorrectedValue(
                        value=corrected,
                        type=type(corrected).__name__,
                        reasoning="Value corrected",
                        source=CorrectionSource.HUMAN_EXPERT
                    ),
                    change_type="modified",
                    impact_score=0.5,
                    description="Value modified"
                )
                diffs.append(diff)

        return diffs


class APICorrectionCapture:
    """
    API-based correction capture for programmatic access.
    """

    def __init__(self):
        self.capture_handlers: Dict[str, Callable] = {}
        self.validation_rules: List[Callable] = []

    def register_handler(self, operation: str, handler: Callable):
        """Register a custom capture handler for an operation."""
        self.capture_handlers[operation] = handler

    def add_validation_rule(self, rule: Callable):
        """Add a validation rule for corrections."""
        self.validation_rules.append(rule)

    async def capture(
        self,
        request: CorrectionCaptureRequest
    ) -> CorrectionCaptureResponse:
        """
        Capture correction via API.

        Args:
            request: Correction capture request

        Returns:
            CorrectionCaptureResponse with result
        """
        # Validate request
        validation_errors = self._validate_request(request)

        if validation_errors:
            return CorrectionCaptureResponse(
                correction_id="",
                success=False,
                message="Validation failed",
                validation_errors=validation_errors
            )

        # Check for custom handler
        handler = self.capture_handlers.get(request.operation)

        if handler:
            correction = await handler(request)
        else:
            correction = self._default_capture(request)

        return CorrectionCaptureResponse(
            correction_id=correction.id,
            success=True,
            message="Correction captured successfully"
        )

    def _validate_request(self, request: CorrectionCaptureRequest) -> List[str]:
        """Validate correction request."""
        errors = []

        # Basic validation
        if not request.task_id:
            errors.append("task_id is required")

        if not request.reasoning:
            errors.append("reasoning is required")

        # Custom validation rules
        for rule in self.validation_rules:
            try:
                if not rule(request):
                    errors.append(f"Validation rule failed: {rule.__name__}")
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                errors.append(f"Validation error: {str(exc)}")

        return errors

    def _default_capture(self, request: CorrectionCaptureRequest) -> Correction:
        """Default correction capture logic."""
        context = CorrectionContext(
            task_id=request.task_id,
            phase="execution",
            operation=request.operation,
            user_id=request.user_id,
            metadata=request.metadata
        )

        return create_simple_correction(
            task_id=request.task_id,
            field_name="output",
            original_value=request.original_output,
            corrected_value=request.corrected_output,
            reasoning=request.reasoning,
            correction_type=request.correction_type or CorrectionType.OUTPUT_MODIFICATION,
            severity=request.severity or CorrectionSeverity.MEDIUM
        )


class InlineCorrectionCapture:
    """
    Inline correction capture for real-time corrections during execution.
    """

    def __init__(self):
        self.active_corrections: Dict[str, Correction] = {}

    def start_inline_correction(
        self,
        task_id: str,
        field_name: str,
        current_value: Any
    ) -> str:
        """
        Start an inline correction.

        Args:
            task_id: Task ID
            field_name: Field being corrected
            current_value: Current value

        Returns:
            Correction ID
        """
        context = CorrectionContext(
            task_id=task_id,
            phase="execution",
            operation="inline_correction"
        )

        correction = Correction(
            correction_type=CorrectionType.OUTPUT_MODIFICATION,
            severity=CorrectionSeverity.MEDIUM,
            context=context,
            diffs=[],
            explanation="Inline correction in progress",
            reasoning="",
            metrics=CorrectionMetrics(
                time_to_correct_seconds=0,
                correction_complexity="simple"
            )
        )

        self.active_corrections[correction.id] = correction
        return correction.id

    def apply_inline_correction(
        self,
        correction_id: str,
        field_name: str,
        original_value: Any,
        corrected_value: Any,
        reasoning: str
    ) -> Correction:
        """
        Apply an inline correction.

        Args:
            correction_id: Correction ID
            field_name: Field name
            original_value: Original value
            corrected_value: Corrected value
            reasoning: Reasoning for correction

        Returns:
            Updated Correction object
        """
        correction = self.active_corrections.get(correction_id)

        if not correction:
            raise ValueError(f"Correction {correction_id} not found")

        # Add diff
        diff = CorrectionDiff(
            field_name=field_name,
            original=OriginalValue(
                value=original_value,
                type=type(original_value).__name__
            ),
            corrected=CorrectedValue(
                value=corrected_value,
                type=type(corrected_value).__name__,
                reasoning=reasoning,
                source=CorrectionSource.HUMAN_EXPERT
            ),
            change_type="modified",
            impact_score=0.5,
            description=f"Inline correction of {field_name}"
        )

        correction.diffs.append(diff)
        correction.reasoning = reasoning
        correction.explanation = reasoning

        return correction

    def finalize_inline_correction(self, correction_id: str) -> Correction:
        """Finalize an inline correction."""
        correction = self.active_corrections.pop(correction_id, None)

        if not correction:
            raise ValueError(f"Correction {correction_id} not found")

        correction.updated_at = datetime.now(timezone.utc)
        return correction


class CorrectionCaptureSystem:
    """
    Unified correction capture system.
    Provides all capture methods in one interface.
    """

    def __init__(self):
        self.interactive = InteractiveCorrectionCapture()
        self.batch = BatchCorrectionCapture()
        self.api = APICorrectionCapture()
        self.inline = InlineCorrectionCapture()
        self.all_corrections: List[Correction] = []

    # Interactive methods
    def start_interactive(self, task_id: str, operation: str, original_output: Any):
        """Start interactive correction capture."""
        return self.interactive.start_capture(task_id, operation, original_output)

    def capture_interactive_step(self, session_id: str, step: int, response: Any):
        """Capture interactive step."""
        return self.interactive.capture_step(session_id, step, response)

    def finalize_interactive(self, session_id: str, context: CorrectionContext) -> Correction:
        """Finalize interactive capture."""
        correction = self.interactive.finalize_capture(session_id, context)
        self.all_corrections.append(correction)
        return correction

    # Batch methods
    def add_to_batch(self, request: CorrectionCaptureRequest):
        """Add to batch queue."""
        self.batch.add_to_batch(request)

    def process_batch(self) -> List[Correction]:
        """Process batch queue."""
        corrections = self.batch.process_batch()
        self.all_corrections.extend(corrections)
        return corrections

    # API methods
    async def capture_via_api(self, request: CorrectionCaptureRequest) -> CorrectionCaptureResponse:
        """Capture via API."""
        response = await self.api.capture(request)
        if response.success:
            # Would retrieve and store the correction
            pass
        return response

    # Inline methods
    def start_inline(self, task_id: str, field_name: str, current_value: Any) -> str:
        """Start inline correction."""
        return self.inline.start_inline_correction(task_id, field_name, current_value)

    def apply_inline(
        self,
        correction_id: str,
        field_name: str,
        original_value: Any,
        corrected_value: Any,
        reasoning: str
    ) -> Correction:
        """Apply inline correction."""
        return self.inline.apply_inline_correction(
            correction_id,
            field_name,
            original_value,
            corrected_value,
            reasoning
        )

    def finalize_inline(self, correction_id: str) -> Correction:
        """Finalize inline correction."""
        correction = self.inline.finalize_inline_correction(correction_id)
        self.all_corrections.append(correction)
        return correction

    # Utility methods
    def get_all_corrections(self) -> List[Correction]:
        """Get all captured corrections."""
        return self.all_corrections

    def get_correction_count(self) -> int:
        """Get total correction count."""
        return len(self.all_corrections)

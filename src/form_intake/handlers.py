"""
Form Handlers for Murphy System

This module provides handlers for processing each form type.
Handlers validate forms, process submissions, and route to appropriate
execution engines.

A module-level submission ledger (``_SUBMISSION_LEDGER``) tracks every
submission so that the ``/submission/{id}`` endpoint can return real-time
status without coupling to a database.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .schemas import (
    CorrectionForm,
    FormType,
    PlanGenerationForm,
    PlanUploadForm,
    TaskExecutionForm,
    ValidationForm,
    validate_form,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Submission Ledger — thread-safe, module-scoped
# ---------------------------------------------------------------------------
_LEDGER_LOCK = threading.Lock()
_SUBMISSION_LEDGER: Dict[str, Dict[str, Any]] = {}


def _record_submission(submission_id: str, form_type: str, initial_status: str,
                       data: Optional[Dict[str, Any]] = None) -> None:
    """Record a new submission in the ledger."""
    now = datetime.now(timezone.utc).isoformat()
    with _LEDGER_LOCK:
        _SUBMISSION_LEDGER[submission_id] = {
            'submission_id': submission_id,
            'form_type': form_type,
            'status': initial_status,
            'progress_pct': 0.0,
            'created_at': now,
            'updated_at': now,
            'phases_completed': [],
            'current_phase': initial_status,
            'data': data or {},
            'error': None,
        }


def update_submission_status(submission_id: str, *,
                             status_val: Optional[str] = None,
                             progress_pct: Optional[float] = None,
                             phase: Optional[str] = None,
                             error: Optional[str] = None) -> None:
    """Update an existing submission entry (thread-safe)."""
    with _LEDGER_LOCK:
        entry = _SUBMISSION_LEDGER.get(submission_id)
        if entry is None:
            return
        if status_val is not None:
            entry['status'] = status_val
        if progress_pct is not None:
            entry['progress_pct'] = progress_pct
        if phase is not None:
            entry['current_phase'] = phase
            if phase not in entry['phases_completed']:
                entry['phases_completed'].append(phase)
        if error is not None:
            entry['error'] = error
        entry['updated_at'] = datetime.now(timezone.utc).isoformat()


def get_submission_status(submission_id: str) -> Optional[Dict[str, Any]]:
    """Return a snapshot of a submission's current status, or ``None``."""
    with _LEDGER_LOCK:
        entry = _SUBMISSION_LEDGER.get(submission_id)
        return dict(entry) if entry is not None else None
# In-process submission status store.  Keyed by submission_id, each value
# is a dict with at least: status, form_type, submitted_at, updated_at.
# The execution engine updates entries as tasks progress.
_submission_store: Dict[str, Dict[str, Any]] = {}


def _record_submission_store(submission_id: str, form_type: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Record a new submission in the in-process store."""
    now = datetime.now(timezone.utc).isoformat()
    _submission_store[submission_id] = {
        'status': 'queued',
        'form_type': form_type,
        'submitted_at': now,
        'updated_at': now,
        'progress': {},
        'results': None,
        **(extra or {}),
    }


class FormSubmissionResult:
    """Result of form submission"""

    def __init__(
        self,
        success: bool,
        submission_id: str,
        form_type: FormType,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.submission_id = submission_id
        self.form_type = form_type
        self.message = message
        self.data = data or {}
        self.errors = errors or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'submission_id': self.submission_id,
            'form_type': self.form_type.value,
            'message': self.message,
            'data': self.data,
            'errors': self.errors,
            'timestamp': self.timestamp.isoformat()
        }


class PlanUploadFormHandler:
    """Handler for Plan Upload Form"""

    def __init__(self):
        self.form_type = FormType.PLAN_UPLOAD

    def handle(self, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Handle plan upload form submission

        Args:
            form_data: Form data to process

        Returns:
            FormSubmissionResult with processing outcome
        """
        try:
            # Validate form
            form = validate_form(self.form_type, form_data)

            # Generate submission ID
            submission_id = self._generate_submission_id(form)

            # Log submission
            logger.info(f"Plan upload form submitted: {submission_id}")
            logger.debug(f"Plan context: {form.plan_context[:100]}...")

            # Process form (will be implemented in plan decomposition engine)
            result_data = {
                'submission_id': submission_id,
                'plan_document': form.plan_document,
                'expansion_level': form.expansion_level.value,
                'status': 'queued_for_processing',
                'next_step': 'plan_decomposition'
            }

            # Record in submission ledger for status tracking
            _record_submission(
                submission_id, self.form_type.value,
                'queued_for_processing', data=result_data,
            )

            _record_submission_store(submission_id, self.form_type.value)
            return FormSubmissionResult(
                success=True,
                submission_id=submission_id,
                form_type=self.form_type,
                message="Plan upload form submitted successfully. Processing will begin shortly.",
                data=result_data
            )

        except Exception as exc:
            logger.error(f"Error handling plan upload form: {str(exc)}")
            return FormSubmissionResult(
                success=False,
                submission_id="",
                form_type=self.form_type,
                message=f"Error processing form: {str(exc)}",
                errors={'validation_error': str(exc)}
            )

    def _generate_submission_id(self, form: PlanUploadForm) -> str:
        """Generate unique submission ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"plan_upload_{timestamp}"


class PlanGenerationFormHandler:
    """Handler for Plan Generation Form"""

    def __init__(self):
        self.form_type = FormType.PLAN_GENERATION

    def handle(self, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Handle plan generation form submission

        Args:
            form_data: Form data to process

        Returns:
            FormSubmissionResult with processing outcome
        """
        try:
            # Validate form
            form = validate_form(self.form_type, form_data)

            # Generate submission ID
            submission_id = self._generate_submission_id(form)

            # Log submission
            logger.info(f"Plan generation form submitted: {submission_id}")
            logger.debug(f"Goal: {form.goal[:100]}...")
            logger.debug(f"Domain: {form.domain.value}")

            # Process form (will be implemented in plan generation engine)
            result_data = {
                'submission_id': submission_id,
                'domain': form.domain.value,
                'timeline': form.timeline,
                'budget': form.budget,
                'team_size': form.team_size,
                'status': 'queued_for_generation',
                'next_step': 'plan_generation'
            }

            # Record in submission ledger for status tracking
            _record_submission(
                submission_id, self.form_type.value,
                'queued_for_generation', data=result_data,
            )

            _record_submission_store(submission_id, self.form_type.value)
            return FormSubmissionResult(
                success=True,
                submission_id=submission_id,
                form_type=self.form_type,
                message="Plan generation form submitted successfully. Plan generation will begin shortly.",
                data=result_data
            )

        except Exception as exc:
            logger.error(f"Error handling plan generation form: {str(exc)}")
            return FormSubmissionResult(
                success=False,
                submission_id="",
                form_type=self.form_type,
                message=f"Error processing form: {str(exc)}",
                errors={'validation_error': str(exc)}
            )

    def _generate_submission_id(self, form: PlanGenerationForm) -> str:
        """Generate unique submission ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        domain = form.domain.value
        return f"plan_gen_{domain}_{timestamp}"


class TaskExecutionFormHandler:
    """Handler for Task Execution Form"""

    def __init__(self):
        self.form_type = FormType.TASK_EXECUTION

    def handle(self, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Handle task execution form submission

        Args:
            form_data: Form data to process

        Returns:
            FormSubmissionResult with processing outcome
        """
        try:
            # Validate form
            form = validate_form(self.form_type, form_data)

            # Generate submission ID
            submission_id = self._generate_submission_id(form)

            # Log submission
            logger.info(f"Task execution form submitted: {submission_id}")
            logger.debug(f"Plan ID: {form.plan_id}")
            logger.debug(f"Task ID: {form.task_id}")
            logger.debug(f"Execution mode: {form.execution_mode.value}")

            # Process form (will be implemented in execution orchestrator)
            result_data = {
                'submission_id': submission_id,
                'plan_id': form.plan_id,
                'task_id': form.task_id,
                'execution_mode': form.execution_mode.value,
                'confidence_threshold': form.confidence_threshold,
                'status': 'queued_for_execution',
                'next_step': 'task_execution'
            }

            _record_submission_store(submission_id, self.form_type.value)
            return FormSubmissionResult(
                success=True,
                submission_id=submission_id,
                form_type=self.form_type,
                message="Task execution form submitted successfully. Execution will begin shortly.",
                data=result_data
            )

        except Exception as exc:
            logger.error(f"Error handling task execution form: {str(exc)}")
            return FormSubmissionResult(
                success=False,
                submission_id="",
                form_type=self.form_type,
                message=f"Error processing form: {str(exc)}",
                errors={'validation_error': str(exc)}
            )

    def _generate_submission_id(self, form: TaskExecutionForm) -> str:
        """Generate unique submission ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"task_exec_{form.task_id}_{timestamp}"


class ValidationFormHandler:
    """Handler for Validation Form"""

    def __init__(self):
        self.form_type = FormType.VALIDATION

    def handle(self, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Handle validation form submission

        Args:
            form_data: Form data to process

        Returns:
            FormSubmissionResult with processing outcome
        """
        try:
            # Validate form
            form = validate_form(self.form_type, form_data)

            # Generate submission ID
            submission_id = self._generate_submission_id(form)

            # Log submission
            logger.info(f"Validation form submitted: {submission_id}")
            logger.debug(f"Task ID: {form.task_id}")
            logger.debug(f"Output ID: {form.output_id}")
            logger.debug(f"Result: {form.validation_result.value}")
            logger.debug(f"Quality score: {form.quality_score}/10")

            # Process form (will update task status and trigger next steps)
            result_data = {
                'submission_id': submission_id,
                'task_id': form.task_id,
                'output_id': form.output_id,
                'validation_result': form.validation_result.value,
                'quality_score': form.quality_score,
                'has_corrections': form.corrections is not None,
                'status': 'validation_recorded',
                'next_step': 'update_task_status'
            }

            # If corrections exist, trigger correction capture
            if form.corrections:
                result_data['next_step'] = 'correction_capture'

            _record_submission_store(submission_id, self.form_type.value)
            return FormSubmissionResult(
                success=True,
                submission_id=submission_id,
                form_type=self.form_type,
                message="Validation recorded successfully. Thank you for your feedback!",
                data=result_data
            )

        except Exception as exc:
            logger.error(f"Error handling validation form: {str(exc)}")
            return FormSubmissionResult(
                success=False,
                submission_id="",
                form_type=self.form_type,
                message=f"Error processing form: {str(exc)}",
                errors={'validation_error': str(exc)}
            )

    def _generate_submission_id(self, form: ValidationForm) -> str:
        """Generate unique submission ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"validation_{form.output_id}_{timestamp}"


class CorrectionFormHandler:
    """Handler for Correction Form"""

    def __init__(self):
        self.form_type = FormType.CORRECTION

    def handle(self, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Handle correction form submission

        Args:
            form_data: Form data to process

        Returns:
            FormSubmissionResult with processing outcome
        """
        try:
            # Validate form
            form = validate_form(self.form_type, form_data)

            # Generate submission ID
            submission_id = self._generate_submission_id(form)

            # Log submission
            logger.info(f"Correction form submitted: {submission_id}")
            logger.debug(f"Task ID: {form.task_id}")
            logger.debug(f"Output ID: {form.output_id}")
            logger.debug(f"Correction types: {[ct.value for ct in form.correction_type]}")
            logger.debug(f"Severity: {form.severity.value}")

            # Process form (will be implemented in correction capture system)
            result_data = {
                'submission_id': submission_id,
                'task_id': form.task_id,
                'output_id': form.output_id,
                'correction_types': [ct.value for ct in form.correction_type],
                'severity': form.severity.value,
                'status': 'queued_for_training',
                'next_step': 'create_training_example'
            }

            _record_submission_store(submission_id, self.form_type.value)
            return FormSubmissionResult(
                success=True,
                submission_id=submission_id,
                form_type=self.form_type,
                message="Correction captured successfully. This will be used to improve Murphy's performance. Thank you!",
                data=result_data
            )

        except Exception as exc:
            logger.error(f"Error handling correction form: {str(exc)}")
            return FormSubmissionResult(
                success=False,
                submission_id="",
                form_type=self.form_type,
                message=f"Error processing form: {str(exc)}",
                errors={'validation_error': str(exc)}
            )

    def _generate_submission_id(self, form: CorrectionForm) -> str:
        """Generate unique submission ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"correction_{form.output_id}_{timestamp}"


class FormHandlerRegistry:
    """Registry of form handlers"""

    def __init__(self):
        self.handlers = {
            FormType.PLAN_UPLOAD: PlanUploadFormHandler(),
            FormType.PLAN_GENERATION: PlanGenerationFormHandler(),
            FormType.TASK_EXECUTION: TaskExecutionFormHandler(),
            FormType.VALIDATION: ValidationFormHandler(),
            FormType.CORRECTION: CorrectionFormHandler()
        }

    def get_handler(self, form_type: FormType):
        """Get handler for form type"""
        return self.handlers.get(form_type)

    def handle_form(self, form_type: FormType, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Handle form submission

        Args:
            form_type: Type of form
            form_data: Form data

        Returns:
            FormSubmissionResult
        """
        handler = self.get_handler(form_type)
        if not handler:
            return FormSubmissionResult(
                success=False,
                submission_id="",
                form_type=form_type,
                message=f"No handler found for form type: {form_type.value}",
                errors={'handler_error': 'Handler not found'}
            )

        return handler.handle(form_data)


# Global form handler registry
form_handler_registry = FormHandlerRegistry()


def submit_form(form_type: FormType, form_data: Dict[str, Any]) -> FormSubmissionResult:
    """
    Submit a form for processing

    Args:
        form_type: Type of form to submit
        form_data: Form data

    Returns:
        FormSubmissionResult with processing outcome
    """
    return form_handler_registry.handle_form(form_type, form_data)

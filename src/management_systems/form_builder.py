"""
Management Systems – Form Builder
================================

Intake forms that auto-create board items.

Provides:
- Field types matching Monday column types
- Conditional logic (show/hide fields based on answers)
- Form templates for common workflows (Bug Report, Feature Request,
  Client Intake, Incident Report)
- Form submission validation
- Matrix-native form rendering (sequential question flow in chat)
- Form response storage and analytics

Integration points:
    - Form submissions create board items via ``board_engine.py``
    - Submissions trigger automations via ``automation_recipes.py``
    - Chat flow managed through ``command_router.py`` (PR 2)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FORM_FIELDS: int = 50
MAX_FORM_OPTIONS: int = 100


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class FieldType(Enum):
    """Form field types mirroring Monday column types."""

    TEXT = "text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RATING = "rating"
    FILE = "file"
    PERSON = "person"
    STATUS = "status"
    PRIORITY = "priority"


class FormTemplateType(Enum):
    """Pre-built form templates."""

    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    CLIENT_INTAKE = "client_intake"
    INCIDENT_REPORT = "incident_report"
    GENERAL_REQUEST = "general_request"
    ONBOARDING_CHECKLIST = "onboarding_checklist"
    CHANGE_REQUEST = "change_request"


class FormStatus(Enum):
    """Lifecycle status of a form."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SubmissionStatus(Enum):
    """Outcome status of a form submission."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    PROCESSED = "processed"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FormField:
    """A single field in a form.

    Args:
        title: Display label.
        field_type: Data type.
        required: Whether the field must be filled.
        options: Allowed values for dropdown/checkbox fields.
        placeholder: Hint text shown in the Matrix prompt.
        board_column_id: Target column in the destination board.
        condition: Optional condition dict for show/hide logic.
          Format: ``{"field_id": "...", "operator": "eq", "value": "..."}``
        min_value: Minimum value for number/rating fields.
        max_value: Maximum value for number/rating fields.
    """

    title: str
    field_type: FieldType = FieldType.TEXT
    required: bool = False
    options: List[str] = field(default_factory=list)
    placeholder: str = ""
    board_column_id: str = ""
    condition: Optional[Dict[str, Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    id: str = field(default_factory=_uid)

    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a value against this field's constraints.

        Args:
            value: The submitted value.

        Returns:
            ``(True, None)`` if valid, ``(False, error_message)`` otherwise.
        """
        if self.required and (value is None or value == ""):
            return False, f"Field '{self.title}' is required."
        if value is None or value == "":
            return True, None  # Optional empty is OK

        if self.field_type == FieldType.NUMBER:
            try:
                num = float(value)
            except (TypeError, ValueError):
                return False, f"Field '{self.title}' must be a number."
            if self.min_value is not None and num < self.min_value:
                return False, f"Field '{self.title}' must be ≥ {self.min_value}."
            if self.max_value is not None and num > self.max_value:
                return False, f"Field '{self.title}' must be ≤ {self.max_value}."

        elif self.field_type == FieldType.EMAIL:
            if "@" not in str(value):
                return False, f"Field '{self.title}' must be a valid email address."

        elif self.field_type in (FieldType.DROPDOWN, FieldType.STATUS, FieldType.PRIORITY):
            if self.options and str(value) not in self.options:
                return False, (
                    f"Field '{self.title}' must be one of: {', '.join(self.options)}"
                )

        elif self.field_type == FieldType.RATING:
            try:
                rating = int(value)
            except (TypeError, ValueError):
                return False, f"Field '{self.title}' must be an integer rating."
            lo = int(self.min_value) if self.min_value is not None else 1
            hi = int(self.max_value) if self.max_value is not None else 5
            if not (lo <= rating <= hi):
                return False, f"Field '{self.title}' must be between {lo} and {hi}."

        return True, None

    def is_visible(self, current_answers: Dict[str, Any]) -> bool:
        """Return *True* if this field should be shown given *current_answers*.

        Evaluates the field's conditional logic, if any.

        Args:
            current_answers: Mapping of field_id → submitted value.

        Returns:
            *True* if the field should be shown.
        """
        if self.condition is None:
            return True
        cond_field_id = self.condition.get("field_id", "")
        operator = self.condition.get("operator", "eq")
        expected = self.condition.get("value")
        actual = current_answers.get(cond_field_id)
        if operator == "eq":
            return actual == expected
        if operator == "neq":
            return actual != expected
        if operator == "is_empty":
            return not actual
        if operator == "is_not_empty":
            return bool(actual)
        return True

    def render_prompt(self) -> str:
        """Render the Matrix chat prompt for this field."""
        req_marker = " **(required)**" if self.required else ""
        hint = f"\n  _{self.placeholder}_" if self.placeholder else ""
        if self.field_type in (FieldType.DROPDOWN, FieldType.STATUS, FieldType.PRIORITY):
            options_str = ", ".join(self.options) if self.options else "any value"
            return f"**{self.title}**{req_marker}{hint}\n  Options: {options_str}"
        if self.field_type == FieldType.RATING:
            lo = int(self.min_value) if self.min_value is not None else 1
            hi = int(self.max_value) if self.max_value is not None else 5
            return f"**{self.title}**{req_marker}{hint}\n  Enter a rating from {lo} to {hi}"
        if self.field_type == FieldType.CHECKBOX:
            return f"**{self.title}**{req_marker}{hint}\n  Enter yes/no"
        return f"**{self.title}**{req_marker}{hint}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "field_type": self.field_type.value,
            "required": self.required,
            "options": self.options,
            "placeholder": self.placeholder,
            "board_column_id": self.board_column_id,
            "condition": self.condition,
            "min_value": self.min_value,
            "max_value": self.max_value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormField":
        obj = cls(
            title=data["title"],
            field_type=FieldType(data.get("field_type", "text")),
            required=data.get("required", False),
            options=data.get("options", []),
            placeholder=data.get("placeholder", ""),
            board_column_id=data.get("board_column_id", ""),
            condition=data.get("condition"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
        )
        obj.id = data.get("id", obj.id)
        return obj


@dataclass
class FormSubmission:
    """A completed form submission.

    Args:
        form_id: Source form ID.
        submitted_by: Matrix user ID.
        answers: Mapping of field_id → submitted value.
        board_item_id: Board item created from this submission.
        status: Processing status.
        validation_errors: Any validation error messages.
    """

    form_id: str
    submitted_by: str
    answers: Dict[str, Any] = field(default_factory=dict)
    board_item_id: str = ""
    status: SubmissionStatus = SubmissionStatus.PENDING
    validation_errors: List[str] = field(default_factory=list)
    id: str = field(default_factory=_uid)
    submitted_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "form_id": self.form_id,
            "submitted_by": self.submitted_by,
            "answers": self.answers,
            "board_item_id": self.board_item_id,
            "status": self.status.value,
            "validation_errors": self.validation_errors,
            "submitted_at": self.submitted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormSubmission":
        obj = cls(
            form_id=data["form_id"],
            submitted_by=data.get("submitted_by", ""),
            answers=data.get("answers", {}),
            board_item_id=data.get("board_item_id", ""),
            status=SubmissionStatus(data.get("status", "pending")),
            validation_errors=data.get("validation_errors", []),
        )
        obj.id = data.get("id", obj.id)
        obj.submitted_at = data.get("submitted_at", obj.submitted_at)
        return obj


@dataclass
class FormTemplate:
    """A reusable form definition.

    Args:
        name: Display name.
        template_type: Enum identifier.
        description: Use-case description.
        fields: Ordered list of form fields.
        destination_board_id: Board to create items in.
        destination_group_id: Group to add items to.
        item_name_template: Item name template string using ``{field_title}``.
    """

    name: str
    template_type: FormTemplateType
    description: str = ""
    fields: List[FormField] = field(default_factory=list)
    destination_board_id: str = ""
    destination_group_id: str = ""
    item_name_template: str = "{Title}"
    status: FormStatus = FormStatus.DRAFT
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "template_type": self.template_type.value,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "destination_board_id": self.destination_board_id,
            "destination_group_id": self.destination_group_id,
            "item_name_template": self.item_name_template,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormTemplate":
        obj = cls(
            name=data["name"],
            template_type=FormTemplateType(data["template_type"]),
            description=data.get("description", ""),
            destination_board_id=data.get("destination_board_id", ""),
            destination_group_id=data.get("destination_group_id", ""),
            item_name_template=data.get("item_name_template", "{Title}"),
            status=FormStatus(data.get("status", "draft")),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.fields = [FormField.from_dict(f) for f in data.get("fields", [])]
        return obj


# ---------------------------------------------------------------------------
# Built-in form templates
# ---------------------------------------------------------------------------


def _make_bug_report_template() -> FormTemplate:
    return FormTemplate(
        name="Bug Report",
        template_type=FormTemplateType.BUG_REPORT,
        description="Report a software defect with reproduction steps.",
        item_name_template="Bug: {Title}",
        fields=[
            FormField(title="Title", field_type=FieldType.TEXT, required=True,
                      placeholder="Brief description of the bug"),
            FormField(title="Severity", field_type=FieldType.PRIORITY, required=True,
                      options=["critical", "high", "medium", "low"]),
            FormField(title="Module", field_type=FieldType.DROPDOWN,
                      options=["llm_controller", "matrix_bridge", "trading_bot_engine",
                               "automation_scaler", "other"],
                      placeholder="Affected Murphy module"),
            FormField(title="Steps to Reproduce", field_type=FieldType.LONG_TEXT, required=True,
                      placeholder="1. Do this\n2. Do that\n3. See error"),
            FormField(title="Expected Behaviour", field_type=FieldType.LONG_TEXT,
                      placeholder="What should have happened"),
            FormField(title="Reporter Email", field_type=FieldType.EMAIL),
        ],
    )


def _make_feature_request_template() -> FormTemplate:
    return FormTemplate(
        name="Feature Request",
        template_type=FormTemplateType.FEATURE_REQUEST,
        description="Request a new feature or enhancement.",
        item_name_template="Feature: {Title}",
        fields=[
            FormField(title="Title", field_type=FieldType.TEXT, required=True,
                      placeholder="Short name for the feature"),
            FormField(title="Priority", field_type=FieldType.PRIORITY,
                      options=["critical", "high", "medium", "low"]),
            FormField(title="Use Case", field_type=FieldType.LONG_TEXT, required=True,
                      placeholder="Describe the problem this solves"),
            FormField(title="Proposed Solution", field_type=FieldType.LONG_TEXT,
                      placeholder="How you envision this working"),
            FormField(title="Business Value", field_type=FieldType.RATING,
                      min_value=1, max_value=5,
                      placeholder="1=nice to have, 5=critical"),
        ],
    )


def _make_incident_report_template() -> FormTemplate:
    return FormTemplate(
        name="Incident Report",
        template_type=FormTemplateType.INCIDENT_REPORT,
        description="Report a production incident or outage.",
        item_name_template="Incident: {Title}",
        fields=[
            FormField(title="Title", field_type=FieldType.TEXT, required=True,
                      placeholder="Short incident summary"),
            FormField(title="Severity", field_type=FieldType.PRIORITY, required=True,
                      options=["critical", "high", "medium", "low"]),
            FormField(title="Affected Module", field_type=FieldType.DROPDOWN,
                      options=["matrix_bridge", "llm_controller", "trading_bot_engine",
                               "infrastructure", "security", "other"]),
            FormField(title="Start Time", field_type=FieldType.TEXT, required=True,
                      placeholder="YYYY-MM-DD HH:MM UTC"),
            FormField(title="Impact Description", field_type=FieldType.LONG_TEXT, required=True,
                      placeholder="What is broken or affected?"),
            FormField(title="Immediate Actions Taken", field_type=FieldType.LONG_TEXT,
                      placeholder="What has already been done to mitigate?"),
            FormField(title="On-Call Engineer", field_type=FieldType.PERSON),
        ],
    )


def _make_client_intake_template() -> FormTemplate:
    return FormTemplate(
        name="Client Intake",
        template_type=FormTemplateType.CLIENT_INTAKE,
        description="Onboarding intake form for new clients.",
        item_name_template="Client: {Company Name}",
        fields=[
            FormField(title="Company Name", field_type=FieldType.TEXT, required=True),
            FormField(title="Primary Contact", field_type=FieldType.TEXT, required=True),
            FormField(title="Contact Email", field_type=FieldType.EMAIL, required=True),
            FormField(title="Contact Phone", field_type=FieldType.PHONE),
            FormField(title="Service Package", field_type=FieldType.DROPDOWN,
                      options=["Starter", "Professional", "Enterprise", "Custom"],
                      required=True),
            FormField(title="Start Date", field_type=FieldType.DATE, required=True),
            FormField(title="Special Requirements", field_type=FieldType.LONG_TEXT,
                      placeholder="Any specific needs or constraints"),
        ],
    )


_FORM_TEMPLATES: Dict[FormTemplateType, FormTemplate] = {
    FormTemplateType.BUG_REPORT: _make_bug_report_template(),
    FormTemplateType.FEATURE_REQUEST: _make_feature_request_template(),
    FormTemplateType.INCIDENT_REPORT: _make_incident_report_template(),
    FormTemplateType.CLIENT_INTAKE: _make_client_intake_template(),
}


# ---------------------------------------------------------------------------
# Form Builder
# ---------------------------------------------------------------------------


class FormBuilder:
    """Manages intake forms and processes submissions.

    Supports creating custom forms and loading pre-built templates.
    Handles sequential Matrix chat flows, validation, and routing
    submissions to board items.

    Example::

        builder = FormBuilder()
        form = builder.load_template(FormTemplateType.BUG_REPORT)

        # Interactive chat session
        session = builder.start_session(form.id, "@user:server")
        prompt = builder.get_next_prompt(session["session_id"])

        builder.answer_field(session["session_id"], "Title", "Login breaks on Safari")
        builder.answer_field(session["session_id"], "Severity", "high")
        submission = builder.submit(session["session_id"])
    """

    def __init__(self) -> None:
        self._forms: Dict[str, FormTemplate] = {}
        self._submissions: Dict[str, FormSubmission] = {}
        # Active chat sessions: {session_id: {form_id, user_id, answers, field_index}}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._on_submit: Optional[Callable[[FormSubmission], None]] = None

    # -- Form management ----------------------------------------------------

    def create_form(
        self,
        name: str,
        template_type: FormTemplateType,
        *,
        description: str = "",
        fields: Optional[List[FormField]] = None,
        destination_board_id: str = "",
        destination_group_id: str = "",
        item_name_template: str = "{Title}",
    ) -> FormTemplate:
        """Create a new form.

        Args:
            name: Form display name.
            template_type: Category identifier.
            description: Use-case description.
            fields: Field list (empty starts with a bare form).
            destination_board_id: Target board for submissions.
            destination_group_id: Target group for submissions.
            item_name_template: Item name template.

        Returns:
            The created :class:`FormTemplate`.
        """
        form = FormTemplate(
            name=name,
            template_type=template_type,
            description=description,
            fields=fields or [],
            destination_board_id=destination_board_id,
            destination_group_id=destination_group_id,
            item_name_template=item_name_template,
            status=FormStatus.ACTIVE,
        )
        self._forms[form.id] = form
        logger.info("Form created: %s (%s)", name, form.id)
        return form

    def load_template(self, template_type: FormTemplateType) -> FormTemplate:
        """Load and register a pre-built form template.

        Args:
            template_type: Which template to load.

        Returns:
            A copy of the template registered as an active form.

        Raises:
            KeyError: If the template type is unknown.
        """
        proto = _FORM_TEMPLATES.get(template_type)
        if proto is None:
            raise KeyError(f"Unknown form template: {template_type.value}")
        import copy
        form = copy.deepcopy(proto)
        form.status = FormStatus.ACTIVE
        self._forms[form.id] = form
        return form

    def get_form(self, form_id: str) -> Optional[FormTemplate]:
        return self._forms.get(form_id)

    def list_forms(
        self, *, status: Optional[FormStatus] = None
    ) -> List[FormTemplate]:
        forms = list(self._forms.values())
        if status is not None:
            forms = [f for f in forms if f.status == status]
        return sorted(forms, key=lambda f: f.created_at)

    def add_field(
        self,
        form_id: str,
        field: FormField,
    ) -> bool:
        """Append a field to an existing form."""
        form = self._forms.get(form_id)
        if form is None:
            return False
        if len(form.fields) >= MAX_FORM_FIELDS:
            raise ValueError("Form has reached the maximum field limit")
        form.fields.append(field)
        return True

    # -- Chat session management --------------------------------------------

    def start_session(
        self, form_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Start an interactive form session for a Matrix user.

        Args:
            form_id: Form to use.
            user_id: Matrix user starting the session.

        Returns:
            Session dict with ``session_id`` key.

        Raises:
            KeyError: If *form_id* is not found.
        """
        form = self._forms.get(form_id)
        if form is None:
            raise KeyError(f"Form not found: {form_id}")
        session_id = _uid()
        self._sessions[session_id] = {
            "session_id": session_id,
            "form_id": form_id,
            "user_id": user_id,
            "answers": {},
            "field_index": 0,
            "started_at": _now(),
        }
        logger.debug("Form session started: %s for %s", session_id, user_id)
        return self._sessions[session_id]

    def get_next_prompt(self, session_id: str) -> Optional[str]:
        """Return the prompt for the next unanswered visible field.

        Args:
            session_id: Active chat session.

        Returns:
            Markdown prompt string, or *None* if the form is complete.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        form = self._forms.get(session["form_id"])
        if form is None:
            return None

        answers = session["answers"]
        for f in form.fields:
            if f.id in answers:
                continue
            if not f.is_visible(answers):
                continue
            progress = f"{list(answers.keys()).count(f.id)} / {len(form.fields)}"
            return f.render_prompt() + f"\n\n_({progress} fields answered)_"

        return None  # All fields answered

    def answer_field(
        self,
        session_id: str,
        field_title_or_id: str,
        value: Any,
    ) -> Tuple[bool, Optional[str]]:
        """Record an answer for a field.

        Args:
            session_id: Active chat session.
            field_title_or_id: Field title or ID.
            value: Submitted value.

        Returns:
            ``(True, None)`` on success or ``(False, error)`` on validation failure.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False, "Session not found."
        form = self._forms.get(session["form_id"])
        if form is None:
            return False, "Form not found."

        target_field: Optional[FormField] = None
        for f in form.fields:
            if f.id == field_title_or_id or f.title.lower() == field_title_or_id.lower():
                target_field = f
                break

        if target_field is None:
            return False, f"Field '{field_title_or_id}' not found."

        ok, err = target_field.validate(value)
        if not ok:
            return False, err

        session["answers"][target_field.id] = value
        return True, None

    def submit(self, session_id: str) -> Optional[FormSubmission]:
        """Finalise a session and create a form submission.

        Validates all required visible fields. On success, creates a
        :class:`FormSubmission` and fires the on-submit callback.

        Args:
            session_id: Active chat session to submit.

        Returns:
            The :class:`FormSubmission` on success, or *None* if session
            is not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        form = self._forms.get(session["form_id"])
        if form is None:
            return None

        answers = session["answers"]
        errors: List[str] = []
        for f in form.fields:
            if not f.is_visible(answers):
                continue
            value = answers.get(f.id, "")
            ok, err = f.validate(value)
            if not ok and err:
                errors.append(err)

        submission = FormSubmission(
            form_id=form.id,
            submitted_by=session["user_id"],
            answers=dict(answers),
            status=SubmissionStatus.VALIDATED if not errors else SubmissionStatus.REJECTED,
            validation_errors=errors,
        )
        self._submissions[submission.id] = submission

        # Clean up session
        del self._sessions[session_id]

        if not errors and self._on_submit is not None:
            try:
                self._on_submit(submission)
            except Exception as exc:
                logger.error("on_submit callback failed: %s", exc)

        logger.info(
            "Form %s submitted by %s: %s",
            form.id,
            session["user_id"],
            submission.status.value,
        )
        return submission

    def register_on_submit(
        self, callback: Callable[[FormSubmission], None]
    ) -> None:
        """Register a callback invoked on each successful submission."""
        self._on_submit = callback

    # -- Submissions --------------------------------------------------------

    def get_submission(self, submission_id: str) -> Optional[FormSubmission]:
        return self._submissions.get(submission_id)

    def list_submissions(
        self,
        *,
        form_id: Optional[str] = None,
        status: Optional[SubmissionStatus] = None,
        limit: int = 100,
    ) -> List[FormSubmission]:
        subs = list(self._submissions.values())
        if form_id is not None:
            subs = [s for s in subs if s.form_id == form_id]
        if status is not None:
            subs = [s for s in subs if s.status == status]
        return sorted(subs, key=lambda s: s.submitted_at, reverse=True)[:limit]

    def get_analytics(self, form_id: str) -> Dict[str, Any]:
        """Return submission analytics for a form.

        Args:
            form_id: Form to analyse.

        Returns:
            Dict with ``total``, ``validated``, ``rejected``, ``processed``,
            and ``field_response_rates`` keys.
        """
        subs = self.list_submissions(form_id=form_id)
        total = len(subs)
        validated = sum(1 for s in subs if s.status == SubmissionStatus.VALIDATED)
        rejected = sum(1 for s in subs if s.status == SubmissionStatus.REJECTED)
        processed = sum(1 for s in subs if s.status == SubmissionStatus.PROCESSED)

        form = self._forms.get(form_id)
        field_response_rates: Dict[str, float] = {}
        if form and total > 0:
            for f in form.fields:
                answered = sum(
                    1 for s in subs if f.id in s.answers and s.answers[f.id] != ""
                )
                field_response_rates[f.title] = round(answered / total * 100, 1)

        return {
            "total": total,
            "validated": validated,
            "rejected": rejected,
            "processed": processed,
            "field_response_rates": field_response_rates,
        }

    @staticmethod
    def list_templates() -> List[FormTemplate]:
        """Return all available built-in form templates."""
        return list(_FORM_TEMPLATES.values())

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forms": {fid: f.to_dict() for fid, f in self._forms.items()},
            "submissions": {
                sid: s.to_dict()
                for sid, s in list(self._submissions.items())[-500:]
            },
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._forms = {
            fid: FormTemplate.from_dict(fdata)
            for fid, fdata in data.get("forms", {}).items()
        }
        self._submissions = {
            sid: FormSubmission.from_dict(sdata)
            for sid, sdata in data.get("submissions", {}).items()
        }

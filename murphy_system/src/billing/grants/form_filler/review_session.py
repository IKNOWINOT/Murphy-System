"""
Review Session — Pydantic models and manager for grant form review sessions.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FormField(BaseModel):
    field_id: str
    label: str
    field_type: str
    required: bool = True
    max_length: Optional[int] = None
    options: Optional[List[str]] = None
    validation_regex: Optional[str] = None
    help_text: str = ""
    section_id: str = "default"
    data_source_hint: str = "company_info"
    legal_certification: bool = False


class FormSection(BaseModel):
    section_id: str
    title: str
    description: str = ""
    order: int = 0


class ValidationRule(BaseModel):
    rule_id: str
    field_id: str
    rule_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


class FormDefinition(BaseModel):
    form_id: str
    form_name: str
    grant_program_id: str
    version: str = "1.0"
    fields: List[FormField] = Field(default_factory=list)
    sections: List[FormSection] = Field(default_factory=list)
    validation_rules: List[ValidationRule] = Field(default_factory=list)
    submission_format: str = "pdf"


class FilledField(BaseModel):
    field_id: str
    value: Any = None
    confidence: float = 0.0
    source: str = "llm_generated"
    status: str = "needs_review"
    reasoning: str = ""
    alternatives: List[str] = Field(default_factory=list)
    edited_by_human: bool = False


class ReviewSession(BaseModel):
    review_id: str
    session_id: str
    application_id: str
    form_id: str
    filled_fields: List[FilledField] = Field(default_factory=list)
    status: str = "draft"
    reviewer_id: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    review_notes: str = ""


class ReviewSessionManager:
    def __init__(self) -> None:
        self._reviews: Dict[str, ReviewSession] = {}
        self._app_to_review: Dict[str, str] = {}

    def create_review(
        self,
        session_id: str,
        application_id: str,
        form_id: str,
        filled_fields: List[FilledField],
    ) -> ReviewSession:
        review_id = str(uuid.uuid4())
        review = ReviewSession(
            review_id=review_id,
            session_id=session_id,
            application_id=application_id,
            form_id=form_id,
            filled_fields=list(filled_fields),
            status="draft",
            created_at=_now(),
        )
        self._reviews[review_id] = review
        self._app_to_review[application_id] = review_id
        return review

    def get_review(self, review_id: str) -> Optional[ReviewSession]:
        return self._reviews.get(review_id)

    def get_review_for_application(self, application_id: str) -> Optional[ReviewSession]:
        review_id = self._app_to_review.get(application_id)
        if review_id is None:
            return None
        return self._reviews.get(review_id)

    def start_review(self, review_id: str, reviewer_id: str) -> Optional[ReviewSession]:
        review = self._reviews.get(review_id)
        if review is None:
            return None
        review.status = "in_review"
        review.reviewer_id = reviewer_id
        return review

    def approve_review(
        self,
        review_id: str,
        reviewer_id: str,
        notes: str,
    ) -> Optional[ReviewSession]:
        review = self._reviews.get(review_id)
        if review is None:
            return None
        review.status = "approved"
        review.reviewer_id = reviewer_id
        review.review_notes = notes
        review.approved_at = _now()
        return review

    def reject_review(
        self,
        review_id: str,
        reviewer_id: str,
        notes: str,
    ) -> Optional[ReviewSession]:
        review = self._reviews.get(review_id)
        if review is None:
            return None
        review.status = "draft"
        review.reviewer_id = reviewer_id
        review.review_notes = notes
        return review

    def edit_field(
        self,
        review_id: str,
        field_id: str,
        new_value: Any,
        reviewer_id: str,
    ) -> Optional[FilledField]:
        review = self._reviews.get(review_id)
        if review is None:
            return None
        for ff in review.filled_fields:
            if ff.field_id == field_id:
                ff.value = new_value
                ff.edited_by_human = True
                ff.source = "user_input"
                ff.confidence = 1.0
                ff.status = "auto_filled"
                return ff
        new_ff = FilledField(
            field_id=field_id,
            value=new_value,
            confidence=1.0,
            source="user_input",
            status="auto_filled",
            edited_by_human=True,
        )
        review.filled_fields.append(new_ff)
        return new_ff

    def get_review_summary(self, review_id: str) -> Dict[str, Any]:
        review = self._reviews.get(review_id)
        if review is None:
            return {}
        counts: Dict[str, int] = {
            "auto_filled": 0,
            "needs_review": 0,
            "blocked_human_required": 0,
            "total": 0,
        }
        for ff in review.filled_fields:
            counts["total"] += 1
            counts[ff.status] = counts.get(ff.status, 0) + 1
        return counts

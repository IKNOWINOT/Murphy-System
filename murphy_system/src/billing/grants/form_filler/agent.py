"""
Form Filler Agent — Orchestrates form filling with HITL confidence tiers.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.billing.grants.form_filler.confidence_scorer import (
    TIER_AUTO,
    TIER_BLOCKED,
    TIER_REVIEW,
    ConfidenceScorer,
)
from src.billing.grants.form_filler.field_mapper import FieldMapper
from src.billing.grants.form_filler.review_session import FilledField, FormDefinition
from src.billing.grants.hitl_task_queue import HITLTaskQueue
from src.billing.grants.murphy_profiles import MurphyProfileManager
from src.billing.grants.session_manager import GrantSessionManager

logger = logging.getLogger(__name__)


class FormFillerAgent:
    def __init__(
        self,
        session_manager: GrantSessionManager,
        profile_manager: MurphyProfileManager,
        task_queue: HITLTaskQueue,
    ) -> None:
        self.session_manager = session_manager
        self.profile_manager = profile_manager
        self.task_queue = task_queue
        self.field_mapper = FieldMapper()
        self.confidence_scorer = ConfidenceScorer()

    def fill_form(
        self,
        session_id: str,
        tenant_id: str,
        application_id: str,
        form_def: FormDefinition,
    ) -> List[FilledField]:
        saved_data = self.session_manager.get_saved_form_data(session_id, tenant_id)

        app = self.session_manager.get_application(application_id, session_id, tenant_id)
        program_id = app.program_id if app else ""

        profile = self.profile_manager.get_best_profile_for_program(
            session_id, tenant_id, program_id
        )
        profile_data = self.profile_manager.to_form_data(profile) if profile else {}

        mapped_values = self.field_mapper.map_fields(form_def, saved_data, profile_data)
        filled_fields = self.confidence_scorer.score_all_fields(form_def, mapped_values)

        auto_save: Dict[str, Any] = {}

        for ff in filled_fields:
            if ff.status == TIER_BLOCKED and ff.value is None and not _is_legal_cert(form_def, ff.field_id):
                generated_value, gen_conf = self._generate_field_value(
                    _get_form_field(form_def, ff.field_id),
                    {**saved_data, **profile_data},
                )
                if generated_value:
                    ff.value = generated_value
                    ff.source = "llm_generated"
                    final_conf, status = self.confidence_scorer.score_field(
                        _get_form_field(form_def, ff.field_id),
                        generated_value,
                        "llm_generated",
                        gen_conf,
                    )
                    ff.confidence = round(final_conf, 4)
                    ff.status = status
                    ff.reasoning = f"Generated placeholder value with confidence {final_conf:.2f}."

            tier_map = {
                "auto_filled": TIER_AUTO,
                "needs_review": TIER_REVIEW,
                "blocked_human_required": TIER_BLOCKED,
            }
            hitl_tier = tier_map.get(ff.status, TIER_BLOCKED)

            if hitl_tier in (TIER_REVIEW, TIER_BLOCKED):
                self.task_queue.enqueue(
                    session_id=session_id,
                    application_id=application_id,
                    field_id=ff.field_id,
                    tier=hitl_tier,
                    value=ff.value,
                    confidence=ff.confidence,
                    reasoning=ff.reasoning,
                )

            if ff.value is not None and ff.status != TIER_BLOCKED:
                auto_save[ff.field_id] = ff.value

        if auto_save:
            self.session_manager.save_form_data(session_id, tenant_id, auto_save)

        return filled_fields

    def _generate_field_value(
        self,
        field: Any,
        context: Dict[str, Any],
    ) -> Tuple[str, float]:
        if field is None:
            return ("", 0.3)

        fid = field.field_id.lower()
        label = field.label.lower()

        if "project_title" in fid or "project title" in label:
            company = context.get("company_name", context.get("company_legal_name", "Company"))
            return (f"{company} Innovation Project", 0.6)

        if "project_description" in fid or "project description" in label:
            val = (
                context.get("rd_description")
                or context.get("technical_focus")
                or "Innovative technology project."
            )
            return (str(val), 0.55)

        if "budget" in fid or "funding" in fid:
            revenue = float(context.get("annual_revenue_usd", context.get("annual_revenue", 100000)) or 100000)
            budget = str(int(min(revenue * 0.1, 275000)))
            return (budget, 0.5)

        if "employee" in fid or "employee" in label:
            return (str(context.get("employee_count", 10)), 0.6)

        return ("", 0.3)

    def update_field(
        self,
        session_id: str,
        tenant_id: str,
        application_id: str,
        field_id: str,
        new_value: Any,
        reviewer_id: str,
    ) -> Optional[FilledField]:
        self.session_manager.save_form_data(session_id, tenant_id, {field_id: new_value})
        return FilledField(
            field_id=field_id,
            value=new_value,
            confidence=1.0,
            source="user_input",
            status="auto_filled",
            edited_by_human=True,
            reasoning=f"Manually edited by reviewer '{reviewer_id}'.",
        )


def _get_form_field(form_def: FormDefinition, field_id: str):
    for f in form_def.fields:
        if f.field_id == field_id:
            return f
    return None


def _is_legal_cert(form_def: FormDefinition, field_id: str) -> bool:
    f = _get_form_field(form_def, field_id)
    return f is not None and f.legal_certification

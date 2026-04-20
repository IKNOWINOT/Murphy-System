"""
Form Filler API — FastAPI router for form filler operations.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

# Import shared singletons and helpers from the parent grants API
from src.billing.grants.api import (
    _agent,
    _profile_manager,
    _review_manager,
    _session_manager,
    _task_queue,
    _EXPORT_GENERATORS,
    _validate_application_id,
    _validate_session_id,
    _validate_tenant_id,
    _validate_program_id,
)
from src.billing.grants.form_filler.form_definitions import FORM_REGISTRY, get_form

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/grants", tags=["grants-form-filler"])

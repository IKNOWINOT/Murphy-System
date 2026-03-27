"""
Document Export API — FastAPI router.

Endpoints
---------
POST /api/export                  — Export a bot output as a document
GET  /api/export/formats          — List available output formats
GET  /api/export/styles           — List available writing styles
GET  /api/export/templates        — List available template types
POST /api/brands                  — Register a brand profile
GET  /api/brands                  — List registered brand profiles
GET  /api/brands/{brand_id}       — Get a specific brand profile
DELETE /api/brands/{brand_id}     — Delete a brand profile
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    """Request body for POST /api/export."""

    source_output: Dict[str, Any]
    format: str = "markdown"
    brand_profile_id: Optional[str] = None
    writing_style: str = "formal_engineering"
    template_type: str = "cx_plan_report"


class BrandCreateRequest(BaseModel):
    """Request body for POST /api/brands."""

    company_name: str
    logo_url: Optional[str] = None
    logo_base64: Optional[str] = None
    primary_color: str = "#1E3A5F"
    secondary_color: str = "#2E86AB"
    accent_color: str = "#F18F01"
    font_heading: str = "Helvetica"
    font_body: str = "Helvetica"
    header_template: str = "**{company_name}** | {document_title} | {date}"
    footer_template: str = "{legal_line} | Page {page_number}"
    cover_page_template: Optional[str] = None
    legal_line: str = "© 2026 Murphy System. Confidential."
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Router factory (avoids hard FastAPI import at module load)
# ---------------------------------------------------------------------------


def create_router(pipeline=None, brand_registry=None):  # type: ignore[no-untyped-def]
    """
    Build and return a FastAPI ``APIRouter`` with all document export endpoints.

    Parameters
    ----------
    pipeline:
        An :class:`~export_pipeline.ExportPipeline` instance.
        If ``None`` a fresh one is created.
    brand_registry:
        A :class:`~brand_registry.BrandRegistry` instance shared with *pipeline*.
        If ``None`` the pipeline's own registry is used.
    """
    try:
        from fastapi import APIRouter, HTTPException
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI must be installed to use the export API.") from exc

    from .brand_registry import BrandProfile, BrandRegistry
    from .export_pipeline import ExportPipeline

    if pipeline is None:
        pipeline = ExportPipeline()
    if brand_registry is None:
        brand_registry = pipeline._brand_registry

    router = APIRouter(prefix="/api", tags=["document_export"])

    # ------------------------------------------------------------------
    # Export endpoint
    # ------------------------------------------------------------------

    @router.post("/export")
    async def export_document(request: ExportRequest):
        """Export bot JSON output as a branded, styled document."""
        try:
            result = await pipeline.export(
                source_output=request.source_output,
                format=request.format,
                brand_profile_id=request.brand_profile_id,
                writing_style=request.writing_style,
                template_type=request.template_type,
            )
            return result.model_dump()
        except ValueError as exc:
            logger.debug("Export rejected with invalid parameters: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid export parameters") from exc
        except Exception as exc:
            logger.exception("Export failed: %s", exc)
            raise HTTPException(status_code=500, detail="Export failed.") from exc

    @router.get("/export/formats")
    def list_formats():
        """Return available output formats."""
        return {"formats": pipeline.available_formats()}

    @router.get("/export/styles")
    def list_styles():
        """Return available writing styles."""
        return {"styles": pipeline.available_styles()}

    @router.get("/export/templates")
    def list_templates():
        """Return available template types."""
        return {"templates": pipeline.available_templates()}

    # ------------------------------------------------------------------
    # Brand endpoints
    # ------------------------------------------------------------------

    @router.post("/brands", status_code=201)
    def register_brand(request: BrandCreateRequest):
        """Register a new brand profile."""
        profile = BrandProfile(**request.model_dump())
        brand_registry.register(profile)
        return profile.model_dump()

    @router.get("/brands")
    def list_brands():
        """List all registered brand profiles."""
        return {"brands": [b.model_dump() for b in brand_registry.list_brands()]}

    @router.get("/brands/{brand_id}")
    def get_brand(brand_id: str):
        """Get a specific brand profile by ID."""
        profile = brand_registry.get(brand_id)
        if profile is None:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
        return profile.model_dump()

    @router.delete("/brands/{brand_id}")
    def delete_brand(brand_id: str):
        """Delete a brand profile."""
        deleted = brand_registry.delete(brand_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Brand '{brand_id}' not found or cannot be deleted.",
            )
        return {"deleted": brand_id}

    return router

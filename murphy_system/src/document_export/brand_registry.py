"""
Brand Asset Registry — per-user/per-org brand configurations.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default brand colours / fonts
# ---------------------------------------------------------------------------

_DEFAULT_BRAND_ID = "default"


class BrandProfile(BaseModel):
    """Immutable brand configuration record."""

    brand_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str = "murphy_system"

    # Logos — at most one should be set
    logo_url: Optional[str] = None
    logo_base64: Optional[str] = None

    # Colours (hex strings, e.g. "#1A2B3C")
    primary_color: str = "#1E3A5F"
    secondary_color: str = "#2E86AB"
    accent_color: str = "#F18F01"

    # Typography
    font_heading: str = "Helvetica"
    font_body: str = "Helvetica"

    # Header / footer / cover page (HTML/Markdown strings; may contain {placeholders})
    header_template: str = "**{company_name}** | {document_title} | {date}"
    footer_template: str = "{legal_line} | Page {page_number}"
    cover_page_template: Optional[str] = None

    # Legal / compliance
    legal_line: str = "© 2026 Murphy System. Confidential."

    # Arbitrary extra metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def render_header(self, context: Dict[str, str]) -> str:
        """Render the header template with the supplied context."""
        ctx = {"company_name": self.company_name, "legal_line": self.legal_line}
        ctx.update(context)
        try:
            return self.header_template.format(**ctx)
        except KeyError:
            return self.header_template

    def render_footer(self, context: Dict[str, str]) -> str:
        """Render the footer template with the supplied context."""
        ctx = {"company_name": self.company_name, "legal_line": self.legal_line}
        ctx.update(context)
        try:
            return self.footer_template.format(**ctx)
        except KeyError:
            return self.footer_template


# ---------------------------------------------------------------------------
# Built-in DEFAULT brand
# ---------------------------------------------------------------------------

_DEFAULT_BRAND = BrandProfile(
    brand_id=_DEFAULT_BRAND_ID,
    company_name="murphy_system",
    primary_color="#1E3A5F",
    secondary_color="#2E86AB",
    accent_color="#F18F01",
    font_heading="Helvetica",
    font_body="Helvetica",
    header_template="**{company_name}** | {document_title} | {date}",
    footer_template="{legal_line} | Page {page_number}",
    legal_line="© 2026 Murphy System. Confidential.",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class BrandRegistry:
    """In-memory store of brand profiles.

    Thread-safe via an internal lock (matching OptimizationEngine pattern).
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._brands: Dict[str, BrandProfile] = {
            _DEFAULT_BRAND_ID: _DEFAULT_BRAND,
        }

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def register(self, profile: BrandProfile) -> BrandProfile:
        """Store *profile* and return it (overwrites an existing entry with the same id)."""
        with self._lock:
            self._brands[profile.brand_id] = profile
            logger.info("Brand profile registered: %s (%s)", profile.brand_id, profile.company_name)
        return profile

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, brand_id: str) -> Optional[BrandProfile]:
        """Return the profile for *brand_id*, or ``None`` if not found."""
        with self._lock:
            return self._brands.get(brand_id)

    def get_or_default(self, brand_id: Optional[str]) -> BrandProfile:
        """Return the requested profile, falling back to DEFAULT if not found."""
        if brand_id is None:
            return _DEFAULT_BRAND
        profile = self.get(brand_id)
        if profile is None:
            logger.warning("Brand profile '%s' not found; using DEFAULT.", brand_id)
            return _DEFAULT_BRAND
        return profile

    def list_brands(self) -> List[BrandProfile]:
        """Return a snapshot of all registered brand profiles."""
        with self._lock:
            return list(self._brands.values())

    def delete(self, brand_id: str) -> bool:
        """Remove a brand profile.  Returns ``True`` if it existed."""
        if brand_id == _DEFAULT_BRAND_ID:
            logger.warning("Cannot delete the built-in DEFAULT brand.")
            return False
        with self._lock:
            existed = brand_id in self._brands
            self._brands.pop(brand_id, None)
        return existed

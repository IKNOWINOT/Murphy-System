# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Industry preset registry for the org_build_plan package.

Provides pre-configured organization profiles for rapid tenant deployment
across seven major industry verticals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IndustryPreset dataclass
# ---------------------------------------------------------------------------


@dataclass
class IndustryPreset:
    """A complete industry-specific configuration profile.

    Bundles default departments, connectors, compliance frameworks, and
    workflow templates so any new tenant can be provisioned in one call.
    """

    preset_id: str
    name: str
    description: str
    industry: str
    default_org_type: str
    default_labor_model: str
    default_company_size: str
    recommended_connectors: List[str] = field(default_factory=list)
    recommended_frameworks: List[str] = field(default_factory=list)
    default_departments: List[Dict[str, Any]] = field(default_factory=list)
    workflow_templates: List[Dict[str, Any]] = field(default_factory=list)
    setup_wizard_preset: str = "org_onboarding"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "preset_id": self.preset_id,
            "name": self.name,
            "description": self.description,
            "industry": self.industry,
            "default_org_type": self.default_org_type,
            "default_labor_model": self.default_labor_model,
            "default_company_size": self.default_company_size,
            "recommended_connectors": list(self.recommended_connectors),
            "recommended_frameworks": list(self.recommended_frameworks),
            "default_departments": [d.copy() for d in self.default_departments],
            "workflow_templates": [t.copy() for t in self.workflow_templates],
            "setup_wizard_preset": self.setup_wizard_preset,
        }


# ---------------------------------------------------------------------------
# Lazy-load individual preset modules
# ---------------------------------------------------------------------------

def _load_presets() -> Dict[str, IndustryPreset]:
    """Lazily import each preset module and return the registry dict."""
    from .energy_utilities import PRESET as _nrg
    from .financial_services import PRESET as _fin
    from .logistics_fleet import PRESET as _log
    from .manufacturing import PRESET as _mfg
    from .nonprofit_advocacy import PRESET as _npo
    from .retail_ecommerce import PRESET as _ret
    from .saas_agency import PRESET as _saas

    return {
        _mfg.preset_id: _mfg,
        _fin.preset_id: _fin,
        _log.preset_id: _log,
        _npo.preset_id: _npo,
        _nrg.preset_id: _nrg,
        _ret.preset_id: _ret,
        _saas.preset_id: _saas,
    }


INDUSTRY_PRESETS: Dict[str, IndustryPreset] = _load_presets()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_preset(preset_id: str) -> Optional[IndustryPreset]:
    """Return the :class:`IndustryPreset` for *preset_id*, or ``None``."""
    return INDUSTRY_PRESETS.get(preset_id)


def list_presets() -> List[Dict[str, Any]]:
    """Return a summary list of all available presets."""
    return [
        {
            "preset_id": p.preset_id,
            "name": p.name,
            "description": p.description,
            "industry": p.industry,
        }
        for p in INDUSTRY_PRESETS.values()
    ]


__all__ = [
    "IndustryPreset",
    "INDUSTRY_PRESETS",
    "get_preset",
    "list_presets",
]

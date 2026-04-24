"""
Grant Eligibility Engine — Matches project parameters to applicable grant programs.

Scoring algorithm:
  1. Hard filters: entity type, state, commercial, R&D activity requirements
  2. Project type overlap scoring
  3. Tag bonus scoring
  4. Final ranking by match score

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.billing.grants.models import (
    EligibilityMatch,
    EligibilityRequest,
    EligibilityResponse,
    Grant,
    GrantTrack,
)
from src.billing.grants.database import GRANT_CATALOG, list_grants

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project type aliases — normalize user input to internal project types
# ---------------------------------------------------------------------------
_PROJECT_TYPE_ALIASES: Dict[str, str] = {
    "agentic_ai": "agentic",
    "agentic_automation": "agentic",
    "building_automation": "bas_bms",
    "bas": "bas_bms",
    "bms": "bas_bms",
    "energy_management": "ems",
    "energy": "ems",
    "industrial": "scada",
    "manufacturing": "manufacturing_automation",
    "smart_factory": "smart_manufacturing",
    "ai": "ai_platform",
    "software": "software_rd",
    "iot": "industrial_iot",
    "hvac": "hvac_automation",
    "hvac_controls": "hvac_automation",
    "solar_pv": "solar",
    "solar_controls": "solar",
    "storage": "battery_storage",
    "ev": "ev_charging",
    "dr": "demand_response",
    "grid": "grid_interactive",
    "home_automation": "home_energy_management",
    "general_automation": "general_business_automation",
    "workflow_automation": "general_business_automation",
    "crm_automation": "general_business_automation",
    "compliance_automation": "automation_rd",
}


def _normalize_project_type(project_type: str) -> str:
    return _PROJECT_TYPE_ALIASES.get(project_type.lower(), project_type.lower())


# ---------------------------------------------------------------------------
# Eligibility Engine
# ---------------------------------------------------------------------------

class GrantEligibilityEngine:
    """Matches project parameters to applicable grant programs."""

    def __init__(self, catalog: Optional[Dict[str, Grant]] = None) -> None:
        self._catalog = catalog or GRANT_CATALOG

    def match(self, request: EligibilityRequest) -> EligibilityResponse:
        """
        Run eligibility matching for a project request.

        Args:
            request: EligibilityRequest with project parameters.

        Returns:
            EligibilityResponse with ranked list of matching grants.
        """
        normalized_project_type = _normalize_project_type(request.project_type)

        matches: List[EligibilityMatch] = []

        for grant in self._catalog.values():
            match = self._score_grant(grant, request, normalized_project_type)
            if match is not None:
                matches.append(match)

        # Sort by match score descending
        matches.sort(key=lambda m: m.match_score, reverse=True)

        total_value = sum(
            m.estimated_value_usd for m in matches if m.estimated_value_usd is not None
        )

        return EligibilityResponse(
            request=request,
            matches=matches,
            total_estimated_value_usd=total_value,
        )

    def _score_grant(
        self,
        grant: Grant,
        request: EligibilityRequest,
        normalized_project_type: str,
    ) -> Optional[EligibilityMatch]:
        """Score a single grant against the request. Returns None if ineligible."""
        reasons: List[str] = []
        score = 0.0

        # --- Hard filter: entity type ---
        if grant.eligible_entity_types:
            entity_norm = request.entity_type.lower()
            matched_entity = any(
                entity_norm in et.lower() or et.lower() in entity_norm
                for et in grant.eligible_entity_types
            )
            if not matched_entity:
                return None
        reasons.append(f"Entity type '{request.entity_type}' eligible")

        # --- Hard filter: state ---
        if grant.eligible_states:
            if request.state.upper() not in grant.eligible_states:
                return None
            reasons.append(f"Available in {request.state}")

        # --- Hard filter: commercial required ---
        if grant.requires_commercial and not request.is_commercial:
            return None

        # --- Hard filter: R&D activity required ---
        if grant.requires_rd_activity and not request.has_rd_activity:
            return None

        # --- Hard filter: existing building required ---
        if grant.requires_existing_building and not request.existing_building:
            return None

        # --- Project type match (primary signal) ---
        # Scoring uses presence-based matching (does request type appear in grant's list?)
        # rather than overlap-fraction — avoids penalizing grants with broad eligibility
        if grant.eligible_project_types:
            project_types_normalized = [
                _normalize_project_type(pt) for pt in grant.eligible_project_types
            ]
            req_types_normalized = set([
                normalized_project_type,
                *[_normalize_project_type(t) for t in request.tags],
            ])

            overlap = set(project_types_normalized) & req_types_normalized
            if overlap:
                # Presence bonus: 0.45 base + 0.05 per additional overlap type (cap 0.65)
                project_score = min(0.65, 0.45 + (len(overlap) - 1) * 0.05)
                score += project_score
                reasons.append(f"Matches project types: {', '.join(overlap)}")
            else:
                # Weak relevance — grant is broadly eligible but project type not listed
                score += 0.08
        else:
            # Grant has no project type restriction — broadly eligible
            score += 0.25
            reasons.append("No project type restriction — broadly eligible")

        # --- Tag bonus scoring ---
        if grant.tags and request.tags:
            req_tags_lower = {t.lower() for t in request.tags}
            grant_tags_lower = {t.lower() for t in grant.tags}
            tag_overlap = req_tags_lower & grant_tags_lower
            if tag_overlap:
                score += min(0.25, len(tag_overlap) * 0.05)
                reasons.append(f"Tag matches: {', '.join(tag_overlap)}")

        # --- R&D activity bonus ---
        if request.has_rd_activity and getattr(grant, "requires_rd_activity", False):
            score += 0.10
            reasons.append("R&D activity confirmed — required for this program")
        elif request.has_rd_activity and grant.tags and any(
            t in grant.tags for t in ("rd", "research", "innovation", "sbir", "sttr")
        ):
            score += 0.05
            reasons.append("R&D activity aligns with program focus")

        # --- Project cost signal ---
        if request.project_cost_usd and grant.min_amount_usd:
            if request.project_cost_usd >= grant.min_amount_usd:
                score += 0.05
                reasons.append("Project cost meets minimum program threshold")

        # --- Bonus: stacking opportunities ---
        stacking: List[str] = []
        if grant.stackable_with:
            for stack_id in grant.stackable_with:
                if stack_id in self._catalog:
                    stacking.append(stack_id)

        # --- Estimate value ---
        estimated_value: Optional[float] = None
        if request.project_cost_usd:
            if grant.max_amount_usd is not None:
                estimated_value = min(grant.max_amount_usd, request.project_cost_usd * 0.3)
            elif grant.min_amount_usd is not None:
                estimated_value = grant.min_amount_usd
        elif grant.max_amount_usd is not None:
            estimated_value = grant.max_amount_usd
        elif grant.min_amount_usd is not None:
            estimated_value = grant.min_amount_usd

        # Normalize score to 0–1
        score = min(1.0, max(0.0, score))

        return EligibilityMatch(
            grant=grant,
            match_score=round(score, 3),
            estimated_value_usd=estimated_value,
            match_reasons=reasons,
            stacking_opportunities=stacking,
        )

"""Grant eligibility matching engine."""

from __future__ import annotations

from typing import Any, Dict, List

from src.billing.grants.models import EligibilityResult, Grant, GrantTrack
from src.billing.grants.database import get_all_grants
from src.billing.grants.murphy_profiles import get_murphy_profiles


def match_grants(profile_data: Dict[str, Any]) -> List[EligibilityResult]:
    """Match grants against a company/project profile.

    Profile keys used:
        - entity_type: str (e.g., "small_business", "startup", "nonprofit", "individual")
        - state: str (2-letter state code)
        - verticals: List[str] (e.g., ["building_automation", "energy_management"])
        - project_type: str
        - annual_revenue: float
        - employee_count: int
        - project_cost: float
        - naics_codes: List[str]
        - is_rural: bool (for USDA eligibility)
        - has_ein: bool
        - has_sam_gov: bool

    Args:
        profile_data: Dictionary describing the applicant.

    Returns:
        Ranked list of EligibilityResult objects sorted by estimated_value descending.
    """
    grants = get_all_grants()
    results = [_score_grant(g, profile_data) for g in grants]
    return sorted(results, key=lambda r: r.estimated_value, reverse=True)


def match_for_murphy(profile_name: str = "sbir") -> List[EligibilityResult]:
    """Convenience method to match using Murphy's own Track A profiles.

    Args:
        profile_name: Short profile name ("sbir", "doe", "nsf", "manufacturing").

    Returns:
        Ranked list of EligibilityResult objects.
    """
    profiles = get_murphy_profiles()
    key = f"murphy_{profile_name}_profile"
    profile = profiles.get(key, profiles.get("murphy_sbir_profile"))
    return match_grants(profile)  # type: ignore[arg-type]


def match_for_customer(customer_profile: Dict[str, Any]) -> List[EligibilityResult]:
    """General eligibility matching for Track B customers.

    Args:
        customer_profile: Dictionary describing the customer.

    Returns:
        Ranked list of EligibilityResult objects.
    """
    return match_grants(customer_profile)


def _score_grant(grant: Grant, profile: Dict[str, Any]) -> EligibilityResult:
    """Score a single grant against a profile.

    Eligibility conditions checked:
        1. State: if grant.eligible_states is non-empty, profile state must be in it.
        2. Entity type: if grant.eligible_entity_types is non-empty, profile entity_type
           must appear in it.
        3. Verticals: if grant.eligible_verticals is non-empty, at least one profile
           vertical must overlap.
        4. USDA rural check: REAP requires is_rural=True.
        5. Registration checks: federal grants requiring SAM.gov note it as action item.

    Confidence is scored 0.0-1.0 based on how many positive signals are present.

    Args:
        grant: The Grant to evaluate.
        profile: Applicant profile dictionary.

    Returns:
        EligibilityResult with eligible flag, confidence, reasons, and action_items.
    """
    reasons: List[str] = []
    action_items: List[str] = []
    disqualifiers: List[str] = []
    positive_signals = 0
    total_checks = 0

    entity_type: str = profile.get("entity_type", "")
    state: str = profile.get("state", "")
    verticals: List[str] = profile.get("verticals", [])
    is_rural: bool = bool(profile.get("is_rural", False))
    has_ein: bool = bool(profile.get("has_ein", True))
    has_sam_gov: bool = bool(profile.get("has_sam_gov", False))
    project_cost: float = float(profile.get("project_cost", 0.0))

    # --- State check ---
    if grant.eligible_states:
        total_checks += 1
        if state and state.upper() in [s.upper() for s in grant.eligible_states]:
            reasons.append(f"State '{state}' is eligible for this program.")
            positive_signals += 1
        else:
            disqualifiers.append(
                f"Program limited to states: {', '.join(grant.eligible_states)}. "
                f"Profile state: '{state}'."
            )
    else:
        # All states eligible — minor positive signal
        reasons.append("Available in all states.")
        positive_signals += 1
        total_checks += 1

    # --- Entity type check ---
    if grant.eligible_entity_types and entity_type:
        total_checks += 1
        if entity_type in grant.eligible_entity_types:
            reasons.append(f"Entity type '{entity_type}' is eligible.")
            positive_signals += 1
        else:
            disqualifiers.append(
                f"Entity type '{entity_type}' not in eligible types: "
                f"{', '.join(grant.eligible_entity_types)}."
            )

    # --- Vertical overlap check ---
    if grant.eligible_verticals and verticals:
        total_checks += 1
        overlap = set(verticals) & set(grant.eligible_verticals)
        if overlap:
            reasons.append(f"Verticals overlap: {', '.join(sorted(overlap))}.")
            positive_signals += 1
        else:
            disqualifiers.append(
                f"No vertical overlap. Profile: {verticals}. "
                f"Grant requires: {grant.eligible_verticals}."
            )

    # --- USDA REAP rural requirement ---
    if grant.id == "usda_reap":
        total_checks += 1
        if is_rural:
            reasons.append("Rural location confirmed — REAP eligible.")
            positive_signals += 1
        else:
            disqualifiers.append("USDA REAP requires rural location (is_rural=True).")

    # --- Registration readiness ---
    federal_grant_ids = {
        "sbir_phase1", "sbir_phase2", "sbir_breakthrough", "sttr",
        "doe_arpa_e", "doe_amo", "doe_bto", "cesmii",
        "nsf_convergence", "nsf_pfi", "eda_b2s", "nist_mep", "doe_grip", "usda_reap",
    }
    if grant.id in federal_grant_ids:
        if not has_ein:
            action_items.append("Obtain EIN from IRS before applying.")
        if not has_sam_gov:
            action_items.append("Register in SAM.gov (allow 10 business days).")

    # --- Project cost vs grant range ---
    if project_cost > 0:
        if project_cost < grant.min_amount:
            action_items.append(
                f"Project cost ${project_cost:,.0f} is below minimum ${grant.min_amount:,.0f}. "
                "Consider scaling project scope."
            )
        elif project_cost > grant.max_amount:
            action_items.append(
                f"Project cost ${project_cost:,.0f} exceeds maximum ${grant.max_amount:,.0f}. "
                "Consider phasing the project."
            )

    # --- Eligibility decision ---
    eligible = len(disqualifiers) == 0
    if not eligible:
        reasons.extend(disqualifiers)

    # Confidence: ratio of positive signals to total checks
    confidence = (positive_signals / total_checks) if total_checks > 0 else 0.5
    if not eligible:
        confidence = min(confidence, 0.3)

    # Estimated value: midpoint of grant range, scaled by confidence
    estimated_midpoint = (grant.min_amount + grant.max_amount) / 2.0
    estimated_value = estimated_midpoint * confidence if eligible else 0.0

    return EligibilityResult(
        grant_id=grant.id,
        eligible=eligible,
        confidence=round(confidence, 3),
        reasons=reasons,
        estimated_value=round(estimated_value, 2),
        action_items=action_items,
    )

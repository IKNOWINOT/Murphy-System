# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Rosette Lens — MSS Data-Lens Bridge for the Murphy System

The "rosette" is the constellation of Rosetta agent positions.  Their
configuration shapes the *lens* of data that the MSS (Magnify/Simplify/
Solidify) system will operate on.

Different guises (named configurations) of the rosette produce different
data views for the LCM to act upon.

Usage::

    from rosette_lens import RosetteLens

    lens = RosetteLens()
    criteria = lens.select_lens(rosetta_states, {"intent": "sales_review"})
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in guise definitions
# ---------------------------------------------------------------------------
_GUISE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "default": {
        "description": "Standard balanced lens — all data sources at RM2",
        "resolution_level": "RM2",
        "data_sources": ["all"],
        "magnify_dims": [],
        "simplify_dims": [],
    },
    "sales_focus": {
        "description": "Magnify sales + revenue signals; simplify ops noise",
        "resolution_level": "RM3",
        "data_sources": ["crm", "pipeline", "revenue"],
        "magnify_dims": ["pipeline_value", "close_probability"],
        "simplify_dims": ["operational_overhead"],
    },
    "compliance_focus": {
        "description": "High-resolution compliance view; simplify unrelated data",
        "resolution_level": "RM4",
        "data_sources": ["compliance", "legal", "audit"],
        "magnify_dims": ["risk_score", "control_gap"],
        "simplify_dims": ["sales_metrics"],
    },
    "research_focus": {
        "description": "Research-mode lens with maximum data breadth at RM5",
        "resolution_level": "RM5",
        "data_sources": ["all"],
        "magnify_dims": ["novelty_score", "citation_density"],
        "simplify_dims": [],
    },
    "finance_focus": {
        "description": "Finance lens emphasising grant and funding data",
        "resolution_level": "RM3",
        "data_sources": ["grants", "financials", "runway"],
        "magnify_dims": ["grant_match_score", "burn_rate"],
        "simplify_dims": ["ops_metrics"],
    },
}


class RosetteLens:
    """Maps Rosetta agent positions/states to MSS filter criteria.

    The rosette is the constellation of agent positions.  Its configuration
    shapes the lens of data that MSS will magnify, simplify, or solidify.

    Different guises (configurations) of the rosette system produce different
    data views for the LCM to operate on.

    Thread-safety: this class is intentionally stateless beyond the active
    guise name; callers are responsible for locking if shared across threads.
    """

    def __init__(self, initial_guise: str = "default") -> None:
        self._active_guise: str = (
            initial_guise if initial_guise in _GUISE_DEFINITIONS else "default"
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def select_lens(
        self,
        rosetta_states: list[Any],
        query_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Derive MSS filter criteria from Rosetta agent states and context.

        The method examines the active guise together with the current agent
        states and the query context to produce a criteria dict that MSS
        can consume directly.

        Args:
            rosetta_states: List of ``RosettaAgentState`` (or plain dicts)
                describing each agent's current position/state.
            query_context: Ambient context for the query (keys like ``intent``,
                ``domain``, ``priority``, etc.).

        Returns:
            A dict with keys:
            - ``resolution_level`` (str) — target RM level for MSS
            - ``data_sources`` (list[str]) — data sources to include
            - ``magnify_dims`` (list[str]) — dimensions to amplify
            - ``simplify_dims`` (list[str]) — dimensions to reduce
            - ``guise`` (str) — name of the active guise used
            - ``agent_count`` (int) — number of states evaluated
            - ``context_intent`` (str) — echoed from *query_context*
        """
        guise = _GUISE_DEFINITIONS[self._active_guise]

        # Apply any intent-based guise override from the query context
        intent = query_context.get("intent", "")
        derived_guise = self._derive_guise_from_context(intent, rosetta_states)
        if derived_guise and derived_guise != self._active_guise:
            guise = _GUISE_DEFINITIONS.get(derived_guise, guise)
            logger.debug(
                "RosetteLens: context-derived guise %r overrides active %r",
                derived_guise,
                self._active_guise,
            )

        return {
            "resolution_level": guise["resolution_level"],
            "data_sources": list(guise["data_sources"]),
            "magnify_dims": list(guise["magnify_dims"]),
            "simplify_dims": list(guise["simplify_dims"]),
            "guise": derived_guise or self._active_guise,
            "agent_count": len(rosetta_states),
            "context_intent": intent,
        }

    def get_active_guise(self) -> str:
        """Return the current rosette configuration name."""
        return self._active_guise

    def set_guise(self, guise_name: str) -> None:
        """Switch the rosette to a named configuration.

        Silently falls back to ``"default"`` if *guise_name* is unknown.
        """
        if guise_name not in _GUISE_DEFINITIONS:
            logger.warning(
                "RosetteLens.set_guise: unknown guise %r — defaulting", guise_name
            )
            self._active_guise = "default"
        else:
            self._active_guise = guise_name

    def list_guises(self) -> list[str]:
        """Return the names of all available guise configurations."""
        return list(_GUISE_DEFINITIONS.keys())

    def get_guise_definition(self, guise_name: str) -> dict[str, Any]:
        """Return the definition dict for a named guise (copy)."""
        return dict(_GUISE_DEFINITIONS.get(guise_name, {}))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _derive_guise_from_context(
        self,
        intent: str,
        rosetta_states: list[Any],
    ) -> str:
        """Infer the best guise from intent keywords and agent roles.

        Returns an empty string when no specific override is warranted.
        """
        intent_lower = intent.lower()

        # Keyword-based override
        if any(kw in intent_lower for kw in ("sales", "revenue", "pipeline", "crm")):
            return "sales_focus"
        if any(kw in intent_lower for kw in ("compliance", "audit", "legal", "risk")):
            return "compliance_focus"
        if any(kw in intent_lower for kw in ("grant", "finance", "funding", "runway")):
            return "finance_focus"
        if any(kw in intent_lower for kw in ("research", "study", "analyse", "analyze")):
            return "research_focus"

        # Agent-state majority vote
        role_counts: dict[str, int] = {}
        for state in rosetta_states:
            role = ""
            if isinstance(state, dict):
                role = str(state.get("role", state.get("agent_type", "")))
            else:
                role = str(getattr(state, "role", getattr(state, "agent_type", "")))

            if role:
                role_counts[role] = role_counts.get(role, 0) + 1

        if role_counts:
            dominant_role = max(role_counts, key=lambda r: role_counts[r])
            if "sales" in dominant_role:
                return "sales_focus"
            if "compliance" in dominant_role or "legal" in dominant_role:
                return "compliance_focus"
            if "finance" in dominant_role or "grant" in dominant_role:
                return "finance_focus"
            if "research" in dominant_role:
                return "research_focus"

        return ""

"""
Writing Style / Tone Transformation Layer.

Rewrites structured JSON data into formatted prose in the requested style.
Works fully without an LLM — the deterministic fallback formats JSON into
clean Markdown sections.  The LLM path is an optional enhancement.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style catalogue
# ---------------------------------------------------------------------------

STYLE_PROMPTS: Dict[str, str] = {
    "formal_engineering": (
        "You are a senior engineering consultant producing a formal technical document. "
        "Use precise engineering language, passive voice where appropriate, and maintain "
        "technical accuracy throughout. Reference industry standards where applicable. "
        "Organise content into clearly delineated sections with numbered headings."
    ),
    "executive_summary": (
        "You are a management consultant summarising findings for C-suite executives. "
        "Be concise — no sentence should exceed 25 words. Lead with outcomes and risks. "
        "Avoid jargon; use plain language that a non-technical business leader can act upon. "
        "Bullet-point key decisions required."
    ),
    "technical_manual": (
        "You are a technical writer producing an instructional manual for field engineers. "
        "Use the imperative mood ('Verify…', 'Connect…', 'Record…'). "
        "Present procedures as numbered steps with clear acceptance criteria. "
        "Include safety warnings in ALL CAPS where relevant."
    ),
    "client_facing": (
        "You are writing for a building owner or facilities manager with no engineering background. "
        "Use a warm, professional tone. Explain technical concepts in plain English. "
        "Emphasise the benefits and what the client needs to do or approve. "
        "Avoid acronyms unless they are immediately defined."
    ),
    "academic": (
        "You are an academic researcher writing a technical paper in APA format. "
        "Use formal academic prose, third person, and cite standards where possible "
        "(e.g., ASHRAE Guideline 0-2019). Include an abstract-style opening paragraph. "
        "Support all claims with referenced data from the supplied structured data."
    ),
    "casual": (
        "You are writing a conversational summary for a technically-curious but non-specialist "
        "reader. Be friendly and accessible. Use contractions ('it's', 'we've'). "
        "Break down complex ideas into simple analogies. Keep paragraphs short."
    ),
}

# ---------------------------------------------------------------------------
# Deterministic Markdown formatter (LLM-free fallback)
# ---------------------------------------------------------------------------


def _deterministic_markdown(structured_data: Dict[str, Any], document_type: str) -> str:
    """
    Format *structured_data* into readable Markdown without an LLM.

    Each top-level key becomes an H2 section.  Nested dicts become H3 sub-sections.
    Lists are rendered as bullet lists with sub-fields.
    """
    lines: list[str] = []
    lines.append(f"# {document_type.replace('_', ' ').title()}\n")

    def _render_value(val: Any, depth: int = 0) -> list[str]:
        indent = "  " * depth
        result: list[str] = []
        if isinstance(val, dict):
            for k, v in val.items():
                label = str(k).replace("_", " ").title()
                if isinstance(v, (dict, list)):
                    result.append(f"{indent}- **{label}**:")
                    result.extend(_render_value(v, depth + 1))
                else:
                    result.append(f"{indent}- **{label}**: {v}")
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, dict):
                    result.append(f"{indent}- *Item {i + 1}*")
                    result.extend(_render_value(item, depth + 1))
                else:
                    result.append(f"{indent}- {item}")
        else:
            result.append(f"{indent}{val}")
        return result

    for section_key, section_val in structured_data.items():
        heading = str(section_key).replace("_", " ").title()
        lines.append(f"\n## {heading}\n")
        if isinstance(section_val, dict):
            for k, v in section_val.items():
                label = str(k).replace("_", " ").title()
                if isinstance(v, (dict, list)):
                    lines.append(f"\n### {label}\n")
                    lines.extend(_render_value(v))
                else:
                    lines.append(f"- **{label}**: {v}")
        elif isinstance(section_val, list):
            lines.extend(_render_value(section_val))
        else:
            lines.append(str(section_val))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class DocumentStyleRewriter:
    """
    Rewrites a structured data dictionary into formatted prose.

    * When an LLM client is provided it will call the LLM using the appropriate
      system prompt for the requested style.
    * When no LLM is available (or the call fails) it falls back to the
      deterministic Markdown formatter above.
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        """
        Parameters
        ----------
        llm_client:
            Optional LLM client.  Must expose an async ``complete(system, user)``
            method that returns a string.  If ``None``, deterministic formatting
            is always used.
        """
        self._llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rewrite(
        self,
        structured_data: Dict[str, Any],
        style: str,
        document_type: str,
    ) -> str:
        """
        Rewrite *structured_data* as formatted prose.

        Parameters
        ----------
        structured_data:
            The dict payload to convert (e.g. ``result.plan`` from commissioning bot).
        style:
            One of the keys in :data:`STYLE_PROMPTS` or ``"default"``
            (which maps to ``"formal_engineering"``).
        document_type:
            Human-readable document type used for the document heading and
            any LLM context (e.g. ``"cx_plan_report"``).

        Returns
        -------
        str
            Formatted Markdown (or prose) string.
        """
        style = style or "formal_engineering"
        if style == "default":
            style = "formal_engineering"

        if style not in STYLE_PROMPTS:
            logger.warning("Unknown style '%s'; falling back to 'formal_engineering'.", style)
            style = "formal_engineering"

        # Try LLM path first
        if self._llm is not None:
            try:
                return await self._rewrite_with_llm(structured_data, style, document_type)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM rewrite failed (%s); using deterministic fallback.", exc)

        return _deterministic_markdown(structured_data, document_type)

    def rewrite_sync(
        self,
        structured_data: Dict[str, Any],
        style: str,
        document_type: str,
    ) -> str:
        """Synchronous wrapper around :meth:`rewrite` for non-async callers."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.rewrite(structured_data, style, document_type),
                    )
                    return future.result()
            return loop.run_until_complete(self.rewrite(structured_data, style, document_type))
        except RuntimeError:
            return asyncio.run(self.rewrite(structured_data, style, document_type))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _rewrite_with_llm(
        self,
        structured_data: Dict[str, Any],
        style: str,
        document_type: str,
    ) -> str:
        system_prompt = STYLE_PROMPTS[style]
        user_message = (
            f"Document type: {document_type}\n\n"
            f"Structured data (JSON):\n```json\n"
            f"{json.dumps(structured_data, indent=2, default=str)}\n```\n\n"
            "Using the style described in the system prompt, produce a well-formatted "
            "Markdown document from this structured data.  Do not add information that "
            "is not present in the supplied data."
        )
        return await self._llm.complete(system=system_prompt, user=user_message)

    @staticmethod
    def available_styles() -> list[str]:
        """Return the list of built-in style names."""
        return list(STYLE_PROMPTS.keys())

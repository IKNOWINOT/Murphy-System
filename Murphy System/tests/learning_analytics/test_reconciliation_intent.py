"""
Tests for the IntentExtractor — clear vs vague handling, ambiguity
vector, deterministic fallback, and the LLM-backed code path with a
stub adapter.
"""

from __future__ import annotations

import json
from typing import Any

from src.reconciliation import (
    AmbiguityVector,
    DeliverableType,
    IntentExtractor,
    Request,
)


def test_clear_request_yields_single_high_confidence_spec() -> None:
    req = Request(
        text="Generate a Python function that returns the factorial of n",
        deliverable_type=DeliverableType.CODE,
    )
    specs = IntentExtractor().extract(req)
    assert len(specs) == 1
    assert specs[0].confidence >= 0.85
    assert specs[0].deliverable_type == DeliverableType.CODE
    assert specs[0].acceptance_criteria, "must inherit standards-derived criteria"


def test_vague_request_yields_multiple_candidates_and_ambiguity() -> None:
    req = Request(text="make it nicer")
    ext = IntentExtractor()
    assert ext.is_vague(req)
    specs = ext.extract(req)
    assert len(specs) >= 2  # primary + at least one alternative deliverable type
    primary = specs[0]
    assert primary.ambiguity.is_ambiguous
    # Confidence on the primary must be lower than for a clear request.
    assert primary.confidence < 0.85


def test_ambiguity_vector_enumerates_under_specified_dimensions() -> None:
    req = Request(text="do it")
    av = IntentExtractor().ambiguity_vector(req)
    # Vague single-clause should be missing virtually every dimension.
    assert "audience" in av.items
    assert "scope / boundaries" in av.items
    assert "acceptance criteria" in av.items


def test_extractor_max_candidates_is_respected() -> None:
    ext = IntentExtractor(max_candidates=1)
    specs = ext.extract(Request(text="thing"))
    assert len(specs) == 1


def test_extractor_with_callable_llm_adapter() -> None:
    """A callable returning a JSON envelope should drive the LLM path."""

    def fake_llm(prompt: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "candidates": [
                    {
                        "summary": "Generate a deployment script",
                        "deliverable_type": "shell_script",
                        "confidence": 0.92,
                        "criteria": [
                            {"description": "Uses set -euo pipefail", "weight": 1.0, "hard": True},
                            {"description": "Logs every step", "weight": 0.5, "hard": False},
                        ],
                        "soft_preferences": ["bash"],
                        "success_exemplars": [],
                        "failure_exemplars": [],
                        "ambiguity": [],
                    }
                ]
            }
        )

    req = Request(text="write me a deployment script", deliverable_type=DeliverableType.SHELL_SCRIPT)
    ext = IntentExtractor(llm_adapter=fake_llm)
    specs = ext.extract(req)
    assert len(specs) == 1
    spec = specs[0]
    assert spec.confidence == 0.92
    assert spec.deliverable_type == DeliverableType.SHELL_SCRIPT
    assert any("set -euo" in c.description for c in spec.acceptance_criteria)


def test_extractor_falls_back_when_llm_returns_garbage() -> None:
    def broken_llm(prompt: str) -> str:  # noqa: ARG001
        return "this is not json at all"

    specs = IntentExtractor(llm_adapter=broken_llm).extract(
        Request(
            text="Write the user manual for the support team.",
            deliverable_type=DeliverableType.DOCUMENT,
        )
    )
    assert len(specs) == 1  # deterministic fallback for a clear request
    assert specs[0].deliverable_type == DeliverableType.DOCUMENT


def test_extractor_falls_back_when_llm_raises() -> None:
    def raising_llm(prompt: str) -> str:  # noqa: ARG001
        raise RuntimeError("boom")

    specs = IntentExtractor(llm_adapter=raising_llm).extract(
        Request(text="hello world")
    )
    assert len(specs) >= 1


def test_soft_preferences_extracted_from_request_text() -> None:
    req = Request(text="Build the dashboard. Should support dark mode.")
    spec = IntentExtractor().extract(req)[0]
    assert any("dark mode" in p for p in spec.soft_preferences)


def test_intent_includes_literal_request_rubric_criterion() -> None:
    req = Request(text="produce X")
    spec = IntentExtractor().extract(req)[0]
    assert any(
        "satisfies the literal request" in c.description.lower()
        for c in spec.acceptance_criteria
    )

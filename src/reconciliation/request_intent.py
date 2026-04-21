"""
Request → :class:`IntentSpec` extraction.

For *clear* requests the extractor returns a single high-confidence
intent spec.  For *vague* requests it returns multiple candidate intent
specs along with an :class:`AmbiguityVector` enumerating exactly what is
under-specified — that vector is later turned into clarifying questions
by the controller, instead of guessing forever.

The extractor is LLM-backed when available (via the existing
:class:`src.ml.copilot_adapter.CopilotAdapter`), and falls back to a
fully-deterministic, dependency-free heuristic so this module is always
testable in CI and during local development.

Design label: RECON-INTENT-001
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .intent_classifier import IntentClassifier, IntentClassifierError, IntentPrediction
from .models import (
    AcceptanceCriterion,
    AmbiguityVector,
    CriterionKind,
    DeliverableType,
    IntentSpec,
    Request,
)
from .standards import StandardsCatalog, default_catalog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vagueness signals — used by the deterministic fallback.
# ---------------------------------------------------------------------------

_VAGUE_TOKENS = (
    "something", "somehow", "stuff", "things", "etc", "and so on",
    "make it better", "make it nicer", "tidy it up", "fix it",
    "make it work", "improve it", "polish", "clean it up", "as needed",
)
_HEDGE_TOKENS = (
    "maybe", "perhaps", "kind of", "sort of", "ish", "or so", "more or less",
)
_PRONOUN_REFERENCES = re.compile(r"\b(it|that|those|this|these)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _LLMResponse:
    summary: str
    deliverable_type: DeliverableType
    confidence: float
    criteria: List[AcceptanceCriterion]
    soft_preferences: List[str]
    success_exemplars: List[str]
    failure_exemplars: List[str]
    ambiguity: List[str]


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------


class IntentExtractor:
    """Convert a free-form :class:`Request` into one or more :class:`IntentSpec`s.

    Args:
        catalog: Standards catalog whose entries seed the acceptance
            criteria for the inferred deliverable type.  Defaults to the
            process-wide :func:`standards.default_catalog`.
        llm_adapter: Optional callable ``(prompt: str) -> str`` used as
            an LLM backend.  If omitted, the deterministic fallback is
            used.  The adapter is intentionally untyped so the existing
            :class:`CopilotAdapter` (or any custom function) can be
            injected without coupling.
        max_candidates: Upper bound on the number of intent specs
            returned for a single vague request.
    """

    def __init__(
        self,
        catalog: Optional[StandardsCatalog] = None,
        llm_adapter: Optional[Any] = None,
        max_candidates: int = 3,
        classifier: Optional[IntentClassifier] = None,
        classifier_min_confidence: float = 0.20,
    ) -> None:
        if max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        if not 0.0 <= classifier_min_confidence <= 1.0:
            raise ValueError(
                "classifier_min_confidence must be in [0.0, 1.0] "
                f"(got {classifier_min_confidence})"
            )
        self._catalog = catalog or default_catalog()
        self._llm = llm_adapter
        self._max_candidates = max_candidates
        # Optional ML classifier — used only as a non-LLM hint when the
        # caller hasn't pinned a deliverable type or has left it as the
        # GENERIC_TEXT default.  Failures here are NEVER silent: if the
        # classifier is supplied and raises, we surface the exception.
        self._classifier = classifier
        self._classifier_min_confidence = classifier_min_confidence

    # ------------------------------------------------------------------
    # Vagueness detection
    # ------------------------------------------------------------------

    def is_vague(self, request: Request) -> bool:
        """Heuristic vagueness detector — fast and dependency-free."""
        text = request.text.strip()
        if len(text) < 12:
            return True

        lowered = text.lower()
        if any(tok in lowered for tok in _VAGUE_TOKENS):
            return True
        if any(tok in lowered for tok in _HEDGE_TOKENS):
            return True

        # Pure pronoun references with no nouns are vague.
        words = re.findall(r"[A-Za-z']+", text)
        if words and all(w.lower() in {"it", "that", "this", "those", "these"} for w in words):
            return True
        if _PRONOUN_REFERENCES.search(text) and len(words) < 5:
            return True

        return False

    def ambiguity_vector(self, request: Request) -> AmbiguityVector:
        """Enumerate the under-specified dimensions of *request*."""
        items: List[str] = []
        text = request.text.lower()

        # Heuristic dimensions we consistently check.
        dimensions = (
            ("audience", ("for ", "audience", "user", "customer")),
            ("output format", ("format", "as a", "as an", "json", "yaml", "markdown")),
            ("scope / boundaries", ("scope", "limit", "only", "include", "exclude")),
            ("acceptance criteria", ("must", "should", "required", "criteria")),
            ("deadline / urgency", ("by ", "deadline", "urgent", "asap")),
            ("environment / target", ("env", "environment", "prod", "staging", "dev", "target")),
        )
        for label, signals in dimensions:
            if not any(s in text for s in signals):
                items.append(label)

        if request.deliverable_type == DeliverableType.GENERIC_TEXT:
            items.append("deliverable type")

        return AmbiguityVector(items=items)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract(self, request: Request) -> List[IntentSpec]:
        """Return one or more candidate :class:`IntentSpec`s for *request*."""
        llm_specs = self._extract_with_llm(request) if self._llm else []
        if llm_specs:
            return llm_specs[: self._max_candidates]

        # Deterministic fallback.  If a classifier is configured AND the
        # caller hasn't pinned a specific deliverable type (i.e. they
        # accepted the GENERIC_TEXT default), consult it.  The
        # classifier is *advisory* — we override the deliverable type
        # only when its confidence clears the configured floor.
        chosen_type = request.deliverable_type
        classifier_pred = self._classify_or_none(request)
        if (
            request.deliverable_type == DeliverableType.GENERIC_TEXT
            and classifier_pred is not None
            and classifier_pred.confidence >= self._classifier_min_confidence
        ):
            chosen_type = classifier_pred.deliverable_type

        primary = self._build_spec(
            request,
            summary=self._summarise(request.text),
            deliverable_type=chosen_type,
            confidence=0.5 if self.is_vague(request) else 0.9,
        )
        if not self.is_vague(request):
            return [primary]

        # Vague request: emit primary + alternative deliverable-type guesses.
        # Prefer classifier ranking when available; fall back to keyword
        # heuristics otherwise.
        alternatives: List[IntentSpec] = [primary]
        seen = {chosen_type}
        alt_iter: Sequence[DeliverableType]
        if classifier_pred is not None and classifier_pred.token_count > 0:
            alt_iter = tuple(
                cls for cls, _ in classifier_pred.ranking
                if cls != chosen_type
            )
        else:
            alt_iter = self._guess_alt_types(request)
        for alt_type in alt_iter:
            if len(alternatives) >= self._max_candidates:
                break
            if alt_type in seen:
                continue
            seen.add(alt_type)
            alternatives.append(
                self._build_spec(
                    request,
                    summary=f"Interpretation as {alt_type.value}",
                    deliverable_type=alt_type,
                    confidence=0.25,
                )
            )
        return alternatives[: self._max_candidates]

    def _classify_or_none(self, request: Request) -> Optional[IntentPrediction]:
        """Run the classifier defensively.

        Returns ``None`` if no classifier is configured.  If the
        classifier raises an unexpected error we log loudly and return
        ``None`` — we never let an advisory subsystem break extraction —
        but the typed :class:`IntentClassifierError` is re-raised so
        configuration bugs surface during tests rather than degrading
        silently in production.
        """
        if self._classifier is None:
            return None
        try:
            return self._classifier.predict(request.text)
        except IntentClassifierError:
            # Configuration / state bug — must not be silent.
            raise
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "IntentExtractor classifier raised %s; ignoring this advisory "
                "and falling back to keyword heuristics", exc,
            )
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_spec(
        self,
        request: Request,
        *,
        summary: str,
        deliverable_type: DeliverableType,
        confidence: float,
    ) -> IntentSpec:
        criteria: List[AcceptanceCriterion] = [
            std.to_criterion() for std in self._catalog.for_type(deliverable_type)
        ]
        # Always include a rubric-style criterion mirroring the literal
        # request — gives the LLM judge a target even with no standards.
        criteria.append(
            AcceptanceCriterion(
                description="Deliverable satisfies the literal request",
                kind=CriterionKind.LLM_RUBRIC,
                weight=2.0,
                hard=False,
                rubric=(
                    "Score 0..1 how completely the deliverable answers the "
                    f"following request: '{request.text.strip()}'.  "
                    "Penalise missing requirements, off-topic content, and "
                    "departures from above-average professional best "
                    "practices for the relevant domain."
                ),
                check_spec={"source": "literal_request"},
            )
        )
        return IntentSpec(
            request_id=request.id,
            summary=summary,
            deliverable_type=deliverable_type,
            confidence=confidence,
            acceptance_criteria=criteria,
            soft_preferences=self._extract_preferences(request.text),
            ambiguity=self.ambiguity_vector(request),
        )

    @staticmethod
    def _summarise(text: str) -> str:
        text = text.strip()
        if len(text) <= 80:
            return text
        return text[:77].rstrip() + "..."

    @staticmethod
    def _extract_preferences(text: str) -> List[str]:
        """Pull out 'should', 'prefer', 'nice to have' clauses."""
        prefs: List[str] = []
        for marker in ("should ", "prefer ", "nice to have", "ideally "):
            idx = text.lower().find(marker)
            if idx >= 0:
                # Take up to the next sentence boundary.
                end = len(text)
                for boundary in (".", "\n", ";"):
                    b = text.find(boundary, idx)
                    if b != -1:
                        end = min(end, b)
                prefs.append(text[idx:end].strip())
        return prefs

    @staticmethod
    def _guess_alt_types(request: Request) -> Sequence[DeliverableType]:
        text = request.text.lower()
        guesses: List[DeliverableType] = []
        if any(k in text for k in ("script", "bash", "shell", ".sh")):
            guesses.append(DeliverableType.SHELL_SCRIPT)
        if any(k in text for k in ("config", "yaml", "json", ".env", "settings")):
            guesses.append(DeliverableType.CONFIG_FILE)
        if any(k in text for k in ("doc", "readme", "guide", "manual")):
            guesses.append(DeliverableType.DOCUMENT)
        if any(k in text for k in ("plan", "roadmap", "checklist", "steps")):
            guesses.append(DeliverableType.PLAN)
        if not guesses:
            guesses = [DeliverableType.DOCUMENT, DeliverableType.PLAN]
        return guesses

    # ------------------------------------------------------------------
    # LLM-backed extraction (best-effort; failures fall back silently).
    # ------------------------------------------------------------------

    def _extract_with_llm(self, request: Request) -> List[IntentSpec]:
        """Try the configured LLM adapter; return [] on any failure."""
        if self._llm is None:
            return []
        try:
            prompt = self._build_llm_prompt(request)
            raw = self._invoke_llm(prompt)
            if not raw:
                return []
            parsed = self._parse_llm_response(raw)
        except Exception as exc:  # pragma: no cover — defensive
            logger.info("IntentExtractor LLM path failed (%s); using fallback", exc)
            return []

        specs: List[IntentSpec] = []
        for resp in parsed:
            base = self._build_spec(
                request,
                summary=resp.summary or self._summarise(request.text),
                deliverable_type=resp.deliverable_type,
                confidence=resp.confidence,
            )
            # Augment with LLM-supplied criteria + exemplars.
            base.acceptance_criteria.extend(resp.criteria)
            base.soft_preferences.extend(resp.soft_preferences)
            base.success_exemplars.extend(resp.success_exemplars)
            base.failure_exemplars.extend(resp.failure_exemplars)
            if resp.ambiguity:
                base.ambiguity = AmbiguityVector(items=resp.ambiguity)
            specs.append(base)
        return specs

    def _build_llm_prompt(self, request: Request) -> str:
        return (
            "You are extracting a structured intent specification from a user "
            "request.  Respond as JSON of shape:\n"
            '{"candidates": [{"summary": "...", "deliverable_type": "...", '
            '"confidence": 0.0..1.0, "criteria": [{"description": "...", '
            '"hard": true|false, "weight": 0..10}], "soft_preferences": [], '
            '"success_exemplars": [], "failure_exemplars": [], "ambiguity": []}]}\n\n'
            "Allowed deliverable_type values: "
            f"{', '.join(t.value for t in DeliverableType)}\n\n"
            f"Request: {request.text.strip()!r}\n"
            f"Hint deliverable_type from caller: {request.deliverable_type.value}"
        )

    def _invoke_llm(self, prompt: str) -> str:
        if callable(self._llm):
            return str(self._llm(prompt) or "")
        # Duck-typing: if it looks like CopilotAdapter, use its .generate()
        # path — we do NOT depend on it at import time.
        generate = getattr(self._llm, "generate", None)
        if callable(generate):
            try:
                from src.ml.copilot_adapter import CopilotRequest  # type: ignore
                result = generate(CopilotRequest(prompt=prompt))
                return getattr(result, "explanation", "") or getattr(result, "generated_code", "")
            except Exception:
                return ""
        return ""

    @staticmethod
    def _parse_llm_response(raw: str) -> List[_LLMResponse]:
        import json as _json
        # Be liberal: find the first JSON object in the string.
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            data = _json.loads(raw[start : end + 1])
        except _json.JSONDecodeError:
            return []
        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            return []

        out: List[_LLMResponse] = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            try:
                dtype = DeliverableType(c.get("deliverable_type", DeliverableType.GENERIC_TEXT.value))
            except ValueError:
                dtype = DeliverableType.GENERIC_TEXT
            criteria_in = c.get("criteria") or []
            criteria_out: List[AcceptanceCriterion] = []
            for entry in criteria_in:
                if not isinstance(entry, dict):
                    continue
                desc = entry.get("description", "").strip()
                if not desc:
                    continue
                criteria_out.append(
                    AcceptanceCriterion(
                        description=desc,
                        kind=CriterionKind.LLM_RUBRIC,
                        weight=float(entry.get("weight", 1.0) or 1.0),
                        hard=bool(entry.get("hard", False)),
                        rubric=f"Score 0..1 how well the deliverable satisfies: {desc}",
                    )
                )
            out.append(
                _LLMResponse(
                    summary=str(c.get("summary", "")).strip(),
                    deliverable_type=dtype,
                    confidence=float(c.get("confidence", 0.5) or 0.5),
                    criteria=criteria_out,
                    soft_preferences=[
                        str(p) for p in (c.get("soft_preferences") or []) if isinstance(p, str)
                    ],
                    success_exemplars=[
                        str(p) for p in (c.get("success_exemplars") or []) if isinstance(p, str)
                    ],
                    failure_exemplars=[
                        str(p) for p in (c.get("failure_exemplars") or []) if isinstance(p, str)
                    ],
                    ambiguity=[
                        str(p) for p in (c.get("ambiguity") or []) if isinstance(p, str)
                    ],
                )
            )
        return out


__all__ = ["IntentExtractor"]

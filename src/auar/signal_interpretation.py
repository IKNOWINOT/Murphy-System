"""
AUAR Layer 1 — Signal Interpretation Layer
============================================

Parses incoming requests and extracts intent with high confidence using
a hybrid deterministic + ML approach.  Structured API calls (REST,
GraphQL, gRPC) are handled via fast deterministic parsing; natural-
language or ambiguous requests fall back to an LLM-based interpreter.

A weighted confidence scorer decides the processing path:
    confidence = 0.4*schema + 0.3*history + 0.2*semantic + 0.1*completeness

Thresholds:
    >0.85  → direct route
    0.60–0.85 → validation pass
    <0.60  → clarification required

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RequestContext:
    """Contextual metadata attached to every inbound request."""
    user_id: str = ""
    tenant_id: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_ip: str = ""
    session_id: str = ""


@dataclass
class CapabilityIntent:
    """A resolved capability that the request maps to."""
    capability_name: str
    domain: str = ""
    category: str = ""
    version: str = "1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentSignal:
    """Complete output of the Signal Interpretation Layer."""
    request_id: str = field(default_factory=lambda: str(uuid4()))
    raw_request: Dict[str, Any] = field(default_factory=dict)
    parsed_intent: Optional[CapabilityIntent] = None
    confidence_score: float = 0.0
    confidence_factors: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: RequestContext = field(default_factory=RequestContext)
    alternatives: List[CapabilityIntent] = field(default_factory=list)
    requires_clarification: bool = False
    interpretation_method: str = "deterministic"
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Confidence scorer
# ---------------------------------------------------------------------------

class ConfidenceScorer:
    """Multi-factor confidence assessment for intent signals.

    Weights (configurable):
        schema_match  : 0.40
        history_match : 0.30
        semantic_match: 0.20
        completeness  : 0.10
    """

    DEFAULT_WEIGHTS = {
        "schema": 0.40,
        "history": 0.30,
        "semantic": 0.20,
        "completeness": 0.10,
    }

    THRESHOLD_DIRECT = 0.85
    THRESHOLD_VALIDATE = 0.60

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

    def score(
        self,
        schema_match: float = 0.0,
        history_match: float = 0.0,
        semantic_match: float = 0.0,
        completeness: float = 0.0,
    ) -> float:
        """Return a weighted confidence score in [0, 1]."""
        raw = (
            self.weights["schema"] * schema_match
            + self.weights["history"] * history_match
            + self.weights["semantic"] * semantic_match
            + self.weights["completeness"] * completeness
        )
        return max(0.0, min(1.0, raw))

    def factors(
        self,
        schema_match: float = 0.0,
        history_match: float = 0.0,
        semantic_match: float = 0.0,
        completeness: float = 0.0,
    ) -> Dict[str, float]:
        """Return individual factor contributions."""
        return {
            "schema": schema_match,
            "history": history_match,
            "semantic": semantic_match,
            "completeness": completeness,
        }

    def needs_clarification(self, score: float) -> bool:
        return score < self.THRESHOLD_VALIDATE

    def needs_validation(self, score: float) -> bool:
        return self.THRESHOLD_VALIDATE <= score < self.THRESHOLD_DIRECT

    def can_direct_route(self, score: float) -> bool:
        return score >= self.THRESHOLD_DIRECT


# ---------------------------------------------------------------------------
# Capability schema registry (lightweight in-memory)
# ---------------------------------------------------------------------------

@dataclass
class _SchemaEntry:
    capability_name: str
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    domain: str = ""
    category: str = ""


# ---------------------------------------------------------------------------
# Signal Interpreter – main entry point
# ---------------------------------------------------------------------------

class SignalInterpreter:
    """Layer 1 facade: accepts raw requests and emits ``IntentSignal``s.

    Deterministic path is attempted first.  If confidence falls below the
    configurable threshold the interpreter can optionally invoke an LLM
    backend (pluggable via ``llm_backend`` callback).
    """

    def __init__(
        self,
        llm_backend=None,
        confidence_scorer: Optional[ConfidenceScorer] = None,
        llm_confidence_threshold: float = 0.80,
    ):
        self._schemas: Dict[str, _SchemaEntry] = {}
        self._history: Dict[str, str] = {}   # raw_key → capability_name
        self._lock = threading.Lock()
        self._scorer = confidence_scorer or ConfidenceScorer()
        self._llm_backend = llm_backend
        self._llm_threshold = llm_confidence_threshold
        self._stats = {"total": 0, "deterministic": 0, "llm": 0, "clarification": 0}

    # -- Schema management --------------------------------------------------

    def register_schema(
        self,
        capability_name: str,
        required_params: Optional[List[str]] = None,
        optional_params: Optional[List[str]] = None,
        domain: str = "",
        category: str = "",
    ) -> None:
        """Register a capability schema for deterministic matching."""
        with self._lock:
            self._schemas[capability_name] = _SchemaEntry(
                capability_name=capability_name,
                required_params=required_params or [],
                optional_params=optional_params or [],
                domain=domain,
                category=category,
            )

    # -- Core interpretation ------------------------------------------------

    def interpret(
        self,
        raw_request: Dict[str, Any],
        context: Optional[RequestContext] = None,
    ) -> IntentSignal:
        """Interpret *raw_request* and return an ``IntentSignal``."""
        start = time.monotonic()
        ctx = context or RequestContext()

        signal = IntentSignal(
            raw_request=raw_request,
            context=ctx,
        )

        # --- Step 1: deterministic parsing ---
        det_intent, det_score, det_factors = self._deterministic_parse(raw_request)

        if det_score >= self._llm_threshold:
            signal.parsed_intent = det_intent
            signal.confidence_score = det_score
            signal.confidence_factors = det_factors
            signal.parameters = det_intent.parameters if det_intent else {}
            signal.interpretation_method = "deterministic"
        elif self._llm_backend is not None:
            # --- Step 2: LLM fallback ---
            llm_intent, llm_score, llm_factors = self._llm_parse(raw_request)
            if llm_score > det_score:
                signal.parsed_intent = llm_intent
                signal.confidence_score = llm_score
                signal.confidence_factors = llm_factors
                signal.parameters = llm_intent.parameters if llm_intent else {}
                signal.interpretation_method = "llm"
            else:
                signal.parsed_intent = det_intent
                signal.confidence_score = det_score
                signal.confidence_factors = det_factors
                signal.parameters = det_intent.parameters if det_intent else {}
                signal.interpretation_method = "deterministic"
        else:
            signal.parsed_intent = det_intent
            signal.confidence_score = det_score
            signal.confidence_factors = det_factors
            signal.parameters = det_intent.parameters if det_intent else {}
            signal.interpretation_method = "deterministic"

        # --- Step 3: threshold evaluation ---
        if self._scorer.needs_clarification(signal.confidence_score):
            signal.requires_clarification = True

        # --- Step 3b: ambiguity resolution ---
        # When confidence is in the validation range (0.60–0.85), generate
        # ranked alternative interpretations for downstream disambiguation.
        if self._scorer.needs_validation(signal.confidence_score):
            signal.alternatives = self._resolve_ambiguity(raw_request, signal)

        # Record history for future pattern matching
        self._record_history(raw_request, signal)

        signal.latency_ms = (time.monotonic() - start) * 1000
        self._update_stats(signal)
        return signal

    # -- Deterministic parsing ----------------------------------------------

    def _deterministic_parse(self, raw: Dict[str, Any]):
        """Try to match the request against registered schemas."""
        capability = raw.get("capability") or raw.get("action") or raw.get("intent")
        params = raw.get("parameters") or raw.get("params") or raw.get("data") or {}

        # GraphQL support: extract capability from query field
        if not capability and "query" in raw:
            capability = self._parse_graphql(raw["query"])
            if not params and "variables" in raw:
                params = raw["variables"]

        if not capability:
            # Attempt path-based matching for REST-style requests
            path = raw.get("path", "")
            method = raw.get("method", "").upper()
            capability = self._match_path(path, method)

        if not capability:
            return None, 0.0, self._scorer.factors()

        schema_match = 0.0
        history_match = 0.0
        completeness = 0.0

        with self._lock:
            entry = self._schemas.get(capability)

        if entry:
            # Schema match score
            schema_match = 1.0
            # Parameter completeness
            if entry.required_params:
                present = sum(1 for p in entry.required_params if p in params)
                completeness = present / (len(entry.required_params) or 1)
            else:
                completeness = 1.0 if capability else 0.0

            intent = CapabilityIntent(
                capability_name=capability,
                domain=entry.domain,
                category=entry.category,
                parameters=params,
            )
        else:
            # Unknown capability – still return it with low confidence
            intent = CapabilityIntent(
                capability_name=capability,
                parameters=params,
            )
            completeness = 0.5

        # History match
        raw_key = self._request_key(raw)
        with self._lock:
            if raw_key in self._history:
                history_match = 1.0 if self._history[raw_key] == capability else 0.3

        score = self._scorer.score(
            schema_match=schema_match,
            history_match=history_match,
            semantic_match=schema_match * 0.8,  # proxy for semantic
            completeness=completeness,
        )
        factors = self._scorer.factors(
            schema_match=schema_match,
            history_match=history_match,
            semantic_match=schema_match * 0.8,
            completeness=completeness,
        )
        return intent, score, factors

    def _match_path(self, path: str, method: str) -> Optional[str]:
        """Naive REST path → capability matcher."""
        segments = [s for s in path.strip("/").split("/") if s]
        if not segments:
            return None
        # Convention: /api/<capability> or /v1/<capability>
        cap = segments[-1].replace("-", "_")
        with self._lock:
            if cap in self._schemas:
                return cap
        return None

    def _parse_graphql(self, query: str) -> Optional[str]:
        """Extract capability name from a GraphQL query/mutation string."""
        import re
        # Match named operations: mutation sendEmail(...) or query sendEmail(...)
        m = re.search(r'(?:mutation|query)\s+(\w+)', query)
        if m:
            cap = m.group(1)
            # Convert camelCase to snake_case
            cap = re.sub(r'(?<!^)(?=[A-Z])', '_', cap).lower()
            with self._lock:
                if cap in self._schemas:
                    return cap
        # Fallback for anonymous operations: match field names inside braces
        # e.g., query { listUsers { id } } → extract "listUsers"
        brace_match = re.search(r'\{\s*(\w+)', query)
        if brace_match:
            cap = brace_match.group(1)
            cap = re.sub(r'(?<!^)(?=[A-Z])', '_', cap).lower()
            with self._lock:
                if cap in self._schemas:
                    return cap
        # Final fallback: word-boundary match for registered capability names
        with self._lock:
            for name in self._schemas:
                # Use word boundary to avoid partial substring matches
                pattern = r'\b' + re.escape(name.replace("_", "")) + r'\b'
                if re.search(pattern, query, re.IGNORECASE):
                    return name
        return None

    # -- LLM fallback -------------------------------------------------------

    def _llm_parse(self, raw: Dict[str, Any]):
        """Invoke pluggable LLM backend for intent interpretation."""
        try:
            result = self._llm_backend(raw)  # type: ignore[misc]
            capability = result.get("capability", "")
            params = result.get("parameters", {})
            confidence = float(result.get("confidence", 0.5))
            intent = CapabilityIntent(
                capability_name=capability,
                parameters=params,
            )
            factors = self._scorer.factors(
                schema_match=0.0,
                history_match=0.0,
                semantic_match=confidence,
                completeness=confidence * 0.8,
            )
            score = self._scorer.score(
                semantic_match=confidence,
                completeness=confidence * 0.8,
            )
            return intent, score, factors
        except Exception as exc:
            logger.warning("LLM backend failed: %s – falling back", exc)
            return None, 0.0, self._scorer.factors()

    # -- Ambiguity resolution -----------------------------------------------

    def _resolve_ambiguity(
        self, raw: Dict[str, Any], signal: IntentSignal
    ) -> List[CapabilityIntent]:
        """Generate ranked alternative interpretations.

        Called when confidence falls in the validation range (0.60–0.85).
        Returns up to 3 alternative capability intents ordered by estimated
        relevance.
        """
        alternatives: List[CapabilityIntent] = []
        primary_name = (
            signal.parsed_intent.capability_name if signal.parsed_intent else ""
        )
        params = raw.get("parameters") or raw.get("params") or raw.get("data") or {}

        with self._lock:
            for name, entry in self._schemas.items():
                if name == primary_name:
                    continue
                # Score each alternative by keyword overlap
                score = 0.0
                raw_text = " ".join(str(v) for v in raw.values())
                for tag in [entry.domain, entry.category, name]:
                    if tag and tag.lower() in raw_text.lower():
                        score += 0.3
                if score > 0:
                    alternatives.append(
                        CapabilityIntent(
                            capability_name=name,
                            domain=entry.domain,
                            category=entry.category,
                            parameters=params,
                        )
                    )
                if len(alternatives) >= 3:
                    break
        return alternatives

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _request_key(raw: Dict[str, Any]) -> str:
        cap = raw.get("capability") or raw.get("action") or raw.get("path") or ""
        return str(cap).lower().strip()

    def _record_history(self, raw: Dict[str, Any], signal: IntentSignal) -> None:
        if signal.parsed_intent:
            key = self._request_key(raw)
            with self._lock:
                self._history[key] = signal.parsed_intent.capability_name

    def _update_stats(self, signal: IntentSignal) -> None:
        with self._lock:
            self._stats["total"] += 1
            if signal.requires_clarification:
                self._stats["clarification"] += 1
            elif signal.interpretation_method == "llm":
                self._stats["llm"] += 1
            else:
                self._stats["deterministic"] += 1

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

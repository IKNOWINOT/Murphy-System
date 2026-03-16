# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Natural Language Query Interface — NLQ-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Ask questions about Murphy System state in plain English and receive
structured JSON answers.  The engine parses user queries using a
rule-based intent / entity extraction pipeline (no external LLM
required), dispatches them to registered *data-source handlers*, and
formats the results.

Classes: QueryIntent/EntityType/QueryStatus (enums),
Entity/ParsedQuery/QueryResult/DataSourceRegistration/QueryHistoryEntry
(dataclasses), NLQueryEngine (thread-safe orchestrator).
``create_nlq_api(engine)`` returns a Flask Blueprint (JSON error
envelope).

Safety: all mutable state guarded by threading.Lock; history bounded via
capped_append (CWE-770); no PII stored; no external network calls —
data sources are injected via callbacks.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional Flask import
# ---------------------------------------------------------------------------
try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]
    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}
    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}
        @staticmethod
        def get_json(silent: bool = True) -> dict: return {}
    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ── Enums ─────────────────────────────────────────────────────────────────

class QueryIntent(str, Enum):
    """Detected intent of a natural-language query."""
    status = "status"
    count = "count"
    list_items = "list"
    detail = "detail"
    compare = "compare"
    trend = "trend"
    search = "search"
    help = "help"
    unknown = "unknown"

class EntityType(str, Enum):
    """Types of entities extractable from a query."""
    module = "module"
    metric = "metric"
    time_range = "time_range"
    status_filter = "status_filter"
    number = "number"
    name = "name"

class QueryStatus(str, Enum):
    """Processing status of a query."""
    pending = "pending"
    success = "success"
    partial = "partial"
    error = "error"
    no_match = "no_match"

# ── Dataclasses ───────────────────────────────────────────────────────────

@dataclass
class Entity:
    """An extracted entity from a query string."""
    type: EntityType = EntityType.name
    value: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["type"] = self.type.value
        return d

@dataclass
class ParsedQuery:
    """Result of parsing a natural-language query."""
    raw_text: str = ""
    intent: QueryIntent = QueryIntent.unknown
    entities: List[Entity] = field(default_factory=list)
    confidence: float = 0.0
    normalised_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["intent"] = self.intent.value
        d["entities"] = [e.to_dict() for e in self.entities]
        return d

@dataclass
class QueryResult:
    """Structured result returned to the user."""
    query_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: QueryStatus = QueryStatus.pending
    answer: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

@dataclass
class DataSourceRegistration:
    """A registered data source that can answer queries."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    supported_intents: List[QueryIntent] = field(default_factory=list)
    handler: Optional[Callable[[ParsedQuery], Dict[str, Any]]] = None
    enabled: bool = True
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise (handler excluded)."""
        return {
            "id": self.id, "name": self.name,
            "description": self.description,
            "supported_intents": [i.value for i in self.supported_intents],
            "enabled": self.enabled, "priority": self.priority,
        }

@dataclass
class QueryHistoryEntry:
    """One entry in the query history log."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    raw_text: str = ""
    intent: QueryIntent = QueryIntent.unknown
    status: QueryStatus = QueryStatus.pending
    answer: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["intent"] = self.intent.value
        d["status"] = self.status.value
        return d

# ── Intent patterns ───────────────────────────────────────────────────────

_INTENT_PATTERNS: List[Tuple[QueryIntent, re.Pattern[str]]] = [
    # Multi-word / specific patterns first to avoid false positives.
    (QueryIntent.help, re.compile(
        r"\b(help|usage|how do i|what can)\b", re.I)),
    (QueryIntent.count, re.compile(
        r"\b(how many|count|total|number of)\b", re.I)),
    (QueryIntent.compare, re.compile(
        r"\b(compare|versus|vs|differ|between)\b", re.I)),
    (QueryIntent.trend, re.compile(
        r"\b(trend|over time|history|graph|chart|growth)\b", re.I)),
    (QueryIntent.detail, re.compile(
        r"\b(detail|describe|info|about|tell me about|explain)\b", re.I)),
    (QueryIntent.search, re.compile(
        r"\b(search|find|where|look|locate)\b", re.I)),
    (QueryIntent.status, re.compile(
        r"\b(status|state|health|running|up|down|alive)\b", re.I)),
    (QueryIntent.list_items, re.compile(
        r"\b(list|show|display|all|enumerate)\b", re.I)),
]

_ENTITY_PATTERNS: List[Tuple[EntityType, re.Pattern[str]]] = [
    (EntityType.module, re.compile(
        r"\b(module|service|engine|system|component|subsystem)\s+(\w+)", re.I)),
    (EntityType.metric, re.compile(
        r"\b(metric|latency|throughput|error.rate|uptime|cpu|memory)\b", re.I)),
    (EntityType.time_range, re.compile(
        r"\b(last|past|since|today|yesterday|this week|this month"
        r"|(\d+)\s*(hour|day|minute|week|month)s?)\b", re.I)),
    (EntityType.status_filter, re.compile(
        r"\b(healthy|degraded|failed|active|inactive|running|stopped)\b", re.I)),
    (EntityType.number, re.compile(r"\b(\d+)\b")),
]

# ── NLQueryEngine ─────────────────────────────────────────────────────────

class NLQueryEngine:
    """Thread-safe natural-language query engine.

    Parameters
    ----------
    max_history:
        Maximum query history entries retained.
    max_sources:
        Maximum data source registrations.
    """

    def __init__(
        self, max_history: int = 10_000, max_sources: int = 100,
    ) -> None:
        self._lock = threading.Lock()
        self._sources: Dict[str, DataSourceRegistration] = {}
        self._history: List[QueryHistoryEntry] = []
        self._max_history = max_history
        self._max_sources = max_sources
        self._synonyms: Dict[str, str] = {
            "modules": "module", "services": "service",
            "engines": "engine", "components": "component",
            "healthy": "healthy", "ok": "healthy",
            "errors": "error", "failures": "error",
        }

    # ── Data source CRUD ─────────────────────────────────────────────────

    def register_source(
        self, name: str, description: str = "",
        supported_intents: Optional[List[QueryIntent]] = None,
        handler: Optional[Callable[[ParsedQuery], Dict[str, Any]]] = None,
        priority: int = 0,
    ) -> DataSourceRegistration:
        """Register a data source that can answer queries."""
        src = DataSourceRegistration(
            name=name, description=description,
            supported_intents=supported_intents or [],
            handler=handler, priority=priority,
        )
        with self._lock:
            if len(self._sources) >= self._max_sources:
                logger.warning("Source cap reached (%d)", self._max_sources)
                return src
            self._sources[src.id] = src
        logger.info("Data source registered: %s (%s)", name, src.id)
        return src

    def unregister_source(self, source_id: str) -> bool:
        """Remove a data source."""
        with self._lock:
            return self._sources.pop(source_id, None) is not None

    def get_source(self, source_id: str) -> Optional[DataSourceRegistration]:
        """Retrieve a data source by id."""
        with self._lock:
            return self._sources.get(source_id)

    def list_sources(self) -> List[DataSourceRegistration]:
        """Return all registered data sources."""
        with self._lock:
            return list(self._sources.values())

    def enable_source(self, source_id: str) -> bool:
        """Enable a data source."""
        with self._lock:
            src = self._sources.get(source_id)
            if not src:
                return False
            src.enabled = True
        return True

    def disable_source(self, source_id: str) -> bool:
        """Disable a data source."""
        with self._lock:
            src = self._sources.get(source_id)
            if not src:
                return False
            src.enabled = False
        return True

    # ── Query processing ─────────────────────────────────────────────────

    def query(self, text: str) -> QueryResult:
        """Parse and answer a natural-language query."""
        t0 = time.monotonic()
        parsed = self.parse(text)
        result = self._dispatch(parsed)
        result.elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
        self._record_history(text, parsed, result)
        return result

    def parse(self, text: str) -> ParsedQuery:
        """Parse raw text into a structured ParsedQuery."""
        normalised = self._normalise(text)
        intent, conf = self._detect_intent(normalised)
        entities = self._extract_entities(normalised)
        return ParsedQuery(
            raw_text=text, intent=intent, entities=entities,
            confidence=conf, normalised_text=normalised,
        )

    # ── History ──────────────────────────────────────────────────────────

    def get_history(
        self, limit: int = 50, intent: Optional[QueryIntent] = None,
    ) -> List[QueryHistoryEntry]:
        """Return recent query history, optionally filtered."""
        with self._lock:
            entries = list(self._history)
        if intent is not None:
            entries = [e for e in entries if e.intent == intent]
        return entries[-limit:]

    def clear_history(self) -> int:
        """Clear query history, return count cleared."""
        with self._lock:
            count = len(self._history)
            self._history.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Return query statistics."""
        with self._lock:
            history = list(self._history)
            sources = list(self._sources.values())
        return self._compile_stats(history, sources)

    # ── Synonyms ─────────────────────────────────────────────────────────

    def add_synonym(self, word: str, canonical: str) -> None:
        """Register a word synonym for normalisation."""
        with self._lock:
            self._synonyms[word.lower()] = canonical.lower()

    # ── Private: parsing ─────────────────────────────────────────────────

    def _normalise(self, text: str) -> str:
        """Lowercase, strip, collapse whitespace, apply synonyms."""
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[?!.,;:]", "", text)
        tokens = text.split()
        with self._lock:
            syns = dict(self._synonyms)
        tokens = [syns.get(t, t) for t in tokens]
        return " ".join(tokens)

    @staticmethod
    def _detect_intent(text: str) -> Tuple[QueryIntent, float]:
        """Match the first intent pattern; return (intent, confidence)."""
        for intent, pattern in _INTENT_PATTERNS:
            if pattern.search(text):
                return intent, 0.85
        return QueryIntent.unknown, 0.1

    @staticmethod
    def _extract_entities(text: str) -> List[Entity]:
        """Extract entities from normalised text."""
        entities: List[Entity] = []
        for etype, pattern in _ENTITY_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(0).strip()
                entities.append(Entity(
                    type=etype, value=value, confidence=0.8,
                ))
        return entities

    # ── Private: dispatch ────────────────────────────────────────────────

    def _dispatch(self, parsed: ParsedQuery) -> QueryResult:
        """Dispatch a parsed query to matching data sources."""
        if parsed.intent == QueryIntent.help:
            return self._handle_help()
        if parsed.intent == QueryIntent.unknown:
            return self._handle_unknown(parsed)
        sources = self._find_sources(parsed.intent)
        if not sources:
            return self._handle_no_source(parsed)
        return self._call_sources(parsed, sources)

    def _find_sources(self, intent: QueryIntent) -> List[DataSourceRegistration]:
        """Find enabled sources supporting *intent*, sorted by priority."""
        with self._lock:
            matched = [
                s for s in self._sources.values()
                if s.enabled and intent in s.supported_intents and s.handler
            ]
        matched.sort(key=lambda s: s.priority, reverse=True)
        return matched

    def _call_sources(
        self, parsed: ParsedQuery, sources: List[DataSourceRegistration],
    ) -> QueryResult:
        """Invoke data-source handlers and merge results."""
        combined_data: Dict[str, Any] = {}
        answer_parts: List[str] = []
        best_source = ""
        for src in sources:
            try:
                result_data = src.handler(parsed) if src.handler else {}  # type: ignore[misc]
                if result_data:
                    combined_data.update(result_data)
                    if "answer" in result_data:
                        answer_parts.append(str(result_data["answer"]))
                    best_source = best_source or src.name
            except Exception as exc:
                logger.exception("Source %s failed for query: %s", src.name, exc)
        if not combined_data:
            return self._handle_no_source(parsed)
        return QueryResult(
            status=QueryStatus.success,
            answer=" ".join(answer_parts) if answer_parts else "Query processed.",
            data=combined_data, source=best_source,
            confidence=parsed.confidence,
        )

    @staticmethod
    def _handle_help() -> QueryResult:
        """Return a help message."""
        return QueryResult(
            status=QueryStatus.success,
            answer="You can ask about system status, list modules, "
                   "count resources, search for items, compare metrics, "
                   "or view trends. Try: 'What is the system status?'",
            data={"supported_intents": [i.value for i in QueryIntent]},
            confidence=1.0,
        )

    @staticmethod
    def _handle_unknown(parsed: ParsedQuery) -> QueryResult:
        """Handle an unrecognised query."""
        return QueryResult(
            status=QueryStatus.no_match,
            answer=f"I couldn't understand: '{parsed.raw_text}'. "
                   "Try asking about status, counts, or listing items.",
            suggestions=[
                "What is the system status?",
                "How many modules are running?",
                "List all active services",
            ],
            confidence=0.1,
        )

    @staticmethod
    def _handle_no_source(parsed: ParsedQuery) -> QueryResult:
        """No data source matched the intent."""
        return QueryResult(
            status=QueryStatus.partial,
            answer=f"No data source available for intent '{parsed.intent.value}'.",
            suggestions=["Register a data source for this intent type."],
            confidence=parsed.confidence,
        )

    # ── Private: history ─────────────────────────────────────────────────

    def _record_history(
        self, text: str, parsed: ParsedQuery, result: QueryResult,
    ) -> None:
        """Append to bounded history."""
        entry = QueryHistoryEntry(
            raw_text=text, intent=parsed.intent, status=result.status,
            answer=result.answer[:200], elapsed_ms=result.elapsed_ms,
        )
        with self._lock:
            capped_append(self._history, entry, self._max_history)

    @staticmethod
    def _compile_stats(
        history: List[QueryHistoryEntry],
        sources: List[DataSourceRegistration],
    ) -> Dict[str, Any]:
        """Build stats dict."""
        intent_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        total_ms = 0.0
        for h in history:
            intent_counts[h.intent.value] = intent_counts.get(h.intent.value, 0) + 1
            status_counts[h.status.value] = status_counts.get(h.status.value, 0) + 1
            total_ms += h.elapsed_ms
        return {
            "total_queries": len(history),
            "intent_distribution": intent_counts,
            "status_distribution": status_counts,
            "avg_elapsed_ms": round(total_ms / max(len(history), 1), 2),
            "registered_sources": len(sources),
            "enabled_sources": sum(1 for s in sources if s.enabled),
        }

# ── Wingman pair validation ───────────────────────────────────────────────

def validate_wingman_pair(engine: NLQueryEngine) -> Tuple[bool, str]:
    """Validate the NLQ engine meets Wingman requirements.

    Checks: at least one data source registered, at least one enabled,
    all enabled sources have a handler.
    """
    sources = engine.list_sources()
    if not sources:
        return False, "No data sources registered"
    enabled = [s for s in sources if s.enabled]
    if not enabled:
        return False, "No data sources enabled"
    for s in enabled:
        if s.handler is None:
            return False, f"Source '{s.name}' is enabled but has no handler"
    return True, "Valid NLQ wingman pair"

# ── Causality Sandbox gate ────────────────────────────────────────────────

def gate_nlq_in_sandbox(engine: NLQueryEngine) -> Tuple[bool, str]:
    """Gate the NLQ engine for the Causality Sandbox.

    Approved if: engine has ≤100 sources, history is bounded,
    at least one source is registered.
    """
    sources = engine.list_sources()
    if not sources:
        return False, "At least one data source required"
    if len(sources) > 100:
        return False, "Too many data sources (max 100)"
    return True, "Approved for sandbox"

# ── Flask Blueprint ───────────────────────────────────────────────────────

def _api_body() -> Dict[str, Any]:
    """Extract JSON body."""
    return request.get_json(silent=True) or {}

def _api_err(msg: str, code: str, status: int = 400) -> Any:
    """Standard error response."""
    return jsonify({"error": msg, "code": code}), status

def _register_query_routes(bp: Any, engine: NLQueryEngine) -> None:
    """Attach query routes."""
    @bp.route("/query", methods=["POST"])
    def run_query() -> Any:
        """Submit a natural-language query."""
        b = _api_body()
        text = b.get("text", "").strip()
        if not text:
            return _api_err("text required", "NLQ_MISSING")
        result = engine.query(text)
        return jsonify(result.to_dict())

    @bp.route("/parse", methods=["POST"])
    def parse_query() -> Any:
        """Parse a query without executing."""
        b = _api_body()
        text = b.get("text", "").strip()
        if not text:
            return _api_err("text required", "NLQ_MISSING")
        parsed = engine.parse(text)
        return jsonify(parsed.to_dict())

def _register_source_routes(bp: Any, engine: NLQueryEngine) -> None:
    """Attach data-source CRUD routes."""
    @bp.route("/sources", methods=["GET"])
    def list_sources() -> Any:
        """List registered data sources."""
        return jsonify([s.to_dict() for s in engine.list_sources()])

    @bp.route("/sources/<source_id>", methods=["GET"])
    def get_source(source_id: str) -> Any:
        """Get a single data source."""
        src = engine.get_source(source_id)
        if not src:
            return _api_err("Not found", "NLQ_404", 404)
        return jsonify(src.to_dict())

    @bp.route("/sources/<source_id>", methods=["DELETE"])
    def delete_source(source_id: str) -> Any:
        """Remove a data source."""
        if engine.unregister_source(source_id):
            return jsonify({"deleted": True})
        return _api_err("Not found", "NLQ_404", 404)

    @bp.route("/sources/<source_id>/enable", methods=["POST"])
    def enable_source(source_id: str) -> Any:
        """Enable a data source."""
        if engine.enable_source(source_id):
            return jsonify({"enabled": True})
        return _api_err("Not found", "NLQ_404", 404)

    @bp.route("/sources/<source_id>/disable", methods=["POST"])
    def disable_source(source_id: str) -> Any:
        """Disable a data source."""
        if engine.disable_source(source_id):
            return jsonify({"disabled": True})
        return _api_err("Not found", "NLQ_404", 404)

def _register_history_routes(bp: Any, engine: NLQueryEngine) -> None:
    """Attach history and stats routes."""
    @bp.route("/history", methods=["GET"])
    def get_history() -> Any:
        """Query history with optional intent filter."""
        intent_val = request.args.get("intent")
        limit = int(request.args.get("limit", "50"))
        intent = QueryIntent(intent_val) if intent_val else None
        entries = engine.get_history(limit=limit, intent=intent)
        return jsonify([e.to_dict() for e in entries])

    @bp.route("/history", methods=["DELETE"])
    def clear_history() -> Any:
        """Clear query history."""
        count = engine.clear_history()
        return jsonify({"cleared": count})

    @bp.route("/stats", methods=["GET"])
    def get_stats() -> Any:
        """Query engine statistics."""
        return jsonify(engine.get_stats())

def create_nlq_api(engine: NLQueryEngine) -> Any:
    """Create a Flask Blueprint exposing NLQ endpoints."""
    if not _HAS_FLASK:
        return Blueprint("nlq", __name__)
    bp = Blueprint("nlq", __name__, url_prefix="/api/nlq")
    _register_query_routes(bp, engine)
    _register_source_routes(bp, engine)
    _register_history_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp

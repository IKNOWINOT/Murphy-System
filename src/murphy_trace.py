"""
Murphy System - Murphy Trace
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

LLM observability, token/cost/latency tracking, and prompt versioning for Murphy.
100% original implementation - no Langfuse dependency.
Integrates with: observability_counters.py, operational_slo_tracker.py
"""

import asyncio
import csv
import io
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SpanKind(str, Enum):
    """SpanKind enumeration."""
    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    CHAIN = "chain"
    AGENT = "agent"
    GATE = "gate"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LLMMetrics(BaseModel):
    """Metrics container for llm measurement."""
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    temperature: float = 0.0


class PromptVersion(BaseModel):
    """PromptVersion — prompt version definition."""
    version_id: str
    template_name: str
    content: str
    version: int
    ab_tag: Optional[str] = None
    created_at: str


# ---------------------------------------------------------------------------
# Span dataclass
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Span:
    """Span — span definition."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    started_at: str
    ended_at: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    llm_metrics: Optional[LLMMetrics] = None
    status: str = "running"
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value if isinstance(self.kind, SpanKind) else self.kind,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "llm_metrics": self.llm_metrics.model_dump() if self.llm_metrics else None,
            "status": self.status,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Trace dataclass
# ---------------------------------------------------------------------------


@dataclass
class Trace:
    """Trace — trace definition."""
    trace_id: str
    name: str
    started_at: str
    ended_at: Optional[str] = None
    spans: List[Span] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    def finish(self, status: str = "ok") -> None:
        self.ended_at = _utcnow_iso()
        self.status = status

    def total_cost_usd(self) -> float:
        total = 0.0
        for span in self.spans:
            if span.llm_metrics is not None:
                total += span.llm_metrics.cost_usd
        return total

    def total_tokens(self) -> int:
        total = 0
        for span in self.spans:
            if span.llm_metrics is not None:
                total += span.llm_metrics.tokens_in + span.llm_metrics.tokens_out
        return total

    def to_dict(self) -> Dict:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
            "status": self.status,
            "total_cost_usd": self.total_cost_usd(),
            "total_tokens": self.total_tokens(),
        }


# ---------------------------------------------------------------------------
# TraceStore
# ---------------------------------------------------------------------------


class TraceStore:
    """TraceStore — trace store definition."""
    def __init__(self, traces_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._traces: Dict[str, Trace] = {}
        self._order: List[str] = []
        self._traces_dir = traces_dir
        if traces_dir:
            os.makedirs(traces_dir, exist_ok=True)

    def save(self, trace: Trace) -> None:
        with self._lock:
            self._traces[trace.trace_id] = trace
            if trace.trace_id not in self._order:
                capped_append(self._order, trace.trace_id)
            if self._traces_dir:
                file_path = os.path.join(self._traces_dir, "traces.jsonl")
                try:
                    with open(file_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(trace.to_dict()) + "\n")
                except OSError as exc:
                    logger.error("Failed to persist trace %s: %s", trace.trace_id, exc)

    def get(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            return self._traces.get(trace_id)

    def list_recent(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            recent_ids = list(reversed(self._order))[:limit]
            return [self._traces[tid].to_dict() for tid in recent_ids if tid in self._traces]

    def get_stats(self) -> Dict:
        with self._lock:
            traces = list(self._traces.values())

        total_cost = sum(t.total_cost_usd() for t in traces)
        token_usage_by_model: Dict[str, int] = {}
        latencies: List[float] = []

        for trace in traces:
            for span in trace.spans:
                if span.llm_metrics is not None:
                    model_key = span.llm_metrics.model
                    token_usage_by_model[model_key] = (
                        token_usage_by_model.get(model_key, 0)
                        + span.llm_metrics.tokens_in
                        + span.llm_metrics.tokens_out
                    )
                if span.duration_ms > 0:
                    latencies.append(span.duration_ms)

        avg_latency_ms = sum(latencies) / (len(latencies) or 1)

        return {
            "avg_latency_ms": avg_latency_ms,
            "total_cost_usd": total_cost,
            "token_usage_by_model": token_usage_by_model,
            "total_traces": len(traces),
        }


# ---------------------------------------------------------------------------
# TraceExporter
# ---------------------------------------------------------------------------


class TraceExporter:
    """TraceExporter — trace exporter definition."""

    @staticmethod
    def to_json(trace: Trace) -> str:
        return json.dumps(trace.to_dict(), indent=2)

    @staticmethod
    def to_csv(traces: List[Trace]) -> str:
        output = io.StringIO()
        fieldnames = [
            "trace_id",
            "name",
            "started_at",
            "ended_at",
            "status",
            "total_cost_usd",
            "total_tokens",
            "span_count",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for trace in traces:
            writer.writerow(
                {
                    "trace_id": trace.trace_id,
                    "name": trace.name,
                    "started_at": trace.started_at,
                    "ended_at": trace.ended_at or "",
                    "status": trace.status,
                    "total_cost_usd": trace.total_cost_usd(),
                    "total_tokens": trace.total_tokens(),
                    "span_count": len(trace.spans),
                }
            )
        return output.getvalue()

    @staticmethod
    def to_prometheus(stats: Dict) -> str:
        lines: List[str] = []
        lines.append("# HELP murphy_trace_total_cost_usd Total cost")
        lines.append(f"murphy_trace_total_cost_usd {stats.get('total_cost_usd', 0.0)}")
        lines.append("# HELP murphy_trace_avg_latency_ms Average span latency in milliseconds")
        lines.append(f"murphy_trace_avg_latency_ms {stats.get('avg_latency_ms', 0.0)}")
        lines.append("# HELP murphy_trace_total_traces Total number of traces")
        lines.append(f"murphy_trace_total_traces {stats.get('total_traces', 0)}")
        token_usage = stats.get("token_usage_by_model", {})
        for model, tokens in token_usage.items():
            safe_model = model.replace("-", "_").replace(".", "_").replace("/", "_")
            lines.append(f"# HELP murphy_trace_tokens_{safe_model} Token usage for model {model}")
            lines.append(f'murphy_trace_tokens{{model="{model}"}} {tokens}')
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# TraceContext - thread-local
# ---------------------------------------------------------------------------


class TraceContext:
    """TraceContext — trace context definition."""
    _local = threading.local()

    @classmethod
    def get_current_trace(cls) -> Optional[Trace]:
        return getattr(cls._local, "current_trace", None)

    @classmethod
    def set_current_trace(cls, trace: Optional[Trace]) -> None:
        cls._local.current_trace = trace


# ---------------------------------------------------------------------------
# @traced decorator
# ---------------------------------------------------------------------------


def traced(name: Optional[str] = None, kind: SpanKind = SpanKind.CHAIN):
    def decorator(func):
        span_name = name or func.__name__

        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                span = _build_span(span_name, kind)
                trace = TraceContext.get_current_trace()
                if trace is not None:
                    trace.add_span(span)
                try:
                    result = await func(*args, **kwargs)
                    _close_span(span, "ok")
                    return result
                except Exception as exc:
                    _close_span(span, "error", str(exc))
                    logger.error("Traced async span '%s' raised: %s", span_name, exc)
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                span = _build_span(span_name, kind)
                trace = TraceContext.get_current_trace()
                if trace is not None:
                    trace.add_span(span)
                try:
                    result = func(*args, **kwargs)
                    _close_span(span, "ok")
                    return result
                except Exception as exc:
                    _close_span(span, "error", str(exc))
                    logger.error("Traced span '%s' raised: %s", span_name, exc)
                    raise
            return sync_wrapper

    return decorator


def _build_span(name: str, kind: SpanKind) -> Span:
    current = TraceContext.get_current_trace()
    trace_id = current.trace_id if current else str(uuid.uuid4())
    return Span(
        span_id=str(uuid.uuid4()),
        trace_id=trace_id,
        parent_span_id=None,
        name=name,
        kind=kind,
        started_at=_utcnow_iso(),
    )


def _close_span(span: Span, status: str, error: Optional[str] = None) -> None:
    span.ended_at = _utcnow_iso()
    span.status = status
    span.error = error
    try:
        started = datetime.fromisoformat(span.started_at)
        ended = datetime.fromisoformat(span.ended_at)
        span.duration_ms = (ended - started).total_seconds() * 1000.0
    except (ValueError, TypeError) as exc:
        logger.warning("Could not compute duration for span %s: %s", span.span_id, exc)


# ---------------------------------------------------------------------------
# Module-level singleton and convenience functions
# ---------------------------------------------------------------------------

_GLOBAL_TRACE_STORE = TraceStore()


def get_store() -> TraceStore:
    return _GLOBAL_TRACE_STORE


def create_trace(name: str, metadata: Optional[Dict] = None) -> Trace:
    trace = Trace(
        trace_id=str(uuid.uuid4()),
        name=name,
        started_at=_utcnow_iso(),
        metadata=metadata or {},
    )
    return trace


def start_span(
    name: str,
    kind: SpanKind = SpanKind.CHAIN,
    trace: Optional[Trace] = None,
) -> Span:
    current_trace = trace or TraceContext.get_current_trace()
    trace_id = current_trace.trace_id if current_trace else str(uuid.uuid4())
    span = Span(
        span_id=str(uuid.uuid4()),
        trace_id=trace_id,
        parent_span_id=None,
        name=name,
        kind=kind,
        started_at=_utcnow_iso(),
    )
    if current_trace is not None:
        current_trace.add_span(span)
    return span


def finish_span(span: Span, status: str = "ok", error: Optional[str] = None) -> None:
    _close_span(span, status, error)

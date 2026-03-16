"""
Murphy System - Tests for Murphy Trace
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""
import os

import json
import uuid
from datetime import datetime, timezone

import pytest

from murphy_trace import (
    SpanKind,
    LLMMetrics,
    PromptVersion,
    Span,
    Trace,
    TraceStore,
    TraceExporter,
    TraceContext,
    traced,
    create_trace,
    get_store,
    start_span,
    finish_span,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_span(trace_id: str = None, name: str = "test_span", kind: SpanKind = SpanKind.CHAIN) -> Span:
    tid = trace_id or str(uuid.uuid4())
    return Span(
        span_id=str(uuid.uuid4()),
        trace_id=tid,
        parent_span_id=None,
        name=name,
        kind=kind,
        started_at=_now(),
    )


def _make_trace(name: str = "test_trace") -> Trace:
    return Trace(
        trace_id=str(uuid.uuid4()),
        name=name,
        started_at=_now(),
    )


def _make_llm_metrics(cost: float = 0.005, tokens_in: int = 100, tokens_out: int = 50) -> LLMMetrics:
    return LLMMetrics(
        model="gpt-4o",
        provider="openai",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=120.0,
        temperature=0.7,
    )


# ---------------------------------------------------------------------------
# TestSpanAndTrace
# ---------------------------------------------------------------------------

class TestSpanAndTrace:
    def test_span_creation(self):
        trace = _make_trace()
        span = _make_span(trace_id=trace.trace_id)
        assert span.trace_id == trace.trace_id
        assert span.status == "running"
        assert span.ended_at is None

    def test_trace_add_span(self):
        trace = _make_trace()
        span = _make_span(trace_id=trace.trace_id)
        trace.add_span(span)
        assert span in trace.spans

    def test_trace_total_cost_usd_zero_with_no_spans(self):
        trace = _make_trace()
        assert trace.total_cost_usd() == pytest.approx(0.0)

    def test_trace_total_cost_usd_sums_spans(self):
        trace = _make_trace()
        for cost in (0.001, 0.002, 0.003):
            span = _make_span(trace_id=trace.trace_id)
            span.llm_metrics = _make_llm_metrics(cost=cost)
            trace.add_span(span)
        assert trace.total_cost_usd() == pytest.approx(0.006)

    def test_trace_total_tokens(self):
        trace = _make_trace()
        span = _make_span(trace_id=trace.trace_id)
        span.llm_metrics = _make_llm_metrics(tokens_in=100, tokens_out=50)
        trace.add_span(span)
        assert trace.total_tokens() == 150

    def test_trace_finish(self):
        trace = _make_trace()
        trace.finish("ok")
        assert trace.status == "ok"
        assert trace.ended_at is not None

    def test_trace_to_dict_contains_required_keys(self):
        trace = _make_trace()
        d = trace.to_dict()
        for key in ("trace_id", "name", "started_at", "spans", "status", "total_cost_usd"):
            assert key in d, f"Missing key: {key}"

    def test_span_to_dict(self):
        span = _make_span()
        d = span.to_dict()
        assert d["span_id"] == span.span_id
        assert d["name"] == span.name

    def test_span_kind_enum_values(self):
        assert SpanKind.LLM.value == "llm"
        assert SpanKind.TOOL.value == "tool"
        assert SpanKind.AGENT.value == "agent"


# ---------------------------------------------------------------------------
# TestTraceStore
# ---------------------------------------------------------------------------

class TestTraceStore:
    def test_save_and_get(self):
        store = TraceStore()
        trace = _make_trace()
        store.save(trace)
        loaded = store.get(trace.trace_id)
        assert loaded is trace

    def test_get_missing_returns_none(self):
        store = TraceStore()
        assert store.get("nonexistent_id") is None

    def test_list_recent_empty(self):
        store = TraceStore()
        assert store.list_recent() == []

    def test_list_recent_returns_dicts(self):
        store = TraceStore()
        for _ in range(3):
            trace = _make_trace()
            store.save(trace)
        recent = store.list_recent(limit=10)
        assert len(recent) == 3
        assert all(isinstance(r, dict) for r in recent)

    def test_list_recent_respects_limit(self):
        store = TraceStore()
        for _ in range(10):
            store.save(_make_trace())
        recent = store.list_recent(limit=3)
        assert len(recent) == 3

    def test_get_stats_structure(self):
        store = TraceStore()
        trace = _make_trace()
        span = _make_span(trace_id=trace.trace_id)
        span.llm_metrics = _make_llm_metrics()
        span.duration_ms = 50.0
        trace.add_span(span)
        store.save(trace)
        stats = store.get_stats()
        assert "total_cost_usd" in stats
        assert "avg_latency_ms" in stats
        assert "total_traces" in stats
        assert "token_usage_by_model" in stats

    def test_get_stats_total_traces_count(self):
        store = TraceStore()
        for _ in range(4):
            store.save(_make_trace())
        stats = store.get_stats()
        assert stats["total_traces"] == 4

    def test_save_to_disk(self, tmp_path):
        store = TraceStore(traces_dir=str(tmp_path))
        trace = _make_trace("disk_trace")
        store.save(trace)
        loaded = store.get(trace.trace_id)
        assert loaded is not None
        traces_file = tmp_path / "traces.jsonl"
        assert traces_file.exists()


# ---------------------------------------------------------------------------
# TestTraceExporter
# ---------------------------------------------------------------------------

class TestTraceExporter:
    def test_to_json_returns_valid_json(self):
        trace = _make_trace("export_test")
        json_str = TraceExporter.to_json(trace)
        parsed = json.loads(json_str)
        assert parsed["trace_id"] == trace.trace_id

    def test_to_csv_returns_string_with_headers(self):
        traces = [_make_trace(f"t{i}") for i in range(3)]
        csv_str = TraceExporter.to_csv(traces)
        assert "trace_id" in csv_str
        assert "total_cost_usd" in csv_str

    def test_to_csv_contains_all_traces(self):
        traces = [_make_trace() for _ in range(2)]
        csv_str = TraceExporter.to_csv(traces)
        for trace in traces:
            assert trace.trace_id in csv_str

    def test_to_prometheus_returns_metric_lines(self):
        stats = {
            "total_cost_usd": 0.05,
            "avg_latency_ms": 120.0,
            "total_traces": 10,
            "token_usage_by_model": {"gpt-4o": 500},
        }
        prom = TraceExporter.to_prometheus(stats)
        assert "murphy_trace_total_cost_usd" in prom
        assert "murphy_trace_avg_latency_ms" in prom
        assert "murphy_trace_total_traces" in prom

    def test_to_prometheus_includes_model_token_lines(self):
        stats = {
            "total_cost_usd": 0.0,
            "avg_latency_ms": 0.0,
            "total_traces": 0,
            "token_usage_by_model": {"gpt-4o": 100, "claude-3": 200},
        }
        prom = TraceExporter.to_prometheus(stats)
        assert "gpt" in prom
        assert "claude" in prom


# ---------------------------------------------------------------------------
# TestTracedDecorator
# ---------------------------------------------------------------------------

class TestTracedDecorator:
    def test_traced_wraps_function(self):
        @traced(name="my_test_fn")
        def my_func(x: int) -> int:
            return x * 2

        result = my_func(5)
        assert result == 10

    def test_traced_adds_span_to_active_trace(self):
        trace = _make_trace("decorator_trace")
        TraceContext.set_current_trace(trace)
        try:
            @traced(name="span_creator")
            def fn() -> str:
                return "done"

            fn()
            assert len(trace.spans) == 1
            assert trace.spans[0].name == "span_creator"
        finally:
            TraceContext.set_current_trace(None)

    def test_traced_span_status_ok_on_success(self):
        trace = _make_trace()
        TraceContext.set_current_trace(trace)
        try:
            @traced()
            def good_fn() -> str:
                return "ok"

            good_fn()
            assert trace.spans[0].status == "ok"
        finally:
            TraceContext.set_current_trace(None)

    def test_traced_span_status_error_on_exception(self):
        trace = _make_trace()
        TraceContext.set_current_trace(trace)
        try:
            @traced()
            def bad_fn():
                raise ValueError("intentional error")

            with pytest.raises(ValueError, match="intentional error"):
                bad_fn()
            assert trace.spans[0].status == "error"
        finally:
            TraceContext.set_current_trace(None)

    def test_traced_kind_parameter(self):
        trace = _make_trace()
        TraceContext.set_current_trace(trace)
        try:
            @traced(name="llm_call", kind=SpanKind.LLM)
            def llm_fn() -> str:
                return "response"

            llm_fn()
            assert trace.spans[0].kind == SpanKind.LLM
        finally:
            TraceContext.set_current_trace(None)


# ---------------------------------------------------------------------------
# TestConvenienceFunctions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    def test_create_trace_returns_trace(self):
        trace = create_trace("convenience_test")
        assert isinstance(trace, Trace)
        assert trace.name == "convenience_test"
        assert trace.trace_id is not None

    def test_create_trace_with_metadata(self):
        meta = {"env": "test", "version": "1.0"}
        trace = create_trace("meta_trace", metadata=meta)
        assert trace.metadata["env"] == "test"

    def test_get_store_returns_trace_store(self):
        store = get_store()
        assert isinstance(store, TraceStore)

    def test_get_store_is_stable(self):
        s1 = get_store()
        s2 = get_store()
        assert s1 is s2

    def test_start_span_returns_span(self):
        trace = create_trace("span_test")
        span = start_span("my_op", kind=SpanKind.TOOL, trace=trace)
        assert isinstance(span, Span)
        assert span.name == "my_op"
        assert span.kind == SpanKind.TOOL

    def test_start_span_attaches_to_trace(self):
        trace = create_trace("attach_test")
        span = start_span("attached_op", trace=trace)
        assert span in trace.spans

    def test_finish_span_sets_ended_at(self):
        span = _make_span()
        finish_span(span, status="ok")
        assert span.ended_at is not None
        assert span.status == "ok"

    def test_finish_span_records_error(self):
        span = _make_span()
        finish_span(span, status="error", error="something broke")
        assert span.status == "error"
        assert span.error == "something broke"

    def test_finish_span_computes_duration(self):
        span = _make_span()
        finish_span(span)
        assert span.duration_ms >= 0.0

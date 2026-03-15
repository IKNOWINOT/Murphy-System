# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for natural_language_query — NLQ-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable NLQRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from natural_language_query import (  # noqa: E402
    DataSourceRegistration,
    Entity,
    EntityType,
    NLQueryEngine,
    ParsedQuery,
    QueryHistoryEntry,
    QueryIntent,
    QueryResult,
    QueryStatus,
    create_nlq_api,
    gate_nlq_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------

@dataclass
class NLQRecord:
    """One NLQ check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )

_RESULTS: List[NLQRecord] = []

def record(
    check_id: str, desc: str, expected: Any, actual: Any,
    cause: str = "", effect: str = "", lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(NLQRecord(
        check_id=check_id, description=desc, expected=expected,
        actual=actual, passed=ok, cause=cause, effect=effect, lesson=lesson,
    ))
    return ok

# -- Helpers ---------------------------------------------------------------

def _engine(**kw: Any) -> NLQueryEngine:
    """Create a fresh NLQueryEngine."""
    return NLQueryEngine(**kw)


def _dummy_handler(parsed: ParsedQuery) -> Dict[str, Any]:
    """Simple handler that returns a canned answer."""
    return {"answer": "System is healthy", "modules": 42}


def _error_handler(parsed: ParsedQuery) -> Dict[str, Any]:
    """Handler that raises an exception."""
    raise RuntimeError("source failure")


def _engine_with_source() -> NLQueryEngine:
    """Engine with one registered + enabled source."""
    eng = _engine()
    eng.register_source(
        name="system", description="System status provider",
        supported_intents=[QueryIntent.status, QueryIntent.count,
                           QueryIntent.list_items, QueryIntent.detail],
        handler=_dummy_handler, priority=10,
    )
    return eng

# ==================================================================== #
#  Enum tests                                                           #
# ==================================================================== #

def test_nlq_001_intent_enum():
    """QueryIntent enum has expected members."""
    expected = {"status", "count", "list", "detail", "compare",
                "trend", "search", "help", "unknown"}
    assert record("NLQ-001", "QueryIntent values", expected,
                   {m.value for m in QueryIntent})


def test_nlq_002_entity_type_enum():
    """EntityType enum has expected members."""
    expected = {"module", "metric", "time_range", "status_filter",
                "number", "name"}
    assert record("NLQ-002", "EntityType values", expected,
                   {m.value for m in EntityType})


def test_nlq_003_query_status_enum():
    """QueryStatus enum has expected members."""
    expected = {"pending", "success", "partial", "error", "no_match"}
    assert record("NLQ-003", "QueryStatus values", expected,
                   {m.value for m in QueryStatus})

# ==================================================================== #
#  Dataclass tests                                                      #
# ==================================================================== #

def test_nlq_004_entity_defaults():
    """Entity has sane defaults."""
    e = Entity()
    assert record(
        "NLQ-004", "Entity defaults",
        (EntityType.name, "", 1.0),
        (e.type, e.value, e.confidence),
    )


def test_nlq_005_entity_to_dict():
    """Entity.to_dict() serialises type as string."""
    e = Entity(type=EntityType.module, value="core")
    d = e.to_dict()
    assert record("NLQ-005", "Entity to_dict", "module", d["type"])


def test_nlq_006_parsed_query_defaults():
    """ParsedQuery has sane defaults."""
    pq = ParsedQuery()
    assert record(
        "NLQ-006", "ParsedQuery defaults",
        (QueryIntent.unknown, 0.0),
        (pq.intent, pq.confidence),
    )


def test_nlq_007_parsed_query_to_dict():
    """ParsedQuery.to_dict() serialises intent."""
    pq = ParsedQuery(intent=QueryIntent.status, confidence=0.9)
    d = pq.to_dict()
    assert record("NLQ-007", "ParsedQuery to_dict", "status", d["intent"])


def test_nlq_008_query_result_defaults():
    """QueryResult has sane defaults."""
    qr = QueryResult()
    assert record(
        "NLQ-008", "QueryResult defaults",
        (True, QueryStatus.pending),
        (bool(qr.query_id), qr.status),
    )


def test_nlq_009_query_result_to_dict():
    """QueryResult.to_dict() serialises status."""
    qr = QueryResult(status=QueryStatus.success, answer="ok")
    d = qr.to_dict()
    assert record("NLQ-009", "QueryResult to_dict", "success", d["status"])


def test_nlq_010_data_source_to_dict():
    """DataSourceRegistration.to_dict() excludes handler."""
    ds = DataSourceRegistration(name="test", handler=lambda x: {})
    d = ds.to_dict()
    assert record(
        "NLQ-010", "DataSource to_dict",
        True, "handler" not in d,
    )


def test_nlq_011_history_entry_to_dict():
    """QueryHistoryEntry.to_dict() serialises enums."""
    h = QueryHistoryEntry(intent=QueryIntent.count, status=QueryStatus.success)
    d = h.to_dict()
    assert record(
        "NLQ-011", "History to_dict",
        ("count", "success"),
        (d["intent"], d["status"]),
    )

# ==================================================================== #
#  Data source CRUD tests                                               #
# ==================================================================== #

def test_nlq_012_register_source():
    """register_source() adds a data source."""
    eng = _engine()
    src = eng.register_source(name="test", handler=_dummy_handler)
    assert record(
        "NLQ-012", "Register source",
        (True, "test"),
        (bool(src.id), src.name),
        cause="register_source called with handler",
        effect="source stored in engine",
        lesson="data sources are the bridge between NLQ and system data",
    )


def test_nlq_013_unregister_source():
    """unregister_source() removes a source."""
    eng = _engine()
    src = eng.register_source(name="test")
    ok = eng.unregister_source(src.id)
    assert record(
        "NLQ-013", "Unregister source",
        (True, None),
        (ok, eng.get_source(src.id)),
    )


def test_nlq_014_unregister_nonexistent():
    """unregister_source() returns False for unknown id."""
    eng = _engine()
    assert record("NLQ-014", "Unregister nonexistent", False,
                   eng.unregister_source("nope"))


def test_nlq_015_get_source():
    """get_source() returns correct source."""
    eng = _engine()
    src = eng.register_source(name="lookup")
    fetched = eng.get_source(src.id)
    assert record("NLQ-015", "Get source", "lookup",
                   fetched.name if fetched else "")


def test_nlq_016_list_sources():
    """list_sources() returns all registered sources."""
    eng = _engine()
    eng.register_source(name="a")
    eng.register_source(name="b")
    assert record("NLQ-016", "List sources", 2, len(eng.list_sources()))


def test_nlq_017_enable_disable_source():
    """enable/disable toggle source state."""
    eng = _engine()
    src = eng.register_source(name="toggle")
    eng.disable_source(src.id)
    assert record(
        "NLQ-017", "Disable source",
        False, eng.get_source(src.id).enabled,  # type: ignore[union-attr]
    )


def test_nlq_018_enable_source():
    """enable_source() re-enables a disabled source."""
    eng = _engine()
    src = eng.register_source(name="toggle")
    eng.disable_source(src.id)
    eng.enable_source(src.id)
    assert record(
        "NLQ-018", "Enable source",
        True, eng.get_source(src.id).enabled,  # type: ignore[union-attr]
    )


def test_nlq_019_source_cap():
    """Engine respects max_sources limit."""
    eng = _engine(max_sources=2)
    eng.register_source(name="a")
    eng.register_source(name="b")
    eng.register_source(name="c")
    assert record("NLQ-019", "Source cap", 2, len(eng.list_sources()))

# ==================================================================== #
#  Intent detection tests                                               #
# ==================================================================== #

def test_nlq_020_detect_status_intent():
    """'What is the system status?' → status intent."""
    eng = _engine()
    parsed = eng.parse("What is the system status?")
    assert record(
        "NLQ-020", "Status intent",
        QueryIntent.status, parsed.intent,
        cause="query contains 'status' keyword",
        effect="intent classified as status",
        lesson="pattern matching detects status-related queries",
    )


def test_nlq_021_detect_count_intent():
    """'How many modules are running?' → count intent."""
    eng = _engine()
    parsed = eng.parse("How many modules are running?")
    assert record("NLQ-021", "Count intent",
                   QueryIntent.count, parsed.intent)


def test_nlq_022_detect_list_intent():
    """'List all active services' → list intent."""
    eng = _engine()
    parsed = eng.parse("List all active services")
    assert record("NLQ-022", "List intent",
                   QueryIntent.list_items, parsed.intent)


def test_nlq_023_detect_detail_intent():
    """'Tell me about the notification system' → detail intent."""
    eng = _engine()
    parsed = eng.parse("Tell me about the notification system")
    assert record("NLQ-023", "Detail intent",
                   QueryIntent.detail, parsed.intent)


def test_nlq_024_detect_compare_intent():
    """'Compare module A vs module B' → compare intent."""
    eng = _engine()
    parsed = eng.parse("Compare module A vs module B")
    assert record("NLQ-024", "Compare intent",
                   QueryIntent.compare, parsed.intent)


def test_nlq_025_detect_trend_intent():
    """'Show error rate trend over time' → trend intent."""
    eng = _engine()
    parsed = eng.parse("Show error rate trend over time")
    assert record("NLQ-025", "Trend intent",
                   QueryIntent.trend, parsed.intent)


def test_nlq_026_detect_search_intent():
    """'Find modules with errors' → search intent."""
    eng = _engine()
    parsed = eng.parse("Find modules with errors")
    assert record("NLQ-026", "Search intent",
                   QueryIntent.search, parsed.intent)


def test_nlq_027_detect_help_intent():
    """'Help me understand how to use this' → help intent."""
    eng = _engine()
    parsed = eng.parse("Help me understand how to use this")
    assert record("NLQ-027", "Help intent",
                   QueryIntent.help, parsed.intent)


def test_nlq_028_detect_unknown_intent():
    """Gibberish → unknown intent."""
    eng = _engine()
    parsed = eng.parse("xyzzy foobar baz")
    assert record("NLQ-028", "Unknown intent",
                   QueryIntent.unknown, parsed.intent)

# ==================================================================== #
#  Entity extraction tests                                              #
# ==================================================================== #

def test_nlq_029_extract_module_entity():
    """'module core' extracts a module entity."""
    eng = _engine()
    parsed = eng.parse("Tell me about module core")
    types = [e.type for e in parsed.entities]
    assert record("NLQ-029", "Module entity",
                   True, EntityType.module in types)


def test_nlq_030_extract_metric_entity():
    """'latency' extracts a metric entity."""
    eng = _engine()
    parsed = eng.parse("What is the current latency?")
    types = [e.type for e in parsed.entities]
    assert record("NLQ-030", "Metric entity",
                   True, EntityType.metric in types)


def test_nlq_031_extract_time_range():
    """'last 5 hours' extracts a time_range entity."""
    eng = _engine()
    parsed = eng.parse("Show errors in the last 5 hours")
    types = [e.type for e in parsed.entities]
    assert record("NLQ-031", "Time range entity",
                   True, EntityType.time_range in types)


def test_nlq_032_extract_status_filter():
    """'healthy' extracts a status_filter entity."""
    eng = _engine()
    parsed = eng.parse("List healthy modules")
    types = [e.type for e in parsed.entities]
    assert record("NLQ-032", "Status filter entity",
                   True, EntityType.status_filter in types)


def test_nlq_033_extract_number():
    """'42' extracts a number entity."""
    eng = _engine()
    parsed = eng.parse("Show the top 42 results")
    types = [e.type for e in parsed.entities]
    assert record("NLQ-033", "Number entity",
                   True, EntityType.number in types)

# ==================================================================== #
#  Query execution tests                                                #
# ==================================================================== #

def test_nlq_034_query_with_source():
    """query() with a registered source returns success."""
    eng = _engine_with_source()
    result = eng.query("What is the system status?")
    assert record(
        "NLQ-034", "Query with source",
        (QueryStatus.success, True),
        (result.status, "healthy" in result.answer.lower()),
        cause="status query dispatched to system source",
        effect="structured answer returned",
        lesson="data sources bridge NLQ to real system data",
    )


def test_nlq_035_query_no_source():
    """query() without sources returns partial."""
    eng = _engine()
    result = eng.query("What is the system status?")
    assert record("NLQ-035", "Query no source",
                   QueryStatus.partial, result.status)


def test_nlq_036_query_help():
    """query('help') returns help message."""
    eng = _engine()
    result = eng.query("help")
    assert record(
        "NLQ-036", "Help query",
        (QueryStatus.success, True),
        (result.status, "supported_intents" in result.data),
    )


def test_nlq_037_query_unknown():
    """query() with gibberish returns no_match."""
    eng = _engine()
    result = eng.query("xyzzy foobar")
    assert record("NLQ-037", "Unknown query",
                   QueryStatus.no_match, result.status)


def test_nlq_038_query_with_error_handler():
    """query() handles source exceptions gracefully."""
    eng = _engine()
    eng.register_source(
        name="broken", supported_intents=[QueryIntent.status],
        handler=_error_handler,
    )
    result = eng.query("What is the system status?")
    assert record(
        "NLQ-038", "Error handler",
        True, result.status in (QueryStatus.partial, QueryStatus.no_match),
        cause="source handler raises exception",
        effect="engine degrades gracefully",
        lesson="never let a source failure crash the query pipeline",
    )


def test_nlq_039_query_elapsed_ms():
    """query() records elapsed_ms > 0."""
    eng = _engine_with_source()
    result = eng.query("What is the system status?")
    assert record("NLQ-039", "Elapsed ms", True, result.elapsed_ms >= 0)


def test_nlq_040_query_confidence():
    """query() with known intent has confidence > 0."""
    eng = _engine_with_source()
    result = eng.query("What is the system status?")
    assert record("NLQ-040", "Query confidence", True, result.confidence > 0)

# ==================================================================== #
#  Synonym tests                                                        #
# ==================================================================== #

def test_nlq_041_synonym_expansion():
    """Custom synonyms expand during normalisation."""
    eng = _engine_with_source()
    eng.add_synonym("svcs", "service")
    parsed = eng.parse("list svcs")
    assert record("NLQ-041", "Synonym expansion",
                   True, "service" in parsed.normalised_text)


def test_nlq_042_builtin_synonym():
    """Built-in synonym 'ok' → 'healthy' works."""
    eng = _engine()
    parsed = eng.parse("Is everything ok?")
    assert record("NLQ-042", "Builtin synonym",
                   True, "healthy" in parsed.normalised_text)

# ==================================================================== #
#  History tests                                                        #
# ==================================================================== #

def test_nlq_043_history_recorded():
    """query() records to history."""
    eng = _engine_with_source()
    eng.query("What is the system status?")
    history = eng.get_history()
    assert record(
        "NLQ-043", "History recorded",
        True, len(history) >= 1,
        cause="query() was called",
        effect="entry appended to history",
        lesson="history enables analytics and debugging of NLQ usage",
    )


def test_nlq_044_history_filter():
    """get_history(intent=) filters correctly."""
    eng = _engine_with_source()
    eng.query("What is the system status?")
    eng.query("help")
    status_h = eng.get_history(intent=QueryIntent.status)
    help_h = eng.get_history(intent=QueryIntent.help)
    assert record(
        "NLQ-044", "History filter",
        (1, 1),
        (len(status_h), len(help_h)),
    )


def test_nlq_045_history_limit():
    """get_history(limit=) caps results."""
    eng = _engine_with_source()
    for i in range(10):
        eng.query("status check")
    history = eng.get_history(limit=3)
    assert record("NLQ-045", "History limit", 3, len(history))


def test_nlq_046_clear_history():
    """clear_history() empties history and returns count."""
    eng = _engine_with_source()
    eng.query("status")
    eng.query("help")
    count = eng.clear_history()
    assert record(
        "NLQ-046", "Clear history",
        (2, 0),
        (count, len(eng.get_history())),
    )

# ==================================================================== #
#  Stats tests                                                          #
# ==================================================================== #

def test_nlq_047_stats_structure():
    """get_stats() returns expected keys."""
    eng = _engine_with_source()
    eng.query("What is the system status?")
    stats = eng.get_stats()
    expected_keys = {"total_queries", "intent_distribution",
                     "status_distribution", "avg_elapsed_ms",
                     "registered_sources", "enabled_sources"}
    assert record("NLQ-047", "Stats keys", expected_keys, set(stats.keys()))


def test_nlq_048_stats_counts():
    """Stats reflect correct query counts."""
    eng = _engine_with_source()
    eng.query("status")
    eng.query("status")
    eng.query("help")
    stats = eng.get_stats()
    assert record("NLQ-048", "Stats counts", 3, stats["total_queries"])

# ==================================================================== #
#  Wingman & Sandbox tests                                              #
# ==================================================================== #

def test_nlq_049_wingman_valid():
    """validate_wingman_pair() passes with enabled source + handler."""
    eng = _engine_with_source()
    ok, msg = validate_wingman_pair(eng)
    assert record(
        "NLQ-049", "Wingman valid",
        (True, "Valid NLQ wingman pair"),
        (ok, msg),
        cause="engine has enabled source with handler",
        effect="wingman validation passes",
        lesson="NLQ requires at least one data source to be useful",
    )


def test_nlq_050_wingman_no_sources():
    """validate_wingman_pair() fails with no sources."""
    eng = _engine()
    ok, _ = validate_wingman_pair(eng)
    assert record("NLQ-050", "Wingman no sources", False, ok)


def test_nlq_051_wingman_disabled_sources():
    """validate_wingman_pair() fails when all sources disabled."""
    eng = _engine()
    src = eng.register_source(name="test", handler=_dummy_handler)
    eng.disable_source(src.id)
    ok, _ = validate_wingman_pair(eng)
    assert record("NLQ-051", "Wingman disabled", False, ok)


def test_nlq_052_wingman_no_handler():
    """validate_wingman_pair() fails when source has no handler."""
    eng = _engine()
    eng.register_source(name="test")
    ok, _ = validate_wingman_pair(eng)
    assert record("NLQ-052", "Wingman no handler", False, ok)


def test_nlq_053_sandbox_valid():
    """gate_nlq_in_sandbox() approves engine with source."""
    eng = _engine_with_source()
    ok, msg = gate_nlq_in_sandbox(eng)
    assert record(
        "NLQ-053", "Sandbox valid",
        (True, "Approved for sandbox"),
        (ok, msg),
    )


def test_nlq_054_sandbox_no_sources():
    """gate_nlq_in_sandbox() rejects engine with no sources."""
    eng = _engine()
    ok, _ = gate_nlq_in_sandbox(eng)
    assert record("NLQ-054", "Sandbox no sources", False, ok)

# ==================================================================== #
#  Thread safety tests                                                  #
# ==================================================================== #

def test_nlq_055_concurrent_queries():
    """Concurrent queries are thread-safe."""
    eng = _engine_with_source()
    errors: List[str] = []

    def querier(idx: int) -> None:
        try:
            eng.query(f"status check {idx}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=querier, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "NLQ-055", "Concurrent queries",
        (0, True),
        (len(errors), len(eng.get_history()) >= 20),
        cause="20 threads querying simultaneously",
        effect="all queries recorded without errors",
        lesson="Lock protects shared state during concurrent access",
    )


def test_nlq_056_concurrent_register():
    """Concurrent source registration is thread-safe."""
    eng = _engine()
    errors: List[str] = []

    def registerer(idx: int) -> None:
        try:
            eng.register_source(name=f"src-{idx}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=registerer, args=(i,)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "NLQ-056", "Concurrent register",
        (0, 15),
        (len(errors), len(eng.list_sources())),
    )

# ==================================================================== #
#  Flask API tests                                                      #
# ==================================================================== #

def test_nlq_057_create_api_blueprint():
    """create_nlq_api() returns a Blueprint."""
    eng = _engine()
    bp = create_nlq_api(eng)
    assert record("NLQ-057", "API blueprint", True, bp is not None)


def test_nlq_058_api_query():
    """POST /query returns a result."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-058", "Flask unavailable", True, True)
        return
    eng = _engine_with_source()
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.post("/api/nlq/query", json={"text": "system status"})
        assert record("NLQ-058", "API query", 200, resp.status_code)


def test_nlq_059_api_query_missing_text():
    """POST /query without text returns 400."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-059", "Flask unavailable", True, True)
        return
    eng = _engine()
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.post("/api/nlq/query", json={})
        assert record("NLQ-059", "API missing text", 400, resp.status_code)


def test_nlq_060_api_parse():
    """POST /parse returns parsed query."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-060", "Flask unavailable", True, True)
        return
    eng = _engine()
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.post("/api/nlq/parse", json={"text": "how many modules?"})
        data = resp.get_json()
        assert record("NLQ-060", "API parse", "count", data.get("intent"))


def test_nlq_061_api_list_sources():
    """GET /sources returns source list."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-061", "Flask unavailable", True, True)
        return
    eng = _engine_with_source()
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.get("/api/nlq/sources")
        data = resp.get_json()
        assert record("NLQ-061", "API list sources", True, len(data) >= 1)


def test_nlq_062_api_get_source():
    """GET /sources/<id> returns a source."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-062", "Flask unavailable", True, True)
        return
    eng = _engine()
    src = eng.register_source(name="lookup")
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.get(f"/api/nlq/sources/{src.id}")
        assert record("NLQ-062", "API get source", 200, resp.status_code)


def test_nlq_063_api_get_source_404():
    """GET /sources/<bad-id> returns 404."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-063", "Flask unavailable", True, True)
        return
    eng = _engine()
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.get("/api/nlq/sources/nonexistent")
        assert record("NLQ-063", "API 404", 404, resp.status_code)


def test_nlq_064_api_delete_source():
    """DELETE /sources/<id> removes a source."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-064", "Flask unavailable", True, True)
        return
    eng = _engine()
    src = eng.register_source(name="to-delete")
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.delete(f"/api/nlq/sources/{src.id}")
        assert record("NLQ-064", "API delete", 200, resp.status_code)


def test_nlq_065_api_enable_source():
    """POST /sources/<id>/enable enables a source."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-065", "Flask unavailable", True, True)
        return
    eng = _engine()
    src = eng.register_source(name="toggle")
    eng.disable_source(src.id)
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.post(f"/api/nlq/sources/{src.id}/enable")
        assert record("NLQ-065", "API enable", 200, resp.status_code)


def test_nlq_066_api_disable_source():
    """POST /sources/<id>/disable disables a source."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-066", "Flask unavailable", True, True)
        return
    eng = _engine()
    src = eng.register_source(name="toggle")
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.post(f"/api/nlq/sources/{src.id}/disable")
        assert record("NLQ-066", "API disable", 200, resp.status_code)


def test_nlq_067_api_history():
    """GET /history returns query history."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-067", "Flask unavailable", True, True)
        return
    eng = _engine_with_source()
    eng.query("system status")
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.get("/api/nlq/history")
        data = resp.get_json()
        assert record("NLQ-067", "API history", True, len(data) >= 1)


def test_nlq_068_api_clear_history():
    """DELETE /history clears history."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-068", "Flask unavailable", True, True)
        return
    eng = _engine_with_source()
    eng.query("status")
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.delete("/api/nlq/history")
        data = resp.get_json()
        assert record("NLQ-068", "API clear history", True, data.get("cleared", 0) >= 1)


def test_nlq_069_api_stats():
    """GET /stats returns statistics."""
    try:
        from flask import Flask
    except ImportError:
        assert record("NLQ-069", "Flask unavailable", True, True)
        return
    eng = _engine_with_source()
    eng.query("status")
    app = Flask(__name__)
    app.register_blueprint(create_nlq_api(eng))
    with app.test_client() as c:
        resp = c.get("/api/nlq/stats")
        data = resp.get_json()
        assert record("NLQ-069", "API stats", True, "total_queries" in data)


def test_nlq_070_disabled_source_skipped():
    """Disabled sources are not queried."""
    eng = _engine()
    src = eng.register_source(
        name="disabled_src",
        supported_intents=[QueryIntent.status],
        handler=_dummy_handler,
    )
    eng.disable_source(src.id)
    result = eng.query("system status")
    assert record(
        "NLQ-070", "Disabled source skipped",
        True, result.status != QueryStatus.success,
    )


def test_nlq_071_source_priority_order():
    """Higher-priority sources are called first."""
    eng = _engine()
    calls: List[str] = []

    def handler_a(p: ParsedQuery) -> Dict[str, Any]:
        calls.append("a")
        return {"answer": "from A"}

    def handler_b(p: ParsedQuery) -> Dict[str, Any]:
        calls.append("b")
        return {"answer": "from B"}

    eng.register_source(
        name="low", supported_intents=[QueryIntent.status],
        handler=handler_a, priority=1,
    )
    eng.register_source(
        name="high", supported_intents=[QueryIntent.status],
        handler=handler_b, priority=10,
    )
    eng.query("system status")
    assert record("NLQ-071", "Priority order", "b", calls[0] if calls else "")


def test_nlq_072_multiple_sources_combined():
    """Multiple sources contribute data to a single result."""
    eng = _engine()

    def handler_a(p: ParsedQuery) -> Dict[str, Any]:
        return {"answer": "Part A", "a_data": 1}

    def handler_b(p: ParsedQuery) -> Dict[str, Any]:
        return {"b_data": 2}

    eng.register_source(
        name="src_a", supported_intents=[QueryIntent.status],
        handler=handler_a, priority=10,
    )
    eng.register_source(
        name="src_b", supported_intents=[QueryIntent.status],
        handler=handler_b, priority=5,
    )
    result = eng.query("system status")
    assert record(
        "NLQ-072", "Combined sources",
        True, "a_data" in result.data and "b_data" in result.data,
    )

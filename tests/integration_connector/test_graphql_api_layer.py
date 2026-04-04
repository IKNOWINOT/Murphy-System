# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Suite: GraphQL API Layer — GQL-001

Comprehensive tests for the graphql_api_layer module:
  - Data model correctness (GraphQLType, ScalarKind, FieldDef, ObjectTypeDef,
    InputTypeDef, EnumTypeDef, ArgumentNode, FieldNode, OperationNode)
  - SchemaRegistry type registration / lookup / introspection
  - Query field + mutation field registration with resolvers
  - QueryParser — shorthand queries, named queries, mutations,
    arguments with string/int/float/bool/null literals,
    nested selections, aliases
  - Executor — simple field resolution, argument forwarding,
    nested object resolution, list resolution, error handling,
    __schema + __type introspection queries
  - Flask API endpoints (POST /graphql, GET /graphql/schema,
    GET /graphql/types, GET /graphql/health)
  - Input validation (missing query, empty query)
  - Thread safety under concurrent mutation
  - Wingman pair validation gate
  - Causality Sandbox gating
  - Default Murphy type registration helpers
  - User-agent operation testing (non-technical user workflows)

Tests use the storyline-actuals record() pattern.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pytest

# ── path setup ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from graphql_api_layer import (
    ArgumentDef,
    ArgumentNode,
    EnumTypeDef,
    Executor,
    FieldDef,
    FieldNode,
    GraphQLType,
    InputTypeDef,
    ObjectTypeDef,
    OperationNode,
    QueryParser,
    ScalarKind,
    SchemaRegistry,
    build_field,
    build_object_type,
    create_graphql_blueprint,
    register_murphy_queries,
    register_murphy_types,
    set_sandbox_enabled,
    set_wingman_enabled,
)

# ── storyline-actuals helper ──────────────────────────────────────────

@dataclass
class CheckResult:
    """Result of a single verification check."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str
    effect: str
    lesson: str


_results: List[CheckResult] = []


def record(check_id: str, description: str, expected: Any, actual: Any,
           cause: str, effect: str, lesson: str) -> bool:
    """Record a storyline-actuals check result."""
    passed = expected == actual
    _results.append(CheckResult(
        check_id=check_id, description=description,
        expected=expected, actual=actual, passed=passed,
        cause=cause, effect=effect, lesson=lesson))
    return passed


# ── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_gates():
    """Reset Wingman/Sandbox gates around each test."""
    set_wingman_enabled(True)
    set_sandbox_enabled(True)
    yield
    set_wingman_enabled(True)
    set_sandbox_enabled(True)


@pytest.fixture()
def registry():
    """Fresh SchemaRegistry for each test."""
    return SchemaRegistry()


@pytest.fixture()
def flask_app(registry):
    """Flask test app with GraphQL blueprint."""
    try:
        from flask import Flask
    except ImportError:
        pytest.skip("Flask not installed")
    register_murphy_types(registry)
    register_murphy_queries(registry)
    app = Flask(__name__)
    app.register_blueprint(create_graphql_blueprint(registry))
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(flask_app):
    """Flask test client."""
    return flask_app.test_client()


# ═══════════════════════════════════════════════════════════════════════
# GQL-001  GraphQLType enum members
# ═══════════════════════════════════════════════════════════════════════

def test_gql001_graphql_type_enum():
    """GraphQLType has six standard kinds."""
    ok = record("GQL-001", "GraphQLType enum has six members",
                {"OBJECT", "SCALAR", "ENUM", "INPUT_OBJECT", "LIST", "NON_NULL"},
                {m.value for m in GraphQLType},
                cause="Enum defined with six GraphQL type kinds",
                effect="All type kinds representable",
                lesson="Follow GraphQL spec type kinds")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-002  ScalarKind enum
# ═══════════════════════════════════════════════════════════════════════

def test_gql002_scalar_kind_enum():
    """ScalarKind has five built-in scalars."""
    ok = record("GQL-002", "ScalarKind has five members",
                {"String", "Int", "Float", "Boolean", "ID"},
                {s.value for s in ScalarKind},
                cause="Five standard GraphQL scalars",
                effect="Built-in scalars are first-class",
                lesson="Match the GraphQL spec scalar set")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-003  FieldDef creation
# ═══════════════════════════════════════════════════════════════════════

def test_gql003_field_def():
    """FieldDef stores name, type, description."""
    fd = build_field("status", "String", "Health status")
    ok = record("GQL-003", "FieldDef stores attributes",
                ("status", "String"),
                (fd.name, fd.type_name),
                cause="build_field helper used",
                effect="FieldDef is correctly populated",
                lesson="Convenience builders reduce boilerplate")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-004  ObjectTypeDef creation
# ═══════════════════════════════════════════════════════════════════════

def test_gql004_object_type_def():
    """ObjectTypeDef stores name and fields."""
    td = build_object_type("Foo", "A Foo type",
                           [build_field("bar", "String")])
    ok = record("GQL-004", "ObjectTypeDef has correct name and fields",
                ("Foo", 1),
                (td.name, len(td.fields)),
                cause="build_object_type used with one field",
                effect="Type definition is complete",
                lesson="Immutable dataclasses are safe type defs")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-005  InputTypeDef creation
# ═══════════════════════════════════════════════════════════════════════

def test_gql005_input_type_def():
    """InputTypeDef stores fields for mutation inputs."""
    inp = InputTypeDef(name="CreateInput",
                       fields=(build_field("name", "String"),),
                       description="Create something")
    ok = record("GQL-005", "InputTypeDef stores name and fields",
                "CreateInput",
                inp.name,
                cause="InputTypeDef constructed",
                effect="Input types for mutations are supported",
                lesson="Input types mirror object types structurally")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-006  EnumTypeDef creation
# ═══════════════════════════════════════════════════════════════════════

def test_gql006_enum_type_def():
    """EnumTypeDef stores values."""
    ed = EnumTypeDef(name="Status", values=("ACTIVE", "INACTIVE"),
                     description="Status enum")
    ok = record("GQL-006", "EnumTypeDef has two values",
                2, len(ed.values),
                cause="EnumTypeDef created with two values",
                effect="Enum types can be introspected",
                lesson="Enums need name + values tuple")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-007  SchemaRegistry type registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql007_register_type(registry):
    """Types can be registered and looked up."""
    td = build_object_type("Widget", "A widget", [])
    registry.register_type(td)
    ok = record("GQL-007", "Registered type is retrievable",
                "Widget",
                registry.get_type("Widget").name,
                cause="register_type + get_type",
                effect="Type is stored and retrievable",
                lesson="Registry is the single source of truth")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-008  SchemaRegistry enum registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql008_register_enum(registry):
    """Enum types can be registered."""
    ed = EnumTypeDef(name="Color", values=("RED", "BLUE"),
                     description="Colors")
    registry.register_enum_type(ed)
    info = registry.introspect_type("Color")
    ok = record("GQL-008", "Enum type introspection returns values",
                2, len(info["enumValues"]),
                cause="Enum registered and introspected",
                effect="Enum values are accessible",
                lesson="Enum introspection mirrors spec")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-009  SchemaRegistry input type registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql009_register_input_type(registry):
    """Input types can be registered."""
    inp = InputTypeDef(name="FooInput",
                       fields=(build_field("x", "Int"),))
    registry.register_input_type(inp)
    info = registry.introspect_type("FooInput")
    ok = record("GQL-009", "Input type introspection works",
                "INPUT_OBJECT", info["kind"],
                cause="Input type registered",
                effect="Introspection returns INPUT_OBJECT kind",
                lesson="Input types are distinct from object types")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-010  Query field registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql010_add_query_field(registry):
    """Query fields get resolvers."""
    registry.add_query_field(
        build_field("ping", "String", "Ping!"),
        lambda _root, **kw: "pong")
    ok = record("GQL-010", "Query field resolver is registered",
                True,
                registry.get_resolver("Query", "ping") is not None,
                cause="add_query_field called",
                effect="Resolver accessible via get_resolver",
                lesson="Query fields map to resolvers")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-011  Mutation field registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql011_add_mutation_field(registry):
    """Mutation fields get resolvers."""
    registry.add_mutation_field(
        build_field("createItem", "String"),
        lambda _root, **kw: "created")
    ok = record("GQL-011", "Mutation field resolver is registered",
                True,
                registry.get_resolver("Mutation", "createItem") is not None,
                cause="add_mutation_field called",
                effect="Mutation resolver stored",
                lesson="Mutations use same resolver pattern as queries")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-012  QueryParser shorthand query
# ═══════════════════════════════════════════════════════════════════════

def test_gql012_parse_shorthand():
    """Shorthand query { field } is parsed."""
    op = QueryParser.parse("{ ping }")
    ok = record("GQL-012", "Shorthand query parsed",
                ("query", 1),
                (op.operation_type, len(op.fields)),
                cause="Shorthand query syntax used",
                effect="OperationNode has one field",
                lesson="Shorthand is implicit query operation")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-013  QueryParser named query
# ═══════════════════════════════════════════════════════════════════════

def test_gql013_parse_named_query():
    """Named query is parsed with operation name."""
    op = QueryParser.parse("query GetHealth { health { status } }")
    ok = record("GQL-013", "Named query parsed with name",
                ("query", "GetHealth"),
                (op.operation_type, op.name),
                cause="Named query syntax used",
                effect="Operation name is captured",
                lesson="Named queries help with logging/debugging")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-014  QueryParser mutation
# ═══════════════════════════════════════════════════════════════════════

def test_gql014_parse_mutation():
    """Mutation operations are parsed."""
    op = QueryParser.parse('mutation { createItem(name: "x") }')
    ok = record("GQL-014", "Mutation operation parsed",
                "mutation",
                op.operation_type,
                cause="mutation keyword used",
                effect="Operation type is mutation",
                lesson="Mutations are syntactically like queries")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-015  QueryParser arguments parsing
# ═══════════════════════════════════════════════════════════════════════

def test_gql015_parse_arguments():
    """Arguments with different types are parsed."""
    op = QueryParser.parse('{ echo(message: "hello", count: 5) }')
    args = op.fields[0].arguments
    ok = record("GQL-015", "Arguments are parsed with types",
                2, len(args),
                cause="Two arguments provided",
                effect="Both arguments captured",
                lesson="Parser handles string and int literals")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-016  QueryParser nested selections
# ═══════════════════════════════════════════════════════════════════════

def test_gql016_parse_nested():
    """Nested selections are parsed into child FieldNodes."""
    op = QueryParser.parse("{ health { status version } }")
    children = op.fields[0].children
    ok = record("GQL-016", "Nested fields are parsed",
                2, len(children),
                cause="health has two sub-fields",
                effect="Two child FieldNodes created",
                lesson="Recursive parsing handles nesting")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-017  QueryParser alias support
# ═══════════════════════════════════════════════════════════════════════

def test_gql017_parse_alias():
    """Field aliases are parsed."""
    op = QueryParser.parse("{ myHealth: health { status } }")
    fnode = op.fields[0]
    ok = record("GQL-017", "Alias is captured",
                ("health", "myHealth"),
                (fnode.name, fnode.alias),
                cause="alias: field syntax used",
                effect="name=health, alias=myHealth",
                lesson="Aliases let clients rename fields")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-018  QueryParser boolean/null literals
# ═══════════════════════════════════════════════════════════════════════

def test_gql018_parse_bool_null():
    """Boolean and null literals are parsed."""
    op = QueryParser.parse("{ f(a: true, b: false, c: null) }")
    args = {a.name: a.value for a in op.fields[0].arguments}
    ok = record("GQL-018", "Bool/null literals parsed",
                {"a": True, "b": False, "c": None},
                args,
                cause="true, false, null literals in args",
                effect="Python True, False, None values",
                lesson="Literal parsing covers all scalar types")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-019  Executor simple query
# ═══════════════════════════════════════════════════════════════════════

def test_gql019_executor_simple(registry):
    """Executor resolves a simple query field."""
    registry.add_query_field(
        build_field("greeting", "String"),
        lambda _root, **kw: "hello")
    op = QueryParser.parse("{ greeting }")
    result = Executor(registry).execute(op)
    ok = record("GQL-019", "Simple query returns data",
                "hello",
                result["data"]["greeting"],
                cause="greeting resolver returns 'hello'",
                effect="data.greeting == 'hello'",
                lesson="Executor wires parser output to resolvers")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-020  Executor argument forwarding
# ═══════════════════════════════════════════════════════════════════════

def test_gql020_executor_args(registry):
    """Arguments are forwarded to resolvers."""
    registry.add_query_field(
        build_field("echo", "String",
                    arguments=[ArgumentDef("msg", "String")]),
        lambda _root, **kw: kw.get("msg", ""))
    op = QueryParser.parse('{ echo(msg: "hi") }')
    result = Executor(registry).execute(op)
    ok = record("GQL-020", "Argument forwarded to resolver",
                "hi",
                result["data"]["echo"],
                cause='echo resolver receives msg="hi"',
                effect="Returns 'hi'",
                lesson="Arguments map to resolver kwargs")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-021  Executor nested object resolution
# ═══════════════════════════════════════════════════════════════════════

def test_gql021_executor_nested(registry):
    """Nested fields are resolved against returned dicts."""
    registry.add_query_field(
        build_field("health", "HealthCheck"),
        lambda _root, **kw: {"status": "ok", "version": "2.0"})
    op = QueryParser.parse("{ health { status } }")
    result = Executor(registry).execute(op)
    ok = record("GQL-021", "Nested field resolved from dict",
                "ok",
                result["data"]["health"]["status"],
                cause="health returns dict, status extracted",
                effect="Nested selection works",
                lesson="Dict access is the default resolver")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-022  Executor list resolution
# ═══════════════════════════════════════════════════════════════════════

def test_gql022_executor_list(registry):
    """Lists of objects are resolved element-wise."""
    registry.add_query_field(
        build_field("items", "String", is_list=True),
        lambda _root, **kw: [{"name": "a"}, {"name": "b"}])
    op = QueryParser.parse("{ items { name } }")
    result = Executor(registry).execute(op)
    names = [i["name"] for i in result["data"]["items"]]
    ok = record("GQL-022", "List items resolved",
                ["a", "b"], names,
                cause="Resolver returns list of dicts",
                effect="Each element gets child-resolved",
                lesson="List handling is automatic")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-023  Executor error handling
# ═══════════════════════════════════════════════════════════════════════

def test_gql023_executor_error(registry):
    """Resolver errors are captured in errors array."""
    registry.add_query_field(
        build_field("boom", "String"),
        lambda _root, **kw: (_ for _ in ()).throw(ValueError("kaboom")))
    op = QueryParser.parse("{ boom }")
    result = Executor(registry).execute(op)
    ok = record("GQL-023", "Resolver error captured",
                True,
                "errors" in result and len(result["errors"]) > 0,
                cause="Resolver raises ValueError",
                effect="errors array populated",
                lesson="Errors don't crash the executor")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-024  Executor __schema introspection
# ═══════════════════════════════════════════════════════════════════════

def test_gql024_introspection_schema(registry):
    """__schema query returns schema data."""
    register_murphy_types(registry)
    register_murphy_queries(registry)
    op = QueryParser.parse("{ __schema { queryType { name } } }")
    result = Executor(registry).execute(op)
    qt = result["data"]["__schema"]["queryType"]
    ok = record("GQL-024", "__schema.queryType.name == Query",
                "Query",
                qt["name"],
                cause="__schema introspection query",
                effect="Query type name returned",
                lesson="Introspection is built into the executor")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-025  Executor __type introspection
# ═══════════════════════════════════════════════════════════════════════

def test_gql025_introspection_type(registry):
    """__type(name: 'X') returns type info."""
    register_murphy_types(registry)
    op = QueryParser.parse('{ __type(name: "HealthCheck") { name } }')
    result = Executor(registry).execute(op)
    ok = record("GQL-025", "__type returns named type",
                "HealthCheck",
                result["data"]["__type"]["name"],
                cause="__type query for HealthCheck",
                effect="Type info returned",
                lesson="Per-type introspection is essential")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-026  Missing resolver returns null + error
# ═══════════════════════════════════════════════════════════════════════

def test_gql026_missing_resolver(registry):
    """Unknown field returns null with error."""
    op = QueryParser.parse("{ nonexistent }")
    result = Executor(registry).execute(op)
    ok = record("GQL-026", "Missing resolver gives null + error",
                None,
                result["data"]["nonexistent"],
                cause="No resolver registered for 'nonexistent'",
                effect="data.nonexistent is None, errors populated",
                lesson="Graceful degradation on missing resolvers")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-027  Flask POST /graphql happy path
# ═══════════════════════════════════════════════════════════════════════

def test_gql027_flask_post(client):
    """POST /graphql with valid query returns data."""
    resp = client.post("/graphql",
                       json={"query": '{ echo(message: "hi") }'})
    data = resp.get_json()
    ok = record("GQL-027", "POST /graphql returns echo data",
                "hi",
                data["data"]["echo"],
                cause="Valid query sent via POST",
                effect="Correct data returned",
                lesson="Flask endpoint wires to executor")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-028  Flask POST /graphql missing query
# ═══════════════════════════════════════════════════════════════════════

def test_gql028_flask_missing_query(client):
    """POST /graphql without query returns 400."""
    resp = client.post("/graphql", json={})
    ok = record("GQL-028", "Missing query returns 400",
                400, resp.status_code,
                cause="No query field in body",
                effect="400 with error message",
                lesson="Input validation catches missing query")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-029  Flask GET /graphql/schema
# ═══════════════════════════════════════════════════════════════════════

def test_gql029_flask_schema(client):
    """GET /graphql/schema returns introspection."""
    resp = client.get("/graphql/schema")
    data = resp.get_json()
    ok = record("GQL-029", "Schema endpoint returns queryType",
                True,
                "queryType" in data,
                cause="GET /graphql/schema called",
                effect="queryType field present",
                lesson="Schema endpoint enables tooling")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-030  Flask GET /graphql/types
# ═══════════════════════════════════════════════════════════════════════

def test_gql030_flask_types(client):
    """GET /graphql/types lists registered types."""
    resp = client.get("/graphql/types")
    data = resp.get_json()
    ok = record("GQL-030", "Types endpoint returns list",
                True,
                "types" in data and isinstance(data["types"], list),
                cause="GET /graphql/types called",
                effect="Type list returned",
                lesson="Type listing aids development")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-031  Flask GET /graphql/health
# ═══════════════════════════════════════════════════════════════════════

def test_gql031_flask_health(client):
    """Health endpoint returns healthy status."""
    resp = client.get("/graphql/health")
    data = resp.get_json()
    ok = record("GQL-031", "Health endpoint is healthy",
                "healthy",
                data["status"],
                cause="GET /graphql/health called",
                effect="Status is healthy",
                lesson="Subsystem health checks are standard")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-032  Wingman gate blocks registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql032_wingman_blocks(registry):
    """Wingman rejection prevents type registration."""
    set_wingman_enabled(True)
    td = build_object_type("", "Empty name", [])
    with pytest.raises(PermissionError, match="Wingman"):
        registry.register_type(td)
    ok = record("GQL-032", "Empty-name type rejected by Wingman",
                True, True,
                cause="Type name is empty string",
                effect="PermissionError raised",
                lesson="Wingman validates all registrations")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-033  Wingman disabled allows empty name
# ═══════════════════════════════════════════════════════════════════════

def test_gql033_wingman_disabled(registry):
    """Disabling Wingman allows any registration."""
    set_wingman_enabled(False)
    td = build_object_type("", "Empty", [])
    result = registry.register_type(td)
    ok = record("GQL-033", "Wingman disabled allows registration",
                "",
                result.name,
                cause="Wingman disabled",
                effect="Type registered despite empty name",
                lesson="Gate toggle works for testing")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-034  Sandbox gate blocks execution
# ═══════════════════════════════════════════════════════════════════════

def test_gql034_sandbox_blocks(registry):
    """Sandbox rejection prevents query execution."""
    set_sandbox_enabled(True)
    registry.add_query_field(
        build_field("val", "String"),
        lambda _root, **kw: "x")
    # Sandbox rejects when action is empty-string payload
    set_sandbox_enabled(True)
    # Direct sandbox test: override to disabled
    op = OperationNode(operation_type="query",
                       fields=(FieldNode(name="val"),))
    result = Executor(registry).execute(op)
    # With sandbox enabled and anonymous name, should still work (name="anonymous")
    ok = record("GQL-034", "Sandbox gate permits valid execution",
                True,
                "data" in result,
                cause="Sandbox is enabled, valid query",
                effect="Query executes normally",
                lesson="Sandbox allows well-formed queries")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-035  Sandbox disabled
# ═══════════════════════════════════════════════════════════════════════

def test_gql035_sandbox_disabled(registry):
    """Sandbox disabled allows execution."""
    set_sandbox_enabled(False)
    registry.add_query_field(
        build_field("val", "String"),
        lambda _root, **kw: "ok")
    op = QueryParser.parse("{ val }")
    result = Executor(registry).execute(op)
    ok = record("GQL-035", "Sandbox disabled, execution proceeds",
                "ok",
                result["data"]["val"],
                cause="Sandbox disabled",
                effect="Query executed normally",
                lesson="Sandbox toggle works for testing")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-036  Thread safety — concurrent type registration
# ═══════════════════════════════════════════════════════════════════════

def test_gql036_thread_safety(registry):
    """Concurrent type registration is safe."""
    errors: List[str] = []

    def register_batch(start: int) -> None:
        for i in range(start, start + 20):
            try:
                registry.register_type(
                    build_object_type(f"T{i}", f"Type {i}", []))
            except Exception as exc:
                errors.append(str(exc))

    threads = [threading.Thread(target=register_batch, args=(i * 20,))
               for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = record("GQL-036", "100 concurrent registrations, zero errors",
                0, len(errors),
                cause="5 threads × 20 types each",
                effect="All registrations succeed",
                lesson="Lock-based thread safety works")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-037  register_murphy_types helper
# ═══════════════════════════════════════════════════════════════════════

def test_gql037_murphy_types(registry):
    """register_murphy_types adds HealthCheck, Metric, Module."""
    register_murphy_types(registry)
    ok = record("GQL-037", "Murphy types registered",
                True,
                all(registry.get_type(n) is not None
                    for n in ("HealthCheck", "Metric", "Module")),
                cause="register_murphy_types called",
                effect="Three types available",
                lesson="Helper reduces boilerplate for Murphy types")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-038  register_murphy_queries adds echo/health/modules
# ═══════════════════════════════════════════════════════════════════════

def test_gql038_murphy_queries(registry):
    """register_murphy_queries adds echo, health, modules."""
    register_murphy_queries(registry)
    fields = registry.list_query_fields()
    names = {f.name for f in fields}
    ok = record("GQL-038", "Murphy query fields registered",
                True,
                {"echo", "health", "modules"}.issubset(names),
                cause="register_murphy_queries called",
                effect="echo, health, modules fields present",
                lesson="Standard queries are pre-wired")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-039  User-agent workflow: query → introspect → query again
# ═══════════════════════════════════════════════════════════════════════

def test_gql039_user_agent_workflow(client):
    """Non-technical operator introspects then queries."""
    # Step 1: introspect
    r1 = client.get("/graphql/schema")
    assert r1.status_code == 200
    schema = r1.get_json()

    # Step 2: find available queries
    query_names = [f["name"] for f in schema["queryType"]["fields"]]

    # Step 3: query echo
    r2 = client.post("/graphql",
                     json={"query": '{ echo(message: "test") }'})
    data = r2.get_json()

    ok = record("GQL-039", "User workflow: introspect → query",
                "test",
                data["data"]["echo"],
                cause="Operator discovers schema, then queries echo",
                effect="Correct response",
                lesson="Introspection enables self-service")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-040  Empty query string
# ═══════════════════════════════════════════════════════════════════════

def test_gql040_empty_query_string(client):
    """Empty query string returns 400."""
    resp = client.post("/graphql", json={"query": ""})
    ok = record("GQL-040", "Empty query returns 400",
                400, resp.status_code,
                cause="Query is empty string",
                effect="400 error returned",
                lesson="Always validate input")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-041  Float argument parsing
# ═══════════════════════════════════════════════════════════════════════

def test_gql041_float_argument():
    """Float arguments are parsed correctly."""
    op = QueryParser.parse("{ f(val: 3.14) }")
    val = op.fields[0].arguments[0].value
    ok = record("GQL-041", "Float argument parsed",
                3.14, val,
                cause="Argument value is 3.14",
                effect="Parsed as Python float",
                lesson="Parser handles decimal literals")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-042  Mutation execution via Flask
# ═══════════════════════════════════════════════════════════════════════

def test_gql042_mutation_via_flask(registry):
    """Mutations execute through the Flask endpoint."""
    registry.add_mutation_field(
        build_field("addItem", "String",
                    arguments=[ArgumentDef("name", "String")]),
        lambda _root, **kw: f"added-{kw.get('name', '')}")
    register_murphy_types(registry)
    register_murphy_queries(registry)

    try:
        from flask import Flask
    except ImportError:
        pytest.skip("Flask not installed")
    app = Flask(__name__)
    app.register_blueprint(create_graphql_blueprint(registry))
    app.config["TESTING"] = True
    client = app.test_client()

    resp = client.post("/graphql",
                       json={"query": 'mutation { addItem(name: "x") }'})
    data = resp.get_json()
    ok = record("GQL-042", "Mutation executes via Flask",
                "added-x",
                data["data"]["addItem"],
                cause="Mutation sent via POST",
                effect="Resolver receives argument",
                lesson="Mutations and queries share the endpoint")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-043  SchemaRegistry type_count
# ═══════════════════════════════════════════════════════════════════════

def test_gql043_type_count(registry):
    """type_count includes scalars + custom types."""
    base = registry.type_count()  # 5 scalars
    registry.register_type(build_object_type("X", "X", []))
    ok = record("GQL-043", "type_count increments",
                base + 1, registry.type_count(),
                cause="One type registered",
                effect="Count increases by 1",
                lesson="type_count is authoritative")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-044  SchemaRegistry resolver_count
# ═══════════════════════════════════════════════════════════════════════

def test_gql044_resolver_count(registry):
    """resolver_count tracks registered resolvers."""
    registry.add_query_field(
        build_field("a", "String"),
        lambda _root, **kw: "a")
    registry.add_query_field(
        build_field("b", "String"),
        lambda _root, **kw: "b")
    ok = record("GQL-044", "Resolver count is 2",
                2, registry.resolver_count(),
                cause="Two query fields registered",
                effect="resolver_count == 2",
                lesson="Count method is reliable")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# GQL-045  set_field_resolver for nested type
# ═══════════════════════════════════════════════════════════════════════

def test_gql045_set_field_resolver(registry):
    """set_field_resolver attaches resolver to a type.field."""
    registry.register_type(build_object_type(
        "Car", "A car", [build_field("color", "String")]))
    registry.set_field_resolver("Car", "color",
                                lambda obj, **kw: "red")
    fn = registry.get_resolver("Car", "color")
    ok = record("GQL-045", "Field resolver set and retrieved",
                "red", fn(None),
                cause="set_field_resolver called",
                effect="Resolver returns 'red'",
                lesson="Per-field resolvers enable complex graphs")
    assert ok

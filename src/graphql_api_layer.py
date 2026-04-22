# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
GraphQL API Layer — GQL-001

Lightweight, stdlib-only GraphQL execution engine that wraps existing
Murphy REST endpoints behind a single ``/graphql`` entrypoint.
Non-technical operators can query system state with a simple JSON POST
instead of memorising many REST routes.

Design Principles
─────────────────
- Schema-first: define ObjectTypes, Fields, Arguments and InputTypes as
  plain dataclasses — no external ``graphql-core`` dependency.
- Resolver registry maps ``TypeName.fieldName`` to Python callables.
- Query parser turns incoming GraphQL strings into an AST of
  OperationNode / FieldNode / ArgumentNode objects.
- Execution engine walks the AST, calls resolvers, and returns a
  ``{"data": …, "errors": …}`` response.
- Introspection: ``__schema`` and ``__type(name:)`` queries are
  supported out-of-the-box.
- Flask blueprint exposes ``POST /graphql`` (JSON body) and
  ``GET /graphql/schema`` (human-readable schema dump).
- Wingman pair validation gates every resolver registration.
- Causality Sandbox gating simulates execution side-effects.
- Thread-safe: all mutable state protected by locks.
- ≤ 800 source lines, no external deps beyond stdlib + Flask.

Key Classes
───────────
  GraphQLType          — enum of OBJECT / SCALAR / ENUM / INPUT / LIST
  ScalarKind           — enum of built-in scalar names
  FieldDef             — field definition with name, type, args, doc
  ObjectTypeDef        — object type with name, fields, doc
  InputTypeDef         — input type for mutations
  ArgumentNode         — parsed argument from a query
  FieldNode            — parsed field selection from a query
  OperationNode        — parsed top-level operation (query / mutation)
  SchemaRegistry       — stores type defs + resolver functions
  QueryParser          — turns GraphQL text → OperationNode
  Executor             — walks AST + calls resolvers → result dict
  GraphQLAPI           — Flask blueprint factory

Copyright © 2020 Inoni Limited Liability Company

.. deprecated::
    This module is **experimental** and slated for removal. See
    `docs/adr/0008-graphql-layer-experimental.md` for the rationale and
    removal schedule. Importing this module emits a ``DeprecationWarning``.
    No internal HTTP route is wired to it; it has no current consumers.
    If you need GraphQL going forward, the planned replacement is
    ``strawberry`` per ADR-0008.
"""
from __future__ import annotations

import json
import logging
import warnings

# Class S Roadmap, Item 13 (per ADR-0008): mark this module experimental
# and emit a DeprecationWarning at import time so any out-of-tree caller
# becomes visible in their own CI before the module is finally removed.
__experimental__ = True
warnings.warn(
    "src.graphql_api_layer is experimental and slated for removal; see "
    "docs/adr/0008-graphql-layer-experimental.md. Replace with `strawberry` "
    "if you need a real GraphQL surface.",
    DeprecationWarning,
    stacklevel=2,
)
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ── Wingman / Sandbox stubs (real wiring when available) ─────────────
_WINGMAN_ENABLED = True
_SANDBOX_ENABLED = True


def set_wingman_enabled(flag: bool) -> None:
    """Toggle Wingman validation gate."""
    global _WINGMAN_ENABLED
    _WINGMAN_ENABLED = flag


def set_sandbox_enabled(flag: bool) -> None:
    """Toggle Causality Sandbox gate."""
    global _SANDBOX_ENABLED
    _SANDBOX_ENABLED = flag


def _wingman_validate(action: str, payload: Dict[str, Any]) -> bool:
    """Return True when Wingman pair approves *action*."""
    if not _WINGMAN_ENABLED:
        return True
    if not (bool(action) and isinstance(payload, dict)):
        return False
    name = payload.get("name", "")
    return bool(name)


def _sandbox_simulate(action: str, payload: Dict[str, Any]) -> bool:
    """Return True when Causality Sandbox allows *action*."""
    if not _SANDBOX_ENABLED:
        return True
    if not (bool(action) and isinstance(payload, dict)):
        return False
    return True


# ── Enums ────────────────────────────────────────────────────────────

class GraphQLType(str, Enum):
    """Kind of GraphQL type."""
    OBJECT = "OBJECT"
    SCALAR = "SCALAR"
    ENUM = "ENUM"
    INPUT_OBJECT = "INPUT_OBJECT"
    LIST = "LIST"
    NON_NULL = "NON_NULL"


class ScalarKind(str, Enum):
    """Built-in scalar type names."""
    STRING = "String"
    INT = "Int"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    ID = "ID"


# ── Data Models ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ArgumentDef:
    """Argument definition on a field."""
    name: str
    type_name: str
    default_value: Any = None
    description: str = ""


@dataclass(frozen=True)
class FieldDef:
    """Field definition inside an ObjectType or InputType."""
    name: str
    type_name: str
    description: str = ""
    arguments: Tuple[ArgumentDef, ...] = ()
    is_list: bool = False
    is_non_null: bool = False


@dataclass(frozen=True)
class ObjectTypeDef:
    """GraphQL Object Type definition."""
    name: str
    fields: Tuple[FieldDef, ...]
    description: str = ""


@dataclass(frozen=True)
class InputTypeDef:
    """GraphQL Input Type definition."""
    name: str
    fields: Tuple[FieldDef, ...]
    description: str = ""


@dataclass(frozen=True)
class EnumTypeDef:
    """GraphQL Enum Type definition."""
    name: str
    values: Tuple[str, ...]
    description: str = ""


# ── AST Nodes (parser output) ───────────────────────────────────────

@dataclass(frozen=True)
class ArgumentNode:
    """Parsed argument from a query."""
    name: str
    value: Any


@dataclass
class FieldNode:
    """Parsed field selection."""
    name: str
    alias: Optional[str] = None
    arguments: Tuple[ArgumentNode, ...] = ()
    children: Tuple["FieldNode", ...] = ()


@dataclass
class OperationNode:
    """Parsed top-level operation."""
    operation_type: str  # "query" or "mutation"
    name: Optional[str] = None
    fields: Tuple[FieldNode, ...] = ()
    variables: Dict[str, Any] = field(default_factory=dict)


# ── Resolver type alias ─────────────────────────────────────────────
ResolverFn = Callable[..., Any]


# ── Schema Registry ─────────────────────────────────────────────────

class SchemaRegistry:
    """Central store for type definitions and resolver functions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._types: Dict[str, ObjectTypeDef] = {}
        self._input_types: Dict[str, InputTypeDef] = {}
        self._enum_types: Dict[str, EnumTypeDef] = {}
        self._resolvers: Dict[str, ResolverFn] = {}
        self._query_fields: Dict[str, FieldDef] = {}
        self._mutation_fields: Dict[str, FieldDef] = {}
        self._register_scalars()

    def _register_scalars(self) -> None:
        """Pre-register built-in scalar types as stub ObjectTypeDefs."""
        for s in ScalarKind:
            self._types[s.value] = ObjectTypeDef(
                name=s.value, fields=(), description=f"Built-in {s.value} scalar")

    # ── type registration ────────────────────────────────────────

    def register_type(self, typedef: ObjectTypeDef) -> ObjectTypeDef:
        """Register an Object Type. Wingman-gated."""
        if not _wingman_validate("register_type",
                                 {"name": typedef.name}):
            raise PermissionError("Wingman rejected type registration")
        if not _sandbox_simulate("register_type",
                                 {"name": typedef.name}):
            raise RuntimeError("Sandbox rejected type registration")
        with self._lock:
            self._types[typedef.name] = typedef
        return typedef

    def register_input_type(self, typedef: InputTypeDef) -> InputTypeDef:
        """Register an Input Type."""
        if not _wingman_validate("register_input",
                                 {"name": typedef.name}):
            raise PermissionError("Wingman rejected input registration")
        with self._lock:
            self._input_types[typedef.name] = typedef
        return typedef

    def register_enum_type(self, typedef: EnumTypeDef) -> EnumTypeDef:
        """Register an Enum Type."""
        if not _wingman_validate("register_enum",
                                 {"name": typedef.name}):
            raise PermissionError("Wingman rejected enum registration")
        with self._lock:
            self._enum_types[typedef.name] = typedef
        return typedef

    # ── query / mutation field registration ───────────────────────

    def add_query_field(self, fdef: FieldDef,
                        resolver: ResolverFn) -> None:
        """Add a root Query field with its resolver."""
        if not _wingman_validate("add_query_field",
                                 {"name": fdef.name}):
            raise PermissionError("Wingman rejected query field")
        key = f"Query.{fdef.name}"
        with self._lock:
            self._query_fields[fdef.name] = fdef
            self._resolvers[key] = resolver

    def add_mutation_field(self, fdef: FieldDef,
                           resolver: ResolverFn) -> None:
        """Add a root Mutation field with its resolver."""
        if not _wingman_validate("add_mutation_field",
                                 {"name": fdef.name}):
            raise PermissionError("Wingman rejected mutation field")
        key = f"Mutation.{fdef.name}"
        with self._lock:
            self._mutation_fields[fdef.name] = fdef
            self._resolvers[key] = resolver

    def set_field_resolver(self, type_name: str, field_name: str,
                           resolver: ResolverFn) -> None:
        """Attach a resolver to a specific type field."""
        key = f"{type_name}.{field_name}"
        with self._lock:
            self._resolvers[key] = resolver

    # ── lookups ──────────────────────────────────────────────────

    def get_type(self, name: str) -> Optional[ObjectTypeDef]:
        """Look up a registered type by name."""
        with self._lock:
            return self._types.get(name)

    def get_resolver(self, type_name: str,
                     field_name: str) -> Optional[ResolverFn]:
        """Look up a resolver for type.field."""
        key = f"{type_name}.{field_name}"
        with self._lock:
            return self._resolvers.get(key)

    def type_count(self) -> int:
        """Number of registered types."""
        with self._lock:
            return len(self._types)

    def resolver_count(self) -> int:
        """Number of registered resolvers."""
        with self._lock:
            return len(self._resolvers)

    def list_query_fields(self) -> List[FieldDef]:
        """Return all root Query field definitions."""
        with self._lock:
            return list(self._query_fields.values())

    def list_mutation_fields(self) -> List[FieldDef]:
        """Return all root Mutation field definitions."""
        with self._lock:
            return list(self._mutation_fields.values())

    # ── introspection helpers ────────────────────────────────────

    def introspect_schema(self) -> Dict[str, Any]:
        """Return introspection data for __schema."""
        with self._lock:
            types_out = []
            for td in self._types.values():
                types_out.append(self._introspect_type(td))
            for ed in self._enum_types.values():
                types_out.append({
                    "kind": GraphQLType.ENUM.value,
                    "name": ed.name,
                    "description": ed.description,
                    "enumValues": [{"name": v} for v in ed.values],
                })
            for inp in self._input_types.values():
                types_out.append(self._introspect_input(inp))
            query_fields = self._fmt_fields(self._query_fields)
            mutation_fields = self._fmt_fields(self._mutation_fields)
        return {
            "queryType": {"name": "Query", "fields": query_fields},
            "mutationType": ({"name": "Mutation",
                              "fields": mutation_fields}
                             if mutation_fields else None),
            "types": types_out,
        }

    @staticmethod
    def _introspect_type(td: ObjectTypeDef) -> Dict[str, Any]:
        """Format an ObjectTypeDef for introspection."""
        return {
            "kind": GraphQLType.OBJECT.value,
            "name": td.name,
            "description": td.description,
            "fields": [{"name": f.name, "type": f.type_name,
                         "description": f.description}
                        for f in td.fields],
        }

    @staticmethod
    def _introspect_input(td: InputTypeDef) -> Dict[str, Any]:
        """Format an InputTypeDef for introspection."""
        return {
            "kind": GraphQLType.INPUT_OBJECT.value,
            "name": td.name,
            "description": td.description,
            "inputFields": [{"name": f.name, "type": f.type_name}
                             for f in td.fields],
        }

    @staticmethod
    def _fmt_fields(fields: Dict[str, FieldDef]) -> List[Dict[str, Any]]:
        """Format field defs for introspection."""
        out: List[Dict[str, Any]] = []
        for fd in fields.values():
            out.append({
                "name": fd.name,
                "type": fd.type_name,
                "description": fd.description,
                "args": [{"name": a.name, "type": a.type_name}
                         for a in fd.arguments],
            })
        return out

    def introspect_type(self, name: str) -> Optional[Dict[str, Any]]:
        """Return introspection data for a single named type."""
        with self._lock:
            td = self._types.get(name)
            if td:
                return self._introspect_type(td)
            ed = self._enum_types.get(name)
            if ed:
                return {
                    "kind": GraphQLType.ENUM.value,
                    "name": ed.name,
                    "description": ed.description,
                    "enumValues": [{"name": v} for v in ed.values],
                }
            inp = self._input_types.get(name)
            if inp:
                return self._introspect_input(inp)
        return None


# ── Query Parser ─────────────────────────────────────────────────────

# Minimal parser for: query [Name] { field(arg:val) { sub } }
# Handles string, int, float, bool literals and nested selections.

_RE_OP = re.compile(
    r"^\s*\b(query|mutation)\b\s*(\w+)?\s*\{", re.IGNORECASE)
_RE_FIELD = re.compile(
    r"(\w+)\s*(?::\s*(\w+))?\s*(?:\(([^)]*)\))?\s*(\{)?")
_RE_ARG = re.compile(
    r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|[\w.+-]+)')


def _parse_value(raw: str) -> Any:
    """Convert a raw string token into a Python value."""
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        logger.debug("Cannot parse %r as int, trying float", raw)
    try:
        return float(raw)
    except ValueError:
        logger.debug("Cannot parse %r as float, returning as string", raw)
    return raw


def _parse_arguments(text: str) -> Tuple[ArgumentNode, ...]:
    """Parse `key: value, …` argument text into ArgumentNodes."""
    args: List[ArgumentNode] = []
    for m in _RE_ARG.finditer(text):
        args.append(ArgumentNode(name=m.group(1),
                                 value=_parse_value(m.group(2))))
    return tuple(args)


def _parse_selection_set(text: str, pos: int) -> Tuple[Tuple[FieldNode, ...], int]:
    """Parse fields inside { … } starting from *pos*."""
    fields: List[FieldNode] = []
    length = len(text)
    while pos < length:
        # skip whitespace and commas
        while pos < length and text[pos] in " \t\n\r,":
            pos += 1
        if pos >= length or text[pos] == "}":
            pos += 1  # consume closing brace
            break
        m = _RE_FIELD.match(text, pos)
        if not m:
            pos += 1
            continue
        pos = m.end()
        raw_name = m.group(1)
        alias_part = m.group(2)
        args_text = m.group(3) or ""
        has_children = m.group(4) is not None
        # handle alias: `alias: fieldName` pattern
        if alias_part:
            alias = raw_name
            name = alias_part
        else:
            alias = None
            name = raw_name
        arguments = _parse_arguments(args_text)
        children: Tuple[FieldNode, ...] = ()
        if has_children:
            children, pos = _parse_selection_set(text, pos)
        fields.append(FieldNode(name=name, alias=alias,
                                arguments=arguments,
                                children=children))
    return tuple(fields), pos


class QueryParser:
    """Parse GraphQL query text into OperationNode AST."""

    @staticmethod
    def parse(text: str,
              variables: Optional[Dict[str, Any]] = None) -> OperationNode:
        """Parse *text* into an OperationNode."""
        text = text.strip()
        variables = variables or {}
        op_match = _RE_OP.search(text)
        if op_match:
            op_type = op_match.group(1).lower()
            op_name = op_match.group(2)
            start = op_match.end()
        else:
            # shorthand query: `{ field … }`
            op_type = "query"
            op_name = None
            brace = text.find("{")
            if brace == -1:
                return OperationNode(operation_type="query")
            start = brace + 1
        fields, _ = _parse_selection_set(text, start)
        return OperationNode(operation_type=op_type, name=op_name,
                             fields=fields, variables=variables)


# ── Executor ─────────────────────────────────────────────────────────

class Executor:
    """Walk an OperationNode AST and call resolvers."""

    def __init__(self, registry: SchemaRegistry) -> None:
        self._registry = registry

    def execute(self, op: OperationNode) -> Dict[str, Any]:
        """Execute the operation and return GraphQL response dict."""
        if not _sandbox_simulate("execute_query",
                                 {"name": op.name or "anonymous"}):
            return {"data": None,
                    "errors": [{"message": "Sandbox rejected execution"}]}
        root_type = ("Query" if op.operation_type == "query"
                     else "Mutation")
        data: Dict[str, Any] = {}
        errors: List[Dict[str, Any]] = []
        for fnode in op.fields:
            key = fnode.alias or fnode.name
            if fnode.name == "__schema":
                data[key] = self._registry.introspect_schema()
                continue
            if fnode.name == "__type":
                type_name = _arg_value(fnode.arguments, "name")
                data[key] = self._registry.introspect_type(
                    str(type_name)) if type_name else None
                continue
            result, err = self._resolve_field(
                root_type, fnode, None)
            if err:
                errors.append(err)
            data[key] = result
        out: Dict[str, Any] = {"data": data}
        if errors:
            out["errors"] = errors
        return out

    def _resolve_field(self, parent_type: str,
                       fnode: FieldNode,
                       parent_obj: Any) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Resolve a single field node."""
        resolver = self._registry.get_resolver(parent_type, fnode.name)
        if resolver is None:
            # try default dict/attr access on parent
            if isinstance(parent_obj, dict):
                value = parent_obj.get(fnode.name)
            elif parent_obj is not None and hasattr(parent_obj, fnode.name):
                value = getattr(parent_obj, fnode.name)
            else:
                return None, {"message": f"No resolver for "
                              f"{parent_type}.{fnode.name}",
                              "path": [fnode.name]}
            return self._resolve_children(fnode, value), None
        kwargs = _args_to_kwargs(fnode.arguments)
        try:
            value = resolver(parent_obj, **kwargs)
        except Exception as exc:
            logger.warning("Resolver %s.%s error: %s",
                           parent_type, fnode.name, exc)
            return None, {"message": str(exc),
                          "path": [fnode.name]}
        return self._resolve_children(fnode, value), None

    def _resolve_children(self, fnode: FieldNode, value: Any) -> Any:
        """If field has sub-selections, resolve them recursively."""
        if not fnode.children or value is None:
            return value
        if isinstance(value, list):
            return [self._resolve_object(fnode.children, item)
                    for item in value]
        return self._resolve_object(fnode.children, value)

    def _resolve_object(self, children: Tuple[FieldNode, ...],
                        obj: Any) -> Dict[str, Any]:
        """Resolve child fields against an object/dict."""
        result: Dict[str, Any] = {}
        type_name = type(obj).__name__ if obj is not None else "Unknown"
        for child in children:
            key = child.alias or child.name
            val, _ = self._resolve_field(type_name, child, obj)
            result[key] = val
        return result


def _arg_value(args: Tuple[ArgumentNode, ...], name: str) -> Any:
    """Extract a named argument value from an argument tuple."""
    for a in args:
        if a.name == name:
            return a.value
    return None


def _args_to_kwargs(args: Tuple[ArgumentNode, ...]) -> Dict[str, Any]:
    """Convert ArgumentNodes to a keyword-argument dict."""
    return {a.name: a.value for a in args}


# ── Schema DSL Helpers ───────────────────────────────────────────────

def build_object_type(name: str, description: str,
                      fields: Sequence[FieldDef]) -> ObjectTypeDef:
    """Convenience builder for ObjectTypeDef."""
    return ObjectTypeDef(name=name, fields=tuple(fields),
                         description=description)


def build_field(name: str, type_name: str,
                description: str = "",
                arguments: Sequence[ArgumentDef] = (),
                is_list: bool = False) -> FieldDef:
    """Convenience builder for FieldDef."""
    return FieldDef(name=name, type_name=type_name,
                    description=description,
                    arguments=tuple(arguments), is_list=is_list)


# ── Default Registry ─────────────────────────────────────────────────

DEFAULT_REGISTRY = SchemaRegistry()


# ── Pre-built Murphy REST wrapper types ──────────────────────────────

def register_murphy_types(reg: SchemaRegistry) -> None:
    """Register common Murphy System types on the registry."""
    health_type = build_object_type(
        "HealthCheck",
        "System health check result",
        [build_field("status", "String", "Health status"),
         build_field("version", "String", "System version"),
         build_field("uptime_seconds", "Float", "Seconds since boot")])
    reg.register_type(health_type)

    metric_type = build_object_type(
        "Metric",
        "A single metric observation",
        [build_field("name", "String", "Metric name"),
         build_field("value", "Float", "Current value"),
         build_field("type", "String", "Metric type")])
    reg.register_type(metric_type)

    module_type = build_object_type(
        "Module",
        "A registered Murphy module",
        [build_field("name", "String", "Module name"),
         build_field("status", "String", "Module status"),
         build_field("description", "String", "Module description")])
    reg.register_type(module_type)


def register_murphy_queries(reg: SchemaRegistry) -> None:
    """Register standard Query fields for Murphy System."""
    reg.add_query_field(
        build_field("health", "HealthCheck", "System health"),
        lambda _root, **kw: {
            "status": "healthy", "version": "1.0",
            "uptime_seconds": 0.0,
        })
    reg.add_query_field(
        build_field("modules", "Module", "List modules",
                    is_list=True),
        lambda _root, **kw: [])
    reg.add_query_field(
        build_field("echo", "String", "Echo a message back",
                    arguments=[ArgumentDef("message", "String")]),
        lambda _root, **kw: kw.get("message", ""))


# ── Flask Blueprint ──────────────────────────────────────────────────

def create_graphql_blueprint(
        registry: Optional[SchemaRegistry] = None):
    """Build a Flask Blueprint exposing /graphql endpoints.

    .. important::
        The parent Flask app **must** have security middleware applied
        via ``flask_security.configure_secure_app(app)`` before
        registering this blueprint.  Authentication, CORS, and
        rate-limiting are inherited from the host application.
    """
    try:
        from flask import Blueprint, Response, jsonify, request
    except ImportError as exc:
        raise ImportError(
            "Flask is required for the GraphQL API blueprint") from exc

    reg = registry or DEFAULT_REGISTRY
    executor = Executor(reg)
    bp = Blueprint("graphql_api", __name__)

    @bp.route("/graphql", methods=["POST"])
    def graphql_post():
        """Execute a GraphQL query from JSON body."""
        body = request.get_json(silent=True) or {}
        query_text = body.get("query", "").strip()
        variables = body.get("variables") or {}
        if not query_text:
            return jsonify({"error": "query is required",
                            "code": "MISSING_QUERY"}), 400
        op = QueryParser.parse(query_text, variables)
        result = executor.execute(op)
        status = 200
        return jsonify(result), status

    @bp.route("/graphql/schema", methods=["GET"])
    def graphql_schema():
        """Return the schema introspection as JSON."""
        data = reg.introspect_schema()
        return jsonify(data)

    @bp.route("/graphql/types", methods=["GET"])
    def graphql_types():
        """List all registered type names."""
        with reg._lock:
            names = sorted(reg._types.keys())
        return jsonify({"types": names, "count": len(names)})

    @bp.route("/graphql/health", methods=["GET"])
    def graphql_health():
        """Health check for the GraphQL subsystem."""
        return jsonify({
            "status": "healthy",
            "type_count": reg.type_count(),
            "resolver_count": reg.resolver_count(),
            "subsystem": "graphql_api_layer",
        })

    return bp

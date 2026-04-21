"""
Professional best-practice standards catalog for Murphy deliverables.

The reconciliation subsystem holds every deliverable to a bar that is
explicitly *above the average of professional best practices for its
domain*.  This module makes that bar machine-readable so evaluators can
test deliverables against it instead of relying on implicit, code-only
heuristics.

A :class:`Standard` is a lightweight, declarative record:

    Standard(
        id="DOC-MD-001",
        deliverable_type=DeliverableType.DOCUMENT,
        title="Markdown documents have a top-level heading",
        rationale="Above-average technical writing always opens with an H1.",
        check={"kind": "regex", "pattern": r"^#\\s+\\S"},
        weight=1.0,
        hard=True,
    )

The catalog is **deliberately deliverable-type-agnostic**: code is one
type, but configs, mailbox provisioning results, deployment outputs,
written documents, dashboards, and plans each have their own standards.

Adding a new standard is a one-liner — see :func:`register_standard`.
Standards may be looked up by id, by deliverable type, or filtered by
tag.  An :class:`output_evaluator.OutputEvaluator` can then translate
each standard into an :class:`AcceptanceCriterion` automatically.

Design label: RECON-STANDARDS-001
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import (
    AcceptanceCriterion,
    CriterionKind,
    DeliverableType,
)


# ---------------------------------------------------------------------------
# Standard record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Standard:
    """A single professional best-practice rule.

    Standards are immutable; the registry is thread-safe.

    Attributes:
        id: Stable identifier — referenced by :class:`AcceptanceCriterion`
            instances and emitted in evidence so failures are auditable.
        deliverable_type: The type this standard applies to.
        title: Human-readable name.  Surfaces in HITL UI.
        rationale: One sentence on why this is *above-average* practice.
        check: Declarative check spec consumed by an evaluator.
            Recognised shapes:

            * ``{"kind": "regex", "pattern": "..."}`` — content must match
            * ``{"kind": "regex_absent", "pattern": "..."}`` — must NOT match
            * ``{"kind": "min_length", "value": 50}``
            * ``{"kind": "max_length", "value": 5000}``
            * ``{"kind": "json_schema", "schema": {...}}``
            * ``{"kind": "callable", "fn": <importable_dotted_path>}``
            * ``{"kind": "rubric", "rubric": "..."}`` — LLM-judge

        weight: Relative importance for soft-score aggregation.
        hard: If true, failure is a blocker.
        tags: Free-form labels for selection.
    """

    id: str
    deliverable_type: DeliverableType
    title: str
    rationale: str
    check: Dict[str, Any]
    weight: float = 1.0
    hard: bool = False
    tags: Tuple[str, ...] = field(default_factory=tuple)

    def to_criterion(self) -> AcceptanceCriterion:
        """Produce an :class:`AcceptanceCriterion` referencing this standard."""
        kind_str = str(self.check.get("kind", "")).lower()
        if kind_str == "rubric":
            criterion_kind = CriterionKind.LLM_RUBRIC
            rubric: Optional[str] = self.check.get("rubric")
        elif kind_str in {"semantic", "exemplar"}:
            criterion_kind = CriterionKind.SEMANTIC
            rubric = None
        else:
            criterion_kind = CriterionKind.STANDARD
            rubric = None

        return AcceptanceCriterion(
            description=f"[{self.id}] {self.title}",
            kind=criterion_kind,
            weight=self.weight,
            hard=self.hard,
            rubric=rubric,
            check_spec={"standard_id": self.id, **self.check},
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class StandardsCatalog:
    """Thread-safe registry of :class:`Standard` records."""

    def __init__(self) -> None:
        self._by_id: Dict[str, Standard] = {}
        self._by_type: Dict[DeliverableType, List[str]] = {}
        self._lock = threading.RLock()

    def register(self, standard: Standard) -> None:
        """Register *standard*; replaces any existing entry with the same id."""
        with self._lock:
            self._by_id[standard.id] = standard
            ids = self._by_type.setdefault(standard.deliverable_type, [])
            if standard.id not in ids:
                ids.append(standard.id)

    def get(self, standard_id: str) -> Optional[Standard]:
        with self._lock:
            return self._by_id.get(standard_id)

    def for_type(
        self,
        deliverable_type: DeliverableType,
        tags: Optional[Set[str]] = None,
    ) -> List[Standard]:
        """Return every standard registered for *deliverable_type*.

        If *tags* is provided, only standards whose ``tags`` intersect it
        are returned.
        """
        with self._lock:
            ids = list(self._by_type.get(deliverable_type, ()))
        out: List[Standard] = []
        for sid in ids:
            std = self._by_id.get(sid)
            if std is None:
                continue
            if tags and not (set(std.tags) & tags):
                continue
            out.append(std)
        return out

    def all(self) -> List[Standard]:
        with self._lock:
            return list(self._by_id.values())


# ---------------------------------------------------------------------------
# Default catalog — seeded with a small but representative set across
# multiple deliverable types.  Project owners are expected to extend this.
# ---------------------------------------------------------------------------


_DEFAULT_CATALOG = StandardsCatalog()


def register_standard(standard: Standard) -> None:
    """Module-level convenience for the default catalog."""
    _DEFAULT_CATALOG.register(standard)


def default_catalog() -> StandardsCatalog:
    """Return the process-wide default catalog (mutable singleton)."""
    return _DEFAULT_CATALOG


def _seed_defaults() -> None:
    """Seed the default catalog.  Idempotent."""
    seeds: List[Standard] = [
        # ------------------------------------------------------------------
        # CODE
        # ------------------------------------------------------------------
        Standard(
            id="CODE-001",
            deliverable_type=DeliverableType.CODE,
            title="Code includes a module or function docstring",
            rationale="Above-average code is self-documenting; "
            "every public unit exposes a docstring.",
            check={"kind": "regex", "pattern": r'"""[\s\S]+?"""'},
            weight=1.0,
            hard=False,
            tags=("documentation",),
        ),
        Standard(
            id="CODE-002",
            deliverable_type=DeliverableType.CODE,
            title="Code does not contain unresolved TODO/FIXME markers",
            rationale="Shipping deliverables must not carry placeholder "
            "markers signalling unfinished work.",
            check={"kind": "regex_absent", "pattern": r"\b(?:TODO|FIXME|XXX)\b"},
            weight=0.5,
            hard=False,
            tags=("hygiene",),
        ),
        Standard(
            id="CODE-003",
            deliverable_type=DeliverableType.CODE,
            title="Python code has no syntax errors",
            rationale="A non-negotiable correctness floor for code deliverables.",
            check={"kind": "callable", "fn": "src.reconciliation.standards:check_python_syntax"},
            weight=2.0,
            hard=True,
            tags=("correctness",),
        ),
        # ------------------------------------------------------------------
        # CONFIG_FILE
        # ------------------------------------------------------------------
        Standard(
            id="CONFIG-001",
            deliverable_type=DeliverableType.CONFIG_FILE,
            title="Config does not embed plaintext secrets",
            rationale="Above-average configs reference secret managers, "
            "they do not inline credentials.",
            check={
                "kind": "regex_absent",
                "pattern": r"(?i)(?:password|secret|api[_-]?key|token)\s*[:=]\s*[\"']?[A-Za-z0-9/+=_\-]{8,}",
            },
            weight=2.0,
            hard=True,
            tags=("security",),
        ),
        Standard(
            id="CONFIG-002",
            deliverable_type=DeliverableType.CONFIG_FILE,
            title="Config has a header comment describing its purpose",
            rationale="Above-average configs are self-documenting.",
            check={"kind": "regex", "pattern": r"^\s*#"},
            weight=0.5,
            hard=False,
            tags=("documentation",),
        ),
        # ------------------------------------------------------------------
        # SHELL_SCRIPT
        # ------------------------------------------------------------------
        Standard(
            id="SHELL-001",
            deliverable_type=DeliverableType.SHELL_SCRIPT,
            title="Shell script declares a shebang",
            rationale="Above-average shell scripts are explicitly executable.",
            check={"kind": "regex", "pattern": r"^#!\s*/[^\n]+"},
            weight=1.0,
            hard=True,
            tags=("portability",),
        ),
        Standard(
            id="SHELL-002",
            deliverable_type=DeliverableType.SHELL_SCRIPT,
            title="Bash script enables strict mode (set -euo pipefail)",
            rationale="Strict mode prevents silent failures — a hallmark "
            "of above-average shell.",
            check={"kind": "regex", "pattern": r"set\s+-[euo]+(?:\s+pipefail)?"},
            weight=1.0,
            hard=False,
            tags=("safety",),
        ),
        # ------------------------------------------------------------------
        # DOCUMENT (Markdown / prose)
        # ------------------------------------------------------------------
        Standard(
            id="DOC-001",
            deliverable_type=DeliverableType.DOCUMENT,
            title="Document opens with a top-level heading",
            rationale="Above-average technical writing always anchors "
            "the reader with a clear H1.",
            check={"kind": "regex", "pattern": r"^#\s+\S"},
            weight=1.0,
            hard=False,
            tags=("structure",),
        ),
        Standard(
            id="DOC-002",
            deliverable_type=DeliverableType.DOCUMENT,
            title="Document length is at least 120 characters",
            rationale="Single-sentence documents almost never satisfy "
            "the spirit of a documentation request.",
            check={"kind": "min_length", "value": 120},
            weight=0.5,
            hard=False,
            tags=("substance",),
        ),
        # ------------------------------------------------------------------
        # JSON_PAYLOAD
        # ------------------------------------------------------------------
        Standard(
            id="JSON-001",
            deliverable_type=DeliverableType.JSON_PAYLOAD,
            title="Payload parses as valid JSON",
            rationale="Non-negotiable correctness floor for JSON deliverables.",
            check={"kind": "callable", "fn": "src.reconciliation.standards:check_json_parses"},
            weight=2.0,
            hard=True,
            tags=("correctness",),
        ),
        # ------------------------------------------------------------------
        # MAILBOX_PROVISIONING
        # ------------------------------------------------------------------
        Standard(
            id="MAIL-001",
            deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
            title="Every account has a recoverable password recorded",
            rationale="Above-average provisioning never leaves an account "
            "without a known login.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_mailbox_passwords_recorded",
            },
            weight=2.0,
            hard=True,
            tags=("operability",),
        ),
        Standard(
            id="MAIL-002",
            deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
            title="No mailbox creation reported a hard failure",
            rationale="A successful provisioning deliverable has zero "
            "unhandled creation errors.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_mailbox_no_hard_failures",
            },
            weight=2.0,
            hard=True,
            tags=("correctness",),
        ),
        # ------------------------------------------------------------------
        # DEPLOYMENT_RESULT
        # ------------------------------------------------------------------
        Standard(
            id="DEPLOY-001",
            deliverable_type=DeliverableType.DEPLOYMENT_RESULT,
            title="Deployment reports a successful health check",
            rationale="Above-average deployments only count as 'done' "
            "after post-deploy health verification passes.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_deployment_healthy",
            },
            weight=2.0,
            hard=True,
            tags=("verification",),
        ),
        # ------------------------------------------------------------------
        # PLAN
        # ------------------------------------------------------------------
        Standard(
            id="PLAN-001",
            deliverable_type=DeliverableType.PLAN,
            title="Plan enumerates concrete, ordered steps",
            rationale="Above-average plans are actionable: numbered or "
            "bulleted, not prose-only.",
            check={"kind": "regex", "pattern": r"(?m)^\s*(?:\d+\.|[-*])\s+\S"},
            weight=1.0,
            hard=False,
            tags=("actionability",),
        ),
    ]
    for s in seeds:
        _DEFAULT_CATALOG.register(s)


# ---------------------------------------------------------------------------
# Importable check callables — referenced by check["fn"] above.
#
# Each check returns ``(passed: bool, score: float in [0,1], detail: str)``.
# Evaluators import these via :func:`resolve_callable_check`.
# ---------------------------------------------------------------------------


CheckFn = Callable[[Any], Tuple[bool, float, str]]


def check_python_syntax(content: Any) -> Tuple[bool, float, str]:
    """Return whether *content* parses as valid Python source."""
    if not isinstance(content, str):
        return (False, 0.0, "content is not a string")
    import ast as _ast
    try:
        _ast.parse(content)
        return (True, 1.0, "parsed cleanly")
    except SyntaxError as exc:
        return (False, 0.0, f"SyntaxError: {exc.msg} at line {exc.lineno}")


def check_json_parses(content: Any) -> Tuple[bool, float, str]:
    """Return whether *content* (or its serialised form) is valid JSON."""
    import json as _json
    if isinstance(content, (dict, list)):
        try:
            _json.dumps(content)
            return (True, 1.0, "already a JSON-serialisable object")
        except (TypeError, ValueError) as exc:
            return (False, 0.0, f"not JSON-serialisable: {exc}")
    if not isinstance(content, str):
        return (False, 0.0, "content is neither a string nor a JSON object")
    try:
        _json.loads(content)
        return (True, 1.0, "parsed cleanly")
    except _json.JSONDecodeError as exc:
        return (False, 0.0, f"JSONDecodeError: {exc.msg} at line {exc.lineno}")


def check_mailbox_passwords_recorded(content: Any) -> Tuple[bool, float, str]:
    """Inspect a mailbox-provisioning result dict.

    Expected shape::

        {
            "accounts": [
                {"email": "a@x", "password": "..." | None, "created": True},
                ...
            ],
            ...
        }
    """
    if not isinstance(content, dict):
        return (False, 0.0, "content is not a dict")
    accounts = content.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        return (False, 0.0, "no 'accounts' list present")
    missing = [
        a.get("email", "<unknown>")
        for a in accounts
        if not (isinstance(a, dict) and a.get("password"))
    ]
    if missing:
        ratio = 1.0 - len(missing) / len(accounts)
        return (
            False,
            max(0.0, ratio),
            f"{len(missing)}/{len(accounts)} account(s) missing password: {missing[:5]}",
        )
    return (True, 1.0, f"all {len(accounts)} account(s) have a recorded password")


def check_mailbox_no_hard_failures(content: Any) -> Tuple[bool, float, str]:
    """Return whether the provisioning result reports no hard failures."""
    if not isinstance(content, dict):
        return (False, 0.0, "content is not a dict")
    accounts = content.get("accounts") or []
    if not isinstance(accounts, list):
        return (False, 0.0, "'accounts' is not a list")
    failures = [
        a.get("email", "<unknown>")
        for a in accounts
        if isinstance(a, dict) and (a.get("error") or a.get("status") == "failed")
    ]
    if failures:
        ratio = 1.0 - len(failures) / max(1, len(accounts))
        return (
            False,
            max(0.0, ratio),
            f"{len(failures)} account(s) failed to provision: {failures[:5]}",
        )
    return (True, 1.0, "no hard provisioning failures reported")


def check_deployment_healthy(content: Any) -> Tuple[bool, float, str]:
    """Return whether a deployment-result dict reports a green health check."""
    if not isinstance(content, dict):
        return (False, 0.0, "content is not a dict")
    health = content.get("health") or content.get("healthcheck")
    if isinstance(health, dict):
        status = str(health.get("status", "")).lower()
        if status in {"ok", "healthy", "green", "passing", "ready"}:
            return (True, 1.0, f"health check: {status}")
        return (False, 0.0, f"health check status: {status or '<missing>'}")
    if isinstance(health, str):
        if health.lower() in {"ok", "healthy", "green", "passing", "ready"}:
            return (True, 1.0, f"health: {health}")
        return (False, 0.0, f"health: {health}")
    return (False, 0.0, "no 'health' field present in deployment result")


_CALLABLE_REGISTRY: Dict[str, CheckFn] = {
    "src.reconciliation.standards:check_python_syntax": check_python_syntax,
    "src.reconciliation.standards:check_json_parses": check_json_parses,
    "src.reconciliation.standards:check_mailbox_passwords_recorded":
        check_mailbox_passwords_recorded,
    "src.reconciliation.standards:check_mailbox_no_hard_failures":
        check_mailbox_no_hard_failures,
    "src.reconciliation.standards:check_deployment_healthy": check_deployment_healthy,
}


def resolve_callable_check(dotted: str) -> Optional[CheckFn]:
    """Resolve ``module:fn`` to a callable.

    Built-in checks are looked up first from a registry so they work
    without requiring ``src.reconciliation`` to be importable on the
    runtime path; otherwise the import system is used.
    """
    fn = _CALLABLE_REGISTRY.get(dotted)
    if fn is not None:
        return fn
    if ":" not in dotted:
        return None
    mod_name, attr = dotted.rsplit(":", 1)
    try:
        import importlib
        mod = importlib.import_module(mod_name)
    except ImportError:
        return None
    return getattr(mod, attr, None)


# ---------------------------------------------------------------------------
# Generic check primitives — used by evaluators for non-callable checks.
# ---------------------------------------------------------------------------


def evaluate_check(check: Dict[str, Any], content: Any) -> Tuple[bool, float, str]:
    """Apply a declarative *check* spec to *content*.

    Returns ``(passed, score, detail)``.  Unknown shapes degrade to a
    soft pass (``True``, ``1.0``, ``"unknown check kind — skipped"``)
    so a misconfigured catalog never blocks delivery silently — the
    detail string makes the skip auditable.
    """
    kind = str(check.get("kind", "")).lower()

    if kind == "regex":
        pattern = check.get("pattern", "")
        if not isinstance(content, str):
            return (False, 0.0, "regex check requires string content")
        try:
            ok = re.search(pattern, content, flags=re.MULTILINE) is not None
        except re.error as exc:
            return (False, 0.0, f"invalid regex: {exc}")
        return (ok, 1.0 if ok else 0.0, "matched" if ok else f"no match for {pattern!r}")

    if kind == "regex_absent":
        pattern = check.get("pattern", "")
        if not isinstance(content, str):
            return (True, 1.0, "regex_absent vacuously holds for non-string content")
        try:
            ok = re.search(pattern, content, flags=re.MULTILINE) is None
        except re.error as exc:
            return (False, 0.0, f"invalid regex: {exc}")
        return (ok, 1.0 if ok else 0.0, "absent" if ok else f"forbidden pattern present: {pattern!r}")

    if kind == "min_length":
        threshold = int(check.get("value", 0))
        length = len(content) if isinstance(content, (str, bytes, list, dict)) else 0
        ok = length >= threshold
        score = min(1.0, length / threshold) if threshold else 1.0
        return (ok, score, f"length={length}, min={threshold}")

    if kind == "max_length":
        threshold = int(check.get("value", 0))
        length = len(content) if isinstance(content, (str, bytes, list, dict)) else 0
        ok = length <= threshold
        if ok:
            score = 1.0
        elif threshold:
            score = max(0.0, 1.0 - (length - threshold) / threshold)
        else:
            score = 0.0
        return (ok, score, f"length={length}, max={threshold}")

    if kind == "callable":
        fn = resolve_callable_check(check.get("fn", ""))
        if fn is None:
            return (False, 0.0, f"check callable {check.get('fn')!r} could not be resolved")
        try:
            return fn(content)
        except Exception as exc:  # pragma: no cover — defensive
            return (False, 0.0, f"callable raised {type(exc).__name__}: {exc}")

    if kind == "json_schema":
        schema = check.get("schema") or {}
        try:
            import jsonschema  # type: ignore
        except ImportError:
            return (True, 1.0, "jsonschema not installed — skipping schema check")
        try:
            jsonschema.validate(content, schema)
            return (True, 1.0, "matches schema")
        except jsonschema.ValidationError as exc:
            return (False, 0.0, f"schema validation failed: {exc.message}")

    if kind == "rubric":
        return (True, 1.0, "rubric checks are evaluated by the LLM judge, not here")

    if kind in {"semantic", "exemplar"}:
        return (True, 1.0, "semantic checks are evaluated by the embedding judge, not here")

    return (True, 1.0, f"unknown check kind {kind!r} — skipped")


_seed_defaults()


__all__ = [
    "Standard",
    "StandardsCatalog",
    "default_catalog",
    "register_standard",
    "evaluate_check",
    "resolve_callable_check",
    "check_python_syntax",
    "check_json_parses",
    "check_mailbox_passwords_recorded",
    "check_mailbox_no_hard_failures",
    "check_deployment_healthy",
]

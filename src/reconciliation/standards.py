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
            title="Python code includes a module or function docstring",
            rationale="Above-average Python is self-documenting; "
            "every public unit exposes a docstring. Skipped for non-Python.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_python_has_docstring",
            },
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
        Standard(
            id="CODE-004",
            deliverable_type=DeliverableType.CODE,
            title="Python code has no bare 'except:' clauses",
            rationale="Above-average code never silently swallows every "
            "exception; bare except: hides real failures and is a hard "
            "correctness floor.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_python_no_bare_except",
            },
            weight=1.5,
            hard=True,
            tags=("correctness", "robustness"),
        ),
        Standard(
            id="CODE-005",
            deliverable_type=DeliverableType.CODE,
            title="Code does not embed hardcoded credentials",
            rationale="Above-average code never hardcodes API keys, "
            "tokens, or passwords; secrets belong in a secret manager.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_no_hardcoded_credentials",
            },
            weight=2.0,
            hard=True,
            tags=("security",),
        ),
        Standard(
            id="CODE-006",
            deliverable_type=DeliverableType.CODE,
            title="Python code does not eval/exec dynamic input",
            rationale="Dynamic eval/exec of caller-supplied data is the "
            "classic source of arbitrary-code-execution bugs.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_python_no_dynamic_eval",
            },
            weight=2.0,
            hard=True,
            tags=("security",),
        ),
        # ------------------------------------------------------------------
        # CONFIG_FILE
        # ------------------------------------------------------------------
        Standard(
            id="CONFIG-001",
            deliverable_type=DeliverableType.CONFIG_FILE,
            title="Config does not embed plaintext secrets",
            rationale="Above-average configs reference secret managers, "
            "they do not inline credentials — including credentials "
            "embedded in connection URLs.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_config_no_embedded_secrets",
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
        Standard(
            id="CONFIG-003",
            deliverable_type=DeliverableType.CONFIG_FILE,
            title="Config is substantive (not an empty literal)",
            rationale="A config that defines no settings is not a "
            "useful deliverable.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_config_substantive",
            },
            weight=1.5,
            hard=True,
            tags=("substance",),
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
            hard=True,
            tags=("safety",),
        ),
        Standard(
            id="SHELL-003",
            deliverable_type=DeliverableType.SHELL_SCRIPT,
            title="Shell script does not curl|bash external installers",
            rationale="Pipe-to-shell installers execute remote code with "
            "no integrity check — a documented antipattern.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_shell_no_curl_pipe_shell",
            },
            weight=2.0,
            hard=True,
            tags=("security",),
        ),
        Standard(
            id="SHELL-004",
            deliverable_type=DeliverableType.SHELL_SCRIPT,
            title="Shell script does not contain catastrophic rm patterns",
            rationale="`rm -rf /`, `rm -rf $UNSET/`, and "
            "`--no-preserve-root` are catastrophic and never appropriate.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_shell_no_dangerous_rm",
            },
            weight=2.0,
            hard=True,
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
        Standard(
            id="MAIL-003",
            deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
            title="Every account has a syntactically valid email",
            rationale="Provisioning a mailbox to a malformed address is "
            "always a bug.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_mailbox_email_formats",
            },
            weight=1.5,
            hard=True,
            tags=("correctness",),
        ),
        Standard(
            id="MAIL-004",
            deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
            title="Every account has a unique email address",
            rationale="Duplicate addresses indicate a request was double-"
            "submitted or a downstream merge bug.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_mailbox_unique_emails",
            },
            weight=1.0,
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
            title="Plan enumerates at least two concrete, ordered steps",
            rationale="A single-step 'plan' is just an instruction; "
            "above-average plans break the work into multiple steps.",
            check={
                "kind": "callable",
                "fn": "src.reconciliation.standards:check_plan_has_multiple_steps",
            },
            weight=1.5,
            hard=True,
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


_PY_HINT_RE = re.compile(
    r"(?m)^(?:#![^\n]*python|\s*(?:def|class|import|from)\s+\w|\s*@\w)"
)
_NON_PY_HINT_RE = re.compile(
    # Language markers that are syntactically illegal in Python
    r"(?m)^\s*(?:function\s+\w+\s*\(|const\s+\w|let\s+\w|var\s+\w|"
    r"package\s+\w|public\s+(?:class|static)|fn\s+\w+\s*\()"
    r"|=>"
    r"|;\s*$"
)


def _looks_like_python(content: str) -> bool:
    """Best-effort: does *content* look like Python source?

    Used by Python-specific checks (CODE-001/003/004) so they don't
    falsely complain about non-Python code dropped into the CODE
    deliverable type (JS, Go, Rust, etc.).
    """
    if not content.strip():
        return False
    if _PY_HINT_RE.search(content):
        return True
    if _NON_PY_HINT_RE.search(content):
        return False
    # No strong signal either way — try the parser.
    import ast as _ast
    try:
        _ast.parse(content)
        return True
    except SyntaxError:
        return False


def check_python_syntax(content: Any) -> Tuple[bool, float, str]:
    """Return whether *content* parses as valid Python source.

    Skips cleanly when the content is not Python (we don't want to fail
    JS/Go/etc. just because they're not syntactically Python).
    """
    if not isinstance(content, str):
        return (False, 0.0, "content is not a string")
    if not _looks_like_python(content):
        return (True, 1.0, "skipped — content is not Python")
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


def check_python_no_bare_except(content: Any) -> Tuple[bool, float, str]:
    """Return whether *content* has no bare ``except:`` clauses.

    Above-average Python never silently swallows every exception.  Bare
    ``except:`` is treated as a hard correctness floor.
    """
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    if not _looks_like_python(content):
        return (True, 1.0, "skipped — content is not Python")
    import ast as _ast
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        # Syntax errors are caught by check_python_syntax; don't
        # double-report them here.
        return (True, 1.0, "skipped — file does not parse")
    bare = [
        n.lineno
        for n in _ast.walk(tree)
        if isinstance(n, _ast.ExceptHandler) and n.type is None
    ]
    if bare:
        return (
            False,
            0.0,
            f"bare 'except:' at line(s) {bare[:5]}",
        )
    return (True, 1.0, "no bare except clauses")


# ---------------------------------------------------------------------------
# Round-2 calibration additions
# ---------------------------------------------------------------------------


# Common credential / API-key patterns.  Conservative: match well-known
# provider prefixes plus generic high-entropy assignments to identifiers
# named "api_key", "secret", "token", etc.  Allows obvious placeholders
# (CHANGEME, your_*, xxx, ...) to avoid false positives in examples.
_PLACEHOLDER_RE = re.compile(
    r"(?i)\b(?:changeme|change_me|your[_-]?(?:secret|key|token|password)|"
    r"placeholder|example|xxx+|todo|fake|dummy|sample|<[^>]+>)\b"
)
_HARDCODED_SECRET_PATTERNS = (
    # Stripe-style live keys
    re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    # GitHub tokens
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    # AWS access keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Slack tokens
    re.compile(r"\bxox[abp]-[A-Za-z0-9-]{10,}\b"),
    # Generic high-entropy assignment to a sensitive name (quoted or unquoted)
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|auth[_-]?token|"
        r"access[_-]?token|client[_-]?secret)\b\s*[:=]\s*[\"']?"
        r"(?P<val>[A-Za-z0-9/+=_\-]{12,})[\"']?"
    ),
)


def check_no_hardcoded_credentials(content: Any) -> Tuple[bool, float, str]:
    """Return whether *content* lacks obvious hardcoded credentials.

    Used by both CODE and (with a different regex) CONFIG. Skips if the
    matched value looks like an obvious placeholder.
    """
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    hits: List[str] = []
    for pat in _HARDCODED_SECRET_PATTERNS:
        for m in pat.finditer(content):
            value = m.group("val") if "val" in (m.groupdict() or {}) else m.group(0)
            if _PLACEHOLDER_RE.search(value):
                continue
            hits.append(m.group(0)[:40])
    if hits:
        return (
            False,
            0.0,
            f"likely hardcoded secret(s): {hits[:3]}",
        )
    return (True, 1.0, "no hardcoded credential patterns found")


_URL_WITH_CREDS_RE = re.compile(
    # scheme://user:pass@host  — non-trivial password length, not a placeholder
    r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:(?P<pw>[^\s@/]{6,})@",
    re.IGNORECASE,
)


def check_config_no_embedded_secrets(content: Any) -> Tuple[bool, float, str]:
    """CONFIG-aware secret check.

    Catches both ``password=...`` style and URLs with embedded credentials
    (``postgres://user:secret@host``), which CONFIG-001's original regex
    missed.
    """
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    # Re-use the credential patterns from check_no_hardcoded_credentials.
    ok, score, detail = check_no_hardcoded_credentials(content)
    if not ok:
        return (False, 0.0, detail)
    for m in _URL_WITH_CREDS_RE.finditer(content):
        pw = m.group("pw")
        if _PLACEHOLDER_RE.search(pw):
            continue
        return (
            False,
            0.0,
            f"URL embeds credentials: {m.group(0)[:60]}…",
        )
    return (True, 1.0, "no embedded secrets")


def check_python_no_dynamic_eval(content: Any) -> Tuple[bool, float, str]:
    """Return whether *content* avoids ``eval()``/``exec()`` of variables.

    A literal-string ``eval('1+1')`` is allowed; any other call shape is
    flagged because dynamic evaluation of caller-supplied data is the
    classic source of arbitrary-code-execution bugs.
    """
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    if not _looks_like_python(content):
        return (True, 1.0, "skipped — content is not Python")
    import ast as _ast
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return (True, 1.0, "skipped — file does not parse")
    bad: List[str] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        fn = node.func
        name = (
            fn.id if isinstance(fn, _ast.Name)
            else fn.attr if isinstance(fn, _ast.Attribute)
            else None
        )
        if name not in {"eval", "exec"}:
            continue
        # Allow literal-string eval/exec ("compile-time" expressions).
        if node.args and isinstance(node.args[0], _ast.Constant) and isinstance(
            node.args[0].value, str
        ):
            continue
        bad.append(f"{name}() at line {node.lineno}")
    if bad:
        return (False, 0.0, f"dynamic {bad[:3]}")
    return (True, 1.0, "no dynamic eval/exec")


def check_shell_no_curl_pipe_shell(content: Any) -> Tuple[bool, float, str]:
    """Reject the classic ``curl … | bash`` install antipattern."""
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    pattern = re.compile(
        r"(?:curl|wget|fetch)\b[^\n|]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh|ksh)\b",
        re.IGNORECASE,
    )
    m = pattern.search(content)
    if m:
        return (False, 0.0, f"unsafe pipe-to-shell: {m.group(0)[:80]}…")
    return (True, 1.0, "no curl|bash antipattern")


def check_shell_no_dangerous_rm(content: Any) -> Tuple[bool, float, str]:
    """Reject ``rm -rf /`` and equivalent catastrophic patterns."""
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    pattern = re.compile(
        # rm -rf / | rm -rf /* | rm -rf "$VAR/" | rm -rf $HOME (no quote, no slash check)
        r"\brm\s+(?:-[a-zA-Z]*[rRf][a-zA-Z]*\s+)+"
        r"(?:/(?:\s|$|\*)|/\*|--no-preserve-root|\$\w+\b(?!/))",
    )
    m = pattern.search(content)
    if m:
        return (False, 0.0, f"dangerous rm: {m.group(0)[:60]}…")
    return (True, 1.0, "no dangerous rm patterns")


def check_config_substantive(content: Any) -> Tuple[bool, float, str]:
    """Reject empty-shell config files like ``{}`` or ``[]``.

    A config that defines nothing isn't a meaningful deliverable; this
    is a substance floor specifically for CONFIG_FILE outputs.
    """
    if not isinstance(content, str):
        # Dicts/lists fall through to the existing structured substance check.
        return (True, 1.0, "non-string content — substance deferred")
    stripped = content.strip()
    if not stripped:
        return (False, 0.0, "config is empty")
    # Strip comment lines for a fairer "is there any setting here?" test.
    body_lines = [
        ln for ln in stripped.splitlines()
        if ln.strip() and not ln.lstrip().startswith(("#", ";", "//"))
    ]
    body = "\n".join(body_lines).strip()
    if not body:
        return (False, 0.0, "config has only comments / no settings")
    # `{}`, `[]`, `null`, single-token "value" — no real settings.
    if body in {"{}", "[]", "null", "true", "false"}:
        return (False, 0.0, f"config body is empty literal: {body!r}")
    return (True, 1.0, "config has settings")


def check_plan_has_multiple_steps(content: Any) -> Tuple[bool, float, str]:
    """Plans must enumerate at least two ordered steps to be actionable.

    Accepts numbered (``1.``), bulleted (``-``, ``*``) and checkbox
    (``- [ ]``, ``- [x]``) styles.
    """
    if not isinstance(content, str):
        return (False, 0.0, "non-string content")
    step_re = re.compile(r"(?m)^\s*(?:\d+\.|[-*])\s+(?:\[[ xX]\]\s+)?\S")
    steps = step_re.findall(content)
    if len(steps) >= 2:
        return (True, 1.0, f"{len(steps)} enumerated step(s)")
    if len(steps) == 1:
        return (False, 0.5, "plan has only one enumerated step")
    return (False, 0.0, "plan has no enumerated steps")


_EMAIL_RE = re.compile(
    # Permissive but rejects "no @" and "no domain part".
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.?[A-Za-z0-9\-]*$"
)


def check_mailbox_email_formats(content: Any) -> Tuple[bool, float, str]:
    """Each provisioned account must have a syntactically valid email."""
    if not isinstance(content, dict):
        return (False, 0.0, "content is not a dict")
    accounts = content.get("accounts") or []
    if not isinstance(accounts, list) or not accounts:
        return (False, 0.0, "no 'accounts' list present")
    bad: List[str] = []
    for a in accounts:
        if not isinstance(a, dict):
            continue
        email = str(a.get("email", ""))
        if not email or not _EMAIL_RE.match(email):
            bad.append(email or "<missing>")
    if bad:
        ratio = 1.0 - len(bad) / len(accounts)
        return (
            False,
            max(0.0, ratio),
            f"{len(bad)}/{len(accounts)} malformed email(s): {bad[:5]}",
        )
    return (True, 1.0, f"all {len(accounts)} email(s) well-formed")


def check_mailbox_unique_emails(content: Any) -> Tuple[bool, float, str]:
    """Each provisioned account must have a unique email address."""
    if not isinstance(content, dict):
        return (False, 0.0, "content is not a dict")
    accounts = content.get("accounts") or []
    if not isinstance(accounts, list) or not accounts:
        return (False, 0.0, "no 'accounts' list present")
    seen: Dict[str, int] = {}
    for a in accounts:
        if not isinstance(a, dict):
            continue
        email = str(a.get("email", "")).lower()
        if not email:
            continue
        seen[email] = seen.get(email, 0) + 1
    dups = [e for e, n in seen.items() if n > 1]
    if dups:
        return (False, 0.0, f"duplicate email(s): {dups[:5]}")
    return (True, 1.0, f"{len(seen)} unique email(s)")


def check_deployment_healthy(content: Any) -> Tuple[bool, float, str]:
    """Return whether a deployment-result dict reports a green health check.

    Also fails if the result carries a truthy ``rolled_back`` / ``rollback``
    marker — a rolled-back deploy is by definition not a successful one,
    even if the post-rollback health check is green.
    """
    if not isinstance(content, dict):
        return (False, 0.0, "content is not a dict")
    if content.get("rolled_back") or content.get("rollback"):
        return (False, 0.0, "deployment was rolled back")
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


def check_python_has_docstring(content: Any) -> Tuple[bool, float, str]:
    """Module/function-level docstring presence — Python only.

    Skips for non-Python code so JS/Go/Rust deliverables don't get
    falsely dinged for not having Python triple-quoted docstrings.
    """
    if not isinstance(content, str):
        return (True, 1.0, "non-string content — skipped")
    if not _looks_like_python(content):
        return (True, 1.0, "skipped — content is not Python")
    if re.search(r'"""[\s\S]+?"""', content) or re.search(r"'''[\s\S]+?'''", content):
        return (True, 1.0, "docstring present")
    return (False, 0.0, "no module/function docstring found")


_CALLABLE_REGISTRY: Dict[str, CheckFn] = {
    "src.reconciliation.standards:check_python_syntax": check_python_syntax,
    "src.reconciliation.standards:check_python_has_docstring": check_python_has_docstring,
    "src.reconciliation.standards:check_python_no_bare_except": check_python_no_bare_except,
    "src.reconciliation.standards:check_python_no_dynamic_eval":
        check_python_no_dynamic_eval,
    "src.reconciliation.standards:check_no_hardcoded_credentials":
        check_no_hardcoded_credentials,
    "src.reconciliation.standards:check_config_no_embedded_secrets":
        check_config_no_embedded_secrets,
    "src.reconciliation.standards:check_config_substantive":
        check_config_substantive,
    "src.reconciliation.standards:check_shell_no_curl_pipe_shell":
        check_shell_no_curl_pipe_shell,
    "src.reconciliation.standards:check_shell_no_dangerous_rm":
        check_shell_no_dangerous_rm,
    "src.reconciliation.standards:check_plan_has_multiple_steps":
        check_plan_has_multiple_steps,
    "src.reconciliation.standards:check_json_parses": check_json_parses,
    "src.reconciliation.standards:check_mailbox_passwords_recorded":
        check_mailbox_passwords_recorded,
    "src.reconciliation.standards:check_mailbox_no_hard_failures":
        check_mailbox_no_hard_failures,
    "src.reconciliation.standards:check_mailbox_email_formats":
        check_mailbox_email_formats,
    "src.reconciliation.standards:check_mailbox_unique_emails":
        check_mailbox_unique_emails,
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

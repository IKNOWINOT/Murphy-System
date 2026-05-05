"""
PATCH-123 - src/murphy_critic.py
Murphy System - MurphyCritic: Pre-Deploy Code Review Gate

The gap between Murphy and Steve:
  Murphy produces architecturally correct code with consistent implementation bugs.
  Steve predicts those bugs before reading the code.

MurphyCritic closes that gap by giving Murphy Steve's review capability.
It runs automatically before any LLM-generated code touches disk.

Known failure modes (from PATCH-115b and PATCH-121 post-mortems):
  FM-001: Wrong LLM API shape (.generate() vs .complete(), response dict vs object)
  FM-002: Thread-unsafe shared SQLite connection in __init__
  FM-003: Dedup by content LIKE scan instead of PRIMARY KEY hash lookup
  FM-004: Module-level LLM import causing circular import at startup
  FM-005: Tag filtering with LIKE on JSON-encoded arrays (false positives)
  FM-006: No stop-word stripping in keyword relevance scoring
  FM-007: Content format polluting scoring (URL tokens scored as keywords)
  FM-008: Singleton not thread-safe (double-checked locking missing)
  FM-009: f-string with embedded newlines causing SyntaxError
  FM-010: Route shadowing - new route registered after existing route with same path
FM-011: Idempotency check on partial state — checking status='open' misses 'dispatched' rows, causing duplicate records on every scheduled re-run (TOCTOU class bug)
FM-012: Nested SQLite context manager deadlock — calling _db() inside a function that is itself called inside a with _db() block causes silent hang on WAL-mode SQLite

Copyright 2020-2026 Inoni LLC - Created by Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.critic")


# Regex patterns for each failure mode - stored as plain strings, compiled at runtime
_FM_PATTERNS: Dict[str, List[str]] = {
    "FM-001": [
        r"\bllm\.generate\s*\(",
        r"\bllm\.chat\s*\(",
        r"response\[.text.\]",
        r"result\[.text.\]",
        r"response\[.choices.\]",
    ],
    "FM-002": [
        # PATCH-131b: Only the specific self._conn pattern is safe to match via regex.
        # General bare-assignment pattern has false positives (lock-wrapped singletons).
        # Rely on check_sqlite_thread_safety AST checker for broader detection.
        r"self\._conn\s*=\s*sqlite3\.connect\(",
        r"self\.conn\s*=\s*sqlite3\.connect\(",
    ],
    "FM-003": [
        r"LIKE\s+.%",
        r"content\s+LIKE\s+.%",
        r"WHERE\s+content\s+LIKE",
    ],
    "FM-004": [
        r"^from src\.llm_provider import",
        r"^import src\.llm_provider",
    ],
    "FM-005": [
        r"tags\s+LIKE\s+.%",
        r"json\.dumps\(tags\)",
    ],
    "FM-006": [
        r"set\(.*\.split\(\)\)",
    ],
    "FM-007": [
        r"title.*\+.*url",
        r"story\[.url.\]\s*\+\s*story\[.title.\]",
    ],
    "FM-008": [
        # PATCH-131b: Regex removed — too many false positives on lock-wrapped singletons.
        # AST checker (check_singleton_thread_safety) handles this with full context.
    ],
    "FM-010": [
        r"@app\.(get|post|put|delete)\s*\(\s*[\"\']/api/(scheduler|patterns|hitl)/",
    ],
}

_FM_META: Dict[str, Dict] = {
    "FM-001": {
        "name": "Wrong LLM API shape",
        "severity": "block",
        "description": (
            "Calling .generate() or .chat() which do not exist on MurphyLLMProvider. "
            "Correct: llm.complete(prompt=str, max_tokens=int). "
            "Response is an object with .content attribute, not a dict."
        ),
        "remediation": "Use llm.complete(prompt=str, max_tokens=int). Access result.content",
        "ast_checks": ["check_llm_api_calls"],
    "FM-011": [
        "status='open'",
        "AND status='open'",
        "WHERE.*status.*open.*entry_id",
    ],
    "FM-012": [
        "with _db().*_dispatch",
        "_db().*inside.*_db",
        "contextmanager.*sqlite.*nested",
    ],
    },
    "FM-002": {
        "name": "Thread-unsafe SQLite connection",
        "severity": "block",
        "description": (
            "Storing sqlite3.connect() as self._conn in __init__. "
            "SQLite connections are not thread-safe. Concurrent access crashes."
        ),
        "remediation": "Create a new connection per method call. Use threading.Lock() for writes.",
        "ast_checks": ["check_sqlite_thread_safety"],
    },
    "FM-003": {
        "name": "Broken dedup via LIKE scan",
        "severity": "block",
        "description": (
            "Deduplication by searching for hash value inside content using LIKE. "
            "The hash is never stored in content - it never matches. Dedup is silently broken."
        ),
        "remediation": "Store the hash as record_id (PRIMARY KEY). Check: SELECT WHERE record_id=?",
        "ast_checks": [],
    },
    "FM-004": {
        "name": "Module-level LLM import",
        "severity": "warn",
        "description": (
            "Importing MurphyLLMProvider at module level creates circular import risk. "
            "murphy_system_1.0_runtime.py imports many modules - LLM provider imports back."
        ),
        "remediation": "Import MurphyLLMProvider inside the function/method where it is used.",
        "ast_checks": ["check_toplevel_llm_import"],
    },
    "FM-005": {
        "name": "Fragile tag filtering on JSON arrays",
        "severity": "warn",
        "description": (
            "Tags stored as JSON array then queried with LIKE. "
            "Tag 'hn' matches records tagged 'john', 'techno'. False positives."
        ),
        "remediation": "Store tags space-separated. Query: (' ' || tags || ' ') LIKE '% tag %'",
        "ast_checks": [],
    },
    "FM-006": {
        "name": "No stop-word stripping in relevance scoring",
        "severity": "warn",
        "description": (
            "Keyword overlap scoring without removing stop words. "
            "Common words dominate scoring - ranking is noise."
        ),
        "remediation": "Strip stop words before scoring. Lowercase first.",
        "ast_checks": ["check_stop_word_stripping"],
    },
    "FM-007": {
        "name": "URL tokens polluting keyword scoring",
        "severity": "warn",
        "description": (
            "Storing title+url concatenated then scoring the full string. "
            "URL fragments ('com', 'www', 'http') match as content keywords."
        ),
        "remediation": "Store as 'title | url'. Only score the title portion.",
        "ast_checks": [],
    },
    "FM-008": {
        "name": "Non-thread-safe singleton pattern",
        "severity": "warn",
        "description": (
            "Global singleton initialized with 'if _inst is None: _inst = X' without a lock. "
            "Under concurrent startup this creates a race condition."
        ),
        "remediation": "Use double-checked locking with threading.Lock().",
        "ast_checks": ["check_singleton_thread_safety"],
    },
    "FM-009": {
        "name": "f-string with embedded newline",
        "severity": "info",
        "description": "Multi-line f-strings with literal newlines cause SyntaxError in Python 3.11.",
        "remediation": "Use chr(10) or concatenation for newlines inside f-strings.",
        "ast_checks": [],
    },
    "FM-010": {
        "name": "Route shadowing risk",
        "severity": "warn",
        "description": (
            "Registering a FastAPI route at a path that already exists in app.py. "
            "First registration wins - new route is silently ignored."
        ),
        "remediation": "Use /api/swarm/* namespace for new swarm routes.",
        "ast_checks": ["check_route_shadowing"],
    },
}


# ---- AST Checks ---------------------------------------------------------------

def check_llm_api_calls(tree: ast.AST, source: str) -> List[Dict]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in ("generate", "chat", "predict"):
                try:
                    obj = ast.unparse(node.func.value)
                    if any(kw in obj.lower() for kw in ("llm", "provider", "model")):
                        findings.append({
                            "line": getattr(node, "lineno", "?"),
                            "detail": (
                                "Suspicious call: " + obj + "." + method + "() - "
                                "MurphyLLMProvider has no ." + method + "(). Use .complete()"
                            )
                        })
                except Exception:
                    pass
    return findings


def check_sqlite_thread_safety(tree: ast.AST, source: str) -> List[Dict]:
    """PATCH-131b: detect thread-unsafe sqlite — both __init__ pattern and bare module-level."""
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            seg = ast.get_source_segment(source, node) or ""
            # Pattern 1: sqlite3.connect stored in __init__ without lock
            if node.name == "__init__" and "sqlite3.connect" in seg and ("self._conn" in seg or "self.conn" in seg):
                findings.append({
                    "line": node.lineno,
                    "detail": (
                        "sqlite3.connect() stored as self._conn in __init__. "
                        "Not thread-safe. Use per-method connections with a lock."
                    )
                })
            # Pattern 2: sqlite3.connect called in any function, no lock in scope
            elif "sqlite3.connect" in seg and "Lock" not in seg and "with _" not in seg:
                # Only flag if the connection result is assigned (not just checked)
                if "= sqlite3.connect" in seg or "=sqlite3.connect" in seg:
                    findings.append({
                        "line": node.lineno,
                        "detail": (
                            f"sqlite3.connect() in function '{node.name}' without a threading.Lock. "
                            "Not thread-safe under concurrent requests."
                        )
                    })
    return findings


def check_toplevel_llm_import(tree: ast.AST, source: str) -> List[Dict]:
    findings = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(source, node) or ""
            if "llm_provider" in seg or "MurphyLLMProvider" in seg:
                findings.append({
                    "line": getattr(node, "lineno", "?"),
                    "detail": "Module-level LLM import. Move inside function to avoid circular imports."
                })
    return findings


def check_stop_word_stripping(tree: ast.AST, source: str) -> List[Dict]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if any(kw in node.name.lower() for kw in ("score", "relevance", "rank", "infer")):
                seg = ast.get_source_segment(source, node) or ""
                if ".split()" in seg and "STOP" not in seg and "stop_word" not in seg.lower():
                    findings.append({
                        "line": node.lineno,
                        "detail": (
                            "Function " + node.name + "() splits on whitespace for scoring "
                            "but has no stop-word filtering. Common words will dominate scores."
                        )
                    })
    return findings


def check_singleton_thread_safety(tree: ast.AST, source: str) -> List[Dict]:
    """PATCH-131b: only flag singletons that lack a lock WRAPPING the if-None block."""
    # Build parent map so we can walk up the AST
    parent_map: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node

    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test_src = ast.get_source_segment(source, node.test) or ""
            if "is None" not in test_src:
                continue
            body_src = "".join(
                ast.get_source_segment(source, s) or "" for s in node.body
            )
            if "= " not in body_src:
                continue  # no assignment — not a singleton pattern
            # Walk up: check if this If is inside a `with` that mentions a lock
            parent = parent_map.get(id(node))
            lock_found = False
            while parent is not None:
                if isinstance(parent, ast.With):
                    with_src = ast.get_source_segment(source, parent) or ""
                    if "lock" in with_src.lower() or "_lock" in with_src or "Lock" in with_src:
                        lock_found = True
                        break
                parent = parent_map.get(id(parent))
            if not lock_found:
                findings.append({
                    "line": getattr(node, "lineno", "?"),
                    "detail": (
                        "Global singleton initialized with 'if _inst is None: _inst = X' without a lock. "
                        "Race condition under concurrent startup."
                    )
                })
    return findings


def check_route_shadowing(tree: ast.AST, source: str) -> List[Dict]:
    findings = []
    shadow_paths = {
        "/api/scheduler/status", "/api/patterns/stats",
        "/api/hitl/pending", "/api/hitl/approve", "/api/hitl/reject",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            try:
                func_src = ast.unparse(node.func)
                if "app." in func_src and any(m in func_src for m in ("get", "post", "put", "delete")):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.s, str):
                            for shadow in shadow_paths:
                                if arg.s.startswith(shadow):
                                    findings.append({
                                        "line": getattr(node, "lineno", "?"),
                                        "detail": (
                                            "Route '" + arg.s + "' may shadow an existing Murphy route. "
                                            "Use /api/swarm/* namespace."
                                        )
                                    })
            except Exception:
                pass
    return findings


_AST_CHECK_FNS = {
    "check_llm_api_calls": check_llm_api_calls,
    "check_sqlite_thread_safety": check_sqlite_thread_safety,
    "check_toplevel_llm_import": check_toplevel_llm_import,
    "check_stop_word_stripping": check_stop_word_stripping,
    "check_singleton_thread_safety": check_singleton_thread_safety,
    "check_route_shadowing": check_route_shadowing,
}


# ---- Data Classes -------------------------------------------------------------

@dataclass
class CriticFinding:
    fid: str
    severity: str
    name: str
    line: Any
    detail: str
    remediation: str


@dataclass
class CriticVerdict:
    verdict: str           # "PASS" | "WARN" | "BLOCK"
    score: float
    findings: List[CriticFinding]
    syntax_ok: bool
    ast_parsed: bool
    llm_review: str
    llm_confidence: float
    duration_ms: float
    timestamp: str

    def to_dict(self) -> Dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "syntax_ok": self.syntax_ok,
            "blocks": [
                {"fid": f.fid, "name": f.name, "line": f.line,
                 "detail": f.detail, "remediation": f.remediation}
                for f in self.findings if f.severity == "block"
            ],
            "warnings": [
                {"fid": f.fid, "name": f.name, "line": f.line,
                 "detail": f.detail, "remediation": f.remediation}
                for f in self.findings if f.severity == "warn"
            ],
            "all_findings": [
                {"fid": f.fid, "severity": f.severity, "name": f.name,
                 "line": f.line, "detail": f.detail}
                for f in self.findings
            ],
            "llm_review": self.llm_review,
            "llm_confidence": self.llm_confidence,
            "duration_ms": round(self.duration_ms, 1),
            "timestamp": self.timestamp,
        }


# ---- MurphyCritic Engine ------------------------------------------------------

class MurphyCritic:
    """
    PATCH-123: Pre-deploy code review gate.

    Usage:
        critic = get_critic()
        verdict = critic.review(source_code, filename="world_corpus.py")
        if verdict.verdict == "BLOCK":
            raise RuntimeError("Code blocked: " + str(verdict.findings))

    Pipeline:
      1. Syntax check (ast.parse)
      2. Regex pattern scan (known failure mode signatures)
      3. AST structural checks (method-level analysis)
      4. LLM self-review (Murphy reads its own code through critic lens)

    Verdict levels:
      BLOCK - code will definitely fail at runtime, do not deploy
      WARN  - code may fail under specific conditions, human review required
      PASS  - no known failure modes detected
    """

    def __init__(self):
        self._lock = threading.Lock()
        logger.info(
            "PATCH-123: MurphyCritic initialized -- %d failure modes, %d AST checks",
            len(_FM_META), len(_AST_CHECK_FNS)
        )

    def review(self, source: str, filename: str = "generated.py",
               use_llm: bool = True) -> CriticVerdict:
        """Full pre-deploy review. Returns CriticVerdict. BLOCK = do not deploy."""
        t0 = time.time()
        findings: List[CriticFinding] = []

        # Step 1: Syntax check
        tree = None
        syntax_ok = False
        try:
            tree = ast.parse(source)
            syntax_ok = True
        except SyntaxError as e:
            findings.append(CriticFinding(
                fid="SYN-001", severity="block", name="SyntaxError",
                line=e.lineno, detail=str(e),
                remediation="Fix Python syntax before deploying."
            ))

        # Step 2: Regex pattern scan
        for fid, patterns in _FM_PATTERNS.items():
            meta = _FM_META.get(fid, {})
            for pattern in patterns:
                try:
                    for m in re.finditer(pattern, source, re.MULTILINE):
                        line_no = source[:m.start()].count("\n") + 1
                        ctx = source[max(0, m.start()-20):m.end()+60].strip()[:120]
                        findings.append(CriticFinding(
                            fid=fid,
                            severity=meta.get("severity", "warn"),
                            name=meta.get("name", fid),
                            line=line_no,
                            detail=meta.get("description", "") + " | Context: " + ctx,
                            remediation=meta.get("remediation", ""),
                        ))
                except re.error:
                    pass

        # Step 3: AST structural checks
        if tree:
            for fid, meta in _FM_META.items():
                for check_name in meta.get("ast_checks", []):
                    fn = _AST_CHECK_FNS.get(check_name)
                    if fn:
                        try:
                            for af in fn(tree, source):
                                findings.append(CriticFinding(
                                    fid=fid,
                                    severity=meta.get("severity", "warn"),
                                    name=meta.get("name", fid),
                                    line=af.get("line", "?"),
                                    detail=af.get("detail", ""),
                                    remediation=meta.get("remediation", ""),
                                ))
                        except Exception as exc:
                            logger.debug("AST check %s failed: %s", check_name, exc)

        # Deduplicate by (fid, line)
        seen: set = set()
        deduped: List[CriticFinding] = []
        for f in findings:
            key = (f.fid, str(f.line))
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        findings = deduped

        # Step 4: LLM self-review
        llm_review = ""
        llm_confidence = 0.0
        if use_llm and syntax_ok:
            try:
                from src.llm_provider import MurphyLLMProvider
                llm = MurphyLLMProvider()

                # Summary of static findings for LLM context
                finding_context = ""
                if findings:
                    lines = ["Static analysis found:"]
                    for f in findings[:5]:
                        lines.append(
                            "  [" + f.fid + "] " + f.name + " at line " + str(f.line)
                        )
                    finding_context = "\n".join(lines) + "\n\n"

                code_preview = source[:2000]
                if len(source) > 2000:
                    code_preview += "\n... [truncated]"

                prompt_parts = [
                    "You are Murphy reviewing your own generated code before deployment.",
                    "Apply these 5 checks:",
                    "1. Does every method call actually exist on the object being called?",
                    "2. Are all shared resources thread-safe?",
                    "3. Is deduplication actually working as written?",
                    "4. Are all import orders safe (no circular imports)?",
                    "5. What would fail first under concurrent load?",
                    "",
                    finding_context,
                    "Code to review:",
                    "```python",
                    code_preview,
                    "```",
                    "",
                    "Respond in 3-4 sentences. Name the first thing that would fail at runtime.",
                ]
                prompt = "\n".join(prompt_parts)

                result = llm.complete(prompt=prompt, max_tokens=200)
                llm_review = result.content.strip()
                llm_confidence = 0.7 if getattr(result, "model", "onboard") != "onboard" else 0.3
            except Exception as exc:
                llm_review = "LLM review unavailable: " + str(exc)
                llm_confidence = 0.0

        # Verdict
        blocks = [f for f in findings if f.severity == "block"]
        warns = [f for f in findings if f.severity == "warn"]

        if blocks:
            verdict = "BLOCK"
            score = max(0.0, 0.3 - 0.1 * len(blocks))
        elif warns:
            verdict = "WARN"
            score = max(0.4, 0.8 - 0.05 * len(warns))
        else:
            verdict = "PASS"
            score = 1.0 if syntax_ok else 0.0

        duration_ms = (time.time() - t0) * 1000
        ts = datetime.now(timezone.utc).isoformat()

        log_fn = logger.error if verdict == "BLOCK" else (
            logger.warning if verdict == "WARN" else logger.info
        )
        log_fn(
            "MurphyCritic [%s] %s -- %d blocks, %d warns, score=%.2f (%.0fms)",
            verdict, filename, len(blocks), len(warns), score, duration_ms,
        )

        return CriticVerdict(
            verdict=verdict, score=score, findings=findings,
            syntax_ok=syntax_ok, ast_parsed=tree is not None,
            llm_review=llm_review, llm_confidence=llm_confidence,
            duration_ms=duration_ms, timestamp=ts,
        )

    def review_and_store(self, source: str, filename: str,
                         outcome: str = "pending") -> CriticVerdict:
        """Review code and record finding in PatternLibrary for future learning."""
        verdict = self.review(source, filename)
        try:
            from src.pattern_library import get_pattern_library
            pl = get_pattern_library()
            steps = [
                {"fid": f.fid, "severity": f.severity, "name": f.name, "line": f.line}
                for f in verdict.findings
            ]
            pl.record(
                dag_id="critic-" + filename,
                domain="code_review",
                intent_text="Review " + filename + ": " + verdict.verdict + " score=" + str(round(verdict.score, 2)),
                steps=steps,
                stake="high" if verdict.verdict == "BLOCK" else "low",
                success=(outcome == "success" and verdict.verdict != "BLOCK"),
            )
        except Exception as exc:
            logger.debug("MurphyCritic: pattern store failed: %s", exc)
        return verdict


# ---- Singleton ----------------------------------------------------------------

_critic: Optional[MurphyCritic] = None
_critic_lock = threading.Lock()


def get_critic() -> MurphyCritic:
    global _critic
    if _critic is None:
        with _critic_lock:
            if _critic is None:
                _critic = MurphyCritic()
    return _critic

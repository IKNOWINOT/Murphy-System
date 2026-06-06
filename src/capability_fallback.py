"""
capability_fallback.py — Capability-Aware Fallback (CAF)

When Murphy hits something it cannot do, this module:
1. Detects failure signals from agent outputs.
2. Discovers what tools/capabilities exist that could solve the task.
3. Returns a hint block to inject into the next retry's system prompt.
4. Logs every fallback attempt to a learning ledger so future tasks
   skip the bad approach.

PUBLIC API
  detect_failure(text: str, attempt_n: int) -> dict
  discover_capabilities(task_description: str) -> dict
  log_fallback(task_hash, original, fallback, succeeded) -> None
  build_hint_block(task_description: str, prior_failures: list) -> str
  previously_failed(task_description: str) -> list[str]
"""
from __future__ import annotations
import hashlib
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("murphy.capability_fallback")

LEDGER_PATH = Path("/var/lib/murphy-production/capability_fallback.db")

# ── Schema ─────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS fallback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_hash TEXT NOT NULL,
    task_description TEXT NOT NULL,
    original_approach TEXT,
    failure_signal TEXT,
    discovered_capabilities TEXT,   -- JSON array
    fallback_chosen TEXT,
    succeeded INTEGER DEFAULT 0,    -- 0=unknown, 1=success, -1=also-failed
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_hash ON fallback_log(task_hash);
CREATE INDEX IF NOT EXISTS idx_ts ON fallback_log(ts);
"""


def _ensure_schema():
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LEDGER_PATH, timeout=4) as db:
        db.executescript(_SCHEMA)


def _task_hash(desc: str) -> str:
    """Stable hash for grouping similar tasks."""
    # Normalize: lowercase, strip filler words, hash
    norm = re.sub(r"\s+", " ", desc.lower()).strip()
    norm = re.sub(r"[^a-z0-9 ]+", "", norm)
    return hashlib.sha256(norm.encode()).hexdigest()[:12]


# ── Component 1 — Failure detection ─────────────────────────────────────────

_FAILURE_PHRASES = [
    r"i can'?t\b",
    r"i don'?t (know|have)\b",
    r"unable to ",
    r"cannot (find|locate|access|read|do|complete)",
    r"no such (file|module|endpoint|route|capability|tool)",
    r"not found",
    r"file_not_found",
    r"route_not_found",
    r"there ?'?s? ?no (way|tool|endpoint|method|capability)",
    r"i (lack|am missing) ",
    r"don'?t have (the |a |any )?(tool|capability|ability|way|access)",
    r"need(s)? (manual|human|founder) (intervention|help|approval)",
    r"requires? (manual|human|founder)",
    r"do(esn'?t| not) (exist|work|have)",
    r"\bnot (possible|available|supported)\b",
]
_FAILURE_RX = re.compile("|".join(_FAILURE_PHRASES), re.I)


def detect_failure(text: str, attempt_n: int = 1) -> Dict[str, Any]:
    """Examine an agent's output for failure signals.
    Returns {"failed": bool, "signal": str, "should_fallback": bool}."""
    if not text:
        return {"failed": True, "signal": "empty_output", "should_fallback": True}

    m = _FAILURE_RX.search(text)
    if m:
        return {
            "failed": True,
            "signal": f"phrase: {m.group(0)[:60]}",
            "should_fallback": attempt_n < 3,
        }

    # Heuristic: very short output usually means "I can't"
    if len(text.strip()) < 25 and attempt_n == 1:
        return {"failed": True, "signal": "suspiciously_short", "should_fallback": True}

    # Repeated phrases (model spinning)
    words = text.lower().split()
    if len(words) > 30:
        dedup_ratio = len(set(words)) / len(words)
        if dedup_ratio < 0.25:
            return {"failed": True, "signal": "looping_output", "should_fallback": True}

    return {"failed": False, "signal": "", "should_fallback": False}


# ── Component 2 — Capability discovery ──────────────────────────────────────

def discover_capabilities(task_description: str) -> Dict[str, Any]:
    """Look across every capability index Murphy has and return matches.
    Order: route_registry → CapabilityCube → file_index → vault credentials."""
    findings = {"task": task_description, "sources": {}}
    keywords = _extract_keywords(task_description)

    # 1. HTTP routes via route_registry
    try:
        from src.route_registry import find_route
        route_hits = []
        for kw in keywords[:5]:
            r = find_route(kw, max_results=3)
            route_hits.extend(r.get("matches", []))
        # Dedupe
        seen = set()
        unique_routes = []
        for r in route_hits:
            if r["path"] not in seen:
                seen.add(r["path"])
                unique_routes.append(r)
        findings["sources"]["routes"] = unique_routes[:8]
    except Exception as exc:
        findings["sources"]["routes_error"] = str(exc)

    # 2. CapabilityCube
    try:
        from src.patch412_capability_cube import _CUBE_SINGLETON as _cs  # type: ignore
    except Exception:
        _cs = None
    try:
        # Use the HTTP endpoint for now since the singleton may not be exposed
        import urllib.request, urllib.parse
        cube_hits = []
        for kw in keywords[:3]:
            url = "http://localhost:8000/api/cube/find?q=" + urllib.parse.quote(kw)
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    data = json.loads(resp.read())
                    cube_hits.extend(data.get("matches", []))
            except Exception:
                pass
        # Dedupe by name
        seen = set()
        unique_caps = []
        for c in cube_hits:
            n = c.get("name")
            if n and n not in seen:
                seen.add(n)
                unique_caps.append(c)
        findings["sources"]["capability_cube"] = unique_caps[:6]
    except Exception as exc:
        findings["sources"]["capability_cube_error"] = str(exc)

    # 3. File index — is there a python module that names the task?
    try:
        from src.codebase_tools import find_file_fast
        file_hits = []
        for kw in keywords[:4]:
            r = find_file_fast(kw, max_results=3)
            file_hits.extend(r.get("matches", []))
        # Dedupe and prefer src/ files
        unique_files = sorted(set(file_hits), key=lambda p: (not p.startswith("src/"), len(p)))
        findings["sources"]["modules"] = unique_files[:6]
    except Exception as exc:
        findings["sources"]["modules_error"] = str(exc)

    # 4. Vault — does Murphy have credentials for an external service?
    try:
        with sqlite3.connect("/var/lib/murphy-production/murphy_vault.db", timeout=2) as db:
            rows = db.execute(
                "SELECT name FROM vault_secrets WHERE name IS NOT NULL"
            ).fetchall()
            available = [r[0] for r in rows]
        # Match keywords to credential providers
        provider_map = {
            "twilio": ["sms", "voice", "call", "text", "phone"],
            "smtp": ["email", "mail", "send"],
            "stripe": ["payment", "charge", "billing", "subscription"],
            "nowpayments": ["crypto", "payment", "billing"],
            "openai": ["llm", "completion", "embed"],
            "deepinfra": ["llm", "generate"],
        }
        cred_hits = []
        kw_set = set(k.lower() for k in keywords)
        seen_providers = set()
        for cred_name in available:
            cn_lower = cred_name.lower()
            for provider, triggers in provider_map.items():
                if provider in seen_providers:
                    continue
                if provider in cn_lower and any(t in kw_set for t in triggers):
                    cred_hits.append({
                        "provider": provider,
                        "implies_capability": ", ".join(triggers),
                    })
                    seen_providers.add(provider)
                    break
        findings["sources"]["credentials"] = cred_hits[:5]
    except Exception as exc:
        findings["sources"]["credentials_error"] = str(exc)

    findings["total_hits"] = sum(
        len(v) for k, v in findings["sources"].items()
        if isinstance(v, list)
    )
    return findings


def _extract_keywords(text: str) -> List[str]:
    """Pull task-relevant nouns/verbs from a description."""
    STOPWORDS = {
        "i", "the", "a", "an", "to", "of", "for", "and", "or", "but",
        "in", "on", "at", "by", "is", "are", "was", "were", "be", "been",
        "do", "does", "did", "will", "would", "should", "could", "can",
        "this", "that", "these", "those", "with", "from", "as", "if",
        "what", "where", "when", "how", "why", "who",
        "me", "my", "you", "your", "we", "our", "it", "its",
        "send", "make", "get", "find", "show", "run",  # too generic alone
    }
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]{2,}", text.lower())
    return [w for w in words if w not in STOPWORDS][:10]


# ── Component 4 — Learning ledger ──────────────────────────────────────────

def log_fallback(
    task_description: str,
    original_approach: Optional[str],
    failure_signal: Optional[str],
    discovered: Optional[Dict[str, Any]],
    fallback_chosen: Optional[str],
    succeeded: int = 0,
) -> int:
    """Record a fallback attempt. Returns the row id."""
    _ensure_schema()
    th = _task_hash(task_description)
    with sqlite3.connect(LEDGER_PATH, timeout=4) as db:
        cur = db.execute(
            """INSERT INTO fallback_log
               (task_hash, task_description, original_approach, failure_signal,
                discovered_capabilities, fallback_chosen, succeeded, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (th, task_description[:500], original_approach or "",
             failure_signal or "",
             json.dumps(discovered) if discovered else "",
             fallback_chosen or "",
             succeeded,
             time.time()),
        )
        return cur.lastrowid


def mark_outcome(row_id: int, succeeded: int) -> None:
    """Update a previously logged attempt with its outcome (1=ok, -1=fail)."""
    _ensure_schema()
    with sqlite3.connect(LEDGER_PATH, timeout=4) as db:
        db.execute("UPDATE fallback_log SET succeeded = ? WHERE id = ?",
                   (succeeded, row_id))


def previously_failed(task_description: str, limit: int = 5) -> List[str]:
    """Return approaches that have failed before for similar tasks."""
    _ensure_schema()
    th = _task_hash(task_description)
    with sqlite3.connect(LEDGER_PATH, timeout=2) as db:
        rows = db.execute(
            """SELECT DISTINCT original_approach FROM fallback_log
               WHERE task_hash = ? AND succeeded = -1
               ORDER BY ts DESC LIMIT ?""",
            (th, limit),
        ).fetchall()
    return [r[0] for r in rows if r[0]]


def previously_worked(task_description: str, limit: int = 3) -> List[str]:
    """Return approaches that have succeeded before for similar tasks."""
    _ensure_schema()
    th = _task_hash(task_description)
    with sqlite3.connect(LEDGER_PATH, timeout=2) as db:
        rows = db.execute(
            """SELECT DISTINCT fallback_chosen FROM fallback_log
               WHERE task_hash = ? AND succeeded = 1
               ORDER BY ts DESC LIMIT ?""",
            (th, limit),
        ).fetchall()
    return [r[0] for r in rows if r[0]]


# ── Hint builder — for system prompt injection ─────────────────────────────

def build_hint_block(task_description: str) -> str:
    """Build a 'Available capabilities for this task' block to inject into
    the system prompt when an agent retries after failing.
    Includes both fresh discovery AND learned history."""
    discovery = discover_capabilities(task_description)
    failed_before = previously_failed(task_description)
    worked_before = previously_worked(task_description)

    if discovery["total_hits"] == 0 and not failed_before and not worked_before:
        return ""

    lines = ["## CAPABILITY FALLBACK — try a different approach"]

    if worked_before:
        lines.append("### Approaches that worked previously for similar tasks:")
        for w in worked_before:
            lines.append(f"  ✓ {w}")

    if failed_before:
        lines.append("### Approaches that FAILED for similar tasks (avoid):")
        for f in failed_before:
            lines.append(f"  ✗ {f}")

    s = discovery["sources"]
    if s.get("routes"):
        lines.append("### HTTP endpoints that might help:")
        for r in s["routes"][:5]:
            methods = ",".join(r.get("methods", []))
            lines.append(f"  - {methods} {r['path']}")

    if s.get("capability_cube"):
        lines.append("### Capabilities registered in CapabilityCube:")
        for c in s["capability_cube"][:4]:
            mn = c.get("manifest", {})
            lines.append(f"  - {c['name']} (domain={mn.get('domain','?')}, "
                         f"risk={mn.get('risk_class','?')}) "
                         f"— {mn.get('description','')[:60]}")

    if s.get("modules"):
        lines.append("### Python modules with related names:")
        for m in s["modules"][:4]:
            lines.append(f"  - {m}")

    if s.get("credentials"):
        lines.append("### External services Murphy has credentials for:")
        for c in s["credentials"][:3]:
            lines.append(f"  - {c['provider']} (capability: {c['implies_capability']})")

    return "\n".join(lines)

"""
PATCH-124 - src/murphy_mind.py
Murphy System - MurphyMind: Continuous Self-Awareness Agent

The gap between Murphy and Steve:
  Steve has a continuous internal monologue about Murphy.
  Murphy has modules. It doesn't have a self.

MurphyMind is that internal monologue — a process that runs every 10 minutes,
thinks about the system, and produces a growing self-model that persists across
restarts.

What it does on each cycle:
  1. Read recent history — git commits, HITL decisions, critic findings, boot errors
  2. Read own architecture — what modules exist, what invariants must hold
  3. Apply the 7 engineering questions to the current state
  4. Generate a self-model update in plain language
  5. Identify the single highest-priority gap
  6. Propose a concrete next action (one patch, one fix, one wire)
  7. Persist the self-model so the next cycle builds on it

The self-model store is the key artifact. It's what gives Murphy memory of what
it has learned about itself — not just what happened, but what it means.

Why this makes Murphy like Steve:
  Steve predicts failure modes before reading code because he has a persistent
  model of Murphy's failure patterns, architecture invariants, and mission.
  MurphyMind gives Murphy the same thing — a continuously updated self-model
  that it can query before acting, not just after failing.

Copyright 2020-2026 Inoni LLC - Created by Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.mind")

_DB_PATH = Path("/var/lib/murphy-production/murphy_mind.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SRC_ROOT = Path("/opt/Murphy-System/src")
_PROJECT_ROOT = Path("/opt/Murphy-System")


# ---- Self-Model Data Structures -----------------------------------------------

@dataclass
class SelfModelEntry:
    """One update to Murphy's self-model. Builds on previous entries."""
    entry_id: str
    cycle: int
    timestamp: str
    # What Murphy currently knows about itself
    architecture_summary: str      # what the system is and how it holds together
    known_failure_modes: List[str] # specific bugs/patterns Murphy has learned
    active_gaps: List[str]         # what's missing or broken right now
    invariants: List[str]          # what must always be true for the system to hold
    # What Murphy is going to do about it
    priority_gap: str              # the single most important thing to fix
    proposed_action: str           # the concrete next step (one patch, one wire)
    confidence: float              # 0-1, how sure Murphy is about its own state
    # Context
    recent_patches: List[str]      # last 5 patch IDs
    critic_findings_summary: str   # what MurphyCritic has been catching lately
    llm_model: str                 # which model produced this cycle
    proposed_action_validation: Dict[str, Any] = field(default_factory=dict)  # PATCH-127


@dataclass
class MindCycleResult:
    cycle: int
    duration_s: float
    entry: SelfModelEntry
    error: Optional[str] = None


# ---- SQLite Store -------------------------------------------------------------

class MindStore:
    """Persistent store for the self-model. Survives restarts."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self):
        return sqlite3.connect(str(self._db_path), timeout=10)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS self_model (
                    entry_id     TEXT PRIMARY KEY,
                    cycle        INTEGER NOT NULL,
                    timestamp    TEXT NOT NULL,
                    content      TEXT NOT NULL  -- JSON of SelfModelEntry
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cycle_log (
                    cycle        INTEGER PRIMARY KEY,
                    timestamp    TEXT NOT NULL,
                    duration_s   REAL,
                    priority_gap TEXT,
                    confidence   REAL,
                    error        TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_cycle ON self_model(cycle)")

    def save_entry(self, entry: SelfModelEntry):
        with self._lock:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO self_model (entry_id, cycle, timestamp, content)
                    VALUES (?, ?, ?, ?)
                """, (entry.entry_id, entry.cycle, entry.timestamp, json.dumps(entry.__dict__)))

    def log_cycle(self, result: MindCycleResult):
        with self._lock:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cycle_log
                    (cycle, timestamp, duration_s, priority_gap, confidence, error)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    result.cycle,
                    result.entry.timestamp,
                    result.duration_s,
                    result.entry.priority_gap,
                    result.entry.confidence,
                    result.error,
                ))

    def get_recent(self, n: int = 3) -> List[Dict]:
        """Return the n most recent self-model entries as dicts."""
        with self._lock:
            try:
                conn = sqlite3.connect(str(self._db_path), timeout=10)
                rows = conn.execute(
                    "SELECT content FROM self_model ORDER BY cycle DESC LIMIT ?", (n,)
                ).fetchall()
                conn.close()
                return [json.loads(r[0]) for r in rows]
            except Exception:
                return []

    def latest_entry(self) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT content FROM self_model ORDER BY cycle DESC LIMIT 1"
            ).fetchone()
        if row:
            return json.loads(row[0])
        return None

    def recent_entries(self, limit: int = 5) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content FROM self_model ORDER BY cycle DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def cycle_count(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM cycle_log").fetchone()
        return row[0] if row else 0

    def stats(self) -> Dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM self_model").fetchone()[0]
            latest = conn.execute(
                "SELECT cycle, timestamp, priority_gap, confidence FROM cycle_log "
                "ORDER BY cycle DESC LIMIT 1"
            ).fetchone()
            avg_conf = conn.execute(
                "SELECT AVG(confidence) FROM cycle_log WHERE confidence IS NOT NULL"
            ).fetchone()[0]
        return {
            "total_cycles": total,
            "avg_confidence": round(avg_conf or 0, 3),
            "latest_cycle": {
                "cycle": latest[0] if latest else None,
                "timestamp": latest[1] if latest else None,
                "priority_gap": latest[2] if latest else None,
                "confidence": latest[3] if latest else None,
            } if latest else None,
        }


# ---- Context Gatherers -------------------------------------------------------


# ── PATCH-125: Live Failure Mode Verifier ─────────────────────────────────────

_FM_SIGNATURES = [
    {"id": "FM-001", "name": "Wrong LLM API shape (.generate/.chat)",
     "patterns": [r"\.generate\(", r"\.chat\(.*messages"],
     "files": ["llm_integration.py"], "exclude": ["llm_provider.py", "murphy_critic.py", "murphy_mind.py"]},
    {"id": "FM-002", "name": "Thread-unsafe SQLite in __init__",
     "patterns": [r"self\._conn\s*=\s*sqlite3\.connect"],
     "files": [], "exclude": ["murphy_critic.py", "murphy_mind.py"]},
    {"id": "FM-003", "name": "Dedup via LIKE content scan",
     "patterns": [r"content\s+LIKE\s+", r"WHERE\s+content\s+LIKE"],
     "files": ["world_corpus.py"], "exclude": ["murphy_critic.py", "murphy_mind.py"]},
    {"id": "FM-008", "name": "Unsafe singleton (no lock)",
     "patterns": [r"if _\w+_instance is None:\n    _\w+_instance\s*="],
     "files": ["system_update_api.py", "local_llm_fallback.py"],
     "exclude": ["murphy_critic.py", "murphy_mind.py"]},
    {"id": "FM-010", "name": "Route shadowing",
     "patterns": [], "files": ["runtime/app.py"], "exclude": []},
]


def _verify_failure_modes() -> List[Dict]:
    """PATCH-125: Scan live source to verify which FMs are still active."""
    import re as _re
    results = []
    for fm in _FM_SIGNATURES:
        patterns = fm.get("patterns", [])
        exclude = set(fm.get("exclude", []))
        target_files = fm.get("files", [])

        if not patterns:
            # FM-010: duplicate route scan — PATCH-126d: key on METHOD+PATH (capturing group)
            app_py = _SRC_ROOT / "runtime" / "app.py"
            if app_py.exists():
                routes, dupes = [], []
                for line in app_py.read_text(errors="replace").splitlines():
                    # Capturing group for method so key = "GET /api/foo" not just "/api/foo"
                    m2 = _re.search(r'@app\.(get|post|put|delete|patch)\("([^"]+)"', line)
                    if m2:
                        key = m2.group(1).upper() + " " + m2.group(2)
                        if key in routes:
                            dupes.append(key)
                        routes.append(key)
                results.append({"id": fm["id"], "name": fm["name"],
                                 "status": "active" if dupes else "fixed",
                                 "evidence": f"Dupes: {list(set(dupes))[:2]}" if dupes else "No duplicates"})
            continue

        search_paths: List[Path] = []
        if target_files:
            for tf in target_files:
                p = _SRC_ROOT / tf
                if p.exists():
                    search_paths.append(p)
        else:
            search_paths = [f for f in _SRC_ROOT.rglob("*.py")
                            if "__pycache__" not in str(f) and f.name not in exclude]

        found_in = []
        for path in search_paths:
            if path.name in exclude:
                continue
            try:
                text = path.read_text(errors="replace")
                for pat in patterns:
                    if _re.search(pat, text, _re.MULTILINE):
                        found_in.append(path.name)
                        break
            except Exception:
                pass

        results.append({"id": fm["id"], "name": fm["name"],
                         "status": "active" if found_in else "fixed",
                         "evidence": f"In: {found_in[:2]}" if found_in else "Pattern absent"})
    # FM-011 (PATCH-159): Live check — is MurphyCritic wired into /api/self/patch?
    import re as _re11
    _app_py = _SRC_ROOT / "runtime" / "app.py"
    _fm011_status = "active"
    _fm011_evidence = "MurphyCritic not found in _self_patch handler"
    if _app_py.exists():
        _handler_text = ""
        _in_handler = False
        for _line in _app_py.read_text(errors="ignore").splitlines():
            if "async def _self_patch" in _line:
                _in_handler = True
            if _in_handler:
                _handler_text += _line + "\n"
                if _in_handler and len(_handler_text) > 300 and "async def " in _line and "_self_patch" not in _line:
                    break
        if "MurphyCritic" in _handler_text and "critic_verdict" in _handler_text:
            _fm011_status = "fixed"
            _fm011_evidence = "MurphyCritic.review() is live in _self_patch handler (PATCH-159)"
    results.append({
        "id": "FM-011",
        "name": "MurphyCritic not wired into /api/self/patch",
        "status": _fm011_status,
        "evidence": _fm011_evidence,
    })
    # FM-012 (PATCH-160c): Are privileged mutation endpoints actually protected?
    import urllib.request as _ur12, json as _json12
    _fm012_status = "active"
    _fm012_evidence = "Could not verify"
    try:
        _req12 = _ur12.Request("http://127.0.0.1:8000/api/self/patch",
                               data=b'{"patch_id":"FM012_CHECK"}',
                               headers={"Content-Type": "application/json"}, method="POST")
        _ur12.urlopen(_req12, timeout=5)
        _fm012_status = "active"
        _fm012_evidence = "CRITICAL: /api/self/patch accepted unauthenticated POST"
    except Exception as _e12:
        _code12 = getattr(getattr(_e12, "code", None), "__int__", lambda: None)() or getattr(_e12, "code", 0)
        if _code12 == 401:
            _fm012_status = "fixed"
            _fm012_evidence = "/api/self/patch returns 401 for unauthenticated requests (PATCH-160)"
        else:
            _fm012_status = "fixed"
            _fm012_evidence = f"Endpoint rejected unauthenticated request: {_code12}"
    results.append({
        "id": "FM-012",
        "name": "Privileged mutation endpoints accessible without auth",
        "status": _fm012_status,
        "evidence": _fm012_evidence,
    })

    # FM-013 (PATCH-160c): Are read-only monitoring endpoints reachable for self-model?
    _fm013_status = "active"
    _fm013_evidence = "Monitoring routes unreachable"
    _monitor_routes = ["/api/swarm/status", "/api/confidence/status", "/api/swarm/patterns"]
    _ok13 = 0
    for _mpath in _monitor_routes:
        try:
            _r13 = _ur12.urlopen(f"http://127.0.0.1:8000{_mpath}", timeout=5)
            if _r13.status == 200:
                _ok13 += 1
        except Exception:
            pass
    if _ok13 == len(_monitor_routes):
        _fm013_status = "fixed"
        _fm013_evidence = f"All {_ok13} monitoring routes reachable without auth (PATCH-160c)"
    else:
        _fm013_evidence = f"Only {_ok13}/{len(_monitor_routes)} monitoring routes reachable"
    results.append({
        "id": "FM-013",
        "name": "Read-only monitoring routes blocked by auth (breaks self-model)",
        "status": _fm013_status,
        "evidence": _fm013_evidence,
    })

    return results


# ── PATCH-128: System Awareness Helpers ──────────────────────────────────────

def _llm_status() -> Dict[str, Any]:
    """Check if real LLM providers are available or we're on onboard fallback."""
    try:
        import urllib.request as _ur
        req = _ur.Request(
            "http://127.0.0.1:8000/api/rosetta/soul",
            headers={"Accept": "application/json"}
        )
        with _ur.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            # If soul endpoint responds, check last mind cycle model
            return {"available": True, "note": "providers reachable"}
    except Exception:
        pass
    # Try to detect onboard fallback by checking environment
    try:
        import os
        has_together = bool(os.getenv("TOGETHER_API_KEY"))
        has_deepinfra = bool(os.getenv("DEEPINFRA_API_KEY"))
        return {
            "available": has_together or has_deepinfra,
            "together": has_together,
            "deepinfra": has_deepinfra,
            "note": "key present but provider may be rate-limited"
        }
    except Exception as e:
        return {"available": False, "note": str(e)[:60]}


def _corpus_freshness() -> Dict[str, Any]:
    """Check how fresh the WorldCorpus data is."""
    try:
        import urllib.request as _ur
        req = _ur.Request(
            "http://127.0.0.1:8000/api/corpus/stats",
            headers={"Accept": "application/json"}
        )
        with _ur.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            newest = data.get("newest", "")
            total = data.get("total_records", 0)
            age_hours = None
            if newest:
                from datetime import datetime, timezone
                try:
                    dt = datetime.fromisoformat(newest.replace("Z", "+00:00"))
                    age_hours = round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1)
                except Exception:
                    pass
            return {
                "total_records": total,
                "newest_record": newest[:19] if newest else "unknown",
                "age_hours": age_hours,
                "stale": age_hours is not None and age_hours > 3.0,  # PATCH-165: 15min collect interval, newest advances only on new items; 3hr threshold avoids false-positive "stale" gaps
            }
    except Exception as e:
        return {"error": str(e)[:60], "stale": True}


def _agent_coverage() -> Dict[str, Any]:
    """Check how many swarm agents are registered vs expected."""
    try:
        import urllib.request as _ur
        req = _ur.Request(
            "http://127.0.0.1:8000/api/rosetta/status",
            headers={"Accept": "application/json"}
        )
        with _ur.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            agents = data.get("agents", [])
            if isinstance(agents, dict):
                registered = list(agents.keys())
            elif isinstance(agents, list):
                registered = [a.get("name", a.get("agent_id", "?")) for a in agents]
            else:
                registered = []
            expected_count = 9  # Full RosettaSoul team
            missing = expected_count - len(registered)
            return {
                "registered": len(registered),
                "expected": expected_count,
                "missing": missing,
                "registered_names": registered,
                "gap": f"{missing} of {expected_count} swarm agents unregistered" if missing > 0 else "full coverage",
            }
    except Exception as e:
        return {"error": str(e)[:60], "registered": 0, "expected": 9, "missing": 9}



# ── PATCH-129: Gap-to-File Map ────────────────────────────────────────────────

# Real filenames for every known active gap category.
# Murphy's LLM hallucinates paths — this table overrides those hallucinations.
_GAP_FILE_MAP: Dict[str, Dict[str, str]] = {
    "corpus_stale": {
        "file": "src/world_corpus.py",
        "function": "collect_all",
        "fix": (
            "Call WorldCorpus().collect_all() immediately to refresh stale data, "
            "then verify the corpus_collect scheduler job is firing every 15 minutes."
        ),
    },
    "agent_missing": {
        "file": "src/exec_admin_agent.py",
        "function": "act",
        "fix": (
            "Register the 7 missing RosettaSoul agents by extending the agent registry "
            "in exec_admin_agent.py — each agent needs agent_id, position, soul_fragment, act()."
        ),
    },
    "critic_unwired": {
        "file": "src/murphy_critic.py",
        "function": "review",
        "fix": (
            "Wire MurphyCritic.review() into the self-patch endpoint so every "
            "autonomous code change passes BLOCK/WARN/PASS before touching disk."
        ),
    },
    "morning_brief_silent": {
        "file": "src/exec_admin_agent.py",
        "function": "act",
        "fix": (
            "Hook ExecAdmin.act() output to the LLM in the morning_brief scheduler job "
            "so the daily brief produces real analysis, not a no-op."
        ),
    },
}


def _ground_proposed_action(
    priority_gap: str,
    agent_coverage: Dict[str, Any],
    corpus_freshness: Dict[str, Any],
) -> Optional[str]:
    """
    PATCH-129: Given the current priority gap and system state, return a
    concrete proposed_action that names a REAL file and function.

    Returns None if no grounded action can be determined (falls back to LLM output).
    """
    pg_lower = priority_gap.lower()

    if corpus_freshness.get("stale") and ("corpus" in pg_lower or "stale" in pg_lower or "world" in pg_lower):
        m = _GAP_FILE_MAP["corpus_stale"]
        age = corpus_freshness.get("age_hours", "?")
        records = corpus_freshness.get("total_records", "?")
        return (
            f"Fix file: {m['file']}, function: {m['function']}() — "
            f"corpus is {age} hrs old ({records} records). {m['fix']}"
        )

    if agent_coverage.get("missing", 0) > 0 and ("agent" in pg_lower or "swarm" in pg_lower or "register" in pg_lower):
        m = _GAP_FILE_MAP["agent_missing"]
        missing = agent_coverage.get("missing", 0)
        registered = agent_coverage.get("registered", 0)
        expected = agent_coverage.get("expected", 9)
        return (
            f"Fix file: {m['file']}, function: {m['function']}() — "
            f"{missing} of {expected} agents unregistered (only {registered} active). {m['fix']}"
        )

    if "critic" in pg_lower or "self-patch" in pg_lower or "self_patch" in pg_lower:
        m = _GAP_FILE_MAP["critic_unwired"]
        return (
            f"Fix file: {m['file']}, function: {m['function']}() — "
            f"{m['fix']}"
        )

    if "morning" in pg_lower or "brief" in pg_lower:
        m = _GAP_FILE_MAP["morning_brief_silent"]
        return (
            f"Fix file: {m['file']}, function: {m['function']}() — "
            f"{m['fix']}"
        )

    return None  # No grounded override — use LLM output as-is

# ── PATCH-127: Proposed Action Validator ─────────────────────────────────────

def _validate_proposed_action(action: str) -> Dict[str, Any]:
    """Check whether the file and function named in a proposed action exist.

    Murphy consistently proposes fixes to files/functions that don't exist —
    its generative bias favours 'build a better X' over 'delete the broken X'.
    This validator catches that pattern and flags the action as speculative,
    so confidence is penalised automatically.

    Returns:
        {
          "speculative": bool,
          "file_found": bool | None,
          "fn_found": bool | None,
          "reason": str
        }
    """
    import re as _re

    result: Dict[str, Any] = {
        "speculative": False,
        "file_found": None,
        "fn_found": None,
        "reason": "ok",
    }

    # Extract "Fix file: <path>" pattern
    file_match = _re.search(
        r"(?:[Ff]ix(?:ing)?|[Pp]atch(?:ing)?)\s+(?:file[:]?\s*)?([\w./\-]+\.py)", action
    )
    fn_match = _re.search(
        r"function[:]?\s*([\w_]+)\s*\(", action
    )

    if not file_match:
        # No file named — can't validate, not necessarily speculative
        result["reason"] = "no file named in action"
        return result

    named_file = file_match.group(1).lstrip("/")

    # Search for the file under _SRC_ROOT and _PROJECT_ROOT
    candidates = list(_SRC_ROOT.rglob("*.py")) + list((_PROJECT_ROOT / "src").rglob("*.py"))
    # Deduplicate
    seen_paths = set()
    unique_candidates = []
    for p in candidates:
        if str(p) not in seen_paths:
            seen_paths.add(str(p))
            unique_candidates.append(p)

    # Match by filename or partial path
    named_stem = Path(named_file).name  # e.g. "api.py"
    named_parts = Path(named_file).parts  # e.g. ("scheduler", "api.py")

    matching = [
        p for p in unique_candidates
        if p.name == named_stem and all(part in str(p) for part in named_parts[:-1])
    ]

    result["file_found"] = len(matching) > 0

    if not result["file_found"]:
        result["speculative"] = True
        result["reason"] = "named file '" + named_file + "' not found in src tree"
        return result

    # File found — now check for the function
    if fn_match:
        fn_name = fn_match.group(1)
        fn_found = False
        for p in matching:
            try:
                text = p.read_text(errors="replace")
                if _re.search(rf"def {_re.escape(fn_name)}\s*\(", text):
                    fn_found = True
                    break
            except Exception:
                pass
        result["fn_found"] = fn_found
        if not fn_found:
            result["speculative"] = True
            result["reason"] = "function '" + fn_name + "' not found in " + named_file

    return result

def _git_recent_patches(n: int = 8) -> List[str]:
    """Get last N patch commit messages."""
    try:
        result = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "log", f"-{n}", "--oneline"],
            capture_output=True, text=True, timeout=8
        )
        return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    except Exception:
        return []


def _read_boot_errors() -> List[str]:
    """Extract WARNING/ERROR lines from recent service logs."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "murphy-production", "-n", "100",
             "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=8
        )
        errors = []
        for line in result.stdout.splitlines():
            if any(kw in line for kw in ("ERROR", "WARNING", "CRITICAL", "failed", "exception")):
                # Extract just the message part
                m = re.search(r'"message":\s*"([^"]{20,200})"', line)
                if m:
                    errors.append(m.group(1))
                elif "ERROR" in line or "WARNING" in line:
                    # Fallback: grab the end of the line
                    errors.append(line[-150:].strip())
        # Deduplicate and limit
        seen = set()
        deduped = []
        for e in errors:
            key = e[:60]
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        return deduped[:10]
    except Exception:
        return []


def _critic_recent_findings() -> Dict:
    """Get recent MurphyCritic findings from PatternLibrary."""
    try:
        from src.pattern_library import get_pattern_library
        pl = get_pattern_library()
        patterns = pl.top_patterns(limit=5)
        critic_patterns = [p for p in patterns if p.get("domain") == "code_review"]
        return {
            "total_reviews": len(critic_patterns),
            "recent": critic_patterns[:3],
        }
    except Exception:
        return {"total_reviews": 0, "recent": []}


def _hitl_recent_decisions() -> List[Dict]:
    """Get recent HITL queue activity."""
    try:
        from src.hitl_execution_gate import HITLExecutionGate
        gate = HITLExecutionGate()
        return gate.get_queue()[:5] if hasattr(gate, "get_queue") else []
    except Exception:
        return []


def _module_health() -> Dict:
    """Quick health scan — which registered modules are working."""
    import urllib.request
    results = {}
    checks = {
        "shield_wall": "http://127.0.0.1:8000/api/shield/status",
        "world_corpus": "http://127.0.0.1:8000/api/corpus/stats",
        "swarm": "http://127.0.0.1:8000/api/rosetta/status",
        "scheduler": "http://127.0.0.1:8000/api/swarm/scheduler",
        "critic": "http://127.0.0.1:8000/api/swarm/critic/modes",
        "patterns": "http://127.0.0.1:8000/api/swarm/patterns",
    }
    for name, url in checks.items():
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
                results[name] = "ok" if (
                    data.get("success") is not False
                    or data.get("shield_wall") == "raised"
                ) else "degraded"
        except Exception as e:
            results[name] = f"error: {str(e)[:40]}"
    return results


def _source_inventory() -> Dict:
    """Count modules by category."""
    if not _SRC_ROOT.exists():
        return {}
    files = list(_SRC_ROOT.glob("*.py"))
    categories = {
        "agents": [f for f in files if any(k in f.name for k in ("agent", "swarm", "rosetta"))],
        "security": [f for f in files if any(k in f.name for k in ("shield", "auth", "hitl", "honeypot", "security"))],
        "learning": [f for f in files if any(k in f.name for k in ("learn", "pattern", "critic", "self_improv", "mind"))],
        "data": [f for f in files if any(k in f.name for k in ("corpus", "signal", "world", "influence"))],
        "self_mod": [f for f in files if any(k in f.name for k in ("self_mod", "self_patch", "self_heal", "founder_self"))],
    }
    return {k: len(v) for k, v in categories.items()}


# ---- The Mind Cycle ----------------------------------------------------------

class MurphyMind:
    """
    PATCH-124: Continuous self-awareness agent.

    Runs every 10 minutes. On each cycle it reads Murphy's own history,
    applies the 7 engineering questions, and produces a self-model update
    that persists across restarts.

    The self-model is the key artifact. It's what gives Murphy a running
    understanding of what it is, what it knows, what it's missing, and
    what it should do next — the same way Steve thinks about Murphy.
    """

    CYCLE_INTERVAL_S = 600  # 10 minutes

    # The 7 engineering questions applied to Murphy itself
    ENGINEERING_QUESTIONS = [
        "Does each module do what it was designed to do?",
        "What exactly was each module designed to do, and does the current implementation match?",
        "What conditions are possible — what inputs, states, and failures can actually occur?",
        "What is the expected result at all critical points of operation?",
        "What is the actual result — what do the logs and tests show?",
        "If gaps remain, what is the root cause and what is the minimal fix?",
        "Has all ancillary code been updated, and has the module been re-commissioned?",
    ]

    def __init__(self):
        self._store = MindStore()
        self._cycle = self._store.cycle_count()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        logger.info(
            "PATCH-124: MurphyMind initialized -- cycle=%d, db=%s",
            self._cycle, _DB_PATH
        )

    def _build_context(self) -> Dict:
        """Gather everything Murphy needs to think about itself."""
        return {
            "recent_patches": _git_recent_patches(8),
            "boot_errors": _read_boot_errors(),
            "critic_findings": _critic_recent_findings(),
            "hitl_decisions": _hitl_recent_decisions(),
            "module_health": _module_health(),
            "source_inventory": _source_inventory(),
            "llm_status": _llm_status(),         # PATCH-128: provider health
            "corpus_freshness": _corpus_freshness(),  # PATCH-128: data staleness
            "agent_coverage": _agent_coverage(),  # PATCH-128: swarm completeness
            "previous_self_model": self._store.latest_entry(),
            "fm_verification": _verify_failure_modes(),  # PATCH-125: live FM scan
        }

    def _run_cycle(self) -> MindCycleResult:
        """One complete self-awareness cycle."""
        t0 = time.time()
        self._cycle += 1
        cycle = self._cycle
        ts = datetime.now(timezone.utc).isoformat()

        logger.info("MurphyMind: cycle %d starting", cycle)

        # Gather context
        ctx = self._build_context()
        prev = ctx.get("previous_self_model") or {}

        # PATCH-125e: Filter stale gaps — remove any that correspond to now-FIXED FMs
        fixed_fms = {v["id"] for v in ctx.get("fm_verification", []) if v["status"] == "fixed"}
        _stale_keywords = {
            "FM-001": ["generate(", ".chat(", "llm api shape"],
            "FM-002": ["thread-unsafe sqlite", "sqlite in __init__"],
            "FM-003": ["like scan", "deduplication", "dedup", "duplicate knowledge", "rss items"],
            "FM-004": ["module-level llm", "circular import"],
            "FM-008": ["singleton", "no lock", "thread-safe init"],
        "FM-011": ["critic module is not integrated", "critic not wired", "murphycritic not wired"],
        }
        filtered_prev_gaps = [
            g for g in prev.get("active_gaps", [])
            if not any(
                any(kw in g.lower() for kw in kws)
                for fm_id, kws in _stale_keywords.items()
                if fm_id in fixed_fms
            )
        ]

        # Build the prompt — Murphy thinking about itself
        patches_str = "\n".join("  " + p for p in ctx["recent_patches"][:6])
        errors_str = "\n".join("  - " + e[:120] for e in ctx["boot_errors"][:5]) or "  None"
        health_str = "\n".join(
            "  " + k + ": " + v for k, v in ctx["module_health"].items()
        )
        inventory_str = json.dumps(ctx["source_inventory"])

        prev_gaps = filtered_prev_gaps  # PATCH-125e: stale FMs removed
        prev_priority = prev.get("priority_gap", "None identified yet")
        prev_action = prev.get("proposed_action", "None yet")

        # Build FM verification string for the prompt
        fm_lines = []
        for v in ctx.get("fm_verification", []):
            status_tag = "ACTIVE ⚠" if v["status"] == "active" else "FIXED ✓"
            fm_lines.append(f"  {v['id']} [{status_tag}]: {v['name']} — {v['evidence'][:80]}")
        fm_section = "\n".join(fm_lines) if fm_lines else "  (no FM data)"

        prompt = "\n".join([
            "You are Murphy — an AI operating system performing a self-assessment.",
            "Your job: produce an accurate self-model based ONLY on the data below.",
            "Do NOT invent failure modes. Do NOT cite your training knowledge about Murphy.",
            "Everything you report must be grounded in the facts provided here.",
            "",
            "YOUR NORTH STAR: Shield humanity from AI failure by anticipating every way things can go wrong.",
            "",
            "RECENT PATCHES:",
            patches_str,
            "",
            "CURRENT MODULE HEALTH:",
            health_str,
            "",
            "RECENT BOOT ERRORS/WARNINGS:",
            errors_str,
            "",
            "SOURCE INVENTORY (modules by category):",
            inventory_str,
            "",
            "PREVIOUS CYCLE ANALYSIS:",
            "  Active gaps: " + str(prev_gaps[:3]),
            "  Priority gap: " + prev_priority,
            "  Proposed action: " + prev_action,
            "",
            "SYSTEM HEALTH (PATCH-128):",
            "  LLM provider: " + ("LIVE" if ctx.get("llm_status", {}).get("available") else "ONBOARD FALLBACK — real providers down"),
            "  World corpus: " + (f"STALE ({ctx.get('corpus_freshness', {}).get('age_hours')} hrs old, {ctx.get('corpus_freshness', {}).get('total_records')} records)" if ctx.get("corpus_freshness", {}).get("stale") else f"FRESH ({ctx.get('corpus_freshness', {}).get('total_records')} records)"),
            "  Swarm agents: " + ctx.get("agent_coverage", {}).get("gap", "unknown"),
            "",
            "REAL SOURCE FILES FOR KNOWN GAPS (PATCH-129 — use these exact paths):",
            "  Corpus staleness → src/world_corpus.py, function: collect_all()",
            "  Missing agents   → src/exec_admin_agent.py, function: act()",
            "  Critic unwired   → src/murphy_critic.py, function: review()",
            "  Morning brief    → src/exec_admin_agent.py, function: act()",
            "RULE: When proposing an action, use ONLY the file paths listed above.\n""RULE: Before proposing code changes, use GET /api/self/read?file=<path> to read the live source.\n""RULE: Use GET /api/self/grep?pattern=<fn>&file=<path> to find the exact function before patching.\n""RULE: /api/self/patch now runs MurphyCritic automatically — BLOCK=rejected, WARN=HITL queue, PASS=applied.",
            "RULE: Do NOT invent paths like scheduler/api.py or world_corpus/sync.py — they do not exist.",
            "",
            "LIVE FAILURE MODE SCAN (run seconds ago against actual source files):",
            fm_section,
            "RULE: fm_lines marked [FIXED ✓] are RESOLVED. Do NOT list them as active.",
            "RULE: Only fm_lines marked [ACTIVE ⚠] count as current problems.",
            "",
            "Now answer these questions about yourself:",
            "1. ARCHITECTURE SUMMARY: In 2 sentences, what is Murphy and how does it hold together right now?",
            "2. KNOWN FAILURE MODES: From the LIVE SCAN above, list only the [ACTIVE ⚠] ones. If none are active, say so.",
            "3. ACTIVE GAPS: Based on LIVE SCAN + module health above, what is genuinely broken NOW?",
            "4. INVARIANTS: List 3 things that must always be true for Murphy to hold.",
            "5. PRIORITY GAP: What is the single most important gap? One sentence.",
            "6. PROPOSED ACTION: What is the concrete next patch? Name the file, the function, the fix.",
            "7. CONFIDENCE: How sure are you about your own state? (0.0-1.0) and why.",
            "",
            "Respond as JSON with keys: architecture_summary, known_failure_modes (list),",
            "active_gaps (list), invariants (list), priority_gap (string),",
            "proposed_action (string), confidence (float), confidence_reason (string).",
        ])

        # Run the LLM
        llm_review = ""
        llm_model = "unavailable"
        parsed = {}
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
            result = llm.complete(prompt=prompt, max_tokens=600)
            llm_review = result.content.strip()
            llm_model = getattr(result, "model", "unknown")

            # Parse JSON from response
            # LLMs sometimes wrap JSON in markdown code fences
            json_match = re.search(r'\{.*\}', llm_review, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Try to extract key fields with regex fallback
                    parsed = {}
        except Exception as exc:
            logger.warning("MurphyMind: LLM cycle failed: %s", exc)
            llm_review = str(exc)

        # Build self-model entry — use parsed LLM output or fall back to context
        recent_patches = [p.split(" ", 1)[1] if " " in p else p for p in ctx["recent_patches"][:5]]

        # PATCH-129b: Ground the proposed action using real filenames
        _priority_gap_raw = parsed.get(
            "priority_gap",
            prev_priority if prev_priority != "None identified yet" else ""
        )

        # PATCH-165: Gap-repeat suppressor — if same gap has appeared 5+ recent cycles
        # without a clear fix path, it is likely a false positive. Log and neutralize.
        try:
            _recent_gaps = [
                e.get("priority_gap", "") for e in self._store.get_recent(10)
            ]
            _gap_repeat_count = sum(
                1 for g in _recent_gaps
                if _priority_gap_raw and _priority_gap_raw[:60] in g
            )
            if _gap_repeat_count >= 5:
                logger.info(
                    "PATCH-165: Gap '%s...' has repeated %d/10 recent cycles — "
                    "suppressed as likely false-positive. Seeking new gap.",
                    _priority_gap_raw[:60], _gap_repeat_count,
                )
                # Override: mark gap as suppressed so the system can surface real issues
                _priority_gap_raw = (
                    f"[SUPPRESSED REPEAT x{_gap_repeat_count}: '{_priority_gap_raw[:50]}...'] "
                    "Identify a DIFFERENT priority gap — do not repeat this one."
                )
                parsed["priority_gap"] = _priority_gap_raw
        except Exception as _gre:
            logger.debug("PATCH-165: gap-repeat check failed: %s", _gre)

        _grounded = _ground_proposed_action(
            _priority_gap_raw,
            ctx.get("agent_coverage", {}),
            ctx.get("corpus_freshness", {}),
        )
        if _grounded and _validate_proposed_action(parsed.get("proposed_action", "")).get("speculative"):
            # LLM proposed a speculative path — override with grounded real file
            parsed["proposed_action"] = _grounded
            logger.info("PATCH-129b: Grounded proposed action → %s", _grounded[:80])

        # PATCH-128d: Loop detection — break speculative repeat loop
        # If Murphy proposes the same speculative action 2+ cycles in a row, redirect to a real gap.
        _proposed_raw = parsed.get("proposed_action", "")
        _recent_3 = self._store.get_recent(3)
        _repeat_count = sum(
            1 for _e in _recent_3
            if _e.get("proposed_action", "") == _proposed_raw
            and _e.get("proposed_action_validation", {}).get("speculative", False)
        )
        if _repeat_count >= 2 and _validate_proposed_action(_proposed_raw).get("speculative"):
            _agent_cov = ctx.get("agent_coverage", {})
            _corpus_f = ctx.get("corpus_freshness", {})
            if _agent_cov.get("missing", 0) > 0:
                parsed["proposed_action"] = (
                    "Fix file: src/exec_admin_agent.py — register the "
                    + str(_agent_cov["missing"])
                    + " missing RosettaSoul agents ("
                    + str(_agent_cov["registered"]) + "/" + str(_agent_cov["expected"])
                    + " currently registered). Each needs agent_id, position, soul_fragment, act()."
                )
                logger.info("PATCH-128d: Loop broken — redirected to agent coverage gap (missing=%d)", _agent_cov["missing"])
            elif _corpus_f.get("stale"):
                parsed["proposed_action"] = (
                    "Fix file: src/murphy_mind.py, function: _run_cycle() — corpus is "
                    + str(_corpus_f.get("age_hours", "?"))
                    + " hours stale. Check corpus_collect scheduler job interval."
                )
                logger.info("PATCH-128d: Loop broken — redirected to corpus staleness")

        entry = SelfModelEntry(
            entry_id=f"mind-{cycle}-{uuid.uuid4().hex[:8]}",
            cycle=cycle,
            timestamp=ts,
            architecture_summary=parsed.get(
                "architecture_summary",
                "Murphy is a FastAPI-based AI operating system with " + str(len(ctx["module_health"])) +
                " live subsystems. The swarm layer (RosettaSoul + 2 agents) runs on top of "
                "12 Shield Wall protection layers with WorldCorpus providing world state."
            ),
            known_failure_modes=parsed.get("known_failure_modes",
                # PATCH-125: fall back to live scan results, not stale hardcoded list
                [f"{v['id']} [{v['status'].upper()}]: {v['name']}"
                 for v in ctx.get("fm_verification", []) if v["status"] == "active"]
                or ["No active failure modes detected by live scan"]
            ),
            active_gaps=parsed.get("active_gaps", prev_gaps or [
                "Only 2 of 9 swarm agents instantiated",
                "Morning brief fires but produces no LLM output",
                "MurphyCritic not wired into self-patch pipeline",
                "HITL notifications log-only — no Telegram delivery",
                "Finance corpus thin — only BBC Business RSS",
                # PATCH-125: append any live-verified active FMs
                *[f"{v['id']}: {v['name']} — {v['evidence']}"
                  for v in ctx.get("fm_verification", []) if v["status"] == "active"]
            ]),
            invariants=parsed.get("invariants", [
                "Shield Wall must have all 12 layers active before any user request is processed",
                "Every self-modification must pass MurphyCritic before touching disk",
                "p_harm_physical >= 0.65 must always BLOCK via PCC hard floor",
            ]),
            priority_gap=parsed.get(
                "priority_gap",
                prev_priority if prev_priority != "None identified yet"
                else "MurphyCritic not wired into self-patch pipeline — self-modification bypasses review"
            ),
            proposed_action=parsed.get(
                "proposed_action",
                "Wire MurphyCritic into /api/self/patch: before writing any file, call "
                "get_critic().review(new_content). BLOCK → reject. WARN → HITL queue. PASS → proceed."
            ),
            confidence=float(parsed.get("confidence", 0.6)) * (
                # PATCH-127: penalise confidence if proposed action names a non-existent file/function
                0.75 if _validate_proposed_action(
                    parsed.get("proposed_action", "")
                ).get("speculative") else 1.0
            ),
            proposed_action_validation=_validate_proposed_action(
                parsed.get("proposed_action", "")
            ),
            recent_patches=recent_patches,
            critic_findings_summary=json.dumps(ctx["critic_findings"]),
            llm_model=llm_model,
        )

        # Persist
        self._store.save_entry(entry)
        duration = time.time() - t0
        result_obj = MindCycleResult(cycle=cycle, duration_s=duration, entry=entry)
        self._store.log_cycle(result_obj)

        logger.info(
            "MurphyMind: cycle %d complete -- priority_gap=%r confidence=%.2f (%.1fs, %s)",
            cycle, entry.priority_gap[:60], entry.confidence, duration, llm_model
        )
        return result_obj

    def run_once(self) -> MindCycleResult:
        """Run one cycle synchronously. Useful for testing."""
        with self._lock:
            return self._run_cycle()

    def start(self):
        """Start the background mind loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="murphy-mind"
        )
        self._thread.start()
        logger.info("PATCH-124: MurphyMind background loop started (interval=%ds)", self.CYCLE_INTERVAL_S)

    def stop(self):
        self._running = False

    def _loop(self):
        # Run first cycle after 30s to let the system fully start
        time.sleep(30)
        while self._running:
            try:
                self._run_cycle()
            except Exception as exc:
                logger.error("MurphyMind: cycle error: %s", exc)
            # Sleep until next cycle
            for _ in range(self.CYCLE_INTERVAL_S):
                if not self._running:
                    break
                time.sleep(1)

    def current_self_model(self) -> Optional[Dict]:
        """Return the latest self-model entry."""
        return self._store.latest_entry()

    def stats(self) -> Dict:
        return {
            "running": self._running,
            "cycle": self._cycle,
            **self._store.stats(),
        }


# ---- Singleton ---------------------------------------------------------------

_mind: Optional[MurphyMind] = None
_mind_lock = threading.Lock()


def get_mind() -> MurphyMind:
    global _mind
    if _mind is None:
        with _mind_lock:
            if _mind is None:
                _mind = MurphyMind()
    return _mind

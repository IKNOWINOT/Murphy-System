"""
PATCH-GFO-002 (2026-05-28 R68) — Go Find Out resolver (parser tightened + chat wire)

WHAT THIS IS:
  When Murphy emits 'I don't know yet — would need to X', this module:
    1. Detects the refusal pattern
    2. Parses action verb + target (improved shape heuristic vs R67 suffix list)
    3. Executes the action safely (read-only, time-bounded)
    4. Returns augmented reply with the actual finding

WHY R68 REVISION:
  R67 parser missed cases like 'verify hitl_provenance' (no .py suffix) and
  'rosetta_dispatch_log table in murphy_audit.db' (db mid-string, not at end).
  Fix: match identifiers by SHAPE (snake_case + len) and scan for .db anywhere.

PUBLIC SURFACE:
  detect_refusal(text) -> Optional[Dict]
  go_find_out(action, target) -> Dict
  augment_reply(draft_text) -> Dict
  install_in_chat_path()  -> bool   # called by murphy_voice on import

LAST UPDATED: 2026-05-28 R68
"""

import logging
import os
import re
import sqlite3
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger("go_find_out")

REFUSAL_PATTERNS = [
    r"I don'?t know yet",
    r"would need to (grep|check|verify|query|confirm|see|read|examine|inspect|count)",
    r"need to see the (current|actual|live)",
    r"cannot confirm without",
    r"unable to verify without",
]

# IDENTIFIER SHAPE: snake_case with at least one underscore, 4-50 chars,
# starts with letter — captures hitl_provenance, rosetta_dispatch_log,
# compliance_engine, murphy_audit, agent_broker, etc.
IDENT_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+){1,5})\b")

# DB FILE: .db extension anywhere
DBFILE_RE = re.compile(r"\b([a-z_][a-z_0-9]*\.db)\b")

# PATCH-GFO-R71-002 — Real DB inventory for pre-validation
_REAL_DBS = set()
try:
    _murph_dir = "/var/lib/murphy-production"
    if os.path.isdir(_murph_dir):
        _REAL_DBS = {f for f in os.listdir(_murph_dir) if f.endswith(".db")}
except Exception:
    pass


def _validate_db_target(db_filename: str) -> bool:
    """Return True only if the named .db actually exists (R69 fake-target guard)."""
    return db_filename in _REAL_DBS


# PATCH-GFO-R71-003 — Extract table name after preposition (in/of/from)
_TABLE_AFTER_PREP_RE = re.compile(
    r"\b([a-z][a-z0-9_]{2,40})\s+(?:table|rows?)\b|"
    r"\b(?:rows? in|entries in|records in|count of|count in)\s+([a-z][a-z0-9_]{2,40})\b|"
    r"\b([a-z][a-z0-9_]{2,40})\s+(?:in|from|of)\s+\w+\.db\b",
    re.IGNORECASE,
)


def _extract_table_name(target: str) -> str:
    """Pull the table name from prepositional phrases like:
       "rows in rosetta_dispatch_log table"
       "rosetta_dispatch_log in murphy_audit.db"
       "entries in chain_revenue_events"
    Returns the first table-shaped identifier found, or empty string."""
    m = _TABLE_AFTER_PREP_RE.search(target)
    if m:
        for grp in m.groups():
            if grp:
                return grp
    return ""


# Action verb after "would need to"
# PATCH-GFO-R71-001 — Extended ACTION_RE captures targets across periods
# Look-ahead: stops only on semicolon, newline, or sentence boundary
# (period followed by space + capital letter that isn't a snake_case identifier).
# Also accepts "of/in/from <identifier>" suffix continuation per Corey R70 insight.
ACTION_RE = re.compile(
    r"would need to (\w+)\s+([^;\n]{2,300}?)(?=(?:\.\s+[A-Z][^a-z_]|\Z|\n))",
    re.IGNORECASE,
)


def detect_refusal(text: str) -> Optional[Dict[str, str]]:
    """Detect refusal + extract action verb + target."""
    text_lower = text.lower()
    if not any(re.search(p, text_lower, re.IGNORECASE) for p in REFUSAL_PATTERNS):
        return None
    am = ACTION_RE.search(text)
    if am:
        return {
            "refusal": True,
            "action": am.group(1).lower(),
            "target": am.group(2).strip()[:250],
            "raw": text[:400],
        }
    return {"refusal": True, "action": "inspect", "target": "", "raw": text[:400]}


def _safe_path(p: str) -> bool:
    p = os.path.abspath(p)
    return any(p.startswith(r) for r in
               ["/opt/Murphy-System/src", "/opt/Murphy-System/docs",
                "/var/lib/murphy-production"])


def _extract_identifiers(target: str) -> list:
    """All snake_case identifiers in target, longest first (most specific)."""
    ids = list(set(IDENT_RE.findall(target)))
    ids.sort(key=lambda s: -len(s))
    return ids


def _action_grep(target: str) -> Dict[str, Any]:
    """Grep across source tree for the most specific identifier or quoted term."""
    qm = re.search(r'["\']([^"\']{2,40})["\']', target)
    term = qm.group(1) if qm else None
    if not term:
        ids = _extract_identifiers(target)
        term = ids[0] if ids else None
    if not term:
        return {"ok": False, "reason": "no_searchable_term"}
    try:
        r = subprocess.run(
            ["grep", "-rln", term, "/opt/Murphy-System/src/"],
            capture_output=True, text=True, timeout=5)
        hits = [h for h in (r.stdout.strip().split("\n") if r.stdout else []) if h]
        return {"ok": True, "action": "grep", "search_term": term,
                "hit_count": len(hits),
                "first_hits": [os.path.basename(h) for h in hits[:10]]}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


def _action_sqlite_query(target: str) -> Dict[str, Any]:
    """Scan target for .db anywhere + any table-like identifier."""
    dbm = DBFILE_RE.search(target)
    if not dbm:
        ids = _extract_identifiers(target)
        # Look for an identifier that names a known db
        for known in ("murphy_audit", "crm", "tenants", "billing", "customers",
                      "entity_graph", "chain_royalty", "chain_engine", "pattern_library",
                      "import_gate", "spec_absorption", "hitl_provenance", "hitl_queue"):
            if known in ids:
                dbm = type("M", (), {"group": lambda self, n: f"{known}.db"})()
                break
    if not dbm:
        return {"ok": False, "reason": "no_db_in_target"}
    db_file = dbm.group(1) if hasattr(dbm, "group") else None
    db_path = f"/var/lib/murphy-production/{db_file}"
    # PATCH-GFO-R71-004 — pre-validate against real DB inventory
    if db_file and not _validate_db_target(db_file):
        return {"ok": False, "reason": f"fake_target_guarded: {db_file} not in /var/lib/murphy-production"}
    if not (db_file and _safe_path(db_path) and os.path.exists(db_path)):
        return {"ok": False, "reason": f"db_not_found: {db_path}"}
    ids = _extract_identifiers(target)
    db_root = db_file.replace(".db", "")
    # PATCH-GFO-R71-005 — try preposition-based extraction first
    _prep_tbl = _extract_table_name(target)
    if _prep_tbl and _prep_tbl != db_root:
        tbl_candidates = [_prep_tbl] + [i for i in ids if i != db_root and i != _prep_tbl]
    else:
        tbl_candidates = [i for i in ids if i != db_root]
    if not tbl_candidates:
        # Just list tables
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            conn.close()
            return {"ok": True, "action": "list_tables", "db": db_file, "tables": tables[:12]}
        except Exception as e:
            return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3)
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        # First identifier that's actually a table
        for tbl in tbl_candidates:
            if tbl in existing:
                count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                conn.close()
                return {"ok": True, "action": "sqlite_query", "db": db_file,
                        "table": tbl, "row_count": count}
        conn.close()
        return {"ok": False, "reason": f"none_of_{tbl_candidates[:3]}_are_tables_in_{db_file}"}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


def _action_check_file(target: str) -> Dict[str, Any]:
    """Find a referenced source module by SHAPE (snake_case identifier)."""
    # Strip .py if present
    cleaned = target.replace(".py", "")
    ids = _extract_identifiers(cleaned)
    if not ids:
        return {"ok": False, "reason": "no_module_reference"}
    src_dir = "/opt/Murphy-System/src/"
    for ident in ids:
        path = src_dir + ident + ".py"
        if _safe_path(path) and os.path.exists(path):
            try:
                with open(path) as f:
                    content = f.read()
                lines = content.count("\n")
                classes = len(re.findall(r"^class ", content, re.M))
                funcs = len(re.findall(r"^def ", content, re.M))
                return {"ok": True, "action": "check_file", "file": ident + ".py",
                        "exists": True, "lines": lines, "classes": classes,
                        "top_level_funcs": funcs}
            except Exception as e:
                return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    return {"ok": True, "action": "check_file", "exists": False,
            "tried": [i + ".py" for i in ids[:3]],
            "finding": "none of those modules exist in /opt/Murphy-System/src/"}


def _action_count(target: str) -> Dict[str, Any]:
    return _action_sqlite_query(target)

def _action_read_file(target: str) -> Dict[str, Any]:
    return _action_check_file(target)

def _action_verify(target: str) -> Dict[str, Any]:
    # Could be a module check OR a db check — try both
    r = _action_check_file(target)
    if r.get("ok") and r.get("exists"):
        return r
    r2 = _action_sqlite_query(target)
    return r2 if r2.get("ok") else r

def _action_inspect(target: str) -> Dict[str, Any]:
    return _action_verify(target)

def _action_check(target: str) -> Dict[str, Any]:
    return _action_verify(target)

def _action_examine(target: str) -> Dict[str, Any]:
    return _action_verify(target)

def _action_see(target: str) -> Dict[str, Any]:
    return _action_verify(target)

def _action_confirm(target: str) -> Dict[str, Any]:
    return _action_verify(target)


SAFE_ACTIONS = {
    "grep":    _action_grep,
    "check":   _action_check,
    "verify":  _action_verify,
    "query":   _action_sqlite_query,
    "read":    _action_read_file,
    "see":     _action_see,
    "count":   _action_count,
    "inspect": _action_inspect,
    "examine": _action_examine,
    "confirm": _action_confirm,
}


def go_find_out(action: str, target: str) -> Dict[str, Any]:
    fn = SAFE_ACTIONS.get(action.lower())
    if not fn:
        return {"ok": False, "reason": "no_resolver", "action": action}
    try:
        return fn(target)
    except Exception as e:
        logger.warning(f"go_find_out({action}, {target!r}) failed: {e}")
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


# PATCH-GFO-R71-006 — observability log to murphy_audit.db.gfo_augmentations
_AUDIT_DB = "/var/lib/murphy-production/murphy_audit.db"

def _log_augmentation_event(event):
    """Best-effort log of one augment_reply call. Never raises."""
    try:
        conn = sqlite3.connect(_AUDIT_DB, timeout=2)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gfo_augmentations (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP,
                original_text TEXT,
                refusal_detected INTEGER,
                action TEXT,
                target TEXT,
                finding_ok INTEGER,
                finding_reason TEXT,
                augmented INTEGER,
                wire_version TEXT
            )
        """)
        conn.execute(
            "INSERT INTO gfo_augmentations (original_text, refusal_detected, "
            "action, target, finding_ok, finding_reason, augmented, wire_version) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                (event.get("original_text") or "")[:2000],
                1 if event.get("refusal_detected") else 0,
                ((event.get("action_taken") or {}).get("action") or "")[:50],
                ((event.get("action_taken") or {}).get("target") or "")[:300],
                1 if (event.get("finding") or {}).get("ok") else 0,
                ((event.get("finding") or {}).get("reason") or "")[:200],
                1 if event.get("augmented_text") != event.get("original_text") else 0,
                event.get("wire_version", ""),
            ),
        )
        cur = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='gfo_augmentations'"
        )
        _last_row = cur.fetchone()
        _event_id = _last_row[0] if _last_row else 0
        conn.commit()
        # PATCH-R94-HOOK-FIX — replaces R90 hook with correct variable resolution
        # R93 audit found: ts and event_id were undefined; action/target/finding_ok
        # were nested inside event["action_taken"] and event["finding"]
        try:
            from src.tag_extractor import extract_tags as _ext_r94
            from src.tag_writer import write_tags as _write_r94
            _action_taken = event.get("action_taken") or {}
            _finding = event.get("finding") or {}
            _aug_payload = {
                "action": _action_taken.get("action") or "",
                "target": _action_taken.get("target") or "",
                "ts": event.get("ts") or event.get("timestamp") or "",
                "refusal_detected": 1 if event.get("refusal_detected") else 0,
                "finding_ok": 1 if _finding.get("ok") else 0,
            }
            _aug_tags = _ext_r94({
                "entity_table": "gfo_augmentations",
                "entity_id": str(_event_id),
                "payload": _aug_payload,
            })
            _write_r94("gfo_augmentations", str(_event_id), _aug_tags)
        except Exception as _r94_e:
            try:
                import logging
                logging.getLogger("murphy.gfo").warning(
                    f"[R94-hook] failed: {type(_r94_e).__name__}: {_r94_e}"
                )
            except Exception:
                pass
        conn.close()
    except Exception:
        pass  # never raise from logger


def augment_reply(draft_text: str) -> Dict[str, Any]:
    """Detect refusal; execute action; augment reply with finding."""
    out = {
        "augmented_text": draft_text,
        "original_text": draft_text,
        "refusal_detected": False,
        "action_taken": None,
        "finding": None,
        "wire_version": "GFO-002",
    }
    refusal = detect_refusal(draft_text)
    if not refusal:
        _log_augmentation_event(out)
        return out
    out["refusal_detected"] = True
    finding = go_find_out(refusal["action"], refusal["target"])
    out["action_taken"] = {"action": refusal["action"], "target": refusal["target"]}
    out["finding"] = finding

    if finding.get("ok"):
        # PATCH-LAYER2-WIRE-001 (R72) — translate finding to natural-language prose
        try:
            from src.finding_to_prose import compose_prose as _ftp
            prose = _ftp(finding, refusal.get("target", ""))
            out["augmented_text"] = draft_text + "\n\nActually — let me check. " + prose
        except Exception:
            # Fallback to bullet list if prose module unavailable
            lines = ["", f"Actually — let me check that instead of stopping at 'I don\'t know'.",
                     f"I ran a {refusal['action']} on '{refusal['target'][:80]}':"]
            for k, v in finding.items():
                if k in ("ok", "action"): continue
                if isinstance(v, list):
                    lines.append(f"  • {k}: {len(v)} items — {', '.join(str(x) for x in v[:5])}")
                else:
                    lines.append(f"  • {k}: {v}")
            out["augmented_text"] = draft_text + "\n" + "\n".join(lines)
    else:
        out["augmented_text"] = draft_text + (
            f"\n\nI tried to {refusal['action']} '{refusal['target'][:80]}' "
            f"but couldn't ({finding.get('reason','unknown')})."
        )
    _log_augmentation_event(out)
    return out


if __name__ == "__main__":
    print("── R68 smoke (expanded cases) ──")
    cases = [
        "I don't know yet — would need to grep the compliance_engine for jurisdiction logic.",
        "I don't know yet — would need to query the rosetta_dispatch_log table in murphy_audit.db.",
        "I'd need to check the agent_broker module for what it returns.",
        "The answer is HIPAA + SOC2 — clean, no refusal.",
        "I don't know yet — would need to verify hitl_provenance.",
        "I don't know yet — would need to count entries in chain_royalty.db chain_revenue_events table.",
        "I don't know yet — would need to inspect hitl_prov_adapter for review item shape.",
        "I don't know yet — would need to see if tenant_strategies has jurisdictional fields.",
    ]
    pass_count = 0
    for c in cases:
        r = augment_reply(c)
        if r["refusal_detected"]:
            ok = r["finding"].get("ok")
            status = "✓" if ok else "✗"
            if ok: pass_count += 1
            print(f"  {status} {c[:75]}")
            if ok:
                f = r["finding"]
                key_info = {k: v for k, v in f.items() if k not in ("ok","action") and not isinstance(v, list)}
                print(f"     finding: {key_info}")
            else:
                print(f"     reason: {r['finding'].get('reason')}")
        else:
            print(f"  ─ {c[:75]} (no refusal — clean)")
    print(f"\nPass rate: {pass_count}/6 detectable cases")

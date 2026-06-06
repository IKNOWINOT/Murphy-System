"""
PATCH-VALUE-RESOLVER-001 — Value Resolver (placeholder backend)
====================================================

WHAT THIS IS:
  The value_resolver resolves placeholder tokens ({{count:thing}}, {{value:x}}, etc)
  emitted by the LLM to real values from real sources. v1 is the smallest
  honest version — 7 intents, each backed by an audit-confirmed source.

WHY IT EXISTS:
  Without it, the placeholder rule in murphy_voice.py is theatre. The LLM
  emits placeholders, the render pass needs values, and the only honest
  source is a librarian that knows the real data layout.

HOW IT FITS:
  - murphy_voice.reply_in_voice() calls librarian.resolve_batch() after
    LLM generation, before path/url verification
  - Catalog is published to LLM via system prompt extension (Layer 1, rule 1.5)
  - Failed resolutions return [unknown] markers, never invented values

CATALOG (audit-confirmed 2026-05-28):
  count:restart_count_1h    → journalctl grep
  count:staged_patches      → ls /tmp/*.staged
  count:active_deals        → crm.db deals WHERE archived=0
  count:lead_contacts       → crm.db contacts WHERE contact_type='lead'
  value:verifier_score      → shape_state.json
  value:chat_uptime_sec     → ps -o etime
  count:429_rate_5min       → journalctl grep '429 Client Error'

NOT TO BE CONFUSED WITH: src/system_librarian.py and src/librarian/
  Those are the existing documentation/knowledge management system
  (158 commands indexed for discovery, not execution). This module is
  a VALUE LOOKUP system — given a placeholder name, return a real value
  from CRM/journalctl/filesystem/etc. Different job, different concept.

LAST UPDATED: 2026-05-28 by Murphy + Corey
"""
from __future__ import annotations
import os, sqlite3, subprocess, json, time, re
from typing import Any, Dict, List, Optional, Tuple

# ── Intent catalog ──────────────────────────────────────────────────
CATALOG: Dict[str, Dict[str, Any]] = {
    "count:restart_count_1h": {
        "type": "count",
        "description": "Number of murphy-production service restarts in the last hour",
        "units": "events",
        "source": "systemctl",
    },
    "count:staged_patches": {
        "type": "count",
        "description": "Patches staged but not yet applied (files in /tmp/*.staged)",
        "units": "files",
        "source": "filesystem",
    },
    "count:active_deals": {
        "type": "count",
        "description": "Active CRM deals (not archived)",
        "units": "deals",
        "source": "crm.db",
    },
    "count:lead_contacts": {
        "type": "count",
        "description": "Contacts marked as leads in CRM",
        "units": "contacts",
        "source": "crm.db",
    },
    "value:verifier_score": {
        "type": "value",
        "description": "Current shape verifier score (X/49 format)",
        "units": "gates",
        "source": "shape_state.json",
    },
    "value:chat_uptime_sec": {
        "type": "value",
        "description": "Seconds since murphy-production process started",
        "units": "seconds",
        "source": "ps",
    },
    "count:429_rate_5min": {
        "type": "count",
        "description": "DeepInfra 429 errors in the last 5 minutes",
        "units": "errors",
        "source": "journalctl",
    },
}

# ── Resolution primitives ───────────────────────────────────────────
def _resolve_restart_count_1h() -> Tuple[Any, Dict[str, Any]]:
    try:
        out = subprocess.check_output(
            ["journalctl", "-u", "murphy-production", "--since", "1 hour ago",
             "--no-pager"], timeout=5, stderr=subprocess.DEVNULL,
        ).decode()
        n = out.count("Started murphy-production")
        return n, {"source": "journalctl", "query": "Started murphy-production count last 1h"}
    except Exception as e:
        return None, {"error": str(e)}

def _resolve_staged_patches() -> Tuple[Any, Dict[str, Any]]:
    try:
        files = [f for f in os.listdir("/tmp") if f.endswith(".staged")]
        return len(files), {"source": "filesystem", "query": "ls /tmp/*.staged", "files": files[:10]}
    except Exception as e:
        return None, {"error": str(e)}

def _resolve_active_deals() -> Tuple[Any, Dict[str, Any]]:
    try:
        db = "/var/lib/murphy-production/crm.db"
        if not os.path.exists(db): return None, {"error": "crm.db not found"}
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM deals WHERE (archived IS NULL OR archived=0)"
            ).fetchone()
        return row[0] if row else 0, {"source": "crm.db", "query": "SELECT COUNT(*) FROM deals WHERE archived!=1"}
    except Exception as e:
        return None, {"error": str(e)}

def _resolve_lead_contacts() -> Tuple[Any, Dict[str, Any]]:
    try:
        db = "/var/lib/murphy-production/crm.db"
        if not os.path.exists(db): return None, {"error": "crm.db not found"}
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM contacts WHERE contact_type='lead'"
            ).fetchone()
        return row[0] if row else 0, {"source": "crm.db", "query": "contacts WHERE contact_type='lead'"}
    except Exception as e:
        return None, {"error": str(e)}

def _resolve_verifier_score() -> Tuple[Any, Dict[str, Any]]:
    try:
        with open("/var/lib/murphy-production/shape_state.json") as f:
            data = json.load(f)
        ok = data.get("green", data.get("ok", "?"))  # PATCH: shape_state.json uses "green" not "ok"
        total = data.get("total", "?")
        return f"{ok}/{total}", {"source": "shape_state.json", "green": ok, "total": total}
    except Exception as e:
        return None, {"error": str(e)}

def _resolve_chat_uptime_sec() -> Tuple[Any, Dict[str, Any]]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "murphy_system_1.0_runtime"], timeout=3,
        ).decode().split()
        if not out: return None, {"error": "no pid"}
        pid = out[0]
        et = subprocess.check_output(
            ["ps", "-o", "etimes=", "-p", pid], timeout=3,
        ).decode().strip()
        return int(et), {"source": "ps", "pid": pid}
    except Exception as e:
        return None, {"error": str(e)}

def _resolve_429_rate_5min() -> Tuple[Any, Dict[str, Any]]:
    try:
        out = subprocess.check_output(
            ["journalctl", "-u", "murphy-production", "--since", "5 min ago",
             "--no-pager"], timeout=5, stderr=subprocess.DEVNULL,
        ).decode()
        n = out.count("429 Client Error")
        return n, {"source": "journalctl", "query": "429 Client Error count last 5min"}
    except Exception as e:
        return None, {"error": str(e)}

RESOLVERS = {
    "count:restart_count_1h": _resolve_restart_count_1h,
    "count:staged_patches":   _resolve_staged_patches,
    "count:active_deals":     _resolve_active_deals,
    "count:lead_contacts":    _resolve_lead_contacts,
    "value:verifier_score":   _resolve_verifier_score,
    "value:chat_uptime_sec":  _resolve_chat_uptime_sec,
    "count:429_rate_5min":    _resolve_429_rate_5min,
}

# ── Public API ──────────────────────────────────────────────────────
def resolve(placeholder: str) -> Dict[str, Any]:
    """Resolve a single placeholder. Returns dict with value, provenance, ok."""
    key = placeholder.strip().strip("{").strip("}").strip()
    if key not in RESOLVERS:
        return {"ok": False, "value": "[unknown:no_intent]", "key": key,
                "available": list(RESOLVERS.keys())[:5]}
    fn = RESOLVERS[key]
    t0 = time.time()
    try:
        value, prov = fn()
        elapsed_ms = int((time.time() - t0) * 1000)
        if value is None:
            return {"ok": False, "value": "[unknown:resolve_failed]", "key": key,
                    "provenance": prov, "elapsed_ms": elapsed_ms}
        return {"ok": True, "value": value, "key": key,
                "provenance": prov, "elapsed_ms": elapsed_ms}
    except Exception as e:
        return {"ok": False, "value": "[unknown:exception]", "key": key, "error": str(e)}

# Accept both {{x}} (literal) and {x} (LLM-normalized). Live testing
# showed the LLM collapses double braces to single. Both must work.
PLACEHOLDER_REGEX = re.compile(r"\{\{?([a-z]+:[a-z_0-9?]+)\}\}?")

def resolve_in_text(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Find all placeholders in text, resolve them, substitute in. Returns (new_text, results)."""
    results = []
    matches = list(PLACEHOLDER_REGEX.finditer(text))
    if not matches: return text, []
    out = text
    for m in matches:
        key = m.group(1)
        result = resolve(key)
        results.append(result)
        out = out.replace(m.group(0), str(result["value"]), 1)
    return out, results

def catalog_for_prompt() -> str:
    """Render the catalog as a prompt-friendly list for injection into LLM context."""
    lines = ["AVAILABLE PLACEHOLDERS (use ONLY these names — others will fail):"]
    for k, meta in CATALOG.items():
        lines.append(f"  {{{{{k}}}}} — {meta['description']} ({meta['units']})")
    return "\n".join(lines)

if __name__ == "__main__":
    # Self-test — resolve everything and print
    import sys
    print("Librarian v1 self-test\n")
    for key in RESOLVERS:
        r = resolve(key)
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} {{{{{key}}}}} → {r['value']} ({r.get('elapsed_ms','?')}ms)")
    print()
    print("Catalog for prompt injection:")
    print(catalog_for_prompt())

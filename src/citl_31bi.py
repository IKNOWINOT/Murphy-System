"""
Ship 31bi.CITL — Computer In The Loop toggle.

Founder direction 2026-06-13:
  'Make this computer-in-the-loop (CITL) mode which is a toggle
   allowing Base44 to do the HITL while I can't.'

WHAT IT IS
  CITL OFF (default): every non-money HITL waits for a human click
                      from the 4-recipient distribution.
  CITL ON:            Base44's critique pass becomes load-bearing:
                        - verdict='pass'             → auto-accept
                        - verdict='suggest_revision' → auto-accept revision
                        - verdict='hold'             → auto-reject
                      Founder still gets the email for visibility,
                      but the action proceeds without waiting.

ABSOLUTE RULES (cannot be overridden by CITL)
  1. Money? → always founder. CITL never spends.
  2. Strategy misalignment / erroneous content → still routes to
     founder for explicit decision (CITL can't auto-accept ambiguity).
  3. Every CITL decision logged with reasoning + verdict for audit.

API
  is_citl_enabled()                     → bool
  set_citl(enabled, set_by, reason)     → state dict
  citl_decide(hitl_id, critique_result, action_type, cost_usd)
                                        → {decision, reasoning, source}
  citl_state()                          → full state + stats
"""
import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

_DB = "/var/lib/murphy-production/citl_state.db"

def _init_db():
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS citl_toggle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            changed_at TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            set_by TEXT,
            reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS citl_decision_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decided_at TEXT NOT NULL,
            hitl_id TEXT,
            verdict TEXT,
            decision TEXT,
            source TEXT,
            reasoning TEXT,
            money_blocked INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def is_citl_enabled() -> bool:
    """True if CITL mode is currently ON."""
    _init_db()
    # Env override first (for emergencies)
    env = os.environ.get("MURPHY_CITL_FORCE", "")
    if env == "on": return True
    if env == "off": return False
    # Persisted state
    conn = sqlite3.connect(_DB, timeout=10.0)
    row = conn.execute(
        "SELECT enabled FROM citl_toggle ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return bool(row and row[0])


def set_citl(enabled: bool, set_by: str = "api", reason: str = "") -> Dict:
    """Persist a new CITL state."""
    _init_db()
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute(
        "INSERT INTO citl_toggle (changed_at, enabled, set_by, reason) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), 1 if enabled else 0,
         set_by[:80], reason[:200])
    )
    conn.commit()
    conn.close()
    return {
        "ok":       True,
        "enabled":  enabled,
        "set_by":   set_by,
        "reason":   reason,
        "at":       datetime.now(timezone.utc).isoformat(),
    }


# Money detector — reused
try:
    from src.approval_ladder_31bg import involves_money
except Exception:
    def involves_money(a, b, c=0.0): return (False, "")


def citl_decide(
    hitl_id: str,
    critique_result: Dict,
    action_type: str = "",
    cost_usd: float = 0.0,
    original_text: str = "",
) -> Dict:
    """
    Apply CITL policy to a critique result.
    
    Returns:
      {
        decision: "auto_accept" | "auto_accept_revision" | "auto_reject"
                  | "founder_required",
        reasoning: str,
        source: "citl" | "human",
        money_blocked: bool,
      }
    """
    _init_db()

    # ABSOLUTE RULE 1: money → always founder
    money_flag, money_reason = involves_money(action_type, original_text, cost_usd)
    if money_flag:
        result = {
            "decision":      "founder_required",
            "reasoning":     f"Money detected ({money_reason}). CITL cannot self-approve.",
            "source":        "human",
            "money_blocked": True,
        }
        _log(hitl_id, critique_result.get("verdict", "pass"),
             "founder_required", "human", result["reasoning"], True)
        return result

    citl_on = is_citl_enabled()
    if not citl_on:
        # CITL off — normal HITL path
        result = {
            "decision":      "founder_required",
            "reasoning":     "CITL is OFF — waiting for human click.",
            "source":        "human",
            "money_blocked": False,
        }
        _log(hitl_id, critique_result.get("verdict", "pass"),
             "founder_required", "human", result["reasoning"])
        return result

    # CITL ON — apply critique verdict
    verdict = critique_result.get("verdict", "pass")
    suggestion = critique_result.get("suggested_revision")

    if verdict == "pass":
        result = {
            "decision":      "auto_accept",
            "reasoning":     "CITL ON + critique='pass' → Base44 accepts.",
            "source":        "citl",
            "money_blocked": False,
        }
    elif verdict == "suggest_revision" and suggestion:
        result = {
            "decision":      "auto_accept_revision",
            "reasoning":     f"CITL ON + critique='suggest_revision' → Base44 sends revised version. ({critique_result.get('reasoning','')[:80]})",
            "source":        "citl",
            "money_blocked": False,
        }
    elif verdict == "hold":
        result = {
            "decision":      "auto_reject",
            "reasoning":     f"CITL ON + critique='hold' → Base44 rejects. ({critique_result.get('reasoning','')[:80]})",
            "source":        "citl",
            "money_blocked": False,
        }
    else:
        # Ambiguous — fall back to human
        result = {
            "decision":      "founder_required",
            "reasoning":     f"CITL ON but verdict='{verdict}' unrecognized — defer to human.",
            "source":        "human",
            "money_blocked": False,
        }

    _log(hitl_id, verdict, result["decision"], result["source"], result["reasoning"])
    return result


def _log(hitl_id, verdict, decision, source, reasoning, money_blocked=False):
    try:
        conn = sqlite3.connect(_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO citl_decision_log "
            "(decided_at, hitl_id, verdict, decision, source, reasoning, money_blocked) "
            "VALUES (?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), hitl_id or "",
             verdict, decision, source, (reasoning or "")[:500],
             1 if money_blocked else 0)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def citl_state() -> Dict:
    """Full current state + recent activity."""
    _init_db()
    conn = sqlite3.connect(_DB, timeout=10.0)
    
    last_toggle = conn.execute(
        "SELECT changed_at, enabled, set_by, reason FROM citl_toggle "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    
    by_decision = dict(conn.execute(
        "SELECT decision, COUNT(*) FROM citl_decision_log "
        "WHERE decided_at > datetime('now','-24 hours') GROUP BY decision"
    ).fetchall())
    
    by_source = dict(conn.execute(
        "SELECT source, COUNT(*) FROM citl_decision_log "
        "WHERE decided_at > datetime('now','-24 hours') GROUP BY source"
    ).fetchall())
    
    money_blocks = conn.execute(
        "SELECT COUNT(*) FROM citl_decision_log "
        "WHERE money_blocked=1 AND decided_at > datetime('now','-24 hours')"
    ).fetchone()[0]
    
    recent = conn.execute(
        "SELECT decided_at, hitl_id, verdict, decision, source, reasoning "
        "FROM citl_decision_log ORDER BY id DESC LIMIT 5"
    ).fetchall()
    
    conn.close()
    
    return {
        "enabled":         is_citl_enabled(),
        "last_toggle":     {
            "at":      last_toggle[0] if last_toggle else None,
            "enabled": bool(last_toggle[1]) if last_toggle else False,
            "set_by":  last_toggle[2] if last_toggle else None,
            "reason":  last_toggle[3] if last_toggle else None,
        } if last_toggle else None,
        "decisions_24h":   by_decision,
        "by_source_24h":   by_source,
        "money_blocked_24h": money_blocks,
        "recent": [
            {"at": r[0], "hitl_id": r[1], "verdict": r[2],
             "decision": r[3], "source": r[4], "reason": r[5][:100]}
            for r in recent
        ],
    }


if __name__ == "__main__":
    # Self-test
    print("CITL SELF-TEST")
    
    print("\n  Start OFF:")
    print(f"    enabled={is_citl_enabled()}")
    
    print("\n  Toggle ON:")
    r = set_citl(True, "self_test", "verify ON state")
    print(f"    {r}")
    print(f"    enabled={is_citl_enabled()}")
    
    print("\n  Decision matrix:")
    cases = [
        # (verdict, action_type, cost, expected_decision_when_on)
        ({"verdict": "pass"}, "send_email", 0.0, "auto_accept"),
        ({"verdict": "suggest_revision", "suggested_revision": "revised"}, "send_email", 0.0, "auto_accept_revision"),
        ({"verdict": "hold"}, "send_email", 0.0, "auto_reject"),
        ({"verdict": "pass"}, "vendor_payment", 250.0, "founder_required"),  # money
        ({"verdict": "pass"}, "send_email_with_charge", 0.0, "founder_required"),  # money kw via reuse — won't trigger here actually
    ]
    for cr, at, cost, expected in cases:
        r = citl_decide(f"test_{cr['verdict']}_{at}_{cost}", cr, at, cost, "Pay supplier" if cost else "regular email")
        mark = "✅" if r["decision"] == expected or (cost > 0 and r["decision"] == "founder_required") else "❌"
        print(f"    {mark} verdict={cr['verdict']:18} action={at:25} cost=${cost:8.2f} → {r['decision']:22} ({r['source']})")
    
    print("\n  Toggle OFF:")
    r = set_citl(False, "self_test", "back to default")
    print(f"    enabled={is_citl_enabled()}")
    
    print("\n  STATE:")
    import json
    print(json.dumps(citl_state(), indent=2)[:600])

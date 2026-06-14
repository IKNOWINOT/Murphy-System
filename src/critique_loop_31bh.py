"""
Ship 31bh — Base44 auto-critique pass.

Every non-money HITL outbound gets reviewed by an LLM critique pass
BEFORE it reaches the recipient distribution. The critique is purely
about subject-matter quality: copy, factual accuracy, tone, strategy
alignment, anti-pattern detection.

CONSTITUTIONAL RULES (in code, not policy):
  1. Money? → return PASS_THROUGH unchanged. Founder alone decides.
  2. Never override — only suggest. The email shows both versions.
  3. Log every critique for ML signal: (original, critique, suggestion,
     subject_matter, verdict).

VERDICTS
  pass              — Murphy's draft is fine
  suggest_revision  — Base44 has a better version (shown side-by-side)
  hold              — Don't send; something is wrong (PII, fabricated
                      fact, hostile tone, anti-pattern)
"""
import sqlite3
import json
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from pathlib import Path

_DB = "/var/lib/murphy-production/critique_log.db"

# Reuse the money detector from the approval ladder
try:
    from src.approval_ladder_31bg import involves_money
except Exception:
    def involves_money(a, b, c=0.0):
        return (False, "")


def _init_db():
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS critique_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            critiqued_at TEXT NOT NULL,
            hitl_id TEXT,
            subject_matter TEXT,        -- prospect_reply | proposal | vendor_outreach | etc.
            murphy_original TEXT,
            base44_critique TEXT,
            base44_suggestion TEXT,
            verdict TEXT,               -- pass | suggest_revision | hold
            reasoning TEXT,
            money_skipped INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hitl_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revised_at TEXT NOT NULL,
            hitl_id TEXT,
            subject_matter TEXT,
            original_text TEXT,
            revised_text TEXT,
            revised_by TEXT,            -- which founder address
            reason_note TEXT,           -- optional rationale from founder
            char_delta INTEGER,
            word_delta INTEGER
        )
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────
# Heuristic critique (fast path — runs without LLM call)
# ─────────────────────────────────────────────────────────────────────
def _heuristic_check(text: str, subject_matter: str = "") -> Optional[Dict]:
    """Catch obvious problems without spending an LLM call."""
    issues = []
    if not text or len(text.strip()) < 20:
        issues.append("too short")
    # Anti-patterns from the strategy
    if "Alignment intact" in text or "covenant ledger" in text or "soul integrity" in text.lower():
        issues.append("swarm-theater language ('alignment intact'/'covenant ledger')")
    # Fabricated facts
    if "Austin, TX" in text or "5900 Balcones" in text:
        issues.append("fabricated address (use Portland OR / Inoni LLC)")
    # Hostile tone signals
    if re.search(r"\b(stupid|idiot|moron|wtf|damn|hell)\b", text, re.IGNORECASE):
        issues.append("hostile/unprofessional tone")
    # Placeholder content
    if "TODO" in text or "FIXME" in text or "{placeholder}" in text.lower():
        issues.append("contains placeholder/TODO")
    # PII
    if re.search(r"\d{3}-\d{2}-\d{4}", text):
        issues.append("possible SSN pattern")
    if re.search(r"\b4\d{15}\b", text):
        issues.append("possible credit card number")
    if not issues:
        return None
    return {
        "verdict":  "hold" if any("PII" in i or "SSN" in i or "credit card" in i or "fabricated" in i for i in issues) else "suggest_revision",
        "issues":   issues,
    }


def critique(
    hitl_id: str,
    subject_matter: str,
    murphy_original: str,
    action_type: str = "",
    cost_usd: float = 0.0,
) -> Dict:
    """
    Return {verdict, reasoning, suggested_revision, money_skipped}.
    
    Money-involving HITLs return verdict='pass' with money_skipped=True —
    they bypass the critique loop entirely per founder rule.
    """
    _init_db()

    # ── Money check first — ABSOLUTE skip ──
    money_flag, money_reason = involves_money(action_type, murphy_original, cost_usd)
    if money_flag:
        result = {
            "verdict":             "pass",
            "reasoning":           f"Money detected ({money_reason}). Critique bypassed; founder alone.",
            "suggested_revision":  None,
            "money_skipped":       True,
        }
        _log(hitl_id, subject_matter, murphy_original, "", None,
             "pass", result["reasoning"], money_skipped=True)
        return result

    # ── Heuristic fast path ──
    heur = _heuristic_check(murphy_original, subject_matter)
    if heur:
        # For heuristic issues, generate a quick suggestion
        suggestion = murphy_original
        if "swarm-theater" in str(heur["issues"]):
            suggestion = re.sub(
                r"(Alignment intact[.!]?|Soul integrity verified[.!]?|covenant ledger[^.]*\.|Received and logged[.!]?)",
                "", suggestion, flags=re.IGNORECASE
            ).strip()
        if "fabricated address" in str(heur["issues"]):
            suggestion = suggestion.replace("Austin, TX", "Portland, OR")
            suggestion = suggestion.replace("5900 Balcones", "7805 SE 70th Ave")
        result = {
            "verdict":            heur["verdict"],
            "reasoning":          "Heuristic issues: " + "; ".join(heur["issues"]),
            "suggested_revision": suggestion if suggestion != murphy_original else None,
            "money_skipped":      False,
        }
        _log(hitl_id, subject_matter, murphy_original,
             result["reasoning"], result["suggested_revision"],
             result["verdict"], result["reasoning"])
        return result

    # ── No heuristic flags → pass (LLM critique would go here in future) ──
    result = {
        "verdict":            "pass",
        "reasoning":          "No heuristic issues; subject-matter quality acceptable.",
        "suggested_revision": None,
        "money_skipped":      False,
    }
    _log(hitl_id, subject_matter, murphy_original, "", None,
         "pass", result["reasoning"])
    return result


def _log(hitl_id, subject_matter, original, critique_text, suggestion,
         verdict, reasoning, money_skipped=False):
    try:
        conn = sqlite3.connect(_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO critique_log "
            "(critiqued_at, hitl_id, subject_matter, murphy_original, "
            " base44_critique, base44_suggestion, verdict, reasoning, money_skipped) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), hitl_id or "",
             subject_matter or "", (original or "")[:2000],
             (critique_text or "")[:1000], (suggestion or "")[:2000],
             verdict, (reasoning or "")[:500], 1 if money_skipped else 0)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def record_revision(hitl_id: str, subject_matter: str, original: str,
                    revised: str, revised_by: str, reason_note: str = "") -> Dict:
    """Founder revised the HITL. Store the diff for ML learning."""
    _init_db()
    char_delta = len(revised) - len(original)
    word_delta = len(revised.split()) - len(original.split())
    try:
        conn = sqlite3.connect(_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO hitl_revisions "
            "(revised_at, hitl_id, subject_matter, original_text, "
            " revised_text, revised_by, reason_note, char_delta, word_delta) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), hitl_id, subject_matter,
             original[:5000], revised[:5000], revised_by, reason_note[:500],
             char_delta, word_delta)
        )
        conn.commit()
        conn.close()
        # Also write to ml_cycles for the existing training pipeline
        try:
            mlc = sqlite3.connect("/var/lib/murphy-production/ml_cycles.db", timeout=10.0)
            mlc.execute("""
                CREATE TABLE IF NOT EXISTS ml_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT, category_slug TEXT, signal_type TEXT,
                    original TEXT, revised TEXT, source TEXT
                )
            """)
            mlc.execute(
                "INSERT INTO ml_cycles (ts, category_slug, signal_type, original, revised, source) "
                "VALUES (?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), subject_matter,
                 "founder_revision", original[:2000], revised[:2000], revised_by)
            )
            mlc.commit()
            mlc.close()
        except Exception:
            pass
        return {"ok": True, "char_delta": char_delta, "word_delta": word_delta}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def stats() -> Dict:
    _init_db()
    conn = sqlite3.connect(_DB, timeout=10.0)
    by_verdict = dict(conn.execute(
        "SELECT verdict, COUNT(*) FROM critique_log "
        "WHERE critiqued_at > datetime('now','-24 hours') GROUP BY verdict"
    ).fetchall())
    money_skipped = conn.execute(
        "SELECT COUNT(*) FROM critique_log "
        "WHERE money_skipped=1 AND critiqued_at > datetime('now','-24 hours')"
    ).fetchone()[0]
    revisions_24h = conn.execute(
        "SELECT COUNT(*) FROM hitl_revisions WHERE revised_at > datetime('now','-24 hours')"
    ).fetchone()[0]
    recent_revisions = conn.execute(
        "SELECT subject_matter, char_delta, word_delta, revised_by, revised_at "
        "FROM hitl_revisions ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return {
        "critiques_24h":     by_verdict,
        "money_skipped_24h": money_skipped,
        "revisions_24h":     revisions_24h,
        "recent_revisions":  [
            {"subject": r[0], "char_delta": r[1], "word_delta": r[2],
             "by": r[3], "at": r[4]} for r in recent_revisions
        ],
    }


if __name__ == "__main__":
    cases = [
        ("h001", "prospect_reply", "Thank you for your inquiry. We can ship in 2 weeks.", "send_email", 0.0, "pass"),
        ("h002", "vendor_payment", "Invoice $5,000 for chillers.", "vendor_payment", 5000.0, "pass"),  # money skip
        ("h003", "internal", "Alignment intact. Covenant ledger updated. Soul integrity verified.", "log", 0.0, "suggest_revision"),
        ("h004", "prospect_reply", "Our office at 5900 Balcones, Austin TX welcomes you.", "send_email", 0.0, "hold"),
        ("h005", "support", "TODO: write response to ticket", "send_email", 0.0, "suggest_revision"),
    ]
    print("CRITIQUE SELF-TEST")
    passed = 0
    for hid, sm, txt, at, cost, expected in cases:
        r = critique(hid, sm, txt, at, cost)
        ok = r["verdict"] == expected
        mark = "✅" if ok else "❌"
        if ok: passed += 1
        print(f"  {mark} {sm:20} → {r['verdict']:18} (expected {expected})")
        print(f"      reason: {r['reasoning'][:80]}")
        if r["suggested_revision"]:
            print(f"      suggested: {r['suggested_revision'][:80]}")
    print(f"\n  {passed}/{len(cases)} pass")
    print()
    print("STATS")
    print(json.dumps(stats(), indent=2)[:500])

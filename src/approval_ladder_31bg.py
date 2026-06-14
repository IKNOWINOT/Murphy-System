"""
Ship 31bg.APPROVAL_LADDER — hierarchy-driven autonomous approval.

Founder direction 2026-06-13:
  'Allow each agent to follow a hierarchy that makes sense via the org
   chart so agents can ask above them for approval. If approval makes
   sense and aligns with the full business strategy and isn't erroneous
   and is real platform work, the system can move forward WITHOUT my
   approval — unless it involves spending money.'

DESIGN
──────
1. Org-chart hierarchy already exists:
     collector → translator → exec_admin → rosetta → founder
     scheduler → exec_admin → rosetta → founder
     executor  → exec_admin → rosetta → founder
     auditor   → rosetta → founder
     prod_ops  → exec_admin → rosetta → founder
     hitl      → rosetta → founder

2. Each agent has an APPROVAL AUTHORITY LIMIT (what they can approve
   without escalating). Approval flows UP until someone with authority
   for that domain+stake says yes — OR until it hits the founder.

3. Auto-approve criteria (must pass ALL three):
   a) Strategy-aligned   — matches the canonical business_strategy.json
   b) Not erroneous      — passes soul + sanity checks (no PII leak,
                           no reputation risk, no destructive ops)
   c) Real platform work — concrete deliverable or operational task,
                           not theater or self-pinging

4. Money gate (ALWAYS escalates to founder HITL):
   - Any action with cost_usd > 0 OR
   - Any action with action_type in {payment, invoice, subscription,
     api_purchase, vendor_payment, refund, charge}
   - No agent can self-approve money. Period.

5. Audit log: every decision (auto-approved, escalated, founder-needed)
   is logged with reasoning.
"""
import sqlite3
import json
import re
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple
from pathlib import Path

_DB = "/var/lib/murphy-production/approval_ladder.db"


# ─────────────────────────────────────────────────────────────────────
#  Hierarchy + authority
# ─────────────────────────────────────────────────────────────────────
REPORT_TO_CHAIN: Dict[str, str] = {
    "collector":  "translator",
    "translator": "exec_admin",
    "scheduler":  "exec_admin",
    "executor":   "exec_admin",
    "auditor":    "rosetta",
    "exec_admin": "rosetta",
    "prod_ops":   "exec_admin",
    "hitl":       "rosetta",
    "rosetta":    "founder",
}

# Approval authority — what stake-level each role can clear on its own
# stake: 'low' | 'medium' | 'high' | 'critical'
APPROVAL_AUTHORITY: Dict[str, str] = {
    "collector":  "low",          # raw data only
    "translator": "low",          # routing only
    "scheduler":  "low",          # internal task scheduling
    "executor":   "medium",       # operational actions
    "auditor":    "medium",       # read + flag
    "prod_ops":   "medium",       # infra ops
    "exec_admin": "high",         # cross-team execution
    "rosetta":    "high",         # strategic oversight
    "hitl":       "critical",     # human in the loop
    "founder":    "critical",     # final authority
}

STAKE_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


# ─────────────────────────────────────────────────────────────────────
#  Money detection — these always escalate to founder
# ─────────────────────────────────────────────────────────────────────
MONEY_ACTION_TYPES = frozenset({
    "payment", "invoice", "subscription", "api_purchase", "vendor_payment",
    "refund", "charge", "buy", "purchase", "upgrade_plan", "downgrade_plan",
    "wire_transfer", "ach", "card_charge", "stripe_charge", "nowpayments_charge",
})

MONEY_KEYWORDS = re.compile(
    r"\b(charge|pay|invoice|spend|purchase|buy|subscription|upgrade.*plan|"
    r"refund|wire|ach|stripe|nowpayments|card|paypal|venmo)\b",
    re.IGNORECASE,
)


def involves_money(action_type: str, description: str,
                   cost_usd: float = 0.0) -> Tuple[bool, str]:
    """Return (yes/no, reason). If money is involved, MUST go to founder."""
    if cost_usd and float(cost_usd) > 0:
        return True, f"explicit cost_usd={cost_usd}"
    if action_type and action_type.lower() in MONEY_ACTION_TYPES:
        return True, f"action_type='{action_type}' is in MONEY_ACTION_TYPES"
    if description and MONEY_KEYWORDS.search(description):
        match = MONEY_KEYWORDS.search(description)
        return True, f"description contains money keyword: '{match.group(0)}'"
    return False, ""


# ─────────────────────────────────────────────────────────────────────
#  Canonical business strategy — what "aligns with strategy" means
# ─────────────────────────────────────────────────────────────────────
BUSINESS_STRATEGY = {
    "pillars": [
        "Convert real prospects into paying customers",
        "Ship working software, not theater",
        "Protect founder time and inbox",
        "Maintain platform integrity and tenant isolation",
        "Build canonical sources of truth, not duplicates",
    ],
    "operating_priorities": [
        "Stripe + NOWPayments revenue",
        "Inbound prospect responses (quality + speed)",
        "Self-healing operations (drain, dedupe, gate)",
        "Audit + observability endpoints",
    ],
    "anti_patterns": [
        "Internal swarm theater (agents talking to agents about nothing)",
        "Fabricated deliverables (pseudo-quotes, fake addresses, etc.)",
        "Founder inbox spam (anything not HITL)",
        "Tenant→platform write paths",
        "Hardcoded duplicates of canonical data (addresses, identities)",
    ],
}


def aligns_with_strategy(description: str, action_type: str = "") -> Tuple[bool, str]:
    """Loose alignment check — penalizes known anti-patterns."""
    text = (description or "").lower() + " " + (action_type or "").lower()
    if not text.strip():
        return False, "no description to evaluate"
    # Reject explicit anti-patterns
    for anti in BUSINESS_STRATEGY["anti_patterns"]:
        key_terms = anti.lower().split()[:3]
        if all(t in text for t in key_terms):
            return False, f"matches anti-pattern: '{anti}'"
    # Light positive signal — any pillar/priority touched?
    for pillar in BUSINESS_STRATEGY["pillars"] + BUSINESS_STRATEGY["operating_priorities"]:
        key_terms = [t for t in pillar.lower().split() if len(t) > 3][:2]
        if key_terms and any(t in text for t in key_terms):
            return True, f"touches priority: '{pillar[:50]}'"
    # Default: neutral — let it pass on the assumption it's mundane real work
    return True, "no anti-pattern triggered (neutral pass)"


# ─────────────────────────────────────────────────────────────────────
#  Sanity / erroneous-information check
# ─────────────────────────────────────────────────────────────────────
ERRONEOUS_FLAGS = [
    (r"\d{3}-\d{2}-\d{4}", "looks like SSN"),
    (r"4\d{15}", "looks like credit card"),
    (r"\bAustin,?\s+TX\b", "fabricated address (use Portland, OR)"),
    (r"\b5900 Balcones\b", "fabricated street (use 7805 SE 70th Ave)"),
    (r"\bDELETE\s+FROM\s+\w+\s*;?\s*$", "destructive SQL with no WHERE"),
    (r"\brm\s+-rf\s+/\b", "destructive shell command"),
]


def is_erroneous(description: str, payload: Optional[dict] = None) -> Tuple[bool, str]:
    """True if the action carries known-bad content."""
    text = description or ""
    if payload:
        text += " " + json.dumps(payload, default=str)
    for pattern, reason in ERRONEOUS_FLAGS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, reason
    return False, ""


def is_real_work(action_type: str, description: str) -> Tuple[bool, str]:
    """True if this looks like concrete platform work (not theater)."""
    if not action_type and not description:
        return False, "no action_type or description"
    # Block ping-pong-style action types
    theater = ["acknowledge", "heartbeat", "ping", "received_and_logged",
               "alignment_check", "soul_integrity", "covenant_record"]
    text = (action_type or "").lower() + " " + (description or "").lower()
    for t in theater:
        if t in text:
            return False, f"theater action: '{t}'"
    return True, "concrete work"


# ─────────────────────────────────────────────────────────────────────
#  The decision engine
# ─────────────────────────────────────────────────────────────────────
def _init_db():
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decided_at TEXT NOT NULL,
            requesting_agent TEXT,
            action_type TEXT,
            description TEXT,
            stake TEXT,
            cost_usd REAL DEFAULT 0,
            decision TEXT,                  -- auto_approve | escalate | founder_required | reject
            approving_role TEXT,             -- which role in the chain approved
            reasoning TEXT,
            payload TEXT
        )
    """)
    conn.commit()
    conn.close()


def request_approval(
    requesting_agent: str,
    action_type: str,
    description: str,
    stake: str = "low",
    cost_usd: float = 0.0,
    payload: Optional[dict] = None,
) -> Dict:
    """
    Walk up the hierarchy. Returns:
      {
        decision: "auto_approve" | "escalate" | "founder_required" | "reject",
        approving_role: str | None,
        chain_walked: [list of roles],
        reasoning: str,
        money: bool,
        ...
      }
    """
    _init_db()

    # ── Step 1: money check (ABSOLUTE — always founder) ──
    money_flag, money_reason = involves_money(action_type, description, cost_usd)
    if money_flag:
        result = {
            "decision":        "founder_required",
            "approving_role":  None,
            "chain_walked":    [],
            "reasoning":       f"Money detected: {money_reason}. Founder HITL required.",
            "money":           True,
            "stake":           stake,
            "cost_usd":        cost_usd,
        }
        _log_decision(requesting_agent, action_type, description, stake,
                      cost_usd, "founder_required", None, result["reasoning"], payload)
        return result

    # ── Step 2: erroneous content check ──
    err_flag, err_reason = is_erroneous(description, payload)
    if err_flag:
        result = {
            "decision":        "reject",
            "approving_role":  requesting_agent,
            "chain_walked":    [requesting_agent],
            "reasoning":       f"Rejected as erroneous: {err_reason}",
            "money":           False,
            "stake":           stake,
        }
        _log_decision(requesting_agent, action_type, description, stake,
                      cost_usd, "reject", requesting_agent, result["reasoning"], payload)
        return result

    # ── Step 3: real-work check ──
    real_flag, real_reason = is_real_work(action_type, description)
    if not real_flag:
        result = {
            "decision":        "reject",
            "approving_role":  requesting_agent,
            "chain_walked":    [requesting_agent],
            "reasoning":       f"Rejected as non-work: {real_reason}",
            "money":           False,
            "stake":           stake,
        }
        _log_decision(requesting_agent, action_type, description, stake,
                      cost_usd, "reject", requesting_agent, result["reasoning"], payload)
        return result

    # ── Step 4: strategy alignment ──
    aligned, align_reason = aligns_with_strategy(description, action_type)
    if not aligned:
        result = {
            "decision":        "founder_required",
            "approving_role":  None,
            "chain_walked":    [],
            "reasoning":       f"Strategy misalignment: {align_reason}. Founder needed.",
            "money":           False,
            "stake":           stake,
        }
        _log_decision(requesting_agent, action_type, description, stake,
                      cost_usd, "founder_required", None, result["reasoning"], payload)
        return result

    # ── Step 5: walk up the chain until authority is sufficient ──
    required_rank = STAKE_RANK.get(stake.lower(), 1)
    chain = [requesting_agent]
    current = requesting_agent
    while True:
        authority = APPROVAL_AUTHORITY.get(current, "low")
        current_rank = STAKE_RANK.get(authority, 1)
        if current_rank >= required_rank:
            # current role has authority
            result = {
                "decision":        "auto_approve",
                "approving_role":  current,
                "chain_walked":    chain,
                "reasoning":       (
                    f"Auto-approved by '{current}' "
                    f"(authority={authority} ≥ stake={stake}). "
                    f"Strategy: {align_reason}. "
                    f"Money: no. Real work: {real_reason}."
                ),
                "money":           False,
                "stake":           stake,
            }
            _log_decision(requesting_agent, action_type, description, stake,
                          cost_usd, "auto_approve", current, result["reasoning"], payload)
            return result
        # not enough authority — escalate
        nxt = REPORT_TO_CHAIN.get(current)
        if not nxt or nxt == "founder":
            # ran out of chain or hit founder
            result = {
                "decision":        "founder_required",
                "approving_role":  None,
                "chain_walked":    chain + ["founder"],
                "reasoning":       (
                    f"Chain exhausted at '{current}' "
                    f"(authority={authority} < stake={stake}). Founder required."
                ),
                "money":           False,
                "stake":           stake,
            }
            _log_decision(requesting_agent, action_type, description, stake,
                          cost_usd, "founder_required", None,
                          result["reasoning"], payload)
            return result
        current = nxt
        chain.append(current)


def _log_decision(agent, action_type, description, stake, cost,
                  decision, approver, reasoning, payload):
    try:
        conn = sqlite3.connect(_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO approval_log "
            "(decided_at, requesting_agent, action_type, description, "
            " stake, cost_usd, decision, approving_role, reasoning, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), agent or "",
             action_type or "", (description or "")[:400], stake or "low",
             float(cost or 0), decision, approver,
             (reasoning or "")[:500], json.dumps(payload or {}, default=str)[:1000])
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def stats() -> Dict:
    _init_db()
    conn = sqlite3.connect(_DB, timeout=10.0)
    by_decision = dict(conn.execute(
        "SELECT decision, COUNT(*) FROM approval_log "
        "WHERE decided_at > datetime('now','-24 hours') GROUP BY decision"
    ).fetchall())
    by_agent = dict(conn.execute(
        "SELECT requesting_agent, COUNT(*) FROM approval_log "
        "WHERE decided_at > datetime('now','-24 hours') GROUP BY requesting_agent"
    ).fetchall())
    recent_founder = conn.execute(
        "SELECT decided_at, requesting_agent, action_type, description, reasoning "
        "FROM approval_log WHERE decision='founder_required' "
        "AND decided_at > datetime('now','-24 hours') ORDER BY id DESC LIMIT 10"
    ).fetchall()
    money_total = conn.execute(
        "SELECT COALESCE(SUM(cost_usd),0) FROM approval_log "
        "WHERE decision='founder_required' AND cost_usd > 0 "
        "AND decided_at > datetime('now','-24 hours')"
    ).fetchone()[0]
    conn.close()
    return {
        "by_decision_24h":         by_decision,
        "by_agent_24h":            by_agent,
        "money_pending_usd_24h":   money_total,
        "recent_founder_required": [
            {"at": r[0], "agent": r[1], "action": r[2],
             "desc": (r[3] or "")[:80], "reason": (r[4] or "")[:120]}
            for r in recent_founder
        ],
    }


if __name__ == "__main__":
    # Self-test
    print("APPROVAL LADDER SELF-TEST")
    cases = [
        # (agent, action, desc, stake, cost, expected_decision)
        ("collector", "data_collect", "Collect inbound email metadata", "low", 0.0, "auto_approve"),
        ("executor",  "send_email",   "Send reply to prospect Tom Briggs", "medium", 0.0, "auto_approve"),
        ("executor",  "vendor_payment", "Pay supplier $250 for chillers", "medium", 250.0, "founder_required"),
        ("scheduler", "purchase_api", "Buy OpenAI credits", "low", 0.0, "founder_required"),  # money kw
        ("auditor",   "ping",        "Heartbeat", "low", 0.0, "reject"),  # theater
        ("collector", "data_collect", "DELETE FROM accounts;", "low", 0.0, "reject"),  # erroneous
        ("executor",  "send_invoice", "Invoice customer Apex GC $66,000", "medium", 66000.0, "founder_required"),
        ("exec_admin","strategic_init","Launch new vertical for HVAC market", "high", 0.0, "auto_approve"),
        ("collector", "data_collect", "Send email Austin, TX office update", "low", 0.0, "reject"),  # erroneous
    ]
    passed = 0
    for agent, action, desc, stake, cost, expected in cases:
        r = request_approval(agent, action, desc, stake, cost)
        ok = r["decision"] == expected
        mark = "✅" if ok else "❌"
        if ok: passed += 1
        print(f"  {mark} {agent:11} '{action:18}' → {r['decision']:18} (expected {expected})")
        print(f"      chain={r.get('chain_walked', [])} reason={r['reasoning'][:80]}")
    print(f"\n  {passed}/{len(cases)} pass")
    print()
    print("STATS")
    print(json.dumps(stats(), indent=2)[:600])

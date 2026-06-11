"""
Ship 31aa — Thread Situation Model

Per-thread substrate that tracks:
  KNOWN       facts established (linked to claim_ledger)
  NEEDED      facts missing, each tied to gating decision
  DELIVERED   artifacts already shipped to correspondent
  DERIVABLE   facts that become available once NEEDED is filled
  CHARACTER   model of the correspondent (uses character_network
              engine's 8-pillar schema, inverted to observe THEM
              rather than express Murphy)
  PHYSICS     rules / corpus references applied to derivations

The solution space evolves as facts fill. Each fact unlocks
new derivable facts. The character model improves Murphy's
prediction of how the correspondent will respond.

This is the substrate for causality predictions in Forks B/C.
Fork A just wires this into stranger_responder so every reply
carries the situation as LLM context.

Storage: /var/lib/murphy-production/thread_situation.db
"""
from __future__ import annotations
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DB = "/var/lib/murphy-production/thread_situation.db"


# ── Character pillars (inverted from character_network_engine) ──
# We observe these in the correspondent, not assert them about Murphy.
CHARACTER_PILLARS = [
    "integrity",       # do they keep their word; consistency
    "discernment",     # judgement under uncertainty
    "courage",         # willing to make hard calls
    "stewardship",     # care for resources / others
    "competence",      # depth in their field
    "humility",        # acknowledges limits
    "decisiveness",    # speed of resolution
    "moral_clarity",   # honest framing
]


def _conn():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=2.0)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _ensure_schema():
    c = _conn()
    try:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS thread_situation (
            thread_key      TEXT PRIMARY KEY,
            from_addr       TEXT NOT NULL,
            from_domain     TEXT,
            first_seen_ts   REAL NOT NULL,
            last_updated_ts REAL NOT NULL,
            subject_root    TEXT,
            role            TEXT,
            vertical        TEXT,
            corpus_hint     TEXT,
            -- JSON blobs (small, readable, easy to evolve)
            known_facts     TEXT DEFAULT '[]',
            needed_facts    TEXT DEFAULT '[]',
            delivered       TEXT DEFAULT '[]',
            derivable       TEXT DEFAULT '[]',
            character_model TEXT DEFAULT '{}',
            physics_refs    TEXT DEFAULT '[]'
        );
        CREATE INDEX IF NOT EXISTS idx_thread_addr ON thread_situation(from_addr);
        CREATE INDEX IF NOT EXISTS idx_thread_domain ON thread_situation(from_domain);
        CREATE INDEX IF NOT EXISTS idx_thread_updated ON thread_situation(last_updated_ts DESC);

        CREATE TABLE IF NOT EXISTS situation_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_key      TEXT NOT NULL,
            ts              REAL NOT NULL,
            event           TEXT NOT NULL,
            payload         TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hist_thread ON situation_history(thread_key, ts DESC);
        """)
        c.commit()
    finally:
        c.close()


def _thread_key(from_addr: str, subject: str) -> str:
    """Derive a stable thread key from from_addr + normalized subject root."""
    addr = (from_addr or "").lower().strip()
    subj = (subject or "").strip()
    # Strip RE:/FWD: prefixes
    while True:
        low = subj.lower()
        if low.startswith(("re:", "fw:", "fwd:")):
            subj = subj.split(":", 1)[1].strip()
        else:
            break
    return f"{addr}::{subj[:80].lower()}"


def load_or_create(from_addr: str, subject: str,
                   from_domain: str = "",
                   role: str = "",
                   vertical: str = "") -> Dict[str, Any]:
    """Get the situation for this thread, creating an empty one if new."""
    _ensure_schema()
    tk = _thread_key(from_addr, subject)
    now = time.time()
    c = _conn()
    try:
        row = c.execute(
            "SELECT * FROM thread_situation WHERE thread_key=?", (tk,)
        ).fetchone()
        if row:
            cols = [d[0] for d in c.execute(
                "SELECT * FROM thread_situation WHERE thread_key=?", (tk,)
            ).description]
            sit = dict(zip(cols, row))
        else:
            sit = {
                "thread_key": tk, "from_addr": from_addr,
                "from_domain": from_domain or addr_domain(from_addr),
                "first_seen_ts": now, "last_updated_ts": now,
                "subject_root": subject[:80], "role": role, "vertical": vertical,
                "corpus_hint": _corpus_for_role(role),
                "known_facts": "[]", "needed_facts": "[]",
                "delivered": "[]", "derivable": "[]",
                "character_model": json.dumps(
                    {p: {"score": 0.5, "evidence_count": 0} for p in CHARACTER_PILLARS}
                ),
                "physics_refs": "[]",
            }
            c.execute(
                """INSERT INTO thread_situation
                   (thread_key, from_addr, from_domain, first_seen_ts,
                    last_updated_ts, subject_root, role, vertical, corpus_hint,
                    known_facts, needed_facts, delivered, derivable,
                    character_model, physics_refs)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sit["thread_key"], sit["from_addr"], sit["from_domain"],
                 sit["first_seen_ts"], sit["last_updated_ts"],
                 sit["subject_root"], sit["role"], sit["vertical"],
                 sit["corpus_hint"], sit["known_facts"], sit["needed_facts"],
                 sit["delivered"], sit["derivable"],
                 sit["character_model"], sit["physics_refs"]),
            )
            c.commit()
            _log_event(c, tk, "created", {"role": role, "vertical": vertical})
        # Decode JSON blobs for caller convenience
        for k in ("known_facts", "needed_facts", "delivered",
                  "derivable", "physics_refs"):
            sit[k] = json.loads(sit[k] or "[]")
        sit["character_model"] = json.loads(sit["character_model"] or "{}")
        return sit
    finally:
        c.close()


def addr_domain(addr: str) -> str:
    if not addr or "@" not in addr:
        return ""
    return addr.split("@")[-1].lower().strip()


def _corpus_for_role(role: str) -> str:
    """Which reference corpus matches this role?"""
    mapping = {
        "mep_engineer": "engineering_toolbox",
        "fde": "engineering_toolbox",
        "engineer": "engineering_toolbox",
        "cfo": "finance_fasb",
        "cto": "engineering_toolbox",
        "lawyer": "legal_lii",
        "risk_lawyer": "legal_lii",
    }
    return mapping.get(role, "")


def _log_event(c, thread_key: str, event: str, payload: Dict):
    c.execute(
        "INSERT INTO situation_history (thread_key, ts, event, payload) VALUES (?,?,?,?)",
        (thread_key, time.time(), event, json.dumps(payload)),
    )


def _save(sit: Dict[str, Any]):
    """Persist the updated situation."""
    c = _conn()
    try:
        c.execute(
            """UPDATE thread_situation SET
                 last_updated_ts=?, role=?, vertical=?, corpus_hint=?,
                 known_facts=?, needed_facts=?, delivered=?, derivable=?,
                 character_model=?, physics_refs=?
               WHERE thread_key=?""",
            (time.time(), sit.get("role", ""), sit.get("vertical", ""),
             sit.get("corpus_hint", ""),
             json.dumps(sit.get("known_facts", [])),
             json.dumps(sit.get("needed_facts", [])),
             json.dumps(sit.get("delivered", [])),
             json.dumps(sit.get("derivable", [])),
             json.dumps(sit.get("character_model", {})),
             json.dumps(sit.get("physics_refs", [])),
             sit["thread_key"]),
        )
        c.commit()
    finally:
        c.close()


def absorb_inbound(sit: Dict[str, Any], subject: str, body: str) -> Dict:
    """Extract KNOWN facts from new inbound. Recompute DERIVABLE."""
    new_facts = _extract_facts(subject, body)
    for f in new_facts:
        # Avoid dups by text-signature
        if not any(k.get("text") == f["text"] for k in sit["known_facts"]):
            sit["known_facts"].append(f)
    sit["needed_facts"] = _infer_needed(sit)
    sit["derivable"] = _infer_derivable(sit)
    _save(sit)
    c = _conn()
    try:
        _log_event(c, sit["thread_key"], "inbound_absorbed",
                   {"new_facts": len(new_facts)})
        c.commit()
    finally:
        c.close()
    return sit


def log_delivery(sit: Dict[str, Any], artifact: str, queue_id: str = ""):
    """Record that Murphy delivered something. Recompute DERIVABLE."""
    sit["delivered"].append({
        "artifact": artifact[:200], "queue_id": queue_id, "ts": time.time()
    })
    sit["derivable"] = _infer_derivable(sit)
    _save(sit)


def update_character(sit: Dict[str, Any], signals: Dict[str, float]):
    """Update the correspondent's character model from new observations.

    signals: {pillar_name: delta_score}  e.g. {"decisiveness": +0.1}
    Each pillar is a running average weighted by evidence count.
    """
    cm = sit["character_model"]
    for pillar, delta in signals.items():
        if pillar not in cm:
            cm[pillar] = {"score": 0.5, "evidence_count": 0}
        ec = cm[pillar]["evidence_count"]
        old = cm[pillar]["score"]
        # Weighted update — caps the impact of each observation
        cm[pillar]["score"] = max(0.0, min(1.0, (old * ec + (old + delta)) / (ec + 1)))
        cm[pillar]["evidence_count"] = ec + 1
    sit["character_model"] = cm
    _save(sit)


# ── Fact extraction (Fork A: regex + keyword heuristics) ──
# Fork B will replace this with LLM-extracted structured claims.
def _extract_facts(subject: str, body: str) -> List[Dict]:
    """Pull obvious facts from email text. Conservative — only high-signal."""
    import re
    text = f"{subject}\n{body}"
    facts: List[Dict] = []

    # Dates / deadlines
    for m in re.finditer(
        r"\b(?:by\s+)?(monday|tuesday|wednesday|thursday|friday|"
        r"saturday|sunday|tomorrow|today|next week|this week|"
        r"end of (?:day|week|month|quarter)|eod|eow)\b",
        text, re.IGNORECASE):
        facts.append({"text": f"deadline: {m.group(1).lower()}",
                      "kind": "deadline", "confidence": 0.7,
                      "extracted_at": time.time()})
    # Quantities + units
    for m in re.finditer(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(percent|%|kw|hp|cfm|psi|gpm|mw|kva|amp|amps|volt|volts|"
        r"square feet|sf|sq ft|ft|inches|inch|story|stories|floor|floors)\b",
        text, re.IGNORECASE):
        facts.append({"text": f"{m.group(1)} {m.group(2).lower()}",
                      "kind": "measurement", "confidence": 0.85,
                      "extracted_at": time.time()})
    # Roles / positions claimed
    for kw in ["CFO", "CTO", "CEO", "COO", "Professional Engineer",
               "P.E.", "Architect", "Owner", "GC", "Subcontractor",
               "Counsel", "Partner", "Series A", "Series B", "Series C"]:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            facts.append({"text": f"self-identifies as {kw}",
                          "kind": "identity", "confidence": 0.9,
                          "extracted_at": time.time()})
    return facts


def _infer_needed(sit: Dict) -> List[Dict]:
    """Given KNOWN facts, what's the next gating question?

    Fork A: small rule table. Fork B will use LLM to propose questions
    that, if answered, would most reduce uncertainty.
    """
    needed: List[Dict] = []
    role = sit.get("role", "")
    known_kinds = {f.get("kind") for f in sit.get("known_facts", [])}
    if role == "mep_engineer":
        if "measurement" not in known_kinds:
            needed.append({"question": "what is the current Rev level "
                                       "and which trades are affected?",
                           "gates": "stamp recommendation"})
        if "deadline" not in known_kinds:
            needed.append({"question": "what is the binding submittal date?",
                           "gates": "sequencing"})
    elif role == "cfo":
        if not any("close" in (f.get("text") or "").lower()
                   for f in sit.get("known_facts", [])):
            needed.append({"question": "what fiscal close cadence are you on?",
                           "gates": "scope of help"})
    else:
        if not sit.get("known_facts"):
            needed.append({"question": "what outcome would make this useful?",
                           "gates": "any concrete action"})
    return needed


def _infer_derivable(sit: Dict) -> List[Dict]:
    """What facts become available given the current KNOWN+DELIVERED?

    Fork A: simple causal templates. Fork B plugs this into
    causality_sandbox for real prediction.
    """
    derivable: List[Dict] = []
    known_text = " ".join(f.get("text", "") for f in sit.get("known_facts", []))
    if "cfm" in known_text.lower() and "psi" not in known_text.lower():
        derivable.append({
            "candidate": "pressure_drop computable via Darcy-Weisbach "
                         "once pipe diameter is known",
            "prereqs": ["pipe diameter"],
            "rule": "darcy_weisbach",
            "corpus": "engineering_toolbox",
        })
    if any(f.get("kind") == "deadline" for f in sit.get("known_facts", [])) and \
       any(f.get("kind") == "measurement" for f in sit.get("known_facts", [])):
        derivable.append({
            "candidate": "schedule feasibility computable once "
                         "crew size and shift count are known",
            "prereqs": ["crew size", "shift count"],
            "rule": "throughput_per_shift",
            "corpus": "engineering_toolbox",
        })
    return derivable


def render_for_prompt(sit: Dict, max_chars: int = 1200) -> str:
    """Produce the LLM-prompt block describing the current situation.

    Goes into the system prompt so the LLM knows the conversation state.
    """
    known = sit.get("known_facts", [])[-8:]
    needed = sit.get("needed_facts", [])[:4]
    delivered = sit.get("delivered", [])[-4:]
    derivable = sit.get("derivable", [])[:3]

    lines = ["SITUATION MODEL (use this; do not invent facts beyond it):"]
    if known:
        lines.append(f"  KNOWN ({len(known)}):")
        for f in known:
            lines.append(f"    - {f.get('text','')} ({f.get('kind','?')})")
    else:
        lines.append("  KNOWN: nothing established yet")
    if needed:
        lines.append("  NEEDED:")
        for n in needed:
            lines.append(f"    - {n.get('question','')} "
                         f"[gates: {n.get('gates','')}]")
    if delivered:
        lines.append("  ALREADY DELIVERED:")
        for d in delivered:
            lines.append(f"    - {d.get('artifact','')[:80]}")
    if derivable:
        lines.append("  DERIVABLE ONCE NEEDED ANSWERED:")
        for d in derivable:
            lines.append(f"    - {d.get('candidate','')}")
            lines.append(f"      (rule: {d.get('rule','?')}, "
                         f"corpus: {d.get('corpus','?')})")
    cm = sit.get("character_model", {})
    if cm:
        strong = sorted(
            ((p, v) for p, v in cm.items() if v.get("evidence_count", 0) > 0),
            key=lambda x: -x[1].get("score", 0)
        )[:3]
        if strong:
            lines.append("  CHARACTER OBSERVED (top 3):")
            for p, v in strong:
                lines.append(f"    - {p}: {v.get('score',0):.2f} "
                             f"(n={v.get('evidence_count',0)})")
    out = "\n".join(lines)
    return out[:max_chars]


def get_stats() -> Dict[str, Any]:
    _ensure_schema()
    c = _conn()
    try:
        total = c.execute("SELECT COUNT(*) FROM thread_situation").fetchone()[0]
        by_role = c.execute(
            "SELECT role, COUNT(*) FROM thread_situation GROUP BY role"
        ).fetchall()
        recent = c.execute(
            "SELECT thread_key, from_addr, role, last_updated_ts "
            "FROM thread_situation ORDER BY last_updated_ts DESC LIMIT 10"
        ).fetchall()
        return {
            "total_threads": total,
            "by_role": dict(by_role),
            "recent": [{"thread_key": r[0], "from_addr": r[1],
                        "role": r[2], "last_updated_ts": r[3]}
                       for r in recent],
        }
    finally:
        c.close()

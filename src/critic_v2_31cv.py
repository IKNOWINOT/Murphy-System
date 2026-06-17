"""
Ship 31cv — Critic v2 with writer-notes / addendum mechanism.

Wraps the existing critique_loop_31bh.critique() (Ship 31bq path) with three
parallel checks that produce STRUCTURED writer-notes the LLM can act on:

  1. Shape-Critic   — does draft fit pre-drill recommended_reply_chars envelope?
                      Cheap, deterministic, no LLM call.
  2. Riff-Critic    — for "Re:" replies, does draft restate the quoted history?
                      Semantic dedup against prior chain.
  3. Pattern-Critic — does draft follow patterns of past PASS replies?
                      Matches against tiny corpus of approved outputs.

Orchestrator pattern:
  - All three run in parallel (asyncio.gather).
  - Each returns: {verdict, issues: [...], suggested_edits: {add,delete,revise}}.
  - Orchestrator collects all into a single writer-notes packet.
  - If any critic emits BLOCK -> verdict = "hold".
  - If any critic emits REVISE and we have suggested_edits -> verdict = "revise"
    and we emit the addendum payload for re-prompt.
  - If all PASS -> verdict = "pass".

The existing 31bh critique still runs FIRST (as it does today). Critic v2 runs
AFTER 31bh and only fires if 31bh said pass. This is purely additive —
removing this module restores prior behavior.

The "addendum" payload is structured so the caller can feed it back to the
LLM as a re-prompt:
    ORIGINAL DRAFT: <body>
    WRITER NOTES:
      ADD:    <thing to add>
      DELETE: <thing to remove>
      REVISE: <thing to rephrase>
    NOW PRODUCE REVISED DRAFT.
"""
from __future__ import annotations

import re
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

_DB = "/var/lib/murphy-production/critic_v2_log.db"


def _init_db():
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS critic_v2_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ran_at TEXT NOT NULL,
            correlation_id TEXT,
            to_addr TEXT,
            subject TEXT,
            shape_verdict TEXT,
            shape_issues TEXT,
            riff_verdict TEXT,
            riff_issues TEXT,
            pattern_verdict TEXT,
            pattern_issues TEXT,
            final_verdict TEXT,
            writer_notes_json TEXT,
            iteration INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approved_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            added_at TEXT NOT NULL,
            sender_tier TEXT,
            intent_hint TEXT,
            body_sample TEXT,
            length_chars INTEGER,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────
# Critic 1: Shape-Critic
# ──────────────────────────────────────────────────────────────────────
def shape_critic(
    *,
    body: str,
    shape: Optional[Dict] = None,
) -> Dict:
    """Does the draft respect the recommended_reply_chars envelope?

    `shape` is the dict returned by predrill_dlfr_31cu.shape_predrill_context.
    If shape is None (no pre-drill data), this critic abstains (PASS).
    """
    if not shape:
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    n = len(body or "")
    lo = int(shape.get("recommended_reply_chars_min", 0) or 0)
    hi = int(shape.get("recommended_reply_chars_max", 99999) or 99999)
    tone = shape.get("recommended_tone", "balanced")

    issues = []
    edits = {}

    if n > hi * 1.5:
        # Way over — block, not just revise
        issues.append(
            f"draft is {n} chars but envelope is {lo}-{hi} for {shape.get('size_tier')} "
            f"{shape.get('intent_hint')} — {n - hi} chars over (1.5x)"
        )
        edits["delete"] = (
            f"Trim draft to {lo}-{hi} chars. Remove repetition, generic preamble, "
            f"and any sentence that doesn't advance the answer."
        )
        return {"verdict": "BLOCK", "issues": issues, "suggested_edits": edits}

    if n > hi:
        issues.append(
            f"draft is {n} chars but envelope is {lo}-{hi} — {n - hi} chars over"
        )
        edits["delete"] = f"Trim to fit {lo}-{hi} char envelope ({tone} tone)."
        return {"verdict": "REVISE", "issues": issues, "suggested_edits": edits}

    if n < lo:
        issues.append(
            f"draft is {n} chars but envelope expects at least {lo} for {shape.get('intent_hint')}"
        )
        edits["add"] = (
            f"Expand to at least {lo} chars. Add a concrete next step or example "
            f"appropriate for {tone} tone."
        )
        return {"verdict": "REVISE", "issues": issues, "suggested_edits": edits}

    return {"verdict": "PASS", "issues": [], "suggested_edits": {}}


# ──────────────────────────────────────────────────────────────────────
# Critic 2: Riff-Critic
# ──────────────────────────────────────────────────────────────────────
_QUOTE_PREFIXES = (">", "On ", "From:", "Sent:", "wrote:")


def _extract_quoted_history(inbound_body: str) -> str:
    """Pull the quoted text from a Re: reply (lines starting with > or after
    'On <date> <name> wrote:' markers).
    """
    lines = (inbound_body or "").splitlines()
    quoted = []
    in_quoted = False
    for ln in lines:
        s = ln.strip()
        if s.startswith(">"):
            quoted.append(s.lstrip("> "))
            in_quoted = True
            continue
        if "wrote:" in s.lower() and ("on " in s.lower() or "from:" in s.lower()):
            in_quoted = True
            continue
        if in_quoted and s:
            quoted.append(s)
    return " ".join(quoted)[:5000]


def _sentence_overlap_ratio(draft: str, quoted: str) -> float:
    """Cheap n-gram overlap: what fraction of draft sentences appear nearly
    verbatim in the quoted history?
    """
    if not draft or not quoted:
        return 0.0
    draft_sents = re.split(r"(?<=[.!?])\s+", draft)
    quoted_norm = re.sub(r"\s+", " ", quoted.lower())
    hits = 0
    counted = 0
    for s in draft_sents:
        s = s.strip().lower()
        if len(s) < 30:
            continue
        counted += 1
        # Check if the first 40 chars of this sentence appear in quoted history
        if s[:40] in quoted_norm:
            hits += 1
    if counted == 0:
        return 0.0
    return hits / counted


def riff_critic(
    *,
    body: str,
    subject: str,
    inbound_body: str = "",
) -> Dict:
    """For Re: replies, does the draft restate the quoted history instead of
    riffing forward?
    """
    if not (subject or "").lower().startswith("re:"):
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    quoted = _extract_quoted_history(inbound_body)
    if not quoted:
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    overlap = _sentence_overlap_ratio(body, quoted)
    if overlap > 0.50:
        return {
            "verdict": "REVISE",
            "issues": [f"{overlap:.0%} of draft sentences restate the quoted history"],
            "suggested_edits": {
                "revise": (
                    "This is a Re: chain — DO NOT restate what's been said. "
                    "Riff forward: advance the conversation using NUANCE of prior "
                    "turns. Give a direct example of what they're asking for, "
                    "include implied task-list items in optimal order."
                )
            },
        }
    if overlap > 0.30:
        return {
            "verdict": "REVISE",
            "issues": [f"{overlap:.0%} sentence overlap with quoted history (warning)"],
            "suggested_edits": {
                "delete": "Remove sentences that paraphrase the quoted history."
            },
        }
    return {"verdict": "PASS", "issues": [], "suggested_edits": {}}


# ──────────────────────────────────────────────────────────────────────
# Critic 3: Pattern-Critic
# ──────────────────────────────────────────────────────────────────────
def pattern_critic(
    *,
    body: str,
    shape: Optional[Dict] = None,
) -> Dict:
    """Does the draft follow the patterns of past PASS replies for this
    (sender_tier, intent_hint) combination?

    If the approved_patterns corpus is empty for this combo, abstain.
    """
    if not shape:
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    try:
        _init_db()
        conn = sqlite3.connect(_DB, timeout=10.0)
        rows = conn.execute(
            "SELECT length_chars FROM approved_patterns "
            "WHERE sender_tier=? AND intent_hint=? "
            "ORDER BY added_at DESC LIMIT 20",
            (shape.get("sender_tier"), shape.get("intent_hint")),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.debug("Pattern-critic db read failed: %s", exc)
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    if len(rows) < 3:
        # Not enough history to enforce a pattern — abstain
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    lengths = sorted([r[0] for r in rows if r[0]])
    if not lengths:
        return {"verdict": "PASS", "issues": [], "suggested_edits": {}}

    median = lengths[len(lengths) // 2]
    n = len(body or "")
    # If draft is more than 2x the median historical length, flag
    if n > median * 2:
        return {
            "verdict": "REVISE",
            "issues": [
                f"draft is {n} chars; median for "
                f"{shape.get('sender_tier')}/{shape.get('intent_hint')} is "
                f"{median} (over 2x)"
            ],
            "suggested_edits": {
                "delete": f"Trim toward the historical median of {median} chars."
            },
        }
    return {"verdict": "PASS", "issues": [], "suggested_edits": {}}


# ──────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────
def run_critic_v2(
    *,
    body: str,
    subject: str,
    inbound_body: str = "",
    shape: Optional[Dict] = None,
    correlation_id: str = "",
    to_addr: str = "",
    iteration: int = 0,
) -> Dict:
    """Run all three critics. Return a single packet:

    {
      "verdict": "pass" | "revise" | "hold",
      "writer_notes": {
         "add":    [...],
         "delete": [...],
         "revise": [...],
      },
      "details": {
         "shape":   {...},
         "riff":    {...},
         "pattern": {...},
      },
      "addendum_prompt": "<the re-prompt text to feed to the LLM>",
    }
    """
    _init_db()

    shape_r   = shape_critic(body=body, shape=shape)
    riff_r    = riff_critic(body=body, subject=subject, inbound_body=inbound_body)
    pattern_r = pattern_critic(body=body, shape=shape)

    # Aggregate verdicts
    verdicts = [shape_r["verdict"], riff_r["verdict"], pattern_r["verdict"]]
    if "BLOCK" in verdicts:
        final = "hold"
    elif "REVISE" in verdicts:
        final = "revise"
    else:
        final = "pass"

    # Aggregate writer-notes
    writer_notes = {"add": [], "delete": [], "revise": []}
    for r in (shape_r, riff_r, pattern_r):
        edits = r.get("suggested_edits", {}) or {}
        for k in ("add", "delete", "revise"):
            v = edits.get(k)
            if v:
                writer_notes[k].append(v)

    # Build addendum prompt for re-prompt path
    addendum_lines = []
    if writer_notes["add"]:
        addendum_lines.append("ADD:")
        for x in writer_notes["add"]:
            addendum_lines.append(f"  - {x}")
    if writer_notes["delete"]:
        addendum_lines.append("DELETE:")
        for x in writer_notes["delete"]:
            addendum_lines.append(f"  - {x}")
    if writer_notes["revise"]:
        addendum_lines.append("REVISE:")
        for x in writer_notes["revise"]:
            addendum_lines.append(f"  - {x}")
    addendum_prompt = (
        "ORIGINAL DRAFT:\n"
        f"{body}\n\n"
        "WRITER NOTES:\n"
        + "\n".join(addendum_lines)
        + "\n\nNOW PRODUCE A REVISED DRAFT that addresses the writer notes. "
          "Keep what was working; change only what the notes ask you to change."
    ) if addendum_lines else ""

    # Log
    try:
        conn = sqlite3.connect(_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO critic_v2_log (ran_at, correlation_id, to_addr, subject, "
            "shape_verdict, shape_issues, riff_verdict, riff_issues, "
            "pattern_verdict, pattern_issues, final_verdict, writer_notes_json, iteration) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                correlation_id, to_addr, subject[:200],
                shape_r["verdict"],   json.dumps(shape_r["issues"]),
                riff_r["verdict"],    json.dumps(riff_r["issues"]),
                pattern_r["verdict"], json.dumps(pattern_r["issues"]),
                final, json.dumps(writer_notes), iteration,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug("Critic v2 log write failed: %s", exc)

    return {
        "verdict": final,
        "writer_notes": writer_notes,
        "details": {"shape": shape_r, "riff": riff_r, "pattern": pattern_r},
        "addendum_prompt": addendum_prompt,
    }


def record_approved_pattern(
    *,
    body: str,
    shape: Optional[Dict] = None,
    notes: str = "",
) -> None:
    """Call this when a draft is approved (by 31bh PASS + critic v2 PASS + sent
    successfully). Builds the corpus that Pattern-Critic uses.
    """
    if not shape:
        return
    try:
        _init_db()
        conn = sqlite3.connect(_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO approved_patterns (added_at, sender_tier, intent_hint, "
            "body_sample, length_chars, notes) VALUES (?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                shape.get("sender_tier"),
                shape.get("intent_hint"),
                (body or "")[:2000],
                len(body or ""),
                notes,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug("Approved pattern write failed: %s", exc)

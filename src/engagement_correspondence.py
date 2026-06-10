"""
PCR-054j — Engagement as correspondence thread

The founder's reframe (2026-06-09):
  "Can engagement be in juxtaposition for any correspondence that may
   be needed?"
  "Their employees train the system. The language and generation follows."

Before this patch the EngagementFolder was a TRANSACTION:
  one outreach -> one attestation reply -> finalize. Anything else
  (clarifying questions, revisions, status pings, scope changes) was
  dropped by process_reply with "folder not in AWAITING".

After this patch the EngagementFolder is a CORRESPONDENCE THREAD:
  every message related to the engagement attaches via
  engagement_correspondence. Only messages classified as `attestation`
  run the 6-point gate. Everything else accumulates context and is
  available as training signal for PCR-054k (PractitionerCorpus) and
  PCR-054l (generation conditioning).

This module is the THREAD SURFACE. It has no opinions about LLM
training yet — that opens in 054k. Here we just guarantee no message
is dropped, every message is classified, and the thread is queryable.

COMPOSITION
-----------
- src.engagement_folder    DB + folder state machine (we add a new table)
- src.engagement_inbound   reshape to call attach_correspondence() always,
                           gate only when classifier returns 'attestation'
- inbound_replies.db       upstream message source (untouched)

INTENT CLASSES
--------------
attestation         - Practitioner is signing off ("personally reviewed",
                      "professional responsibility", license number cited)
clarifying_question - Practitioner needs more info ("can you tell me",
                      "what's the", "?", interrogative shape)
revision_request    - Practitioner wants changes ("please revise",
                      "change the", "should be", "instead of")
status_inquiry      - Status/timing ping ("where are we", "any update",
                      "ETA")
decline             - Refusal ("DECLINE", "cannot accept",
                      "outside my scope")
unclassified        - Doesn't fit any pattern; still attaches to thread
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.engagement_folder import (
    DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH,
    _connect,
)

LOG = logging.getLogger("murphy.engagement_correspondence")


# ─────────────────────────────────────────────────────────────────────
# Schema (idempotent)
# ─────────────────────────────────────────────────────────────────────


SCHEMA = """
CREATE TABLE IF NOT EXISTS engagement_correspondence (
    corr_id               TEXT PRIMARY KEY,
    engagement_id         TEXT NOT NULL,
    received_at           REAL NOT NULL,
    direction             TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    from_email            TEXT NOT NULL,
    to_email              TEXT,
    subject               TEXT,
    body                  TEXT NOT NULL,
    classified_intent     TEXT NOT NULL,
    classifier_confidence TEXT NOT NULL,
    gate_applied          INTEGER NOT NULL DEFAULT 0,
    gate_result_json      TEXT,
    folder_state_at_time  TEXT,
    metadata_json         TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (engagement_id) REFERENCES engagement_folders (engagement_id)
);

CREATE INDEX IF NOT EXISTS idx_corr_engagement
    ON engagement_correspondence (engagement_id, received_at);
CREATE INDEX IF NOT EXISTS idx_corr_intent
    ON engagement_correspondence (classified_intent);
CREATE INDEX IF NOT EXISTS idx_corr_from
    ON engagement_correspondence (from_email);
"""


def init_db(db_path: str = ENGAGEMENT_DB_PATH) -> None:
    """Add the correspondence table. Safe to call repeatedly."""
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Intent classifier (rule-based v1)
# ─────────────────────────────────────────────────────────────────────


# Attestation: must have license phrasing + responsibility language
ATTESTATION_PATTERNS = [
    re.compile(r"\bpersonally\s+reviewed?\b", re.IGNORECASE),
    re.compile(r"\bprofessional\s+responsibility\b", re.IGNORECASE),
    re.compile(r"\bI,?\s+[A-Z][a-zA-Z\.\s]+,?\s+(?:holder|holding|hold)\b", re.IGNORECASE),
    re.compile(r"\blicense\s*#?\s*[:.\-]?\s*[A-Z0-9\-]+\b", re.IGNORECASE),
    re.compile(r"\battest\b", re.IGNORECASE),
    re.compile(r"\bin\s+good\s+standing\b", re.IGNORECASE),
]

# Decline: explicit refusal language
DECLINE_PATTERNS = [
    re.compile(r"^\s*DECLINE\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"\bcannot\s+accept\b", re.IGNORECASE),
    re.compile(r"\boutside\s+(?:my|the)\s+scope\b", re.IGNORECASE),
    re.compile(r"\bunable\s+to\s+(?:sign|attest|complete)\b", re.IGNORECASE),
    re.compile(r"\bwithdraw(?:ing)?\s+from\b", re.IGNORECASE),
]

# Revision: change-request language
REVISION_PATTERNS = [
    re.compile(r"\bplease\s+(?:revise|update|change|correct|fix)\b", re.IGNORECASE),
    re.compile(r"\bshould\s+(?:be|read|say)\b", re.IGNORECASE),
    re.compile(r"\binstead\s+of\b", re.IGNORECASE),
    re.compile(r"\bneeds?\s+(?:to\s+be\s+)?(?:revised|updated|changed|corrected)\b", re.IGNORECASE),
    re.compile(r"\b(?:before|prior\s+to)\s+(?:I|we)\s+(?:sign|attest|approve)\b", re.IGNORECASE),
    re.compile(r"\battached\s+(?:revised|updated)\b", re.IGNORECASE),
]

# Clarifying question: interrogative
QUESTION_PATTERNS = [
    re.compile(r"\?\s*$", re.MULTILINE),
    re.compile(r"\b(?:can|could|would)\s+you\s+(?:tell|explain|clarify|confirm|send|provide)\b", re.IGNORECASE),
    re.compile(r"\bwhat(?:'s|\s+is)\s+the\b", re.IGNORECASE),
    re.compile(r"\bwhy\s+(?:is|did|does|are)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(?:do|did|are|is|was)\b", re.IGNORECASE),
    re.compile(r"\b(?:please\s+)?clarify\b", re.IGNORECASE),
    re.compile(r"\bmore\s+information\b", re.IGNORECASE),
]

# Status: timing inquiries
STATUS_PATTERNS = [
    re.compile(r"\bwhere\s+(?:are|is)\s+(?:we|this|that|things)\b", re.IGNORECASE),
    re.compile(r"\bany\s+update\b", re.IGNORECASE),
    re.compile(r"\b(?:ETA|eta|status|status\s+update)\b"),
    re.compile(r"\bchecking\s+in\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+(?:will|can|do\s+you\s+expect)\b", re.IGNORECASE),
]


@dataclass
class IntentResult:
    intent:     str           # one of the six classes
    confidence: str           # "high" | "medium" | "low"
    signals:    List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "intent":     self.intent,
            "confidence": self.confidence,
            "signals":    list(self.signals),
        }


def classify_intent(body: str, subject: str = "") -> IntentResult:
    """Rule-based intent classifier. Pure function, no I/O.

    Priority order: decline > attestation > revision > question > status > unclassified.
    Decline ranks first because a decline that mentions a license number
    should NOT be classified as attestation.
    """
    text = f"{subject}\n{body}"
    signals: List[str] = []

    # Decline first — explicit refusal wins over everything
    decline_hits = [p.pattern for p in DECLINE_PATTERNS if p.search(text)]
    if decline_hits:
        signals.extend(f"decline:{h[:30]}" for h in decline_hits)
        return IntentResult("decline", "high", signals)

    # Attestation — needs at least 2 signals to be considered high confidence
    att_hits = [p.pattern for p in ATTESTATION_PATTERNS if p.search(text)]
    if len(att_hits) >= 3:
        signals.extend(f"att:{h[:30]}" for h in att_hits)
        return IntentResult("attestation", "high", signals)
    if len(att_hits) == 2:
        signals.extend(f"att:{h[:30]}" for h in att_hits)
        return IntentResult("attestation", "medium", signals)

    # Revision request
    rev_hits = [p.pattern for p in REVISION_PATTERNS if p.search(text)]
    if rev_hits:
        signals.extend(f"rev:{h[:30]}" for h in rev_hits)
        return IntentResult("revision_request", "high" if len(rev_hits) >= 2 else "medium", signals)

    # Status inquiry — checked BEFORE question because status is a
    # specific subset of questions ('any update', 'where are we', 'ETA')
    # and we want the specific class to win.
    status_hits = [p.pattern for p in STATUS_PATTERNS if p.search(text)]
    if status_hits:
        signals.extend(f"status:{h[:30]}" for h in status_hits)
        return IntentResult("status_inquiry", "high" if len(status_hits) >= 2 else "medium", signals)

    # Clarifying question (generic interrogative)
    q_hits = [p.pattern for p in QUESTION_PATTERNS if p.search(text)]
    if q_hits:
        signals.extend(f"q:{h[:30]}" for h in q_hits)
        return IntentResult("clarifying_question", "high" if len(q_hits) >= 2 else "medium", signals)

    # Lone attestation signal isn't enough — falls through to unclassified
    if att_hits:
        signals.extend(f"att-weak:{h[:30]}" for h in att_hits)
        return IntentResult("unclassified", "low", signals)

    return IntentResult("unclassified", "low", signals)


# ─────────────────────────────────────────────────────────────────────
# Attach correspondence to a folder
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Correspondence:
    corr_id:                str
    engagement_id:          str
    received_at:            float
    direction:              str          # "in" | "out"
    from_email:             str
    to_email:               Optional[str]
    subject:                Optional[str]
    body:                   str
    classified_intent:      str
    classifier_confidence:  str
    gate_applied:           bool
    gate_result_json:       Optional[str]
    folder_state_at_time:   Optional[str]
    metadata_json:          str = "{}"

    def to_row(self) -> tuple:
        return (
            self.corr_id, self.engagement_id, self.received_at,
            self.direction, self.from_email, self.to_email,
            self.subject, self.body, self.classified_intent,
            self.classifier_confidence, 1 if self.gate_applied else 0,
            self.gate_result_json, self.folder_state_at_time,
            self.metadata_json,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Correspondence":
        return cls(
            corr_id=row["corr_id"],
            engagement_id=row["engagement_id"],
            received_at=row["received_at"],
            direction=row["direction"],
            from_email=row["from_email"],
            to_email=row["to_email"],
            subject=row["subject"],
            body=row["body"],
            classified_intent=row["classified_intent"],
            classifier_confidence=row["classifier_confidence"],
            gate_applied=bool(row["gate_applied"]),
            gate_result_json=row["gate_result_json"],
            folder_state_at_time=row["folder_state_at_time"],
            metadata_json=row["metadata_json"] or "{}",
        )

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["gate_applied"] = bool(self.gate_applied)
        return d


def attach_correspondence(
    engagement_id: str,
    direction: str,
    from_email: str,
    body: str,
    *,
    subject: Optional[str] = None,
    to_email: Optional[str] = None,
    folder_state_at_time: Optional[str] = None,
    gate_applied: bool = False,
    gate_result: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Correspondence:
    """Attach a message to the engagement thread.

    NEVER drops the message. The classifier always returns *something*
    (worst case 'unclassified' with low confidence). The folder's state
    is recorded so future analysis can see WHEN in the engagement
    lifecycle each message arrived.
    """
    init_db(db_path)
    if direction not in ("in", "out"):
        raise ValueError(f"direction must be 'in' or 'out', got {direction!r}")

    intent = classify_intent(body, subject or "")
    corr = Correspondence(
        corr_id=f"corr_{uuid.uuid4().hex[:14]}",
        engagement_id=engagement_id,
        received_at=time.time(),
        direction=direction,
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        body=body,
        classified_intent=intent.intent,
        classifier_confidence=intent.confidence,
        gate_applied=gate_applied,
        gate_result_json=json.dumps(gate_result) if gate_result else None,
        folder_state_at_time=folder_state_at_time,
        metadata_json=json.dumps({**(metadata or {}), "classifier_signals": intent.signals},
                                 sort_keys=True),
    )

    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO engagement_correspondence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            corr.to_row(),
        )
        con.commit()
    finally:
        con.close()

    LOG.info(
        "PCR-054j attached corr_id=%s eid=%s direction=%s intent=%s confidence=%s",
        corr.corr_id, engagement_id, direction, intent.intent, intent.confidence,
    )
    return corr


# ─────────────────────────────────────────────────────────────────────
# Query: get the thread
# ─────────────────────────────────────────────────────────────────────


def get_thread(
    engagement_id: str,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> List[Correspondence]:
    """Return the full correspondence thread for an engagement, oldest first."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM engagement_correspondence "
            "WHERE engagement_id = ? ORDER BY received_at ASC",
            (engagement_id,),
        ).fetchall()
        return [Correspondence.from_row(r) for r in rows]
    finally:
        con.close()


def get_thread_by_intent(
    engagement_id: str,
    intent: str,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> List[Correspondence]:
    """Return only messages with a specific intent (oldest first)."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM engagement_correspondence "
            "WHERE engagement_id = ? AND classified_intent = ? "
            "ORDER BY received_at ASC",
            (engagement_id, intent),
        ).fetchall()
        return [Correspondence.from_row(r) for r in rows]
    finally:
        con.close()


def get_thread_by_practitioner(
    from_email: str,
    limit: int = 200,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> List[Correspondence]:
    """Return correspondence from a single practitioner across all engagements.

    Foundation for PCR-054k (PractitionerCorpus). When 054k lands,
    aggregation by (from_email, role_id, jurisdiction) builds the
    per-practitioner voice/vocabulary store.
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM engagement_correspondence "
            "WHERE from_email = ? ORDER BY received_at DESC LIMIT ?",
            (from_email, limit),
        ).fetchall()
        return [Correspondence.from_row(r) for r in rows]
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Recovery from DECLINED_OR_EDITS_ASKED
# ─────────────────────────────────────────────────────────────────────


def is_recoverable_followup(corr: Correspondence) -> bool:
    """Heuristic: is this message a real attestation arriving AFTER a decline/edits?

    Used by the reshaped process_reply to detect when a folder previously
    in DECLINED_OR_EDITS_ASKED should be reset to AWAITING_ATTESTATION
    (and then re-run the gate).
    """
    if corr.classified_intent != "attestation":
        return False
    if corr.classifier_confidence not in ("high", "medium"):
        return False
    return True

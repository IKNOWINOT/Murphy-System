"""
PCR-054e — Engagement inbound attestation parser

Reads rows from /var/lib/murphy-production/inbound_replies.db
(populated every 5min by murphy-inbound-poller.timer + inbound_maildir_poller.py),
matches them to AWAITING_ATTESTATION engagement folders by engagement_id
in subject/body, runs the 6-point gate on the parsed payload, and pushes
the folder to either FINALIZED or DECLINED_OR_EDITS_ASKED.

CLOSES the engagement loop end-to-end.

THE 6-POINT GATE
================
A practitioner's reply earns transition to FINALIZED only if ALL six pass:

  1. ENGAGEMENT_ID present  - subject or body cites the engagement_id
  2. LICENSE_TYPE match     - claim names the SAME license the folder requires
                              (case-insensitive, e.g. "CPA" matches "cpa")
  3. LICENSE_NUMBER present - non-empty number after "License #" pattern
  4. JURISDICTION match     - claim names the SAME jurisdiction as the folder
                              (or its US-XX state code)
  5. ATTESTATION_LANGUAGE   - body contains the canonical phrases
                              "personally reviewed", "professional responsibility",
                              "good standing"
  6. NOT_DECLINED           - body does NOT contain a standalone "DECLINE" line

If gate fails, folder goes to DECLINED_OR_EDITS_ASKED with the specific
gate failure reasons recorded in the event payload.

DOES NOT SEND MAIL — purely state-machine push from existing inbound data.

Composes with:
  inbound_maildir_poller.py    populates inbound_replies
  PCR-054c engagement_folder   transition() + record_external_event()
                              + record_attestation_payload()
"""
from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.engagement_correspondence import (
    attach_correspondence,
    classify_intent,
    is_recoverable_followup,
)
from src.engagement_folder import (
    DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH,
    FolderState,
    get_folder,
    list_folders,
    record_attestation_payload,
    record_external_event,
    transition,
)

LOG = logging.getLogger("murphy.engagement_inbound")

INBOUND_DB_PATH = "/var/lib/murphy-production/inbound_replies.db"

# ─────────────────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────────────────

ENGAGEMENT_ID_RE = re.compile(r"\b(eng_[a-f0-9]{8,16})\b", re.IGNORECASE)
LICENSE_NUMBER_RE = re.compile(
    # Require # or : after "License" so we don't match "license number".
    # Captured group must contain at least one digit.
    r"License\s*(?:#|number\s*)\s*:?\s*([A-Z0-9][A-Z0-9\-]{2,20})",
    re.IGNORECASE,
)
DECLINE_RE = re.compile(r"^\s*DECLINE\s*$", re.IGNORECASE | re.MULTILINE)

# Phrases that must all appear (case-insensitive) for the attestation
# language gate to pass.
ATTESTATION_PHRASES = [
    "personally reviewed",
    "professional responsibility",
    "good standing",
]


# ─────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ParsedAttestation:
    """Structured payload extracted from a reply body."""
    engagement_id:         Optional[str] = None
    license_type_claimed:  Optional[str] = None
    license_number:        Optional[str] = None
    jurisdiction_claimed:  Optional[str] = None
    has_attestation_lang:  bool = False
    declined:              bool = False
    raw_body:              str = ""


@dataclass
class GateResult:
    """Outcome of running the 6-point gate on a ParsedAttestation."""
    passed:           bool
    failures:         List[str] = field(default_factory=list)
    details:          Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "passed":   self.passed,
            "failures": list(self.failures),
            "details":  dict(self.details),
        }


# ─────────────────────────────────────────────────────────────────────
# Pure parse
# ─────────────────────────────────────────────────────────────────────


def parse_attestation(
    body: str,
    *,
    folder_license_type: Optional[str] = None,
    folder_jurisdiction: Optional[str] = None,
) -> ParsedAttestation:
    """Extract attestation fields from a reply body. Pure function."""
    body = body or ""
    p = ParsedAttestation(raw_body=body)

    # Engagement ID
    m = ENGAGEMENT_ID_RE.search(body)
    if m:
        p.engagement_id = m.group(1).lower()

    # License number
    m = LICENSE_NUMBER_RE.search(body)
    if m:
        p.license_number = m.group(1).strip()

    # Decline flag (standalone line containing only DECLINE)
    p.declined = bool(DECLINE_RE.search(body))

    # License type claim — look for the folder's required license type
    # appearing in the body (case-insensitive). We don't try to discover
    # an arbitrary license type; we verify the practitioner is claiming
    # the one the folder needs.
    if folder_license_type:
        if re.search(rf"\b{re.escape(folder_license_type)}\b", body, re.IGNORECASE):
            p.license_type_claimed = folder_license_type

    # Jurisdiction claim — same logic
    if folder_jurisdiction:
        # Match "US-CA" or just "CA" if it's the state portion
        full = folder_jurisdiction
        state_only = folder_jurisdiction.split("-")[-1] if "-" in folder_jurisdiction else folder_jurisdiction
        pat = rf"\b({re.escape(full)}|{re.escape(state_only)})\b"
        if re.search(pat, body, re.IGNORECASE):
            p.jurisdiction_claimed = folder_jurisdiction

    # Attestation language - all three phrases must appear.
    # Normalize whitespace (newlines, multiple spaces) so a phrase that
    # wraps across lines still matches.
    body_normalized = " ".join(body.lower().split())
    p.has_attestation_lang = all(phrase in body_normalized for phrase in ATTESTATION_PHRASES)

    return p


# ─────────────────────────────────────────────────────────────────────
# 6-point gate
# ─────────────────────────────────────────────────────────────────────


def run_gate(
    parsed: ParsedAttestation,
    *,
    expected_engagement_id: str,
    folder_license_type: str,
    folder_jurisdiction: str,
) -> GateResult:
    """Apply the 6-point gate. Pure function."""
    failures: List[str] = []
    details: Dict[str, Any] = {}

    # 0. Decline branch first (short-circuit — declined reply isn't a failed
    #    attestation, it's a declined engagement)
    if parsed.declined:
        return GateResult(
            passed=False,
            failures=["explicitly_declined"],
            details={"reason": "body contained standalone DECLINE line"},
        )

    # 1. Engagement ID present + matches
    if parsed.engagement_id is None:
        failures.append("missing_engagement_id")
    elif parsed.engagement_id != expected_engagement_id.lower():
        failures.append("engagement_id_mismatch")
        details["expected_engagement_id"] = expected_engagement_id
        details["found_engagement_id"] = parsed.engagement_id

    # 2. License type claimed matches folder requirement
    if parsed.license_type_claimed is None:
        failures.append("license_type_not_claimed")
        details["required_license_type"] = folder_license_type

    # 3. License number present
    if not parsed.license_number:
        failures.append("missing_license_number")

    # 4. Jurisdiction matches
    if parsed.jurisdiction_claimed is None:
        failures.append("jurisdiction_not_claimed")
        details["required_jurisdiction"] = folder_jurisdiction

    # 5. Attestation language present
    if not parsed.has_attestation_lang:
        failures.append("missing_attestation_language")
        details["required_phrases"] = list(ATTESTATION_PHRASES)

    # 6. NOT_DECLINED — already handled above (short-circuit)

    return GateResult(
        passed=(len(failures) == 0),
        failures=failures,
        details=details,
    )


# ─────────────────────────────────────────────────────────────────────
# Inbound DB query helpers
# ─────────────────────────────────────────────────────────────────────


def fetch_candidate_replies(
    *,
    since: Optional[str] = None,
    limit: int = 200,
    inbound_db_path: str = INBOUND_DB_PATH,
) -> List[Dict[str, Any]]:
    """Pull recent inbound rows that mention an engagement ID in subject or body.

    Args:
      since: ISO timestamp; only return rows with received_at >= since.
             If None, returns the most recent `limit` rows.
      limit: cap on rows returned (defensive — engagement matching should
             never need to scan all 63k+ historical rows).
    """
    con = sqlite3.connect(inbound_db_path)
    try:
        # Match anywhere "eng_" appears in subject or body_preview. Cheap
        # initial filter — the regex in parse_attestation makes the
        # final determination.
        params: List[Any] = []
        sql = """
            SELECT id, received_at, from_addr, to_addr, subject, body_preview
            FROM inbound_replies
            WHERE (subject LIKE '%eng_%' OR body_preview LIKE '%eng_%')
        """
        if since:
            sql += " AND received_at >= ?"
            params.append(since)
        sql += " ORDER BY received_at DESC LIMIT ?"
        params.append(limit)
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # DB or table doesn't exist yet — return empty
        return []
    finally:
        con.close()

    return [
        {
            "id":           r[0],
            "received_at":  r[1],
            "from_addr":    r[2],
            "to_addr":      r[3],
            "subject":      r[4],
            "body_preview": r[5] or "",
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────
# End-to-end: process one reply
# ─────────────────────────────────────────────────────────────────────


def process_reply(
    reply: Dict[str, Any],
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Process a single inbound reply row against the engagement state machine.

    Returns dict describing what was done. Idempotent enough: if the folder
    is no longer in AWAITING_ATTESTATION, this is a no-op.
    """
    subject = reply.get("subject") or ""
    body    = reply.get("body_preview") or ""
    combined = f"{subject}\n\n{body}"

    # Find engagement_id in the message
    m = ENGAGEMENT_ID_RE.search(combined)
    if not m:
        return {"ok": False, "skipped": True, "reason": "no engagement_id in subject/body"}
    engagement_id = m.group(1).lower()

    folder = get_folder(engagement_id, db_path=db_path)
    if folder is None:
        return {"ok": False, "skipped": True, "reason": f"engagement {engagement_id} not found"}

    # ── PCR-054j: attach correspondence to thread FIRST, regardless of state ──
    # No message is ever dropped. Classifier always returns *something*.
    intent_result = classify_intent(body, subject)

    # ── PCR-054j: recovery from DECLINED_OR_EDITS_ASKED ──
    # Per founder's reframe (2026-06-09): a folder bounced to
    # DECLINED_OR_EDITS_ASKED is NOT terminal. If the practitioner sends a
    # real attestation later, reset to AWAITING so the gate runs again.
    if (folder.state is FolderState.DECLINED_OR_EDITS_ASKED
            and intent_result.intent == "attestation"
            and intent_result.confidence in ("high", "medium")):
        transition(
            engagement_id,
            FolderState.DRAFTING,
            actor="system:engagement_inbound",
            reason=f"PCR-054j recovery: attestation intent on declined folder ({intent_result.confidence} confidence)",
            db_path=db_path,
        )
        transition(
            engagement_id,
            FolderState.OUTREACH_QUEUED,
            actor="system:engagement_inbound",
            reason="PCR-054j recovery: re-queueing for attestation",
            db_path=db_path,
        )
        transition(
            engagement_id,
            FolderState.AWAITING_ATTESTATION,
            actor="system:engagement_inbound",
            reason="PCR-054j recovery: re-armed for gate",
            db_path=db_path,
        )
        # Refresh folder state for the gate path below
        folder = get_folder(engagement_id, db_path=db_path)

    # PCR-054j contract:
    # - Folder NOT in AWAITING: attach to thread, no state change, no gate.
    #   (The recovery path above already handled the high-conf attestation
    #    arriving on a DECLINED folder.)
    # - Folder IN AWAITING: ALWAYS run the gate. The gate is the source of
    #   truth for whether the reply is a valid attestation. Classifier intent
    #   is used to detect declines/revisions for accurate audit, but the gate
    #   itself decides terminal state.
    if folder.state is not FolderState.AWAITING_ATTESTATION:
        attach_correspondence(
            engagement_id=engagement_id,
            direction="in",
            from_email=reply.get("from_addr") or "",
            body=body,
            subject=subject,
            folder_state_at_time=folder.state.value,
            gate_applied=False,
            db_path=db_path,
        )
        return {
            "ok":            True,
            "skipped":       False,   # NOT skipped — attached to thread
            "attached":      True,
            "engagement_id": engagement_id,
            "intent":        intent_result.intent,
            "confidence":    intent_result.confidence,
            "folder_state":  folder.state.value,
            "reason":        f"intent={intent_result.intent} state={folder.state.value} — captured without state change",
        }

    # Parse + gate (only when intent is attestation AND folder is AWAITING)
    parsed = parse_attestation(
        combined,
        folder_license_type=folder.license_type_required,
        folder_jurisdiction=folder.jurisdiction_required,
    )
    gate = run_gate(
        parsed,
        expected_engagement_id=engagement_id,
        folder_license_type=folder.license_type_required or "",
        folder_jurisdiction=folder.jurisdiction_required or "",
    )

    # PCR-054j: attach to thread (with gate result captured)
    attach_correspondence(
        engagement_id=engagement_id,
        direction="in",
        from_email=reply.get("from_addr") or "",
        body=body,
        subject=subject,
        folder_state_at_time=folder.state.value,
        gate_applied=True,
        gate_result=gate.as_dict(),
        db_path=db_path,
    )

    # Record raw payload for forensics
    record_attestation_payload(
        engagement_id=engagement_id,
        from_email=reply.get("from_addr") or "",
        raw_body=f"Subject: {subject}\n\n{body}",
        license_type_claimed=parsed.license_type_claimed,
        license_number_claimed=parsed.license_number,
        license_jurisdiction_claimed=parsed.jurisdiction_claimed,
        attestation_language_present=parsed.has_attestation_lang,
        parse_errors=gate.failures if not gate.passed else [],
        db_path=db_path,
    )

    # Always advance: AWAITING -> VALIDATING (we did the work of validating)
    transition(
        engagement_id,
        FolderState.VALIDATING_ATTESTATION,
        actor="system:engagement_inbound",
        reason=f"inbound reply from {reply.get('from_addr')} - parsing complete",
        db_path=db_path,
    )

    # Decision: VALIDATING -> FINALIZED  OR  -> DECLINED_OR_EDITS_ASKED
    if gate.passed:
        transition(
            engagement_id,
            FolderState.FINALIZED,
            actor="system:engagement_inbound",
            reason=f"6-point gate passed (license #{parsed.license_number})",
            db_path=db_path,
        )
        outcome = "finalized"
    else:
        transition(
            engagement_id,
            FolderState.DECLINED_OR_EDITS_ASKED,
            actor="system:engagement_inbound",
            reason=f"gate failed: {', '.join(gate.failures)}",
            db_path=db_path,
        )
        outcome = "declined_or_edits_asked"

    return {
        "ok":            True,
        "engagement_id": engagement_id,
        "outcome":       outcome,
        "gate":          gate.as_dict(),
        "parsed": {
            "license_type_claimed": parsed.license_type_claimed,
            "license_number":       parsed.license_number,
            "jurisdiction_claimed": parsed.jurisdiction_claimed,
            "has_attestation_lang": parsed.has_attestation_lang,
            "declined":             parsed.declined,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# Batch processor (cron entrypoint)
# ─────────────────────────────────────────────────────────────────────


def process_pending_replies(
    *,
    since: Optional[str] = None,
    limit: int = 200,
    db_path: str = ENGAGEMENT_DB_PATH,
    inbound_db_path: str = INBOUND_DB_PATH,
) -> Dict[str, Any]:
    """Scan inbound replies, push every matching folder forward.

    Designed to be called from a heartbeat or systemd timer. Idempotent.
    """
    replies = fetch_candidate_replies(
        since=since, limit=limit, inbound_db_path=inbound_db_path,
    )

    results: List[Dict[str, Any]] = []
    finalized = 0
    declined = 0
    skipped = 0

    for r in replies:
        outcome = process_reply(r, db_path=db_path)
        results.append(outcome)
        if outcome.get("skipped"):
            skipped += 1
        elif outcome.get("outcome") == "finalized":
            finalized += 1
        elif outcome.get("outcome") == "declined_or_edits_asked":
            declined += 1

    return {
        "ok":         True,
        "scanned":    len(replies),
        "finalized":  finalized,
        "declined":   declined,
        "skipped":    skipped,
        "results":    results,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }

"""PCR-054c — EngagementFolder state machine + persistence.

The persistent state container for one Creation engagement.

A licensed practitioner reviews and (if they concur) attests an artifact.
The folder tracks every step:

  drafting
    -> outreach_queued    (mail_writing composes Engagement Request)
    -> awaiting_attestation (sent, watching inbox)
    -> validating_attestation (inbound reply parsed, gate running)
    -> finalized            (gate passed)
    or
    -> declined_or_edits_asked (gate failed or practitioner pushed back)
    -> verifying            (async post-fact license lookup)

Architecture (per PCR-054b.1):
  * SQLite at /var/murphy/audit/engagement_folders.db is system of record.
  * /var/murphy/engagements/<id>/ is a generated browse mirror.
  * The practitioner's inbound attestation payload is the SOURCE of license
    truth — Murphy does not pre-populate license_number/expires_at/scope.

Composes with:
  PCR-053f shadow loop (OPERATION roles) - unaffected.
  PCR-054b RoleClass.CREATION/HYBRID roles - these route here.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("murphy.engagement_folder")

# PCR-054c.1-fix: align with project convention (053f uses /var/lib/murphy-production/)
DEFAULT_DB_PATH = os.environ.get(
    "MURPHY_ENGAGEMENT_DB",
    "/var/lib/murphy-production/engagement_folders.db",
)
DEFAULT_BROWSE_ROOT = os.environ.get(
    "MURPHY_ENGAGEMENT_BROWSE_ROOT",
    "/var/lib/murphy-production/engagements",
)


# ─────────────────────────────────────────────────────────────────────
# State machine
# ─────────────────────────────────────────────────────────────────────


class FolderState(Enum):
    DRAFTING                 = "drafting"
    OUTREACH_QUEUED          = "outreach_queued"
    AWAITING_ATTESTATION     = "awaiting_attestation"
    VALIDATING_ATTESTATION   = "validating_attestation"
    FINALIZED                = "finalized"
    DECLINED_OR_EDITS_ASKED  = "declined_or_edits_asked"
    VERIFYING                = "verifying"
    VERIFIED                 = "verified"
    FLAGGED                  = "flagged"  # post-fact lookup contradicted claim


# Allowed transitions. Anything not listed here is rejected.
ALLOWED_TRANSITIONS: Dict[FolderState, set] = {
    FolderState.DRAFTING:                {FolderState.OUTREACH_QUEUED},
    FolderState.OUTREACH_QUEUED:         {FolderState.AWAITING_ATTESTATION,
                                          FolderState.DECLINED_OR_EDITS_ASKED},
    FolderState.AWAITING_ATTESTATION:    {FolderState.VALIDATING_ATTESTATION,
                                          FolderState.DECLINED_OR_EDITS_ASKED},
    FolderState.VALIDATING_ATTESTATION:  {FolderState.FINALIZED,
                                          FolderState.DECLINED_OR_EDITS_ASKED},
    FolderState.FINALIZED:               {FolderState.VERIFYING},
    FolderState.DECLINED_OR_EDITS_ASKED: {FolderState.DRAFTING,
                                          FolderState.OUTREACH_QUEUED},
    FolderState.VERIFYING:               {FolderState.VERIFIED,
                                          FolderState.FLAGGED},
    FolderState.VERIFIED:                set(),  # terminal-good
    FolderState.FLAGGED:                 set(),  # terminal-bad
}


class IllegalTransition(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────
# Dataclasses (in-memory shape)
# ─────────────────────────────────────────────────────────────────────


@dataclass
class EngagementFolder:
    engagement_id: str
    tenant_id: str
    role_id: str
    artifact_type: str
    artifact_path: str             # path to draft.pdf in browse mirror
    state: FolderState = FolderState.DRAFTING
    practitioner_id: Optional[str] = None       # set when outreach queued
    practitioner_email: Optional[str] = None
    license_type_required: Optional[str] = None # e.g. "CPA", set at draft time
    jurisdiction_required: Optional[str] = None
    rate_quote_usd: Optional[float] = None
    rate_quote_source: Optional[str] = None     # e.g. "bls:13-2011:p90:US-CA"
    deadline_at: Optional[float] = None         # unix ts
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    finalized_at: Optional[float] = None
    metadata_json: str = "{}"

    def to_row(self) -> Tuple:
        return (
            self.engagement_id, self.tenant_id, self.role_id,
            self.artifact_type, self.artifact_path, self.state.value,
            self.practitioner_id, self.practitioner_email,
            self.license_type_required, self.jurisdiction_required,
            self.rate_quote_usd, self.rate_quote_source,
            self.deadline_at, self.created_at, self.updated_at,
            self.finalized_at, self.metadata_json,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "EngagementFolder":
        return cls(
            engagement_id=row["engagement_id"],
            tenant_id=row["tenant_id"],
            role_id=row["role_id"],
            artifact_type=row["artifact_type"],
            artifact_path=row["artifact_path"],
            state=FolderState(row["state"]),
            practitioner_id=row["practitioner_id"],
            practitioner_email=row["practitioner_email"],
            license_type_required=row["license_type_required"],
            jurisdiction_required=row["jurisdiction_required"],
            rate_quote_usd=row["rate_quote_usd"],
            rate_quote_source=row["rate_quote_source"],
            deadline_at=row["deadline_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            finalized_at=row["finalized_at"],
            metadata_json=row["metadata_json"] or "{}",
        )


@dataclass
class EngagementEvent:
    """Append-only log row. Every transition + every external touch."""
    event_id: Optional[int]      # sqlite autoincrement, None before insert
    engagement_id: str
    occurred_at: float
    event_type: str               # 'transition' | 'outbound_email' | 'inbound_reply' | 'system_note'
    from_state: Optional[str]
    to_state: Optional[str]
    actor: str                    # 'system' | 'practitioner:<email>' | 'tenant:<id>'
    payload_json: str = "{}"


@dataclass
class AttestationPayload:
    """Inbound attestation parsed from a practitioner's reply."""
    payload_id: Optional[int]    # sqlite autoincrement
    engagement_id: str
    received_at: float
    from_email: str
    raw_body: str                 # full email body for forensic replay
    license_type_claimed: Optional[str]
    license_number_claimed: Optional[str]
    license_jurisdiction_claimed: Optional[str]
    expires_at_claimed: Optional[float]
    scope_endorsements_claimed_json: str = "[]"
    attestation_language_present: bool = False
    qc_acknowledgments_json: str = "[]"  # which QC items the practitioner acknowledged
    parse_errors_json: str = "[]"


# ─────────────────────────────────────────────────────────────────────
# Schema + connection
# ─────────────────────────────────────────────────────────────────────


SCHEMA = """
CREATE TABLE IF NOT EXISTS engagement_folders (
    engagement_id           TEXT PRIMARY KEY,
    tenant_id               TEXT NOT NULL,
    role_id                 TEXT NOT NULL,
    artifact_type           TEXT NOT NULL,
    artifact_path           TEXT NOT NULL,
    state                   TEXT NOT NULL,
    practitioner_id         TEXT,
    practitioner_email      TEXT,
    license_type_required   TEXT,
    jurisdiction_required   TEXT,
    rate_quote_usd          REAL,
    rate_quote_source       TEXT,
    deadline_at             REAL,
    created_at              REAL NOT NULL,
    updated_at              REAL NOT NULL,
    finalized_at            REAL,
    metadata_json           TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_folders_tenant_state
    ON engagement_folders (tenant_id, state);
CREATE INDEX IF NOT EXISTS idx_folders_role
    ON engagement_folders (role_id);
CREATE INDEX IF NOT EXISTS idx_folders_practitioner_email
    ON engagement_folders (practitioner_email);

CREATE TABLE IF NOT EXISTS engagement_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id   TEXT NOT NULL,
    occurred_at     REAL NOT NULL,
    event_type      TEXT NOT NULL,
    from_state      TEXT,
    to_state        TEXT,
    actor           TEXT NOT NULL,
    payload_json    TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (engagement_id) REFERENCES engagement_folders (engagement_id)
);

CREATE INDEX IF NOT EXISTS idx_events_engagement
    ON engagement_events (engagement_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_type
    ON engagement_events (event_type, occurred_at);

CREATE TABLE IF NOT EXISTS attestation_payloads (
    payload_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id                    TEXT NOT NULL,
    received_at                      REAL NOT NULL,
    from_email                       TEXT NOT NULL,
    raw_body                         TEXT NOT NULL,
    license_type_claimed             TEXT,
    license_number_claimed           TEXT,
    license_jurisdiction_claimed     TEXT,
    expires_at_claimed               REAL,
    scope_endorsements_claimed_json  TEXT NOT NULL DEFAULT '[]',
    attestation_language_present     INTEGER NOT NULL DEFAULT 0,
    qc_acknowledgments_json          TEXT NOT NULL DEFAULT '[]',
    parse_errors_json                TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (engagement_id) REFERENCES engagement_folders (engagement_id)
);

CREATE INDEX IF NOT EXISTS idx_attestations_engagement
    ON attestation_payloads (engagement_id, received_at);
CREATE INDEX IF NOT EXISTS idx_attestations_from_email
    ON attestation_payloads (from_email);
"""


def _connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=10.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Idempotent schema bootstrap."""
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Browse mirror (filesystem)
# ─────────────────────────────────────────────────────────────────────


def browse_path_for(engagement_id: str, browse_root: str = DEFAULT_BROWSE_ROOT) -> str:
    """Return the browse directory path for an engagement. Creates it."""
    p = Path(browse_root) / engagement_id
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def write_browse_file(engagement_id: str, filename: str, content: str,
                      browse_root: str = DEFAULT_BROWSE_ROOT) -> str:
    """Write a file into the engagement's browse directory. Returns full path."""
    dirp = Path(browse_path_for(engagement_id, browse_root))
    fp = dirp / filename
    fp.write_text(content)
    return str(fp)


# ─────────────────────────────────────────────────────────────────────
# Core CRUD
# ─────────────────────────────────────────────────────────────────────


def create_folder(
    tenant_id: str,
    role_id: str,
    artifact_type: str,
    artifact_content: str = "",
    license_type_required: Optional[str] = None,
    jurisdiction_required: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = DEFAULT_DB_PATH,
    browse_root: str = DEFAULT_BROWSE_ROOT,
) -> EngagementFolder:
    """Create a fresh folder in DRAFTING state. Writes draft to browse mirror."""
    init_db(db_path)
    engagement_id = f"eng_{uuid.uuid4().hex[:12]}"
    artifact_path = write_browse_file(
        engagement_id, "draft.txt", artifact_content, browse_root,
    )
    folder = EngagementFolder(
        engagement_id=engagement_id,
        tenant_id=tenant_id,
        role_id=role_id,
        artifact_type=artifact_type,
        artifact_path=artifact_path,
        state=FolderState.DRAFTING,
        license_type_required=license_type_required,
        jurisdiction_required=jurisdiction_required,
        metadata_json=json.dumps(metadata or {}, sort_keys=True),
    )
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO engagement_folders VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            folder.to_row(),
        )
        _record_event(
            con, engagement_id, "transition", None, "drafting",
            actor="system",
            payload={"reason": "folder created"},
        )
    finally:
        con.close()
    LOG.info(
        "PCR-054c folder created %s tenant=%s role=%s artifact_type=%s",
        engagement_id, tenant_id, role_id, artifact_type,
    )
    return folder


def get_folder(engagement_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[EngagementFolder]:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM engagement_folders WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        return EngagementFolder.from_row(row) if row else None
    finally:
        con.close()


def list_folders(
    tenant_id: Optional[str] = None,
    state: Optional[FolderState] = None,
    limit: int = 50,
    db_path: str = DEFAULT_DB_PATH,
) -> List[EngagementFolder]:
    con = _connect(db_path)
    try:
        sql = "SELECT * FROM engagement_folders WHERE 1=1"
        args: list = []
        if tenant_id is not None:
            sql += " AND tenant_id = ?"; args.append(tenant_id)
        if state is not None:
            sql += " AND state = ?"; args.append(state.value)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 500)))
        return [EngagementFolder.from_row(r) for r in con.execute(sql, args).fetchall()]
    finally:
        con.close()


def transition(
    engagement_id: str,
    to_state: FolderState,
    actor: str = "system",
    reason: str = "",
    update_fields: Optional[Dict[str, Any]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> EngagementFolder:
    """Move a folder to a new state. Raises IllegalTransition on bad moves."""
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT state FROM engagement_folders WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        if row is None:
            raise IllegalTransition(f"folder {engagement_id} not found")
        from_state = FolderState(row["state"])
        if to_state not in ALLOWED_TRANSITIONS[from_state]:
            raise IllegalTransition(
                f"{from_state.value} -> {to_state.value} not allowed; "
                f"valid: {[s.value for s in ALLOWED_TRANSITIONS[from_state]]}"
            )

        # Build update SET clause
        set_parts = ["state = ?", "updated_at = ?"]
        args: list = [to_state.value, time.time()]
        if to_state is FolderState.FINALIZED:
            set_parts.append("finalized_at = ?"); args.append(time.time())
        if update_fields:
            for k, v in update_fields.items():
                if k in {"engagement_id", "tenant_id", "created_at"}:
                    continue  # never overwrite immutable fields
                set_parts.append(f"{k} = ?"); args.append(v)
        args.append(engagement_id)
        con.execute(
            f"UPDATE engagement_folders SET {', '.join(set_parts)} WHERE engagement_id = ?",
            args,
        )
        _record_event(
            con, engagement_id, "transition", from_state.value, to_state.value,
            actor=actor,
            payload={"reason": reason, "updates": list((update_fields or {}).keys())},
        )
    finally:
        con.close()
    LOG.info(
        "PCR-054c %s : %s -> %s (by %s)",
        engagement_id, from_state.value, to_state.value, actor,
    )
    folder = get_folder(engagement_id, db_path)
    assert folder is not None
    return folder


# ─────────────────────────────────────────────────────────────────────
# Events + attestation persistence
# ─────────────────────────────────────────────────────────────────────


def _record_event(
    con: sqlite3.Connection,
    engagement_id: str,
    event_type: str,
    from_state: Optional[str],
    to_state: Optional[str],
    actor: str,
    payload: Optional[Dict[str, Any]] = None,
) -> int:
    cur = con.execute(
        "INSERT INTO engagement_events "
        "(engagement_id, occurred_at, event_type, from_state, to_state, actor, payload_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            engagement_id, time.time(), event_type, from_state, to_state, actor,
            json.dumps(payload or {}, sort_keys=True),
        ),
    )
    return cur.lastrowid or 0


def record_external_event(
    engagement_id: str,
    event_type: str,
    actor: str,
    payload: Optional[Dict[str, Any]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Public hook for non-transition events (outbound email sent, inbound received, etc.)"""
    con = _connect(db_path)
    try:
        return _record_event(con, engagement_id, event_type, None, None, actor, payload)
    finally:
        con.close()


def get_events(engagement_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM engagement_events WHERE engagement_id = ? "
            "ORDER BY occurred_at ASC, event_id ASC",
            (engagement_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json"))
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        con.close()


def store_attestation_payload(
    payload: AttestationPayload,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO attestation_payloads "
            "(engagement_id, received_at, from_email, raw_body, "
            " license_type_claimed, license_number_claimed, license_jurisdiction_claimed, "
            " expires_at_claimed, scope_endorsements_claimed_json, "
            " attestation_language_present, qc_acknowledgments_json, parse_errors_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload.engagement_id, payload.received_at, payload.from_email,
                payload.raw_body, payload.license_type_claimed,
                payload.license_number_claimed, payload.license_jurisdiction_claimed,
                payload.expires_at_claimed, payload.scope_endorsements_claimed_json,
                1 if payload.attestation_language_present else 0,
                payload.qc_acknowledgments_json, payload.parse_errors_json,
            ),
        )
        return cur.lastrowid or 0
    finally:
        con.close()


def get_attestations(engagement_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM attestation_payloads WHERE engagement_id = ? "
            "ORDER BY received_at ASC",
            (engagement_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Status summary (for /api/org/engagements)
# ─────────────────────────────────────────────────────────────────────


def folder_summary(folder: EngagementFolder) -> Dict[str, Any]:
    return {
        "engagement_id":         folder.engagement_id,
        "tenant_id":             folder.tenant_id,
        "role_id":               folder.role_id,
        "artifact_type":         folder.artifact_type,
        "state":                 folder.state.value,
        "practitioner_email":    folder.practitioner_email,
        "license_type_required": folder.license_type_required,
        "jurisdiction_required": folder.jurisdiction_required,
        "rate_quote_usd":        folder.rate_quote_usd,
        "rate_quote_source":     folder.rate_quote_source,
        "deadline_at":           folder.deadline_at,
        "created_at":            folder.created_at,
        "updated_at":            folder.updated_at,
        "finalized_at":          folder.finalized_at,
        "browse_path":           browse_path_for(folder.engagement_id),
    }

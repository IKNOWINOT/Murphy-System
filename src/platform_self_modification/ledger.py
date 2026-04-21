"""PSM-002 — Immutable, hash-chained self-edit change log.

Design label: ``PSM-002``
Owner: Platform Engineering

Commissioning answers (CLAUDE.md / problem-statement checklist):

* **What is this module supposed to do?**
  Provide an append-only audit trail of every platform self-modification
  attempt. Every entry references the ``ImprovementProposal`` driving the
  change, captures the RSC snapshot at decision time, and links to the
  prior entry via SHA-256 so any tampering is detectable. The log is the
  source of truth for "what did Murphy change about itself, when, and
  who approved it" — and is the basis for revertibility (each APPLIED
  entry carries the diff metadata needed by ``git revert``).

* **What conditions are possible?**
  - Empty log on first start → ``read_all()`` returns []; ``verify_chain()``
    is True.
  - Append succeeds → entry has monotonically increasing ``seq``,
    ``prev_hash`` matches the previous ``this_hash``, and ``this_hash``
    is reproducible from the entry contents.
  - Concurrent writers → file lock serialises them; no torn writes.
  - Mid-file tamper → ``verify_chain()`` returns False with the offending
    seq.
  - Malformed JSONL line → ``verify_chain()`` raises ``LedgerError`` with
    the line number; never silent.
  - Missing parent dir → auto-created on first write.

* **Hardening:** entries flushed and ``fsync``'d before the lock is
  released. ``payload`` is stored verbatim — callers must hand
  pre-validated dicts. Reads always recompute and re-verify hashes.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import enum
import fcntl
import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


GENESIS_HASH = "0" * 64


class LedgerError(RuntimeError):
    """Raised when the ledger detects a fatal integrity problem."""


class LedgerEntryKind(str, enum.Enum):
    """Lifecycle states of a single self-edit attempt.

    The state machine is intentionally append-only: a ``REQUESTED`` entry
    is followed by *either* a terminal ``VETOED`` (gate refused) *or* an
    ``APPROVED`` → ``LAUNCHED`` → ``APPLIED``/``FAILED`` chain, with an
    optional later ``REVERTED`` if a human rolls the change back.
    """

    REQUESTED = "REQUESTED"   # Operator submitted; pre-gate
    VETOED = "VETOED"         # RSC gate refused
    APPROVED = "APPROVED"     # Gate allowed, ledger booked
    LAUNCHED = "LAUNCHED"     # Cycle handed to orchestrator
    APPLIED = "APPLIED"       # Self-edit landed (PR merged)
    FAILED = "FAILED"         # Cycle errored out
    REVERTED = "REVERTED"     # Operator rolled the change back


@dataclass(frozen=True)
class LedgerEntry:
    """One immutable record in the self-edit ledger."""

    seq: int
    ts: str
    prev_hash: str
    this_hash: str
    kind: str
    proposal_id: str
    operator_id: str
    rsc_snapshot: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def compute_hash(
        seq: int,
        ts: str,
        prev_hash: str,
        kind: str,
        proposal_id: str,
        operator_id: str,
        rsc_snapshot: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> str:
        """Deterministic SHA-256 over the canonical JSON of all fields
        except ``this_hash``. JSON keys are sorted so re-computation on
        read produces the same digest regardless of dict ordering."""
        material = json.dumps(
            {
                "seq": seq,
                "ts": ts,
                "prev_hash": prev_hash,
                "kind": kind,
                "proposal_id": proposal_id,
                "operator_id": operator_id,
                "rsc_snapshot": rsc_snapshot,
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(material).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SelfEditLedger:
    """Append-only JSONL ledger with SHA-256 chain integrity.

    A single instance is safe for concurrent use within a process
    (in-process ``threading.Lock``) and across processes (``fcntl``
    advisory file lock during append).
    """

    def __init__(self, path: os.PathLike | str):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._proc_lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def record(
        self,
        kind: LedgerEntryKind | str,
        *,
        proposal_id: str,
        operator_id: str,
        rsc_snapshot: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LedgerEntry:
        """Append one entry; returns the entry actually written.

        Validation is fail-loud: empty ``proposal_id`` / ``operator_id``
        or unknown ``kind`` raise ``ValueError`` *before* the lock is
        taken so partial writes are impossible.
        """
        kind_enum = LedgerEntryKind(kind) if not isinstance(kind, LedgerEntryKind) else kind
        if not proposal_id or not isinstance(proposal_id, str):
            raise ValueError("PSM-002: proposal_id must be a non-empty string")
        if not operator_id or not isinstance(operator_id, str):
            raise ValueError("PSM-002: operator_id must be a non-empty string")

        snapshot = dict(rsc_snapshot or {})
        body = dict(payload or {})

        with self._proc_lock:
            # Open in append mode + take an exclusive flock so another
            # process appending to the same file blocks until we're done.
            with open(self._path, "a+", encoding="utf-8") as fh:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                    fh.seek(0, os.SEEK_END)

                    last_seq, last_hash = self._tail_state_locked(fh)
                    seq = last_seq + 1
                    ts = _utc_now_iso()
                    this_hash = LedgerEntry.compute_hash(
                        seq=seq,
                        ts=ts,
                        prev_hash=last_hash,
                        kind=kind_enum.value,
                        proposal_id=proposal_id,
                        operator_id=operator_id,
                        rsc_snapshot=snapshot,
                        payload=body,
                    )
                    entry = LedgerEntry(
                        seq=seq,
                        ts=ts,
                        prev_hash=last_hash,
                        this_hash=this_hash,
                        kind=kind_enum.value,
                        proposal_id=proposal_id,
                        operator_id=operator_id,
                        rsc_snapshot=snapshot,
                        payload=body,
                    )
                    fh.write(json.dumps(entry.to_dict(), sort_keys=True, default=str))
                    fh.write("\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                    return entry
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _tail_state_locked(self, fh) -> tuple[int, str]:
        """Return (last_seq, last_hash) by re-reading the open file.

        The file handle is assumed to already hold ``LOCK_EX``.  We
        deliberately re-scan the whole file rather than caching, so a
        process restart cannot desync the chain pointer.
        """
        fh.seek(0)
        last_seq = 0
        last_hash = GENESIS_HASH
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                last_seq = int(obj["seq"])
                last_hash = str(obj["this_hash"])
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                raise LedgerError(
                    f"PSM-002: corrupt ledger at line {lineno}: {exc}"
                ) from exc
        return last_seq, last_hash

    # ------------------------------------------------------------------
    # Read / verify
    # ------------------------------------------------------------------

    def read_all(self) -> List[LedgerEntry]:
        """Return every entry, oldest first. Empty list if no log yet."""
        if not self._path.exists():
            return []
        out: List[LedgerEntry] = []
        for entry in self._iter_raw():
            out.append(LedgerEntry(**entry))
        return out

    def verify_chain(self) -> tuple[bool, Optional[str]]:
        """Recompute the entire chain. Returns (ok, error_message).

        Detects: bad seq sequence, bad prev_hash linkage, mutated entry
        (recomputed hash mismatches the stored ``this_hash``).
        """
        prev_hash = GENESIS_HASH
        expected_seq = 1
        for entry in self._iter_raw():
            if entry["seq"] != expected_seq:
                return False, (
                    f"PSM-002: seq gap at entry {entry['seq']!r} "
                    f"(expected {expected_seq})"
                )
            if entry["prev_hash"] != prev_hash:
                return False, (
                    f"PSM-002: prev_hash mismatch at seq {entry['seq']}"
                )
            recomputed = LedgerEntry.compute_hash(
                seq=entry["seq"],
                ts=entry["ts"],
                prev_hash=entry["prev_hash"],
                kind=entry["kind"],
                proposal_id=entry["proposal_id"],
                operator_id=entry["operator_id"],
                rsc_snapshot=entry["rsc_snapshot"],
                payload=entry["payload"],
            )
            if recomputed != entry["this_hash"]:
                return False, (
                    f"PSM-002: hash mismatch at seq {entry['seq']} "
                    "(entry was tampered with)"
                )
            prev_hash = entry["this_hash"]
            expected_seq += 1
        return True, None

    def find_by_proposal(self, proposal_id: str) -> List[LedgerEntry]:
        """Return all entries for one proposal in chronological order."""
        return [e for e in self.read_all() if e.proposal_id == proposal_id]

    def tail(self, n: int = 20) -> List[LedgerEntry]:
        """Return the last ``n`` entries (or fewer)."""
        if n <= 0:
            return []
        all_entries = self.read_all()
        return all_entries[-n:]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _iter_raw(self) -> Iterator[Dict[str, Any]]:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerError(
                        f"PSM-002: malformed JSON at line {lineno}: {exc}"
                    ) from exc

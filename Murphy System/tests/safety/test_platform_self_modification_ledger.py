"""Tests for PSM-002 — immutable, hash-chained self-edit ledger.

Test profile (one case per condition enumerated in ledger.py docstring):

  1. Empty log → read_all=[], verify_chain=ok.
  2. Single record → seq=1, prev_hash=GENESIS, this_hash reproducible.
  3. Multiple records → seqs monotonic, chain links correctly.
  4. verify_chain detects a mid-file tamper.
  5. verify_chain detects a seq gap.
  6. verify_chain detects a broken prev_hash link.
  7. Malformed JSONL line → LedgerError, never silent.
  8. Missing parent dir is auto-created.
  9. Concurrent threads serialise; chain stays valid.
 10. find_by_proposal returns chronological subset.
 11. Bad input (empty proposal_id, unknown kind) raises pre-write.
 12. tail() returns the last N.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from src.platform_self_modification.ledger import (
    GENESIS_HASH,
    LedgerEntry,
    LedgerEntryKind,
    LedgerError,
    SelfEditLedger,
)


@pytest.fixture
def ledger(tmp_path) -> SelfEditLedger:
    return SelfEditLedger(tmp_path / "psm" / "self_edit_ledger.jsonl")


# 1
def test_empty_log_verifies_clean(ledger):
    assert ledger.read_all() == []
    ok, err = ledger.verify_chain()
    assert ok and err is None


# 2
def test_first_record_links_to_genesis(ledger):
    e = ledger.record(
        LedgerEntryKind.REQUESTED,
        proposal_id="p-1",
        operator_id="op-alice",
        rsc_snapshot={"reason": "stable"},
        payload={"justification": "smoke"},
    )
    assert e.seq == 1
    assert e.prev_hash == GENESIS_HASH
    # Re-derive the hash from the dataclass body — must match.
    rederived = LedgerEntry.compute_hash(
        seq=e.seq, ts=e.ts, prev_hash=e.prev_hash, kind=e.kind,
        proposal_id=e.proposal_id, operator_id=e.operator_id,
        rsc_snapshot=e.rsc_snapshot, payload=e.payload,
    )
    assert rederived == e.this_hash


# 3
def test_chain_links_across_records(ledger):
    a = ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="o")
    b = ledger.record(LedgerEntryKind.APPROVED, proposal_id="p", operator_id="o")
    c = ledger.record(LedgerEntryKind.LAUNCHED, proposal_id="p", operator_id="o")
    assert (a.seq, b.seq, c.seq) == (1, 2, 3)
    assert b.prev_hash == a.this_hash
    assert c.prev_hash == b.this_hash
    ok, err = ledger.verify_chain()
    assert ok, err


# 4
def test_verify_chain_detects_tamper(ledger):
    ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="o")
    ledger.record(LedgerEntryKind.APPROVED, proposal_id="p", operator_id="o")
    # Mutate the proposal_id of the first line on disk.
    raw = ledger.path.read_text().splitlines()
    obj = json.loads(raw[0])
    obj["proposal_id"] = "p-EVIL"
    raw[0] = json.dumps(obj, sort_keys=True)
    ledger.path.write_text("\n".join(raw) + "\n")

    ok, err = ledger.verify_chain()
    assert ok is False
    assert "hash mismatch" in (err or "")


# 5
def test_verify_chain_detects_seq_gap(ledger):
    ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="o")
    ledger.record(LedgerEntryKind.APPROVED, proposal_id="p", operator_id="o")
    raw = ledger.path.read_text().splitlines()
    # Drop the middle entry to create a seq gap (1, 3 — neither links).
    ledger.path.write_text(raw[0] + "\n")
    # Re-add a synthetic entry with seq=3 but valid hash chain off seq=1.
    ledger.record(LedgerEntryKind.LAUNCHED, proposal_id="p", operator_id="o")
    # That last record would be seq=2 since we re-read the file, so
    # construct a manual gap directly:
    obj = json.loads(ledger.path.read_text().splitlines()[-1])
    obj["seq"] = 7  # introduce explicit gap
    lines = ledger.path.read_text().splitlines()
    lines[-1] = json.dumps(obj, sort_keys=True)
    ledger.path.write_text("\n".join(lines) + "\n")

    ok, err = ledger.verify_chain()
    assert ok is False
    assert "seq gap" in (err or "") or "hash mismatch" in (err or "")


# 6
def test_verify_chain_detects_broken_prev_hash(ledger):
    ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="o")
    ledger.record(LedgerEntryKind.APPROVED, proposal_id="p", operator_id="o")
    raw = ledger.path.read_text().splitlines()
    obj = json.loads(raw[1])
    obj["prev_hash"] = "f" * 64  # break the link
    raw[1] = json.dumps(obj, sort_keys=True)
    ledger.path.write_text("\n".join(raw) + "\n")

    ok, err = ledger.verify_chain()
    assert ok is False
    assert "prev_hash mismatch" in (err or "") or "hash mismatch" in (err or "")


# 7
def test_malformed_line_raises_loud(ledger):
    ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="o")
    with open(ledger.path, "a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    with pytest.raises(LedgerError, match="malformed JSON"):
        ledger.read_all()


# 8
def test_missing_parent_dir_is_auto_created(tmp_path):
    target = tmp_path / "deep" / "deeper" / "ledger.jsonl"
    led = SelfEditLedger(target)
    led.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="o")
    assert target.exists()


# 9
def test_concurrent_writes_serialise(ledger):
    """30 threads × 1 write each → 30 entries, chain valid, seqs unique."""
    errors = []

    def worker(i):
        try:
            ledger.record(
                LedgerEntryKind.REQUESTED,
                proposal_id=f"p-{i}",
                operator_id="op-bot",
            )
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    entries = ledger.read_all()
    assert len(entries) == 30
    assert sorted(e.seq for e in entries) == list(range(1, 31))
    ok, err = ledger.verify_chain()
    assert ok, err


# 10
def test_find_by_proposal_returns_chronological(ledger):
    ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p-A", operator_id="o")
    ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p-B", operator_id="o")
    ledger.record(LedgerEntryKind.APPROVED, proposal_id="p-A", operator_id="o")
    out = ledger.find_by_proposal("p-A")
    assert [e.kind for e in out] == ["REQUESTED", "APPROVED"]
    assert [e.seq for e in out] == [1, 3]


# 11
def test_bad_input_raises_pre_write(ledger):
    with pytest.raises(ValueError):
        ledger.record(LedgerEntryKind.REQUESTED, proposal_id="", operator_id="o")
    with pytest.raises(ValueError):
        ledger.record(LedgerEntryKind.REQUESTED, proposal_id="p", operator_id="")
    with pytest.raises(ValueError):
        ledger.record("not_a_real_kind", proposal_id="p", operator_id="o")
    # And nothing was written.
    assert ledger.read_all() == []


# 12
def test_tail_returns_last_n(ledger):
    for i in range(5):
        ledger.record(LedgerEntryKind.REQUESTED, proposal_id=f"p-{i}", operator_id="o")
    out = ledger.tail(n=3)
    assert [e.seq for e in out] == [3, 4, 5]
    assert ledger.tail(n=0) == []
    assert ledger.tail(n=100) == ledger.read_all()


def test_entries_survive_round_trip_to_disk(ledger):
    """Read after restart must produce identical hashes."""
    ledger.record(
        LedgerEntryKind.REQUESTED,
        proposal_id="p", operator_id="o",
        rsc_snapshot={"x": 1.5, "nested": {"a": [1, 2, 3]}},
        payload={"justification": "round-trip"},
    )
    led2 = SelfEditLedger(ledger.path)
    ok, err = led2.verify_chain()
    assert ok, err
    assert led2.read_all()[0].rsc_snapshot["nested"]["a"] == [1, 2, 3]

"""Tests for murphy_integrity_monitor — file integrity engine."""

import pathlib
from unittest import mock

import pytest

from murphy_integrity_monitor import IntegrityMonitor, _sha3_256_file, QUARANTINE_DIR


# ── build_baseline ────────────────────────────────────────────────────────
class TestBuildBaseline:
    def test_baseline_creates_hashes(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("aaa")
        (tmp_dir / "b.txt").write_text("bbb")
        mon = IntegrityMonitor(
            watched_paths=[str(tmp_dir)],
            baseline_dir=tmp_dir / "baseline",
        )
        baseline = mon.build_baseline()
        assert len(baseline) >= 2
        assert all(isinstance(v, str) and len(v) == 64 for v in baseline.values())

    def test_baseline_empty_dir(self, tmp_dir):
        mon = IntegrityMonitor(
            watched_paths=[str(tmp_dir)],
            baseline_dir=tmp_dir / "baseline",
        )
        baseline = mon.build_baseline()
        assert isinstance(baseline, dict)


# ── verify_integrity ──────────────────────────────────────────────────────
class TestVerifyIntegrity:
    def test_detects_modification(self, tmp_dir):
        f = tmp_dir / "config.txt"
        f.write_text("original")
        mon = IntegrityMonitor(
            watched_paths=[str(tmp_dir)],
            baseline_dir=tmp_dir / "baseline",
        )
        mon.build_baseline()
        f.write_text("tampered!")
        violations = mon.verify_integrity()
        assert len(violations) >= 1

    def test_no_violations_when_clean(self, tmp_dir):
        f = tmp_dir / "ok.txt"
        f.write_text("stable")
        mon = IntegrityMonitor(
            watched_paths=[str(tmp_dir)],
            baseline_dir=tmp_dir / "baseline",
        )
        mon.build_baseline()
        violations = mon.verify_integrity()
        assert violations == []


# ── quarantine ────────────────────────────────────────────────────────────
class TestQuarantine:
    def test_quarantine_moves_file(self, tmp_dir):
        f = tmp_dir / "bad.exe"
        f.write_bytes(b"\x00" * 16)
        q = tmp_dir / "quarantine"
        q.mkdir(parents=True, exist_ok=True)
        mon = IntegrityMonitor(
            watched_paths=[str(tmp_dir)],
            baseline_dir=tmp_dir / "baseline",
        )
        with mock.patch("murphy_integrity_monitor.QUARANTINE_DIR", q):
            result = mon.on_tampering_detected(str(f))
        # File should be moved; no backup means returns False
        assert not f.exists()
        assert any(q.iterdir())


# ── sha3 helper ───────────────────────────────────────────────────────────
class TestSHA3Helper:
    def test_hash_deterministic(self, tmp_dir):
        f = tmp_dir / "det.bin"
        f.write_bytes(b"deterministic")
        assert _sha3_256_file(f) == _sha3_256_file(f)

    def test_hash_changes_with_content(self, tmp_dir):
        f = tmp_dir / "x.bin"
        f.write_bytes(b"version1")
        h1 = _sha3_256_file(f)
        f.write_bytes(b"version2")
        h2 = _sha3_256_file(f)
        assert h1 != h2

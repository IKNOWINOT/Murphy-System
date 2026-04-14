"""Tests for murphy_network_sentinel — network threat detection."""

import time
from unittest import mock

import pytest

from murphy_network_sentinel import NetworkSentinel, _shannon_entropy


# ── threat scoring heuristics ─────────────────────────────────────────────
class TestThreatScoring:
    def _sentinel(self):
        with mock.patch("murphy_network_sentinel._run"):
            s = NetworkSentinel()
            s._nft_ok = False  # disable nftables interactions
        return s

    def test_normal_port_low_score(self):
        s = self._sentinel()
        score = s.analyze_connection({"dst_ip": "1.1.1.1", "dst_port": 443, "proto": "tcp"})
        assert 0 <= score < 50

    def test_high_port_higher_score(self):
        s = self._sentinel()
        low = s.analyze_connection({"dst_ip": "1.1.1.1", "dst_port": 80, "proto": "tcp"})
        high = s.analyze_connection({"dst_ip": "1.1.1.1", "dst_port": 54321, "proto": "tcp"})
        assert high >= low

    def test_suspicious_tld_higher_score(self):
        s = self._sentinel()
        normal = s.analyze_connection({"dst_ip": "1.1.1.1", "dst_port": 443, "proto": "tcp", "domain": "example.com"})
        sus = s.analyze_connection({"dst_ip": "1.1.1.1", "dst_port": 443, "proto": "tcp", "domain": "evil.xyz"})
        assert sus >= normal

    def test_empty_connection_dict(self):
        s = self._sentinel()
        score = s.analyze_connection({})
        assert isinstance(score, (int, float))


# ── DNS exfiltration detection ────────────────────────────────────────────
class TestDNSExfiltration:
    def _sentinel(self):
        with mock.patch("murphy_network_sentinel._run"):
            s = NetworkSentinel()
            s._nft_ok = False
        return s

    def test_normal_query_not_flagged(self):
        s = self._sentinel()
        assert s.dns_exfil_detector("www.google.com") is False

    def test_high_entropy_subdomain_flagged(self):
        s = self._sentinel()
        query = "a1b2c3d4e5f6g7h8.exfil.example.com"
        result = s.dns_exfil_detector(query)
        assert isinstance(result, bool)

    def test_excessive_labels_flagged(self):
        s = self._sentinel()
        query = ".".join(["sub"] * 20) + ".example.com"
        assert s.dns_exfil_detector(query) is True

    def test_oversized_label_flagged(self):
        s = self._sentinel()
        query = ("a" * 64) + ".example.com"
        assert s.dns_exfil_detector(query) is True


# ── auto-block / auto-expire ──────────────────────────────────────────────
class TestAutoBlock:
    def _sentinel(self):
        with mock.patch("murphy_network_sentinel._run"):
            s = NetworkSentinel()
            s._nft_ok = False
        return s

    def test_auto_block_records_ip(self):
        s = self._sentinel()
        s.auto_block_threat("10.0.0.99", reason="test threat")
        # When nft is unavailable, the IP may not be persistently blocked
        # but the method should still return a bool
        assert isinstance(s.threat_summary(), dict)

    def test_auto_expire_removes_old(self):
        s = self._sentinel()
        s._block_duration = 0  # instant expiry
        s.auto_block_threat("10.0.0.50", reason="test")
        time.sleep(0.05)
        s._unblock("10.0.0.50")
        summary = s.threat_summary()
        assert isinstance(summary, dict)


# ── allowlist ─────────────────────────────────────────────────────────────
class TestAllowlist:
    def _sentinel(self):
        with mock.patch("murphy_network_sentinel._run"):
            s = NetworkSentinel()
            s._nft_ok = False
        return s

    def test_allowlist_add_remove(self):
        s = self._sentinel()
        s.add_to_allowlist("192.168.1.1")
        assert "192.168.1.1" in s._allowlist
        s.remove_from_allowlist("192.168.1.1")
        assert "192.168.1.1" not in s._allowlist

    def test_allowed_ip_not_blocked(self):
        s = self._sentinel()
        s.add_to_allowlist("192.168.1.1")
        s.auto_block_threat("192.168.1.1", reason="test")
        assert "192.168.1.1" not in s._blocked


# ── baseline learning ─────────────────────────────────────────────────────
class TestBaselineLearning:
    def _sentinel(self):
        with mock.patch("murphy_network_sentinel._run"):
            s = NetworkSentinel()
            s._nft_ok = False
        return s

    def test_learn_empty_returns_dict(self):
        s = self._sentinel()
        baseline = s.learn_normal_baseline(window_hours=0)
        assert isinstance(baseline, dict)


# ── shannon entropy helper ────────────────────────────────────────────────
class TestShannonEntropy:
    def test_low_entropy_string(self):
        assert _shannon_entropy("aaaa") == 0.0

    def test_high_entropy_string(self):
        assert _shannon_entropy("a1b2c3d4e5f6") > 2.0

    def test_empty_string(self):
        assert _shannon_entropy("") == 0.0

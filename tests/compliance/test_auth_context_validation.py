"""
Test Suite: Auth Context Validation — DEFICIENCY-4

Verifies:
  - TF-IDF semantic match returns high score for similar text
  - TF-IDF semantic match returns low score for dissimilar text
  - Location validation with known/unknown locations
  - Network classification (private IP → no penalty, public → reduced confidence)
  - Device fingerprint validation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SRC_DIR / "security_plane"))


# ---------------------------------------------------------------------------
# Import helpers — use lazy import to avoid full auth module loading issues
# ---------------------------------------------------------------------------

def _get_intent_confirmer():
    from security_plane.authentication import IntentConfirmer
    return IntentConfirmer()


def _get_contextual_verifier(**kwargs):
    from security_plane.authentication import ContextualVerifier
    return ContextualVerifier(**kwargs)


# ---------------------------------------------------------------------------
# TF-IDF Semantic Match
# ---------------------------------------------------------------------------

class TestSemanticMatch:
    def _confirmer(self):
        return _get_intent_confirmer()

    def test_identical_text_returns_1(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match("delete all records", "delete all records")
        assert score == pytest.approx(1.0, abs=0.01)

    def test_similar_text_high_score(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match(
            "delete all customer records permanently",
            "delete all customer records permanently",
        )
        assert score > 0.8

    def test_overlapping_text_moderate_score(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match(
            "delete all customer records",
            "delete customer records from database",
        )
        # Should be moderately high — shares 3 of the key words
        assert score > 0.4

    def test_dissimilar_text_low_score(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match(
            "delete all customer records",
            "send an email notification",
        )
        assert score < 0.3

    def test_empty_description_returns_zero(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match("", "some understanding")
        assert score == 0.0

    def test_empty_understanding_returns_zero(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match("some description", "")
        assert score == 0.0

    def test_both_empty_returns_zero(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match("", "")
        assert score == 0.0

    def test_score_in_valid_range(self):
        ic = self._confirmer()
        score = ic._compute_semantic_match("foo bar baz", "qux quux corge")
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Location Validation
# ---------------------------------------------------------------------------

class TestLocationValidation:
    def test_known_location_no_penalty(self):
        cv = _get_contextual_verifier(known_locations={"office-nyc", "home-alice"})
        result = cv.verify_context("user1", "business_hours", location="office-nyc")
        assert result.confidence == pytest.approx(1.0, abs=0.01)
        assert result.verified is True

    def test_unknown_location_reduces_confidence(self):
        cv = _get_contextual_verifier(known_locations={"office-nyc"})
        result = cv.verify_context("user1", "business_hours", location="random-cafe")
        assert result.confidence < 1.0
        assert any("unknown" in a.lower() or "unrecognised" in a.lower() for a in result.anomalies)

    def test_no_location_provided_no_penalty(self):
        cv = _get_contextual_verifier()
        result = cv.verify_context("user1", "business_hours", location=None)
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_register_location_adds_to_registry(self):
        cv = _get_contextual_verifier()
        cv.register_location("new-office")
        result = cv.verify_context("user1", "business_hours", location="new-office")
        assert result.confidence == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Network Classification
# ---------------------------------------------------------------------------

class TestNetworkClassification:
    def _cv_with_private_networks(self):
        """Return a verifier with an explicit private_networks list for CIDR-based testing."""
        from security_plane.authentication import ContextualVerifier
        return ContextualVerifier(private_networks=[
            "10.", "172.16.", "172.17.", "172.18.", "172.19.",
            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
            "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
            "172.30.", "172.31.", "192.168.", "127.",
        ])

    def test_private_192168_no_penalty(self):
        cv = self._cv_with_private_networks()
        result = cv.verify_context("user1", "business_hours", network="192.168.1.10")
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_private_10_no_penalty(self):
        cv = self._cv_with_private_networks()
        result = cv.verify_context("user1", "business_hours", network="10.0.0.5")
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_private_172_no_penalty(self):
        cv = self._cv_with_private_networks()
        result = cv.verify_context("user1", "business_hours", network="172.16.0.1")
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_loopback_no_penalty(self):
        cv = self._cv_with_private_networks()
        result = cv.verify_context("user1", "business_hours", network="127.0.0.1")
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_public_ip_reduces_confidence(self):
        cv = self._cv_with_private_networks()
        result = cv.verify_context("user1", "business_hours", network="8.8.8.8")
        assert result.confidence < 1.0
        assert any("public" in a.lower() or "external" in a.lower() for a in result.anomalies)

    def test_no_network_no_penalty(self):
        cv = _get_contextual_verifier()
        result = cv.verify_context("user1", "business_hours", network=None)
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_heuristic_public_prefix_reduces_confidence(self):
        """Without a custom registry, only 'public'-prefixed networks are flagged."""
        cv = _get_contextual_verifier()
        result = cv.verify_context("user1", "business_hours", network="public-wifi")
        assert result.confidence < 1.0

    def test_heuristic_other_network_no_penalty(self):
        """Without a custom registry, non-'public' network names don't trigger penalty."""
        cv = _get_contextual_verifier()
        result = cv.verify_context("user1", "business_hours", network="corporate")
        assert result.confidence == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Device Validation
# ---------------------------------------------------------------------------

class TestDeviceValidation:
    def test_known_device_no_penalty(self):
        cv = _get_contextual_verifier(
            known_devices={"dev-laptop-01": {"fingerprint": "abc123"}}
        )
        result = cv.verify_context("user1", "business_hours", device_id="dev-laptop-01")
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_unknown_device_reduces_confidence(self):
        cv = _get_contextual_verifier(
            known_devices={"dev-laptop-01": {"fingerprint": "abc123"}}
        )
        result = cv.verify_context("user1", "business_hours", device_id="unknown-phone")
        assert result.confidence < 1.0

    def test_register_device_allows_access(self):
        cv = _get_contextual_verifier()
        cv.register_device("tablet-01", {"fingerprint": "xyz"})
        result = cv.verify_context("user1", "business_hours", device_id="tablet-01")
        assert result.confidence == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Compound context
# ---------------------------------------------------------------------------

class TestCompoundContext:
    def test_multiple_anomalies_compound_reduction(self):
        from security_plane.authentication import ContextualVerifier
        cv = ContextualVerifier(
            known_locations={"home"},
            private_networks=[
                "10.", "172.16.", "192.168.", "127.",
            ],
        )
        result = cv.verify_context(
            "user1",
            "after_hours",
            location="unknown-cafe",
            network="8.8.8.8",
        )
        # after_hours: *0.8, unknown location: *0.7, public network: *0.9
        expected = 1.0 * 0.8 * 0.7 * 0.9
        assert result.confidence == pytest.approx(expected, abs=0.01)
        assert result.verified is False  # below 0.7

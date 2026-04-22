"""
Tests for :mod:`src.reconciliation.intent_classifier`.

Covers:

  * Construction validation — empty corpus, malformed corpus,
    underpopulated classes, bad ``min_per_class``.
  * Tokenisation behaviour — stopwords / 1-char tokens dropped,
    non-letter junk tolerated.
  * Prediction shape — ``IntentPrediction`` fields, ranking
    monotonic-decreasing, confidences sum to ~1.0.
  * Out-of-vocab input → ``OTHER`` with ``confidence == 0.0`` and
    ``token_count == 0`` (the documented "no signal" contract).
  * Held-out generalisation on the curated Murphy corpus — gates the
    100% target on a 32-scenario sweep.
  * Leave-one-out cross-validation accuracy ≥ 0.90.
  * Integration with :class:`IntentExtractor` — when the caller leaves
    ``deliverable_type=GENERIC_TEXT`` the classifier overrides; when the
    caller has pinned a type, it is *respected*.
  * Error-handling: typed :class:`IntentClassifierError` re-raised
    through :class:`IntentExtractor` (no silent failures).

Design label: RECON-INTENT-002 / tests
"""

from __future__ import annotations

import math
from typing import List, Tuple

import pytest

from src.reconciliation import (
    DeliverableType,
    IntentClassifier,
    IntentClassifierError,
    IntentExtractor,
    IntentPrediction,
    Request,
    evaluate_corpus,
    get_corpus,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_empty_corpus_raises() -> None:
    with pytest.raises(IntentClassifierError, match="empty"):
        IntentClassifier([])


def test_min_per_class_validated() -> None:
    with pytest.raises(IntentClassifierError, match="min_per_class"):
        IntentClassifier([("hello world", DeliverableType.CODE)], min_per_class=0)


def test_underpopulated_class_raises() -> None:
    # Only 1 example for CODE but min_per_class default is 2.
    with pytest.raises(IntentClassifierError, match="below min_per_class"):
        IntentClassifier(
            [
                ("write a function", DeliverableType.CODE),
                ("write the readme", DeliverableType.DOCUMENT),
                ("write the readme guide", DeliverableType.DOCUMENT),
            ]
        )


def test_all_examples_tokenise_to_empty_raises() -> None:
    # All-stopwords / non-letter input → cannot train.
    with pytest.raises(IntentClassifierError, match="tokenised to empty"):
        IntentClassifier(
            [
                ("a is the of", DeliverableType.CODE),
                ("by to a", DeliverableType.CODE),
            ],
            min_per_class=2,
        )


def test_drops_individual_empty_examples_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    # Build a tiny corpus with one empty example mixed in.
    corpus: List[Tuple[str, DeliverableType]] = [
        ("write the readme", DeliverableType.DOCUMENT),
        ("document the runbook", DeliverableType.DOCUMENT),
        ("", DeliverableType.DOCUMENT),  # dropped, not silent
        ("plan the rollout steps", DeliverableType.PLAN),
        ("plan the migration steps", DeliverableType.PLAN),
    ]
    with caplog.at_level("WARNING", logger="src.reconciliation.intent_classifier"):
        clf = IntentClassifier(corpus, min_per_class=2)
    assert clf.corpus_size == 4
    assert any("dropping empty" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Prediction shape & contract
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trained_clf() -> IntentClassifier:
    return IntentClassifier(get_corpus())


def test_prediction_shape(trained_clf: IntentClassifier) -> None:
    pred = trained_clf.predict("Write a deploy script for staging")
    assert isinstance(pred, IntentPrediction)
    assert pred.deliverable_type == DeliverableType.SHELL_SCRIPT
    assert 0.0 < pred.confidence <= 1.0
    assert pred.token_count > 0
    # Ranking covers every trained class, monotonic-decreasing.
    assert len(pred.ranking) == len(trained_clf.classes)
    confidences = [c for _, c in pred.ranking]
    assert confidences == sorted(confidences, reverse=True)
    # Confidences are a proper distribution.
    assert math.isclose(sum(confidences), 1.0, rel_tol=1e-6, abs_tol=1e-6)


def test_out_of_vocab_returns_other_with_zero_confidence(
    trained_clf: IntentClassifier,
) -> None:
    pred = trained_clf.predict("xqzpv qwertyuiop")
    assert pred.deliverable_type == DeliverableType.OTHER
    assert pred.confidence == 0.0
    assert pred.token_count == 0


def test_empty_input_returns_other(trained_clf: IntentClassifier) -> None:
    pred = trained_clf.predict("")
    assert pred.deliverable_type == DeliverableType.OTHER
    assert pred.confidence == 0.0
    assert pred.token_count == 0


def test_none_input_does_not_crash(trained_clf: IntentClassifier) -> None:
    # None gets coerced to "" inside predict() — must not raise.
    pred = trained_clf.predict(None)  # type: ignore[arg-type]
    assert pred.deliverable_type == DeliverableType.OTHER
    assert pred.confidence == 0.0


# ---------------------------------------------------------------------------
# Generalisation — held-out sweep
# ---------------------------------------------------------------------------

# 32 held-out scenarios — every one must classify correctly.
_HELD_OUT: List[Tuple[str, DeliverableType]] = [
    ("Code up a Python function that parses ISO timestamps", DeliverableType.CODE),
    ("Implement a class method to compute the order subtotal", DeliverableType.CODE),
    ("Add a Python helper function for token bucket throttling", DeliverableType.CODE),
    ("Generate the YAML config file for the new ingest pipeline", DeliverableType.CONFIG_FILE),
    ("Write the dev environment config file with feature flags enabled", DeliverableType.CONFIG_FILE),
    ("Create the Helm values config file overriding the prod chart", DeliverableType.CONFIG_FILE),
    ("Write a bash script that promotes the canary to production", DeliverableType.SHELL_SCRIPT),
    ("Create a shell script that purges the cache nightly", DeliverableType.SHELL_SCRIPT),
    ("Build a bash script that runs the smoke tests against staging", DeliverableType.SHELL_SCRIPT),
    ("Document the failover procedure with screenshots", DeliverableType.DOCUMENT),
    ("Write a runbook document for handling Kafka consumer lag", DeliverableType.DOCUMENT),
    ("Author the design document for the new event bus", DeliverableType.DOCUMENT),
    ("Plan the steps for rolling back the failed migration", DeliverableType.PLAN),
    ("Outline a plan for splitting the orders table into shards", DeliverableType.PLAN),
    ("Build a step-by-step plan to deprecate the old admin UI", DeliverableType.PLAN),
    ("Construct the JSON payload for the user deletion webhook", DeliverableType.JSON_PAYLOAD),
    ("Build the JSON response payload for the inventory query endpoint", DeliverableType.JSON_PAYLOAD),
    ("Generate the JSON payload that the audit pipeline ingests", DeliverableType.JSON_PAYLOAD),
    ("Provision shared mailboxes for the new support pod", DeliverableType.MAILBOX_PROVISIONING),
    ("Create mailboxes for the incoming summer interns", DeliverableType.MAILBOX_PROVISIONING),
    ("Set up mailboxes with delegated access for the leadership team", DeliverableType.MAILBOX_PROVISIONING),
    ("Deploy the search service to the production cluster", DeliverableType.DEPLOYMENT_RESULT),
    ("Roll out the deployment of the new ranker to all regions", DeliverableType.DEPLOYMENT_RESULT),
    ("Promote the staging deployment of the gateway to production", DeliverableType.DEPLOYMENT_RESULT),
    ("Build a dashboard with panels for cache hit ratio and miss rate", DeliverableType.DASHBOARD),
    ("Construct an SLO dashboard with burn-rate panels per service", DeliverableType.DASHBOARD),
    ("Create a dashboard visualizing per-region request latency", DeliverableType.DASHBOARD),
    ("Wire up an automated workflow that reconciles invoices nightly", DeliverableType.WORKFLOW),
    ("Build an automated workflow that nudges stale review requests", DeliverableType.WORKFLOW),
    ("Compose a short customer-facing apology message", DeliverableType.GENERIC_TEXT),
    ("Draft a short paragraph welcoming the new VP of engineering", DeliverableType.GENERIC_TEXT),
    ("Write a short status note for the all-hands channel", DeliverableType.GENERIC_TEXT),
]


@pytest.mark.parametrize("text,expected", _HELD_OUT, ids=[t[:50] for t, _ in _HELD_OUT])
def test_held_out_classification(
    trained_clf: IntentClassifier, text: str, expected: DeliverableType,
) -> None:
    """Round-7 calibration sweep — must be 100% (no failures allowed)."""
    pred = trained_clf.predict(text)
    assert pred.deliverable_type == expected, (
        f"misclassified {text!r}: got {pred.deliverable_type.value} "
        f"(conf={pred.confidence:.3f}); top-3="
        f"{[(c.value, round(s, 3)) for c, s in pred.ranking[:3]]}"
    )


def test_loo_accuracy_above_threshold() -> None:
    """Leave-one-out accuracy on the curated corpus — minimum 90%."""
    accuracy, mistakes = evaluate_corpus(get_corpus())
    assert accuracy >= 0.90, (
        f"LOO accuracy {accuracy:.3f} below 0.90 threshold; "
        f"{len(mistakes)} mistakes — corpus may need rebalancing"
    )


def test_evaluate_corpus_rejects_tiny_corpus() -> None:
    with pytest.raises(IntentClassifierError, match="too small"):
        evaluate_corpus([("a", DeliverableType.CODE)])


# ---------------------------------------------------------------------------
# IntentExtractor integration
# ---------------------------------------------------------------------------


def test_extractor_uses_classifier_when_type_is_generic(
    trained_clf: IntentClassifier,
) -> None:
    extractor = IntentExtractor(classifier=trained_clf)
    req = Request(
        text="Write a bash script that backs up the database to S3",
        deliverable_type=DeliverableType.GENERIC_TEXT,
    )
    [spec] = extractor.extract(req)
    assert spec.deliverable_type == DeliverableType.SHELL_SCRIPT


def test_extractor_respects_pinned_type_over_classifier(
    trained_clf: IntentClassifier,
) -> None:
    extractor = IntentExtractor(classifier=trained_clf)
    req = Request(
        text="Write a bash script that backs up the database to S3",
        deliverable_type=DeliverableType.DOCUMENT,  # caller has pinned this
    )
    [spec] = extractor.extract(req)
    # Caller knows best — classifier must not override an explicit pin.
    assert spec.deliverable_type == DeliverableType.DOCUMENT


def test_extractor_ignores_classifier_below_confidence_floor(
    trained_clf: IntentClassifier,
) -> None:
    # Floor of 0.99 means the classifier essentially never wins.
    extractor = IntentExtractor(classifier=trained_clf, classifier_min_confidence=0.99)
    req = Request(
        text="Write a bash script that backs up the database to S3",
        deliverable_type=DeliverableType.GENERIC_TEXT,
    )
    [spec] = extractor.extract(req)
    assert spec.deliverable_type == DeliverableType.GENERIC_TEXT


def test_extractor_validates_confidence_floor_bounds() -> None:
    with pytest.raises(ValueError, match="classifier_min_confidence"):
        IntentExtractor(classifier_min_confidence=1.5)
    with pytest.raises(ValueError, match="classifier_min_confidence"):
        IntentExtractor(classifier_min_confidence=-0.1)


def test_extractor_works_without_classifier() -> None:
    """No classifier wired → original heuristic behaviour, unchanged."""
    extractor = IntentExtractor()  # no classifier
    req = Request(
        text="Generate a Python function returning the factorial of n",
        deliverable_type=DeliverableType.CODE,
    )
    [spec] = extractor.extract(req)
    assert spec.deliverable_type == DeliverableType.CODE


def test_extractor_surfaces_classifier_errors_loudly() -> None:
    """Configuration bugs in the classifier must NOT be silent."""

    class _BrokenClassifier:
        def predict(self, text: str) -> IntentPrediction:
            raise IntentClassifierError("simulated config bug")

    extractor = IntentExtractor(classifier=_BrokenClassifier())  # type: ignore[arg-type]
    req = Request(text="please do something", deliverable_type=DeliverableType.GENERIC_TEXT)
    with pytest.raises(IntentClassifierError, match="simulated config bug"):
        extractor.extract(req)


def test_vague_request_uses_classifier_ranking_for_alternatives(
    trained_clf: IntentClassifier,
) -> None:
    """Vague inputs get the classifier's top-N classes as alternatives."""
    extractor = IntentExtractor(classifier=trained_clf, max_candidates=3)
    # "Build the dashboard" is concrete enough to anchor the classifier
    # but the request itself is short — primary stays GENERIC_TEXT only
    # if classifier confidence is low; here it should be high.
    req = Request(
        text="build the SRE dashboard",
        deliverable_type=DeliverableType.GENERIC_TEXT,
    )
    specs = extractor.extract(req)
    types = [s.deliverable_type for s in specs]
    assert DeliverableType.DASHBOARD in types

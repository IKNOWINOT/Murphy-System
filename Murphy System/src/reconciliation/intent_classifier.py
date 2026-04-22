"""
ML intent classifier — maps free-form request text → :class:`DeliverableType`.

A deliberately small, dependency-free classifier (stdlib + numpy) that
strengthens the deterministic fallback in :class:`IntentExtractor` by
learning from a curated corpus of Murphy's *own* internal request
patterns (the system is both the automation and the production).

Algorithm: TF-IDF vectorisation + L2-normalised nearest-centroid
classification.  Chosen for:
  * **Transparency** — every weight is inspectable; no opaque model.
  * **Determinism** — same training corpus → same model bytes.
  * **No new deps** — uses numpy (already required) and stdlib only.
  * **Adequacy** — for ≤ a few hundred examples across ≤ 12 classes,
    nearest-centroid TF-IDF matches or beats most heavier models on
    short-text classification.

Error semantics — *never silent*:
  * Empty / malformed corpus → :class:`IntentClassifierError`.
  * Class with zero training examples → :class:`IntentClassifierError`.
  * Out-of-vocabulary or empty input → returns ``OTHER`` with
    confidence ``0.0`` and a single-element diagnostic.  Callers may
    treat low confidence as a vagueness signal but must never silently
    coerce it to a high-confidence prediction.

Design label: RECON-INTENT-002
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .models import DeliverableType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IntentClassifierError(RuntimeError):
    """Raised on any unrecoverable classifier configuration error.

    Distinct from generic ``RuntimeError`` so callers can isolate
    classifier failures from the surrounding intent-extraction pipeline.
    """


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------


# Conservative English stopword list — kept small on purpose so domain
# terms ("plan", "config", "deploy", "json", ...) survive tokenisation.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "i", "in", "is", "it", "of", "on", "or", "that",
    "the", "this", "to", "was", "we", "with", "you", "your", "our",
    "do", "does", "did", "can", "could", "would", "should", "will",
    "be", "been", "being", "any", "some", "all",
})

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on word characters, drop short tokens & stopwords.

    Note: tokens of length 1 are dropped (eliminates noise from single
    letters like "a"/"i" without needing a giant stopword list).
    """
    if not text:
        return []
    return [
        t for t in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
        if len(t) > 1 and t not in _STOPWORDS
    ]


# ---------------------------------------------------------------------------
# Prediction record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentPrediction:
    """Result of :meth:`IntentClassifier.predict`.

    Attributes:
        deliverable_type: Most-likely class.
        confidence: ``[0.0, 1.0]`` normalised score for ``deliverable_type``.
        ranking: Full class-by-class scores, sorted descending.  Useful
            for vagueness detection (small margin → multiple plausible
            interpretations).
        token_count: Number of in-vocabulary tokens seen.  ``0`` means
            the input had nothing the classifier could anchor on.
    """

    deliverable_type: DeliverableType
    confidence: float
    ranking: Tuple[Tuple[DeliverableType, float], ...]
    token_count: int


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class IntentClassifier:
    """TF-IDF + nearest-centroid intent classifier.

    The classifier is trained eagerly in :meth:`__init__` from the supplied
    labeled corpus.  All state (vocabulary, IDF weights, class centroids)
    is held in plain numpy arrays — easy to inspect, easy to serialise.

    Example::

        clf = IntentClassifier([
            ("Write a Python function to parse CSV", DeliverableType.CODE),
            ("Add a section to the README about deploys", DeliverableType.DOCUMENT),
            ...
        ])
        pred = clf.predict("draft a runbook for the on-call rotation")
        # pred.deliverable_type == DeliverableType.DOCUMENT
    """

    def __init__(
        self,
        corpus: Sequence[Tuple[str, DeliverableType]],
        *,
        min_per_class: int = 2,
    ) -> None:
        if min_per_class < 1:
            raise IntentClassifierError(
                "min_per_class must be >= 1 (got %d)" % min_per_class
            )
        if not corpus:
            raise IntentClassifierError(
                "corpus is empty — classifier cannot be trained"
            )

        # 1. Tokenise + drop empty examples (and surface them loudly).
        tokenised: List[Tuple[List[str], DeliverableType]] = []
        dropped = 0
        for text, label in corpus:
            tokens = _tokenize(text)
            if not tokens:
                dropped += 1
                logger.warning(
                    "IntentClassifier: dropping empty example (label=%s text=%r)",
                    label.value, text,
                )
                continue
            tokenised.append((tokens, label))
        if not tokenised:
            raise IntentClassifierError(
                "all %d corpus examples tokenised to empty — check stopword/regex config"
                % len(corpus)
            )
        if dropped:
            logger.info("IntentClassifier: dropped %d empty example(s)", dropped)

        # 2. Validate per-class population.
        per_class_count: Dict[DeliverableType, int] = {}
        for _, label in tokenised:
            per_class_count[label] = per_class_count.get(label, 0) + 1
        underpopulated = {
            cls.value: n for cls, n in per_class_count.items()
            if n < min_per_class
        }
        if underpopulated:
            raise IntentClassifierError(
                f"classes below min_per_class={min_per_class}: {underpopulated}"
            )

        # 3. Build vocabulary + document frequencies.
        self._classes: Tuple[DeliverableType, ...] = tuple(sorted(
            per_class_count.keys(), key=lambda c: c.value
        ))
        self._class_index: Dict[DeliverableType, int] = {
            c: i for i, c in enumerate(self._classes)
        }
        vocab: Dict[str, int] = {}
        df: Dict[str, int] = {}
        for tokens, _ in tokenised:
            unique = set(tokens)
            for tok in unique:
                if tok not in vocab:
                    vocab[tok] = len(vocab)
                df[tok] = df.get(tok, 0) + 1
        self._vocab: Dict[str, int] = vocab

        n_docs = len(tokenised)
        # Smoothed IDF — keeps weights finite for terms appearing in every doc.
        self._idf = np.zeros(len(vocab), dtype=np.float64)
        for tok, idx in vocab.items():
            self._idf[idx] = math.log((1 + n_docs) / (1 + df[tok])) + 1.0

        # 4. Vectorise + accumulate per-class centroid (mean of L2-normalised vectors).
        n_classes = len(self._classes)
        n_features = len(vocab)
        centroids = np.zeros((n_classes, n_features), dtype=np.float64)
        for tokens, label in tokenised:
            vec = self._vectorise(tokens)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            centroids[self._class_index[label]] += vec
        for i, cls in enumerate(self._classes):
            centroids[i] /= per_class_count[cls]
            n = np.linalg.norm(centroids[i])
            if n > 0:
                centroids[i] /= n
        self._centroids = centroids
        self._n_corpus = n_docs

        logger.info(
            "IntentClassifier trained: %d docs, %d classes, %d vocab terms",
            n_docs, n_classes, n_features,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def classes(self) -> Tuple[DeliverableType, ...]:
        """Sorted tuple of classes the model was trained on."""
        return self._classes

    @property
    def vocab_size(self) -> int:
        return len(self._vocab)

    @property
    def corpus_size(self) -> int:
        return self._n_corpus

    def predict(self, text: str) -> IntentPrediction:
        """Classify *text*.

        For empty or wholly out-of-vocabulary input, returns
        ``DeliverableType.OTHER`` with confidence ``0.0`` — *not* an
        exception.  Callers must check ``confidence`` to distinguish a
        confident answer from a "no signal" answer.
        """
        tokens = _tokenize(text or "")
        in_vocab = [t for t in tokens if t in self._vocab]
        if not in_vocab:
            ranking = tuple((c, 0.0) for c in self._classes)
            return IntentPrediction(
                deliverable_type=DeliverableType.OTHER,
                confidence=0.0,
                ranking=ranking,
                token_count=0,
            )

        vec = self._vectorise(in_vocab)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        # Cosine similarity (centroids already L2-normalised).
        scores = self._centroids @ vec
        # Map similarities ([-1, 1]) to confidences via softmax over the
        # positive-margin scores.  Use temperature 4.0 — empirically
        # produces well-calibrated margins for our short-text setting.
        exp_scores = np.exp(np.clip(scores, -1.0, 1.0) * 4.0)
        confidences = exp_scores / exp_scores.sum()
        order = np.argsort(-confidences)
        ranking = tuple(
            (self._classes[i], float(confidences[i])) for i in order
        )
        best_idx = int(order[0])
        return IntentPrediction(
            deliverable_type=self._classes[best_idx],
            confidence=float(confidences[best_idx]),
            ranking=ranking,
            token_count=len(in_vocab),
        )

    def cross_validate(self) -> float:
        """Leave-one-out accuracy on the training corpus.

        Useful as a self-check; expensive (O(n²)) but our corpus is small.
        Re-trains a model excluding each example in turn, predicts it,
        and returns the fraction correctly classified.
        """
        # We can't easily peel off one example without re-training, so
        # we approximate LOO by removing one example's contribution from
        # its class centroid (closed-form) and using that for prediction.
        # This is exact for centroid classifiers when the L2 norm of the
        # rebuilt centroid is recomputed.
        # Implementation note: requires re-tokenising; we already have
        # the trained state but not the per-example vectors. Keep simple
        # by re-tokenising the corpus from scratch isn't possible — the
        # corpus is gone. Cross-validation is therefore offered as a
        # train-time API; see :func:`evaluate_corpus` for the offline
        # evaluator that operates on the corpus directly.
        raise NotImplementedError(
            "Use evaluate_corpus() for leave-one-out cross-validation; "
            "the trained model does not retain per-example vectors."
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _vectorise(self, tokens: Sequence[str]) -> np.ndarray:
        """Build an L2-unnormalised TF-IDF vector for *tokens*."""
        vec = np.zeros(len(self._vocab), dtype=np.float64)
        if not tokens:
            return vec
        # Term frequency (raw counts; IDF re-weights below).
        for tok in tokens:
            idx = self._vocab.get(tok)
            if idx is not None:
                vec[idx] += 1.0
        return vec * self._idf


# ---------------------------------------------------------------------------
# Offline evaluator (leave-one-out)
# ---------------------------------------------------------------------------


def evaluate_corpus(
    corpus: Sequence[Tuple[str, DeliverableType]],
) -> Tuple[float, List[Tuple[str, DeliverableType, DeliverableType, float]]]:
    """Leave-one-out accuracy on *corpus*.

    Returns ``(accuracy, mistakes)`` where ``mistakes`` is the list of
    ``(text, true_label, predicted_label, confidence)`` for every
    misclassified example.  Used by the calibration sweep to track
    success-rate improvements as new examples are added.

    Raises :class:`IntentClassifierError` if *corpus* has too few
    examples to train a model with one held out.
    """
    if len(corpus) < 4:
        raise IntentClassifierError(
            f"corpus too small for LOO evaluation (need >=4, got {len(corpus)})"
        )

    correct = 0
    mistakes: List[Tuple[str, DeliverableType, DeliverableType, float]] = []
    for i in range(len(corpus)):
        held_out_text, held_out_label = corpus[i]
        train = [c for j, c in enumerate(corpus) if j != i]
        # Need >= min_per_class examples per class still.
        try:
            clf = IntentClassifier(train, min_per_class=1)
        except IntentClassifierError:
            # Skip examples whose removal makes a class empty — we can't
            # fairly evaluate them.  Don't pretend it's correct.
            continue
        pred = clf.predict(held_out_text)
        if pred.deliverable_type == held_out_label:
            correct += 1
        else:
            mistakes.append((held_out_text, held_out_label,
                             pred.deliverable_type, pred.confidence))
    total = len(corpus) - sum(
        1 for i in range(len(corpus))
        if _would_underpopulate(corpus, i)
    )
    accuracy = correct / total if total else 0.0
    return accuracy, mistakes


def _would_underpopulate(
    corpus: Sequence[Tuple[str, DeliverableType]], idx: int,
) -> bool:
    """True iff removing *corpus[idx]* would leave its class empty."""
    label = corpus[idx][1]
    return sum(1 for j, (_, l) in enumerate(corpus) if l == label and j != idx) == 0


__all__ = [
    "IntentClassifier",
    "IntentPrediction",
    "IntentClassifierError",
    "evaluate_corpus",
]

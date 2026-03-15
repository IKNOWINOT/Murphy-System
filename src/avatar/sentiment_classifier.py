"""Simple keyword-based sentiment classifier."""

import logging
from typing import Dict, List

from .avatar_models import SentimentResult

logger = logging.getLogger(__name__)


class SentimentClassifier:
    """Simple keyword-based sentiment classifier (no external ML dependencies)."""

    POSITIVE_WORDS = {
        "good", "great", "excellent", "happy", "love", "wonderful",
        "amazing", "perfect", "thank", "thanks", "awesome", "brilliant",
        "fantastic",
    }
    NEGATIVE_WORDS = {
        "bad", "terrible", "awful", "hate", "horrible", "poor",
        "worst", "angry", "frustrated", "disappointed", "annoying",
        "useless",
    }

    def classify(self, text: str) -> SentimentResult:
        """Classify sentiment of text using keyword matching."""
        words = set(text.lower().split())
        pos_count = len(words & self.POSITIVE_WORDS)
        neg_count = len(words & self.NEGATIVE_WORDS)
        total = pos_count + neg_count

        if total == 0:
            sentiment = "neutral"
            confidence = 0.5
            emotions: Dict[str, float] = {}
        elif pos_count > neg_count:
            sentiment = "positive"
            confidence = min(pos_count / max(total, 1), 1.0)
            emotions = {"joy": confidence}
        elif neg_count > pos_count:
            sentiment = "negative"
            confidence = min(neg_count / max(total, 1), 1.0)
            emotions = {"anger": confidence * 0.5, "sadness": confidence * 0.5}
        else:
            sentiment = "neutral"
            confidence = 0.5
            emotions = {}

        return SentimentResult(
            text=text,
            sentiment=sentiment,
            confidence=confidence,
            emotions=emotions,
        )

    def classify_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Classify sentiment for multiple texts."""
        return [self.classify(t) for t in texts]

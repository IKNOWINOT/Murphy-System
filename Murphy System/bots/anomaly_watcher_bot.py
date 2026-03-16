from __future__ import annotations

import numpy as np
from .anomaly_detection import ewma_control


class AnomalyWatcherBot:
    def __init__(self, alpha: float = 0.2) -> None:
        self.alpha = alpha

    def detect(self, data: np.ndarray) -> np.ndarray:
        return ewma_control(data, alpha=self.alpha)


class ThresholdRefinerBot:
    def adjust(self, baseline: float, new_value: float) -> float:
        return baseline * 0.9 + new_value * 0.1

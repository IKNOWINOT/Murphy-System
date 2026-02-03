"""Anomaly detection utilities using statistical process control."""
from __future__ import annotations

import numpy as np


def detect_anomalies(values: np.ndarray, threshold: float = 3.0) -> np.ndarray:
    mean = np.mean(values)
    std = np.std(values)
    z_scores = np.abs((values - mean) / std)
    return np.where(z_scores > threshold)[0]


def ewma_control(data: np.ndarray, alpha: float = 0.2) -> np.ndarray:
    """Return boolean mask where EWMA exceeds 3-sigma control limits."""
    if len(data) == 0:
        return np.array([], dtype=bool)
    ewma = np.empty_like(data, dtype=float)
    ewma[0] = data[0]
    for i in range(1, len(data)):
        ewma[i] = alpha * data[i] + (1 - alpha) * ewma[i - 1]
    std = data.std()
    ucl = ewma + 3 * std
    lcl = ewma - 3 * std
    return (data > ucl) | (data < lcl)

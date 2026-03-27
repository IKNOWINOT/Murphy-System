# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Configuration
================================

Singleton configuration class backed by environment variables, following
the same pattern as ``murphy_system/src/config.py``.

Environment variables
---------------------
MURPHY_TT_DEFAULT_RATE        — default_hourly_rate (float, default 150.00)
MURPHY_TT_CURRENCY            — default_currency (str, default "USD")
MURPHY_TT_AUTO_INVOICE_THRESHOLD — auto_invoice_threshold_hours (float, default 40.0)
MURPHY_TT_MAX_TIMER_HOURS     — max_timer_duration_hours (float, default 12.0)
MURPHY_TT_WORK_WEEK_HOURS     — work_week_hours (float, default 40.0)
MURPHY_TT_REQUIRE_APPROVAL    — require_approval (bool, default True)
MURPHY_TT_ROUNDING_MINUTES    — rounding_increment_minutes (int, default 15)
MURPHY_TT_BILLABLE_DEFAULT    — billable_by_default (bool, default True)
MURPHY_TT_OVERTIME_THRESHOLD  — allowed_overtime_percentage (float, default 0.25)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import math
import os
import threading
from typing import List, Optional


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if raw.strip():
        return float(raw.strip())
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if raw.strip():
        return int(raw.strip())
    return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name, "").strip()
    return raw if raw else default


class TimeTrackingConfig:
    """Singleton configuration for time tracking behaviour.

    Obtain the instance via :meth:`get_config`.  Call :meth:`reload` to
    re-read all env vars without restarting the process.  Call
    :meth:`_reset` (classmethod) to discard the singleton — useful for
    test isolation.
    """

    _instance: Optional["TimeTrackingConfig"] = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._load_from_env()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_config(cls) -> "TimeTrackingConfig":
        """Return the singleton instance, creating it if necessary."""
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset(cls) -> None:
        """Discard singleton — for testing only."""
        with cls._singleton_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Load / reload
    # ------------------------------------------------------------------

    def _load_from_env(self) -> None:
        self.default_hourly_rate: float = _env_float(
            "MURPHY_TT_DEFAULT_RATE", 150.00
        )
        self.default_currency: str = _env_str("MURPHY_TT_CURRENCY", "USD")
        self.auto_invoice_threshold_hours: float = _env_float(
            "MURPHY_TT_AUTO_INVOICE_THRESHOLD", 40.0
        )
        self.max_timer_duration_hours: float = _env_float(
            "MURPHY_TT_MAX_TIMER_HOURS", 12.0
        )
        self.work_week_hours: float = _env_float(
            "MURPHY_TT_WORK_WEEK_HOURS", 40.0
        )
        self.require_approval: bool = _env_bool(
            "MURPHY_TT_REQUIRE_APPROVAL", True
        )
        self.rounding_increment_minutes: int = _env_int(
            "MURPHY_TT_ROUNDING_MINUTES", 15
        )
        self.billable_by_default: bool = _env_bool(
            "MURPHY_TT_BILLABLE_DEFAULT", True
        )
        self.allowed_overtime_percentage: float = _env_float(
            "MURPHY_TT_OVERTIME_THRESHOLD", 0.25
        )

    def reload(self) -> None:
        """Re-read all settings from environment variables."""
        with self._lock:
            self._load_from_env()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise all settings to a plain dict."""
        with self._lock:
            return {
                "default_hourly_rate": self.default_hourly_rate,
                "default_currency": self.default_currency,
                "auto_invoice_threshold_hours": self.auto_invoice_threshold_hours,
                "max_timer_duration_hours": self.max_timer_duration_hours,
                "work_week_hours": self.work_week_hours,
                "require_approval": self.require_approval,
                "rounding_increment_minutes": self.rounding_increment_minutes,
                "billable_by_default": self.billable_by_default,
                "allowed_overtime_percentage": self.allowed_overtime_percentage,
            }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Check all values are within acceptable ranges.

        Returns a list of warning strings (empty = all OK).
        """
        warnings: List[str] = []
        with self._lock:
            if self.default_hourly_rate < 0:
                warnings.append(
                    f"default_hourly_rate is negative ({self.default_hourly_rate})"
                )
            if self.rounding_increment_minutes <= 0:
                warnings.append(
                    f"rounding_increment_minutes must be > 0 "
                    f"(got {self.rounding_increment_minutes})"
                )
            if self.max_timer_duration_hours <= 0:
                warnings.append(
                    f"max_timer_duration_hours must be > 0 "
                    f"(got {self.max_timer_duration_hours})"
                )
            if self.work_week_hours <= 0:
                warnings.append(
                    f"work_week_hours must be > 0 (got {self.work_week_hours})"
                )
            if self.auto_invoice_threshold_hours < 0:
                warnings.append(
                    f"auto_invoice_threshold_hours is negative "
                    f"({self.auto_invoice_threshold_hours})"
                )
            if not (0.0 <= self.allowed_overtime_percentage <= 1.0):
                warnings.append(
                    f"allowed_overtime_percentage should be between 0 and 1 "
                    f"(got {self.allowed_overtime_percentage})"
                )
            if not self.default_currency or len(self.default_currency) != 3:
                warnings.append(
                    f"default_currency should be a 3-letter ISO 4217 code "
                    f"(got {self.default_currency!r})"
                )
        return warnings

    # ------------------------------------------------------------------
    # Duration rounding
    # ------------------------------------------------------------------

    def round_duration(self, seconds: int) -> int:
        """Round *seconds* to the nearest ``rounding_increment_minutes``.

        Example: 500 seconds with a 15-minute increment → 900 seconds
        (500 s ≈ 8.33 min; nearest 15-min mark is 15 min = 900 s).
        """
        with self._lock:
            increment_seconds = self.rounding_increment_minutes * 60
        if increment_seconds <= 0:
            return seconds
        return int(round(seconds / increment_seconds) * increment_seconds)

    # ------------------------------------------------------------------
    # Partial update
    # ------------------------------------------------------------------

    def update(self, data: dict) -> List[str]:
        """Apply a partial update from *data* dict.

        Returns a list of keys that were updated.
        """
        allowed = {
            "default_hourly_rate": float,
            "default_currency": str,
            "auto_invoice_threshold_hours": float,
            "max_timer_duration_hours": float,
            "work_week_hours": float,
            "require_approval": bool,
            "rounding_increment_minutes": int,
            "billable_by_default": bool,
            "allowed_overtime_percentage": float,
        }
        updated: List[str] = []
        with self._lock:
            for key, cast in allowed.items():
                if key in data:
                    setattr(self, key, cast(data[key]))
                    updated.append(key)
        return updated

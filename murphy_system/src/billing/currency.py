"""
Currency Conversion & Regional Pricing — Murphy System Billing

Converts USD base prices to local fiat currencies using a static
exchange-rate table (updated at startup or on-demand via an external
API).  Also applies regional discounts:

  • **Japan (JPY / locale ``ja``)** — 10 % automatic discount

The static rate table covers every currency that Coinbase Commerce
and PayPal support.  Rates are approximate and should be refreshed
from a live feed in production (see ``refresh_rates``).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------

# ISO 4217 currency codes: 3 uppercase letters
_CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")

# Exchange rate sanity bounds — reject extreme / malicious values
_MIN_RATE = 1e-6      # no rate below 0.000001
_MAX_RATE = 1_000_000  # no rate above 1,000,000 (covers VND, IDR, etc.)


# ---------------------------------------------------------------------------
# Static exchange rates (1 USD → X)
# Approximate mid-market rates — updated 2026-03-13.
# In production, call ``refresh_rates()`` to pull from a live feed.
# ---------------------------------------------------------------------------

_DEFAULT_RATES: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 149.50,
    "CAD": 1.36,
    "AUD": 1.54,
    "CHF": 0.88,
    "CNY": 7.24,
    "INR": 83.10,
    "BRL": 4.97,
    "MXN": 17.15,
    "KRW": 1330.0,
    "SGD": 1.34,
    "HKD": 7.82,
    "NOK": 10.55,
    "SEK": 10.42,
    "DKK": 6.88,
    "NZD": 1.63,
    "ZAR": 18.65,
    "RUB": 91.50,
    "TRY": 30.25,
    "PLN": 4.02,
    "THB": 35.60,
    "TWD": 31.50,
    "MYR": 4.72,
    "PHP": 55.80,
    "IDR": 15650.0,
    "VND": 24500.0,
    "CZK": 22.80,
    "ILS": 3.64,
    "CLP": 890.0,
    "ARS": 830.0,
    "COP": 3950.0,
    "PEN": 3.72,
    "EGP": 30.90,
    "NGN": 1550.0,
    "KES": 153.0,
    "GHS": 12.50,
    "AED": 3.67,
    "SAR": 3.75,
    "QAR": 3.64,
    "KWD": 0.31,
    "BHD": 0.38,
    "OMR": 0.39,
    "PKR": 279.0,
    "BDT": 110.0,
    "LKR": 310.0,
    "HUF": 355.0,
    "RON": 4.59,
    "BGN": 1.80,
    "HRK": 6.95,
    "UAH": 37.50,
}

# Currencies whose locale qualifies for the 10% Japan discount
_JAPAN_DISCOUNT_CURRENCIES = frozenset({"JPY"})
_JAPAN_DISCOUNT_LOCALES = frozenset({"ja", "ja_jp", "ja-jp"})
_JAPAN_DISCOUNT_LOCALES_NORMALIZED = frozenset(
    lc.replace("_", "-") for lc in _JAPAN_DISCOUNT_LOCALES
)
_JAPAN_DISCOUNT_RATE = 0.10  # 10%


class CurrencyConverter:
    """Convert USD prices to local currencies with optional regional discounts.

    Thread-safe — the rate table can be refreshed at runtime.

    Usage::

        cc = CurrencyConverter()
        jpy_price = cc.convert(29.00, "JPY")          # ≈ 4,355.50
        jpy_discounted = cc.localize(29.00, "JPY", locale="ja")  # 10% off
    """

    def __init__(self, rates: Optional[Dict[str, float]] = None) -> None:
        self._lock = threading.Lock()
        self._rates: Dict[str, float] = dict(rates or _DEFAULT_RATES)
        self._last_refresh: Optional[str] = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, usd_amount: float, currency: str) -> float:
        """Convert *usd_amount* to *currency* using the current rate table.

        Returns the amount rounded to 2 decimal places (or 0 for JPY/KRW
        since those currencies don't use decimals).

        Raises ValueError if the currency code is malformed or unsupported.
        """
        currency = currency.upper()
        if not _CURRENCY_CODE_RE.match(currency):
            raise ValueError(f"Invalid currency code format: {currency!r}")
        with self._lock:
            rate = self._rates.get(currency)
        if rate is None:
            raise ValueError(f"Unsupported currency: {currency}")
        converted = usd_amount * rate
        if currency in ("JPY", "KRW", "VND", "IDR"):
            return float(round(converted))
        return round(converted, 2)

    def localize(
        self,
        usd_amount: float,
        currency: str = "USD",
        locale: str = "",
    ) -> Dict[str, Any]:
        """Convert and apply regional discounts.

        Returns a dict with ``amount``, ``currency``, ``discount_applied``,
        ``discount_percent``, and ``original_usd``.
        """
        currency = currency.upper()
        locale_lower = locale.lower().replace("_", "-") if locale else ""
        discount_pct = 0.0

        # Japan 10 % discount
        if currency in _JAPAN_DISCOUNT_CURRENCIES or locale_lower in _JAPAN_DISCOUNT_LOCALES_NORMALIZED:
            discount_pct = _JAPAN_DISCOUNT_RATE

        discounted_usd = usd_amount * (1.0 - discount_pct)
        converted = self.convert(discounted_usd, currency)

        return {
            "amount": converted,
            "currency": currency,
            "original_usd": usd_amount,
            "discount_applied": discount_pct > 0,
            "discount_percent": round(discount_pct * 100, 1),
            "discount_reason": "japan_regional" if discount_pct > 0 else None,
        }

    def list_currencies(self) -> list[str]:
        """Return all supported currency codes."""
        with self._lock:
            return sorted(self._rates.keys())

    def get_rate(self, currency: str) -> Optional[float]:
        """Return the current exchange rate for *currency*, or None."""
        with self._lock:
            return self._rates.get(currency.upper())

    def refresh_rates(self, new_rates: Dict[str, float]) -> None:
        """Bulk-update exchange rates (e.g. from a live API feed).

        Ignores entries with non-alphabetic currency codes or rates outside
        the sane bounds (``_MIN_RATE``..``_MAX_RATE``) to prevent injection
        of malicious values.
        """
        sanitized: Dict[str, float] = {}
        for k, v in new_rates.items():
            code = k.upper()
            if not _CURRENCY_CODE_RE.match(code):
                logger.warning("Ignoring invalid currency code in rate update: %r", k)
                continue
            if not isinstance(v, (int, float)) or v < _MIN_RATE or v > _MAX_RATE:
                logger.warning("Ignoring out-of-bounds rate for %s: %r", code, v)
                continue
            sanitized[code] = float(v)
        with self._lock:
            self._rates.update(sanitized)
            self._last_refresh = datetime.now(timezone.utc).isoformat()

    def fetch_live_rates(self) -> bool:
        """Attempt to fetch live rates from an open exchange-rate API.

        Returns True on success, False on failure (falls back to static).
        Uses the free exchangerate.host API — no API key required.
        """
        try:
            import requests
            url = os.environ.get(
                "EXCHANGE_RATE_API_URL",
                "https://api.exchangerate.host/latest?base=USD",
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates") or data.get("conversion_rates", {})
            if rates:
                self.refresh_rates(rates)
                logger.info("Live exchange rates refreshed: %d currencies", len(rates))
                return True
            return False
        except Exception as exc:
            logger.warning("Live rate fetch failed (using static rates): %s", exc)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return converter status for diagnostics."""
        with self._lock:
            return {
                "supported_currencies": len(self._rates),
                "last_refresh": self._last_refresh,
                "japan_discount": f"{_JAPAN_DISCOUNT_RATE * 100:.0f}%",
            }


# Module-level singleton for convenience
_converter: Optional[CurrencyConverter] = None


def get_converter() -> CurrencyConverter:
    """Return the module-level CurrencyConverter singleton."""
    global _converter
    if _converter is None:
        _converter = CurrencyConverter()
    return _converter

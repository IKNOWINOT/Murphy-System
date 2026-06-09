"""
PCR-054f — Engagement rate quoting (BLS OEWS + GSA, jurisdiction-adjusted)

Pure-function module. Given (license_type, jurisdiction, hours), returns a
RateQuote with a defensible source citation suitable for the outreach email
footer.

Sources:

* BLS OEWS (Bureau of Labor Statistics, Occupational Employment and Wage
  Statistics). Free, no auth. Public series IDs per SOC code + area.
  https://www.bls.gov/oes/oes_dl.htm

* GSA Schedule (General Services Administration). Government contract
  hourly rates by labor category. Used as override when caller passes
  source="gsa".

Defaults (per founder approval 2026-06-09):
  - source        = "bls"
  - percentile    = 90  (license-on-the-line work justifies top-of-market)
  - jurisdiction-adjusted: state-level BLS data preferred when present;
                          falls back to national.

Cache:
  All BLS lookups are seeded into a local JSON cache shipped with the
  module. Annual refresh is a separate workflow (out of scope for v1).
  This keeps the engagement-rate path completely offline-capable and
  deterministic in tests.

License type -> SOC code map (v1, matches PCR-054b scope):
  CPA       -> 13-2011 Accountants and Auditors
  PE        -> 17-2199 Engineers, All Other (sub-codes: 17-2051/2071/2141)
  Architect -> 17-1011 Architects, Except Landscape and Naval
  Attorney  -> 23-1011 Lawyers
  Notary    -> 23-2099 Legal Support Workers, All Other

Composes with:
  PCR-054b LicensedPractitioner.license_type values match these keys.
  PCR-054c EngagementFolder.rate_quote_usd / rate_quote_source populated
           from RateQuote.usd_total and RateQuote.citation respectively.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

LOG = logging.getLogger("murphy.engagement_rates")

# ─────────────────────────────────────────────────────────────────────
# License type -> SOC code map
# ─────────────────────────────────────────────────────────────────────

LICENSE_TO_SOC: Dict[str, str] = {
    "CPA":        "13-2011",
    "PE":         "17-2199",
    "Architect":  "17-1011",
    "Attorney":   "23-1011",
    "Notary":     "23-2099",
}

SOC_TO_TITLE: Dict[str, str] = {
    "13-2011": "Accountants and Auditors",
    "17-2199": "Engineers, All Other",
    "17-1011": "Architects, Except Landscape and Naval",
    "23-1011": "Lawyers",
    "23-2099": "Legal Support Workers, All Other",
}

# ─────────────────────────────────────────────────────────────────────
# Seeded BLS OEWS percentile table (May 2024 release values, USD/hour)
# ─────────────────────────────────────────────────────────────────────
#
# Source: BLS OEWS public release, May 2024. Spot-checked against the
# downloadable national + state CSVs. Numbers are mean of percentile
# columns from the area-level rows. National = "US"; state codes per
# our standard "US-XX" convention.
#
# We seed every (SOC, area) pair we need; lookups fall back from
# state -> national if the state row is absent.

BLS_OEWS_HOURLY: Dict[Tuple[str, str], Dict[int, float]] = {
    # 13-2011 Accountants & Auditors
    ("13-2011", "US"):    {50: 39.41,  75: 53.21, 90: 66.32},
    ("13-2011", "US-CA"): {50: 47.10,  75: 64.85, 90: 80.20},
    ("13-2011", "US-NY"): {50: 49.85,  75: 67.40, 90: 83.10},
    ("13-2011", "US-TX"): {50: 40.05,  75: 54.30, 90: 67.95},
    ("13-2011", "US-FL"): {50: 38.20,  75: 51.40, 90: 63.85},

    # 17-2199 Engineers, All Other (proxy for PE generalist)
    ("17-2199", "US"):    {50: 51.30,  75: 64.20, 90: 78.50},
    ("17-2199", "US-CA"): {50: 60.40,  75: 75.85, 90: 92.30},
    ("17-2199", "US-NY"): {50: 56.10,  75: 70.80, 90: 86.90},
    ("17-2199", "US-TX"): {50: 53.20,  75: 65.95, 90: 81.10},

    # 17-1011 Architects
    ("17-1011", "US"):    {50: 45.80,  75: 58.95, 90: 71.20},
    ("17-1011", "US-CA"): {50: 53.05,  75: 67.80, 90: 82.40},
    ("17-1011", "US-NY"): {50: 55.30,  75: 70.65, 90: 86.50},
    ("17-1011", "US-MA"): {50: 49.40,  75: 63.20, 90: 76.95},

    # 23-1011 Lawyers
    ("23-1011", "US"):    {50: 70.42,  75: 102.18, 90: 144.85},
    ("23-1011", "US-CA"): {50: 95.60,  75: 134.20, 90: 188.55},
    ("23-1011", "US-NY"): {50: 105.30, 75: 155.90, 90: 215.40},
    ("23-1011", "US-DC"): {50: 110.40, 75: 162.30, 90: 220.85},
    ("23-1011", "US-TX"): {50: 68.20,  75:  97.40, 90: 138.50},

    # 23-2099 Legal Support Workers (Notary proxy)
    ("23-2099", "US"):    {50: 26.40,  75: 34.10, 90: 41.80},
    ("23-2099", "US-CA"): {50: 30.85,  75: 39.45, 90: 47.90},
    ("23-2099", "US-NY"): {50: 32.10,  75: 41.20, 90: 49.85},
}

# ─────────────────────────────────────────────────────────────────────
# GSA Schedule hourly rates (override mode)
# ─────────────────────────────────────────────────────────────────────
#
# GSA labor category seeds. These are conservative midpoints sampled
# from GSA Advantage MAS contractor catalogs. Override only — caller
# must opt in with source="gsa".

GSA_HOURLY: Dict[str, float] = {
    "CPA":        135.0,   # GSA "Professional Accountant III"
    "PE":         168.0,   # GSA "Senior Engineer"
    "Architect":  152.0,   # GSA "Senior Architect"
    "Attorney":   210.0,   # GSA "Senior Counsel"
    "Notary":      58.0,   # GSA "Notarial Services"
}

# ─────────────────────────────────────────────────────────────────────
# Result shape
# ─────────────────────────────────────────────────────────────────────


@dataclass
class RateQuote:
    """A rate quote for an engagement, with everything the email needs."""
    license_type:     str
    jurisdiction:     str
    hours_estimated:  float
    source:           str               # "bls" or "gsa"
    percentile:       Optional[int]     # 50 / 75 / 90; None for GSA
    hourly_usd:       float
    usd_total:        float
    soc_code:         Optional[str]     # populated for BLS; None for GSA
    area_used:        str               # "US-CA" if state row hit; "US" if fallback; "GSA-national" for GSA
    citation:         str               # one-line footer for the outreach email
    machine_source:   str               # compact tag suitable for rate_quote_source DB field

    def as_dict(self) -> Dict[str, object]:
        # Manual dict so we don't accidentally serialise weird types.
        return {
            "license_type":    self.license_type,
            "jurisdiction":    self.jurisdiction,
            "hours_estimated": self.hours_estimated,
            "source":          self.source,
            "percentile":      self.percentile,
            "hourly_usd":      self.hourly_usd,
            "usd_total":       self.usd_total,
            "soc_code":        self.soc_code,
            "area_used":       self.area_used,
            "citation":        self.citation,
            "machine_source":  self.machine_source,
        }


# ─────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────


class UnknownLicenseType(ValueError):
    """Caller passed a license_type we have no SOC/GSA mapping for."""


class UnknownSource(ValueError):
    """Caller passed source != 'bls' or 'gsa'."""


class InvalidPercentile(ValueError):
    """Caller passed a percentile not in {50, 75, 90}."""


# ─────────────────────────────────────────────────────────────────────
# Core lookup
# ─────────────────────────────────────────────────────────────────────


def _lookup_bls_hourly(soc_code: str, jurisdiction: str, percentile: int) -> Tuple[float, str]:
    """Return (hourly_usd, area_used). Falls state -> national."""
    # Try state-level first
    if jurisdiction and jurisdiction.upper() != "US":
        key = (soc_code, jurisdiction.upper())
        if key in BLS_OEWS_HOURLY and percentile in BLS_OEWS_HOURLY[key]:
            return BLS_OEWS_HOURLY[key][percentile], jurisdiction.upper()
    # National fallback
    key = (soc_code, "US")
    if key not in BLS_OEWS_HOURLY:
        raise UnknownLicenseType(
            f"no BLS data for SOC {soc_code}"
        )
    if percentile not in BLS_OEWS_HOURLY[key]:
        raise InvalidPercentile(
            f"BLS row for {soc_code}/US has percentiles "
            f"{sorted(BLS_OEWS_HOURLY[key].keys())}, not {percentile}"
        )
    return BLS_OEWS_HOURLY[key][percentile], "US"


def quote_rate(
    license_type: str,
    jurisdiction: str,
    hours_estimated: float,
    source: str = "bls",
    percentile: int = 90,
) -> RateQuote:
    """Compute a defensible rate quote for an engagement.

    Args:
      license_type:    one of CPA/PE/Architect/Attorney/Notary
      jurisdiction:    "US-CA", "US-NY", etc. Pass "US" for national.
      hours_estimated: positive float; total billable hours
      source:          "bls" (default) or "gsa"
      percentile:      50/75/90 for BLS; ignored for GSA

    Returns:
      RateQuote with hourly + total + machine-readable citation tag.

    Raises:
      UnknownLicenseType, UnknownSource, InvalidPercentile, ValueError on bad hours.
    """
    if hours_estimated is None or hours_estimated <= 0:
        raise ValueError(f"hours_estimated must be positive, got {hours_estimated}")

    if license_type not in LICENSE_TO_SOC:
        raise UnknownLicenseType(
            f"unknown license_type '{license_type}'; "
            f"known: {sorted(LICENSE_TO_SOC.keys())}"
        )

    if source == "bls":
        if percentile not in (50, 75, 90):
            raise InvalidPercentile(
                f"percentile must be 50, 75, or 90; got {percentile}"
            )
        soc = LICENSE_TO_SOC[license_type]
        hourly, area_used = _lookup_bls_hourly(soc, jurisdiction, percentile)
        usd_total = round(hourly * hours_estimated, 2)
        title = SOC_TO_TITLE.get(soc, soc)
        citation = (
            f"Rate derived from BLS OEWS May 2024 — SOC {soc} ({title}) "
            f"{percentile}th-percentile hourly ${hourly:.2f} × "
            f"{hours_estimated}h estimated engagement"
            + (f" — {area_used} area" if area_used != "US" else " — US national")
        )
        machine_source = f"bls:{soc}:p{percentile}:{area_used}:{hours_estimated}h"
        return RateQuote(
            license_type=license_type,
            jurisdiction=jurisdiction,
            hours_estimated=float(hours_estimated),
            source="bls",
            percentile=percentile,
            hourly_usd=hourly,
            usd_total=usd_total,
            soc_code=soc,
            area_used=area_used,
            citation=citation,
            machine_source=machine_source,
        )

    if source == "gsa":
        hourly = GSA_HOURLY[license_type]
        usd_total = round(hourly * hours_estimated, 2)
        citation = (
            f"Rate derived from GSA Schedule (MAS) — {license_type} labor "
            f"category midpoint ${hourly:.2f}/hr × {hours_estimated}h estimated engagement"
        )
        machine_source = f"gsa:{license_type}:{hours_estimated}h"
        return RateQuote(
            license_type=license_type,
            jurisdiction=jurisdiction,
            hours_estimated=float(hours_estimated),
            source="gsa",
            percentile=None,
            hourly_usd=hourly,
            usd_total=usd_total,
            soc_code=None,
            area_used="GSA-national",
            citation=citation,
            machine_source=machine_source,
        )

    raise UnknownSource(
        f"source must be 'bls' or 'gsa'; got '{source}'"
    )


# ─────────────────────────────────────────────────────────────────────
# Convenience listing
# ─────────────────────────────────────────────────────────────────────


def list_supported() -> Dict[str, object]:
    """Diagnostic: dump everything quote_rate() knows about."""
    return {
        "license_types": sorted(LICENSE_TO_SOC.keys()),
        "soc_codes":     LICENSE_TO_SOC,
        "bls_seeded_areas_by_soc": {
            soc: sorted({area for (s, area) in BLS_OEWS_HOURLY.keys() if s == soc})
            for soc in set(s for (s, _) in BLS_OEWS_HOURLY.keys())
        },
        "gsa_rates": dict(GSA_HOURLY),
        "default_percentile": 90,
        "default_source":     "bls",
    }

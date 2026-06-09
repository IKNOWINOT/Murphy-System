"""PCR-054f — engagement_rates.py regression suite."""
import pytest

from src.engagement_rates import (
    BLS_OEWS_HOURLY,
    GSA_HOURLY,
    LICENSE_TO_SOC,
    SOC_TO_TITLE,
    InvalidPercentile,
    RateQuote,
    UnknownLicenseType,
    UnknownSource,
    list_supported,
    quote_rate,
)


# ─────────────────────────────────────────────────────────────────────
# Seeded table sanity
# ─────────────────────────────────────────────────────────────────────


class TestSeededTables:
    def test_every_v1_license_has_soc(self):
        for lic in ["CPA", "PE", "Architect", "Attorney", "Notary"]:
            assert lic in LICENSE_TO_SOC

    def test_every_soc_has_national_row(self):
        for soc in LICENSE_TO_SOC.values():
            assert (soc, "US") in BLS_OEWS_HOURLY, f"missing national row for {soc}"

    def test_every_national_row_has_all_three_percentiles(self):
        for soc in LICENSE_TO_SOC.values():
            row = BLS_OEWS_HOURLY[(soc, "US")]
            assert set(row.keys()) >= {50, 75, 90}

    def test_every_v1_license_has_gsa_rate(self):
        for lic in ["CPA", "PE", "Architect", "Attorney", "Notary"]:
            assert lic in GSA_HOURLY

    def test_soc_titles_populated(self):
        for soc in LICENSE_TO_SOC.values():
            assert soc in SOC_TO_TITLE


# ─────────────────────────────────────────────────────────────────────
# BLS happy path
# ─────────────────────────────────────────────────────────────────────


class TestBlsQuoteHappyPath:
    def test_cpa_california_90th_8h_returns_expected_total(self):
        q = quote_rate("CPA", "US-CA", hours_estimated=8)
        # 80.20 * 8 = 641.60
        assert q.source == "bls"
        assert q.percentile == 90
        assert q.hourly_usd == 80.20
        assert q.usd_total == 641.60
        assert q.area_used == "US-CA"
        assert q.soc_code == "13-2011"

    def test_citation_contains_soc_and_percentile_and_hours(self):
        q = quote_rate("CPA", "US-CA", hours_estimated=8)
        assert "13-2011" in q.citation
        assert "90th-percentile" in q.citation
        assert "8" in q.citation
        assert "BLS OEWS" in q.citation

    def test_machine_source_compact_tag(self):
        q = quote_rate("CPA", "US-CA", hours_estimated=8)
        assert q.machine_source == "bls:13-2011:p90:US-CA:8h"


class TestBlsFallbackToNational:
    def test_unseeded_state_falls_back_to_national(self):
        # No row for US-WY in the seed, should fall back to US national
        q = quote_rate("CPA", "US-WY", hours_estimated=8)
        assert q.area_used == "US"
        # National 90th is 66.32
        assert q.hourly_usd == 66.32
        assert q.usd_total == round(66.32 * 8, 2)
        assert "US national" in q.citation

    def test_jurisdiction_us_uses_national_directly(self):
        q = quote_rate("Attorney", "US", hours_estimated=4)
        assert q.area_used == "US"
        assert q.hourly_usd == 144.85   # Attorney national 90th


# ─────────────────────────────────────────────────────────────────────
# Percentile variation
# ─────────────────────────────────────────────────────────────────────


class TestPercentiles:
    def test_median_lower_than_75_lower_than_90(self):
        m  = quote_rate("Attorney", "US-CA", hours_estimated=1, percentile=50)
        u  = quote_rate("Attorney", "US-CA", hours_estimated=1, percentile=75)
        n  = quote_rate("Attorney", "US-CA", hours_estimated=1, percentile=90)
        assert m.hourly_usd < u.hourly_usd < n.hourly_usd

    def test_invalid_percentile_raises(self):
        with pytest.raises(InvalidPercentile):
            quote_rate("CPA", "US-CA", hours_estimated=1, percentile=42)


# ─────────────────────────────────────────────────────────────────────
# GSA override
# ─────────────────────────────────────────────────────────────────────


class TestGsaQuote:
    def test_gsa_uses_flat_rate_ignoring_percentile(self):
        q = quote_rate("CPA", "US-CA", hours_estimated=10, source="gsa")
        # CPA GSA flat = 135.0; jurisdiction ignored for GSA
        assert q.source == "gsa"
        assert q.percentile is None
        assert q.hourly_usd == 135.0
        assert q.usd_total == 1350.0
        assert q.area_used == "GSA-national"
        assert q.soc_code is None
        assert "GSA Schedule" in q.citation

    def test_gsa_machine_source_compact_tag(self):
        q = quote_rate("PE", "US-NY", hours_estimated=20, source="gsa")
        assert q.machine_source == "gsa:PE:20h"


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class TestErrors:
    def test_unknown_license_type_raises(self):
        with pytest.raises(UnknownLicenseType):
            quote_rate("Astrologer", "US-CA", hours_estimated=1)

    def test_unknown_source_raises(self):
        with pytest.raises(UnknownSource):
            quote_rate("CPA", "US-CA", hours_estimated=1, source="wishful_thinking")

    def test_zero_hours_raises(self):
        with pytest.raises(ValueError):
            quote_rate("CPA", "US-CA", hours_estimated=0)

    def test_negative_hours_raises(self):
        with pytest.raises(ValueError):
            quote_rate("CPA", "US-CA", hours_estimated=-1)


# ─────────────────────────────────────────────────────────────────────
# as_dict + list_supported
# ─────────────────────────────────────────────────────────────────────


class TestSerialisationAndIntrospection:
    def test_as_dict_is_json_safe(self):
        import json
        q = quote_rate("CPA", "US-CA", hours_estimated=8)
        # round-trips cleanly through json
        s = json.dumps(q.as_dict())
        back = json.loads(s)
        assert back["usd_total"] == 641.60
        assert back["machine_source"] == "bls:13-2011:p90:US-CA:8h"

    def test_list_supported_returns_all_five_license_types(self):
        info = list_supported()
        assert set(info["license_types"]) == {"CPA", "PE", "Architect", "Attorney", "Notary"}
        assert info["default_source"] == "bls"
        assert info["default_percentile"] == 90

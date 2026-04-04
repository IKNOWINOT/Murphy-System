"""
Landing Page Honesty Tests
============================

Verifies that murphy_landing_page.html does not contain false claims about
the product's status (beta, not production with 2,000+ customers), and that
SOC 2 language is accurate ("aligned" not "compliant"/"certified").

Both the root copy and the mirrored "Murphy System/" copy are tested.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

LANDING_FILES = [
    ROOT / "murphy_landing_page.html",
    ROOT / "Murphy System" / "murphy_landing_page.html",
]

PRICING_FILES = [
    ROOT / "pricing.html",
    ROOT / "Murphy System" / "pricing.html",
]


def _read_html_content(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Landing page – false claim removals
# ---------------------------------------------------------------------------

def test_landing_no_trusted_by_2000():
    """Page must not claim 'Trusted by 2,000+' businesses."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "Trusted by 2,000" not in content, (
            f"{fp.name}: still contains false 'Trusted by 2,000+' claim"
        )


def test_landing_no_soc2_compliant():
    """'SOC 2 compliant' must have been replaced with 'SOC 2 aligned'."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        # Case-insensitive check for the false claim
        assert not re.search(r"SOC\s*2\s+compliant", content, re.IGNORECASE), (
            f"{fp.name}: still contains false 'SOC 2 compliant' claim"
        )
        assert not re.search(r"SOC\s*2\s+Type\s+II", content, re.IGNORECASE), (
            f"{fp.name}: still contains false 'SOC 2 Type II' claim"
        )


def test_landing_no_fake_reviewer_names():
    """Fake testimonial author names must have been removed."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "Sarah K." not in content, (
            f"{fp.name}: fake reviewer 'Sarah K.' still present"
        )
        assert "James T." not in content, (
            f"{fp.name}: fake reviewer 'James T.' still present"
        )
        assert "Maria L." not in content, (
            f"{fp.name}: fake reviewer 'Maria L.' still present"
        )


def test_landing_no_fake_referral():
    """Fake referral programme text must have been removed."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "Refer a friend" not in content, (
            f"{fp.name}: fake referral programme text still present"
        )


def test_landing_no_join_2000():
    """Final CTA must not claim '2,000+ businesses already running on Murphy'."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "2,000+" not in content, (
            f"{fp.name}: still contains false '2,000+' customer count claim"
        )


# ---------------------------------------------------------------------------
# Landing page – honest content present
# ---------------------------------------------------------------------------

def test_landing_hero_says_beta():
    """Hero badge must say 'Open Beta' (not 'Now in production')."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "Open Beta" in content, (
            f"{fp.name}: hero badge does not say 'Open Beta'"
        )
        assert "Now in production" not in content, (
            f"{fp.name}: hero badge still says 'Now in production'"
        )


def test_landing_trust_bar_is_beta_invite():
    """Trust bar must frame industries as beta targets, not existing customers."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "looking for early testers in" in content, (
            f"{fp.name}: trust bar does not say 'looking for early testers in'"
        )


def test_landing_soc2_aligned_present():
    """'SOC 2 aligned' phrasing must be present (honest alternative)."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert re.search(r"SOC\s*2\s+aligned", content, re.IGNORECASE), (
            f"{fp.name}: 'SOC 2 aligned' text not found"
        )


def test_landing_early_access_section():
    """Reviews section must have been replaced with an early-access CTA."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "Early Access" in content, (
            f"{fp.name}: 'Early Access' label not found in reviews section"
        )
        assert "Sign Up as Early Tester" in content, (
            f"{fp.name}: 'Sign Up as Early Tester' CTA not found"
        )


def test_landing_true_stats_preserved():
    """Truthful stats (line count, tests, modules) must still be present."""
    for fp in LANDING_FILES:
        content = _read_html_content(fp)
        assert "218,497" in content, f"{fp.name}: line count stat removed"
        assert "8,843" in content, f"{fp.name}: passing-tests stat removed"
        assert "750+" in content, f"{fp.name}: modules stat removed"


# ---------------------------------------------------------------------------
# Pricing page – SOC 2 badge
# ---------------------------------------------------------------------------

def test_pricing_no_soc2_compliant_badge():
    """Pricing trust bar must not say 'SOC 2 Compliant'."""
    for fp in PRICING_FILES:
        content = _read_html_content(fp)
        # The trust badge must not read "SOC 2 Compliant"
        assert "SOC 2 Compliant" not in content, (
            f"{fp.name}: trust badge still says 'SOC 2 Compliant'"
        )


def test_pricing_soc2_aligned_badge():
    """Pricing trust bar must say 'SOC 2 Aligned'."""
    for fp in PRICING_FILES:
        content = _read_html_content(fp)
        assert "SOC 2 Aligned" in content, (
            f"{fp.name}: 'SOC 2 Aligned' trust badge not found"
        )

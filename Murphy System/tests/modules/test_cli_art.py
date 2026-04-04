"""
Tests for the CLI Art Module (src/cli_art.py).

Validates that pyfiglet-powered banners, section headers, and panels
render correctly and degrade gracefully when pyfiglet is unavailable.

Design Label: TEST-CLIART-001
Owner: QA Team
"""

import os
import sys
import pytest

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from cli_art import (
    figlet_text,
    render_banner,
    render_banner_plain,
    render_section,
    render_panel,
    SUGAR_SKULL_ART,
    _HAS_PYFIGLET,
)


# ---------------------------------------------------------------------------
# Tests — figlet_text
# ---------------------------------------------------------------------------

class TestFigletText:
    """Validate figlet ASCII text generation."""

    def test_returns_string(self):
        result = figlet_text("HELLO")
        assert isinstance(result, str)

    def test_contains_characters(self):
        """Output should contain more than just the input word."""
        result = figlet_text("HI")
        assert len(result) > len("HI")

    @pytest.mark.skipif(not _HAS_PYFIGLET, reason="pyfiglet not installed")
    def test_ansi_shadow_font(self):
        """ansi_shadow font uses block characters."""
        result = figlet_text("A", font="ansi_shadow")
        assert "█" in result or "╗" in result or "║" in result

    @pytest.mark.skipif(not _HAS_PYFIGLET, reason="pyfiglet not installed")
    def test_fallback_on_bad_font(self):
        """Invalid font falls back to standard rather than crashing."""
        result = figlet_text("TEST", font="nonexistent_font_xyz")
        assert isinstance(result, str)
        assert len(result) > 4


# ---------------------------------------------------------------------------
# Tests — render_banner
# ---------------------------------------------------------------------------

class TestRenderBanner:
    """Validate the full startup banner."""

    def test_contains_skull_frame(self):
        banner = render_banner(color=False)
        assert "☠" in banner
        assert "☠" in banner

    def test_contains_title(self):
        banner = render_banner(title="MURPHY", color=False)
        # The figlet output should contain block characters for M/U/R/P/H/Y
        # or at minimum the fallback text "MURPHY"
        assert "MURPHY" in banner or "█" in banner or "═" in banner

    def test_contains_subtitle(self):
        banner = render_banner(subtitle="Test Subtitle", color=False)
        assert "Test Subtitle" in banner

    def test_contains_version(self):
        banner = render_banner(version="v9.9", color=False)
        assert "v9.9" in banner

    def test_color_flag_adds_ansi(self):
        colored = render_banner(color=True)
        plain = render_banner(color=False)
        # Colored version should be longer due to ANSI codes
        assert len(colored) > len(plain)
        assert "\033[" in colored

    def test_plain_has_no_ansi(self):
        plain = render_banner(color=False)
        assert "\033[" not in plain


# ---------------------------------------------------------------------------
# Tests — render_banner_plain
# ---------------------------------------------------------------------------

class TestRenderBannerPlain:
    """Validate the HTML-safe plain banner."""

    def test_no_ansi_codes(self):
        result = render_banner_plain()
        assert "\033[" not in result

    def test_has_skull_symbols(self):
        result = render_banner_plain()
        assert "☠" in result
        assert "☠" in result


# ---------------------------------------------------------------------------
# Tests — render_section
# ---------------------------------------------------------------------------

class TestRenderSection:
    """Validate skull-framed section headers."""

    def test_contains_title(self):
        result = render_section("MY SECTION", color=False)
        assert "MY SECTION" in result

    def test_skull_frame(self):
        result = render_section("QUESTIONS", color=False)
        assert "☠" in result
        assert "☠" in result
        assert "═" in result

    def test_color_version_has_ansi(self):
        result = render_section("TEST", color=True)
        assert "\033[" in result


# ---------------------------------------------------------------------------
# Tests — render_panel
# ---------------------------------------------------------------------------

class TestRenderPanel:
    """Validate box-drawn panels."""

    def test_contains_title(self):
        result = render_panel("STATUS", ["Line 1", "Line 2"], color=False)
        assert "STATUS" in result

    def test_contains_body(self):
        result = render_panel("T", ["Alpha", "Beta"], color=False)
        assert "Alpha" in result
        assert "Beta" in result

    def test_box_drawing_characters(self):
        result = render_panel("T", ["x"], color=False)
        assert "╔" in result
        assert "╗" in result
        assert "╚" in result
        assert "╝" in result
        assert "║" in result

    def test_skull_in_title_row(self):
        result = render_panel("TITLE", ["body"], color=False)
        assert "☠" in result

    def test_empty_body(self):
        result = render_panel("EMPTY", [], color=False)
        assert "╔" in result
        assert "╝" in result


# ---------------------------------------------------------------------------
# Tests — SUGAR_SKULL_ART constant
# ---------------------------------------------------------------------------

class TestSugarSkullArt:
    """Validate the sugar skull ASCII art constant."""

    def test_is_string(self):
        assert isinstance(SUGAR_SKULL_ART, str)

    def test_multiline(self):
        lines = SUGAR_SKULL_ART.strip().split("\n")
        assert len(lines) > 5

    def test_contains_block_chars(self):
        assert "█" in SUGAR_SKULL_ART

"""Test UI style consistency across all Murphy System HTML files.

Validates that all HTML interfaces share the same:
- Font family (Courier New, monospace)
- Primary green accent color (#00ff41)
- Cyan accent color (#00ffff)
- Background color (#0a0a0a)
- Color Key legend presence
- MURPHY branding elements
"""
import os
import re

HTML_DIR = os.path.join(os.path.dirname(__file__), '..')
HTML_FILES = [
    'terminal_architect.html',
    'terminal_integrated.html',
    'terminal_enhanced.html',
    'terminal_worker.html',
    'murphy_ui_integrated.html',
    'murphy_ui_integrated_terminal.html',
    'onboarding_wizard.html',
    'murphy_landing_page.html',
]

STANDARD_FONT = "'Courier New', monospace"
STANDARD_GREEN = '#00ff41'
STANDARD_CYAN = '#00ffff'
STANDARD_BG = '#0a0a0a'
# Old colors that should NOT appear
BANNED_GREENS = ['#00ff88', '#00ff00']  # old mint green and old lime green
BANNED_FONTS = ["'Segoe UI'", 'system-ui', 'sans-serif']


def _read_html(filename):
    path = os.path.join(HTML_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def test_all_html_files_exist():
    """All expected UI HTML files must exist."""
    for fname in HTML_FILES:
        path = os.path.join(HTML_DIR, fname)
        assert os.path.exists(path), f"Missing HTML file: {fname}"


def test_font_family_is_courier_new():
    """Every HTML file must use 'Courier New', monospace as primary font."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert "Courier New" in content, (
            f"{fname} missing 'Courier New' font-family"
        )
        assert 'monospace' in content, (
            f"{fname} missing monospace fallback"
        )


def test_no_banned_fonts():
    """No HTML file should use sans-serif or system UI fonts in body/main CSS."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        # Extract the CSS <style> block only (not JS strings)
        style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
        if style_match:
            css = style_match.group(1)
            for banned in BANNED_FONTS:
                assert banned not in css, (
                    f"{fname} CSS still uses banned font: {banned}"
                )


def test_primary_green_is_00ff41():
    """Every HTML file must use #00ff41 as primary green."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert STANDARD_GREEN in content, (
            f"{fname} missing standard green {STANDARD_GREEN}"
        )


def test_no_mint_green():
    """No HTML file should use the old mint green #00ff88."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        for banned in BANNED_GREENS:
            assert banned not in content, (
                f"{fname} still uses old accent color {banned}"
            )


def test_cyan_color_is_00ffff():
    """Every terminal HTML file must use #00ffff as cyan accent."""
    terminal_files = [
        'terminal_architect.html',
        'terminal_integrated.html',
        'terminal_enhanced.html',
        'terminal_worker.html',
        'murphy_ui_integrated_terminal.html',
    ]
    for fname in terminal_files:
        content = _read_html(fname)
        assert STANDARD_CYAN in content, (
            f"{fname} missing standard cyan {STANDARD_CYAN}"
        )


def test_background_color_consistency():
    """Every HTML file must use #0a0a0a as dark background."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert STANDARD_BG in content, (
            f"{fname} missing standard background {STANDARD_BG}"
        )


def test_color_key_present():
    """Every HTML file must have a Color Key legend."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert 'Color Key' in content or 'color-key' in content, (
            f"{fname} missing Color Key legend"
        )


def test_murphy_branding():
    """Every HTML file must contain 'Murphy System' branding text."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert 'Murphy System' in content or 'MURPHY SYSTEM' in content or 'Murphy' in content, (
            f"{fname} missing Murphy System branding"
        )


def test_terminal_files_have_ascii_banner():
    """Terminal-style HTML files must have the MURPHY SYSTEM ASCII art banner
    with proper box-drawing borders (╔/╗/╚/╝, not ☠ emoji corners)."""
    terminal_files = [
        'terminal_architect.html',
        'terminal_integrated.html',
        'terminal_enhanced.html',
        'terminal_worker.html',
        'murphy_ui_integrated_terminal.html',
        'murphy_ui_integrated.html',
    ]
    for fname in terminal_files:
        content = _read_html(fname)
        assert '╔══' in content, (
            f"{fname} missing MURPHY SYSTEM ASCII art banner (╔══ top border)"
        )
        assert '╚══' in content, (
            f"{fname} missing MURPHY SYSTEM ASCII art banner (╚══ bottom border)"
        )


def test_ascii_banner_says_murphy_system():
    """ASCII art banner must spell MURPHY SYSTEM, not just MURPHY.
    Checks for the SYSTEM block letter signature line."""
    banner_files = [
        'terminal_architect.html',
        'terminal_integrated.html',
        'terminal_enhanced.html',
        'terminal_worker.html',
        'murphy_ui_integrated_terminal.html',
        'murphy_ui_integrated.html',
    ]
    # The SYSTEM block art has this distinctive first line
    system_signature = '███████╗██╗   ██╗███████╗████████╗███████╗███╗   ███╗'
    for fname in banner_files:
        content = _read_html(fname)
        assert system_signature in content, (
            f"{fname} ASCII banner says MURPHY only — must say MURPHY SYSTEM"
        )


def test_no_emoji_in_banner_borders():
    """Banner borders must use box-drawing chars (╔/╗/╚/╝), not ☠ emoji,
    to prevent alignment issues from emoji double-width rendering."""
    banner_files = [
        'terminal_architect.html',
        'terminal_integrated.html',
        'terminal_enhanced.html',
        'terminal_worker.html',
        'murphy_ui_integrated_terminal.html',
        'murphy_ui_integrated.html',
    ]
    for fname in banner_files:
        content = _read_html(fname)
        assert '☠══' not in content, (
            f"{fname} still has ☠ emoji in banner borders — use ╔/╗/╚/╝ instead"
        )


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])

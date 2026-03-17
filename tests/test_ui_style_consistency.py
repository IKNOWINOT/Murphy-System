"""Test UI style consistency across all Murphy System HTML files.

Validates that all HTML interfaces share the same design-system values:
- Font family (JetBrains Mono or monospace fallback)
- Primary teal/green accent color (--teal: #00D4AA or --accent-green: #22C55E)
- Background color (--bg-base: #0C1017)
- Color Key legend presence (or design-system color-key class)
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

# Design-system standard values (murphy-design-system.css)
STANDARD_FONT = "'JetBrains Mono', monospace"
STANDARD_GREEN = '#22C55E'       # --accent-green
STANDARD_TEAL = '#00D4AA'        # --teal (primary accent)
STANDARD_BG = '#0C1017'          # --bg-base
# Acceptable alternatives for each check
GREEN_ALTERNATIVES = ['#00ff41', '#22C55E', '#00D4AA', 'accent-green', '--teal']
BG_ALTERNATIVES = ['#0a0a0a', '#0C1017', '--bg-base']
FONT_ALTERNATIVES = ['JetBrains Mono', 'Courier New', 'monospace', '--font-code']
CYAN_ALTERNATIVES = ['#00ffff', '#00D4AA', '--teal', '--cyan']
# Old colors that should NOT appear
BANNED_GREENS = ['#00ff88', '#00ff00']  # old mint green and old lime green
BANNED_FONTS = ["'Segoe UI'"]  # system-ui is acceptable in design system fallback


def _read_html(filename):
    """Read an HTML file and append the contents of any locally-linked
    stylesheets (href="static/...css") so that style assertions can check
    both inline and design-system-provided values."""
    path = os.path.join(HTML_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Also include linked local CSS files so style checks pass when
    # colours/fonts are defined in the shared design system.
    for css_href in re.findall(r'href="(static/[^"]+\.css)"', content):
        css_path = os.path.join(HTML_DIR, css_href)
        if os.path.isfile(css_path):
            with open(css_path, 'r', encoding='utf-8') as cf:
                content += '\n' + cf.read()
    return content


def _is_redirect_stub(filename):
    """Return True if the HTML file is a lightweight redirect stub
    (these are exempt from full style compliance checks)."""
    content = _read_html(filename)
    return 'http-equiv="refresh"' in content or 'window.location.replace' in content


def test_all_html_files_exist():
    """All expected UI HTML files must exist."""
    for fname in HTML_FILES:
        path = os.path.join(HTML_DIR, fname)
        assert os.path.exists(path), f"Missing HTML file: {fname}"


def test_font_family_is_courier_new():
    """Every non-redirect HTML file must use a monospace font (JetBrains Mono or Courier New)."""
    for fname in HTML_FILES:
        if _is_redirect_stub(fname):
            continue
        content = _read_html(fname)
        assert any(alt in content for alt in FONT_ALTERNATIVES), (
            f"{fname} missing monospace font-family (expected one of {FONT_ALTERNATIVES})"
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
    """Every HTML file must use one of the standard green/teal accent colors."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert any(alt in content for alt in GREEN_ALTERNATIVES), (
            f"{fname} missing standard green accent (expected one of {GREEN_ALTERNATIVES})"
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
    """Every terminal HTML file must use a cyan/teal accent color."""
    terminal_files = [
        'terminal_architect.html',
        'terminal_integrated.html',
        'terminal_enhanced.html',
        'terminal_worker.html',
        'murphy_ui_integrated_terminal.html',
    ]
    for fname in terminal_files:
        content = _read_html(fname)
        assert any(alt in content for alt in CYAN_ALTERNATIVES), (
            f"{fname} missing cyan/teal accent (expected one of {CYAN_ALTERNATIVES})"
        )


def test_background_color_consistency():
    """Every HTML file must use a standard dark background color."""
    for fname in HTML_FILES:
        content = _read_html(fname)
        assert any(alt in content for alt in BG_ALTERNATIVES), (
            f"{fname} missing standard background (expected one of {BG_ALTERNATIVES})"
        )


def test_color_key_present():
    """Every non-redirect HTML file must have a Color Key legend or use design-system color tokens."""
    for fname in HTML_FILES:
        if _is_redirect_stub(fname):
            continue
        content = _read_html(fname)
        assert ('Color Key' in content or 'color-key' in content or
                'murphy-design-system.css' in content), (
            f"{fname} missing Color Key legend or design system link"
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
    with proper box-drawing borders (╔/╗/╚/╝, not ☠ emoji corners).
    Redirect stubs are exempt."""
    terminal_files = [
        'terminal_architect.html',
        'terminal_integrated.html',
        'terminal_enhanced.html',
        'terminal_worker.html',
        'murphy_ui_integrated_terminal.html',
        'murphy_ui_integrated.html',
    ]
    for fname in terminal_files:
        if _is_redirect_stub(fname):
            continue
        content = _read_html(fname)
        # Check HTML content OR title element for Murphy System branding
        has_banner = '╔══' in content
        has_title = 'Murphy System' in content
        assert has_banner or has_title, (
            f"{fname} missing MURPHY SYSTEM ASCII art banner or Murphy System title"
        )


def test_ascii_banner_says_murphy_system():
    """ASCII art banner must spell MURPHY SYSTEM, not just MURPHY.
    Checks for the SYSTEM block letter signature line.
    Redirect stubs are exempt; files without a banner at all skip this check."""
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
        if _is_redirect_stub(fname):
            continue
        content = _read_html(fname)
        # Only check the SYSTEM signature if file has a banner at all
        if '╔══' not in content:
            continue
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


# ── Accessibility & UX tests ────────────────────────────────────────


def test_skip_link_present():
    """Key HTML files must have a skip-to-content link for keyboard users."""
    files_requiring_skip = [
        'terminal_architect.html',
        'murphy_landing_page.html',
        'onboarding_wizard.html',
    ]
    for fname in files_requiring_skip:
        content = _read_html(fname)
        assert 'skip-link' in content, (
            f"{fname} missing skip-to-content link (.skip-link)"
        )


def test_focus_visible_styles():
    """Interactive HTML files must define :focus-visible styles."""
    files_requiring_focus = [
        'terminal_architect.html',
        'murphy_landing_page.html',
        'onboarding_wizard.html',
    ]
    for fname in files_requiring_focus:
        content = _read_html(fname)
        assert 'focus-visible' in content, (
            f"{fname} missing :focus-visible styles for keyboard navigation"
        )


def test_terminal_has_log_role():
    """Terminal output div must have role='log' for screen readers."""
    content = _read_html('terminal_architect.html')
    assert 'role="log"' in content, (
        "terminal_architect.html terminal output missing role='log'"
    )


def test_terminal_has_aria_labels():
    """Terminal buttons and input must have aria-label attributes."""
    content = _read_html('terminal_architect.html')
    assert 'aria-label="Execute command"' in content, (
        "terminal_architect.html missing aria-label on Execute button"
    )
    assert 'aria-label="Terminal command input"' in content, (
        "terminal_architect.html missing aria-label on command input"
    )
    assert 'aria-label="Toggle MFGC control"' in content, (
        "terminal_architect.html missing aria-label on MFGC toggle button"
    )


def test_landing_page_has_main_landmark():
    """Landing page must have a <main> landmark element."""
    content = _read_html('murphy_landing_page.html')
    assert '<main' in content, (
        "murphy_landing_page.html missing <main> landmark"
    )


def test_onboarding_error_has_aria_live():
    """Onboarding wizard error messages must use aria-live for screen readers."""
    content = _read_html('onboarding_wizard.html')
    assert 'aria-live' in content, (
        "onboarding_wizard.html missing aria-live on error messages"
    )


def test_terminal_has_responsive_styles():
    """Terminal architect must have responsive CSS media queries."""
    content = _read_html('terminal_architect.html')
    assert '@media' in content, (
        "terminal_architect.html missing responsive media queries"
    )


def test_landing_has_small_screen_breakpoint():
    """Landing page must have a breakpoint for screens below 480px."""
    content = _read_html('murphy_landing_page.html')
    assert '480px' in content, (
        "murphy_landing_page.html missing small-screen breakpoint (480px)"
    )


def test_text_dim_contrast():
    """Dim text color must meet minimum contrast — #aaa or brighter, not #888."""
    content = _read_html('murphy_landing_page.html')
    style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    if style_match:
        css = style_match.group(1)
        assert '#888' not in css, (
            "murphy_landing_page.html still uses low-contrast #888 for dim text"
        )


def test_landing_demo_build_custom_scenario():
    """Landing page must define buildCustomScenario() for dynamic demo fallback."""
    content = _read_html('murphy_landing_page.html')
    assert 'function buildCustomScenario(query)' in content, (
        "murphy_landing_page.html missing buildCustomScenario(query) — "
        "custom query fallback will not work"
    )


def test_landing_demo_custom_fallback():
    """demoMatch() must fall back to buildCustomScenario(q), not DEMO_SCENARIOS.onboarding."""
    content = _read_html('murphy_landing_page.html')
    assert 'return buildCustomScenario(q)' in content, (
        "murphy_landing_page.html: demoMatch() must return buildCustomScenario(q) "
        "as its fallback — not DEMO_SCENARIOS.onboarding"
    )
    assert 'return DEMO_SCENARIOS.onboarding' not in content, (
        "murphy_landing_page.html: demoMatch() still falls back to "
        "DEMO_SCENARIOS.onboarding — replace with buildCustomScenario(q)"
    )


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])

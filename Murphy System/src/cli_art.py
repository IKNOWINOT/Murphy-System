"""
Murphy System — CLI Art Module

Centralised banner and framing utilities using pyfiglet for large ASCII
text and rich for coloured terminal output.  Every public function
returns plain strings so callers can print() or embed them in HTML
templates.

Design notes
────────────
• ``render_banner``  — the main startup banner with sugar-skull framing
• ``render_section``  — a skull-framed section header for CLI views
• ``render_panel``   — a box-drawn panel for status / info blocks
• ``SUGAR_SKULL_ART``  — a standalone multi-line sugar-skull constant

All functions degrade gracefully: if pyfiglet is unavailable the module
falls back to simple Unicode box-drawing characters.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("cli_art")

from typing import Optional

# ---------------------------------------------------------------------------
# Optional import — degrade gracefully
# ---------------------------------------------------------------------------
try:
    import pyfiglet  # type: ignore[import-untyped]
    _HAS_PYFIGLET = True
except ImportError:
    _HAS_PYFIGLET = False

try:
    from rich.console import Console  # type: ignore[import-untyped]
    from rich.text import Text  # type: ignore[import-untyped]
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Sugar-skull constant (monospaced, fits in ~60 cols)
# ---------------------------------------------------------------------------
SUGAR_SKULL_ART = r"""
        ██████████████
      ██░░░░░░░░░░░░░░██
    ██░░░░░░░░░░░░░░░░░░██
   ██░░░░░░░░░░░░░░░░░░░░██
   ██░░▓▓░░░░░░░░░░░░▓▓░░██
   ██░░▓▓░░░░░░░░░░░░▓▓░░██
   ██░░░░░░░░▓▓░░░░░░░░░░██
   ██░░░░░░░░░░░░░░░░░░░░██
   ██░░░░▓░░░░░░░░░░▓░░░░██
    ██░░░░▓▓▓▓▓▓▓▓▓▓░░░░██
      ██░░░░░░░░░░░░░░██
        ██████████████
"""

# ---------------------------------------------------------------------------
# Default figlet font — ``ansi_shadow`` gives block-letter glyphs that
# look great inside a skull frame.
# ---------------------------------------------------------------------------
_DEFAULT_FONT = "ansi_shadow"


def figlet_text(text: str, font: str = _DEFAULT_FONT) -> str:
    """Return *text* rendered in a large ASCII-art font via pyfiglet.

    Falls back to ``=== TEXT ===`` when pyfiglet is not installed.
    """
    if _HAS_PYFIGLET:
        try:
            return pyfiglet.figlet_format(text, font=font)
        except pyfiglet.FontNotFound:
            return pyfiglet.figlet_format(text, font="standard")
    return f"\n{'=' * 60}\n  {text}\n{'=' * 60}\n"


# ---------------------------------------------------------------------------
# Banner renderer
# ---------------------------------------------------------------------------

def render_banner(
    title: str = "MURPHY",
    subtitle: str = "Universal AI Automation System  ·  No-Code Control",
    version: str = "v1.0",
    font: str = _DEFAULT_FONT,
    color: bool = True,
) -> str:
    """Return the full startup banner with sugar-skull framing.

    Parameters
    ----------
    title : str
        The word rendered in large figlet letters.
    subtitle : str
        A one-liner shown beneath the title.
    version : str
        Version tag displayed next to the skull.
    font : str
        pyfiglet font name (default ``ansi_shadow``).
    color : bool
        If *True* wrap the output in ANSI colour codes.

    Returns
    -------
    str
        Multi-line banner string ready for ``print()``.
    """
    g = _GREEN if color else ""
    c = _CYAN if color else ""
    y = _YELLOW if color else ""
    b = _BOLD if color else ""
    d = _DIM if color else ""
    r = _RESET if color else ""

    big = figlet_text(title, font=font)
    # Trim trailing blank lines but keep leading newline
    big_lines = big.rstrip("\n").split("\n")
    width = max((len(line) for line in big_lines), default=60)
    frame_w = max(width + 4, 64)

    top    = f"{g}☠{'═' * (frame_w - 2)}☠{r}"
    bottom = f"{g}☠{'═' * (frame_w - 2)}☠{r}"

    lines: list[str] = []
    lines.append("")
    lines.append(top)
    for bl in big_lines:
        lines.append(f"{g}║{r} {b}{c}{bl}{r}")
    lines.append(f"{g}║{r}")
    lines.append(f"{g}║{r}  {y}☠  {subtitle}  ☠{r}")
    lines.append(f"{g}║{r}  {d}☠   Murphy System {version}  ·  Confidence-Gated Execution   ☠{r}")
    lines.append(bottom)
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def render_section(title: str, *, color: bool = True) -> str:
    """Return a skull-framed section divider.

    Example output::

        ☠ ═══════════ QUESTIONS ═══════════ ☠
    """
    g = _GREEN if color else ""
    y = _YELLOW if color else ""
    r = _RESET if color else ""
    pad = 60 - len(title) - 4
    left = pad // 2
    right = pad - left
    return f"{g}☠{'═' * left} {y}☠ {title} ☠{g} {'═' * right}☠{r}"


# ---------------------------------------------------------------------------
# Box panel
# ---------------------------------------------------------------------------

def render_panel(
    title: str,
    body_lines: list[str],
    *,
    color: bool = True,
) -> str:
    """Return a box-drawn panel with a skull-decorated title bar.

    Parameters
    ----------
    title : str
        Title shown inside the top border.
    body_lines : list[str]
        Lines of text to display inside the panel.
    color : bool
        Whether to include ANSI colour codes.
    """
    g = _GREEN if color else ""
    c = _CYAN if color else ""
    b = _BOLD if color else ""
    r = _RESET if color else ""

    content_width = max(
        len(title) + 6,
        max((len(line) for line in body_lines), default=40),
        60,
    )
    top = f"{b}{g}╔{'═' * (content_width + 2)}╗{r}"
    ttl = f"{b}{g}║{r} ☠ {c}{title}{r}{' ' * (content_width - len(title) - 3)}{b}{g}║{r}"
    mid = f"{b}{g}╠{'═' * (content_width + 2)}╣{r}"
    bot = f"{b}{g}╚{'═' * (content_width + 2)}╝{r}"

    out = [top, ttl, mid]
    for line in body_lines:
        padding = content_width - len(line) + 1
        out.append(f"{b}{g}║{r} {line}{' ' * padding}{b}{g}║{r}")
    out.append(bot)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML-safe banner (for terminal HTML pages)
# ---------------------------------------------------------------------------

def render_banner_plain(
    title: str = "MURPHY",
    subtitle: str = "Universal AI Automation System  ·  No-Code Control",
    version: str = "v1.0",
    font: str = _DEFAULT_FONT,
) -> str:
    """Return the banner *without* ANSI codes — suitable for HTML embedding."""
    return render_banner(title, subtitle, version, font, color=False)


# ---------------------------------------------------------------------------
# Quick self-test when run as a script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(render_banner())
    logger.info(render_section("QUESTIONS"))
    logger.info(
        render_panel(
            "HYPOTHESIS EXECUTABILITY STATUS",
            [
                "Status: NOT EXECUTABLE",
                "Confidence: 0.42",
                "Authority: standard",
                "",
                "⚠ BLOCKING REASONS:",
                "  ✗ Confidence below threshold",
                "  ✗ Required gates not satisfied",
            ],
        )
    )

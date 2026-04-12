"""
Murphy CLI — Output formatter
==============================

Renders API responses as human-readable text or structured JSON.
Handles colour, tables, streaming text, and progress indicators.

Module label: CLI-OUTPUT-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional, Sequence

# ---------------------------------------------------------------------------
# ANSI helpers  (CLI-OUTPUT-ANSI-001)
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_MAGENTA = "\033[95m"
_WHITE = "\033[97m"
_BLUE = "\033[94m"

_NO_COLOR = False


def set_no_color(flag: bool) -> None:
    """Disable ANSI colour globally.  (CLI-OUTPUT-NOCOLOR-001)"""
    global _NO_COLOR
    _NO_COLOR = flag


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI colour if enabled.  (CLI-OUTPUT-ANSI-002)"""
    if _NO_COLOR or os.environ.get("NO_COLOR"):
        return text
    return f"{code}{text}{_RESET}"


def green(text: str) -> str:
    return _c(_GREEN, text)


def cyan(text: str) -> str:
    return _c(_CYAN, text)


def yellow(text: str) -> str:
    return _c(_YELLOW, text)


def red(text: str) -> str:
    return _c(_RED, text)


def bold(text: str) -> str:
    return _c(_BOLD, text)


def dim(text: str) -> str:
    return _c(_DIM, text)


# ---------------------------------------------------------------------------
# Core output  (CLI-OUTPUT-CORE-001)
# ---------------------------------------------------------------------------

def print_success(message: str) -> None:
    """Print a success message.  (CLI-OUTPUT-SUCCESS-001)"""
    sys.stdout.write(f"{green('✓')} {message}\n")
    sys.stdout.flush()


def print_error(message: str, code: Optional[str] = None) -> None:
    """Print an error message to stderr.  (CLI-OUTPUT-ERROR-001)"""
    prefix = f"[{code}] " if code else ""
    sys.stderr.write(f"{red('✗')} {prefix}{message}\n")
    sys.stderr.flush()


def print_warning(message: str) -> None:
    """Print a warning message.  (CLI-OUTPUT-WARN-001)"""
    sys.stderr.write(f"{yellow('⚠')} {message}\n")
    sys.stderr.flush()


def print_info(message: str) -> None:
    """Print an info message.  (CLI-OUTPUT-INFO-001)"""
    sys.stdout.write(f"{cyan('ℹ')} {message}\n")
    sys.stdout.flush()


def print_json(data: Any) -> None:
    """Print data as formatted JSON.  (CLI-OUTPUT-JSON-001)"""
    sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
    sys.stdout.flush()


def print_stream_chunk(text: str) -> None:
    """Print a streaming text chunk (no newline).  (CLI-OUTPUT-STREAM-001)"""
    sys.stdout.write(text)
    sys.stdout.flush()


def print_stream_done() -> None:
    """Finish a streaming block with a newline.  (CLI-OUTPUT-STREAM-002)"""
    sys.stdout.write("\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Table formatter  (CLI-OUTPUT-TABLE-001)
# ---------------------------------------------------------------------------

def print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    max_col_width: int = 50,
) -> None:
    """Print a formatted table.  (CLI-OUTPUT-TABLE-001)"""
    all_rows = [list(headers)] + [list(r) for r in rows]

    # Truncate cells
    for row in all_rows:
        for i, cell in enumerate(row):
            s = str(cell)
            if len(s) > max_col_width:
                row[i] = s[: max_col_width - 3] + "..."
            else:
                row[i] = s

    # Column widths
    col_widths = [0] * len(headers)
    for row in all_rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Header
    hdr = "  ".join(bold(str(h).ljust(w)) for h, w in zip(headers, col_widths))
    sep = "  ".join("─" * w for w in col_widths)
    sys.stdout.write(hdr + "\n")
    sys.stdout.write(dim(sep) + "\n")

    # Rows
    for row in all_rows[1:]:
        line = "  ".join(str(c).ljust(w) for c, w in zip(row, col_widths))
        sys.stdout.write(line + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Key-value display  (CLI-OUTPUT-KV-001)
# ---------------------------------------------------------------------------

def print_kv(pairs: Dict[str, Any], *, indent: int = 0) -> None:
    """Print key-value pairs aligned.  (CLI-OUTPUT-KV-001)"""
    if not pairs:
        return
    prefix = " " * indent
    max_key = max(len(str(k)) for k in pairs)
    for k, v in pairs.items():
        label = cyan(str(k).ljust(max_key))
        sys.stdout.write(f"{prefix}{label}  {v}\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Unified response renderer  (CLI-OUTPUT-RENDER-001)
# ---------------------------------------------------------------------------

def render_response(
    resp_data: Any,
    *,
    output_format: str = "text",
    title: Optional[str] = None,
) -> None:
    """Render an API response in the requested format.  (CLI-OUTPUT-RENDER-001)"""
    if output_format == "json":
        print_json(resp_data)
        return

    if title:
        sys.stdout.write(f"\n{bold(title)}\n{'─' * len(title)}\n")

    if isinstance(resp_data, dict):
        print_kv(resp_data)
    elif isinstance(resp_data, list):
        for item in resp_data:
            if isinstance(item, dict):
                print_kv(item)
                sys.stdout.write("\n")
            else:
                sys.stdout.write(f"  • {item}\n")
    else:
        sys.stdout.write(f"{resp_data}\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Banner  (CLI-OUTPUT-BANNER-001)
# ---------------------------------------------------------------------------

BANNER = r"""
  ╔══════════════════════════════════════════════════╗
  ║              murphy.systems CLI                  ║
  ║  AI-powered business automation from the terminal║
  ╚══════════════════════════════════════════════════╝
"""


def print_banner() -> None:
    """Print the Murphy CLI startup banner.  (CLI-OUTPUT-BANNER-001)"""
    sys.stdout.write(cyan(BANNER.strip()) + "\n\n")
    sys.stdout.flush()

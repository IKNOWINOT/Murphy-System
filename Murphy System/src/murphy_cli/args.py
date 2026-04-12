"""
Murphy CLI — Argument parser & routing engine
==============================================

Parses CLI arguments using a hand-rolled parser (zero external deps) with
the same ``<resource> <command> [flags]`` convention as MiniMax CLI.

Module label: CLI-ARGS-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Global flag definitions  (CLI-ARGS-FLAG-001)
# ---------------------------------------------------------------------------

GLOBAL_FLAGS: Dict[str, Dict[str, Any]] = {
    "--api-key":         {"type": "string",  "env": "MURPHY_API_KEY",    "help": "API key for authentication"},
    "--api-url":         {"type": "string",  "env": "MURPHY_API_URL",    "help": "API base URL (default: http://localhost:8000)"},
    "--output":          {"type": "choice",  "choices": ["text", "json"], "default": "text", "help": "Output format"},
    "--timeout":         {"type": "int",     "default": 30,              "help": "Request timeout in seconds"},
    "--quiet":           {"type": "bool",    "default": False,           "help": "Suppress non-essential output"},
    "--verbose":         {"type": "bool",    "default": False,           "help": "Enable verbose/debug output"},
    "--no-color":        {"type": "bool",    "default": False,           "help": "Disable ANSI colour output"},
    "--dry-run":         {"type": "bool",    "default": False,           "help": "Preview request without executing"},
    "--non-interactive": {"type": "bool",    "default": False,           "help": "Disable interactive prompts (CI/agent mode)"},
    "--version":         {"type": "bool",    "default": False,           "help": "Show version and exit"},
    "--help":            {"type": "bool",    "default": False,           "help": "Show help and exit"},
    "-h":                {"type": "bool",    "default": False,           "help": "Show help and exit (short)"},
    "-v":                {"type": "bool",    "default": False,           "help": "Show version (short)"},
    "-q":                {"type": "bool",    "default": False,           "help": "Quiet mode (short)"},
}


@dataclass
class ParsedArgs:
    """Result of parsing CLI arguments.  (CLI-ARGS-PARSED-001)"""

    resource: Optional[str] = None          # e.g. "auth", "chat", "forge"
    command: Optional[str] = None           # e.g. "login", "generate"
    positional: List[str] = field(default_factory=list)  # remaining positional args
    flags: Dict[str, Any] = field(default_factory=dict)  # --flag values
    raw: List[str] = field(default_factory=list)         # original argv

    # Convenience accessors for global flags
    @property
    def api_key(self) -> Optional[str]:
        return self.flags.get("api_key")

    @property
    def api_url(self) -> Optional[str]:
        return self.flags.get("api_url")

    @property
    def output_format(self) -> str:
        return self.flags.get("output", "text")

    @property
    def timeout(self) -> int:
        return int(self.flags.get("timeout", 30))

    @property
    def quiet(self) -> bool:
        return bool(self.flags.get("quiet", False))

    @property
    def verbose(self) -> bool:
        return bool(self.flags.get("verbose", False))

    @property
    def no_color(self) -> bool:
        return bool(self.flags.get("no_color", False))

    @property
    def dry_run(self) -> bool:
        return bool(self.flags.get("dry_run", False))

    @property
    def non_interactive(self) -> bool:
        return bool(self.flags.get("non_interactive", False))

    @property
    def show_version(self) -> bool:
        return bool(self.flags.get("version", False))

    @property
    def show_help(self) -> bool:
        return bool(self.flags.get("help", False))


def _normalise_flag_name(flag: str) -> str:
    """Convert ``--api-key`` → ``api_key``.  (CLI-ARGS-NORM-001)"""
    return flag.lstrip("-").replace("-", "_")


def parse_args(argv: Optional[Sequence[str]] = None) -> ParsedArgs:
    """Parse CLI arguments into a :class:`ParsedArgs`.  (CLI-ARGS-PARSE-001)

    Grammar::

        murphy [global-flags] <resource> [command] [flags] [positional...]

    Handles ``--flag value``, ``--flag=value``, and boolean ``--flag``.
    """
    if argv is None:
        argv = sys.argv[1:]
    tokens = list(argv)
    result = ParsedArgs(raw=list(argv))

    i = 0
    positional_collected: List[str] = []

    while i < len(tokens):
        tok = tokens[i]

        # --- boolean short flags ---
        if tok in ("-h",):
            result.flags["help"] = True
            i += 1
            continue
        if tok in ("-v",):
            result.flags["version"] = True
            i += 1
            continue
        if tok in ("-q",):
            result.flags["quiet"] = True
            i += 1
            continue

        # --- long flags ---
        if tok.startswith("--"):
            # Handle --flag=value
            if "=" in tok:
                flag_part, _, val_part = tok.partition("=")
                name = _normalise_flag_name(flag_part)
                result.flags[name] = val_part
            else:
                name = _normalise_flag_name(tok)
                meta = GLOBAL_FLAGS.get(tok, {})
                ftype = meta.get("type", "string")
                if ftype == "bool":
                    result.flags[name] = True
                else:
                    # Consume next token as value
                    if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                        result.flags[name] = tokens[i + 1]
                        i += 1
                    else:
                        result.flags[name] = True
            i += 1
            continue

        # --- positional tokens ---
        positional_collected.append(tok)
        i += 1

    # Assign resource / command from positional tokens
    if positional_collected:
        result.resource = positional_collected[0]
    if len(positional_collected) > 1:
        result.command = positional_collected[1]
    if len(positional_collected) > 2:
        result.positional = positional_collected[2:]

    return result

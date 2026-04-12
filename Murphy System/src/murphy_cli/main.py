"""
Murphy CLI — Main entry point
==============================

Bootstrap the CLI: parse args → resolve command → execute.

Usage::

    python -m murphy_cli [args]
    murphy [args]              # via console_scripts entry point

Module label: CLI-MAIN-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional, Sequence

from murphy_cli import __version__
from murphy_cli.args import ParsedArgs, parse_args
from murphy_cli.client import MurphyClient
from murphy_cli.config import CLIConfig
from murphy_cli.output import (
    print_banner,
    print_error,
    print_info,
    set_no_color,
)
from murphy_cli.registry import CommandRegistry
from murphy_cli.commands import register_all_commands


logger = logging.getLogger(__name__)


def _build_context(parsed_args: "ParsedArgs", config: CLIConfig) -> dict:
    """Build the execution context dict passed to every handler.  (CLI-MAIN-CTX-001)"""
    # Determine API URL: flag → env → config → default
    api_url = (
        parsed_args.api_url
        or os.environ.get("MURPHY_API_URL")
        or config.api_url
    )
    api_key = (
        parsed_args.api_key
        or os.environ.get("MURPHY_API_KEY")
        or config.api_key
    )
    timeout = int(parsed_args.flags.get("timeout", config.timeout))

    client = MurphyClient(
        base_url=api_url,
        api_key=api_key,
        timeout=timeout,
        verbose=parsed_args.verbose,
    )

    return {
        "client": client,
        "config": config,
        "api_url": api_url,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point.  Returns an exit code.  (CLI-MAIN-ENTRY-001)"""
    parsed = parse_args(argv)

    # --- no-color ---
    if parsed.no_color or os.environ.get("NO_COLOR"):
        set_no_color(True)

    # --- verbose logging ---
    if parsed.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    # --- version ---
    if parsed.show_version:
        sys.stdout.write(f"murphy-cli {__version__}\n")
        return 0

    # --- build registry ---
    registry = CommandRegistry()
    register_all_commands(registry)

    # --- help (global) ---
    if parsed.show_help and not parsed.resource:
        registry.print_global_help()
        return 0

    # --- no resource given ---
    if not parsed.resource:
        if not parsed.quiet:
            print_banner()
        registry.print_global_help()
        return 0

    # --- resource-level help ---
    if parsed.show_help or parsed.command == "help":
        registry.print_resource_help(parsed.resource)
        return 0

    # --- resolve command ---
    cmd_def = registry.resolve(parsed)
    if cmd_def is None:
        print_error(
            f"Unknown command: murphy {parsed.resource}"
            + (f" {parsed.command}" if parsed.command else "")
        )
        print_info(f"Run 'murphy {parsed.resource} --help' for available commands.")
        return 1

    # --- build context ---
    config = CLIConfig()
    ctx = _build_context(parsed, config)

    # --- dry-run announcement ---
    if parsed.dry_run and not parsed.quiet:
        print_info("DRY RUN mode — no API calls will be made.")

    # --- execute ---
    try:
        exit_code = cmd_def.handler(parsed, ctx)
        return exit_code if isinstance(exit_code, int) else 0
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        print_info("Interrupted.")
        return 130
    except BrokenPipeError:  # CLI-MAIN-ERR-001
        # Graceful handling when piped to head/tail etc.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    except Exception as exc:  # CLI-MAIN-ERR-002
        logger.debug("CLI-MAIN-ERR-002: Unhandled exception", exc_info=True)
        print_error(f"Unexpected error: {exc}", code="CLI-MAIN-ERR-002")
        return 1


# Allow `python -m murphy_cli`
if __name__ == "__main__":
    sys.exit(main())

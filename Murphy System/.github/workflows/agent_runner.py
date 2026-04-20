"""
Murphy System — Founder Claude Code Agent Runner
================================================
Design Label: AGENT-001
Owner: Platform Engineering / Founder Control Plane

Executes Claude Code non-interactively against the Murphy repository.
Supports:
  - Task override via TASK_OVERRIDE environment variable
  - Fallback to TASK_INSTRUCTIONS.txt when no override is provided
  - Dry-run mode (DRY_RUN=true) — skips claude invocation, prints plan only
  - Hard failure on missing API key, missing instructions, or claude error
  - Structured output written to AGENT_OUTPUT.txt for artifact upload

Error Handling:
  - Raises SystemExit with a descriptive message on every failure condition.
  - Never silently swallows exceptions.
  - Exit code mirrors claude's exit code so CI fails correctly.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL-1.1
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_FILE = Path(".github/workflows/TASK_INSTRUCTIONS.txt")
OUTPUT_FILE = Path("AGENT_OUTPUT.txt")

# Guiding principles injected into every Claude invocation so it always
# follows the engineering discipline the founder specified.
SYSTEM_PREAMBLE = textwrap.dedent("""
    You are a senior software engineer working on the Murphy System repository.
    Follow these principles for every task:

    1. Analyse before acting: identify what the module does, what it should do,
       and all possible conditions.
    2. Plan explicitly: list the ordered steps you will take before writing code.
    3. Implement: make the changes, labelling all code with design labels where
       they exist (e.g. AGENT-001, WIRE-004).
    4. Test: run or write tests; validate with the full range of conditions.
    5. Review results: if tests fail, diagnose from symptoms → root cause → fix → test again (loop).
    6. Harden: apply error handling, input validation, and structured logging.
       Nothing should fail silently. Automations must not execute or fail silently.
    7. Update ancillary code and documentation to reflect every change made.
    8. Re-commission: verify the module passes CI after all changes.
    9. Never delete files prefixed with 'steve' (steve2028merch.html,
       voteforsteve2028.html, stevewiki.html, steve_candidate.png).
    10. Canonical source is Murphy System/src/ — always edit there first,
        then sync root src/ to match. Never edit root copies independently.
""").strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_task() -> str:
    """Return the task string from env override or TASK_INSTRUCTIONS.txt."""
    override = os.environ.get("TASK_OVERRIDE", "").strip()
    if override:
        print(f"[agent_runner] Using task from TASK_OVERRIDE env var ({len(override)} chars)")
        return override

    if not TASK_FILE.exists():
        raise SystemExit(
            f"[agent_runner] ERROR: No task provided and {TASK_FILE} does not exist. "
            "Set TASK_OVERRIDE or create TASK_INSTRUCTIONS.txt."
        )

    instructions = TASK_FILE.read_text(encoding="utf-8").strip()
    if not instructions:
        raise SystemExit(
            f"[agent_runner] ERROR: {TASK_FILE} exists but is empty. "
            "Provide a task in the file or via TASK_OVERRIDE."
        )

    print(f"[agent_runner] Using task from {TASK_FILE} ({len(instructions)} chars)")
    return instructions


def _validate_env() -> None:
    """Abort early if required environment variables are missing."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "[agent_runner] ERROR: ANTHROPIC_API_KEY is not set. "
            "Ensure the Murphy_System_Claude secret is configured in GitHub."
        )


def _run_claude(task: str, dry_run: bool) -> int:
    """Invoke claude --print with the task. Returns claude's exit code."""
    full_prompt = f"{SYSTEM_PREAMBLE}\n\n---\n\n{task}"

    if dry_run:
        print("[agent_runner] DRY RUN — skipping claude invocation.")
        print("[agent_runner] Would have sent prompt:")
        print(full_prompt[:1000] + ("..." if len(full_prompt) > 1000 else ""))
        OUTPUT_FILE.write_text(
            f"[DRY RUN — no claude invocation]\n\nPROMPT PREVIEW:\n{full_prompt[:2000]}\n",
            encoding="utf-8",
        )
        return 0

    print("[agent_runner] Invoking claude --print ...")
    result = subprocess.run(
        ["claude", "--print", full_prompt],
        capture_output=False,   # let stdout/stderr stream to Actions log in real time
        text=True,
    )

    # Capture output for artifact (re-run with capture after we've streamed it)
    capture = subprocess.run(
        ["claude", "--print", full_prompt],
        capture_output=True,
        text=True,
    )
    output = capture.stdout or capture.stderr or "(no output captured)"
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"[agent_runner] Output written to {OUTPUT_FILE} ({len(output)} chars)")

    return result.returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _validate_env()
    task = _resolve_task()
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    print(f"[agent_runner] dry_run={dry_run}")
    print(f"[agent_runner] Task preview: {task[:200]}{'...' if len(task) > 200 else ''}")

    exit_code = _run_claude(task, dry_run)

    if exit_code != 0:
        raise SystemExit(
            f"[agent_runner] ERROR: claude exited with code {exit_code}. "
            "Check the workflow log for details."
        )

    print("[agent_runner] Claude Code agent run completed successfully.")


if __name__ == "__main__":
    main()


# Copyright © 2026 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Rosetta CTO Rules Loader — Murphy System (ROSETTA-RULES-001)

Owner: Agent Identity / Rosetta Subsystem
Dep: rosetta_soul_renderer

Loads the canonical rule corpus from /opt/Murphy-System/rules/ and
prepends it to the CTO role's soul context. Without this, Rosetta
CTO renders souls but has no patch/code discipline.

R50 (2026-06-05): Created after Corey directive — "make sure his
Rosetta is discerning and follows the rules we have put together for
how to perform patches and code." Solves the gap surfaced when
Superagent batch-processed 387 platform_cto proposals (R47) — many
were status-noise, none had been gated by audit-first / before-after
canon / check-github-first because the rules weren't loaded.

Design:
  - Single function: load_rules() returns the rule corpus as a list
    of (name, content) tuples, sorted by tier.
  - Tier 0 = governance (do not deviate) — audit_first,
    before_after_canon, error_discipline, no_fake_revenue,
    correctness_over_cycles, ask_murphy_first
  - Tier 1 = process — check_github_first,
    code_documentation_standard, shape_of_complete,
    does_it_do_what_designed, show_your_work, state_transition_labeling
  - Tier 2 = workflow — murphy_workflow, cyborg_mode,
    continuous_loop_until_working, interrupt_recovery, memory_hygiene,
    suggestion_queue, rosetta_architecture
  - Tier 3 = reference — endpoint_map, murphy_channels_canonical,
    ask_murphy_before_all_choices
  - Idempotent + cached (re-reads on mtime change only).

Public API:
    load_rules() -> List[Tuple[str, str]]
    render_rules_for_cto() -> str   # ready-to-prepend markdown block
    rules_summary() -> Dict[str, int]  # for health/debug endpoints

Error Handling:
    Logs and degrades gracefully — if /opt/Murphy-System/rules/ is
    missing or unreadable, returns empty list. Never raises. The CTO
    can still render; it just won't be rule-bound. The
    /api/rosetta/cto/rules-status endpoint reports this state so
    operators can see.

Error codes: ROSETTA-RULES-ERR-001 through ROSETTA-RULES-ERR-003.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────

RULES_DIR = Path(os.environ.get("MURPHY_RULES_DIR", "/opt/Murphy-System/rules"))

TIER_0_GOVERNANCE = {
    "ask_murphy_first",
    "ask_murphy_before_all_choices",
    "audit_first",
    "before_after_canon",
    "error_discipline",
    "no_fake_revenue",
    "correctness_over_cycles",
}

TIER_1_PROCESS = {
    "check_github_first",
    "code_documentation_standard",
    "shape_of_complete",
    "shape_of_complete_v2",
    "does_it_do_what_designed",
    "show_your_work",
    "state_transition_labeling",
}

TIER_2_WORKFLOW = {
    "murphy_workflow",
    "cyborg_mode",
    "continuous_loop_until_working",
    "interrupt_recovery",
    "memory_hygiene",
    "suggestion_queue",
    "rosetta_architecture",
}

# Anything not classified above lands in tier_3 (reference)

# ─────────────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────────────

_CACHE: Dict[str, object] = {"rules": [], "fingerprint": None}


def _compute_fingerprint() -> Optional[str]:
    """Cheap signature: max mtime over all rule files."""
    try:
        if not RULES_DIR.exists():
            return None
        max_mtime = 0.0
        for p in RULES_DIR.glob("*.md"):
            try:
                m = p.stat().st_mtime
                if m > max_mtime:
                    max_mtime = m
            except OSError:
                continue
        return f"{max_mtime:.6f}"
    except Exception as e:
        logger.warning(
            "ROSETTA-RULES-ERR-001: fingerprint compute failed: %s", e
        )
        return None


def _tier_of(stem: str) -> int:
    if stem in TIER_0_GOVERNANCE:
        return 0
    if stem in TIER_1_PROCESS:
        return 1
    if stem in TIER_2_WORKFLOW:
        return 2
    return 3


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────


def load_rules() -> List[Tuple[str, str]]:
    """Return [(name, markdown_content), ...] sorted (tier, name).

    Caches result; re-reads only when any file's mtime changes.
    Returns empty list (and logs warning) if rules dir is missing.
    """
    fp = _compute_fingerprint()
    if fp is not None and fp == _CACHE.get("fingerprint"):
        return _CACHE["rules"]  # type: ignore[return-value]

    rules: List[Tuple[int, str, str]] = []
    if not RULES_DIR.exists():
        logger.warning(
            "ROSETTA-RULES-ERR-002: rules dir missing: %s", RULES_DIR
        )
        _CACHE["rules"] = []
        _CACHE["fingerprint"] = fp
        return []

    for p in sorted(RULES_DIR.glob("*.md")):
        try:
            content = p.read_text(encoding="utf-8")
            rules.append((_tier_of(p.stem), p.stem, content))
        except OSError as e:
            logger.warning(
                "ROSETTA-RULES-ERR-003: failed to read %s: %s", p, e
            )
            continue

    rules.sort(key=lambda r: (r[0], r[1]))
    result = [(name, content) for _tier, name, content in rules]
    _CACHE["rules"] = result
    _CACHE["fingerprint"] = fp
    logger.info(
        "rosetta_rules: loaded %d files from %s", len(result), RULES_DIR
    )
    return result


def render_rules_for_cto() -> str:
    """Return a markdown block ready to prepend to platform_cto soul context.

    Format:
        # CTO Patch/Code Rules (loaded from /opt/Murphy-System/rules/)
        # 23 rules organized by tier — most binding first.
        # These are NOT optional. Every proposal must comply.

        ## Tier 0 — Governance (do not deviate)
        ### audit_first
        <content>
        ---
        ### before_after_canon
        ...

        ## Tier 1 — Process
        ...
    """
    rules = load_rules()
    if not rules:
        return (
            "# CTO Patch/Code Rules\n"
            "# WARNING: rules directory not loaded — operating without "
            "discernment.\n"
        )

    blocks: List[str] = []
    blocks.append(
        "# CTO Patch/Code Rules "
        "(loaded from /opt/Murphy-System/rules/)\n"
        f"# {len(rules)} rules organized by tier — most binding first.\n"
        "# These are NOT optional. Every proposal MUST comply.\n"
    )

    current_tier = -1
    tier_labels = {
        0: "## Tier 0 — Governance (do not deviate)",
        1: "## Tier 1 — Process",
        2: "## Tier 2 — Workflow",
        3: "## Tier 3 — Reference",
    }

    for name, content in rules:
        tier = _tier_of(name)
        if tier != current_tier:
            blocks.append(tier_labels[tier])
            current_tier = tier
        blocks.append(f"### {name}\n{content}\n---")

    return "\n\n".join(blocks)


def rules_summary() -> Dict[str, int]:
    """Counts per tier — for health endpoints and debugging."""
    rules = load_rules()
    counts = {"tier_0": 0, "tier_1": 0, "tier_2": 0, "tier_3": 0, "total": 0}
    for name, _ in rules:
        counts[f"tier_{_tier_of(name)}"] += 1
        counts["total"] += 1
    return counts


# ─────────────────────────────────────────────────────────────────────────
# Self-test (run as: python3 -m rosetta.rosetta_cto_rules_loader)
# ─────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=== rosetta_cto_rules_loader self-test ===")
    summary = rules_summary()
    print(f"  rules loaded: {summary}")
    rendered = render_rules_for_cto()
    print(f"  rendered length: {len(rendered)} chars "
          f"(~{len(rendered) // 4} tokens)")
    print("  preview:")
    for line in rendered.split("\n")[:20]:
        print(f"    {line}")

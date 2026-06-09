#!/usr/bin/env python3
"""
PCR-046 — L5 Prior Receipts layer in Rosetta soul render

FOUNDER DIRECTION (2026-06-09 00:47 PT):
  "Rosetta injections and dlf is how this is suppose to be replayed."

The accomplishment receipts that PCR-045c is accumulating belong
inside the Rosetta soul stack, not as a separate prompt-augmentation
path. That way:
  - DLF-R picks them up automatically via rosetta_block
  - All consumers of _render_soul() see them with zero rewiring
  - The L0-L4 deep-soul layers from PATCH-385 are unchanged

ARCHITECTURE — extend the layered soul:
  L0  Identity (existing)
  L1  Persona / voice (existing)
  L2  Domain expertise (existing)
  L3  Project context (existing)
  L4  Task context (existing)
  L5  Prior Receipts (NEW) — accomplishments under this persistent_id

L5 only renders when blueprint carries priors (PCR-045c provided
prior_accomplishments_count > 0 OR persistent_id has rows in the
agent_accomplishments table). First-time agents see no L5 layer.

CHANGE — single function modification in dynamic_rosetta_planner.py:
  Add helper _render_l5_priors(agent, profile) -> str.
  Splice it into _render_soul() right before the return so it gets
  appended to full_soul.

FAIL-SOFT: any DB error → empty string → soul renders without L5.
The agent still fires; just doesn't get priors context that call.

VERIFICATION PLAN:
  - Unit test: a blueprint with priors=0 produces no L5 line
  - Unit test: a blueprint with persistent_id matching real
    accomplishments produces an L5 block listing recent wins
  - Live test: dispatch with established persistent_id should now
    show L5 in the rendered soul written to disk by 045b path
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

PLANNER = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")

# ─── Helper function added to the class ────────────────────────────────
HELPER_OLD = '''    def _render_soul(self, agent: AgentBlueprint, profile: TaskProfile) -> str:
        """
        PATCH-385 — Load full layered Deep Soul (L0-L4) from entity_graph.db.

        Rosetta has NO token limit. Layer selection is by relevance to the
        agent's role and the task domain. Full soul stack is returned —
        every layer that exists for this agent is included, no truncation.
        """'''

HELPER_NEW = '''    def _render_l5_prior_receipts(self, agent: AgentBlueprint) -> str:
        """
        PCR-046 — L5 Prior Receipts layer.

        Renders an agent's accumulated accomplishments under its
        persistent_id (PCR-045c) as a soul layer. Cross-domain by
        default — the receipts speak louder than the original
        domain assignment.

        Returns empty string when:
          - no persistent_id on blueprint, OR
          - no successful accomplishments under that persistent_id, OR
          - any DB error (fail-soft)
        """
        pid = getattr(agent, "persistent_id", "") or ""
        if not pid:
            return ""
        try:
            import sqlite3 as _sqlite3_046
            conn = _sqlite3_046.connect(
                "/var/lib/murphy-production/murphy_identity.db", timeout=3.0
            )
            try:
                rows = conn.execute(
                    """
                    SELECT domain, task_prompt, output_type, output_summary, fired_at
                    FROM agent_accomplishments
                    WHERE profile_id = ? AND success = 1
                    ORDER BY fired_at DESC
                    LIMIT 8
                    """,
                    (pid,),
                ).fetchall()
                # Aggregate domain counts for the header summary
                stats = conn.execute(
                    """
                    SELECT domain, COUNT(*) FROM agent_accomplishments
                    WHERE profile_id = ? AND success = 1
                    GROUP BY domain ORDER BY COUNT(*) DESC
                    """,
                    (pid,),
                ).fetchall()
            finally:
                conn.close()
            if not rows:
                return ""
            total = sum(c for _, c in stats)
            dom_line = ", ".join("{}({})".format(d or "general", c) for d, c in stats)
            lines = [
                "## L5 — Prior Receipts (track record under persistent_id={})".format(pid),
                "",
                "**Total successful fires:** {}  |  **Domains:** {}".format(total, dom_line),
                "",
                "**Recent wins (newest first):**",
            ]
            for domain, prompt_txt, output_type, summary, _fired in rows:
                # Keep each receipt to one tight line
                ptxt = (prompt_txt or "")[:80].replace("\\n", " ")
                stxt = (summary or "")[:120].replace("\\n", " ")
                lines.append(
                    "- [{}] {} → {} :: {}".format(
                        domain or "general", ptxt, output_type or "?", stxt
                    )
                )
            lines.append("")
            lines.append(
                "_Use this track record to inform your approach. You have "
                "done this kind of work before; lean on what worked._"
            )
            return "\\n".join(lines)
        except Exception:
            return ""  # fail-soft

    def _render_soul(self, agent: AgentBlueprint, profile: TaskProfile) -> str:
        """
        PATCH-385 — Load full layered Deep Soul (L0-L4) from entity_graph.db.
        PCR-046  — Append L5 Prior Receipts layer when priors exist.

        Rosetta has NO token limit. Layer selection is by relevance to the
        agent's role and the task domain. Full soul stack is returned —
        every layer that exists for this agent is included, no truncation.
        """'''

# ─── Splice L5 onto the full_soul return path ─────────────────────────
RETURN_OLD = '''            # full_soul key already concatenates L0+L1+L2+L3+L4
            # If missing (older deep_soul_engine), build it ourselves
            if "full_soul" in soul_layers and soul_layers["full_soul"]:
                return soul_layers["full_soul"]

            return "\\n\\n".join(
                soul_layers.get(layer, "")
                for layer in ("L0", "L1", "L2", "L3", "L4")
                if soul_layers.get(layer)
            )'''

RETURN_NEW = '''            # full_soul key already concatenates L0+L1+L2+L3+L4
            # If missing (older deep_soul_engine), build it ourselves
            # PCR-046 — append L5 Prior Receipts when blueprint has priors
            _l5_046 = self._render_l5_prior_receipts(agent)
            if "full_soul" in soul_layers and soul_layers["full_soul"]:
                _base_046 = soul_layers["full_soul"]
                return (_base_046 + "\\n\\n" + _l5_046) if _l5_046 else _base_046

            _base_046 = "\\n\\n".join(
                soul_layers.get(layer, "")
                for layer in ("L0", "L1", "L2", "L3", "L4")
                if soul_layers.get(layer)
            )
            return (_base_046 + "\\n\\n" + _l5_046) if _l5_046 else _base_046'''

# ─── Also splice L5 onto the FALLBACK path so test/stub renders see it ─
FALLBACK_OLD = '''            # Fallback to a minimal soul (NOT the old 95-word version — just identity)
            return (
                f"# AGENT — {agent.agent_id}\\n"
                f"**Role:** {agent.role_class}\\n"
                f"**Reports to:** {agent.reports_to or 'CEO'}\\n"
                f"**Task domain:** {getattr(profile, 'domain', 'operations')}\\n"
            )'''

FALLBACK_NEW = '''            # Fallback to a minimal soul (NOT the old 95-word version — just identity)
            # PCR-046 — also include L5 priors in the fallback path
            _stub_046 = (
                f"# AGENT — {agent.agent_id}\\n"
                f"**Role:** {agent.role_class}\\n"
                f"**Reports to:** {agent.reports_to or 'CEO'}\\n"
                f"**Task domain:** {getattr(profile, 'domain', 'operations')}\\n"
            )
            _l5_046 = self._render_l5_prior_receipts(agent)
            return (_stub_046 + "\\n\\n" + _l5_046) if _l5_046 else _stub_046'''


def _patch(old, new, marker, name, verify, revert):
    src = PLANNER.read_text(encoding="utf-8")
    if revert:
        if marker not in src:
            print(f"  · {name}: already absent"); return 0
        if new not in src:
            print(f"  ✗ {name}: new anchor not found"); return 1
        src = src.replace(new, old, 1)
        if verify: print(f"  ✓ {name}: would revert"); return 0
        PLANNER.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: reverted"); return 0
    if marker in src:
        print(f"  · {name}: already present"); return 0
    if old not in src:
        print(f"  ✗ {name}: old anchor not found"); return 1
    if src.count(old) > 1:
        print(f"  ✗ {name}: anchor matches {src.count(old)} places — refusing"); return 1
    src = src.replace(old, new, 1)
    if verify: print(f"  ✓ {name}: would apply"); return 0
    PLANNER.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: applied"); return 0


def apply(verify, revert):
    print(f"PCR-046 L5 prior receipts  verify={verify}  revert={revert}")
    steps = [
        (HELPER_OLD,   HELPER_NEW,   "PCR-046 — Append L5 Prior Receipts layer", "L5 helper + docstring"),
        (RETURN_OLD,   RETURN_NEW,   "PCR-046 — append L5 Prior Receipts when blueprint has priors", "main return path"),
        (FALLBACK_OLD, FALLBACK_NEW, "PCR-046 — also include L5 priors in the fallback path", "fallback path"),
    ]
    if revert:
        steps = list(reversed(steps))
    rc = 0
    for old, new, marker, name in steps:
        r = _patch(old, new, marker, name, verify, revert)
        if r != 0: rc = r
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
PATCH-418-repair — Surgical fix for the lenses module + reinject routes.

The original deploy had two f-strings that got mangled when heredoc'd
through SSH. This repair script writes the corrected module + routes
directly via Python file I/O (no shell interpretation), then re-injects
into the monolith.
"""
from pathlib import Path

LENSES = Path("/opt/Murphy-System/src/role_cognitive_lenses.py")
src = LENSES.read_text()

# Find and replace the broken assemble function tail.
# We'll search for the if-not-lens block and the join block by signature.

# Pattern: "        return " followed by mangled bytes until "\n    parts = []"
# Easier: just slice and rewrite the broken assemble_lens_prompt function.

# Find function start
start_marker = "def assemble_lens_prompt(role_title: str"
end_marker = "def list_lenses() -> list[dict]:"
s = src.index(start_marker)
e = src.index(end_marker)
old_func = src[s:e]

print(f"  found function at {s}-{e}, {len(old_func)} chars")

new_func = (
    'def assemble_lens_prompt(role_title: str, task: str = "", context: str = "") -> str:\n'
    '    """Build the full system+user prompt that primes the LLM to recurse\n'
    '    into the role\'s cognitive region.\n'
    '\n'
    '    Returns the COMPLETE prompt string ready to send to an LLM.\n'
    '    """\n'
    '    NL = chr(10)\n'
    '    lens = ROLE_LENSES.get(role_title)\n'
    '    if not lens:\n'
    '        return "Task: " + str(task) + NL + NL + "Context: " + str(context)\n'
    '\n'
    '    parts = []\n'
    '    parts.append("=" * 60)\n'
    '    parts.append("COGNITIVE FRAME: " + role_title.upper())\n'
    '    parts.append("=" * 60)\n'
    '    parts.append("")\n'
    '    parts.append(lens["identity"])\n'
    '    parts.append("")\n'
    '    parts.append("THINK IN TERMS OF:")\n'
    '    for mm in lens["mental_models"]:\n'
    '        parts.append("  - " + mm)\n'
    '    parts.append("")\n'
    '    parts.append("VOCABULARY YOU USE FLUENTLY:")\n'
    '    parts.append("  " + ", ".join(lens["vocabulary"]))\n'
    '    parts.append("")\n'
    '    parts.append("DECISION HEURISTICS:")\n'
    '    for h in lens["heuristics"]:\n'
    '        parts.append("  - " + h)\n'
    '    parts.append("")\n'
    '    parts.append("EXEMPLAR REASONING (this is HOW you think):")\n'
    '    parts.append("  " + lens["exemplar"])\n'
    '    parts.append("")\n'
    '    parts.append("YOU NEVER:")\n'
    '    for ap in lens["anti_patterns"]:\n'
    '        parts.append("  - " + ap)\n'
    '    parts.append("")\n'
    '    parts.append("VOICE: " + lens["voice"])\n'
    '    parts.append("")\n'
    '    parts.append("=" * 60)\n'
    '    parts.append("")\n'
    '\n'
    '    if context:\n'
    '        parts.append("CONTEXT:")\n'
    '        parts.append(context)\n'
    '        parts.append("")\n'
    '\n'
    '    if task:\n'
    '        parts.append("TASK:")\n'
    '        parts.append(task)\n'
    '        parts.append("")\n'
    '        parts.append(\n'
    '            "Respond as a " + role_title + " would think. Do not break frame. "\n'
    '            "Do not summarize the frame - embody it."\n'
    '        )\n'
    '\n'
    '    return NL.join(parts)\n'
    '\n'
    '\n'
)

new_src = src[:s] + new_func + src[e:]

import ast
ast.parse(new_src)
print("  ✓ AST parses")

LENSES.write_text(new_src)
print(f"  ✓ wrote {LENSES} ({len(new_src)} bytes)")

# Smoke test
import sys
sys.path.insert(0, "/opt/Murphy-System/src")
if "role_cognitive_lenses" in sys.modules:
    del sys.modules["role_cognitive_lenses"]
import role_cognitive_lenses as rcl
print(f"  ✓ module loads {len(rcl.ROLE_LENSES)} lenses")
p = rcl.assemble_lens_prompt("vp-sales", task="A prospect said our price is too high.",
                              context="Fintech CFO, $5M ARR.")
print(f"  ✓ assemble: {len(p)} chars")
assert "COGNITIVE FRAME: VP-SALES" in p
assert "ICP-fit" in p
print("  ✓ frame and content present")

# Also fix the routes block in app.py — same f-string problem may exist there
# Let me check
MONO = Path("/opt/Murphy-System/src/runtime/app.py")
mono_src = MONO.read_text()
print(f"  monolith size: {len(mono_src)}")
print(f"  PATCH-418 markers: {mono_src.count('PATCH-418')}")

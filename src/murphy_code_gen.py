# Copyright © 2020 Inoni LLC | License: BSL 1.1
"""Murphy Code Gen — PATCH-069 | Label: CODE-GEN-001

Bridges the gap between triage (symptom detected) and apply (diff written).
Takes a PatchProposal with symptom/diagnosis/affected_file and uses the LLM
to generate a real unified diff. Human review always required before apply.

Entry points:
    generate_diff_for_proposal(proposal_id) -> updated PatchProposal
    generate_and_test_snippet(task_description, context_files) -> dict
"""
from __future__ import annotations
import difflib, logging, re, textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path("/opt/Murphy-System")


def _read_file_safe(rel_path: str, max_chars: int = 6000) -> str:
    """Read a source file relative to project root, truncated for LLM context."""
    try:
        full = _PROJECT_ROOT / rel_path
        if not full.exists():
            # Try src/ prefix
            full = _PROJECT_ROOT / "src" / rel_path
        if not full.exists():
            return f"# FILE NOT FOUND: {rel_path}"
        content = full.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            # Keep first 3000 + last 3000
            content = content[:3000] + f"\n\n# ... ({len(content)} chars total, truncated) ...\n\n" + content[-3000:]
        return content
    except Exception as exc:
        return f"# ERROR reading {rel_path}: {exc}"


def _call_llm(prompt: str, system: str, max_tokens: int = 1200) -> str:
    """Call LLM with fallback chain. Returns text or error string."""
    try:
        from src.llm_provider import complete
        result = complete(prompt=prompt, system=system, max_tokens=max_tokens, temperature=0.2)
        if result and not result.startswith("[Murphy Onboard]"):
            return result
        return f"[LLM_UNAVAILABLE] {result}"
    except Exception as exc:
        return f"[LLM_ERROR] {exc}"


def _extract_code_block(text: str) -> str:
    """Pull first ```python or ``` block from LLM output."""
    m = re.search(r"```(?:python|diff)?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _make_unified_diff(original: str, modified: str, filepath: str) -> str:
    orig_lines = original.splitlines(keepends=True)
    mod_lines  = modified.splitlines(keepends=True)
    diff = list(difflib.unified_diff(orig_lines, mod_lines,
                                     fromfile=f"a/{filepath}",
                                     tofile=f"b/{filepath}", lineterm=""))
    return "".join(diff)


# ─────────────────────────────────────────────────────────────────────
# Core: generate a real diff for a proposal
# ─────────────────────────────────────────────────────────────────────

def generate_diff_for_proposal(proposal_id: str) -> Dict[str, Any]:
    """
    Given a PatchProposal id, read the affected file, call the LLM to propose
    a minimal fix, compute a unified diff, and update the proposal in the store.

    Returns: {"ok": bool, "proposal_id": str, "diff_lines": int, "preview": str}
    """
    from src.murphy_self_patch_loop import get_proposal, add_proposal, PatchProposal

    prop = get_proposal(proposal_id)
    if prop is None:
        return {"ok": False, "error": "Proposal not found"}

    filepath = prop.affected_file
    original_src = _read_file_safe(filepath)

    system = textwrap.dedent("""
        You are Murphy, an AI operating system that patches its own source code.
        You will receive:
          1. A SYMPTOM (what went wrong)
          2. A DIAGNOSIS (why it went wrong)
          3. The AFFECTED SOURCE FILE (Python)

        Your job:
          - Identify the minimal change needed to fix the problem.
          - Output ONLY the COMPLETE corrected Python file — no explanations, no markdown, no diff.
          - Preserve all existing functionality. Change only what is necessary.
          - Keep the same copyright header and docstring.
          - If you cannot determine a fix, output exactly: CANNOT_FIX

        IMPORTANT: Output the full corrected file content, nothing else.
    """).strip()

    prompt = textwrap.dedent(f"""
        SYMPTOM: {prop.symptom}

        DIAGNOSIS: {prop.diagnosis}

        FUNCTION: {prop.affected_function or "unknown"}

        AFFECTED FILE ({filepath}):
        ```python
        {original_src}
        ```

        Output the complete corrected file:
    """).strip()

    llm_output = _call_llm(prompt, system, max_tokens=2000)

    if llm_output.startswith("[LLM"):
        return {"ok": False, "error": llm_output, "proposal_id": proposal_id}

    if "CANNOT_FIX" in llm_output:
        return {"ok": False, "error": "LLM reported cannot determine fix", "proposal_id": proposal_id}

    # Clean up any accidental markdown wrapping
    corrected_src = _extract_code_block(llm_output) if "```" in llm_output else llm_output.strip()

    diff = _make_unified_diff(original_src, corrected_src, filepath)
    if not diff:
        return {"ok": False, "error": "LLM output identical to original — no changes", "proposal_id": proposal_id}

    # Update the proposal with the real diff
    prop.unified_diff = diff
    prop.proposed_change = f"LLM-generated fix for: {prop.symptom[:120]}"
    add_proposal(prop)

    diff_lines = len(diff.splitlines())
    preview = "\n".join(diff.splitlines()[:20])
    logger.info("CODE-GEN-001: Generated %d-line diff for proposal %s", diff_lines, proposal_id)

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "diff_lines": diff_lines,
        "diff_preview": preview,
        "affected_file": filepath,
    }


# ─────────────────────────────────────────────────────────────────────
# Quick task: describe a task → get a code snippet (for testing)
# ─────────────────────────────────────────────────────────────────────

def generate_snippet(task: str, context_files: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Given a plain-english task description and optional context file paths,
    generate a Python code snippet. Used for self-coding capability tests.

    Returns: {"ok": bool, "code": str, "explanation": str}
    """
    context_blocks = ""
    if context_files:
        for fpath in context_files[:3]:
            src = _read_file_safe(fpath, max_chars=2000)
            context_blocks += f"\n\n# --- {fpath} ---\n{src}"

    system = textwrap.dedent("""
        You are Murphy, an AI operating system writing Python code for yourself.
        Write clean, production-quality Python.
        Format your response as:
            EXPLANATION: <one sentence>
            CODE:
            ```python
            <your code here>
            ```
        Nothing else.
    """).strip()

    prompt = f"TASK: {task}{context_blocks}"

    llm_output = _call_llm(prompt, system, max_tokens=800)

    if llm_output.startswith("[LLM"):
        return {"ok": False, "error": llm_output}

    # Parse response
    explanation = ""
    code = ""
    m = re.search(r"EXPLANATION:\s*(.+?)\n", llm_output)
    if m: explanation = m.group(1).strip()

    code = _extract_code_block(llm_output)

    return {
        "ok": True,
        "task": task,
        "explanation": explanation,
        "code": code,
        "raw_output": llm_output,
    }

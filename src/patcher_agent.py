"""
patcher_agent.py — BLOCK-PHASE-B-C — Self-patch proposal agent
==============================================================

WHAT THIS IS:
  A new swarm role: 'patcher'. Receives a brief describing a desired
  code change, uses codebase tools (grep/read/list) to ground itself
  in Murphy's actual source, asks the LLM to produce a UNIFIED DIFF,
  then files the diff as a proposal in self_patch_proposals.json
  for founder review + optional PSM ledger entry.

WHY IT EXISTS:
  The existing self-patch infrastructure is already built:
    - SelfQCPipeline (causality + rubix gates)
    - platform_self_modification/ (PSM ledger, RSC gate)
    - self_patch_proposals.json (proposal store)
  What was missing was the SWARM ENTRY POINT — a role founders can
  dispatch to via /api/rosetta/dispatch with role=patcher.

HOW IT FITS:
  - Founder POSTs to /api/rosetta/dispatch with:
      {"role":"patcher",
       "question":"Add X to file Y",
       "target_file":"src/foo.py"}    ← optional hint
  - PatcherAgent.act() runs LLM with TOOL_CALL grammar (same as ExecutorAgent)
  - LLM iterates: grep → read → propose diff in unified format
  - Agent extracts the diff, writes a Proposal record
  - Proposal lands in self_patch_proposals.json with status='pending'
  - Founder reviews at /api/patcher/proposals or applies via PSM /launch

SAFETY:
  - Patcher NEVER writes source files directly. Only produces proposals.
  - Apply path goes through existing PSM ledger + SelfQCPipeline gates.
  - All proposals require human review (founder approval).
  - Sandbox boundary: all reads stay under MURPHY_SRC.

LAST UPDATED: 2026-05-26 founder + Murphy (Phase B option C)
"""
from __future__ import annotations
import json
import logging
import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# _R475_STUB_GUARD — locked 2026-06-02
# Prevents LLM stub responses from being persisted as patch diffs.
_R475_STUB_MARKERS = (
    "Murphy Onboard STUB",
    "All LLM providers AND local Ollama unreachable",
    "All LLM providers down",
    "onboard-stub",
    "onboard_stub",
)
def _r475_is_stub_diff(text: str) -> bool:
    """Return True if `text` is an LLM stub response, not a real patch.

    R480: also catches tiny non-diff strings like "HEALTHY", "OK", "PASS"
    that the vision loop has been letting through. A real patch has structure:
    either unified diff markers (--- / +++ / @@) or replace blocks (<<<OLD).
    """
    if not text or not isinstance(text, str):
        return False
    # Explicit stub markers
    if any(m in text for m in _R475_STUB_MARKERS):
        return True
    # Tiny strings cannot be real patches — minimum useful diff is ~30 chars
    s = text.strip()
    if len(s) < 20:
        return True
    # Single-word "HEALTHY"/"OK"/"PASS"/"NONE" responses
    if s.upper() in ("HEALTHY", "OK", "PASS", "NONE", "NO-OP", "NOOP", "EMPTY", "N/A"):
        return True
    # Must have diff structure: unified-diff markers OR replace-block markers
    has_diff_markers = (
        "<<<OLD" in text or
        "@@" in text or
        ("\n+" in text and "\n-" in text) or
        text.lstrip().startswith(("---", "+++", "diff --git"))
    )
    if not has_diff_markers:
        return True
    return False


try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.patcher")

PROPOSALS_PATH = Path("/var/lib/murphy-production/self_patch_proposals.json")
MAX_TOOL_ROUNDS = 6   # bumped from 4 — large files need more grep+read rounds
MAX_DIFF_LINES = 500   # limit: reject any proposal exceeding this — prevents runaway diffs

# BLOCK-PARALLEL-SAFE (2026-05-26): fcntl-based file lock prevents proposal
# loss when multiple patchers save concurrently (race destroyed 30+ proposals
# during a parallel batch earlier — never again).
import fcntl as _fcntl_parallel
import threading as _threading_parallel
_PROPOSALS_LOCK = _threading_parallel.Lock()


def _load_proposals() -> Dict[str, Any]:
    if not PROPOSALS_PATH.exists():
        return {}
    try:
        with PROPOSALS_PATH.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_proposals(data: Dict[str, Any]) -> bool:
    """Parallel-safe save: thread lock + fcntl + read-modify-merge-write.

    Critical: when N patchers finish concurrently, naive open-and-write
    causes one patcher's data to overwrite another's. We hold a file
    lock across read+merge+write, and merge new keys with on-disk state
    so no proposal is lost.

    R480: stub-guard — drop proposals whose unified_diff is a stub response
    before writing to disk. Prevents pollution of the patcher store.
    """
    # R480 stub guard at write boundary
    _r480_dropped = 0
    for _r480_pid in list(data.keys()):
        _r480_p = data.get(_r480_pid) or {}
        _r480_diff = _r480_p.get("unified_diff") or _r480_p.get("patch_content") or ""
        if _r475_is_stub_diff(_r480_diff):
            # only drop NEW proposals (status pending/proposed) — never touch already-applied/rejected
            if _r480_p.get("status") in ("pending", "proposed", None, ""):
                logger.warning("R480: dropping stub proposal %s (target=%s)", _r480_pid, _r480_p.get("affected_file"))
                data.pop(_r480_pid, None)
                _r480_dropped += 1
    if _r480_dropped:
        logger.info("R480: dropped %d stub proposals at write boundary", _r480_dropped)
    with _PROPOSALS_LOCK:
        try:
            # .bak before any mutation
            if PROPOSALS_PATH.exists():
                backup = PROPOSALS_PATH.with_suffix(".json.bak")
                backup.write_text(PROPOSALS_PATH.read_text())
            # Read-modify-write under fcntl
            with open(PROPOSALS_PATH, "a+") as f:
                _fcntl_parallel.flock(f.fileno(), _fcntl_parallel.LOCK_EX)
                try:
                    f.seek(0)
                    text = f.read()
                    on_disk = json.loads(text) if text.strip() else {}
                    # Merge: prefer in-memory data (our updates) but preserve
                    # any on-disk entries we don't have (other patchers' new proposals)
                    merged = dict(on_disk)
                    merged.update(data)
                    f.seek(0)
                    f.truncate()
                    f.write(json.dumps(merged, indent=2))
                finally:
                    _fcntl_parallel.flock(f.fileno(), _fcntl_parallel.LOCK_UN)
            return True
        except OSError as exc:
            logger.warning("save_proposals failed: %s", exc)
            return False


def _extract_unified_diff(text: str) -> Optional[str]:
    """Pull a unified-diff block out of LLM output.

    BLOCK-PHASE-B-E (2026-05-26): Also accepts BEFORE/AFTER blocks and
    synthesizes a guaranteed-valid diff via GNU diff.
    """
    # Match a ```diff ... ``` block OR a section starting with --- ... +++
    m = re.search(r"```(?:diff|patch)?\s*\n(--- .*?\n\+\+\+ .*?\n@@.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"(--- .+?\n\+\+\+ .+?\n@@.+?)(?=\n\n\w|\Z)", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _synthesize_diff_from_blocks(text: str, target_file: str, original_source: str) -> Optional[str]:
    """BLOCK-PHASE-B-E: Find BEFORE/AFTER blocks and synthesize unified diff via GNU diff.

    Expected LLM format:
        BEFORE:
        ```
        <verbatim text from original file>
        ```
        AFTER:
        ```
        <replacement text>
        ```
    """
    import subprocess, tempfile, os
    from pathlib import Path

    # Try ```before / ```after blocks
    bm = re.search(r"BEFORE:\s*```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    am = re.search(r"AFTER:\s*```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not (bm and am):
        return None

    before_block = bm.group(1).rstrip("\n")
    after_block = am.group(1).rstrip("\n")

    if before_block not in original_source:
        logger.warning("PatcherAgent semantic: BEFORE block not found verbatim in source")
        return None

    new_source = original_source.replace(before_block, after_block, 1)
    if new_source == original_source:
        return None

    # Generate proper unified diff via GNU diff
    with tempfile.TemporaryDirectory() as td:
        a = Path(td)/"a.py"
        b = Path(td)/"b.py"
        a.write_text(original_source)
        b.write_text(new_source)
        try:
            result = subprocess.run(
                ["diff", "-u", str(a), str(b)],
                capture_output=True, text=True, timeout=10,
            )
            # diff returns 1 when files differ — thats success here
            if result.returncode not in (0, 1):
                return None
            diff_text = result.stdout
        except Exception:
            return None

    # Replace the temp paths with the proper a/<target> b/<target>
    diff_text = re.sub(r"^--- .+$",  f"--- a/{target_file}", diff_text, count=1, flags=re.MULTILINE)
    diff_text = re.sub(r"^\+\+\+ .+$", f"+++ b/{target_file}", diff_text, count=1, flags=re.MULTILINE)
    return diff_text.strip()


def _extract_target_file(text: str, hint: Optional[str] = None) -> Optional[str]:
    """Find the target file from a diff header or hint."""
    if hint:
        return hint
    m = re.search(r"\+\+\+\s+(?:b/)?(\S+)", text)
    if m:
        return m.group(1)
    m = re.search(r"---\s+(?:b/)?(\S+)", text)
    if m:
        return m.group(1)
    return None


def _classify_risk(diff: str, target_file: str) -> str:
    """LOW / MEDIUM / HIGH based on diff scope + file sensitivity."""
    high_risk_paths = (
        "runtime/app.py",
        "modular_auth.py",
        "platform_self_modification/",
        "billing/",
        "audit_middleware.py",
        "murphy_vault",
        "rosetta_core.py",
    )
    if target_file and any(p in target_file for p in high_risk_paths):
        return "HIGH"
    # Count added/removed lines
    plus = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
    minus = len(re.findall(r"^-[^-]", diff, re.MULTILINE))
    if plus + minus > 50:
        return "HIGH"
    if plus + minus > 15:
        return "MEDIUM"
    return "LOW"



def _caf_hint(question):
    """Capability-fallback hint — silent on error."""
    try:
        from src.capability_fallback import build_hint_block
        block = build_hint_block(question or "")
        return ("\n\n" + block) if block else ""
    except Exception:
        return ""


class PatcherAgent(AgentBase):
    """Swarm role: 'patcher'. Proposes unified diffs as reviewable proposals."""

    def __init__(self):
        super().__init__("patcher")

    def act(self, signal: Dict) -> Dict:
        question = signal.get("question") or signal.get("intent_hint") or ""
        target_hint = signal.get("target_file")
        soul_contexts = signal.get("soul_contexts", {}) or {}

        if not question or len(question.strip()) < 8:
            return {
                "status": "rejected",
                "reason": "patcher requires a 'question' brief describing the desired change",
                "agent": "patcher",
            }

        try:
            from src.llm_provider import get_llm
            from src.codebase_tools import grep_codebase, read_source, list_dir, find_file_fast, path_exists_fast
        except ImportError as exc:
            return {"status": "error", "reason": f"missing dependency: {exc}",
                    "agent": "patcher"}

        # Build the prompt — patcher-specific
        soul_prefix = ""
        if soul_contexts:
            sc_role = list(soul_contexts.values())[0] if soul_contexts else ""
            soul_prefix = f"{sc_role}\n\n" if sc_role else ""

        tool_grammar = (
            "AVAILABLE TOOLS (use these to ground your patch in Murphys real source):\n"
            "  TOOL_CALL: grep \"<regex>\"             -- search src/ for a pattern\n"
            "  TOOL_CALL: read <relative_path>       -- read a Murphy source file\n"
            "  TOOL_CALL: read <relative_path> <start> <end>  -- read line range\n"
            "  TOOL_CALL: list <relative_dir>        -- list a directory\n"
            "  TOOL_CALL: find <basename_or_pattern> -- locate files by name (fuzzy)\n"
            "  TOOL_CALL: exists <relative_path>     -- verify a path BEFORE you read it\n"
            "\nNEVER guess paths. Use `find` or `exists` first.\n"
            "OUTPUT FORMAT — STRONGLY PREFERRED (semantic):\n"
            "  FINAL_ANSWER: <1-2 sentence rationale>\n"
            "  BEFORE:\n"
            "  ```python\n"
            "  <copy-paste the exact text from the file you want to replace, verbatim>\n"
            "  ```\n"
            "  AFTER:\n"
            "  ```python\n"
            "  <the replacement text>\n"
            "  ```\n"
            "\n"
            "The server will generate a guaranteed-valid unified diff from your BEFORE/AFTER.\n"
            "RULES:\n"
            "  1. ALWAYS read the target file before proposing a patch.\n"
            "  2. BEFORE must be COPY-PASTE EXACT from the file (whitespace, indentation, all of it).\n"
            "  3. AFTER is what you want it replaced with.\n"
            "  4. Keep BEFORE/AFTER as small as possible — change only what is necessary.\n"
            "  5. If you cannot use BEFORE/AFTER, emit a unified diff in a ```diff block as fallback.\n\n"
        )
        target_hint_line = f"TARGET FILE HINT: {target_hint}\n\n" if target_hint else ""

        full_prompt = (
            f"{soul_prefix}"
            f"You are Murphys patcher agent. A founder has requested a code change.\n\n"
            f"{tool_grammar}"
            f"{target_hint_line}"
            f"BRIEF:\n{question}\n\n"
            f"Begin. Use tools to gather context, then emit FINAL_ANSWER: <rationale>\\n```diff\\n<unified diff>\\n```"
        )

        llm = get_llm()
        conversation = full_prompt
        tools_called = []
        output_text = ""
        resp_text = ""

        for round_n in range(MAX_TOOL_ROUNDS):
            try:
                llm_resp = llm.complete(prompt=conversation, max_tokens=2500)
                resp_text = (llm_resp.content if hasattr(llm_resp,"content")
                             else (llm_resp.text if hasattr(llm_resp,"text")
                                   else str(llm_resp)))
            except Exception as exc:
                logger.warning("Patcher LLM call failed: %s", exc)
                return {"status":"error","reason":f"llm_failed: {exc}","agent":"patcher"}

            if "FINAL_ANSWER:" in resp_text:
                output_text = resp_text.split("FINAL_ANSWER:", 1)[1].strip()
                break

            tool_calls = re.findall(
                r'TOOL_CALL:\s*(grep|read|list|find|exists)\s+(.+?)(?:\n|$)', resp_text
            )
            if not tool_calls:
                output_text = resp_text
                break

            tool_results = []
            for tool_name, args in tool_calls[:4]:
                args = args.strip()
                try:
                    if tool_name == "grep":
                        pat = args.strip('"').strip("'")
                        r = grep_codebase(pat, max_matches=15)
                        tool_results.append(
                            f"[grep {pat!r}] total={r['total']}, first {len(r['matches'])}:\n" +
                            "\n".join(f"  {m['path']}:{m['line']}  {m['text'][:120]}"
                                     for m in r['matches'])
                        )
                    elif tool_name == "read":
                        parts = args.split()
                        path = parts[0]
                        if not path.endswith(".py") and "." not in path.rsplit("/",1)[-1]:
                            path += ".py"  # auto-append .py extension
                        if len(parts) >= 3:
                            r = read_source(path, line_range=(int(parts[1]), int(parts[2])))
                        else:
                            r = read_source(path)
                        if r.get("error"):
                            tool_results.append(f"[read {path}] ERROR: {r['error']}")
                        else:
                            tool_results.append(
                                f"[read {r['path']}] {r['lines']} lines:\n```\n{r['content'][:4000]}\n```"
                            )
                    elif tool_name == "list":
                        r = list_dir(args.strip())
                    elif kind == "find":
                        r = find_file_fast(args.strip())
                    elif kind == "exists":
                        r = path_exists_fast(args.strip())
                        if r.get("error"):
                            tool_results.append(f"[list {args}] ERROR: {r['error']}")
                        else:
                            tool_results.append(
                                f"[list {r['path']}] dirs={r['dirs'][:15]}  files={r['files'][:25]}"
                            )
                    tools_called.append({"tool": tool_name, "args": args})
                except Exception as terr:
                    tool_results.append(f"[{tool_name} {args}] ERROR: {terr}")

            is_last = (round_n == MAX_TOOL_ROUNDS - 1)
            convergence = (
                "\n\n⚠ FINAL ROUND. No more TOOL_CALL allowed. Emit FINAL_ANSWER now:\n"
                "  FINAL_ANSWER: <rationale starting with a verb that appears in AFTER>\n"
                "  BEFORE:\n  ```python\n  <exact copy-paste from file>\n  ```\n"
                "  AFTER:\n  ```python\n  <replacement text>\n  ```\n"
                if is_last else
                "Issue more TOOL_CALLs OR emit FINAL_ANSWER with BEFORE/AFTER ```python blocks."
            )
            conversation = (
                f"{conversation}\n\n--- TOOL_RESULTS (round {round_n+1}) ---\n"
                + "\n\n".join(tool_results) +
                f"\n--- END_TOOL_RESULTS ---\n\n{convergence}"
            )

        if not output_text:
            output_text = resp_text  # last response as best-effort

        # Extract diff + target
        diff = _extract_unified_diff(output_text)
        target_file = _extract_target_file(output_text, target_hint) or target_hint

        # BLOCK-PHASE-B-E: If no valid diff but target file is known, try BEFORE/AFTER synthesis
        if not diff and target_file:
            try:
                src_root = "/opt/Murphy-System"
                from pathlib import Path as _P
                tf = (_P(src_root) / target_file).resolve()
                if tf.exists() and str(tf).startswith(src_root):
                    original = tf.read_text(encoding="utf-8")
                    synth = _synthesize_diff_from_blocks(output_text, target_file, original)
                    if synth:
                        diff = synth
                        logger.info("PatcherAgent: diff synthesized from BEFORE/AFTER blocks")
            except Exception as syn_err:
                logger.warning("PatcherAgent synthesis fallback failed: %s", syn_err)

        # Extract rationale (everything before the diff block)
        rationale = output_text
        if diff:
            for marker in ("```diff", "```patch", "--- "):
                idx = output_text.find(marker)
                if idx > 0:
                    rationale = output_text[:idx].strip()
                    break

        if not diff:
            # No diff produced — return as a rejection but keep the LLM analysis
            return {
                "status": "no_patch_produced",
                "reason": "LLM did not emit a valid unified diff",
                "agent": "patcher",
                "result": output_text,
                "tools_used": tools_called,
                "rationale": rationale[:500],
            }

        # Build proposal
        proposal_id = "prop_" + uuid.uuid4().hex[:10]
        diff_hash = hashlib.sha256(diff.encode()).hexdigest()[:16]
        risk = _classify_risk(diff, target_file or "")

        proposal = {
            "proposal_id":     proposal_id,
            "created_at":      datetime.now(timezone.utc).isoformat(),
            "source":          "patcher_agent",
            "brief":           question[:500],
            "affected_file":   target_file or "unknown",
            "rationale":       rationale[:1000],
            "unified_diff":    diff,
            "diff_hash":       diff_hash,
            "diff_lines":      len(diff.splitlines()),
            "diff_preview":    "\n".join(diff.splitlines()[:5]),
            "risk_level":      risk,
            "status":          "pending",
            "approved_by":     None,
            "applied_at":      None,
            "tools_used":      tools_called,
            "requires_human_review": True,
        }

        proposals = _load_proposals()
        proposals[proposal_id] = proposal
        _save_proposals(proposals)

        logger.info("PatcherAgent: proposal %s filed (target=%s risk=%s diff_lines=%d)",
                    proposal_id, target_file, risk, proposal["diff_lines"])

        return {
            "status":      "proposal_filed",
            "dag_id":      f"patch-{proposal_id}",
            "dag_status":  "ok",
            "result":      f"Proposal {proposal_id} filed.\nTarget: {target_file}\nRisk: {risk}\nDiff lines: {proposal['diff_lines']}\n\nRationale:\n{rationale[:600]}\n\nDiff preview:\n{diff[:1000]}",
            "proposal_id": proposal_id,
            "target_file": target_file,
            "risk_level":  risk,
            "agent":       "patcher",
            "tools_used":  tools_called,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }


_PATCHER_AGENT_SINGLETON: Optional[PatcherAgent] = None

def get_patcher_agent() -> PatcherAgent:
    global _PATCHER_AGENT_SINGLETON
    if _PATCHER_AGENT_SINGLETON is None:
        _PATCHER_AGENT_SINGLETON = PatcherAgent()
    return _PATCHER_AGENT_SINGLETON

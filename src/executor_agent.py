"""
PATCH-130 — src/executor_agent.py
Murphy System — Executor Agent (position 4 / RosettaSoul)
Carries out approved actions via DAG execution.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.executor")

# ── PATCH-AIONMIND-BRIDGE-R180 (2026-05-29) ─────────────────────────────────
# Bridge executor_agent TOOL_CALL grammar to aionmind.tool_executor (PATCH-062).
# Syntax: TOOL_CALL: tool <aionmind_tool_id> <json_kwargs>
import json as _r180_json

def _r180_bridge_to_aionmind(tool_id, kwargs_json_str):
    """Parse JSON kwargs and dispatch through aionmind.dispatch_tool.

    PATCH-CONTENT-B64-R251 (2026-05-29): if kwargs include 'content_b64',
    decode it and substitute for 'content'. Avoids JSON-quoting collisions
    when content has embedded apostrophes/quotes (e.g. SQL strings).
    """
    try:
        kwargs = _r180_json.loads(kwargs_json_str) if kwargs_json_str.strip() else {}
        if not isinstance(kwargs, dict):
            return f"[tool {tool_id}] ERROR: kwargs must be JSON object"
    except _r180_json.JSONDecodeError as e:
        return f"[tool {tool_id}] ERROR: invalid JSON: {e}"
    # PATCH-CONTENT-B64-R251: decode base64 content if provided
    if "content_b64" in kwargs and "content" not in kwargs:
        try:
            import base64 as _r251_b64
            kwargs["content"] = _r251_b64.b64decode(kwargs.pop("content_b64")).decode("utf-8")
        except Exception as e:
            return f"[tool {tool_id}] ERROR: content_b64 decode failed: {e}"
    try:
        from src.aionmind.tool_executor import dispatch_tool
    except Exception as e:
        return f"[tool {tool_id}] ERROR: aionmind import failed: {e}"
    try:
        result = dispatch_tool(tool_id, **kwargs)
    except Exception as e:
        return f"[tool {tool_id}] EXCEPTION: {type(e).__name__}: {e}"
    if isinstance(result, dict):
        if result.get("ok") is False:
            return f"[tool {tool_id}] FAILED: {result.get('error', 'unknown')}"
        bits = ["ok=" + str(result.get("ok"))]
        for k in ("stdout", "content", "status", "bytes_written", "returncode", "result"):
            if k in result and result[k] is not None:
                bits.append(f"{k}={str(result[k])[:300]}")
        return f"[tool {tool_id}] " + " ".join(bits)
    return f"[tool {tool_id}] {str(result)[:500]}"
# ── END PATCH-AIONMIND-BRIDGE-R180 ───────────────────────────────────────────





def _caf_hint(question):
    """Capability-fallback hint for retry rounds. Silent on error."""
    try:
        from src.capability_fallback import build_hint_block
        block = build_hint_block(question or "")
        return ("\n\n" + block) if block else ""
    except Exception:
        return ""


def _caf_log(task_desc, original, failure_signal, fallback, succeeded):
    """PATCH-CAF-001 (2026-05-27): write-side CAF ledger.

    Records that ``original`` failed and ``fallback`` was tried (and whether
    the fallback succeeded). This feeds the fallback_log SQLite ledger that
    powers DLF-R Phase 5 (FALLBACK_SUCCEEDS weaves) and CAF's retry-hint
    generator. Silent on error — never breaks the executor loop.
    """
    try:
        from src.capability_fallback import log_fallback
        log_fallback(
            task_description=str(task_desc)[:500],
            original_approach=str(original)[:200],
            failure_signal=str(failure_signal)[:200],
            discovered=None,
            fallback_chosen=str(fallback)[:200],
            succeeded=int(succeeded),
        )
    except Exception:
        pass  # CAF ledger must never break the loop


class ExecutorAgent(AgentBase):
    """Position 4 — Executor. Direct, bias: completion."""

    def __init__(self):
        super().__init__("executor")

    def act(self, signal: Dict) -> Dict:
        """Execute a brief via LLM (preferred) or pre-approved action via DAG executor.

        BLOCK-SWARM-EXEC2 (2026-05-26): When signal carries a 'question'/'intent_hint'
        (the HTTP /api/rosetta/dispatch path), invoke the LLM directly on the brief
        and return the response text. Otherwise fall back to the legacy DAG path
        for explicit actions (used by swarm_scheduler heartbeats).
        """
        action      = signal.get("action", "")
        domain      = signal.get("domain", "general")
        payload     = signal.get("raw_payload", {})
        question    = signal.get("question", "") or signal.get("intent_hint", "")
        soul_contexts = signal.get("_soul_contexts", {})

        # ── LLM PATH: brief in question/intent_hint (HTTP dispatch) ──────────
        # GAP-1 UNLOCK (2026-05-26): codebase tools available via TOOL_CALL markers.
        # LLM can emit lines like:
        #   TOOL_CALL: grep "pattern"
        #   TOOL_CALL: read src/foo.py
        #   TOOL_CALL: list src/
        # We execute up to MAX_TOOL_ROUNDS rounds, feeding results back in.
        if question and len(question.strip()) > 8:
            try:
                from src.llm_provider import get_llm
                from src.codebase_tools import grep_codebase, read_source, list_dir, find_file_fast, path_exists_fast
                import re as _toolre

                MAX_TOOL_ROUNDS = (
                    25
                    if ("fs.file_write" in question) and ("/tmp/murphy_" in question)
                    else 15
                )  # PATCH-WRITE-REQUIRED-ROUNDS-R254 (2026-05-29): write-required tasks get 25, others 15. R253: Murphy used 23 rounds. # R227 JUSTIFY-GATE. # R226 ROUNDS-RAISE.

                # Build the prompt with TOOL_CALL grammar
                soul_prefix = ""
                if soul_contexts:
                    sc_role = list(soul_contexts.values())[0] if soul_contexts else ""
                    soul_prefix = f"{sc_role}\n\n" if sc_role else ""

                tool_grammar = (
                    "AVAILABLE TOOLS (use these to ground your answer in Murphys real source):\n"
                    "  TOOL_CALL: grep \"<regex>\"                    -- search src/ for a pattern\n"
                    "  TOOL_CALL: read <relative_path>             -- read a Murphy source file\n"
                    "  TOOL_CALL: read <relative_path> <start> <end>  -- read line range\n"
                    "  TOOL_CALL: list <relative_dir>              -- list a directory\n"
                        "  TOOL_CALL: tool <tool_id> <json_kwargs>     -- invoke aionmind tool\n"
                        "    aionmind tools (PATCH-GRAMMAR-TOOLS-R194):\n"
                        "      fs.file_read, fs.file_write, fs.file_append\n"
                        "      sys.shell_exec, sys.env_read\n"
                        "      net.http_get, net.http_post, web.fetch\n"
                        "      data.json_parse, data.json_format\n"
                        "      self.murphy_patch\n"
                        "    Example: TOOL_CALL: tool sys.shell_exec {\"cmd\": \"date -u\"}\n"
                    "\n"
                    "Emit ONE tool call per line at the START of your response if you need info. "
                    "After tool results come back, either issue more TOOL_CALLs or give your final ANSWER.\n"
                    "When ready to finish, prefix your final response with FINAL_ANSWER:\n\n"


                    # PATCH-GRAMMAR-EXEC-ORDER-R212 (2026-05-29): execution-order rules.


                    "\n"


                    "EXECUTION RULES:\n"


                    "  - Never execute or read a file you have not written in this conversation.\n"


                    "  - Write files BEFORE running them. fs.file_write must precede sys.shell_exec.\n"


                    "  - When asked to verify your own work, query state (grep/journalctl/sqlite3)\n"


                    "    BEFORE writing the verify file, and substitute real output into the file content.\n"


                    "  - If a referenced file does not exist, do NOT explore — write it first.\n"
                      "  - PATCH-JUSTIFY-GATE-R227: rounds 1-6 are free. After round 6, each "
                      "TOOL_CALL line MUST be preceded by a JUSTIFY line: "
                      "JUSTIFY: <tool_name> — <one-sentence reason this is needed>\n"
                      "  - Rounds 7+ without a JUSTIFY are rejected. Use the discipline to "
                      "decide whether you actually need another tool call or can write your final answer.\n"
                    "  - PATCH-WRITE-TERMINATOR-R228 (2026-05-29): for any task that requires writing a file, "
                      "the FINAL line of your response MUST be a TOOL_CALL: tool fs.file_write {...} call. "
                      "No narration after it. No \"Final step:\" framing — emit the call directly as your last action. "
                      "R227 evidence: framing the write as a separate \"Final step\" caused you to skip it.\n"
                      "  - PATCH-GRAMMAR-SUBSTITUTION-R214: when writing a verify/report file, "
                    "INCLUDE the actual output of prior tool calls in the content field. "
                    "Never write placeholder strings like [insert output here] or [from grep]. "
                    "Read your own tool results from the conversation and paste them into the content.\n"
                )
                full_prompt = (
                    f"{soul_prefix}"
                    f"You are Murphys executor agent with codebase-read access.\n\n"
                    f"{tool_grammar}"
                    f"BRIEF:\n{question}\n\n"
                    f"Begin. Use tools if helpful, then FINAL_ANSWER:"
                )

                llm = get_llm()
                output_text = ""
                conversation = full_prompt
                tools_called = []

                for round_n in range(MAX_TOOL_ROUNDS):
                    llm_resp = llm.complete(prompt=conversation, max_tokens=1500)
                    # Extract text
                    if hasattr(llm_resp, "content"):
                        resp_text = llm_resp.content
                    elif hasattr(llm_resp, "text"):
                        resp_text = llm_resp.text
                    elif isinstance(llm_resp, str):
                        resp_text = llm_resp
                    elif isinstance(llm_resp, dict):
                        resp_text = (llm_resp.get("content") or llm_resp.get("text") or str(llm_resp))
                    else:
                        resp_text = str(llm_resp)

                    # If LLM says FINAL_ANSWER:, return it
                    if "FINAL_ANSWER:" in resp_text:
                        output_text = resp_text.split("FINAL_ANSWER:", 1)[1].strip()
                        # PATCH-WRITE-ENFORCER-R230 (2026-05-29): Murphy designed this.
                        # If prompt requires a fs.file_write, the last non-empty line of
                        # the response MUST be a TOOL_CALL: tool fs.file_write line.
                        # If missing → ABORT with explicit rejection marker (Murphy R229).
                        try:
                            import re as _r230_re
                            _r230_prompt_needs_write = ("fs.file_write" in question) and ("/tmp/murphy_" in question)  # PATCH-R231-DETECT-AND (2026-05-29 R232 re-ship): Murphy R231 — require both signals. R232 confirmed semantically safe.
                            if _r230_prompt_needs_write:
                                _r230_check_text = resp_text
                                _r230_lines = [ln for ln in _r230_check_text.split("\n") if ln.strip()]
                                _r230_last = _r230_lines[-1].strip() if _r230_lines else ""
                                _r230_ok = bool(_r230_re.match(r"TOOL_CALL:\s*tool\s+fs\.file_write", _r230_last))
                                if not _r230_ok:
                                    logger.info(
                                        "PATCH-WRITE-ENFORCER-R230 ABORT: write-required task did "
                                        "not terminate with fs.file_write. last_line=%r",
                                        _r230_last[:200],
                                    )
                                    output_text = (
                                        "[ENFORCER-R230-ABORT] Write-required task ended without "
                                        "fs.file_write TOOL_CALL. Last line was: " + _r230_last[:200]
                                    )
                                else:
                                    logger.info("PATCH-WRITE-ENFORCER-R230 OK: write-required task terminated correctly")
                        except Exception as _r230_exc:
                            logger.warning("PATCH-WRITE-ENFORCER-R230 check failed: %s", _r230_exc)
                        break

                    # Find TOOL_CALL lines
                    # PATCH-AIONMIND-BRIDGE-R180: added 'tool' to recognized verbs
                    tool_calls = _toolre.findall(
                        r"TOOL_CALL:\s*(grep|read|list|find|exists|tool)\s+(.+?)(?:\n|$)",
                        resp_text,
                    )
                    if not tool_calls:
                        # No more tools and no FINAL_ANSWER — accept what we got
                        output_text = resp_text
                        break

                    tool_results = []
                    # PATCH-DISPATCH-CAP-R196 (2026-05-29): raise cap from 4 → 12 so
                    # write-side TOOL_CALL: tool calls don't get truncated when the
                    # LLM emits exploration grep/read calls first. Also log dispatch.
                    for tool_name, args in tool_calls[:12]:
                        logger.info("R196_DISPATCH tool_name=%r args=%r", tool_name, args[:140])
                        args = args.strip()
                        try:
                            if tool_name == "grep":
                                # PATCH-GREP-SHELLSTYLE-R241 (2026-05-29): Murphy chose option A
                                # in R241 meta-Q — accommodate natural emission. Parses the
                                # shell-style form Murphy actually uses:
                                #   "regex" path/        → pattern + subdir
                                #   "regex" path/file.py → pattern + single-file filter
                                #   "regex"              → pattern only (default subdir=src)
                                # Strips noise flags (-r, -i, --include=...) that Murphy
                                # appends from bash habit. Falls back to clean regex if no quotes.
                                import shlex as _r241_shlex
                                import re as _r241_re
                                raw_args = args.strip()
                                _r241_note = ""
                                pat = raw_args
                                subdir = "src"
                                try:
                                    _r241_tokens = _r241_shlex.split(raw_args)
                                except ValueError:
                                    _r241_tokens = raw_args.split()
                                # Drop noise flags Murphy commonly appends
                                _r241_clean = []
                                _r241_dropped = []
                                for tk in _r241_tokens:
                                    if tk in ("-r", "-R", "-i", "-n", "-l", "-H", "-E"):
                                        _r241_dropped.append(tk); continue
                                    if tk.startswith("--include") or tk.startswith("--exclude"):
                                        _r241_dropped.append(tk); continue
                                    _r241_clean.append(tk)
                                if _r241_clean:
                                    pat = _r241_clean[0]
                                    # second token = path/subdir if it looks pathlike
                                    if len(_r241_clean) >= 2:
                                        cand = _r241_clean[1]
                                        if "/" in cand or cand in ("src", "tests", "scripts", "docs"):
                                            subdir = cand
                                if _r241_dropped or len(_r241_clean) >= 2:
                                    _r241_note = (
                                        "\n[R241 NOTE: shell-style parsed. pattern=%r subdir=%r"
                                        % (pat, subdir)
                                        + (", noise_flags_dropped=%r" % _r241_dropped if _r241_dropped else "")
                                        + ". Grammar: TOOL_CALL: grep <regex> [subdir]]"
                                    )
                                r = grep_codebase(pat, subdir=subdir, max_matches=15)
                                tool_results.append(
                                    f"[grep {pat!r}@{subdir!r}] total={r['total']}, showing first {len(r['matches'])}:\n" +
                                    "\n".join(f"  {m['path']}:{m['line']}  {m['text'][:120]}" for m in r['matches'])
                                    + _r241_note
                                )
                            elif tool_name == "read":
                                parts = args.split()
                                if len(parts) >= 3:
                                    r = read_source(parts[0], line_range=(int(parts[1]), int(parts[2])))
                                else:
                                    r = read_source(parts[0])
                                if r.get("error"):
                                    tool_results.append(f"[read {args}] ERROR: {r['error']}")
                                else:
                                    tool_results.append(
                                        (
                                          # PATCH-READ-DISPLAY-CAP-R235 (2026-05-29): raised from 3000 → 30000.
                                          # R234 found Murphy answered EventBackbone questions wrong because
                                          # the 3000-char cap hid lines past ~90. Append truncation notice
                                          # so Murphy knows to request a line range.
                                          f"[read {r['path']}] {r['lines']} lines, {r['bytes']} bytes:\n```\n{r['content'][:30000]}\n```"
                                          + ("\n[TRUNCATED: only first 30000 of "
                                             + str(r['bytes']) + " chars shown — use 'read <path> <start> <end>' for ranges]"
                                             if r['bytes'] > 30000 else "")
                                      )
                                    )
                            elif tool_name == "list":
                                r = list_dir(args.strip())
                                if r.get("error"):
                                    tool_results.append(f"[list {args}] ERROR: {r['error']}")
                                else:
                                    tool_results.append(
                                        f"[list {r['path']}] {r['total']} entries:\n" +
                                        f"  dirs: {r['dirs'][:20]}\n" +
                                        f"  files: {r['files'][:30]}"
                                    )
                            # PATCH-AIONMIND-BRIDGE-R180: route to aionmind real tools
                            elif tool_name == "tool":
                                _a = args.strip()
                                if " " in _a:
                                    _tid, _kw = _a.split(" ", 1)
                                else:
                                    _tid, _kw = _a, "{}"
                                tool_results.append(_r180_bridge_to_aionmind(_tid, _kw))
                            tools_called.append({"tool": tool_name, "args": args})
                        except Exception as terr:
                            tool_results.append(f"[{tool_name} {args}] ERROR: {terr}")

                    # PATCH-CAF-001: per-round tool-failure ledger.
                    # Any tool that emitted "ERROR:" this round is a failure signal.
                    # The next round (or force-prompt) becomes the fallback.
                    try:
                        for tr in tool_results:
                            if " ERROR:" in tr or "ERROR:" in tr[:30]:
                                # Parse "[tool args] ERROR: msg"
                                hdr = tr.split("]", 1)[0].lstrip("[")
                                tool_attempted = hdr.split(" ", 1)[0] if " " in hdr else hdr
                                err_msg = tr.split("ERROR:", 1)[1].strip()[:120] if "ERROR:" in tr else "unknown"
                                _caf_log(
                                    task_desc=question,
                                    original=f"tool:{tool_attempted}",
                                    failure_signal=err_msg,
                                    fallback=f"round_{round_n+2}_retry",
                                    succeeded=0,  # unknown until later round resolves
                                )
                    except Exception:
                        pass

                    # Feed results back. On the final round, FORCE convergence.
                    is_last_round = (round_n == MAX_TOOL_ROUNDS - 1)
                    convergence_pressure = (
                        "\n\n⚠ FINAL ROUND: you have used your tool budget. "
                    + _caf_hint(question) + " "
                        "You MUST now emit FINAL_ANSWER: with your conclusion based on the tool results above. "
                        "Do NOT request more tools."
                        if is_last_round
                        else "Now issue more TOOL_CALLs if needed, or emit FINAL_ANSWER: with your answer."
                    )
                    conversation = (
                        f"{conversation}\n\n"
                        f"--- TOOL_RESULTS (round {round_n+1}) ---\n"
                        + "\n\n".join(tool_results) +
                        f"\n--- END_TOOL_RESULTS ---\n\n"
                        f"{convergence_pressure}"
                    )

                # If loop ended without FINAL_ANSWER, do ONE more forced conclusion call.
                # PATCH-CAF-001: this is a FALLBACK_SUCCEEDS event — natural
                # tool-loop completion failed, forced re-prompt is the fallback.
                if not output_text:
                    _caf_log(
                        task_desc=question,
                        original="natural_tool_loop_completion",
                        failure_signal="no_FINAL_ANSWER_after_max_rounds",
                        fallback="forced_conclusion_reprompt",
                        succeeded=0,  # updated below if it works
                    )
                    force_prompt = (
                        f"{conversation}\n\n"
                        f"You did not emit FINAL_ANSWER. Based on the tool results gathered above, "
                        f"write a clear, complete answer to the original brief. Start with FINAL_ANSWER:"
                    )
                    try:
                        force_resp = llm.complete(prompt=force_prompt, max_tokens=1500)
                        force_text = (force_resp.content if hasattr(force_resp,"content")
                                       else (force_resp.text if hasattr(force_resp,"text")
                                             else str(force_resp)))
                        if "FINAL_ANSWER:" in force_text:
                            output_text = force_text.split("FINAL_ANSWER:", 1)[1].strip()
                            # PATCH-CAF-001: force-prompt fallback succeeded
                            _caf_log(
                                task_desc=question,
                                original="natural_tool_loop_completion",
                                failure_signal="no_FINAL_ANSWER_after_max_rounds",
                                fallback="forced_conclusion_reprompt",
                                succeeded=1,
                            )
                        else:
                            output_text = force_text
                    except Exception as force_exc:
                        # PATCH-CAF-001: force-prompt itself failed
                        _caf_log(
                            task_desc=question,
                            original="forced_conclusion_reprompt",
                            failure_signal=str(force_exc)[:120],
                            fallback="raw_last_response",
                            succeeded=-1,
                        )
                        output_text = resp_text  # ultimate fallback

                # PATCH-WRITE-ENFORCER-R237-EXITGATE (2026-05-29): R236 found R230 enforcer
                # only fires when FINAL_ANSWER: is in resp_text, but Murphy's failure modes
                # are exactly when it doesn't emit FINAL_ANSWER. This check runs at the return
                # point regardless of how output_text was set. Murphy's R229 abort semantics.
                try:
                    import re as _r237_re
                    _r237_needs_write = ("fs.file_write" in question) and ("/tmp/murphy_" in question)
                    if _r237_needs_write and "[ENFORCER-R230-ABORT]" not in (output_text or ""):
                        _r237_lines = [ln for ln in (output_text or "").split("\n") if ln.strip()]
                        _r237_last = _r237_lines[-1].strip() if _r237_lines else ""
                        _r237_ok = bool(_r237_re.match(r"TOOL_CALL:\s*tool\s+fs\.file_write", _r237_last))
                        if not _r237_ok:
                            logger.info(
                                "PATCH-WRITE-ENFORCER-R237-EXITGATE ABORT: write-required task "
                                "reached return without fs.file_write. last_line=%r",
                                _r237_last[:200],
                            )
                            output_text = (
                                "[ENFORCER-R237-EXITGATE-ABORT] Write-required task ended without "
                                "fs.file_write TOOL_CALL. Last line was: " + _r237_last[:200]
                            )
                        else:
                            logger.info("PATCH-WRITE-ENFORCER-R237-EXITGATE OK")
                except Exception as _r237_exc:
                    logger.warning("PATCH-WRITE-ENFORCER-R237-EXITGATE check failed: %s", _r237_exc)

                logger.info("ExecutorAgent: LLM brief complete — %d chars, %d tool calls",
                            len(output_text), len(tools_called))
                return {
                    "status": "completed",
                    "dag_id": f"llm-{uuid.uuid4().hex[:10]}",
                    "dag_status": "ok",
                    "result": output_text,
                    "brief": question[:200],
                    "agent": "executor",
                    "tools_used": tools_called,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as exc:
                logger.warning("ExecutorAgent LLM path failed: %s — falling back to DAG", exc)
                # fall through to DAG path

                output_text = ""


        # ── LEGACY DAG PATH: pre-approved action (swarm_heartbeat sigs) ──────
        try:
            from src.workflow_dag import build_dag, task_node, get_executor
            dag = build_dag(
                f"exec_{domain}",
                f"Executor: {action[:60]}",
                domain=domain,
                stake=signal.get("stake", "medium"),
                account=signal.get("source", "system"),
            )
            dag.add_node(task_node("execute", action, depends_on=[]))
            result = get_executor().execute(dag)
            return {
                "status": "executed",
                "dag_id": dag.dag_id,
                "dag_status": result.status,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.warning("ExecutorAgent.act error: %s", exc)
            return {"status": "error", "action": action, "error": str(exc)}


_executor_agent: Optional[ExecutorAgent] = None

def get_executor_agent() -> ExecutorAgent:
    global _executor_agent
    if _executor_agent is None:
        _executor_agent = ExecutorAgent()
    return _executor_agent



# ── PATCH-EXECUTOR-SINGLETON-R194 (2026-05-29) ──────────────────────────────
# R193 added a duplicate of get_executor_agent() — R194 collapses to alias.
# Both names now return the SAME ExecutorAgent singleton.
def get_executor():
    """Alias to get_executor_agent() — keep both names callable.
    R193 found workflow_executor uses get_X() pattern; this preserves it."""
    return get_executor_agent()
# ── END PATCH-EXECUTOR-SINGLETON-R194 ────────────────────────────────────────

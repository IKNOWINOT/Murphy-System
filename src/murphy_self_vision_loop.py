# Copyright © 2020 Inoni LLC | License: BSL 1.1
"""Murphy Self-Vision Loop — PATCH-163

Closed-loop self-improvement engine:
  1. SEE    — screenshot Murphy's own pages, detect visual/JS issues
  2. READ   — load relevant source files (HTML, JS, Python) as ground truth
  3. JUDGE  — LLM analyzes screenshots + source → generates fix proposals
  4. GATE   — MurphyCritic reviews each proposal (PASS/WARN/BLOCK)
  5. FIX    — auto-apply PASS proposals; queue WARN for founder; block BLOCK
  6. VERIFY — re-screenshot after fix, diff visual state
  7. RECORD — persist all proposals + outcomes to vision_loop.db

Murphy never hallucinates its own state — it reads the actual files
before proposing any change. Every proposal answers the 7 guiding principles.

Endpoints (wired in app.py):
  POST /api/self/vision/run                — start async loop cycle
  GET  /api/self/vision/status             — current run + last N outcomes
  GET  /api/self/vision/proposals          — all proposals from last run
  POST /api/self/vision/proposals/{id}/apply   — manually apply queued proposal
  POST /api/self/vision/proposals/{id}/reject  — reject a proposal
  GET  /api/self/vision/history            — past run summary log

PATCH-163 | Label: SELF-VISION-001
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import pathlib
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ROOT = pathlib.Path("/opt/Murphy-System")
_DB_PATH = pathlib.Path("/var/lib/murphy-production/vision_loop.db")

# ── Pages Murphy will inspect by default ─────────────────────────────────────
DEFAULT_PAGES = [
    "/",
    "/ui/terminal-architect",
    "/ui/ambient-intelligence",
    "/ui/compliance-dashboard",
    "/ui/game-studio",
    "/ui/forge",
    "/ui/roi-calendar",
    "/ui/self-vision",
    "/ui/workflow-builder",
    "/ui/swarm-dashboard",
]

BASE_URL = "https://murphy.systems"


# ── Enums ────────────────────────────────────────────────────────────────────

class ProposalStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED  = "applied"
    FAILED   = "failed"
    BLOCKED  = "blocked"
    VERIFIED = "verified"


class RunStatus(str, Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class VisionProposal:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    run_id: str = ""
    page_url: str = ""
    target_file: str = ""
    issue_summary: str = ""
    rationale: str = ""          # answers guiding principles 1-7
    patch_content: str = ""      # the actual fix (full file content or diff hint)
    patch_mode: str = "replace"  # "replace" | "inject" | "config"
    critic_verdict: str = "pending"  # PASS / WARN / BLOCK
    critic_issues: List[str] = field(default_factory=list)
    status: ProposalStatus = ProposalStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    applied_at: str = ""
    verified: bool = False
    verification_notes: str = ""
    confidence: float = 0.0


@dataclass
class VisionRun:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    status: RunStatus = RunStatus.RUNNING
    pages_scanned: int = 0
    proposals_generated: int = 0
    proposals_applied: int = 0
    proposals_blocked: int = 0
    proposals_queued: int = 0
    error: str = ""
    triggered_by: str = "system"
    summary: str = ""


# ── Database ──────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            started_at TEXT,
            finished_at TEXT,
            status TEXT,
            pages_scanned INTEGER DEFAULT 0,
            proposals_generated INTEGER DEFAULT 0,
            proposals_applied INTEGER DEFAULT 0,
            proposals_blocked INTEGER DEFAULT 0,
            proposals_queued INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            triggered_by TEXT DEFAULT 'system',
            summary TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            page_url TEXT,
            target_file TEXT,
            issue_summary TEXT,
            rationale TEXT,
            patch_content TEXT,
            patch_mode TEXT DEFAULT 'replace',
            critic_verdict TEXT DEFAULT 'pending',
            critic_issues TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            applied_at TEXT DEFAULT '',
            verified INTEGER DEFAULT 0,
            verification_notes TEXT DEFAULT '',
            confidence REAL DEFAULT 0.0
        );
    """)
    db.commit()
    return db


def _save_run(run: VisionRun):
    db = _get_db()
    db.execute("""
        INSERT OR REPLACE INTO runs
        (id, started_at, finished_at, status, pages_scanned,
         proposals_generated, proposals_applied, proposals_blocked,
         proposals_queued, error, triggered_by, summary)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (run.id, run.started_at, run.finished_at, run.status,
          run.pages_scanned, run.proposals_generated, run.proposals_applied,
          run.proposals_blocked, run.proposals_queued, run.error,
          run.triggered_by, run.summary))
    db.commit()
    db.close()


def _save_proposal(p: VisionProposal):
    db = _get_db()
    db.execute("""
        INSERT OR REPLACE INTO proposals
        (id, run_id, page_url, target_file, issue_summary, rationale,
         patch_content, patch_mode, critic_verdict, critic_issues, status,
         created_at, applied_at, verified, verification_notes, confidence)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (p.id, p.run_id, p.page_url, p.target_file, p.issue_summary,
          p.rationale, p.patch_content, p.patch_mode, p.critic_verdict,
          json.dumps(p.critic_issues), p.status, p.created_at,
          p.applied_at, int(p.verified), p.verification_notes, p.confidence))
    db.commit()
    db.close()


def _load_proposals(run_id: str) -> List[Dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT * FROM proposals WHERE run_id=? ORDER BY created_at", (run_id,)
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["critic_issues"] = json.loads(d.get("critic_issues", "[]"))
        except Exception:
            d["critic_issues"] = []
        result.append(d)
    return result


def _load_all_proposals() -> List[Dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT * FROM proposals ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["critic_issues"] = json.loads(d.get("critic_issues", "[]"))
        except Exception:
            d["critic_issues"] = []
        result.append(d)
    return result


def _load_proposal_by_id(pid: str) -> Optional[Dict]:
    db = _get_db()
    row = db.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
    db.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["critic_issues"] = json.loads(d.get("critic_issues", "[]"))
    except Exception:
        d["critic_issues"] = []
    return d


def _update_proposal_status(pid: str, status: str, **kwargs):
    db = _get_db()
    sets = ["status=?"]
    vals = [status]
    for k, v in kwargs.items():
        sets.append(f"{k}=?")
        vals.append(v)
    vals.append(pid)
    db.execute(f"UPDATE proposals SET {', '.join(sets)} WHERE id=?", vals)
    db.commit()
    db.close()


def _get_last_run() -> Optional[Dict]:
    db = _get_db()
    row = db.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    db.close()
    return dict(row) if row else None


def _get_run_history(limit: int = 20) -> List[Dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Core engine ───────────────────────────────────────────────────────────────

class MurphySelfVisionLoop:
    """PATCH-163: Closed-loop self-improvement via visual + source inspection."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_run: Optional[VisionRun] = None
        self._current_proposals: List[VisionProposal] = []
        logger.info("PATCH-163: MurphySelfVisionLoop initialised")

    # ── Step 1: SEE ──────────────────────────────────────────────────────────

    async def _screenshot_page(self, url: str, session_token: str = "") -> Dict:
        """Screenshot a single page and return metadata + base64 PNG."""
        try:
            from src.visual_inspector import screenshot_url
            result = await screenshot_url(url, full_page=True, session_token=session_token)
            return result
        except Exception as exc:
            logger.warning("Vision screenshot failed for %s: %s", url, exc)
            return {"url": url, "error": str(exc), "status": 0, "png_b64": ""}

    async def _scan_pages(self, pages: List[str], session_token: str = "") -> List[Dict]:
        """Screenshot all pages concurrently (max 4 at a time)."""
        sem = asyncio.Semaphore(4)

        async def bounded(url: str) -> Dict:
            async with sem:
                return await self._screenshot_page(url, session_token)

        tasks = [bounded(p if p.startswith("http") else f"{BASE_URL}{p}") for p in pages]
        return await asyncio.gather(*tasks)

    # ── Step 2: READ ─────────────────────────────────────────────────────────

    def _read_source_file(self, rel_path: str, max_chars: int = 14000) -> str:
        """Read a source file — grounding Murphy in reality, not hallucination."""
        try:
            full = _ROOT / rel_path
            if not full.exists():
                full = _ROOT / "src" / rel_path
            if not full.exists():
                return f"# FILE NOT FOUND: {rel_path}"
            text = full.read_text(encoding="utf-8", errors="replace")
            if len(text) <= max_chars:
                return text
            half = max_chars // 2
            return (
                text[:half]
                + f"\n\n# ─── [{len(text)} total chars — middle truncated] ───\n\n"
                + text[-half:]
            )
        except Exception as exc:
            return f"# ERROR reading {rel_path}: {exc}"

    def _find_source_for_page(self, url: str) -> List[str]:
        """Given a page URL, return the likely source files to read."""
        path = url.replace(BASE_URL, "").strip("/")
        candidates = []

        # HTML page
        if path.startswith("ui/"):
            slug = path[3:]
            candidates.append(f"{slug}.html")
        elif path == "" or path == "/":
            candidates.append("murphy_landing_page.html")

        # Always include the nav and shell CSS for visual issues
        candidates += ["static/murphy-nav.js", "static/murphy-app-shell.css"]

        return candidates

    # ── Step 3: JUDGE ────────────────────────────────────────────────────────

    def _build_judge_prompt(
        self,
        page_url: str,
        page_meta: Dict,
        source_files: Dict[str, str],
    ) -> str:
        """Build the LLM prompt that asks Murphy to judge its own page."""
        js_errors = page_meta.get("js_errors", [])
        broken_imgs = page_meta.get("broken_images", [])
        status = page_meta.get("status", 0)
        load_ms = page_meta.get("load_ms", 0)
        has_screenshot = bool(page_meta.get("png_b64", ""))

        source_block = ""
        for fname, content in source_files.items():
            source_block += f"\n\n=== SOURCE: {fname} ===\n{content[:6000]}"

        return f"""You are Murphy — an AI system that inspects its own pages and fixes them.

PAGE INSPECTED: {page_url}
HTTP STATUS: {status}
LOAD TIME: {load_ms}ms
HAS SCREENSHOT: {has_screenshot}
JS ERRORS: {json.dumps(js_errors)}
BROKEN IMAGES: {json.dumps(broken_imgs)}

{source_block}

TASK: Apply the 7 Engineering Guiding Principles to this page:
1. Does the module do what it was designed to do?
2. What exactly is the module supposed to do (design intent)?
3. What conditions are possible based on the module?
4. What is the expected result at all points of operation?
5. What is the actual result?
6. If problems remain — restart from symptoms, work back through validation
7. Has ancillary code and documentation been updated?

Identify up to 3 specific, actionable issues with this page.
For each issue, output a JSON object (one per line) with these fields:
{{
  "target_file": "relative/path/to/file.html",
  "issue_summary": "one-line description of the problem",
  "rationale": "answers to principles 1-5 for this specific issue",
  "fix_description": "exact description of what to change",
  "confidence": 0.0-1.0,
  "patch_mode": "replace|inject|config"
}}

RULES:
- Only flag REAL issues visible in the source or errors — no hallucinations
- If the page looks healthy, output {{"issue_summary": "HEALTHY", "target_file": "", "confidence": 1.0}}
- Keep fixes minimal — surgical changes only
- Do NOT propose changes to authentication, security middleware, or Shield Wall layers
- Output ONLY the JSON objects, one per line, no other text
"""

    def _judge_page(
        self,
        page_url: str,
        page_meta: Dict,
        source_files: Dict[str, str],
    ) -> List[Dict]:
        """Call LLM to judge a page and return raw proposals."""
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
            prompt = self._build_judge_prompt(page_url, page_meta, source_files)
            _resp = llm.complete(prompt, max_tokens=2048, temperature=0.2)
            response = _resp.content if hasattr(_resp, "content") else str(_resp)

            proposals = []
            for line in response.strip().splitlines():
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("issue_summary") == "HEALTHY":
                        continue
                    if obj.get("target_file") and obj.get("issue_summary"):
                        proposals.append(obj)
                except json.JSONDecodeError:
                    continue
            return proposals
        except Exception as exc:
            logger.error("Judge LLM call failed for %s: %s", page_url, exc)
            return []

    # ── Step 4: BUILD PATCH CONTENT ──────────────────────────────────────────

    def _build_patch_prompt(self, proposal_raw: Dict, source_content: str) -> str:
        """Ask Murphy to generate a surgical OLD→NEW patch for a proposal.

        PATCH-164: For all files, we now request a surgical diff (<<<OLD / >>>NEW format)
        rather than full file replacement.  This allows safe verify-then-apply on protected
        files and reduces LLM token waste on large files.
        """
        target = proposal_raw.get("target_file", "")
        # Show a focused window around the issue rather than the whole file
        relevant_slice = source_content[:12000]

        return f"""You are Murphy. You identified this issue and must generate a surgical fix.

FILE: {target}
ISSUE: {proposal_raw["issue_summary"]}
FIX DESCRIPTION: {proposal_raw.get("fix_description", "")}
RATIONALE: {proposal_raw.get("rationale", "")}

RELEVANT FILE CONTENT (may be truncated):
{relevant_slice}

TASK: Output a surgical patch using EXACTLY this format:
<<<OLD
[the exact existing text to replace — must be a verbatim substring of the file]
>>>NEW
[the replacement text that fixes the issue]
>>>END

RULES:
- The <<<OLD block must be a VERBATIM substring of the file content shown above — COPY IT EXACTLY including leading spaces/tabs
- Include 2-3 lines of context around the broken line in the OLD block so it is unique
- Change the minimum possible — only the lines that are broken
- Do NOT output the whole file
- Do NOT add markdown fences or explanations
- If no patch is needed because the issue is a false positive, output: HEALTHY
- The NEW block must be complete — never truncate mid-line
"""

    def _generate_patch(self, proposal_raw: Dict, source_content: str) -> str:
        """Generate a surgical patch and return it in <<<OLD / >>>NEW / >>>END format.

        PATCH-164: Returns the raw LLM output containing the surgical diff markers.
        _apply_patch will parse and verify the diff before writing.
        """
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
            prompt = self._build_patch_prompt(proposal_raw, source_content)
            _r = llm.complete(prompt, max_tokens=3500, temperature=0.1)
            raw = _r.content if hasattr(_r, "content") else str(_r)
            return raw.strip()
        except Exception as exc:
            logger.error("Patch generation failed: %s", exc)
            return ""

    # ── Step 5: GATE (MurphyCritic) ──────────────────────────────────────────

    def _critic_gate(self, proposal: VisionProposal) -> VisionProposal:
        """Run MurphyCritic on the patch content. Only for .py files."""
        if not proposal.patch_content:
            proposal.critic_verdict = "BLOCK"
            proposal.critic_issues = ["Empty patch content"]
            return proposal

        # Only run AST/critic on Python files
        if proposal.target_file.endswith(".py"):
            try:
                from src.murphy_critic import get_critic
                critic = get_critic()
                result = critic.review(
                    proposal.patch_content,
                    filename=proposal.target_file,
                    context={"patch_source": "self_vision_loop", "run_id": proposal.run_id},
                )
                proposal.critic_verdict = result.verdict  # "PASS", "WARN", "BLOCK"
                proposal.critic_issues = [str(i) for i in result.issues]
            except Exception as exc:
                logger.warning("Critic gate failed: %s", exc)
                proposal.critic_verdict = "WARN"
                proposal.critic_issues = [f"Critic unavailable: {exc}"]
        else:
            # HTML/JS/CSS — run basic safety checks
            dangerous = ["<script>eval(", "document.write(", "innerHTML=", "javascript:void"]
            hits = [d for d in dangerous if d in proposal.patch_content]
            if hits:
                proposal.critic_verdict = "WARN"
                proposal.critic_issues = [f"Potentially dangerous pattern: {h}" for h in hits]
            else:
                proposal.critic_verdict = "PASS"
                proposal.critic_issues = []

        return proposal

    # ── Step 6: FIX ──────────────────────────────────────────────────────────

    def _apply_patch(self, proposal: VisionProposal) -> bool:
        """Apply a surgical OLD→NEW patch to a file.

        PATCH-164: Parses <<<OLD / >>>NEW / >>>END markers from patch_content.
        Verifies the OLD text is a verbatim substring of the current file before writing.
        This works for ALL files including previously-protected nav.js and app-shell.css.
        Falls back to full-replace only for tiny non-critical files with no OLD marker.
        """
        _GARBAGE_MARKERS = (
            "[Murphy Onboard]",
            "API providers unavailable",
            "Request acknowledged: You are Murphy",
        )

        try:
            target = _ROOT / proposal.target_file
            if not target.exists():
                target = _ROOT / "src" / proposal.target_file
            if not target.exists():
                logger.warning("PATCH-164: target not found: %s", proposal.target_file)
                return False

            patch = (proposal.patch_content or "").strip()

            # Reject LLM garbage
            if any(m in patch for m in _GARBAGE_MARKERS):
                logger.warning("PATCH-164: Garbage patch rejected for %s", proposal.target_file)
                return False

            # PATCH-164b: Reject full-file rewrites disguised as patches
            # If patch starts with markdown fence or a full file header comment, it's not a surgical diff
            _FULL_FILE_MARKERS = ("```", "/*\n * murphy-nav.js", "/*\n * murphy-app-shell")
            if any(patch.startswith(m) for m in _FULL_FILE_MARKERS):
                if "<<<OLD" not in patch:
                    logger.warning(
                        "PATCH-164b: Full-file rewrite rejected for %s — LLM ignored surgical diff instruction",
                        proposal.target_file,
                    )
                    return False

            # HEALTHY → no fix needed
            if patch == "HEALTHY" or patch.startswith("HEALTHY"):
                logger.info("PATCH-164: Proposal marked HEALTHY — no write needed for %s", proposal.target_file)
                return True

            # Config mode → log only
            if (proposal.patch_mode or "") == "config":
                logger.info("PATCH-164: config proposal logged (no write): %s", proposal.issue_summary)
                return True

            current_text = target.read_text(encoding="utf-8", errors="replace")

            # ── Parse surgical diff markers ──────────────────────────────────
            if "<<<OLD" in patch and ">>>NEW" in patch:
                try:
                    old_part = patch.split("<<<OLD", 1)[1].split(">>>NEW", 1)[0]
                    new_part = patch.split(">>>NEW", 1)[1]
                    if ">>>END" in new_part:
                        new_part = new_part.split(">>>END", 1)[0]
                    old_text = old_part.strip("\n")
                    new_text = new_part.strip("\n")
                except Exception as parse_err:
                    logger.error("PATCH-164: Failed to parse diff markers: %s", parse_err)
                    return False

                if not old_text:
                    logger.warning("PATCH-164: Empty OLD block for %s", proposal.target_file)
                    return False

                # VERIFY: old_text must be a verbatim substring of the live file
                if old_text not in current_text:
                    logger.warning(
                        "PATCH-164: OLD block not found in %s — patch is stale/hallucinated. Skipping.",
                        proposal.target_file,
                    )
                    proposal.status = "failed"
                    return False

                # Apply surgical replace
                patched_text = current_text.replace(old_text, new_text, 1)
                backup = target.with_suffix(target.suffix + f".bak_vision_{proposal.id}")
                backup.write_bytes(target.read_bytes())
                target.write_text(patched_text, encoding="utf-8")
                logger.info(
                    "PATCH-164: Surgical fix applied to %s (%d chars → %d chars)",
                    proposal.target_file, len(old_text), len(new_text),
                )
                return True

            else:
                # No diff markers — fall back to full replace only for non-JS/CSS files
                if proposal.target_file.endswith((".js", ".css")):
                    logger.warning(
                        "PATCH-164: Full-replace rejected for %s — JS/CSS require surgical diff",
                        proposal.target_file,
                    )
                    return False

                # For HTML files: full replace is acceptable
                if not patch:
                    logger.warning("PATCH-164: Empty patch for %s", proposal.target_file)
                    return False

                backup = target.with_suffix(target.suffix + f".bak_vision_{proposal.id}")
                backup.write_bytes(target.read_bytes())
                target.write_text(patch, encoding="utf-8")
                logger.info("PATCH-164: Full replace applied to %s", proposal.target_file)
                return True

        except Exception as exc:
            logger.error("PATCH-164: Apply patch failed for %s: %s", proposal.target_file, exc)
            return False

    # ── Step 7: VERIFY ───────────────────────────────────────────────────────

    async def _verify_page(self, url: str, proposal: VisionProposal, session_token: str = "") -> bool:
        """Re-screenshot after fix. Check for JS errors disappearing."""
        try:
            await asyncio.sleep(1)  # brief settle
            result = await self._screenshot_page(url, session_token)
            js_errors = result.get("js_errors", [])
            status = result.get("status", 0)
            if status == 200 and len(js_errors) == 0:
                proposal.verified = True
                proposal.verification_notes = f"Post-fix screenshot: 200 OK, 0 JS errors"
                return True
            else:
                proposal.verification_notes = f"Post-fix: status={status}, js_errors={js_errors}"
                return False
        except Exception as exc:
            proposal.verification_notes = f"Verification error: {exc}"
            return False

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def run_cycle(
        self,
        pages: Optional[List[str]] = None,
        session_token: str = "",
        triggered_by: str = "system",
        auto_apply: bool = True,
    ) -> VisionRun:
        """Run one full see→read→judge→gate→fix→verify cycle."""
        with self._lock:
            if self._current_run and self._current_run.status == RunStatus.RUNNING:
                logger.warning("Vision loop already running — skipping")
                return self._current_run

        pages = pages or DEFAULT_PAGES
        run = VisionRun(triggered_by=triggered_by)
        self._current_run = run
        self._current_proposals = []
        _save_run(run)

        try:
            logger.info("PATCH-163: Vision loop starting — %d pages", len(pages))

            # ── STEP 1: SEE ──────────────────────────────────────────────────
            page_results = await self._scan_pages(pages, session_token)
            run.pages_scanned = len(page_results)
            _save_run(run)

            all_proposals: List[VisionProposal] = []

            for page_meta in page_results:
                url = page_meta.get("url", "")
                if not url:
                    continue

                # ── STEP 2: READ ─────────────────────────────────────────────
                source_file_names = self._find_source_for_page(url)
                source_files = {}
                for fname in source_file_names:
                    content = self._read_source_file(fname)
                    if not content.startswith("# FILE NOT FOUND"):
                        source_files[fname] = content

                # ── STEP 3: JUDGE ────────────────────────────────────────────
                raw_proposals = self._judge_page(url, page_meta, source_files)

                for raw in raw_proposals:
                    target_file = raw.get("target_file", "")
                    if not target_file:
                        continue

                    # ── READ SOURCE FOR PATCH GENERATION ────────────────────
                    src_content = self._read_source_file(target_file)

                    # ── GENERATE PATCH ───────────────────────────────────────
                    patch_content = self._generate_patch(raw, src_content)

                    proposal = VisionProposal(
                        run_id=run.id,
                        page_url=url,
                        target_file=target_file,
                        issue_summary=raw.get("issue_summary", ""),
                        rationale=raw.get("rationale", ""),
                        patch_content=patch_content,
                        patch_mode=raw.get("patch_mode", "replace"),
                        confidence=float(raw.get("confidence", 0.5)),
                    )

                    # ── STEP 4: CRITIC GATE ──────────────────────────────────
                    proposal = self._critic_gate(proposal)

                    if proposal.critic_verdict == "BLOCK":
                        proposal.status = ProposalStatus.BLOCKED
                        run.proposals_blocked += 1
                    elif proposal.critic_verdict == "WARN":
                        proposal.status = ProposalStatus.PENDING  # queue for human
                        run.proposals_queued += 1
                    else:
                        # PASS — auto-apply if enabled
                        if auto_apply and patch_content:
                            # ── STEP 5: FIX ──────────────────────────────────
                            ok = self._apply_patch(proposal)
                            if ok:
                                proposal.status = ProposalStatus.APPLIED
                                proposal.applied_at = datetime.now(timezone.utc).isoformat()
                                run.proposals_applied += 1

                                # ── STEP 6: VERIFY ────────────────────────────
                                await self._verify_page(url, proposal, session_token)
                                if proposal.verified:
                                    proposal.status = ProposalStatus.VERIFIED
                            else:
                                proposal.status = ProposalStatus.FAILED
                        else:
                            proposal.status = ProposalStatus.PENDING
                            run.proposals_queued += 1

                    all_proposals.append(proposal)
                    _save_proposal(proposal)

            run.proposals_generated = len(all_proposals)
            self._current_proposals = all_proposals

            # ── Build summary ─────────────────────────────────────────────────
            applied = sum(1 for p in all_proposals if p.status in (ProposalStatus.APPLIED, ProposalStatus.VERIFIED))
            verified = sum(1 for p in all_proposals if p.verified)
            blocked = sum(1 for p in all_proposals if p.status == ProposalStatus.BLOCKED)
            queued = sum(1 for p in all_proposals if p.status == ProposalStatus.PENDING)

            run.summary = (
                f"Scanned {run.pages_scanned} pages. "
                f"Generated {len(all_proposals)} proposals: "
                f"{applied} applied, {verified} verified, "
                f"{queued} queued for review, {blocked} blocked by Critic."
            )
            run.status = RunStatus.COMPLETED
            run.finished_at = datetime.now(timezone.utc).isoformat()
            _save_run(run)

            logger.info("PATCH-163: Vision loop complete — %s", run.summary)

        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc).isoformat()
            _save_run(run)
            logger.error("PATCH-163: Vision loop failed: %s", exc)

        return run

    # ── Manual proposal application ───────────────────────────────────────────

    def apply_proposal(self, proposal_id: str) -> Dict:
        """Manually apply a queued (WARN/PENDING) proposal."""
        p_data = _load_proposal_by_id(proposal_id)
        if not p_data:
            return {"success": False, "error": "Proposal not found"}
        if p_data["status"] not in ("pending", "approved"):
            return {"success": False, "error": f"Cannot apply proposal in status: {p_data['status']}"}

        proposal = VisionProposal(**{
            k: v for k, v in p_data.items()
            if k in VisionProposal.__dataclass_fields__
        })

        ok = self._apply_patch(proposal)
        if ok:
            _update_proposal_status(
                proposal_id, "applied",
                applied_at=datetime.now(timezone.utc).isoformat()
            )
            return {"success": True, "message": f"Proposal {proposal_id} applied"}
        else:
            _update_proposal_status(proposal_id, "failed")
            return {"success": False, "error": "Failed to write patch to disk"}

    def reject_proposal(self, proposal_id: str) -> Dict:
        """Reject a queued proposal."""
        _update_proposal_status(proposal_id, "rejected")
        return {"success": True, "message": f"Proposal {proposal_id} rejected"}

    # ── Status accessors ──────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        last_run = _get_last_run()
        current = None
        if self._current_run:
            current = {
                "id": self._current_run.id,
                "status": self._current_run.status,
                "pages_scanned": self._current_run.pages_scanned,
                "proposals_generated": len(self._current_proposals),
                "started_at": self._current_run.started_at,
            }
        return {
            "engine": "MurphySelfVisionLoop",
            "patch": "PATCH-163",
            "current_run": current,
            "last_run": last_run,
            "db_path": str(_DB_PATH),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_vision_loop: Optional[MurphySelfVisionLoop] = None
_vision_lock = threading.Lock()


def get_vision_loop() -> MurphySelfVisionLoop:
    global _vision_loop
    with _vision_lock:
        if _vision_loop is None:
            _vision_loop = MurphySelfVisionLoop()
    return _vision_loop

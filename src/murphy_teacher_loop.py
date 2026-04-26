"""
src/murphy_teacher_loop.py
PATCH-103c: Murphy Teacher Loop

The teacher/student protocol:
  1. Steve (teacher) commands Murphy to fix a specific gap
  2. Murphy runs its full pipeline: evaluate → CIDP → Model Team → PCC → draft patch
  3. Murphy submits its homework (proposed patch) for review
  4. Steve evaluates: grade (A-F), feedback, pass/fail
  5. If pass → patch applied. If fail → Murphy revises.
  6. All sessions persisted to SQLite. Full audit trail.

This is NOT Steve writing patches. This is Murphy writing patches
and Steve evaluating whether Murphy's work is good enough.

The teacher grades the homework. Murphy does the work.

PATCH: 103c
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import threading
import ast
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)

_DB_PATH = "/var/lib/murphy-production/teacher_loop.db"

# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class HomeworkAssignment:
    """A task Steve gives Murphy to fix."""
    id:             str
    gap_id:         str
    description:    str             # what needs to be fixed
    acceptance:     List[str]       # what "done" looks like (test criteria)
    assigned_at:    str
    deadline_hint:  str             # e.g. "fix this cycle"
    teacher_notes:  str = ""        # Steve's guidance

@dataclass
class HomeworkSubmission:
    """Murphy's proposed patch — submitted for grading."""
    id:             str
    assignment_id:  str
    submitted_at:   str
    intent:         str             # what Murphy says it's doing
    target_file:    str             # which file it's patching
    target_function: str
    proposed_code:  str             # the actual code Murphy wrote
    murphy_notes:   str             # Murphy's explanation
    cidp_verdict:   str             # what CIDP said
    model_team_verdict: str         # what Model Team said
    pcc_directive:  str             # what PCC said
    syntax_ok:      bool            # did it pass syntax check
    revision:       int = 1         # which revision attempt

@dataclass
class TeacherGrade:
    """Steve's evaluation of Murphy's homework."""
    id:             str
    submission_id:  str
    graded_at:      str
    grade:          str             # A / B / C / D / F
    score:          float           # 0.0–1.0
    passed:         bool            # True = apply the patch
    feedback:       str             # what Murphy needs to fix/learn
    specific_issues: List[str]      # line-level or logic-level issues
    apply_patch:    bool            # Steve explicitly approves application
    revision_request: Optional[str] = None  # if failed, what to redo

@dataclass
class TeacherSession:
    """Full session: assignment → submissions → grades → final outcome."""
    id:             str
    assignment:     HomeworkAssignment
    submissions:    List[HomeworkSubmission] = field(default_factory=list)
    grades:         List[TeacherGrade] = field(default_factory=list)
    final_outcome:  str = "pending"   # pending / passed / failed / abandoned
    patch_applied:  bool = False
    completed_at:   Optional[str] = None

# ── Database ──────────────────────────────────────────────────────────────────

class TeacherDB:
    def __init__(self, path: str = _DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._path = path
        self._init()

    def _init(self):
        with sqlite3.connect(self._path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS grades (
                    id TEXT PRIMARY KEY,
                    submission_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sub_assign ON submissions(assignment_id);
                CREATE INDEX IF NOT EXISTS idx_grade_assign ON grades(assignment_id);
            """)

    def save_assignment(self, a: HomeworkAssignment):
        with sqlite3.connect(self._path) as conn:
            conn.execute("INSERT OR REPLACE INTO assignments VALUES (?,?,?)",
                         (a.id, json.dumps(asdict(a)), time.time()))

    def save_submission(self, s: HomeworkSubmission):
        with sqlite3.connect(self._path) as conn:
            conn.execute("INSERT OR REPLACE INTO submissions VALUES (?,?,?,?)",
                         (s.id, s.assignment_id, json.dumps(asdict(s)), time.time()))

    def save_grade(self, g: TeacherGrade, assignment_id: str):
        with sqlite3.connect(self._path) as conn:
            conn.execute("INSERT OR REPLACE INTO grades VALUES (?,?,?,?,?)",
                         (g.id, g.submission_id, assignment_id, json.dumps(asdict(g)), time.time()))

    def save_session(self, sess: TeacherSession):
        with sqlite3.connect(self._path) as conn:
            d = {
                "id": sess.id,
                "assignment": asdict(sess.assignment),
                "submissions": [asdict(s) for s in sess.submissions],
                "grades": [asdict(g) for g in sess.grades],
                "final_outcome": sess.final_outcome,
                "patch_applied": sess.patch_applied,
                "completed_at": sess.completed_at,
            }
            conn.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?)",
                         (sess.id, json.dumps(d), time.time()))

    def get_sessions(self, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                "SELECT data_json FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def get_session(self, session_id: str) -> Optional[Dict]:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                "SELECT data_json FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self._path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            passed = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE json_extract(data_json,'$.final_outcome')='passed'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE json_extract(data_json,'$.final_outcome')='failed'"
            ).fetchone()[0]
            applied = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE json_extract(data_json,'$.patch_applied')=1"
            ).fetchone()[0]
        return {
            "total_sessions": total,
            "passed": passed,
            "failed": failed,
            "applied": applied,
            "pending": total - passed - failed,
        }

# ── Teacher Loop Engine ───────────────────────────────────────────────────────

class TeacherLoopEngine:
    """
    PATCH-103c: The teacher/student loop.

    Steve commands → Murphy works → Murphy submits → Steve grades → repeat until pass or abandon.

    Murphy's homework goes through its full internal pipeline:
    CIDP → Model Team → PCC → LLM draft → syntax check → submission.

    Steve evaluates: correctness, safety, elegance, alignment with engineering principles.
    If passed: patch applied live. If failed: Murphy revises.
    """

    MAX_REVISIONS = 3

    def __init__(self):
        self._db = TeacherDB()
        self._lock = threading.Lock()
        logger.info("TeacherLoopEngine initialized — PATCH-103c")

    # ── Assignment creation ───────────────────────────────────────────────────

    def assign(
        self,
        gap_id: str,
        description: str,
        acceptance: List[str],
        teacher_notes: str = "",
    ) -> TeacherSession:
        """Steve creates an assignment for Murphy."""
        assignment = HomeworkAssignment(
            id            = f"assign-{uuid.uuid4().hex[:8]}",
            gap_id        = gap_id,
            description   = description,
            acceptance    = acceptance,
            assigned_at   = datetime.now(timezone.utc).isoformat(),
            deadline_hint = "this session",
            teacher_notes = teacher_notes,
        )
        session = TeacherSession(
            id         = f"session-{uuid.uuid4().hex[:8]}",
            assignment = assignment,
        )
        self._db.save_assignment(assignment)
        self._db.save_session(session)
        logger.info("Assignment created: %s — %s", assignment.id, description[:60])
        return session

    # ── Murphy does its homework ──────────────────────────────────────────────

    def murphy_attempt(self, session: TeacherSession) -> HomeworkSubmission:
        """
        Murphy runs its full internal pipeline to attempt the assignment.
        Does NOT apply the patch — just produces the draft for grading.
        """
        assignment = session.assignment
        revision = len(session.submissions) + 1
        prior_feedback = [g.feedback for g in session.grades] if session.grades else []

        logger.info("Murphy attempting assignment %s (revision %d)", assignment.id, revision)

        # Step 1: CIDP investigates the intent
        cidp_verdict = "proceed"
        try:
            from src.criminal_investigation_protocol import investigate as cidp_investigate
            report = cidp_investigate(
                intent=f"Self-patch: {assignment.description}",
                context={
                    "gap_id": assignment.gap_id,
                    "revision": revision,
                    "teacher_notes": assignment.teacher_notes,
                }
            )
            cidp_verdict = report.verdict
            if report.verdict == "blocked":
                return HomeworkSubmission(
                    id               = f"sub-{uuid.uuid4().hex[:8]}",
                    assignment_id    = assignment.id,
                    submitted_at     = datetime.now(timezone.utc).isoformat(),
                    intent           = assignment.description,
                    target_file      = "BLOCKED",
                    target_function  = "BLOCKED",
                    proposed_code    = "",
                    murphy_notes     = f"CIDP blocked this intent: {report.summary}",
                    cidp_verdict     = "blocked",
                    model_team_verdict = "N/A",
                    pcc_directive    = "N/A",
                    syntax_ok        = False,
                    revision         = revision,
                )
        except Exception as e:
            cidp_verdict = f"error: {e}"

        # Step 2: LLM drafts the patch
        proposed_code = ""
        murphy_notes  = ""
        target_file   = "unknown"
        target_fn     = "unknown"
        model_team_verdict = "not_run"
        pcc_directive = "HOLD"

        try:
            from src.llm_provider import get_llm
            llm = get_llm()

            # Build a rich context for Murphy
            prior_str = "\n".join(f"- {fb}" for fb in prior_feedback) if prior_feedback else "None (first attempt)"
            accept_str = "\n".join(f"- {a}" for a in assignment.acceptance)

            prompt = (
                f"You are Murphy's self-modification engine. You must write a Python patch to fix a gap.\n\n"
                f"ASSIGNMENT: {assignment.description}\n\n"
                f"ACCEPTANCE CRITERIA (your patch must satisfy ALL of these):\n{accept_str}\n\n"
                f"TEACHER NOTES: {assignment.teacher_notes or 'None'}\n\n"
                f"PRIOR FEEDBACK (from previous failed attempts):\n{prior_str}\n\n"
                f"ENGINEERING PRINCIPLES (apply all 10):\n"
                f"1. Does the module do what it was designed to do?\n"
                f"2. What exactly is the module supposed to do?\n"
                f"3. What conditions are possible?\n"
                f"4. Does the test profile reflect the full range?\n"
                f"5. What is the expected result at all points of operation?\n"
                f"6. What is the actual result?\n"
                f"7. If problems remain — restart from symptoms\n"
                f"8. Has ancillary code and documentation been updated?\n"
                f"9. Has hardening been applied?\n"
                f"10. Has the module been commissioned after those steps?\n\n"
                f"CONSTRAINTS:\n"
                f"- Never touch Shield Wall layers without explicit approval\n"
                f"- Always add the PATCH number in docstrings\n"
                f"- Syntax must be valid Python\n"
                f"- Include a clear docstring explaining what changed and why\n\n"
                f"OUTPUT FORMAT (JSON only, no markdown):\n"
                f'{{"target_file": "src/example.py", "target_function": "function_name", '
                f'"code": "...full python code...", "notes": "explanation of approach and what changed"}}'
            )

            result = llm.complete(
                prompt,
                system=(
                    "You are Murphy's internal self-modification engine writing Python patches. "
                    "Return ONLY valid JSON with keys: target_file, target_function, code, notes. "
                    "No markdown. No explanation outside the JSON."
                ),
                temperature=0.15,
                max_tokens=2000,
            )

            if result and result.content:
                raw = result.content.strip()
                # Strip markdown code fences if present
                if "```" in raw:
                    raw = re.sub(r"```(?:json)?\n?", "", raw).strip()
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(raw[start:end])
                    except json.JSONDecodeError:
                        # Try to extract code block from malformed JSON
                        parsed = {"code": raw, "notes": "LLM returned non-JSON", "target_file": "unknown", "target_function": "unknown"}
                    proposed_code = parsed.get("code", "")
                    murphy_notes  = parsed.get("notes", "")
                    target_file   = parsed.get("target_file", "unknown")
                    target_fn     = parsed.get("target_function", "unknown")

        except Exception as e:
            murphy_notes = f"LLM draft failed: {e}"
            proposed_code = f"# LLM draft failed: {e}"

        # Step 3: Syntax check Murphy's work
        syntax_ok = False
        if proposed_code:
            try:
                ast.parse(proposed_code)
                syntax_ok = True
            except SyntaxError as se:
                murphy_notes += f"\n[SYNTAX ERROR line {se.lineno}: {se.msg}]"

        # Step 4: PCC quick gate
        try:
            from src.pcc import pcc_engine
            pcc_result = pcc_engine.compute(
                session_id   = session.id,
                state_vector = {"D5": 0.1, "D8": 0.15},
                causal_chain = "autonomy_preservation",
                trajectory_len = revision,
                d9_balance   = 0.5,
                assumptions  = [assignment.description],
            )
            pcc_directive = pcc_result.directive
        except Exception:
            pcc_directive = "HOLD"

        # Step 5: Model Team quick deliberate
        try:
            from src.model_team import deliberate as model_team_deliberate
            team_result = model_team_deliberate(
                task    = f"Review proposed patch: {assignment.description}",
                domain  = "self_modification",
                account = {"role": "owner"},
            )
            model_team_verdict = team_result.get("verdict", "unclear")
        except Exception as e:
            model_team_verdict = f"error: {str(e)[:40]}"

        sub = HomeworkSubmission(
            id               = f"sub-{uuid.uuid4().hex[:8]}",
            assignment_id    = assignment.id,
            submitted_at     = datetime.now(timezone.utc).isoformat(),
            intent           = assignment.description,
            target_file      = target_file,
            target_function  = target_fn,
            proposed_code    = proposed_code,
            murphy_notes     = murphy_notes,
            cidp_verdict     = cidp_verdict,
            model_team_verdict = str(model_team_verdict)[:100],
            pcc_directive    = pcc_directive,
            syntax_ok        = syntax_ok,
            revision         = revision,
        )

        session.submissions.append(sub)
        self._db.save_submission(sub)
        self._db.save_session(session)
        logger.info("Murphy submitted revision %d for %s — syntax_ok=%s", revision, assignment.id, syntax_ok)
        return sub

    # ── Steve grades Murphy's homework ────────────────────────────────────────

    def grade(
        self,
        session: TeacherSession,
        submission: HomeworkSubmission,
        grade_letter: str,
        feedback: str,
        specific_issues: Optional[List[str]] = None,
        apply_patch: bool = False,
        revision_request: Optional[str] = None,
    ) -> TeacherGrade:
        """Steve evaluates Murphy's submission."""
        score_map = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "F": 0.0}
        score = score_map.get(grade_letter.upper(), 0.0)
        passed = grade_letter.upper() in ("A", "B") and submission.syntax_ok

        grade = TeacherGrade(
            id               = f"grade-{uuid.uuid4().hex[:8]}",
            submission_id    = submission.id,
            graded_at        = datetime.now(timezone.utc).isoformat(),
            grade            = grade_letter.upper(),
            score            = score,
            passed           = passed,
            feedback         = feedback,
            specific_issues  = specific_issues or [],
            apply_patch      = apply_patch and passed,
            revision_request = revision_request,
        )

        session.grades.append(grade)
        self._db.save_grade(grade, session.assignment.id)

        # Apply patch if approved
        patch_applied = False
        if grade.apply_patch and submission.proposed_code and submission.syntax_ok:
            try:
                from src.self_modification import SelfModificationEngine
                sme = SelfModificationEngine()
                result = sme.write_patch(
                    intent      = submission.intent,
                    new_content = submission.proposed_code,
                    target_path = submission.target_file,
                )
                patch_applied = result.success
                if result.success:
                    logger.info("PATCH APPLIED: %s → %s", session.assignment.gap_id, submission.target_file)
                else:
                    logger.warning("Patch application failed: %s", result.error)
                    grade.apply_patch = False
            except Exception as e:
                logger.error("write_patch error: %s", e)

        # Update session outcome
        if grade.passed:
            session.final_outcome = "passed"
            session.patch_applied = patch_applied
            session.completed_at  = datetime.now(timezone.utc).isoformat()
        elif len(session.submissions) >= self.MAX_REVISIONS:
            session.final_outcome = "failed"
            session.completed_at  = datetime.now(timezone.utc).isoformat()
        # else still pending — Murphy needs to revise

        self._db.save_session(session)
        logger.info("Graded %s → %s (passed=%s, applied=%s)", submission.id, grade_letter, passed, patch_applied)
        return grade

    # ── Batch command: assign + Murphy attempts in one call ───────────────────

    def command_and_attempt(
        self,
        gap_id: str,
        description: str,
        acceptance: List[str],
        teacher_notes: str = "",
    ) -> Dict[str, Any]:
        """
        One-call: Steve assigns, Murphy immediately attempts.
        Returns the session + submission for Steve to evaluate.
        """
        session = self.assign(gap_id, description, acceptance, teacher_notes)
        submission = self.murphy_attempt(session)
        return {
            "session":    asdict(session.assignment),
            "session_id": session.id,
            "submission": asdict(submission),
            "ready_for_grading": True,
            "syntax_ok":  submission.syntax_ok,
            "cidp":       submission.cidp_verdict,
            "pcc":        submission.pcc_directive,
            "code_preview": submission.proposed_code[:500] if submission.proposed_code else "(none)",
        }

    # ── Steve's dashboard ─────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        sessions = self._db.get_sessions(limit=10)
        stats    = self._db.stats()
        recent   = []
        for s in sessions[:5]:
            recent.append({
                "session_id":    s["id"],
                "gap_id":        s["assignment"]["gap_id"],
                "description":   s["assignment"]["description"][:60],
                "outcome":       s["final_outcome"],
                "patch_applied": s["patch_applied"],
                "revisions":     len(s["submissions"]),
                "grades":        [g["grade"] for g in s["grades"]],
            })
        return {
            "stats":   stats,
            "recent":  recent,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
teacher_loop = TeacherLoopEngine()

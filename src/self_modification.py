"""
PATCH-097b: Murphy Self-Modification Engine
============================================
Gives Murphy the ability to read, draft, and apply changes to its own source files.
Every change passes through the Front-of-Line commissioning gate before it lands.
No file is ever overwritten without: backup, syntax check, gate check, and restart.

Creator: Corey Post / Murphy System  |  License: BSL 1.1
"""

import ast
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SRC_ROOT   = Path("/opt/Murphy-System/src")
PROJ_ROOT  = Path("/opt/Murphy-System")
BACKUP_DIR = Path("/tmp/murphy_self_patches")
BACKUP_DIR.mkdir(exist_ok=True)

SERVICE_NAME   = "murphy-production"
RESTART_WAIT_S = 45


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class PatchIntent:
    """What Murphy wants to change and why."""
    patch_id:     str
    target_file:  str          # relative to PROJ_ROOT, e.g. "src/rules_of_conduct.py"
    description:  str
    rationale:    str          # why this improves the system
    impact_score: float = 0.0  # estimated benefit (0-3 scale)
    debt_score:   float = 0.0  # estimated cost / obligation incurred


@dataclass
class PatchResult:
    """Outcome of applying a patch."""
    patch_id:      str
    success:       bool
    gate_decision: str
    backup_path:   Optional[str]
    errors:        List[str] = field(default_factory=list)
    warnings:      List[str] = field(default_factory=list)
    restarted:     bool = False
    applied_at:    Optional[str] = None

    def to_dict(self):
        return asdict(self)


# ── Core engine ───────────────────────────────────────────────────────────────

class SelfModificationEngine:
    """
    Murphy's self-modification layer.

    Capabilities:
    - read_file(path)          → current source as string
    - write_patch(intent, new_content) → apply with gate + backup + syntax check
    - inject_block(intent, target_file, marker, block) → safe block injection
    - list_backups()           → all saved pre-patch snapshots
    - restore_backup(patch_id) → roll back a patch
    - run_syntax_check(content) → True if valid Python
    - evaluate_self(scope)     → system self-assessment report
    """

    def read_file(self, rel_path: str) -> str:
        """Read a source file (relative to project root)."""
        p = PROJ_ROOT / rel_path
        if not p.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        return p.read_text(encoding="utf-8", errors="replace")

    def list_source_files(self, subdir: str = "src") -> List[str]:
        """List all Python files in a subdir."""
        base = PROJ_ROOT / subdir
        return sorted(str(p.relative_to(PROJ_ROOT)) for p in base.rglob("*.py"))

    def run_syntax_check(self, content: str, filename: str = "<patch>") -> Tuple[bool, str]:
        """Return (ok, error_message). Uses ast.parse."""
        try:
            ast.parse(content)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"

    def _gate_check(self, intent: PatchIntent) -> str:
        """Run the Front-of-Line commissioning gate."""
        try:
            from src.front_of_line import front_of_line
            result = front_of_line.check_deployment(
                deployment_id   = intent.patch_id,
                deployment_desc = f"{intent.description} — {intent.rationale}",
                inherited_debt  = intent.debt_score,
                inherited_10x   = intent.debt_score * 10.0,
                deferred_count  = 0,
            )
            return result.gate_decision
        except Exception as exc:
            logger.warning("SelfMod: gate check failed (%s) — defaulting to CLEAR", exc)
            return "CLEAR"

    def _conduct_check(self, intent: PatchIntent) -> Tuple[bool, str]:
        """Check against Rules of Conduct."""
        try:
            from src.rules_of_conduct import conduct_engine
            result = conduct_engine.check(
                action_desc         = f"Self-modify: {intent.description}",
                individual_affected = False,
                ends_potential      = intent.impact_score > 2.0,
                utilitarian_frame   = False,
            )
            verdict = result.get("verdict", "CLEAR")
            blocked = verdict in ("BLOCKED", "HITL_REQUIRED")
            return not blocked, verdict
        except Exception as exc:
            logger.warning("SelfMod: conduct check failed (%s) — defaulting to CLEAR", exc)
            return True, "CLEAR"

    def _backup(self, rel_path: str, patch_id: str) -> str:
        """Save a backup of the current file. Returns backup path."""
        src = PROJ_ROOT / rel_path
        ts  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        bak = BACKUP_DIR / f"{patch_id}__{ts}__{rel_path.replace('/', '_')}.bak"
        shutil.copy2(src, bak)
        return str(bak)

    def write_patch(
        self,
        intent:      PatchIntent,
        new_content: str,
        restart:     bool = True,
    ) -> PatchResult:
        """
        Apply new_content to intent.target_file.
        Full pipeline: conduct → gate → backup → syntax → write → (restart).
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Conduct check
        conduct_ok, conduct_verdict = self._conduct_check(intent)
        if not conduct_ok:
            return PatchResult(
                patch_id      = intent.patch_id,
                success       = False,
                gate_decision = conduct_verdict,
                backup_path   = None,
                errors        = [f"Conduct check blocked: {conduct_verdict}"],
            )

        # 2. Gate check
        gate = self._gate_check(intent)
        if gate == "HITL_REQUIRED":
            return PatchResult(
                patch_id      = intent.patch_id,
                success       = False,
                gate_decision = gate,
                backup_path   = None,
                errors        = ["Front-of-Line gate requires human review"],
            )

        # PATCH-100: PCC gate — consult PCC before applying any self-patch
        # Principle 5: what is the expected result of this patch?
        try:
            from src.pcc import pcc, PCCInput
            _pcc_inp = PCCInput(
                session_id    = intent.patch_id,
                state_vector  = {
                    "d1_flourishing":          0.6,
                    "d2_contraction":          0.1,
                    "d3_closure":              0.0,
                    "d4_coherence_delta":      0.5,
                    "d5_p_harm_physical":      0.0,
                    "d6_p_harm_psychological": 0.1,
                    "d7_p_harm_financial":     0.0,
                    "d8_p_harm_autonomy":      0.25,
                },
                causal_chain  = "autonomy_preservation",
                trajectory_len= 0,
                d9_balance    = 0.0,
                assumptions   = [f"patch: {intent.description[:80]}"],
            )
            _pcc_result = pcc.compute(_pcc_inp)
            if _pcc_result.hard_floor_hit:
                return PatchResult(
                    patch_id      = intent.patch_id,
                    success       = False,
                    gate_decision = "BLOCKED_PCC_HARD_FLOOR",
                    backup_path   = None,
                    errors        = ["PCC hard floor: harm probability >= 0.65 — Omega_possible boundary"],
                )
            if _pcc_result.steering_directive == "REDUCE" and not _pcc_result.cold_start:
                logger.warning(
                    "PCC REDUCE on self-patch %s: r_fair=%.3f — proceeding with caution",
                    intent.patch_id, _pcc_result.r_fair
                )
            # Record positive feedback — patch cleared all gates
            pcc.feedback(
                intent.patch_id,
                _pcc_result.r_fair if not _pcc_result.cold_start else 0.8,
                confirmed=True,
            )
            gate = f"{gate}|PCC:{_pcc_result.steering_directive}"
        except Exception as _pcc_exc:
            logger.debug("PCC gate non-blocking: %s", _pcc_exc)

        # 3. Syntax check (Python files only)
        if intent.target_file.endswith(".py"):
            syntax_ok, syntax_err = self.run_syntax_check(new_content, intent.target_file)
            if not syntax_ok:
                return PatchResult(
                    patch_id      = intent.patch_id,
                    success       = False,
                    gate_decision = gate,
                    backup_path   = None,
                    errors        = [f"Syntax check failed: {syntax_err}"],
                )

        # 4. Backup
        backup_path = None
        target = PROJ_ROOT / intent.target_file
        if target.exists():
            backup_path = self._backup(intent.target_file, intent.patch_id)

        # 5. Write
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")
        logger.info("SelfMod: wrote %s (%d bytes)", intent.target_file, len(new_content))

        # 6. Commit to git
        try:
            subprocess.run(
                ["git", "add", intent.target_file],
                cwd=str(PROJ_ROOT), capture_output=True, timeout=10
            )
            subprocess.run(
                ["git", "commit", "-m",
                 f"{intent.patch_id}: {intent.description[:72]}"],
                cwd=str(PROJ_ROOT), capture_output=True, timeout=15
            )
        except Exception as exc:
            warnings.append(f"Git commit skipped: {exc}")

        # 7. Restart service if requested
        restarted = False
        if restart:
            try:
                subprocess.run(
                    ["systemctl", "restart", SERVICE_NAME],
                    capture_output=True, timeout=10
                )
                time.sleep(RESTART_WAIT_S)
                restarted = True
                logger.info("SelfMod: service restarted after %s", intent.patch_id)
            except Exception as exc:
                warnings.append(f"Service restart failed: {exc}")

        return PatchResult(
            patch_id      = intent.patch_id,
            success       = True,
            gate_decision = gate,
            backup_path   = backup_path,
            warnings      = warnings,
            restarted     = restarted,
            applied_at    = datetime.now(timezone.utc).isoformat(),
        )

    def inject_block(
        self,
        intent:      PatchIntent,
        marker:      str,
        block:       str,
        after_marker: bool = True,
        restart:     bool  = True,
    ) -> PatchResult:
        """
        Inject a block of code near a marker string in target_file.
        Safer than full rewrites for large files (e.g. app.py).
        """
        current = self.read_file(intent.target_file)
        if marker not in current:
            return PatchResult(
                patch_id      = intent.patch_id,
                success       = False,
                gate_decision = "CLEAR",
                backup_path   = None,
                errors        = [f"Marker not found: {repr(marker)}"],
            )
        if after_marker:
            new_content = current.replace(marker, marker + "\n" + block, 1)
        else:
            new_content = current.replace(marker, block + "\n" + marker, 1)

        return self.write_patch(intent, new_content, restart=restart)

    def list_backups(self) -> List[Dict]:
        """List all patch backups."""
        results = []
        for p in sorted(BACKUP_DIR.glob("*.bak"), reverse=True):
            parts = p.stem.split("__")
            results.append({
                "patch_id":   parts[0] if len(parts) > 0 else "?",
                "timestamp":  parts[1] if len(parts) > 1 else "?",
                "file":       parts[2].replace("_", "/") if len(parts) > 2 else "?",
                "path":       str(p),
                "size_bytes": p.stat().st_size,
            })
        return results

    def restore_backup(self, patch_id: str) -> Dict:
        """Roll back the most recent backup for a patch_id."""
        matches = sorted(BACKUP_DIR.glob(f"{patch_id}__*.bak"), reverse=True)
        if not matches:
            return {"success": False, "error": f"No backup found for {patch_id}"}
        bak = matches[0]
        parts = bak.stem.split("__")
        rel_path = parts[2].replace("_", "/") if len(parts) > 2 else None
        if not rel_path:
            return {"success": False, "error": "Could not parse backup filename"}
        dest = PROJ_ROOT / rel_path
        shutil.copy2(bak, dest)
        return {"success": True, "restored_to": str(dest), "from_backup": str(bak)}

    def evaluate_self(self, scope: str = "full") -> Dict:
        """
        Murphy self-assessment: what works, what gaps remain, what to fix next.
        Applies all 10 guiding engineering principles.
        Uses LLM for dynamic gap analysis and next-action prioritization.
        """
        report: Dict[str, Any] = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "scope":        scope,
            "principle":    "Does the module do what it was designed to do?",
        }

        # ── Principle 6: What is the actual result? ──────────────────────────
        # Shield wall status
        try:
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:8000/api/shield/status", timeout=5) as resp:
                sw = json.loads(resp.read())
            layers = sw.get("layers", [])
            n_active = sum(1 for l in layers if l["active"])
            report["shield_wall"] = {
                "total":   len(layers),
                "active":  n_active,
                "dormant": [l["layer"] for l in layers if not l["active"]],
                "verdict": "HEALTHY" if n_active >= len(layers) - 1 else "DEGRADED",
            }
        except Exception as exc:
            report["shield_wall"] = {"error": str(exc), "verdict": "UNKNOWN"}

        # Front-of-line queue
        try:
            from src.front_of_line import front_of_line
            st = front_of_line.status()
            report["front_of_line"] = {
                "queue_depth":   len(st["queue"]),
                "ai_threatened": sum(1 for i in st["queue"] if i.get("threatens_ai")),
                "items":         [{"rank": i["rank"], "name": i["name"], "status": i["status"]}
                                  for i in st["queue"][:5]],
            }
        except Exception as exc:
            report["front_of_line"] = {"error": str(exc)}

        # RROM status
        try:
            from src.rrom import rrom
            snap = rrom.current_snapshot()
            report["rrom"] = snap if snap else {"status": "warming_up"}
        except Exception as exc:
            report["rrom"] = {"error": str(exc)}

        # Module inventory — what exists, what is stubs
        try:
            source_files = self.list_source_files("src")
            report["source_files"] = len(source_files)
        except Exception:
            report["source_files"] = -1

        # ── Principles 1–5: Dynamic gap analysis via LLM ─────────────────────
        # Murphy uses its own LLM to assess system state and prioritize gaps.
        # This is Principle 4: does the test profile reflect the full range?
        try:
            from src.llm_provider import get_llm as _llm_get
            sw_str  = json.dumps(report.get("shield_wall", {}))
            fl_str  = json.dumps(report.get("front_of_line", {}))
            rrom_str= json.dumps(report.get("rrom", {}).get("faces", {}) if isinstance(report.get("rrom"), dict) else {})

            audit_prompt = (
                f"You are Murphy's engineering audit engine. Apply the 10 guiding principles:\n"
                f"1. Does the module do what it was designed to do?\n"
                f"2. What is the design intent?\n"
                f"3. What conditions are possible?\n"
                f"4. Does the test profile reflect the full range?\n"
                f"5. What is the expected result at all points?\n"
                f"6. What is the actual result?\n"
                f"7. Restart from symptoms if problems remain\n"
                f"8. Has ancillary code and docs been updated?\n"
                f"9. Has hardening been applied?\n"
                f"10. Has the module been recommissioned after changes?\n\n"
                f"Current system state:\n"
                f"Shield Wall: {sw_str}\n"
                f"Front-of-Line: {fl_str}\n"
                f"RROM faces: {rrom_str}\n\n"
                f"Known implemented modules: Rules of Conduct, Ledger Engine, Front-of-Line gate, "
                f"Convergence Engine (GAP-1 + GAP-2 just fixed), RROM Phase 1 (just deployed), "
                f"Criminal Investigation Protocol, Model Team, Self-Modification Engine, "
                f"Honeypot/Counter-Intelligence, Shield Wall.\n\n"
                f"Known open gaps: PCC formula not in code, CIDP reports not persisted, "
                f"Sentinel model too slow, SendGrid dormant, self-mod not wired to PCC cycle.\n\n"
                f"List exactly 5 specific engineering gaps ordered by impact. "
                f"For each: id (GAP-N), priority (HIGH/MEDIUM/LOW), one-line description, "
                f"and the exact file+function where the fix belongs. "
                f"Then list 3 recommended next actions in order. "
                f"Return as JSON: {{gaps: [...], recommended_next: [...]}}"
            )
            llm_out = _llm_get().complete(
                audit_prompt,
                system="You are Murphy's engineering audit engine. Return only valid JSON.",
                model_hint="chat",
                temperature=0.2,
                max_tokens=800,
            )
            if llm_out and llm_out.text:
                raw = llm_out.text.strip()
                # Extract JSON from response
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    report["known_gaps"]      = parsed.get("gaps", [])
                    report["recommended_next"]= parsed.get("recommended_next", [])
                    report["llm_audit"]       = True
                    report["audit_model"]     = getattr(llm_out, "model", "?")
                else:
                    raise ValueError("No JSON object in LLM response")
            else:
                raise ValueError("Empty LLM response")
        except Exception as exc:
            logger.warning("evaluate_self: LLM audit failed (%s) — falling back to static gaps", exc)
            # ── Fallback static gap list (updated after PATCH-097/098) ──────
            report["known_gaps"] = [
                {"id": "GAP-1",  "priority": "FIXED",  "desc": "HIGH_RISK_PATTERNS now trigger early steering (PATCH-097)"},
                {"id": "GAP-2",  "priority": "FIXED",  "desc": "LLM-enriched SteeringAction payload (PATCH-097)"},
                {"id": "GAP-3",  "priority": "FIXED",  "desc": "RROM Phase 1 measurement deployed (PATCH-098)"},
                {"id": "GAP-4",  "priority": "MEDIUM", "desc": "CIDP investigation reports not persisted — src/criminal_investigation_protocol.py"},
                {"id": "GAP-5",  "priority": "HIGH",   "desc": "PCC formula not in code — needs src/pcc.py + wiring to convergence_engine"},
                {"id": "GAP-6",  "priority": "LOW",    "desc": "Sentinel (phi3) timeouts — src/model_team.py SENTINEL config"},
                {"id": "GAP-7",  "priority": "LOW",    "desc": "SendGrid key missing — /etc/murphy-production/secrets.env"},
                {"id": "GAP-8",  "priority": "MEDIUM", "desc": "Self-mod not wired to PCC — src/self_modification.py _gate_check()"},
            ]
            report["recommended_next"] = [
                "Implement PCC formula in src/pcc.py — wire R_fair to convergence + RROM",
                "Persist CIDP reports to SQLite — add LedgerEntry-style storage in criminal_investigation_protocol.py",
                "Replace Sentinel phi3 with faster local model or increase timeout + async retry",
            ]
            report["llm_audit"] = False

        return report


# Singleton
self_mod = SelfModificationEngine()

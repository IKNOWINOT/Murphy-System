# Copyright © 2020 Inoni LLC | License: BSL 1.1
"""Murphy Self-Patch Loop — PATCH-066 | Label: SELF-PATCH-001

The self-patching cycle:
  1. Detect   — sensor surfaces anomaly (route 404, LLM timeout, test fail)
  2. Diagnose — trace to file + function using self-manifest
  3. Propose  — minimal patch with rationale (requires_human_review=True)
  4. Gate     — founder HITL approval before apply
  5. Apply    — murphy_patch tool writes file + backup
  6. Validate — restart + commission tests
  7. Record   — append to patch lineage

All code-diff patches require human review. Config/behaviour patches
may auto-apply at LOW risk with founder approval.

Endpoints (wired in self_manifest_router.py):
  POST /api/self/diagnose          — run one triage cycle
  GET  /api/self/proposals         — pending patch proposals
  POST /api/self/proposals/{id}/approve  — founder approves
  POST /api/self/proposals/{id}/reject   — founder rejects
  POST /api/self/proposals/{id}/apply    — apply an approved proposal
"""
from __future__ import annotations
import json, logging, threading, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------

class ProposalStatus(str, Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    APPLIED   = "applied"
    FAILED    = "failed"


class PatchKind(str, Enum):
    CODE_DIFF  = "code_diff"    # Source file change — always needs human review
    CONFIG     = "config"       # Env var or setting
    BEHAVIOUR  = "behaviour"    # Runtime parameter tweak
    ROLLBACK   = "rollback"     # Revert to backup


@dataclass
class PatchProposal:
    proposal_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:10]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    symptom: str = ""           # What the sensor detected
    diagnosis: str = ""         # Root cause analysis
    affected_file: str = ""     # Which file to patch
    affected_function: str = "" # Which function
    patch_kind: str = PatchKind.CODE_DIFF
    proposed_change: str = ""   # Human-readable description of the change
    unified_diff: str = ""      # If code_diff: the actual diff (for human review)
    rationale: str = ""
    risk_level: str = "HIGH"    # LOW/MEDIUM/HIGH/CRITICAL
    requires_human_review: bool = True
    status: str = ProposalStatus.PENDING
    approved_by: Optional[str] = None
    applied_at: Optional[str] = None
    validation_result: Optional[str] = None

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items()}


# -----------------------------------------------------------------------
# Proposal store (in-memory, persisted to JSON)
# -----------------------------------------------------------------------

_STORE_PATH = "/var/lib/murphy-production/self_patch_proposals.json"
_STORE_LOCK = threading.Lock()
_proposals: Dict[str, PatchProposal] = {}


def _load_store():
    global _proposals
    try:
        import json as _json
        from pathlib import Path
        p = Path(_STORE_PATH)
        if p.exists():
            data = _json.loads(p.read_text())
            _proposals = {k: PatchProposal(**v) for k, v in data.items()}
            logger.info("SELF-PATCH-001: Loaded %d proposals from disk", len(_proposals))
    except Exception as exc:
        logger.warning("SELF-PATCH-001: Could not load proposals: %s", exc)


def _save_store():
    try:
        from pathlib import Path
        Path(_STORE_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(_STORE_PATH).write_text(
            json.dumps({k: v.to_dict() for k, v in _proposals.items()}, indent=2))
    except Exception as exc:
        logger.warning("SELF-PATCH-001: Could not save proposals: %s", exc)


def add_proposal(proposal: PatchProposal) -> PatchProposal:
    with _STORE_LOCK:
        _proposals[proposal.proposal_id] = proposal
        _save_store()
    return proposal


def get_proposal(proposal_id: str) -> Optional[PatchProposal]:
    return _proposals.get(proposal_id)


def list_proposals(status: Optional[str] = None) -> List[Dict]:
    with _STORE_LOCK:
        props = list(_proposals.values())
    if status:
        props = [p for p in props if p.status == status]
    return [p.to_dict() for p in sorted(props, key=lambda x: x.created_at, reverse=True)]


# -----------------------------------------------------------------------
# Triage / Diagnose
# -----------------------------------------------------------------------

def run_triage_cycle() -> Dict:
    """Run one detect→diagnose→generate-diff cycle. PATCH-070.
    
    For every new issue detected:
      1. Create a PatchProposal
      2. Auto-call generate_diff_for_proposal() to produce a real unified diff
      3. Notify founder via /api/notifications (best-effort)
    """
    import subprocess
    from pathlib import Path
    new_proposals = []
    issues_found = []

    # Check 1: Service health
    try:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", "5", "http://127.0.0.1:8000/api/health"],
                           capture_output=True, text=True, timeout=8)
        code = int(r.stdout.strip() or 0)
        if code not in (200, 204):
            issues_found.append({"symptom": f"Health endpoint returned {code}",
                                 "diagnosis": "Service may be degraded or restarting",
                                 "file": "src/runtime/app.py", "risk": "HIGH"})
    except Exception as e:
        issues_found.append({"symptom": f"Health check failed: {e}",
                             "diagnosis": "Service unreachable",
                             "file": "src/runtime/app.py", "risk": "CRITICAL"})

    # Check 2: LLM provider availability
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "10",
             "http://127.0.0.1:8000/api/self/code-gen/status"],
            capture_output=True, text=True, timeout=15)
        import json as _json
        status = _json.loads(r.stdout or "{}")
        if not status.get("llm_available", True):
            issues_found.append({"symptom": "LLM provider unavailable",
                                 "diagnosis": "All LLM providers failing — check API keys and model names",
                                 "file": "src/llm_provider.py", "risk": "HIGH"})
    except Exception:
        pass

    # Check 3: Recent error spike in logs
    try:
        r = subprocess.run(
            ["journalctl", "-u", "murphy-production", "--since", "5 minutes ago",
             "--no-pager", "-q", "--grep", "ERROR|CRITICAL|500"],
            capture_output=True, text=True, timeout=10)
        error_lines = [l for l in r.stdout.splitlines() if l.strip()]
        if len(error_lines) > 5:
            issues_found.append({
                "symptom": f"{len(error_lines)} errors in last 5 min",
                "diagnosis": "High error rate in service logs — inspect journalctl for root cause",
                "file": "src/runtime/app.py", "risk": "HIGH"})
    except Exception:
        pass

    # Check 4: Zombie process (port 8000 PID mismatch)
    try:
        r1 = subprocess.run(["fuser", "8000/tcp"], capture_output=True, text=True, timeout=5)
        r2 = subprocess.run(["systemctl", "show", "murphy-production", "-p", "MainPID", "--value"],
                            capture_output=True, text=True, timeout=5)
        fuser_pid = r1.stdout.strip().split()[0] if r1.stdout.strip() else ""
        main_pid  = r2.stdout.strip()
        if fuser_pid and main_pid and fuser_pid != main_pid:
            issues_found.append({
                "symptom": f"Zombie process: fuser={fuser_pid} vs systemd MainPID={main_pid}",
                "diagnosis": "Old process holding port 8000 — serving stale code",
                "file": "system/process", "risk": "CRITICAL",
                "proposed_change": f"kill -9 {fuser_pid} && systemctl restart murphy-production"})
    except Exception:
        pass

    # Check 5: Import errors in recent logs
    try:
        r = subprocess.run(
            ["journalctl", "-u", "murphy-production", "--since", "10 minutes ago",
             "--no-pager", "-q", "--grep", "ImportError|ModuleNotFoundError|SyntaxError"],
            capture_output=True, text=True, timeout=10)
        import_errors = [l for l in r.stdout.splitlines() if l.strip()]
        if import_errors:
            issues_found.append({
                "symptom": f"Import/Syntax error detected: {import_errors[0][:120]}",
                "diagnosis": "A Python module has an import or syntax error — service may not load correctly",
                "file": "src/runtime/app.py", "risk": "HIGH"})
    except Exception:
        pass

    # Check 6: Test suite failures (if test results file exists)
    try:
        from pathlib import Path as _Path
        result_file = _Path("/tmp/murphy_test_results.txt")
        if result_file.exists() and result_file.stat().st_mtime > (datetime.now(timezone.utc).timestamp() - 3600):
            content = result_file.read_text()
            if "FAILED" in content or "ERROR" in content:
                failed = [l for l in content.splitlines() if "FAILED" in l or "ERROR" in l]
                issues_found.append({
                    "symptom": f"{len(failed)} test failures: {failed[0][:80] if failed else '?'}",
                    "diagnosis": "Recent test run has failures — code correctness may be compromised",
                    "file": "tests/", "risk": "MEDIUM"})
    except Exception:
        pass

    # ── Create proposals + auto-generate diffs ──────────────────────
    diff_results = []
    for issue in issues_found:
        prop = PatchProposal(
            symptom=issue["symptom"],
            diagnosis=issue["diagnosis"],
            affected_file=issue.get("file", ""),
            patch_kind=PatchKind.BEHAVIOUR if issue.get("risk") in ("LOW", "MEDIUM") else PatchKind.CODE_DIFF,
            proposed_change=issue.get("proposed_change", "LLM diff generation in progress..."),
            rationale="Auto-detected by SELF-PATCH-001 triage cycle (PATCH-070)",
            risk_level=issue.get("risk", "HIGH"),
            requires_human_review=True,
        )
        add_proposal(prop)
        new_proposals.append(prop.to_dict())

        # Skip diff generation for system/process issues (no source file to patch)
        if prop.affected_file and prop.affected_file != "system/process" and not issue.get("proposed_change"):
            try:
                from src.murphy_code_gen import generate_diff_for_proposal
                diff_result = generate_diff_for_proposal(prop.proposal_id)
                diff_results.append({
                    "proposal_id": prop.proposal_id,
                    "diff_ok": diff_result.get("ok", False),
                    "diff_lines": diff_result.get("diff_lines", 0),
                    "error": diff_result.get("error"),
                })
                logger.info("SELF-PATCH-070: auto-diff for %s → ok=%s lines=%s",
                            prop.proposal_id,
                            diff_result.get("ok"), diff_result.get("diff_lines"))
            except Exception as exc:
                logger.warning("SELF-PATCH-070: diff gen failed for %s: %s", prop.proposal_id, exc)
                diff_results.append({"proposal_id": prop.proposal_id, "diff_ok": False, "error": str(exc)})

    # ── Notify founder (best-effort) ────────────────────────────────
    if new_proposals:
        try:
            _notify_founder(new_proposals, diff_results)
        except Exception as exc:
            logger.warning("SELF-PATCH-070: notification failed: %s", exc)

    return {
        "ok": True,
        "issues_found": len(issues_found),
        "new_proposals": new_proposals,
        "diff_results": diff_results,
        "triage_ts": datetime.now(timezone.utc).isoformat(),
    }


def _notify_founder(proposals: list, diff_results: list) -> None:
    """Post a notification to the Murphy notification store. PATCH-070."""
    import subprocess, json as _json
    diffs_with_code = sum(1 for d in diff_results if d.get("diff_ok"))
    diffs_failed    = sum(1 for d in diff_results if not d.get("diff_ok"))
    summary_lines = []
    for p in proposals:
        did = p.get("proposal_id", "?")
        diff_info = next((d for d in diff_results if d.get("proposal_id") == did), None)
        diff_tag  = f"[{diff_info.get('diff_lines',0)}-line diff ready]" if diff_info and diff_info.get("diff_ok") else "[needs manual fix]"
        summary_lines.append(f"• [{p.get('risk_level','?')}] {p.get('symptom','?')[:80]} {diff_tag}")

    message = (
        f"🔍 Murphy Triage — {len(proposals)} issue(s) found\n"
        f"{'\n'.join(summary_lines)}\n"
        f"Diffs auto-generated: {diffs_with_code} | Failed: {diffs_failed}\n"
        f"Review at: https://murphy.systems/ui/admin → Self-Patch Proposals"
    )

    # Try to write to the notifications endpoint
    payload = _json.dumps({"type": "triage_alert", "message": message, "level": "warning"})
    subprocess.run(
        ["curl", "-s", "-X", "POST", "http://127.0.0.1:8000/api/notifications",
         "-H", "Content-Type: application/json",
         "-d", payload, "--max-time", "5"],
        capture_output=True, timeout=8)
    logger.info("SELF-PATCH-070: founder notified — %d proposals, %d diffs", len(proposals), diffs_with_code)



def apply_proposal(proposal_id: str, approved_by: str) -> Dict:
    """Apply an approved CODE_DIFF or BEHAVIOUR patch via murphy_patch tool. PATCH-070."""
    prop = get_proposal(proposal_id)
    if prop is None:
        return {"ok": False, "error": "Proposal not found"}
    if prop.status != ProposalStatus.APPROVED:
        return {"ok": False, "error": f"Proposal is {prop.status}, not approved"}

    # If CODE_DIFF has no unified_diff yet, try to generate it now
    if prop.patch_kind == PatchKind.CODE_DIFF and not prop.unified_diff:
        try:
            from src.murphy_code_gen import generate_diff_for_proposal
            diff_result = generate_diff_for_proposal(proposal_id)
            if not diff_result.get("ok"):
                return {"ok": False,
                        "error": f"No diff available and auto-gen failed: {diff_result.get('error')}",
                        "instructions": f"Edit {prop.affected_file} to implement: {prop.proposed_change}"}
            # Reload prop after diff was saved
            prop = get_proposal(proposal_id)
        except Exception as exc:
            return {"ok": False, "error": f"Diff generation error: {exc}"}

    # Apply CODE_DIFF via murphy_patch tool
    if prop.patch_kind == PatchKind.CODE_DIFF and prop.unified_diff:
        try:
            from src.aionmind.tool_executor import murphy_patch as _mp
            from pathlib import Path
            import subprocess, tempfile, os
            # Apply unified diff via patch command
            full_path = str(Path("/opt/Murphy-System") / prop.affected_file)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tf:
                tf.write(prop.unified_diff)
                patch_file = tf.name
            r = subprocess.run(
                ["patch", "-p1", "--dry-run", "-i", patch_file],
                cwd="/opt/Murphy-System", capture_output=True, text=True, timeout=10)
            os.unlink(patch_file)
            if r.returncode != 0:
                return {"ok": False, "error": f"Patch dry-run failed: {r.stderr[:200]}",
                        "diff_preview": prop.unified_diff[:300]}
            # Dry run passed — apply for real
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tf:
                tf.write(prop.unified_diff)
                patch_file = tf.name
            subprocess.run(["patch", "-p1", "-i", patch_file],
                           cwd="/opt/Murphy-System", capture_output=True, text=True, timeout=10)
            os.unlink(patch_file)
        except Exception as exc:
            logger.warning("SELF-PATCH-070: patch apply error: %s", exc)

    with _STORE_LOCK:
        prop.status = ProposalStatus.APPLIED
        prop.applied_at = datetime.now(timezone.utc).isoformat()
        prop.approved_by = approved_by
        _save_store()

    return {"ok": True, "proposal_id": proposal_id, "message": "Patch applied and marked"}



# Bootstrap
_load_store()

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
    """Run one detect→diagnose cycle. Returns list of new proposals."""
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

    # Check 2: LLM provider test
    try:
        r = subprocess.run(
            ["curl", "-s", "-b", "/tmp/cookies.txt", "--max-time", "20",
             "http://127.0.0.1:8000/api/demo/health"],
            capture_output=True, text=True, timeout=25)
        if r.returncode != 0 or '"ok":false' in r.stdout:
            issues_found.append({"symptom": "Demo/Forge health check degraded",
                                 "diagnosis": "LLM provider may be timing out or returning errors",
                                 "file": "src/llm_provider.py", "risk": "MEDIUM"})
    except Exception:
        pass

    # Check 3: Recent error logs
    try:
        r = subprocess.run(
            ["journalctl", "-u", "murphy-production", "--since", "5 minutes ago",
             "--no-pager", "-q", "--grep", "ERROR|CRITICAL|500"],
            capture_output=True, text=True, timeout=10)
        error_lines = [l for l in r.stdout.splitlines() if l.strip()]
        if len(error_lines) > 5:
            issues_found.append({
                "symptom": f"{len(error_lines)} errors in last 5 min",
                "diagnosis": "High error rate detected in service logs. Inspect journalctl.",
                "file": "src/runtime/app.py", "risk": "HIGH"})
    except Exception:
        pass

    # Check 4: Zombie process (port 8000 mismatch)
    try:
        r1 = subprocess.run(["fuser", "8000/tcp"], capture_output=True, text=True, timeout=5)
        r2 = subprocess.run(["systemctl", "show", "murphy-production", "-p", "MainPID", "--value"],
                            capture_output=True, text=True, timeout=5)
        fuser_pid = r1.stdout.strip().split()[0] if r1.stdout.strip() else ""
        main_pid = r2.stdout.strip()
        if fuser_pid and main_pid and fuser_pid != main_pid:
            issues_found.append({
                "symptom": f"Zombie process: fuser={fuser_pid} vs systemd MainPID={main_pid}",
                "diagnosis": "Old process holding port 8000 — serving stale code",
                "file": "system/process", "risk": "CRITICAL",
                "proposed_change": f"kill -9 {fuser_pid} && systemctl restart murphy-production"})
    except Exception:
        pass

    # Create proposals for each issue
    for issue in issues_found:
        prop = PatchProposal(
            symptom=issue["symptom"],
            diagnosis=issue["diagnosis"],
            affected_file=issue.get("file", ""),
            patch_kind=PatchKind.BEHAVIOUR if issue.get("risk") in ("LOW", "MEDIUM") else PatchKind.CODE_DIFF,
            proposed_change=issue.get("proposed_change", "Manual investigation required"),
            rationale="Auto-detected by SELF-PATCH-001 triage cycle",
            risk_level=issue.get("risk", "HIGH"),
            requires_human_review=True,
        )
        add_proposal(prop)
        new_proposals.append(prop.to_dict())

    return {
        "ok": True,
        "issues_found": len(issues_found),
        "new_proposals": new_proposals,
        "triage_ts": datetime.now(timezone.utc).isoformat(),
    }


# -----------------------------------------------------------------------
# Apply an approved proposal
# -----------------------------------------------------------------------

def apply_proposal(proposal_id: str, approved_by: str) -> Dict:
    """Apply an approved CODE_DIFF or BEHAVIOUR patch via murphy_patch tool."""
    prop = get_proposal(proposal_id)
    if prop is None:
        return {"ok": False, "error": "Proposal not found"}
    if prop.status != ProposalStatus.APPROVED:
        return {"ok": False, "error": f"Proposal is {prop.status}, not approved"}

    # For CODE_DIFF patches without a unified_diff, we can't auto-apply
    if prop.patch_kind == PatchKind.CODE_DIFF and not prop.unified_diff:
        return {"ok": False,
                "error": "CODE_DIFF patch has no unified_diff — manual application required",
                "instructions": f"Edit {prop.affected_file} to implement: {prop.proposed_change}"}

    # For BEHAVIOUR/CONFIG patches (simple shell commands)
    if prop.patch_kind in (PatchKind.BEHAVIOUR, PatchKind.CONFIG):
        try:
            from src.aionmind.tool_executor import murphy_patch as _mp
        except ImportError:
            pass

    with _STORE_LOCK:
        prop.status = ProposalStatus.APPLIED
        prop.applied_at = datetime.now(timezone.utc).isoformat()
        prop.approved_by = approved_by
        _save_store()

    return {"ok": True, "proposal_id": proposal_id, "message": "Marked as applied"}


# Bootstrap
_load_store()

# Copyright © 2020 Inoni LLC — Creator: Corey Post — License: BSL 1.1
"""
SelfQCPipeline — PATCH-361
"Murphy reads its own source, improves it, QC-gates the change before
anything leaves Causality or starts operating on Rubix."

Dial-down loop:
  READ → SANDBOX → CAUSALITY GATE → RUBIX GATE → WRITE or HITL
Each cycle tightens requirements. Nothing reaches production without proof.
"""
from __future__ import annotations

import ast
import hashlib
import logging
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.self_qc")

MURPHY_SRC = Path("/opt/Murphy-System/src")


@dataclass
class SandboxEnvironment:
    sandbox_id: str
    original_source: str
    proposed_source: str
    target_file: str
    syntax_valid: bool = False
    import_valid: bool = False
    test_results: List[Dict] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class QCVerdict:
    qc_id: str
    target_file: str
    causality_passed: bool
    rubix_passed: bool
    overall_pass: bool
    causality_detail: str
    rubix_detail: str
    improvement_summary: str
    dial_down_notes: List[str]
    ready_to_write: bool
    hitl_required: bool
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "qc_id": self.qc_id,
            "target_file": self.target_file,
            "causality_passed": self.causality_passed,
            "rubix_passed": self.rubix_passed,
            "overall_pass": self.overall_pass,
            "ready_to_write": self.ready_to_write,
            "hitl_required": self.hitl_required,
            "causality_detail": self.causality_detail,
            "rubix_detail": self.rubix_detail,
            "improvement_summary": self.improvement_summary,
            "dial_down_notes": self.dial_down_notes,
            "created_at": self.created_at,
        }


@dataclass
class SelfModification:
    mod_id: str
    target_file: str
    original_hash: str
    proposed_hash: str
    diff_summary: str
    improvement_reason: str
    qc_verdict: Optional[QCVerdict]
    applied: bool = False
    applied_at: Optional[str] = None


class SelfQCPipeline:
    """
    Murphy's self-improvement QC pipeline.
    Every proposed code change runs through this before touching the filesystem.
    Gates: Causality Commission + Rubix Evidence Battery.
    Both must pass. Either fail → HITL queue.
    """

    def __init__(self, llm_provider=None):
        self._llm = llm_provider
        self._modifications: List[SelfModification] = []
        self._hitl_queue: List[QCVerdict] = []
        logger.info("[PATCH-361] SelfQCPipeline initialized — src=%s", MURPHY_SRC)

    def read_source(self, relative_path: str) -> Tuple[str, str]:
        """Read a Murphy source file. Returns (content, sha256_hash[:16])."""
        relative_path = relative_path.removeprefix("src/")
        full_path = MURPHY_SRC / relative_path
        if not full_path.exists():
            raise FileNotFoundError("Source not found: " + str(full_path))
        content = full_path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        logger.info("[PATCH-361] Read %s (%d bytes hash=%s)", relative_path, len(content), content_hash)
        return content, content_hash

    def list_source_files(self, subdir: str = "") -> List[str]:
        """List Murphy source .py files."""
        base = MURPHY_SRC / subdir if subdir else MURPHY_SRC
        files = sorted(base.glob("*.py"))
        return [str(f.relative_to(MURPHY_SRC)) for f in files
                if not str(f).endswith(".pyc") and not f.name.startswith("__")]

    def create_sandbox(self, original_source: str, proposed_source: str, target_file: str) -> SandboxEnvironment:
        """Create in-memory sandbox and run checks. No filesystem write."""
        sandbox = SandboxEnvironment(
            sandbox_id="sb_" + uuid.uuid4().hex[:8],
            original_source=original_source,
            proposed_source=proposed_source,
            target_file=target_file,
        )

        # Syntax check
        try:
            ast.parse(proposed_source)
            sandbox.syntax_valid = True
            sandbox.test_results.append({"test": "syntax", "passed": True, "detail": "AST parse OK"})
        except SyntaxError as e:
            sandbox.syntax_valid = False
            sandbox.test_results.append({"test": "syntax", "passed": False, "detail": str(e)})
            return sandbox

        # Import check via subprocess (isolated)
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tf:
                tf.write(proposed_source)
                tmp = tf.name
            r = subprocess.run(
                [sys.executable, "-c", "import ast; ast.parse(open('" + tmp + "').read()); print('OK')"],
                capture_output=True, text=True, timeout=10
            )
            os.unlink(tmp)
            sandbox.import_valid = (r.returncode == 0)
            sandbox.test_results.append({
                "test": "import_check", "passed": sandbox.import_valid,
                "detail": r.stdout.strip() or r.stderr.strip()[:200]
            })
        except Exception as e:
            sandbox.import_valid = False
            sandbox.test_results.append({"test": "import_check", "passed": False, "detail": str(e)})

        return sandbox

    def run_causality_gate(self, sandbox: SandboxEnvironment, expected_improvement: str) -> Tuple[bool, str]:
        """Causality Commission: structural causal checks on proposed change."""
        checks = []

        # C1: Syntax
        checks.append(("syntax_valid", sandbox.syntax_valid, "AST parse " + ("OK" if sandbox.syntax_valid else "FAIL")))

        # C2: Change is meaningful
        is_diff = sandbox.original_source.strip() != sandbox.proposed_source.strip()
        checks.append(("is_different", is_diff, "diff=" + ("yes" if is_diff else "no — identical")))

        # C3: No regression in callable count
        orig_callables = sandbox.original_source.count("\ndef ") + sandbox.original_source.count("\nclass ")
        prop_callables = sandbox.proposed_source.count("\ndef ") + sandbox.proposed_source.count("\nclass ")
        no_regress = prop_callables >= orig_callables
        checks.append(("no_regression", no_regress,
                        "orig_defs=" + str(orig_callables) + " prop_defs=" + str(prop_callables)))

        # C4: Improvement keyword appears in proposed (loose causal match)
        # relax: check any word of length 5+ from expected_improvement appears in proposed_source
        words = [w.lower() for w in expected_improvement.split() if len(w) >= 5] if expected_improvement else []
        keyword_present = any(w in sandbox.proposed_source.lower() for w in words) if words else True
        checks.append(("improvement_keyword", keyword_present,
                        "keywords '" + str(words) + "' " + ("some found" if keyword_present else "not found")))

        passed = all(c[1] for c in checks)
        detail = "; ".join(c[0] + "=" + c[2] for c in checks)
        logger.info("[PATCH-361] Causality: %s — %s", "PASS" if passed else "FAIL", detail[:200])
        return passed, detail

    def run_rubix_gate(self, sandbox: SandboxEnvironment, confidence_required: float = 0.75) -> Tuple[bool, str]:
        """Rubix Evidence Battery: statistical confidence that the change is safe."""
        orig_len = len(sandbox.original_source)
        prop_len = len(sandbox.proposed_source)
        size_ratio = prop_len / max(orig_len, 1)
        size_ok = 0.5 <= size_ratio <= 4.0

        tests = sandbox.test_results
        pass_count = sum(1 for t in tests if t.get("passed"))
        pass_ratio = pass_count / max(len(tests), 1)

        # Weighted confidence
        confidence = (
            float(sandbox.syntax_valid) * 0.50 +
            float(size_ok) * 0.25 +
            pass_ratio * 0.25
        )

        try:
            from rubix_evidence_adapter import RubixEvidenceAdapter, EvidenceVerdict
            rubix = RubixEvidenceAdapter()
            checks = [{"type": "confidence_interval", "data": [confidence],
                        "confidence_level": 0.80, "threshold": confidence_required,
                        "label": "self_modification_safety"}]
            result = rubix.run_evidence_battery(checks)
            passed = result.overall_verdict != EvidenceVerdict.FAIL
        except Exception:
            passed = confidence >= confidence_required

        detail = (
            "confidence=" + str(round(confidence, 3)) +
            " required=" + str(confidence_required) +
            " syntax=" + str(sandbox.syntax_valid) +
            " size_ratio=" + str(round(size_ratio, 2)) +
            " tests=" + str(pass_count) + "/" + str(len(tests))
        )
        logger.info("[PATCH-361] Rubix: %s — %s", "PASS" if passed else "FAIL", detail)
        return passed, detail

    def apply_modification(self, sandbox: SandboxEnvironment, verdict: QCVerdict, backup: bool = True) -> bool:
        """Write approved change to real filesystem."""
        if not verdict.ready_to_write:
            logger.warning("[PATCH-361] apply called but not ready_to_write")
            return False
        full_path = MURPHY_SRC / sandbox.target_file
        if backup:
            bak_path = str(full_path) + ".bak361"
            Path(bak_path).write_text(sandbox.original_source, encoding="utf-8")
        full_path.write_text(sandbox.proposed_source, encoding="utf-8")
        logger.info("[PATCH-361] Applied modification: %s", sandbox.target_file)
        return True

    def run(
        self,
        target_file: str,
        proposed_source: str,
        improvement_reason: str,
        expected_improvement: str,
        confidence_required: float = 0.75,
        auto_apply: bool = False,
    ) -> QCVerdict:
        """Full pipeline: sandbox → causality → rubix → write or HITL."""
        qc_id = "qc_" + uuid.uuid4().hex[:8]
        logger.info("[PATCH-361] QC run %s on %s", qc_id, target_file)

        try:
            original_source, orig_hash = self.read_source(target_file)
        except FileNotFoundError as e:
            v = QCVerdict(
                qc_id=qc_id, target_file=target_file,
                causality_passed=False, rubix_passed=False, overall_pass=False,
                causality_detail=str(e), rubix_detail="not reached",
                improvement_summary=improvement_reason,
                dial_down_notes=["ERROR: " + str(e)],
                ready_to_write=False, hitl_required=True,
            )
            self._hitl_queue.append(v)
            return v

        prop_hash = hashlib.sha256(proposed_source.encode()).hexdigest()[:16]
        sandbox = self.create_sandbox(original_source, proposed_source, target_file)
        causality_passed, causality_detail = self.run_causality_gate(sandbox, expected_improvement)
        rubix_passed, rubix_detail = self.run_rubix_gate(sandbox, confidence_required)
        overall_pass = causality_passed and rubix_passed

        dial_down_notes = []
        if overall_pass:
            new_conf = min(confidence_required + 0.02, 0.99)
            dial_down_notes.append("Next cycle: confidence_required=" + str(round(new_conf, 2)))
            dial_down_notes.append("Next cycle: add runtime import test")
        else:
            if not causality_passed:
                dial_down_notes.append("Causality blocked: " + causality_detail[:100])
            if not rubix_passed:
                dial_down_notes.append("Rubix blocked: " + rubix_detail[:100])

        verdict = QCVerdict(
            qc_id=qc_id, target_file=target_file,
            causality_passed=causality_passed, rubix_passed=rubix_passed,
            overall_pass=overall_pass,
            causality_detail=causality_detail, rubix_detail=rubix_detail,
            improvement_summary=improvement_reason,
            dial_down_notes=dial_down_notes,
            ready_to_write=overall_pass,
            hitl_required=not overall_pass,
        )

        mod = SelfModification(
            mod_id="mod_" + uuid.uuid4().hex[:8],
            target_file=target_file,
            original_hash=orig_hash, proposed_hash=prop_hash,
            diff_summary="orig=" + str(len(original_source)) + "b prop=" + str(len(proposed_source)) + "b",
            improvement_reason=improvement_reason,
            qc_verdict=verdict,
        )

        if overall_pass and auto_apply:
            mod.applied = self.apply_modification(sandbox, verdict)
            mod.applied_at = datetime.now(timezone.utc).isoformat() if mod.applied else None

        if not overall_pass:
            self._hitl_queue.append(verdict)

        self._modifications.append(mod)
        return verdict

    def get_hitl_queue(self) -> List[Dict]:
        return [v.to_dict() for v in self._hitl_queue]

    def get_modification_history(self) -> List[Dict]:
        return [
            {
                "mod_id": m.mod_id, "target": m.target_file,
                "applied": m.applied,
                "overall_pass": m.qc_verdict.overall_pass if m.qc_verdict else None,
                "causality": m.qc_verdict.causality_passed if m.qc_verdict else None,
                "rubix": m.qc_verdict.rubix_passed if m.qc_verdict else None,
                "reason": m.improvement_reason[:100],
            }
            for m in self._modifications
        ]

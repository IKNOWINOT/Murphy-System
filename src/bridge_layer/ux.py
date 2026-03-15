"""
UX/Chat Integration for Bridge Layer

Provides structured "why not executable yet" explanations with:
- Blocking gate identification
- Unverified assumption listing
- Evidence requirement specification
- Next steps guidance

Designed for neon green on black terminal aesthetic.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
from .models import (
    BlockingReason,
    CompilationResult,
    HypothesisArtifact,
    VerificationArtifact,
    VerificationStatus,
)


class BlockingFeedback:
    """
    Structured feedback about why hypothesis cannot be executed.

    Provides clear, actionable information about:
    - What's blocking
    - What's needed
    - What's next
    """

    def __init__(
        self,
        hypothesis_id: str,
        blocking_reasons: List[BlockingReason],
        gates_blocking: List[str],
        verifications_pending: List[str],
        required_evidence: List[str],
        confidence: float,
        authority_level: str,
    ):
        self.hypothesis_id = hypothesis_id
        self.blocking_reasons = blocking_reasons
        self.gates_blocking = gates_blocking
        self.verifications_pending = verifications_pending
        self.required_evidence = required_evidence
        self.confidence = confidence
        self.authority_level = authority_level

    def to_terminal_output(self) -> str:
        """
        Format feedback for terminal display with neon green on black.

        Uses the cli_art module for skull-framed panels when available,
        falls back to inline ANSI box-drawing characters.
        """
        # Try to use the centralised art module first
        try:
            from src.cli_art import render_panel
            RED = "\033[91m"
            YELLOW = "\033[93m"
            CYAN = "\033[96m"
            RST = "\033[0m"
            body = []
            executable = not self.blocking_reasons and not self.gates_blocking
            status_label = "EXECUTABLE" if executable else f"{RED}NOT EXECUTABLE{RST}"
            body.append(f"Status: {status_label}")
            body.append(f"Hypothesis ID: {self.hypothesis_id}")
            body.append(f"Confidence: {self.confidence:.2f}")
            body.append(f"Authority: {self.authority_level}")
            body.append("")
            if self.blocking_reasons:
                body.append(f"{YELLOW}⚠ BLOCKING REASONS:{RST}")
                for reason in self.blocking_reasons:
                    body.append(f"  {RED}✗{RST} {self._format_reason(reason)}")
                body.append("")
            if self.gates_blocking:
                body.append(f"{YELLOW}⚠ GATES BLOCKING:{RST}")
                for gate in self.gates_blocking:
                    body.append(f"  {RED}✗{RST} {gate}")
                body.append("")
            if self.verifications_pending:
                body.append(f"{YELLOW}⚠ VERIFICATIONS PENDING:{RST}")
                for v in self.verifications_pending:
                    body.append(f"  {YELLOW}⧗{RST} {v}")
                body.append("")
            if self.required_evidence:
                body.append(f"{CYAN}→ REQUIRED EVIDENCE:{RST}")
                for i, ev in enumerate(self.required_evidence, 1):
                    body.append(f"  {CYAN}{i}.{RST} {ev}")
                body.append("")
            body.append("→ NEXT STEPS:")
            body.append("  1. Complete pending verifications")
            body.append("  2. Satisfy blocking gates")
            body.append("  3. Increase confidence through validation")
            body.append("  4. Retry compilation")
            return render_panel("HYPOTHESIS EXECUTABILITY STATUS", body)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            pass

        # Fallback — inline ANSI rendering
        # ANSI color codes
        GREEN = "\033[92m"  # Bright green (neon)
        YELLOW = "\033[93m"  # Bright yellow
        RED = "\033[91m"  # Bright red
        CYAN = "\033[96m"  # Bright cyan
        RESET = "\033[0m"
        BOLD = "\033[1m"

        lines = []

        # Header
        lines.append(f"{BOLD}{GREEN}╔══════════════════════════════════════════════════════════════╗{RESET}")
        lines.append(f"{BOLD}{GREEN}║  HYPOTHESIS EXECUTABILITY STATUS                             ║{RESET}")
        lines.append(f"{BOLD}{GREEN}╚══════════════════════════════════════════════════════════════╝{RESET}")
        lines.append("")

        # Status
        lines.append(f"{BOLD}{RED}STATUS: NOT EXECUTABLE{RESET}")
        lines.append(f"{GREEN}Hypothesis ID:{RESET} {self.hypothesis_id}")
        lines.append(f"{GREEN}Confidence:{RESET} {self.confidence:.2f}")
        lines.append(f"{GREEN}Authority:{RESET} {self.authority_level}")
        lines.append("")

        # Blocking reasons
        if self.blocking_reasons:
            lines.append(f"{BOLD}{YELLOW}⚠ BLOCKING REASONS:{RESET}")
            for reason in self.blocking_reasons:
                lines.append(f"  {RED}✗{RESET} {self._format_reason(reason)}")
            lines.append("")

        # Blocking gates
        if self.gates_blocking:
            lines.append(f"{BOLD}{YELLOW}⚠ GATES BLOCKING:{RESET}")
            for gate in self.gates_blocking:
                lines.append(f"  {RED}✗{RESET} {gate}")
            lines.append("")

        # Pending verifications
        if self.verifications_pending:
            lines.append(f"{BOLD}{YELLOW}⚠ VERIFICATIONS PENDING:{RESET}")
            for verification in self.verifications_pending:
                lines.append(f"  {YELLOW}⧗{RESET} {verification}")
            lines.append("")

        # Required evidence
        if self.required_evidence:
            lines.append(f"{BOLD}{CYAN}→ REQUIRED EVIDENCE:{RESET}")
            for i, evidence in enumerate(self.required_evidence, 1):
                lines.append(f"  {CYAN}{i}.{RESET} {evidence}")
            lines.append("")

        # Next steps
        lines.append(f"{BOLD}{GREEN}→ NEXT STEPS:{RESET}")
        lines.append(f"  {GREEN}1.{RESET} Complete pending verifications")
        lines.append(f"  {GREEN}2.{RESET} Satisfy blocking gates")
        lines.append(f"  {GREEN}3.{RESET} Increase confidence through validation")
        lines.append(f"  {GREEN}4.{RESET} Retry compilation")
        lines.append("")

        # Footer
        lines.append(f"{GREEN}{'─' * 62}{RESET}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Format feedback as structured data"""
        return {
            "hypothesis_id": self.hypothesis_id,
            "executable": False,
            "blocking_reasons": [br.value for br in self.blocking_reasons],
            "gates_blocking": self.gates_blocking,
            "verifications_pending": self.verifications_pending,
            "required_evidence": self.required_evidence,
            "confidence": self.confidence,
            "authority_level": self.authority_level,
            "next_steps": [
                "Complete pending verifications",
                "Satisfy blocking gates",
                "Increase confidence through validation",
                "Retry compilation",
            ],
        }

    def _format_reason(self, reason: BlockingReason) -> str:
        """Format blocking reason for display"""
        reason_map = {
            BlockingReason.CONFIDENCE_TOO_LOW: "Confidence below threshold",
            BlockingReason.CONTRADICTIONS_TOO_HIGH: "Too many contradictions detected",
            BlockingReason.GATES_NOT_SATISFIED: "Required gates not satisfied",
            BlockingReason.VERIFICATION_INCOMPLETE: "Verification requirements not met",
            BlockingReason.ASSUMPTIONS_UNVERIFIED: "Assumptions not verified",
            BlockingReason.MISSING_DEPENDENCIES: "Dependencies not available",
            BlockingReason.RISK_FLAGS_PRESENT: "Risk flags require mitigation",
            BlockingReason.AUTHORITY_INSUFFICIENT: "Authority level insufficient",
        }
        return reason_map.get(reason, reason.value)


class ExecutabilityExplainer:
    """
    Generates structured explanations for why hypotheses are/aren't executable.

    Provides clear, actionable feedback for users.
    """

    def __init__(self):
        self.explanation_log: List[Dict[str, Any]] = []

    def explain(
        self,
        hypothesis: HypothesisArtifact,
        compilation_result: CompilationResult,
        verifications: List[VerificationArtifact],
    ) -> BlockingFeedback:
        """
        Generate explanation for compilation result.

        Returns BlockingFeedback with structured information.
        """
        if compilation_result.success:
            # Success case - return minimal feedback
            feedback = BlockingFeedback(
                hypothesis_id=hypothesis.hypothesis_id,
                blocking_reasons=[],
                gates_blocking=[],
                verifications_pending=[],
                required_evidence=[],
                confidence=compilation_result.confidence,
                authority_level=compilation_result.authority_level,
            )
        else:
            # Failure case - detailed feedback
            feedback = BlockingFeedback(
                hypothesis_id=hypothesis.hypothesis_id,
                blocking_reasons=compilation_result.blocking_reasons,
                gates_blocking=compilation_result.gates_blocking,
                verifications_pending=compilation_result.verifications_pending,
                required_evidence=compilation_result.required_evidence,
                confidence=compilation_result.confidence,
                authority_level=compilation_result.authority_level,
            )

        # Log explanation
        self.explanation_log.append({
            "hypothesis_id": hypothesis.hypothesis_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": compilation_result.success,
            "feedback": feedback.to_dict(),
        })

        return feedback

    def explain_verification_status(
        self,
        verifications: List[VerificationArtifact],
    ) -> str:
        """
        Generate explanation of verification status.

        Returns formatted string for terminal display.
        """
        # ANSI color codes
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        RED = "\033[91m"
        RESET = "\033[0m"
        BOLD = "\033[1m"

        lines = []

        lines.append(f"{BOLD}{GREEN}VERIFICATION STATUS:{RESET}")
        lines.append("")

        # Group by status
        by_status = {}
        for v in verifications:
            status = v.status.value
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(v)

        # Display each status group
        for status, vlist in by_status.items():
            if status == "verified":
                icon = f"{GREEN}✓{RESET}"
            elif status == "failed":
                icon = f"{RED}✗{RESET}"
            else:
                icon = f"{YELLOW}⧗{RESET}"

            lines.append(f"{icon} {status.upper()}: {len(vlist)}")
            for v in vlist[:3]:  # Show first 3
                lines.append(f"    • {v.verification_id}")
            if len(vlist) > 3:
                lines.append(f"    ... and {len(vlist) - 3} more")
            lines.append("")

        return "\n".join(lines)

    def explain_gates(
        self,
        gates_satisfied: List[str],
        gates_blocking: List[str],
    ) -> str:
        """
        Generate explanation of gate status.

        Returns formatted string for terminal display.
        """
        # ANSI color codes
        GREEN = "\033[92m"
        RED = "\033[91m"
        RESET = "\033[0m"
        BOLD = "\033[1m"

        lines = []

        lines.append(f"{BOLD}{GREEN}GATE STATUS:{RESET}")
        lines.append("")

        # Satisfied gates
        if gates_satisfied:
            lines.append(f"{GREEN}✓ SATISFIED: {len(gates_satisfied)}{RESET}")
            for gate in gates_satisfied[:3]:
                lines.append(f"    • {gate}")
            if len(gates_satisfied) > 3:
                lines.append(f"    ... and {len(gates_satisfied) - 3} more")
            lines.append("")

        # Blocking gates
        if gates_blocking:
            lines.append(f"{RED}✗ BLOCKING: {len(gates_blocking)}{RESET}")
            for gate in gates_blocking:
                lines.append(f"    • {gate}")
            lines.append("")

        return "\n".join(lines)

    def get_explanation_log(
        self,
        hypothesis_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get explanation log"""
        log = self.explanation_log

        if hypothesis_id:
            log = [e for e in log if e["hypothesis_id"] == hypothesis_id]

        return log[-limit:]

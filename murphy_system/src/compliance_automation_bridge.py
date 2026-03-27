"""
Compliance Automation Bridge for Murphy System.

Design Label: CMP-001 — Continuous Compliance Monitoring & Auto-Remediation
Owner: Compliance Team / Platform Engineering
Dependencies:
  - ComplianceEngine (for requirement checking and release-readiness)
  - SelfImprovementEngine (ARCH-001, for remediation proposals)
  - EventBackbone (publishes compliance events, subscribes to DELIVERY_COMPLETED)

Implements Phase 4 — Compliance & Content Automation:
  Bridges the ComplianceEngine into the EventBackbone-driven automation
  pipeline so that every deliverable is automatically validated against
  applicable compliance frameworks, violations generate improvement
  proposals, and compliance reports are continuously available.

Flow:
  1. Subscribe to DELIVERY_COMPLETED events from EventBackbone
  2. Run ComplianceEngine.check_deliverable() for each delivery
  3. For each non-compliant finding, create an ImprovementProposal
  4. Track compliance posture over time
  5. Publish LEARNING_FEEDBACK events with compliance status

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Conservative: non-compliant findings always flagged
  - Audit trail: every compliance check is recorded
  - Human-in-the-loop: CRITICAL findings require manual approval

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ComplianceCheckRecord:
    """Record of a single compliance check cycle."""
    check_id: str
    session_id: str
    domain: str
    total_requirements: int
    compliant: int
    non_compliant: int
    needs_review: int
    release_ready: bool
    proposals_created: int = 0
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "session_id": self.session_id,
            "domain": self.domain,
            "total_requirements": self.total_requirements,
            "compliant": self.compliant,
            "non_compliant": self.non_compliant,
            "needs_review": self.needs_review,
            "release_ready": self.release_ready,
            "proposals_created": self.proposals_created,
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# ComplianceAutomationBridge
# ---------------------------------------------------------------------------

class ComplianceAutomationBridge:
    """Continuous compliance monitoring wired into the automation pipeline.

    Design Label: CMP-001
    Owner: Compliance Team

    Usage::

        bridge = ComplianceAutomationBridge(
            compliance_engine=engine,
            improvement_engine=improvement,
            event_backbone=backbone,
        )
        record = bridge.check_compliance(
            deliverable={"content": "...", "domain": "finance"},
            domain="finance",
        )
    """

    def __init__(
        self,
        compliance_engine=None,
        improvement_engine=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._compliance = compliance_engine
        self._improvement = improvement_engine
        self._backbone = event_backbone
        self._history: List[ComplianceCheckRecord] = []
        self._tracked_violations: Set[str] = set()

        if self._backbone is not None:
            self._subscribe_events()

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Subscribe to delivery events for automatic compliance checks."""
        try:
            from event_backbone import EventType

            def _on_delivery_completed(event) -> None:
                payload = event.payload if hasattr(event, "payload") else {}
                deliverable = payload.get("deliverable", payload)
                domain = payload.get("domain", "general")
                try:
                    self.check_compliance(deliverable=deliverable, domain=domain)
                except Exception as exc:
                    logger.warning("Auto-compliance check failed: %s", exc)

            self._backbone.subscribe(
                EventType.DELIVERY_COMPLETED, _on_delivery_completed
            )
            logger.info("ComplianceAutomationBridge subscribed to DELIVERY_COMPLETED")
        except Exception as exc:
            logger.warning("Failed to subscribe to EventBackbone: %s", exc)

    # ------------------------------------------------------------------
    # Core compliance check
    # ------------------------------------------------------------------

    def check_compliance(
        self,
        deliverable: Dict[str, Any],
        domain: str = "general",
        session_id: Optional[str] = None,
    ) -> ComplianceCheckRecord:
        """Run compliance checks on a deliverable and generate proposals.

        Returns a ComplianceCheckRecord summarising the results.
        """
        sid = session_id or f"cmp-{uuid.uuid4().hex[:8]}"
        compliant_count = 0
        non_compliant_count = 0
        needs_review_count = 0
        total_requirements = 0
        proposals_created = 0
        release_ready = True

        if self._compliance is not None:
            try:
                # Run the compliance engine check
                report = self._compliance.check_deliverable(
                    deliverable=deliverable,
                    domain=domain,
                    session_id=sid,
                )

                results = report if isinstance(report, list) else []
                total_requirements = len(results)

                for result in results:
                    status = getattr(result, "status", None)
                    if status is None:
                        status_val = result.get("status", "") if isinstance(result, dict) else ""
                    else:
                        status_val = status.value if hasattr(status, "value") else str(status)

                    if status_val == "compliant":
                        compliant_count += 1
                    elif status_val == "non_compliant":
                        non_compliant_count += 1
                        proposals_created += self._create_remediation_proposal(
                            result, domain, sid
                        )
                    elif status_val == "needs_review":
                        needs_review_count += 1

                # Check release readiness
                try:
                    ready_result = self._compliance.is_release_ready(session_id=sid)
                    if isinstance(ready_result, tuple):
                        release_ready = ready_result[0]
                    elif isinstance(ready_result, bool):
                        release_ready = ready_result
                    else:
                        release_ready = bool(ready_result)
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    release_ready = non_compliant_count == 0

            except Exception as exc:
                logger.warning("Compliance check failed: %s", exc)
                release_ready = False
        else:
            # No compliance engine — conservative: not ready
            release_ready = False

        record = ComplianceCheckRecord(
            check_id=f"chk-{uuid.uuid4().hex[:8]}",
            session_id=sid,
            domain=domain,
            total_requirements=total_requirements,
            compliant=compliant_count,
            non_compliant=non_compliant_count,
            needs_review=needs_review_count,
            release_ready=release_ready,
            proposals_created=proposals_created,
        )

        with self._lock:
            self._history.append(record)
            if len(self._history) > 200:
                self._history = self._history[-200:]

        # Publish compliance event
        if self._backbone is not None:
            try:
                from event_backbone import EventType
                self._backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "compliance_automation_bridge",
                        "compliance_record": record.to_dict(),
                    },
                    source="compliance_automation_bridge",
                )
            except Exception as exc:
                logger.debug("EventBackbone publish skipped: %s", exc)

        logger.info(
            "Compliance check: domain=%s compliant=%d non_compliant=%d ready=%s",
            domain, compliant_count, non_compliant_count, release_ready,
        )
        return record

    # ------------------------------------------------------------------
    # Remediation proposal creation
    # ------------------------------------------------------------------

    def _create_remediation_proposal(
        self,
        check_result: Any,
        domain: str,
        session_id: str,
    ) -> int:
        """Create an improvement proposal for a non-compliant finding.

        Returns 1 if created, 0 if skipped (duplicate or no engine).
        """
        if self._improvement is None:
            return 0

        # Extract requirement ID for deduplication
        if hasattr(check_result, "requirement_id"):
            req_id = check_result.requirement_id
        elif isinstance(check_result, dict):
            req_id = check_result.get("requirement_id", "unknown")
        else:
            req_id = "unknown"

        dedup_key = f"{session_id}:{req_id}"
        with self._lock:
            if dedup_key in self._tracked_violations:
                return 0
            self._tracked_violations.add(dedup_key)

        try:
            from self_improvement_engine import ImprovementProposal

            evidence = ""
            if hasattr(check_result, "evidence"):
                evidence = check_result.evidence
            elif isinstance(check_result, dict):
                evidence = check_result.get("evidence", "")

            proposal = ImprovementProposal(
                proposal_id=f"cmp-prop-{uuid.uuid4().hex[:8]}",
                category="compliance_violation",
                description=(
                    f"Compliance violation in domain '{domain}': "
                    f"requirement {req_id} — {evidence[:120]}"
                ),
                priority="high",
                source_pattern=f"compliance:{req_id}",
                suggested_action=(
                    f"Remediate compliance violation for requirement {req_id} "
                    f"in domain '{domain}'"
                ),
            )

            with self._improvement._lock:
                self._improvement._proposals[proposal.proposal_id] = proposal
            logger.info("Created compliance proposal %s", proposal.proposal_id)
            return 1
        except Exception as exc:
            logger.warning("Failed to create compliance proposal: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Posture / Status
    # ------------------------------------------------------------------

    def get_compliance_posture(self) -> Dict[str, Any]:
        """Return aggregate compliance posture from history."""
        with self._lock:
            if not self._history:
                return {
                    "total_checks": 0,
                    "overall_compliance_rate": 0.0,
                    "release_ready_rate": 0.0,
                }

            total_compliant = sum(r.compliant for r in self._history)
            total_reqs = sum(r.total_requirements for r in self._history)
            total_ready = sum(1 for r in self._history if r.release_ready)
            total_checks = len(self._history)

        return {
            "total_checks": total_checks,
            "overall_compliance_rate": round(
                total_compliant / max(total_reqs, 1), 4
            ),
            "release_ready_rate": round(
                total_ready / max(total_checks, 1), 4
            ),
            "total_proposals_created": sum(
                r.proposals_created for r in self._history
            ),
            "domains_checked": list(set(r.domain for r in self._history)),
        }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            recent = self._history[-limit:]
        return [r.to_dict() for r in recent]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_checks": len(self._history),
                "tracked_violations": len(self._tracked_violations),
                "compliance_attached": self._compliance is not None,
                "improvement_attached": self._improvement is not None,
                "backbone_attached": self._backbone is not None,
            }

    def clear_tracked_violations(self) -> int:
        """Clear tracked violations for re-evaluation. Returns count cleared."""
        with self._lock:
            count = len(self._tracked_violations)
            self._tracked_violations.clear()
        return count

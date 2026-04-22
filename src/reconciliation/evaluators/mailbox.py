"""Mailbox provisioning result evaluator (non-code deliverable example)."""

from __future__ import annotations

from typing import Iterable

from ..models import (
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
    IntentSpec,
    PatchKind,
)
from .base import DeterministicEvaluator, EvaluationContext, register_evaluator


class MailboxProvisioningEvaluator(DeterministicEvaluator):
    """Evaluator for mailbox-provisioning deliverables.

    Expected ``deliverable.content`` shape::

        {
            "accounts": [
                {"email": "...", "password": "..." | None,
                 "status": "created"|"existed"|"failed",
                 "error": "..." (optional)},
                ...
            ],
            "aliases": [...],          # optional
            "passwords_file": "..."    # optional path
        }
    """

    deliverable_types = (DeliverableType.MAILBOX_PROVISIONING,)

    def additional_diagnoses(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: EvaluationContext,
    ) -> Iterable[Diagnosis]:
        content = deliverable.content
        if not isinstance(content, dict):
            return ()

        diagnoses = []
        accounts = content.get("accounts") or []
        if not isinstance(accounts, list):
            return ()

        for account in accounts:
            if not isinstance(account, dict):
                continue
            email = account.get("email", "<unknown>")
            if account.get("status") == "failed" or account.get("error"):
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.BLOCKER,
                        summary=f"Mailbox creation failed for {email}: {account.get('error', 'unknown error')}",
                        suggested_patch_kind=PatchKind.PARAMETER_RETRY,
                        suggested_action=f"Retry creating {email} with sanitised parameters",
                        evidence={"email": email, "error": account.get("error")},
                    )
                )
            elif not account.get("password"):
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.BLOCKER,
                        summary=f"Mailbox {email} has no recorded password",
                        suggested_patch_kind=PatchKind.PARAMETER_RETRY,
                        suggested_action=f"Reset password for {email} and record it to the passwords file",
                        evidence={"email": email},
                    )
                )

        return diagnoses


register_evaluator(DeliverableType.MAILBOX_PROVISIONING, MailboxProvisioningEvaluator())


__all__ = ["MailboxProvisioningEvaluator"]

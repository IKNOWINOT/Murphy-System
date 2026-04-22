"""
Pluggable evaluator registry for reconciliation.

Each :class:`Evaluator` knows how to score a :class:`Deliverable` of one
:class:`DeliverableType` against an :class:`IntentSpec`.  The
:class:`output_evaluator.OutputEvaluator` looks up the correct evaluator
via :func:`get_evaluator` and merges the results.

Adding support for a new deliverable type is one call to
:func:`register_evaluator` — the catalog is intentionally open so
non-code deliverables (mailbox provisioning, deployment results,
written documents, dashboards, ...) are first-class.
"""

from __future__ import annotations

from .base import (
    DeterministicEvaluator,
    Evaluator,
    EvaluationContext,
    get_evaluator,
    list_evaluators,
    register_evaluator,
)
from .text import TextDeliverableEvaluator
from .code import CodeDeliverableEvaluator
from .config import ConfigDeliverableEvaluator
from .document import DocumentDeliverableEvaluator
from .mailbox import MailboxProvisioningEvaluator
from .structured import StructuredPayloadEvaluator

__all__ = [
    "Evaluator",
    "DeterministicEvaluator",
    "EvaluationContext",
    "register_evaluator",
    "get_evaluator",
    "list_evaluators",
    "TextDeliverableEvaluator",
    "CodeDeliverableEvaluator",
    "ConfigDeliverableEvaluator",
    "DocumentDeliverableEvaluator",
    "MailboxProvisioningEvaluator",
    "StructuredPayloadEvaluator",
]

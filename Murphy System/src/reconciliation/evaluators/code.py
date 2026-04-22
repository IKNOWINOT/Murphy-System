"""Code-deliverable evaluator (Python-aware)."""

from __future__ import annotations

import ast
from typing import Iterable

from ..models import (
    AcceptanceCriterion,
    CriterionKind,
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
    IntentSpec,
    PatchKind,
)
from .base import DeterministicEvaluator, EvaluationContext, register_evaluator


class CodeDeliverableEvaluator(DeterministicEvaluator):
    """Evaluator for code deliverables.

    Python-aware: parses the AST and reports concrete structural problems
    that the standards-catalog regex rules cannot capture (e.g. bare
    ``except:``, missing docstrings on public symbols).  Other languages
    fall through to the standards-catalog regex checks.
    """

    deliverable_types = (DeliverableType.CODE,)

    def additional_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> Iterable[AcceptanceCriterion]:
        # Reuse the canonical Python-syntax check from the standards module.
        yield AcceptanceCriterion(
            description="Code is non-empty",
            kind=CriterionKind.STANDARD,
            weight=1.0,
            hard=True,
            check_spec={"kind": "min_length", "value": 1},
        )

    def additional_diagnoses(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: EvaluationContext,
    ) -> Iterable[Diagnosis]:
        content = deliverable.content
        if not isinstance(content, str):
            return ()

        diagnoses = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Already surfaced by the CODE-003 standard — no need to duplicate.
            return ()

        # Bare except: clauses
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.MAJOR,
                        summary=f"Bare 'except:' at line {node.lineno} swallows all exceptions",
                        suggested_patch_kind=PatchKind.CONTENT_EDIT,
                        suggested_action="Replace with a specific exception type",
                        evidence={"line": node.lineno},
                    )
                )
            # Public function/class without docstring
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("_"):
                    continue
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    diagnoses.append(
                        Diagnosis(
                            severity=DiagnosisSeverity.MINOR,
                            summary=f"Public symbol {node.name!r} at line {node.lineno} lacks a docstring",
                            suggested_patch_kind=PatchKind.CONTENT_EDIT,
                            suggested_action=f"Add a docstring to {node.name}",
                            evidence={"symbol": node.name, "line": node.lineno},
                        )
                    )
        return diagnoses


register_evaluator(DeliverableType.CODE, CodeDeliverableEvaluator())


__all__ = ["CodeDeliverableEvaluator"]

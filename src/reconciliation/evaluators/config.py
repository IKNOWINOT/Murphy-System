"""Config-file deliverable evaluator (YAML / JSON / TOML / .env aware)."""

from __future__ import annotations

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


class ConfigDeliverableEvaluator(DeterministicEvaluator):
    """Evaluator for configuration-file deliverables."""

    deliverable_types = (
        DeliverableType.CONFIG_FILE,
        DeliverableType.SHELL_SCRIPT,
    )

    def additional_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> Iterable[AcceptanceCriterion]:
        yield AcceptanceCriterion(
            description="Configuration is non-empty",
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

        # Inferred parser based on file extension hint in metadata.
        ext = str(deliverable.metadata.get("extension", "")).lower()
        diagnoses = []
        if ext in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
                yaml.safe_load(content)
            except ImportError:
                pass
            except Exception as exc:
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.BLOCKER,
                        summary=f"YAML failed to parse: {exc}",
                        suggested_patch_kind=PatchKind.CONTENT_EDIT,
                        suggested_action="Fix YAML syntax errors",
                        evidence={"parser": "yaml.safe_load"},
                    )
                )
        elif ext == ".json":
            import json
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.BLOCKER,
                        summary=f"JSON failed to parse: {exc.msg} at line {exc.lineno}",
                        suggested_patch_kind=PatchKind.CONTENT_EDIT,
                        suggested_action="Fix JSON syntax",
                        evidence={"line": exc.lineno},
                    )
                )
        elif ext == ".toml":
            try:
                import tomllib  # py>=3.11
                tomllib.loads(content)
            except ImportError:
                pass
            except Exception as exc:
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.BLOCKER,
                        summary=f"TOML failed to parse: {exc}",
                        suggested_patch_kind=PatchKind.CONTENT_EDIT,
                        suggested_action="Fix TOML syntax",
                        evidence={},
                    )
                )
        return diagnoses


register_evaluator(DeliverableType.CONFIG_FILE, ConfigDeliverableEvaluator())
register_evaluator(DeliverableType.SHELL_SCRIPT, ConfigDeliverableEvaluator())


__all__ = ["ConfigDeliverableEvaluator"]

"""
Gap-Closure Verification — Round 30

Validates that all import bugs identified in Round 30 have been fixed:
1. Missing learning_engine/models.py re-export module
2. supervisor/schemas.py dataclass field-ordering errors (3 fields)
3. Broken relative imports in top-level src/ modules (3 modules)
4. Broken parent-relative imports in integrations/ (1 module)
5. Broken cross-package imports in learning_engine/ (3 modules)
"""

import importlib
import os
import sys

import pytest

# Ensure src/ is on the path (mirrors conftest.py behavior)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")


class TestGapClosureRound30:
    """Verify all Round 30 import bugs are fixed."""

    # --- 1. learning_engine/models.py re-export ---
    def test_learning_engine_models_reexport_exists(self):
        """learning_engine.models must re-export from shadow_models."""
        mod = importlib.import_module("learning_engine.models")
        for name in (
            "TrainingDataset",
            "DataSplitType",
            "Feature",
            "FeatureType",
            "TrainingExample",
            "FeatureEngineering",
            "DataQualityMetrics",
            "Label",
            "LabelType",
        ):
            assert hasattr(mod, name), f"learning_engine.models missing {name}"

    # --- 2. supervisor/schemas.py dataclass instantiation ---
    def test_supervisor_schemas_no_field_ordering_error(self):
        """supervisor.schemas dataclasses must instantiate without TypeError."""
        mod = importlib.import_module("supervisor.schemas")
        # AssumptionArtifact — owner_role was non-default after defaults
        obj = mod.AssumptionArtifact(
            assumption_id="a1",
            statement="test",
            evidence_refs=["ref1"],
        )
        assert obj.owner_role == ""

        # SupervisorFeedbackArtifact — supervisor_id/role were non-default
        obj2 = mod.SupervisorFeedbackArtifact(
            feedback_id="f1",
            feedback_type=mod.FeedbackType.APPROVE,
            target_type="hypothesis",
            target_id="t1",
            rationale="ok",
        )
        assert obj2.supervisor_id == ""

        # CorrectionAction — reason was non-default after defaults
        obj3 = mod.CorrectionAction(
            action_id="c1",
            assumption_id="a1",
        )
        assert obj3.reason == ""

    # --- 3. Top-level modules with fixed relative imports ---
    @pytest.mark.parametrize("mod_name", [
        "inference_gate_engine",
        "modular_runtime",
        "statistics_collector",
    ])
    def test_toplevel_module_imports(self, mod_name):
        """Top-level src/ modules must not use relative imports."""
        mod = importlib.import_module(mod_name)
        assert mod is not None

    # --- 4. integrations package ---
    def test_integrations_package_imports(self):
        """integrations.integration_framework must use absolute import."""
        mod = importlib.import_module("integrations.integration_framework")
        assert mod is not None

    def test_integrations_database_connectors_imports(self):
        """integrations.database_connectors must import cleanly."""
        mod = importlib.import_module("integrations.database_connectors")
        assert mod is not None

    # --- 5. learning_engine cross-package imports ---
    @pytest.mark.parametrize("mod_name", [
        "learning_engine.feature_engineering",
        "learning_engine.hyperparameter_tuning",
        "learning_engine.shadow_agent",
        "learning_engine.shadow_evaluation",
        "learning_engine.shadow_integration",
        "learning_engine.training_data_transformer",
        "learning_engine.training_data_validator",
        "learning_engine.training_pipeline",
    ])
    def test_learning_engine_submodule_imports(self, mod_name):
        """All learning_engine submodules must import without error."""
        mod = importlib.import_module(mod_name)
        assert mod is not None

    # --- 6. Zero real import bugs across entire src/ ---
    def test_zero_real_import_bugs_across_src(self):
        """Every .py module in src/ must import (excluding optional deps)."""
        optional_deps = {"fastapi", "matplotlib", "torch", "textual"}
        bugs = []
        for root, _dirs, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn == "__init__.py":
                    continue
                path = os.path.join(root, fn)
                mod_name = (
                    path.replace(SRC_DIR + "/", "")
                    .replace("/", ".")
                    .replace(".py", "")
                )
                try:
                    importlib.import_module(mod_name)
                except Exception as exc:
                    msg = str(exc)
                    if not any(dep in msg for dep in optional_deps):
                        bugs.append(f"{mod_name}: {type(exc).__name__}: {msg[:120]}")
        assert bugs == [], "Real import bugs found:\n" + "\n".join(bugs)

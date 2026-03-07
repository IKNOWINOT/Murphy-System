"""
Gap-closure tests — Round 9.

Gaps addressed:
29. 2 wildcard imports in comms_system/__init__.py → explicit imports
30. 2 production assert statements → proper ValueError raises
31. Code-review fixes: ml_strategy_engine uses capped_append_paired,
    memory_management LRU _access_order comment accuracy
"""

import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


# ===================================================================
# Gap 29 — no wildcard imports in src/
# ===================================================================
class TestNoWildcardImports:
    """No source file in src/ should use ``from xxx import *``."""

    def test_no_wildcard_imports(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if re.match(r"from\s+\S+\s+import\s+\*", s):
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")
        assert violations == [], f"Wildcard imports: {violations}"


# ===================================================================
# Gap 30 — no assert in production code (AST-verified)
# ===================================================================
class TestNoProductionAsserts:
    """Production code must not use assert for validation.

    ``assert`` is stripped when Python runs with ``-O``, so runtime
    validations would silently disappear.
    """

    def test_no_assert_statements_in_src(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                if "test" in fname.lower():
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assert):
                        rel = os.path.relpath(fpath, SRC_DIR)
                        violations.append(f"{rel}:{node.lineno}")
        assert violations == [], (
            f"Production assert statements found: {violations}"
        )

    def test_true_swarm_raises_valueerror(self):
        """Swarm agent with invalid authority_band raises ValueError."""
        from true_swarm_system import AgentInstance, ProfessionAtom, Phase

        with pytest.raises(ValueError, match="propose/analyze/verify"):
            AgentInstance(
                id="test",
                profession=ProfessionAtom.OPTIMIZER,
                domain_scope=set(),
                phase=Phase.EXPAND,
                authority_band="execute",
                risk_models=[],
                regulatory_knowledge=[],
            )

    def test_data_split_raises_on_bad_ratios(self):
        """Train/val/test ratios not summing to 1 raise ValueError."""
        pytest.importorskip("torch")
        pytest.importorskip("torch_geometric")
        from neuro_symbolic_models.data import TrainingDataManager

        mgr = TrainingDataManager()
        with pytest.raises(ValueError, match="must equal 1.0"):
            mgr.split_examples([], train_ratio=0.5, val_ratio=0.5, test_ratio=0.5)


# ===================================================================
# Gap 31 — paired lists use capped_append_paired
# ===================================================================
class TestPairedListIntegrity:
    """ml_strategy_engine paired lists must stay synchronised."""

    def test_ml_strategy_uses_capped_append_paired(self):
        fpath = os.path.join(SRC_DIR, "ml_strategy_engine.py")
        with open(fpath, encoding='utf-8') as f:
            content = f.read()
        assert "capped_append_paired(" in content, (
            "ml_strategy_engine should use capped_append_paired for paired lists"
        )

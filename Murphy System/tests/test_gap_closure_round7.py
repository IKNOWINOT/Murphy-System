"""
Gap-closure tests — Round 7.

Gaps addressed:
23. learning_engine/model_architecture.py — pickle.load (CWE-502) replaced with
    _RestrictedUnpickler that only allows numpy/sklearn/builtins.
24. cross_platform_data_sync.py — two silent ``except Exception: pass`` blocks
    now log errors instead of silently swallowing them.
"""

import io
import logging
import os
import pickle
import re

import pytest



# ===================================================================
# Gap 23 — pickle.load replaced with RestrictedUnpickler
# ===================================================================
class TestRestrictedUnpickler:
    """_RestrictedUnpickler must block arbitrary code execution."""

    def test_allows_numpy_array(self):
        """Numpy arrays must still load correctly."""
        import numpy as np
        from learning_engine.model_architecture import _RestrictedUnpickler

        arr = np.array([1.0, 2.0, 3.0])
        buf = io.BytesIO()
        pickle.dump(arr, buf)
        buf.seek(0)

        loaded = _RestrictedUnpickler(buf).load()
        assert list(loaded) == [1.0, 2.0, 3.0]

    def test_allows_builtin_types(self):
        """Basic Python types (dict, list, int) must still load."""
        from learning_engine.model_architecture import _RestrictedUnpickler

        data = {"accuracy": 0.95, "epochs": [1, 2, 3]}
        buf = io.BytesIO()
        pickle.dump(data, buf)
        buf.seek(0)

        loaded = _RestrictedUnpickler(buf).load()
        assert loaded == data

    def test_blocks_os_module(self):
        """Pickled os.system call must be rejected."""
        from learning_engine.model_architecture import _RestrictedUnpickler

        # Craft a malicious pickle that tries to call posix.system
        malicious = (
            b"\x80\x04\x95\x1f\x00\x00\x00\x00\x00\x00\x00"
            b"\x8c\x05posix\x94\x8c\x06system\x94\x93\x94"
            b"\x8c\x04echo\x94\x85\x94R\x94."
        )
        buf = io.BytesIO(malicious)
        with pytest.raises(pickle.UnpicklingError, match="Restricted"):
            _RestrictedUnpickler(buf).load()

    def test_source_uses_restricted_unpickler(self):
        """The load method in ShadowAgentModel must NOT use pickle.load."""
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src",
            "learning_engine", "model_architecture.py",
        )
        with open(fpath, encoding='utf-8') as f:
            content = f.read()
        assert "pickle.load(" not in content, \
            "Raw pickle.load still present — must use _RestrictedUnpickler"
        assert "_RestrictedUnpickler" in content


# ===================================================================
# Gap 24 — cross_platform_data_sync logs errors instead of silencing
# ===================================================================
class TestCrossPlatformDataSyncErrorLogging:
    """Transform/write failures must be logged, not silently swallowed."""

    def test_source_has_no_silent_except_pass(self):
        """The two except-pass blocks must now log errors."""
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src",
            "cross_platform_data_sync.py",
        )
        with open(fpath, encoding='utf-8') as f:
            lines = f.readlines()

        silent_blocks = []
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if re.match(r"except\s+Exception", s):
                for j in range(i, min(i + 3, len(lines))):
                    ns = lines[j].strip()
                    if ns == "":
                        continue
                    if ns == "pass":
                        silent_blocks.append(f"line {i}")
                    break

        assert silent_blocks == [], \
            f"Silent except-pass still present at: {silent_blocks}"

    def test_transform_error_is_logged(self):
        """Transform/write failures must now be logged, not silenced."""
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src",
            "cross_platform_data_sync.py",
        )
        with open(fpath, encoding='utf-8') as f:
            content = f.read()
        # Must contain logger.error calls where the silent pass used to be
        assert content.count("logger.error") >= 2, \
            "cross_platform_data_sync must log errors on transform/write failure"


# ===================================================================
# Global: no pickle.load anywhere in src/
# ===================================================================
class TestNoRawPickleLoad:
    """No source file should use raw pickle.load — CWE-502."""

    def test_no_pickle_load_in_src(self):
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
        violations = []
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if "pickle.load(" in s or "pickle.loads(" in s:
                            rel = os.path.relpath(fpath, src_dir)
                            violations.append(f"{rel}:{i}")
        assert violations == [], \
            f"Raw pickle.load/loads still present: {violations}"

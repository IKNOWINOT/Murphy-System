"""Tests for ``scripts/find_unused_modules.py``.

Class S Roadmap, Item 20 — pin the relative-import detection that was
added after the original absolute-only scanner reported ~200 false
positives (every module re-exported by a package ``__init__.py`` via the
``from .x import Y`` form was incorrectly flagged as unused).

These tests build a tiny synthetic git repo in a tmpdir so they are
fully hermetic and do not depend on the live source tree.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "find_unused_modules.py"
)


def _load_script(repo_root: Path) -> ModuleType:
    """Import the script as a module with `_REPO_ROOT` rebound to ``repo_root``.

    The script computes ``_REPO_ROOT`` relative to its own file location at
    import time, so we patch it after import to point at the synthetic
    fixture repo. ``_SRC_DIR`` is derived from ``_REPO_ROOT`` so we patch
    that too.
    """
    spec = importlib.util.spec_from_file_location(
        "_test_find_unused_modules", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._REPO_ROOT = repo_root
    module._SRC_DIR = repo_root / "src"
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        # Local identity so commits work even when no global git config exists.
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "PATH": "/usr/bin:/bin",
            "HOME": str(repo),
        },
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Build a synthetic git repo with a representative ``src/`` layout.

    Layout::

        src/pkg/__init__.py        — re-exports leaf, sub.deep, used_by_dot_import
        src/pkg/leaf.py            — referenced via ``from .leaf import X``
        src/pkg/used_by_dot_import.py
                                   — referenced via ``from . import used_by_dot_import``
        src/pkg/sub/__init__.py    — re-exports deep
        src/pkg/sub/deep.py        — referenced via ``from .sub.deep import X``
        src/pkg/sub/cousin.py      — referenced via ``from ..cousin_user`` from a
                                     hypothetical sibling (multi-dot relative)
        src/pkg/cousin_user.py     — does ``from ..cousin import X`` to exercise
                                     the multi-dot pass; never imports cousin.py
        src/pkg/orphan.py          — has NO references anywhere → should be flagged
        src/pkg/absolute_only.py   — referenced only via ``from src.pkg.absolute_only``
        src/other_pkg/__init__.py
        src/other_pkg/orphan_too.py — no references → should be flagged
        src/top_level_orphan.py    — direct child of src/ with no references
    """
    (tmp_path / "src" / "pkg" / "sub").mkdir(parents=True)
    (tmp_path / "src" / "other_pkg").mkdir(parents=True)

    # pkg/__init__.py — exercises the three relative-import re-export forms.
    (tmp_path / "src" / "pkg" / "__init__.py").write_text(
        "from .leaf import LeafThing\n"
        "from .sub.deep import DeepThing\n"
        "from . import used_by_dot_import\n"
    )
    (tmp_path / "src" / "pkg" / "leaf.py").write_text("LeafThing = object()\n")
    (tmp_path / "src" / "pkg" / "used_by_dot_import.py").write_text("VAL = 1\n")
    (tmp_path / "src" / "pkg" / "sub" / "__init__.py").write_text(
        "from .deep import DeepThing\n"
    )
    (tmp_path / "src" / "pkg" / "sub" / "deep.py").write_text("DeepThing = object()\n")

    # cousin / cousin_user — multi-dot relative path
    (tmp_path / "src" / "pkg" / "cousin_user.py").write_text(
        "from ..pkg.cousin import CousinThing\n"
    )
    (tmp_path / "src" / "pkg" / "cousin.py").write_text("CousinThing = object()\n")

    # absolute-only — only referenced via canonical 'src.pkg.absolute_only' form
    (tmp_path / "src" / "pkg" / "absolute_only.py").write_text("X = 1\n")
    (tmp_path / "src" / "consumer.py").write_text(
        "from src.pkg.absolute_only import X\n"
    )

    # Genuinely orphaned modules — no references of any kind.
    (tmp_path / "src" / "pkg" / "orphan.py").write_text("# nothing imports me\n")
    (tmp_path / "src" / "other_pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "other_pkg" / "orphan_too.py").write_text("# nor me\n")
    (tmp_path / "src" / "top_level_orphan.py").write_text("# nor me\n")

    # `git grep` requires the files to be tracked in git.
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture")

    return tmp_path


# ---------------------------------------------------------------------------
# Module enumeration
# ---------------------------------------------------------------------------


def test_enumerate_modules_skips_init_files(repo: Path) -> None:
    script = _load_script(repo)
    dotted_paths = [d for d, _ in script._enumerate_modules()]

    assert "src.pkg.leaf" in dotted_paths
    assert "src.pkg.sub.deep" in dotted_paths
    # __init__.py files must NOT appear as candidates.
    assert "src.pkg" not in dotted_paths
    assert "src.pkg.sub" not in dotted_paths


# ---------------------------------------------------------------------------
# Absolute-import pass (existing behaviour, kept green)
# ---------------------------------------------------------------------------


def test_absolute_import_is_detected(repo: Path) -> None:
    script = _load_script(repo)
    src_file = repo / "src" / "pkg" / "absolute_only.py"

    assert script._has_reference("src.pkg.absolute_only", src_file) is True


def test_module_with_no_references_is_unused(repo: Path) -> None:
    script = _load_script(repo)

    assert script._has_reference(
        "src.pkg.orphan", repo / "src" / "pkg" / "orphan.py"
    ) is False
    assert script._has_reference(
        "src.other_pkg.orphan_too", repo / "src" / "other_pkg" / "orphan_too.py"
    ) is False


# ---------------------------------------------------------------------------
# Relative-import pass — the bug this commit fixes
# ---------------------------------------------------------------------------


def test_single_dot_relative_import_is_detected(repo: Path) -> None:
    script = _load_script(repo)
    src_file = repo / "src" / "pkg" / "leaf.py"

    # Re-exported by pkg/__init__.py via ``from .leaf import LeafThing``.
    assert script._has_reference("src.pkg.leaf", src_file) is True


def test_relative_subpackage_import_is_detected(repo: Path) -> None:
    script = _load_script(repo)
    src_file = repo / "src" / "pkg" / "sub" / "deep.py"

    # pkg/__init__.py does ``from .sub.deep import DeepThing``.
    assert script._has_reference("src.pkg.sub.deep", src_file) is True


def test_from_dot_import_name_form_is_detected(repo: Path) -> None:
    script = _load_script(repo)
    src_file = repo / "src" / "pkg" / "used_by_dot_import.py"

    # pkg/__init__.py does ``from . import used_by_dot_import``.
    assert script._has_reference("src.pkg.used_by_dot_import", src_file) is True


def test_multi_dot_relative_import_is_detected(repo: Path) -> None:
    script = _load_script(repo)
    src_file = repo / "src" / "pkg" / "cousin.py"

    # pkg/cousin_user.py does ``from ..pkg.cousin import CousinThing``.
    assert script._has_reference("src.pkg.cousin", src_file) is True


def test_relative_search_is_scoped_to_package_root(repo: Path) -> None:
    """A leaf-name collision in an unrelated package must not produce a
    false negative for the unrelated module.

    We add ``src/other_pkg/leaf.py`` (no references) and verify it is
    still flagged as unused even though ``src/pkg/leaf.py`` is referenced
    via ``from .leaf import LeafThing`` from ``src/pkg/__init__.py``.
    """
    other_leaf = repo / "src" / "other_pkg" / "leaf.py"
    other_leaf.write_text("# unrelated; no references\n")
    _git(repo, "add", str(other_leaf))
    _git(repo, "commit", "-q", "-m", "add other_pkg.leaf")

    script = _load_script(repo)

    assert script._has_reference("src.other_pkg.leaf", other_leaf) is False
    # Sanity: original ``src.pkg.leaf`` is still detected as referenced.
    assert script._has_reference(
        "src.pkg.leaf", repo / "src" / "pkg" / "leaf.py"
    ) is True


def test_top_level_module_skips_relative_pass(repo: Path) -> None:
    """Modules directly under ``src/`` (e.g. ``src/foo.py``) cannot be the
    target of a relative import — there is no parent package to anchor a
    leading dot. The relative pass must early-exit so we do not waste a
    grep call (and so we never accidentally match an unrelated module
    whose leaf name happens to collide)."""
    script = _load_script(repo)

    assert script._has_relative_reference(
        "src.top_level_orphan", repo / "src" / "top_level_orphan.py"
    ) is False


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------


def test_allowlist_excludes_modules_from_unused_report(
    repo: Path, tmp_path: Path
) -> None:
    script = _load_script(repo)
    allowlist_path = tmp_path / "allowlist.txt"
    allowlist_path.write_text(
        "# comment line\n"
        "src.pkg.orphan   # inline comment\n"
        "\n"
        "src.other_pkg.orphan_too\n"
    )

    loaded = script._load_allowlist(allowlist_path)

    assert loaded == {"src.pkg.orphan", "src.other_pkg.orphan_too"}


def test_load_allowlist_handles_missing_file(tmp_path: Path) -> None:
    script = _load_script(tmp_path)

    assert script._load_allowlist(tmp_path / "no_such.txt") == set()
    assert script._load_allowlist(None) == set()

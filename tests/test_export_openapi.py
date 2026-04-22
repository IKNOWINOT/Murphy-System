"""Tests for ``scripts/export_openapi.py``.

Class S Roadmap, Item 14 — locks in the script's pure-Python surface so that
the follow-up PR which wires ``--check`` into CI does not accidentally
regress its argument parsing, factory dispatch, schema-comparison, or
output formatting.

These tests deliberately avoid importing the real FastAPI ``create_app``
factory: the script's helpers accept any object with an ``openapi()``
method, so a tiny stub is sufficient and the suite stays fast and
hermetic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Loader: import scripts/export_openapi.py without requiring scripts/ to be
# a package (it intentionally is not — the scripts/ directory holds
# standalone CLIs, not an importable package).
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "export_openapi.py"
)


@pytest.fixture(scope="module")
def export_openapi() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_test_export_openapi", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubApp:
    """Minimal stand-in for a FastAPI app — only the .openapi() method is
    exercised by the script."""

    def __init__(self, schema: dict) -> None:
        self._schema = schema

    def openapi(self) -> dict:
        return self._schema


_SAMPLE_SCHEMA = {
    "openapi": "3.1.0",
    "info": {"title": "Murphy", "version": "0.0.0"},
    "paths": {},
}


# ---------------------------------------------------------------------------
# _load_app
# ---------------------------------------------------------------------------


def test_load_app_resolves_attribute(export_openapi, monkeypatch) -> None:
    fake = ModuleType("fake_app_mod_attr")
    fake.app = _StubApp(_SAMPLE_SCHEMA)
    monkeypatch.setitem(sys.modules, "fake_app_mod_attr", fake)

    app = export_openapi._load_app("fake_app_mod_attr:app")

    assert app is fake.app


def test_load_app_invokes_factory(export_openapi, monkeypatch) -> None:
    fake = ModuleType("fake_app_mod_factory")
    expected = _StubApp(_SAMPLE_SCHEMA)
    fake.create_app = lambda: expected
    monkeypatch.setitem(sys.modules, "fake_app_mod_factory", fake)

    app = export_openapi._load_app("fake_app_mod_factory:create_app()")

    assert app is expected


def test_load_app_rejects_target_without_colon(export_openapi) -> None:
    with pytest.raises(SystemExit, match="module.path:attribute"):
        export_openapi._load_app("nope_no_colon")


def test_load_app_raises_on_missing_attribute(export_openapi, monkeypatch) -> None:
    fake = ModuleType("fake_app_mod_missing_attr")
    monkeypatch.setitem(sys.modules, "fake_app_mod_missing_attr", fake)

    with pytest.raises(SystemExit, match="has no attribute"):
        export_openapi._load_app("fake_app_mod_missing_attr:does_not_exist")


def test_load_app_rejects_non_callable_factory(export_openapi, monkeypatch) -> None:
    fake = ModuleType("fake_app_mod_non_callable")
    fake.app = _StubApp(_SAMPLE_SCHEMA)  # not a callable factory
    monkeypatch.setitem(sys.modules, "fake_app_mod_non_callable", fake)

    with pytest.raises(SystemExit, match="not callable"):
        export_openapi._load_app("fake_app_mod_non_callable:app()")


# ---------------------------------------------------------------------------
# _generate_schema
# ---------------------------------------------------------------------------


def test_generate_schema_returns_app_schema(export_openapi) -> None:
    app = _StubApp(_SAMPLE_SCHEMA)
    assert export_openapi._generate_schema(app) == _SAMPLE_SCHEMA


def test_generate_schema_rejects_non_fastapi_object(export_openapi) -> None:
    not_an_app = SimpleNamespace()  # no .openapi attribute

    with pytest.raises(SystemExit, match="openapi\\(\\)"):
        export_openapi._generate_schema(not_an_app)


# ---------------------------------------------------------------------------
# _write — deterministic, sorted-key, trailing-newline JSON
# ---------------------------------------------------------------------------


def test_write_produces_sorted_indented_json(export_openapi, tmp_path) -> None:
    out = tmp_path / "nested" / "openapi.json"
    schema = {"b": 2, "a": 1, "nested": {"y": 0, "x": 0}}

    export_openapi._write(schema, out)

    text = out.read_text(encoding="utf-8")
    # Trailing newline is part of the contract — required for git-friendly
    # diffs on the committed docs/openapi.json.
    assert text.endswith("\n")
    # sort_keys=True is required so the on-disk file is stable across
    # FastAPI versions that emit dicts in non-deterministic insertion order.
    assert text.index('"a"') < text.index('"b"')
    # Round-trip preserves content.
    assert json.loads(text) == schema
    # Parent directories are created on demand.
    assert out.parent.is_dir()


# ---------------------------------------------------------------------------
# _check
# ---------------------------------------------------------------------------


def test_check_passes_when_schema_matches(export_openapi, tmp_path) -> None:
    out = tmp_path / "openapi.json"
    export_openapi._write(_SAMPLE_SCHEMA, out)

    assert export_openapi._check(_SAMPLE_SCHEMA, out) == 0


def test_check_fails_when_schema_differs(export_openapi, tmp_path, capsys) -> None:
    out = tmp_path / "openapi.json"
    export_openapi._write(_SAMPLE_SCHEMA, out)

    drifted = dict(_SAMPLE_SCHEMA)
    drifted["info"] = {"title": "Murphy", "version": "9.9.9"}

    assert export_openapi._check(drifted, out) == 1
    err = capsys.readouterr().err
    assert "out of date" in err
    assert "export_openapi.py" in err


def test_check_fails_when_output_missing(export_openapi, tmp_path, capsys) -> None:
    missing = tmp_path / "no_such.json"

    assert export_openapi._check(_SAMPLE_SCHEMA, missing) == 1
    err = capsys.readouterr().err
    assert "does not exist" in err


# ---------------------------------------------------------------------------
# main — end-to-end via argv
# ---------------------------------------------------------------------------


def test_main_writes_schema(export_openapi, tmp_path, monkeypatch, capsys) -> None:
    fake = ModuleType("fake_app_mod_main_write")
    fake.app = _StubApp(_SAMPLE_SCHEMA)
    monkeypatch.setitem(sys.modules, "fake_app_mod_main_write", fake)

    out = tmp_path / "openapi.json"
    rc = export_openapi.main(
        ["--app", "fake_app_mod_main_write:app", "--output", str(out)]
    )

    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8")) == _SAMPLE_SCHEMA
    assert f"wrote {out}" in capsys.readouterr().out


def test_main_check_succeeds_when_in_sync(
    export_openapi, tmp_path, monkeypatch
) -> None:
    fake = ModuleType("fake_app_mod_main_check_ok")
    fake.app = _StubApp(_SAMPLE_SCHEMA)
    monkeypatch.setitem(sys.modules, "fake_app_mod_main_check_ok", fake)

    out = tmp_path / "openapi.json"
    # Seed the on-disk file using the same writer the script uses.
    export_openapi._write(_SAMPLE_SCHEMA, out)

    rc = export_openapi.main(
        [
            "--app",
            "fake_app_mod_main_check_ok:app",
            "--output",
            str(out),
            "--check",
        ]
    )

    assert rc == 0


def test_main_check_fails_when_drifted(
    export_openapi, tmp_path, monkeypatch
) -> None:
    fake = ModuleType("fake_app_mod_main_check_drift")
    fake.app = _StubApp(_SAMPLE_SCHEMA)
    monkeypatch.setitem(sys.modules, "fake_app_mod_main_check_drift", fake)

    out = tmp_path / "openapi.json"
    # Seed with a *different* schema so check should fail.
    export_openapi._write({"openapi": "3.1.0", "info": {}, "paths": {"/old": {}}}, out)

    rc = export_openapi.main(
        [
            "--app",
            "fake_app_mod_main_check_drift:app",
            "--output",
            str(out),
            "--check",
        ]
    )

    assert rc == 1

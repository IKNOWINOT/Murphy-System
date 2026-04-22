#!/usr/bin/env python3
"""
export_openapi.py — dump the FastAPI app's OpenAPI schema to disk.

Class S Roadmap, Item 14: stable, versioned API contract for external
consumers. The output is committed at ``docs/openapi.json`` so that schema
drift is reviewable in pull requests.

Usage
-----
    # Default: write docs/openapi.json
    python scripts/export_openapi.py

    # Custom output:
    python scripts/export_openapi.py --output build/openapi.json

    # Choose a different app entrypoint (must export `app: FastAPI`):
    python scripts/export_openapi.py --app src.runtime.app:app

The script imports the app lazily and exits non-zero on any failure so it can
be used as a CI gate (``--check`` mode compares the generated schema to the
file on disk and fails if they differ).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any


_DEFAULT_APP = "src.runtime.app:app"
_DEFAULT_OUTPUT = Path("docs") / "openapi.json"


def _load_app(target: str) -> Any:
    """Import ``module:attr`` and return the FastAPI instance."""
    if ":" not in target:
        raise SystemExit(
            f"--app must be of the form 'module.path:attribute'; got {target!r}"
        )
    module_path, attr = target.split(":", 1)
    module = importlib.import_module(module_path)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise SystemExit(
            f"Module {module_path!r} has no attribute {attr!r}"
        ) from exc


def _generate_schema(app: Any) -> dict[str, Any]:
    """Return the OpenAPI schema dict produced by FastAPI."""
    if not hasattr(app, "openapi"):
        raise SystemExit(
            "Loaded object does not expose an `openapi()` method — is it a FastAPI app?"
        )
    return app.openapi()


def _write(schema: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check(schema: dict[str, Any], output: Path) -> int:
    """Return 0 if the on-disk schema matches the generated one, else 1."""
    if not output.exists():
        sys.stderr.write(
            f"error: {output} does not exist; run without --check to generate it\n"
        )
        return 1
    on_disk = json.loads(output.read_text(encoding="utf-8"))
    if on_disk == schema:
        return 0
    sys.stderr.write(
        f"error: OpenAPI schema in {output} is out of date; "
        f"re-run `python scripts/export_openapi.py` and commit the result\n"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app",
        default=_DEFAULT_APP,
        help=f"FastAPI app target as module:attr (default: {_DEFAULT_APP})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Path to write the schema (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the on-disk schema is out of date instead of writing.",
    )
    args = parser.parse_args(argv)

    app = _load_app(args.app)
    schema = _generate_schema(app)

    if args.check:
        return _check(schema, args.output)

    _write(schema, args.output)
    print(f"wrote {args.output} ({len(json.dumps(schema))} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

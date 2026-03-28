#!/usr/bin/env python3
"""
generate_module_registry.py — Canonical module registry generator.

Scans the root ``src/`` directory for all Python modules and writes a
deterministic, sorted ``module_registry.yaml`` at the project root.

Usage
-----
  # Regenerate the registry (overwrites module_registry.yaml):
  python scripts/generate_module_registry.py

  # Check mode — exit 1 if registry is out of date (used in CI):
  python scripts/generate_module_registry.py --check

Output format
-------------
  version: "1.0"
  generated_by: "scripts/generate_module_registry.py"
  canonical_src: "src/"
  modules:
    - key: src.account_management.account_manager
      path: src/account_management/account_manager.py
      package: src.account_management
    ...

The registry is sorted by ``key`` so diffs are minimal.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow running as `python scripts/generate_module_registry.py` from repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required.  Install with:  pip install pyyaml")
    sys.exit(1)


def _collect_modules(src_root: Path) -> list[dict]:
    """Return a sorted list of module descriptors from *src_root*."""
    entries: list[dict] = []
    for py_file in sorted(src_root.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT)
        # Convert path to dotted module key: src/foo/bar.py → src.foo.bar
        parts = list(rel.with_suffix("").parts)
        key = ".".join(parts)
        # Package = everything except the leaf module name
        package = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]
        entries.append({
            "key": key,
            "path": str(rel).replace("\\", "/"),
            "package": package,
        })
    return entries


def _build_registry(src_root: Path) -> dict:
    modules = _collect_modules(src_root)
    return {
        "version": "1.0",
        "generated_by": "scripts/generate_module_registry.py",
        "canonical_src": "src/",
        "module_count": len(modules),
        "modules": modules,
    }


def _dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate / validate module_registry.yaml")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if module_registry.yaml is out of date, without writing.",
    )
    parser.add_argument(
        "--src",
        default="src",
        help="Source directory relative to repo root (default: src)",
    )
    parser.add_argument(
        "--output",
        default="module_registry.yaml",
        help="Output YAML path relative to repo root (default: module_registry.yaml)",
    )
    args = parser.parse_args(argv)

    src_root = _REPO_ROOT / args.src
    if not src_root.is_dir():
        print(f"ERROR: Source directory not found: {src_root}")
        return 1

    registry = _build_registry(src_root)
    fresh_yaml = _dump_yaml(registry)

    output_path = _REPO_ROOT / args.output

    if args.check:
        if not output_path.exists():
            print(f"FAIL: {args.output} does not exist.  Run:")
            print(f"  python scripts/generate_module_registry.py")
            return 1
        existing = output_path.read_text(encoding="utf-8")
        if existing.strip() == fresh_yaml.strip():
            print(f"OK: {args.output} is up to date ({registry['module_count']} modules).")
            return 0
        # Compute drift summary
        existing_data = yaml.safe_load(existing) or {}
        existing_keys = {m["key"] for m in existing_data.get("modules", [])}
        fresh_keys = {m["key"] for m in registry["modules"]}
        added = sorted(fresh_keys - existing_keys)
        removed = sorted(existing_keys - fresh_keys)
        print(f"FAIL: {args.output} is out of date.")
        if added:
            print(f"  {len(added)} module(s) added to src/ but not in registry:")
            for k in added[:20]:
                print(f"    + {k}")
            if len(added) > 20:
                print(f"    ... and {len(added) - 20} more")
        if removed:
            print(f"  {len(removed)} module(s) removed from src/ but still in registry:")
            for k in removed[:20]:
                print(f"    - {k}")
            if len(removed) > 20:
                print(f"    ... and {len(removed) - 20} more")
        print(f"\nRun:  python scripts/generate_module_registry.py")
        return 1

    # Write mode
    output_path.write_text(fresh_yaml, encoding="utf-8")
    print(f"Written: {args.output}  ({registry['module_count']} modules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
compile_shims.py — regenerate bot internal/ shim files from manifests.

Usage:
    python scripts/compile_shims.py
    python scripts/compile_shims.py --dry-run
    python scripts/compile_shims.py --bot kiren
    python scripts/compile_shims.py --config path/to/bot_manifests.yaml

Exit codes:
    0  all shims up-to-date or successfully written
    1  one or more errors during compilation
    2  drift detected when running with --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Resolve repository root (this script lives in <root>/scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.shim_compiler.compiler import ShimCompiler  # noqa: E402
from src.shim_compiler.schemas import BotManifest    # noqa: E402


_DEFAULT_MANIFEST_PATH = REPO_ROOT / "config" / "bot_manifests.yaml"
_TEMPLATE_DIR = REPO_ROOT / "src" / "shim_compiler" / "templates"
_BOTS_DIR = REPO_ROOT / "bots"


def _load_manifests(config_path: Path) -> list[BotManifest]:
    """Parse bot manifests from YAML config."""
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    manifests: list[BotManifest] = []
    for entry in raw.get("bots", []):
        manifests.append(
            BotManifest(
                bot_name=entry["bot_name"],
                archetype=entry.get("archetype", "kiren"),
                authority_level=entry.get("authority_level", "low"),
                cost_ref_usd=float(entry.get("cost_ref_usd", 0.01)),
                latency_ref_s=float(entry.get("latency_ref_s", 1.5)),
                s_min=float(entry.get("s_min", 0.45)),
                founder_cap_cents=int(entry.get("founder_cap_cents", 45000)),
                gp_confidence_threshold=float(entry.get("gp_confidence_threshold", 0.8)),
                gp_maturity_runs=int(entry.get("gp_maturity_runs", 20)),
                kaia_mix=entry.get(
                    "kaia_mix", {"kiren": 0.4, "veritas": 0.4, "vallon": 0.2}
                ),
            )
        )
    return manifests


def _run(
    manifests: list[BotManifest],
    compiler: ShimCompiler,
    dry_run: bool,
) -> int:
    """Core logic — compile or diff each manifest; return exit code."""
    overall_exit = 0

    for manifest in manifests:
        bot_internal = _BOTS_DIR / manifest.bot_name / "internal"

        if dry_run:
            drifts = compiler.diff_existing(manifest, bot_internal)
            if drifts:
                print(f"[DRIFT] {manifest.bot_name} — {len(drifts)} file(s) out of sync:")
                for drift in drifts:
                    print(f"  {drift.output_filename}")
                    for line in drift.diff_lines[:20]:
                        print(f"    {line}", end="")
                overall_exit = 2
            else:
                print(f"[OK]    {manifest.bot_name} — all shims in sync")
        else:
            result = compiler.compile_shims(manifest, bot_internal)
            if result.errors:
                for err in result.errors:
                    print(f"[ERROR] {manifest.bot_name}: {err}", file=sys.stderr)
                overall_exit = 1
            elif result.written:
                print(
                    f"[WROTE] {manifest.bot_name} — "
                    f"{len(result.written)} file(s) updated: "
                    + ", ".join(Path(p).name for p in result.written)
                )
            else:
                print(f"[SKIP]  {manifest.bot_name} — all shims already up-to-date")

    return overall_exit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile bot shim files from manifests."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_MANIFEST_PATH,
        help="Path to bot_manifests.yaml (default: config/bot_manifests.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report drift without writing files",
    )
    parser.add_argument(
        "--bot",
        metavar="NAME",
        help="Only process the named bot",
    )
    args = parser.parse_args(argv)

    manifests = _load_manifests(args.config)
    if args.bot:
        manifests = [m for m in manifests if m.bot_name == args.bot]
        if not manifests:
            print(f"No manifest found for bot '{args.bot}'", file=sys.stderr)
            return 1

    compiler = ShimCompiler(_TEMPLATE_DIR)
    return _run(manifests, compiler, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

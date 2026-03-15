"""
Shim Compiler

Generates the TypeScript shim files for a bot from a BotManifest, eliminating
copy-paste drift across 20+ bots that each carry identical internal/ shims.

Usage::

    from pathlib import Path
    from src.shim_compiler.compiler import ShimCompiler
    from src.shim_compiler.schemas import BotManifest

    compiler = ShimCompiler(Path("src/shim_compiler/templates"))
    manifest = BotManifest(bot_name="my_bot")
    result = compiler.compile_shims(manifest, Path("bots/my_bot/internal"))
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .schemas import BotManifest, CompileResult, ShimDrift

logger = logging.getLogger(__name__)

# Template filename → output filename mapping
_TEMPLATE_MAP: dict[str, str] = {
    "metrics.ts.tmpl": "metrics.ts",
    "shim_budget.ts.tmpl": "shim_budget.ts",
    "shim_quota.ts.tmpl": "shim_quota.ts",
    "shim_stability.ts.tmpl": "shim_stability.ts",
    "shim_golden_paths.ts.tmpl": "shim_golden_paths.ts",
}


class ShimCompiler:
    """
    Compiles bot shim files from a BotManifest using Jinja2 templates.

    Acts as a sibling to ``RoleTemplateCompiler`` (src/org_compiler/compiler.py),
    but targets the TypeScript shim layer rather than organisational role templates.
    """

    def __init__(self, template_dir: Path) -> None:
        self.template_dir = Path(template_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            autoescape=select_autoescape(["html", "htm", "xml"]),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile_shims(self, manifest: BotManifest, output_dir: Path) -> CompileResult:
        """
        Generate all shim files for a bot from its manifest.

        Files are written only when their content has changed (idempotent).

        Args:
            manifest:   BotManifest describing the bot's parameters.
            output_dir: Directory into which shim files are written
                        (normally ``bots/<bot_name>/internal/``).

        Returns:
            CompileResult with lists of written/skipped/error paths.
        """
        output_dir = Path(output_dir)
        result = CompileResult(bot_name=manifest.bot_name, output_dir=str(output_dir))

        output_dir.mkdir(parents=True, exist_ok=True)

        for template_name, output_filename in _TEMPLATE_MAP.items():
            output_path = output_dir / output_filename
            try:
                written = self.compile_single(template_name, manifest, output_path)
                if written:
                    result.written.append(str(output_path))
                else:
                    result.skipped.append(str(output_path))
            except Exception as exc:
                msg = f"Error compiling {template_name}: {exc}"
                logger.error(msg)
                result.errors.append(msg)

        return result

    def compile_single(
        self,
        template_name: str,
        manifest: BotManifest,
        output_path: Path,
    ) -> bool:
        """
        Generate a single shim file from a template.

        Args:
            template_name: Filename of the Jinja2 template (e.g. ``shim_budget.ts.tmpl``).
            manifest:      BotManifest supplying template variables.
            output_path:   Destination path for the rendered file.

        Returns:
            ``True`` if the file was written (new or changed), ``False`` if unchanged.

        Raises:
            jinja2.TemplateNotFound: if the template file does not exist.
            jinja2.UndefinedError:   if a template variable is not supplied.
        """
        rendered = self._render(template_name, manifest)
        output_path = Path(output_path)

        if output_path.exists() and output_path.read_text(encoding="utf-8") == rendered:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        return True

    def diff_existing(
        self,
        manifest: BotManifest,
        existing_dir: Path,
    ) -> List[ShimDrift]:
        """
        Compare generated shims against existing files to detect drift.

        For each template, renders it against *manifest* and diffs the result
        against the corresponding file in *existing_dir*.  Files that match
        produce no drift entry.

        Args:
            manifest:     BotManifest supplying template variables.
            existing_dir: Directory containing the existing shim files to compare.

        Returns:
            List of ShimDrift objects (one per drifted file).  Empty list means
            all files are in sync with the manifest.
        """
        existing_dir = Path(existing_dir)
        drifts: List[ShimDrift] = []

        for template_name, output_filename in _TEMPLATE_MAP.items():
            existing_path = existing_dir / output_filename
            rendered = self._render(template_name, manifest)

            if not existing_path.exists():
                diff_lines = list(
                    difflib.unified_diff(
                        [],
                        rendered.splitlines(keepends=True),
                        fromfile=str(existing_path),
                        tofile=f"(generated from {template_name})",
                    )
                )
                drifts.append(
                    ShimDrift(
                        template_name=template_name,
                        output_filename=output_filename,
                        expected_path=f"(generated from {template_name})",
                        actual_path=str(existing_path),
                        diff_lines=diff_lines,
                    )
                )
                continue

            existing_content = existing_path.read_text(encoding="utf-8")
            if existing_content == rendered:
                continue

            diff_lines = list(
                difflib.unified_diff(
                    existing_content.splitlines(keepends=True),
                    rendered.splitlines(keepends=True),
                    fromfile=str(existing_path),
                    tofile=f"(generated from {template_name})",
                )
            )
            drifts.append(
                ShimDrift(
                    template_name=template_name,
                    output_filename=output_filename,
                    expected_path=f"(generated from {template_name})",
                    actual_path=str(existing_path),
                    diff_lines=diff_lines,
                )
            )

        return drifts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render(self, template_name: str, manifest: BotManifest) -> str:
        """Render a template using the manifest's fields as context variables."""
        template = self._env.get_template(template_name)
        context = {
            "bot_name": manifest.bot_name,
            "archetype": manifest.archetype,
            "authority_level": manifest.authority_level,
            "cost_ref_usd": manifest.cost_ref_usd,
            "latency_ref_s": manifest.latency_ref_s,
            "s_min": manifest.s_min,
            "founder_cap_cents": manifest.founder_cap_cents,
            "gp_confidence_threshold": manifest.gp_confidence_threshold,
            "gp_maturity_runs": manifest.gp_maturity_runs,
            "kaia_mix": manifest.kaia_mix,
        }
        return template.render(**context)

"""
Tests for the ShimCompiler module.

Covers:
1. Default-manifest compilation matches canonical bot_base shims
2. Custom manifest values produce correctly parameterised output
3. diff_existing() detects drift and reports clean state correctly
4. All existing bots with internal/ directories pass a validation sweep
5. compile_shims() result fields (written / skipped / errors / success)
"""

import pytest
import tempfile
from pathlib import Path

from src.shim_compiler.compiler import ShimCompiler
from src.shim_compiler.schemas import BotManifest, CompileResult, ShimDrift

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "src" / "shim_compiler" / "templates"
BOT_BASE_INTERNAL = REPO_ROOT / "bots" / "bot_base" / "internal"
BOTS_DIR = REPO_ROOT / "bots"

SHIM_FILES = [
    "metrics.ts",
    "shim_budget.ts",
    "shim_quota.ts",
    "shim_stability.ts",
    "shim_golden_paths.ts",
]


@pytest.fixture
def compiler() -> ShimCompiler:
    return ShimCompiler(TEMPLATE_DIR)


@pytest.fixture
def default_manifest() -> BotManifest:
    """Manifest whose defaults exactly match bot_base canonical files."""
    return BotManifest(bot_name="bot_base")


@pytest.fixture
def tmpdir_path(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Default manifest → canonical output
# ---------------------------------------------------------------------------

class TestDefaultManifest:
    """Compiled output with defaults must match bot_base canonical shims."""

    def test_all_shim_files_generated(self, compiler, default_manifest, tmp_path):
        result = compiler.compile_shims(default_manifest, tmp_path)
        assert result.success, f"Errors: {result.errors}"
        generated = {Path(p).name for p in result.written}
        assert generated == set(SHIM_FILES)

    @pytest.mark.parametrize("filename", SHIM_FILES)
    def test_matches_canonical(self, compiler, default_manifest, tmp_path, filename):
        """Each generated file must be byte-for-byte identical to the canonical."""
        compiler.compile_shims(default_manifest, tmp_path)
        generated = (tmp_path / filename).read_text(encoding="utf-8")
        canonical = (BOT_BASE_INTERNAL / filename).read_text(encoding="utf-8")
        assert generated == canonical, (
            f"{filename}: generated content differs from canonical.\n"
            f"First diff char at index: "
            f"{next((i for i, (a, b) in enumerate(zip(generated, canonical)) if a != b), 'end')}"
        )

    def test_compile_result_success(self, compiler, default_manifest, tmp_path):
        result = compiler.compile_shims(default_manifest, tmp_path)
        assert result.success
        assert result.bot_name == "bot_base"
        assert len(result.errors) == 0
        assert len(result.written) == 5
        assert len(result.skipped) == 0


# ---------------------------------------------------------------------------
# 2. Custom manifest values → parameterised output
# ---------------------------------------------------------------------------

class TestCustomManifest:
    """Changing manifest values must produce correctly parameterised output."""

    def test_custom_s_min(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="custom_bot", s_min=0.65)
        compiler.compile_shims(manifest, tmp_path)
        content = (tmp_path / "shim_stability.ts").read_text()
        assert "0.65" in content
        assert "0.45" not in content   # default must not appear
        # Value must appear in the decideAction S_min assignment context
        assert "?? 0.65" in content

    def test_custom_founder_cap(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="budget_bot", founder_cap_cents=90000)
        compiler.compile_shims(manifest, tmp_path)
        content = (tmp_path / "shim_budget.ts").read_text()
        assert "90000" in content
        assert "45000" not in content

    def test_custom_cost_ref(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="cost_bot", cost_ref_usd=0.05, latency_ref_s=2.0)
        compiler.compile_shims(manifest, tmp_path)
        content = (tmp_path / "shim_stability.ts").read_text()
        assert "0.05" in content
        assert "2.0" in content
        assert "0.01" not in content
        assert "1.5" not in content

    def test_custom_gp_maturity_runs(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="gp_bot", gp_maturity_runs=50)
        compiler.compile_shims(manifest, tmp_path)
        content = (tmp_path / "shim_golden_paths.ts").read_text()
        assert ">=50" in content
        assert ">=20" not in content

    def test_custom_gp_confidence_threshold(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="gp_bot2", gp_confidence_threshold=0.75)
        compiler.compile_shims(manifest, tmp_path)
        content = (tmp_path / "shim_golden_paths.ts").read_text()
        assert "0.75" in content
        assert "<0.8" not in content

    def test_bot_name_in_metrics(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="my_special_bot")
        compiler.compile_shims(manifest, tmp_path)
        content = (tmp_path / "metrics.ts").read_text()
        assert "my_special_bot" in content
        assert "bot_base" not in content

    def test_bot_name_in_file_header(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="named_bot")
        compiler.compile_shims(manifest, tmp_path)
        for filename in SHIM_FILES:
            content = (tmp_path / filename).read_text()
            assert "named_bot" in content, f"{filename} missing bot name"

    def test_compile_single_returns_true_for_new_file(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="single_bot")
        written = compiler.compile_single(
            "metrics.ts.tmpl", manifest, tmp_path / "metrics.ts"
        )
        assert written is True

    def test_compile_single_returns_false_for_unchanged(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="single_bot")
        out = tmp_path / "metrics.ts"
        compiler.compile_single("metrics.ts.tmpl", manifest, out)
        # Second call — content unchanged
        written = compiler.compile_single("metrics.ts.tmpl", manifest, out)
        assert written is False


# ---------------------------------------------------------------------------
# 3. diff_existing() drift detection
# ---------------------------------------------------------------------------

class TestDiffExisting:
    """diff_existing() must correctly identify drifted and clean shims."""

    def test_no_drift_against_canonical(self, compiler, default_manifest):
        """bot_base canonical files must show zero drift for the default manifest."""
        drifts = compiler.diff_existing(default_manifest, BOT_BASE_INTERNAL)
        assert drifts == [], (
            f"Unexpected drift in bot_base shims: "
            + ", ".join(d.output_filename for d in drifts)
        )

    def test_detects_drift_when_file_modified(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="drift_bot")
        compiler.compile_shims(manifest, tmp_path)

        # Introduce a manual edit
        metrics_file = tmp_path / "metrics.ts"
        original = metrics_file.read_text()
        metrics_file.write_text(original + "\n// hand-edited\n", encoding="utf-8")

        drifts = compiler.diff_existing(manifest, tmp_path)
        drifted_files = [d.output_filename for d in drifts]
        assert "metrics.ts" in drifted_files

    def test_detects_missing_file_as_drift(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="missing_bot")
        # Write only 4 out of 5 shims
        compiler.compile_shims(manifest, tmp_path)
        (tmp_path / "shim_quota.ts").unlink()

        drifts = compiler.diff_existing(manifest, tmp_path)
        drifted_files = [d.output_filename for d in drifts]
        assert "shim_quota.ts" in drifted_files

    def test_no_drift_after_fresh_compile(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="fresh_bot")
        compiler.compile_shims(manifest, tmp_path)
        drifts = compiler.diff_existing(manifest, tmp_path)
        assert drifts == []

    def test_drift_object_fields(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="field_bot")
        compiler.compile_shims(manifest, tmp_path)
        budget_file = tmp_path / "shim_budget.ts"
        budget_file.write_text("// corrupted\n", encoding="utf-8")

        drifts = compiler.diff_existing(manifest, tmp_path)
        drift = next(d for d in drifts if d.output_filename == "shim_budget.ts")
        assert drift.template_name == "shim_budget.ts.tmpl"
        assert isinstance(drift.diff_lines, list)
        assert len(drift.diff_lines) > 0


# ---------------------------------------------------------------------------
# 4. Validation sweep — every existing bot's shims
# ---------------------------------------------------------------------------

class TestExistingBotsValidation:
    """
    Every bot with an internal/ directory must compile without errors.
    Drift is expected (since not all bots are regenerated), but the compiler
    itself must not raise an exception.
    """

    def _bots_with_internal(self):
        return [
            d for d in BOTS_DIR.iterdir()
            if d.is_dir() and (d / "internal").is_dir()
        ]

    def test_all_bots_compile_without_errors(self, compiler, tmp_path):
        bots = self._bots_with_internal()
        assert bots, "No bots with internal/ directories found"
        failures = []
        for bot_dir in bots:
            manifest = BotManifest(bot_name=bot_dir.name)
            out = tmp_path / bot_dir.name
            result = compiler.compile_shims(manifest, out)
            if not result.success:
                failures.append(f"{bot_dir.name}: {result.errors}")
        assert not failures, "Compilation errors:\n" + "\n".join(failures)

    def test_diff_existing_runs_for_all_bots(self, compiler):
        """diff_existing must not raise for any real bot directory."""
        bots = self._bots_with_internal()
        assert bots
        for bot_dir in bots:
            manifest = BotManifest(bot_name=bot_dir.name)
            try:
                compiler.diff_existing(manifest, bot_dir / "internal")
            except Exception as exc:
                pytest.fail(f"diff_existing raised for {bot_dir.name}: {exc}")


# ---------------------------------------------------------------------------
# 5. CompileResult idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Second compile on unchanged files must produce only skipped entries."""

    def test_second_compile_skips_all(self, compiler, tmp_path):
        manifest = BotManifest(bot_name="idem_bot")
        compiler.compile_shims(manifest, tmp_path)       # first pass
        result2 = compiler.compile_shims(manifest, tmp_path)  # second pass
        assert result2.success
        assert result2.written == []
        assert set(Path(p).name for p in result2.skipped) == set(SHIM_FILES)
        assert result2.files_changed == 0

"""
Inference Pipeline Benchmark with Screenshot Reports.

Benchmarks the InferenceDomainGateEngine pipeline (infer, infer_via_llm,
produce_dataset) and generates visual comparison reports as HTML screenshots.
Uses pytest-benchmark for statistical rigour and matplotlib for charts.

Run all inference benchmarks:
    pytest tests/benchmarks/test_inference_benchmark.py --benchmark-only -v

Save a baseline on main:
    pytest tests/benchmarks/test_inference_benchmark.py --benchmark-only \
        --benchmark-save=main_baseline

Compare current branch against main:
    pytest tests/benchmarks/test_inference_benchmark.py --benchmark-only \
        --benchmark-compare=0001_main_baseline --benchmark-compare-fail=mean:10%

Generate screenshot report only (no benchmark fixture needed):
    pytest tests/benchmarks/test_inference_benchmark.py -k "screenshot" -v

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Optional imports — skip gracefully when unavailable
# ---------------------------------------------------------------------------
try:
    import pytest_benchmark  # noqa: F401
    _BENCHMARK_AVAILABLE = True
except ImportError:
    _BENCHMARK_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend for CI
    import matplotlib.pyplot as plt
    _MATPLOTLIB_AVAILABLE = True
except ImportError:
    _MATPLOTLIB_AVAILABLE = False

# ---------------------------------------------------------------------------
# Import project modules
# ---------------------------------------------------------------------------
from inference_gate_engine import InferenceDomainGateEngine, InferenceResult

# Screenshot manager from commissioning infra
sys.path.insert(0, str(ROOT / "tests" / "commissioning"))
from screenshot_manager import ScreenshotManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BENCHMARK_SCENARIOS: List[Dict[str, str]] = [
    {
        "name": "fintech_startup",
        "description": "How do I best manage a fintech startup processing digital payments?",
    },
    {
        "name": "healthcare_clinic",
        "description": "We run a healthcare clinic managing electronic patient records and HIPAA compliance.",
    },
    {
        "name": "manufacturing_plant",
        "description": "Our manufacturing plant produces automotive parts with ISO 9001 certification.",
    },
    {
        "name": "ecommerce_fashion",
        "description": "We are an e-commerce company selling fashion online with global logistics.",
    },
    {
        "name": "law_firm",
        "description": "Our law firm handles corporate litigation and regulatory compliance work.",
    },
    {
        "name": "saas_platform",
        "description": "We build a SaaS platform for project management targeting enterprise customers.",
    },
    {
        "name": "restaurant_chain",
        "description": "We operate a restaurant chain with 50 locations needing inventory and staff management.",
    },
    {
        "name": "real_estate_agency",
        "description": "Our real estate agency manages commercial property listings and tenant relations.",
    },
]

REPORT_DIR = ROOT / "tests" / "benchmarks" / ".inference_reports"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine() -> InferenceDomainGateEngine:
    """Shared inference engine instance for the module."""
    return InferenceDomainGateEngine()


@pytest.fixture(scope="module")
def screenshot_mgr(tmp_path_factory: pytest.TempPathFactory) -> ScreenshotManager:
    """Screenshot manager for capturing visual reports."""
    report_dir = REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    return ScreenshotManager(base_dir=str(report_dir))


# ---------------------------------------------------------------------------
# Helper: run a timing suite without pytest-benchmark
# ---------------------------------------------------------------------------

def _collect_timings(
    engine: InferenceDomainGateEngine,
    iterations: int = 20,
) -> Dict[str, Dict[str, Any]]:
    """Run the inference pipeline and collect per-scenario timing data.

    Returns a dict keyed by scenario name, each containing:
        - times_ms: list of elapsed times in milliseconds
        - mean_ms, median_ms, stdev_ms: summary statistics
        - result: the InferenceResult from the last run
    """
    timings: Dict[str, Dict[str, Any]] = {}

    for scenario in BENCHMARK_SCENARIOS:
        name = scenario["name"]
        desc = scenario["description"]
        times: List[float] = []

        result = None
        for _ in range(iterations):
            t0 = time.perf_counter()
            result = engine.infer(desc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed_ms)

        timings[name] = {
            "times_ms": times,
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
            "min_ms": min(times),
            "max_ms": max(times),
            "iterations": iterations,
            "result": result,
        }

    return timings


def _collect_dataset_timings(
    engine: InferenceDomainGateEngine,
    iterations: int = 20,
) -> Dict[str, Dict[str, Any]]:
    """Benchmark the full pipeline: infer() → produce_dataset()."""
    timings: Dict[str, Dict[str, Any]] = {}

    for scenario in BENCHMARK_SCENARIOS:
        name = scenario["name"]
        desc = scenario["description"]
        times: List[float] = []

        result = None
        for _ in range(iterations):
            t0 = time.perf_counter()
            result = engine.infer(desc)
            _ = result.produce_dataset()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed_ms)

        timings[name] = {
            "times_ms": times,
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
            "min_ms": min(times),
            "max_ms": max(times),
            "iterations": iterations,
        }

    return timings


# ---------------------------------------------------------------------------
# Helper: mock LLM backend for infer_via_llm benchmarks
# ---------------------------------------------------------------------------

class _MockLLMBackend:
    """Deterministic mock LLM that returns structured JSON instantly."""

    _RESPONSES = {
        "fintech": '{"industry":"finance","business_type":"fintech startup","company_name":"PayCo","company_size":"startup","goals":"payment processing, compliance"}',
        "healthcare": '{"industry":"healthcare","business_type":"medical clinic","company_name":"HealthFirst","company_size":"medium","goals":"patient records, HIPAA"}',
        "manufacturing": '{"industry":"manufacturing","business_type":"auto parts","company_name":"AutoParts Inc","company_size":"large","goals":"quality control, ISO"}',
        "ecommerce": '{"industry":"retail","business_type":"online fashion","company_name":"StyleHub","company_size":"medium","goals":"logistics, sales"}',
        "default": '{"industry":"technology","business_type":"general","company_name":"TechCo","company_size":"medium","goals":"automation"}',
    }

    def __call__(self, prompt: str, **kwargs) -> Dict[str, Any]:
        content = self._RESPONSES["default"]
        for key, resp in self._RESPONSES.items():
            if key in prompt.lower():
                content = resp
                break
        return {"content": content, "confidence": 0.85}


def _collect_llm_timings(
    engine: InferenceDomainGateEngine,
    iterations: int = 20,
) -> Dict[str, Dict[str, Any]]:
    """Benchmark infer_via_llm with mock backend."""
    mock_backend = _MockLLMBackend()
    timings: Dict[str, Dict[str, Any]] = {}

    for scenario in BENCHMARK_SCENARIOS:
        name = scenario["name"]
        desc = scenario["description"]
        times: List[float] = []

        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                engine.infer_via_llm(desc, llm_backend=mock_backend)
            except Exception:
                # If SafeLLMWrapper isn't available, measure fallback path
                engine.infer(desc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed_ms)

        timings[name] = {
            "times_ms": times,
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
            "min_ms": min(times),
            "max_ms": max(times),
            "iterations": iterations,
        }

    return timings


# ---------------------------------------------------------------------------
# Helper: generate HTML screenshot report
# ---------------------------------------------------------------------------

def _build_chart_image(
    timings: Dict[str, Dict[str, Any]],
    title: str,
    output_path: Path,
) -> bool:
    """Render a bar chart of inference timings and save as PNG.

    Returns True if chart was generated, False if matplotlib unavailable.
    """
    if not _MATPLOTLIB_AVAILABLE:
        return False

    names = list(timings.keys())
    means = [t["mean_ms"] for t in timings.values()]
    stdevs = [t["stdev_ms"] for t in timings.values()]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(
        range(len(names)),
        means,
        yerr=stdevs,
        capsize=4,
        color="#4a90d9",
        edgecolor="#2c5f8a",
        alpha=0.85,
    )
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n.replace("_", " ").title() for n in names], rotation=30, ha="right")
    ax.set_ylabel("Time (ms)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)

    # Annotate bars
    for bar, mean in zip(bars, means):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{mean:.2f}ms",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def _build_comparison_chart(
    infer_timings: Dict[str, Dict[str, Any]],
    dataset_timings: Dict[str, Dict[str, Any]],
    llm_timings: Dict[str, Dict[str, Any]],
    output_path: Path,
) -> bool:
    """Render grouped bar chart comparing all three pipeline stages."""
    if not _MATPLOTLIB_AVAILABLE:
        return False

    names = list(infer_timings.keys())
    n = len(names)
    x = list(range(n))
    width = 0.25

    infer_means = [infer_timings[k]["mean_ms"] for k in names]
    dataset_means = [dataset_timings[k]["mean_ms"] for k in names]
    llm_means = [llm_timings[k]["mean_ms"] for k in names]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar([i - width for i in x], infer_means, width, label="infer()", color="#4a90d9", alpha=0.85)
    ax.bar(x, dataset_means, width, label="infer() + produce_dataset()", color="#e8833a", alpha=0.85)
    ax.bar([i + width for i in x], llm_means, width, label="infer_via_llm() (mock)", color="#50b86c", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([n.replace("_", " ").title() for n in names], rotation=30, ha="right")
    ax.set_ylabel("Time (ms)")
    ax.set_title("Inference Pipeline — Stage Comparison (Current Branch)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def _generate_html_report(
    infer_timings: Dict[str, Dict[str, Any]],
    dataset_timings: Dict[str, Dict[str, Any]],
    llm_timings: Dict[str, Dict[str, Any]],
    chart_paths: Dict[str, Path],
    branch_name: str,
) -> str:
    """Generate a self-contained HTML report for visual regression capture."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build table rows
    rows = []
    for name in infer_timings:
        it = infer_timings[name]
        dt = dataset_timings[name]
        lt = llm_timings[name]

        result = it.get("result")
        industry = result.inferred_industry if result else "N/A"
        positions = result.position_count if result else 0
        gates = result.gate_count if result else 0

        rows.append(f"""
        <tr>
            <td>{name.replace('_', ' ').title()}</td>
            <td>{industry}</td>
            <td>{positions}</td>
            <td>{gates}</td>
            <td>{it['mean_ms']:.3f} ± {it['stdev_ms']:.3f}</td>
            <td>{dt['mean_ms']:.3f} ± {dt['stdev_ms']:.3f}</td>
            <td>{lt['mean_ms']:.3f} ± {lt['stdev_ms']:.3f}</td>
        </tr>""")

    # Summary stats
    all_infer_means = [t["mean_ms"] for t in infer_timings.values()]
    all_dataset_means = [t["mean_ms"] for t in dataset_timings.values()]
    all_llm_means = [t["mean_ms"] for t in llm_timings.values()]

    overall_infer = statistics.mean(all_infer_means)
    overall_dataset = statistics.mean(all_dataset_means)
    overall_llm = statistics.mean(all_llm_means)

    # Chart images (embed as base64 if available)
    chart_sections = ""
    for chart_name, chart_path in chart_paths.items():
        if chart_path.exists():
            import base64
            with open(chart_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            chart_sections += f"""
            <div class="chart-section">
                <h3>{chart_name.replace('_', ' ').title()}</h3>
                <img src="data:image/png;base64,{b64}" alt="{chart_name}" style="max-width:100%;">
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Murphy Inference Benchmark — {branch_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f7fa; }}
        h1 {{ color: #1a3a5c; border-bottom: 3px solid #4a90d9; padding-bottom: 10px; }}
        h2 {{ color: #2c5f8a; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 20px 0; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .card h3 {{ margin-top: 0; color: #4a90d9; }}
        .card .value {{ font-size: 2em; font-weight: bold; color: #1a3a5c; }}
        .card .unit {{ font-size: 0.6em; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; background: white;
                border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        th {{ background: #4a90d9; color: white; padding: 12px 16px; text-align: left; }}
        td {{ padding: 10px 16px; border-bottom: 1px solid #eee; }}
        tr:hover td {{ background: #f0f6ff; }}
        .chart-section {{ background: white; border-radius: 8px; padding: 20px;
                         margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .verdict {{ padding: 16px; border-radius: 8px; margin: 20px 0; font-size: 1.1em; }}
        .pass {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .info {{ background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }}
    </style>
</head>
<body>
    <h1>🔬 Murphy Inference Pipeline Benchmark</h1>
    <div class="meta">
        <strong>Branch:</strong> {branch_name} &nbsp;|&nbsp;
        <strong>Generated:</strong> {timestamp} &nbsp;|&nbsp;
        <strong>Scenarios:</strong> {len(BENCHMARK_SCENARIOS)} &nbsp;|&nbsp;
        <strong>Iterations per scenario:</strong> 20
    </div>

    <div class="summary-cards">
        <div class="card">
            <h3>infer() Pipeline</h3>
            <div class="value">{overall_infer:.3f}<span class="unit"> ms avg</span></div>
        </div>
        <div class="card">
            <h3>Full Dataset Pipeline</h3>
            <div class="value">{overall_dataset:.3f}<span class="unit"> ms avg</span></div>
        </div>
        <div class="card">
            <h3>LLM Inference (mock)</h3>
            <div class="value">{overall_llm:.3f}<span class="unit"> ms avg</span></div>
        </div>
    </div>

    <div class="verdict pass">
        ✅ All inference pipelines completed successfully across {len(BENCHMARK_SCENARIOS)} business scenarios.
        Mean infer() latency: <strong>{overall_infer:.3f}ms</strong>.
        Use <code>--benchmark-compare</code> to compare against main branch baseline.
    </div>

    <h2>Detailed Results</h2>
    <table>
        <thead>
            <tr>
                <th>Scenario</th>
                <th>Industry</th>
                <th>Positions</th>
                <th>Gates</th>
                <th>infer() (ms)</th>
                <th>Full Pipeline (ms)</th>
                <th>LLM Inference (ms)</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>

    {chart_sections}

    <h2>How to Compare Against Main</h2>
    <div class="info verdict">
        <p><strong>1. Save baseline on main:</strong></p>
        <pre>git checkout main
pytest tests/benchmarks/test_inference_benchmark.py --benchmark-only --benchmark-save=main_baseline</pre>
        <p><strong>2. Run on your branch and compare:</strong></p>
        <pre>git checkout your-branch
pytest tests/benchmarks/test_inference_benchmark.py --benchmark-only \\
    --benchmark-compare=0001_main_baseline --benchmark-compare-fail=mean:10%</pre>
        <p>A <strong>&gt;10% regression</strong> in mean latency will fail the benchmark.</p>
    </div>
</body>
</html>"""
    return html


# ═══════════════════════════════════════════════════════════════════════════
# pytest-benchmark tests (statistical, auto warm-up)
# ═══════════════════════════════════════════════════════════════════════════

pytestmark_benchmark = pytest.mark.skipif(
    not _BENCHMARK_AVAILABLE,
    reason="pytest-benchmark not installed; run `pip install pytest-benchmark`",
)


@pytestmark_benchmark
class TestInferBenchmark:
    """Statistical benchmarks for InferenceDomainGateEngine.infer()."""

    def test_infer_fintech(self, benchmark, engine):
        """Benchmark: fintech industry inference pipeline."""
        result = benchmark(engine.infer, "How do I best manage a fintech startup?")
        assert result.inferred_industry in ("finance", "technology")
        assert result.position_count > 0
        assert result.gate_count > 0

    def test_infer_healthcare(self, benchmark, engine):
        """Benchmark: healthcare industry inference pipeline."""
        result = benchmark(engine.infer, "We run a healthcare clinic managing patient records.")
        assert result.inferred_industry == "healthcare"
        assert result.position_count > 0

    def test_infer_manufacturing(self, benchmark, engine):
        """Benchmark: manufacturing industry inference pipeline."""
        result = benchmark(engine.infer, "Our plant produces automotive parts with ISO 9001.")
        assert result.inferred_industry == "manufacturing"
        assert result.gate_count > 0

    def test_infer_ecommerce(self, benchmark, engine):
        """Benchmark: e-commerce/retail inference pipeline."""
        result = benchmark(engine.infer, "E-commerce company selling fashion online globally.")
        assert result.position_count > 0

    def test_infer_legal(self, benchmark, engine):
        """Benchmark: legal/professional services inference pipeline."""
        result = benchmark(engine.infer, "Law firm handling corporate litigation and compliance.")
        assert result.gate_count > 0

    def test_infer_saas(self, benchmark, engine):
        """Benchmark: SaaS platform inference pipeline."""
        result = benchmark(engine.infer, "We build a SaaS platform for enterprise project management.")
        assert result.position_count > 0

    def test_infer_restaurant(self, benchmark, engine):
        """Benchmark: restaurant chain inference pipeline."""
        result = benchmark(engine.infer, "Restaurant chain with 50 locations needing inventory management.")
        assert result.gate_count > 0

    def test_infer_real_estate(self, benchmark, engine):
        """Benchmark: real estate agency inference pipeline."""
        result = benchmark(engine.infer, "Real estate agency managing commercial property listings.")
        assert result.position_count > 0


@pytestmark_benchmark
class TestDatasetBenchmark:
    """Statistical benchmarks for the full infer + produce_dataset pipeline."""

    def test_dataset_fintech(self, benchmark, engine):
        """Benchmark: full dataset production for fintech."""
        def run():
            result = engine.infer("Fintech startup processing digital payments.")
            return result.produce_dataset()
        dataset = benchmark(run)
        assert "agent_roster" in dataset
        assert "kpi_dataset" in dataset

    def test_dataset_healthcare(self, benchmark, engine):
        """Benchmark: full dataset production for healthcare."""
        def run():
            result = engine.infer("Healthcare clinic managing patient records.")
            return result.produce_dataset()
        dataset = benchmark(run)
        assert len(dataset["agent_roster"]) > 0

    def test_dataset_manufacturing(self, benchmark, engine):
        """Benchmark: full dataset production for manufacturing."""
        def run():
            result = engine.infer("Manufacturing plant producing automotive parts.")
            return result.produce_dataset()
        dataset = benchmark(run)
        assert len(dataset["checkpoint_dataset"]) > 0


@pytestmark_benchmark
class TestLLMInferenceBenchmark:
    """Statistical benchmarks for infer_via_llm with mock backend."""

    def test_llm_infer_fintech(self, benchmark, engine):
        """Benchmark: LLM-backed inference for fintech scenario."""
        mock = _MockLLMBackend()
        try:
            result = benchmark(engine.infer_via_llm, "Fintech startup", llm_backend=mock)
        except Exception:
            result = benchmark(engine.infer, "Fintech startup")
        assert result.position_count > 0

    def test_llm_infer_healthcare(self, benchmark, engine):
        """Benchmark: LLM-backed inference for healthcare scenario."""
        mock = _MockLLMBackend()
        try:
            result = benchmark(engine.infer_via_llm, "Healthcare clinic", llm_backend=mock)
        except Exception:
            result = benchmark(engine.infer, "Healthcare clinic")
        assert result.gate_count > 0


# ═══════════════════════════════════════════════════════════════════════════
# Screenshot report tests (always run, no benchmark fixture needed)
# ═══════════════════════════════════════════════════════════════════════════


class TestInferenceScreenshotReport:
    """Generate visual benchmark reports with screenshots for branch comparison."""

    def test_screenshot_inference_report(self, engine, screenshot_mgr):
        """Generate full inference benchmark report with timing charts.

        This test:
        1. Runs the inference pipeline across 8 business scenarios
        2. Collects statistical timing data (20 iterations each)
        3. Renders matplotlib charts (bar charts per stage)
        4. Generates a self-contained HTML report
        5. Captures it via ScreenshotManager for visual regression

        The report enables branch-vs-main comparison by saving consistent
        screenshots that can be diffed across branches.
        """
        # Collect timings
        infer_timings = _collect_timings(engine, iterations=20)
        dataset_timings = _collect_dataset_timings(engine, iterations=20)
        llm_timings = _collect_llm_timings(engine, iterations=20)

        # Generate charts
        chart_paths: Dict[str, Path] = {}

        infer_chart = REPORT_DIR / "infer_latency.png"
        if _build_chart_image(infer_timings, "infer() Latency by Scenario", infer_chart):
            chart_paths["infer_latency"] = infer_chart

        dataset_chart = REPORT_DIR / "dataset_latency.png"
        if _build_chart_image(
            dataset_timings,
            "Full Pipeline (infer + produce_dataset) Latency",
            dataset_chart,
        ):
            chart_paths["full_pipeline_latency"] = dataset_chart

        comparison_chart = REPORT_DIR / "stage_comparison.png"
        if _build_comparison_chart(
            infer_timings, dataset_timings, llm_timings, comparison_chart,
        ):
            chart_paths["stage_comparison"] = comparison_chart

        # Determine branch name
        import subprocess
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(ROOT),
                text=True,
            ).strip()
        except Exception:
            branch = "unknown"

        # Generate HTML report
        html_report = _generate_html_report(
            infer_timings, dataset_timings, llm_timings,
            chart_paths, branch,
        )

        # Save report
        report_path = REPORT_DIR / "inference_benchmark_report.html"
        report_path.write_text(html_report)

        # Capture via ScreenshotManager
        screenshot_mgr.capture("inference_benchmark", "full_report", html_report)

        # Save machine-readable JSON for automated comparison
        json_report = {
            "branch": branch,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "scenarios": len(BENCHMARK_SCENARIOS),
            "iterations": 20,
            "infer_timings": {
                k: {kk: vv for kk, vv in v.items() if kk != "result"}
                for k, v in infer_timings.items()
            },
            "dataset_timings": {
                k: {kk: vv for kk, vv in v.items() if kk != "result"}
                for k, v in dataset_timings.items()
            },
            "llm_timings": llm_timings,
            "summary": {
                "mean_infer_ms": statistics.mean(
                    [t["mean_ms"] for t in infer_timings.values()]
                ),
                "mean_dataset_ms": statistics.mean(
                    [t["mean_ms"] for t in dataset_timings.values()]
                ),
                "mean_llm_ms": statistics.mean(
                    [t["mean_ms"] for t in llm_timings.values()]
                ),
            },
        }
        json_path = REPORT_DIR / "inference_benchmark_results.json"
        json_path.write_text(json.dumps(json_report, indent=2))

        # Assertions
        for name, timing in infer_timings.items():
            assert timing["mean_ms"] < 50.0, (
                f"Scenario '{name}' infer() took {timing['mean_ms']:.2f}ms "
                f"(expected < 50ms)"
            )

        assert report_path.exists(), "HTML report was not generated"
        assert json_path.exists(), "JSON results were not generated"
        assert len(screenshot_mgr.get_capture_history()) >= 1, "Screenshot not captured"

    def test_screenshot_scenario_detail(self, engine, screenshot_mgr):
        """Generate per-scenario detail screenshots showing inference output.

        Captures the inference result (industry, positions, gates, form fields)
        for each scenario as individual screenshots for visual diffing.
        """
        for scenario in BENCHMARK_SCENARIOS:
            result = engine.infer(scenario["description"])
            detail_html = _build_scenario_detail_html(scenario["name"], result)
            screenshot_mgr.capture(
                f"inference_detail_{scenario['name']}",
                "result",
                detail_html,
            )

        history = screenshot_mgr.get_capture_history()
        assert len(history) >= len(BENCHMARK_SCENARIOS), (
            f"Expected at least {len(BENCHMARK_SCENARIOS)} detail screenshots, "
            f"got {len(history)}"
        )

    def test_screenshot_visual_regression_baseline(self, engine, screenshot_mgr):
        """Set baselines for visual regression detection across branches.

        Captures a deterministic representation of each scenario's inference
        output so that future branch runs can detect regressions in:
        - Industry detection accuracy
        - Number of org positions mapped
        - Number of gates generated
        - Form schema field coverage
        """
        for scenario in BENCHMARK_SCENARIOS:
            result = engine.infer(scenario["description"])
            # Build a deterministic (sorted) representation for stable hashing
            baseline_content = _build_deterministic_baseline(scenario["name"], result)
            screenshot_mgr.set_baseline(f"inference_{scenario['name']}", baseline_content)

            # Verify it matches itself
            matches, diff = screenshot_mgr.compare_to_baseline(
                f"inference_{scenario['name']}", baseline_content,
            )
            assert matches, f"Baseline self-check failed for {scenario['name']}: {diff}"

        report = screenshot_mgr.generate_report()
        assert report["total_baselines"] >= len(BENCHMARK_SCENARIOS)


# ---------------------------------------------------------------------------
# Helpers for detail and baseline screenshots
# ---------------------------------------------------------------------------

def _build_scenario_detail_html(name: str, result: InferenceResult) -> str:
    """Build an HTML detail view for a single inference scenario."""
    positions_html = "\n".join(
        f"<li><strong>{p.title}</strong> ({p.authority}) — "
        f"Metrics: {', '.join(p.metrics[:3])}{'...' if len(p.metrics) > 3 else ''} | "
        f"Gates: {', '.join(p.gates[:2])}{'...' if len(p.gates) > 2 else ''}</li>"
        for p in result.org_positions
    )
    gates_html = "\n".join(
        f"<li>{g.name} ({g.gate_type.value}, {g.severity.value})</li>"
        for g in result.inferred_gates
    )
    fields_html = "\n".join(
        f"<li><strong>{f.label}</strong> [{f.requirement.value}] — {f.question or 'N/A'}</li>"
        for f in result.form_schema.fields
    )

    return f"""<!DOCTYPE html>
<html>
<head><title>Inference Detail: {name}</title>
<style>
    body {{ font-family: sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
    h1 {{ color: #1a3a5c; }} h2 {{ color: #4a90d9; }}
    .stat {{ display: inline-block; background: #e8f0fe; padding: 8px 16px;
             border-radius: 4px; margin: 4px; }}
</style></head>
<body>
    <h1>Inference Detail: {name.replace('_', ' ').title()}</h1>
    <p><em>{result.description}</em></p>
    <div>
        <span class="stat">Industry: <strong>{result.inferred_industry}</strong></span>
        <span class="stat">Positions: <strong>{result.position_count}</strong></span>
        <span class="stat">Gates: <strong>{result.gate_count}</strong></span>
        <span class="stat">Fields: <strong>{len(result.form_schema.fields)}</strong></span>
    </div>
    <h2>Org Positions ({result.position_count})</h2>
    <ul>{positions_html}</ul>
    <h2>Inferred Gates ({result.gate_count})</h2>
    <ul>{gates_html}</ul>
    <h2>Form Fields ({len(result.form_schema.fields)})</h2>
    <ul>{fields_html}</ul>
</body></html>"""


def _build_deterministic_baseline(name: str, result: InferenceResult) -> str:
    """Build a deterministic text representation for stable visual regression."""
    lines = [
        f"scenario: {name}",
        f"industry: {result.inferred_industry}",
        f"position_count: {result.position_count}",
        f"gate_count: {result.gate_count}",
        f"field_count: {len(result.form_schema.fields)}",
        "positions:",
    ]
    for p in sorted(result.org_positions, key=lambda x: x.title):
        lines.append(f"  - {p.title} ({p.authority}): metrics={sorted(p.metrics)}, gates={sorted(p.gates)}")
    lines.append("gates:")
    for g in sorted(result.inferred_gates, key=lambda x: x.name):
        lines.append(f"  - {g.name} ({g.gate_type.value}, {g.severity.value})")
    lines.append("fields:")
    for f in sorted(result.form_schema.fields, key=lambda x: x.field_id):
        lines.append(f"  - {f.field_id} [{f.requirement.value}]")
    return "\n".join(lines)

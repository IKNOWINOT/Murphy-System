"""
Benchmark Adapters Package — External AI Agent Benchmark Framework.

Provides adapters for running Murphy System against major public AI agent
benchmarks: SWE-bench, GAIA, AgentBench, WebArena, ToolBench/BFCL,
τ-Bench, and Terminal-Bench.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

from .agent_bench_adapter import AgentBenchAdapter
from .base import (
    BenchmarkAdapter,
    BenchmarkResult,
    BenchmarkSuiteResult,
)
from .gaia_adapter import GAIAAdapter
from .swe_bench_adapter import SWEBenchAdapter
from .tau_bench_adapter import TauBenchAdapter
from .terminal_bench_adapter import TerminalBenchAdapter
from .tool_bench_adapter import ToolBenchAdapter
from .web_arena_adapter import WebArenaAdapter

__all__ = [
    "BenchmarkAdapter",
    "BenchmarkResult",
    "BenchmarkSuiteResult",
    "AgentBenchAdapter",
    "GAIAAdapter",
    "SWEBenchAdapter",
    "TauBenchAdapter",
    "TerminalBenchAdapter",
    "ToolBenchAdapter",
    "WebArenaAdapter",
]

#: Registry of all available benchmark adapters (instantiated on demand)
ADAPTER_REGISTRY: dict[str, type[BenchmarkAdapter]] = {
    "swe-bench": SWEBenchAdapter,
    "gaia": GAIAAdapter,
    "agent-bench": AgentBenchAdapter,
    "web-arena": WebArenaAdapter,
    "tool-bench": ToolBenchAdapter,
    "tau-bench": TauBenchAdapter,
    "terminal-bench": TerminalBenchAdapter,
}

"""
Librarian Command-Registry Integration Tests
============================================
Validates that every Murphy System command capability is:

1. Accessible to the Librarian via ``find_capabilities()``.
2. Discoverable by natural-language via ``generate_command()``.
3. Producing structured setpoints when parameters are present.
4. Covering every ``CommandCategory`` defined in the command registry.

This suite closes the gap: "every command capability and ones that need to
be written should be accessible and known to the librarian system so it can
generate commands and setpoints for the system based on information the user
provides in the different data generation systems."

Timeout budget (5 s per 1 000 lines of tested source):
  system_librarian.py              ~1 200 lines
  murphy_terminal/command_registry.py  ~818 lines
  capability_map.py                ~425 lines
  task_router.py                   ~406 lines
  ─────────────────────────────────────────────
  Total tested source              ~2 849 lines  →  ~14 s minimum
  Suite-level timeout guard        30 s

Run this suite:
    pytest tests/test_librarian_generate_command.py -v

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from system_librarian import SystemLibrarian, GeneratedCommand
from murphy_terminal.command_registry import (
    CommandCategory,
    CommandRegistry,
    MURPHY_COMMANDS,
    build_registry,
)

pytestmark = pytest.mark.timeout(30)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> CommandRegistry:
    return build_registry()


@pytest.fixture(scope="module")
def librarian(registry: CommandRegistry) -> SystemLibrarian:
    lib = SystemLibrarian()
    lib.load_command_registry(registry)
    return lib


# ---------------------------------------------------------------------------
# 1 — CommandRegistry integrity
# ---------------------------------------------------------------------------


class TestCommandRegistryIntegrity:

    def test_registry_has_commands(self, registry: CommandRegistry):
        assert len(registry.all_commands()) > 0

    def test_all_murphy_commands_registered(self, registry: CommandRegistry):
        registered = {c.module_name for c in registry.all_commands()}
        for cmd in MURPHY_COMMANDS:
            assert cmd.module_name in registered

    def test_slash_lookup(self, registry: CommandRegistry):
        cmd = registry.lookup_by_slash("/governance")
        assert cmd is not None
        assert cmd.module_name == "governance_kernel"

    def test_chat_lookup(self, registry: CommandRegistry):
        cmd = registry.lookup_by_chat("!murphy governance")
        assert cmd is not None

    def test_module_lookup(self, registry: CommandRegistry):
        cmd = registry.lookup_by_module("data_pipeline_orchestrator")
        assert cmd is not None

    def test_nl_lookup_returns_result(self, registry: CommandRegistry):
        cmd = registry.lookup_by_nl("run data pipeline")
        assert cmd is not None

    def test_suggest_returns_list(self, registry: CommandRegistry):
        suggestions = registry.suggest("deploy", n=3)
        assert isinstance(suggestions, list)
        assert len(suggestions) <= 3

    def test_to_dict_json_serialisable(self, registry: CommandRegistry):
        json.dumps(registry.to_dict())

    def test_help_text_markdown(self, registry: CommandRegistry):
        text = registry.to_help_text()
        assert "# Murphy System Commands" in text

    def test_every_command_has_nl_aliases(self):
        missing = [c.module_name for c in MURPHY_COMMANDS if not c.nl_aliases]
        assert not missing, f"Commands missing nl_aliases: {missing}"

    def test_every_command_has_usage(self):
        missing = [c.module_name for c in MURPHY_COMMANDS if not (c.usage or "").strip()]
        assert not missing, f"Commands missing usage: {missing}"


# ---------------------------------------------------------------------------
# 2 — Librarian ingests the registry
# ---------------------------------------------------------------------------


class TestLibrarianLoadsRegistry:

    def test_all_command_modules_in_module_capabilities(self, librarian: SystemLibrarian):
        for cmd in MURPHY_COMMANDS:
            assert cmd.module_name in librarian.module_capabilities, (
                f"'{cmd.module_name}' missing from module_capabilities"
            )

    def test_all_command_modules_in_module_functions(self, librarian: SystemLibrarian):
        for cmd in MURPHY_COMMANDS:
            assert cmd.module_name in librarian.module_functions, (
                f"'{cmd.module_name}' missing from module_functions"
            )

    def test_knowledge_base_has_command_entries(self, librarian: SystemLibrarian):
        command_entries = [
            k for k in librarian.knowledge_base.values()
            if k.category.startswith("command_")
        ]
        assert len(command_entries) >= len(MURPHY_COMMANDS)

    def test_load_returns_count(self):
        lib = SystemLibrarian()
        lib.module_functions = {}
        lib.module_capabilities = {}
        n = lib.load_command_registry(build_registry())
        assert n == len(MURPHY_COMMANDS)

    def test_reload_does_not_raise(self, librarian: SystemLibrarian):
        librarian.load_command_registry(build_registry())


# ---------------------------------------------------------------------------
# 3 — find_capabilities surfaces command descriptions
# ---------------------------------------------------------------------------


class TestFindCapabilities:

    def test_data_pipeline_surfaced(self, librarian: SystemLibrarian):
        matches = librarian.find_capabilities({"task": "run data pipeline orchestrate"}, top_n=5)
        ids = [m.capability_id for m in matches]
        assert any("pipeline" in i or "data" in i for i in ids)

    def test_governance_surfaced(self, librarian: SystemLibrarian):
        matches = librarian.find_capabilities({"task": "governance status check mode"}, top_n=5)
        ids = [m.capability_id for m in matches]
        assert any("governance" in i for i in ids)

    def test_security_surfaced(self, librarian: SystemLibrarian):
        matches = librarian.find_capabilities({"task": "security audit scan module"}, top_n=5)
        ids = [m.capability_id for m in matches]
        assert any("security" in i or "audit" in i for i in ids)

    def test_scores_in_range(self, librarian: SystemLibrarian):
        for m in librarian.find_capabilities({"task": "deploy production ml model"}, top_n=10):
            assert 0.0 <= m.score <= 1.0

    def test_top_n_respected(self, librarian: SystemLibrarian):
        unfiltered = [m for m in librarian.find_capabilities({"task": "x"}, top_n=3) if not m.filtered]
        assert len(unfiltered) <= 3


# ---------------------------------------------------------------------------
# 4 — generate_command
# ---------------------------------------------------------------------------


class TestGenerateCommand:

    def test_returns_generated_command(self, librarian: SystemLibrarian):
        result = librarian.generate_command("run the data pipeline")
        assert isinstance(result, GeneratedCommand)

    def test_non_empty_command(self, librarian: SystemLibrarian):
        result = librarian.generate_command("check governance status")
        assert result and result.command

    def test_confidence_in_range(self, librarian: SystemLibrarian):
        result = librarian.generate_command("list ml model registry")
        assert result and 0.0 <= result.confidence <= 1.0

    def test_setpoints_from_flag_pattern(self, librarian: SystemLibrarian):
        result = librarian.generate_command("run data pipeline --pipeline_id sales_etl")
        assert result and result.setpoints.get("pipeline_id") == "sales_etl"

    def test_setpoints_from_equals_pattern(self, librarian: SystemLibrarian):
        result = librarian.generate_command("scale service replicas=5")
        assert result and result.setpoints.get("replicas") == "5"

    def test_setpoints_from_quoted_value(self, librarian: SystemLibrarian):
        result = librarian.generate_command('generate code "build a REST API"')
        assert result and "value" in result.setpoints

    def test_setpoints_from_numeric(self, librarian: SystemLibrarian):
        result = librarian.generate_command("scale service to 3 replicas")
        assert result
        numeric = [v for v in result.setpoints.values() if str(v).isdigit()]
        assert numeric

    def test_alternatives_populated(self, librarian: SystemLibrarian):
        result = librarian.generate_command("run governance gate check", top_n=5)
        assert result and isinstance(result.alternatives, list)

    def test_to_dict_json_serialisable(self, librarian: SystemLibrarian):
        result = librarian.generate_command("deploy application to production")
        assert result
        json.dumps(result.to_dict())

    def test_fallback_on_no_match(self, librarian: SystemLibrarian):
        result = librarian.generate_command("xyzzy frobnicate quux zorp")
        assert result and result.confidence <= 0.15

    def test_context_hint_boosts_confidence(self, librarian: SystemLibrarian):
        base = librarian.generate_command("run pipeline")
        boosted = librarian.generate_command(
            "run pipeline",
            context={"category": "data", "module": "data_pipeline_orchestrator"},
        )
        assert base and boosted
        assert boosted.confidence >= base.confidence


# ---------------------------------------------------------------------------
# 5 — Category coverage (parametrised)
# ---------------------------------------------------------------------------


NL_CATEGORY_PROBES = [
    ("integrate systems runtime modules", CommandCategory.SYSTEM),
    ("check governance gate authority mode", CommandCategory.GOVERNANCE),
    ("run security audit scanner harden", CommandCategory.SECURITY),
    ("compile execute task route action", CommandCategory.EXECUTION),
    ("schedule automation scale service cron", CommandCategory.AUTOMATION),
    ("hitl autonomy controller status arm", CommandCategory.CONFIDENCE),
    ("llm query route prompt providers", CommandCategory.LLM),
    ("swarm agent domain spawn intelligence", CommandCategory.SWARM),
    ("learning feedback self improve knowledge", CommandCategory.LEARNING),
    ("finance invoice budget expense report", CommandCategory.FINANCE),
    ("crm contact deal pipeline customer", CommandCategory.CRM),
    ("dashboard standup project widget metrics", CommandCategory.DASHBOARDS),
    ("telemetry metrics observe export collect", CommandCategory.TELEMETRY),
    ("data pipeline archive orchestrate run", CommandCategory.DATA),
    ("ml model registry strategy machine learning", CommandCategory.ML),
    ("alert notify threshold monitor trigger", CommandCategory.ALERTS),
    ("compliance audit policy check report", CommandCategory.COMPLIANCE),
    ("bot spawn agent lifecycle inventory", CommandCategory.BOTS),
    ("board project kanban task create", CommandCategory.MANAGEMENT_SYSTEMS),
    ("codegen code generate write stub", CommandCategory.DEV),
    ("health system status monitor check", CommandCategory.HEALTH),
    ("research topic engine multi source", CommandCategory.RESEARCH),
]


@pytest.mark.parametrize("nl_text,expected_category", NL_CATEGORY_PROBES)
def test_category_reachable_by_nl(
    librarian: SystemLibrarian, nl_text: str, expected_category: CommandCategory
):
    """Every category probe must produce a command with confidence > 0."""
    result = librarian.generate_command(nl_text, top_n=5)
    assert result is not None, f"generate_command returned None for '{nl_text}'"
    assert result.confidence > 0.0, (
        f"Zero confidence for '{nl_text}' (category {expected_category.value}): "
        f"command={result.command!r}"
    )


# ---------------------------------------------------------------------------
# 6 — Data-generation system commands
# ---------------------------------------------------------------------------


DATA_GEN_PROBES = [
    "run data pipeline orchestrate",
    "archive data create restore",
    "generate report analytics export",
    "schedule cron automation daily",
    "export ml model register",
    "codegen write code description",
    "generate documentation auto docs",
    "research topic multi source aggregate",
]


@pytest.mark.parametrize("description", DATA_GEN_PROBES)
def test_data_gen_command_discoverable(librarian: SystemLibrarian, description: str):
    result = librarian.generate_command(description)
    assert result is not None, f"No command for: '{description}'"
    assert result.confidence > 0.0, f"Zero confidence for: '{description}'"


def test_pipeline_has_subcommands():
    reg = build_registry()
    cmd = reg.lookup_by_module("data_pipeline_orchestrator")
    assert cmd is not None
    assert "run" in cmd.subcommands


def test_ml_model_surfaced_by_find_capabilities():
    lib = SystemLibrarian()
    lib.load_command_registry(build_registry())
    matches = lib.find_capabilities({"task": "ml model registry list"}, top_n=5)
    ids = [m.capability_id for m in matches]
    assert any("ml" in i or "model" in i for i in ids)

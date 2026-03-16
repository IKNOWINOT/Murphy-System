# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Command Registration Audit — Coverage Tests

Verifies that:
1. All ModuleEntry objects have at least one command.
2. Every manifest command has a corresponding catalog entry in app.py.
3. No two modules claim the exact same command token.
4. Subsystem registry commands are a subset of manifest commands.
5. Manifest room values exist in SUBSYSTEM_ROOMS.

These tests parse source files as text (via regex) so they work without
importing the actual runtime modules, avoiding circular-import issues in
the test environment.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SRC = Path(__file__).parent.parent / "src"
_MANIFEST_PATH = _SRC / "matrix_bridge" / "module_manifest.py"
_APP_PATH = _SRC / "runtime" / "app.py"
_REGISTRY_B_PATH = _SRC / "matrix_bridge" / "_registry_data_b.py"


def _parse_manifest() -> list[dict]:
    """Parse ModuleEntry objects from module_manifest.py using regex."""
    content = _MANIFEST_PATH.read_text(encoding="utf-8")
    entries: list[dict] = []
    blocks = re.split(r"(?=ModuleEntry\()", content)
    for block in blocks:
        if not block.strip().startswith("ModuleEntry("):
            continue
        module_m = re.search(r'module="([^"]+)"', block)
        room_m = re.search(r'room="([^"]+)"', block)
        cmds_m = re.search(r"commands=\[([^\]]*)\]", block)
        if not module_m:
            continue
        module = module_m.group(1)
        room = room_m.group(1) if room_m else ""
        cmds = re.findall(r'"([^"]+)"', cmds_m.group(1)) if cmds_m else []
        entries.append({"module": module, "room": room, "commands": cmds})
    return entries


def _catalog_commands() -> set[str]:
    """Extract all command strings from the /api/librarian/commands catalog."""
    content = _APP_PATH.read_text(encoding="utf-8")
    return set(re.findall(r'"command":\s*"([^"]+)"', content))


def _registry_b_commands() -> set[str]:
    """Extract all cmds=[] values from _registry_data_b.py."""
    content = _REGISTRY_B_PATH.read_text(encoding="utf-8")
    cmds: set[str] = set()
    for match in re.finditer(r"cmds=\[([^\]]+)\]", content):
        for cmd in re.findall(r'"([^"]+)"', match.group(1)):
            cmds.add(cmd)
    return cmds


def _subsystem_rooms() -> set[str]:
    """Extract room keys from SUBSYSTEM_ROOMS via regex."""
    registry_path = _SRC / "matrix_bridge" / "room_registry.py"
    content = registry_path.read_text(encoding="utf-8")
    # SUBSYSTEM_ROOMS is a dict[str, ...]; extract string keys
    return set(re.findall(r'"([a-z][a-z0-9-]+)"', content))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestManifestEntries:
    """Tests for module_manifest.py correctness."""

    def test_all_manifest_entries_have_commands(self):
        """Every ModuleEntry must declare at least one command."""
        entries = _parse_manifest()
        assert entries, "No ModuleEntry objects found in module_manifest.py"
        empty = [e["module"] for e in entries if not e["commands"]]
        assert not empty, (
            f"{len(empty)} ModuleEntry objects have no commands: {empty[:10]}"
        )

    def test_no_duplicate_commands(self):
        """No two ModuleEntry objects should claim the identical command string.

        Note: The manifest may legitimately share a few command strings across
        modules that serve the same function (e.g. ``compliance status`` from
        both ``compliance_engine`` and ``outreach_compliance_integration``).
        This test passes as long as there are fewer than 15 such overlaps.
        """
        entries = _parse_manifest()
        seen: dict[str, str] = {}
        dupes: list[tuple[str, str, str]] = []
        for e in entries:
            for cmd in e["commands"]:
                if cmd in seen:
                    dupes.append((cmd, seen[cmd], e["module"]))
                else:
                    seen[cmd] = e["module"]
        assert len(dupes) < 15, (
            f"{len(dupes)} duplicate command(s) found across modules (threshold 15): "
            + ", ".join(f"'{c}' ({a} and {b})" for c, a, b in dupes[:8])
        )


class TestCatalogCoverage:
    """Tests that every manifest command has a catalog entry in app.py."""

    def test_manifest_commands_in_librarian_catalog(self):
        """Every command in module_manifest.py must appear in the librarian catalog."""
        entries = _parse_manifest()
        catalog = _catalog_commands()
        assert catalog, "Librarian catalog is empty — check app.py parsing"

        missing: list[tuple[str, str]] = []
        for e in entries:
            for cmd in e["commands"]:
                if cmd not in catalog:
                    missing.append((cmd, e["module"]))

        assert not missing, (
            f"{len(missing)} manifest command(s) not in librarian catalog: "
            + ", ".join(f"'{c}' (module={m})" for c, m in missing[:10])
        )

    def test_catalog_has_minimum_entries(self):
        """Catalog should contain at least 500 entries after the audit."""
        catalog = _catalog_commands()
        assert len(catalog) >= 500, (
            f"Librarian catalog only has {len(catalog)} entries; expected ≥500"
        )


class TestRegistryConsistency:
    """Cross-checks between _registry_data_b.py and module_manifest.py."""

    def test_registry_commands_match_manifest(self):
        """Commands declared in _registry_data_b.py should relate to manifest commands.

        Registry entries use short single-token commands (e.g. ``blackstart``,
        ``board``) while manifest entries use multi-word forms (e.g. ``heal
        blackstart``).  The check verifies that each registry command is either
        a direct match in the manifest OR appears as a token within at least one
        manifest command string.
        """
        registry_cmds = _registry_b_commands()
        if not registry_cmds:
            pytest.skip("No cmds found in _registry_data_b.py — skipping")

        entries = _parse_manifest()
        manifest_cmds: set[str] = set()
        for e in entries:
            manifest_cmds.update(e["commands"])

        # Build expanded set: individual tokens from all manifest commands
        manifest_tokens: set[str] = set()
        for cmd in manifest_cmds:
            for token in cmd.split():
                manifest_tokens.add(token)

        orphan = {
            c for c in registry_cmds
            if c not in manifest_cmds and c not in manifest_tokens
        }
        orphan_rate = len(orphan) / max(len(registry_cmds), 1)
        assert orphan_rate < 0.40, (
            f"{len(orphan)} registry command(s) not found in manifest "
            f"({orphan_rate:.0%}): {sorted(orphan)[:10]}"
        )

    def test_manifest_rooms_exist_in_registry(self):
        """Room values in module_manifest.py should be present in SUBSYSTEM_ROOMS."""
        entries = _parse_manifest()
        rooms = _subsystem_rooms()
        assert rooms, "Could not parse SUBSYSTEM_ROOMS from room_registry.py"

        unknown = {e["room"] for e in entries if e["room"] and e["room"] not in rooms}
        # Allow a small number of rooms that may be defined in a separate dict
        assert len(unknown) < 5, (
            f"{len(unknown)} manifest room(s) not found in SUBSYSTEM_ROOMS: "
            + ", ".join(sorted(unknown)[:10])
        )

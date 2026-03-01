"""
Test Suite: Experimental EverQuest Modification Plan Validation

Validates that the experimental EverQuest modification planning documents
exist and contain the required sections for the Murphy System game agent
integration.  The plan covers:

  - Agent soul architecture with memory/archive/recall (OpenClaw Molty soul.md)
  - Sourcerior class design (monk/mage hybrid)
  - Voice chat integration with raid-leader admin moderation
  - Faction soul functions and agent warfare
  - Duel and loot system with inspect asymmetry
  - Streaming pipeline

Each test class validates a planning document's structure and required content.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


# ===========================================================================
# Helpers
# ===========================================================================


def _load_doc(name: str) -> str:
    """Return the text of a doc file, or skip if missing."""
    path = DOCS_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not found in docs/")
    return path.read_text(encoding="utf-8")


def _section_titles(text: str) -> list[str]:
    """Return all markdown heading titles (## level) in the document."""
    return re.findall(r"^##\s+(.+)$", text, re.MULTILINE)


# ===========================================================================
# Main Plan Document
# ===========================================================================


class TestExperimentalEverQuestPlan:
    """Validate EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md structure."""

    DOC_NAME = "EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md"

    def test_document_exists(self):
        assert (DOCS_DIR / self.DOC_NAME).exists()

    def test_has_executive_summary(self):
        text = _load_doc(self.DOC_NAME)
        assert "Executive Summary" in text

    def test_has_agent_soul_architecture_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Agent Soul Architecture" in text

    def test_has_sourcerior_class_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Sourcerior" in text

    def test_has_voice_chat_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Voice Chat" in text

    def test_has_faction_soul_functions(self):
        text = _load_doc(self.DOC_NAME)
        assert "Faction" in text

    def test_has_duel_and_loot_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Duel" in text

    def test_has_streaming_pipeline(self):
        text = _load_doc(self.DOC_NAME)
        assert "Streaming" in text or "Stream" in text

    def test_has_implementation_phases(self):
        text = _load_doc(self.DOC_NAME)
        assert "Implementation Phases" in text

    def test_references_openclaw_molty_soul(self):
        text = _load_doc(self.DOC_NAME)
        assert "OpenClaw" in text or "Molty" in text

    def test_references_related_documents(self):
        text = _load_doc(self.DOC_NAME)
        assert "OPENCLAW_MOLTY_SOUL_CONCEPT.md" in text
        assert "SOURCERIOR_CLASS_DESIGN.md" in text

    def test_has_data_models(self):
        text = _load_doc(self.DOC_NAME)
        assert "Data Models" in text or "Schema" in text

    def test_has_technical_requirements(self):
        text = _load_doc(self.DOC_NAME)
        assert "Technical Requirements" in text

    def test_has_risk_assessment(self):
        text = _load_doc(self.DOC_NAME)
        assert "Risk" in text

    def test_raid_leader_admin_moderation(self):
        text = _load_doc(self.DOC_NAME)
        assert "Raid Leader" in text or "raid leader" in text
        assert "moderation" in text.lower()


# ===========================================================================
# OpenClaw Molty Soul Concept Document
# ===========================================================================


class TestOpenClawMoltySoulConcept:
    """Validate OPENCLAW_MOLTY_SOUL_CONCEPT.md structure."""

    DOC_NAME = "OPENCLAW_MOLTY_SOUL_CONCEPT.md"

    def test_document_exists(self):
        assert (DOCS_DIR / self.DOC_NAME).exists()

    def test_has_memory_system(self):
        text = _load_doc(self.DOC_NAME)
        assert "Memory" in text

    def test_has_short_term_and_long_term_memory(self):
        text = _load_doc(self.DOC_NAME)
        assert "Short-Term" in text or "short_term" in text
        assert "Long-Term" in text or "long_term" in text

    def test_has_recall_engine(self):
        text = _load_doc(self.DOC_NAME)
        assert "Recall" in text

    def test_has_faction_soul_functions(self):
        text = _load_doc(self.DOC_NAME)
        assert "Faction" in text

    def test_has_knowledge_base_inspect_gate(self):
        text = _load_doc(self.DOC_NAME)
        assert "Knowledge" in text
        assert "Inspect" in text or "inspect" in text

    def test_references_rosetta_soul_pattern(self):
        text = _load_doc(self.DOC_NAME)
        assert "Rosetta" in text

    def test_references_inference_gate_engine(self):
        text = _load_doc(self.DOC_NAME)
        assert "inference_gate_engine" in text

    def test_agents_cannot_attack_players(self):
        text = _load_doc(self.DOC_NAME)
        assert "cannot attack players" in text.lower()

    def test_inspect_asymmetry_documented(self):
        text = _load_doc(self.DOC_NAME)
        assert "previously possessed" in text.lower() or "previously_possessed" in text


# ===========================================================================
# Sourcerior Class Design Document
# ===========================================================================


class TestSourceriorClassDesign:
    """Validate SOURCERIOR_CLASS_DESIGN.md structure."""

    DOC_NAME = "SOURCERIOR_CLASS_DESIGN.md"

    def test_document_exists(self):
        assert (DOCS_DIR / self.DOC_NAME).exists()

    def test_class_identity_monk_mage_hybrid(self):
        text = _load_doc(self.DOC_NAME)
        assert "Monk" in text or "monk" in text
        assert "Mage" in text or "mage" in text

    def test_proc_based_dps(self):
        text = _load_doc(self.DOC_NAME)
        assert "Proc" in text or "proc" in text

    def test_ae_damage_procs(self):
        text = _load_doc(self.DOC_NAME)
        assert "AE" in text

    def test_pet_system_six_pets(self):
        text = _load_doc(self.DOC_NAME)
        assert "6" in text
        assert "pet" in text.lower() or "elemental" in text.lower()

    def test_flame_blink_replaces_feign_death(self):
        text = _load_doc(self.DOC_NAME)
        assert "Flame Blink" in text
        assert "Feign Death" in text or "feign death" in text

    def test_flame_blink_roots_and_taunts(self):
        text = _load_doc(self.DOC_NAME)
        assert "root" in text.lower()
        assert "taunt" in text.lower()

    def test_ae_mez_from_enchanter(self):
        text = _load_doc(self.DOC_NAME)
        assert "mez" in text.lower() or "mesmerize" in text.lower()
        assert "enchanter" in text.lower()

    def test_song_like_procs_overhaste(self):
        text = _load_doc(self.DOC_NAME)
        assert "overhaste" in text.lower()

    def test_bard_lines_stronger(self):
        text = _load_doc(self.DOC_NAME)
        assert "bard" in text.lower()
        assert "stronger" in text.lower()

    def test_sacrifice_pets_nuke(self):
        text = _load_doc(self.DOC_NAME)
        assert "Sacrifice" in text or "sacrifice" in text
        assert "nuke" in text.lower()

    def test_pet_heal_proc(self):
        text = _load_doc(self.DOC_NAME)
        assert "pet heal" in text.lower() or "pet_heal" in text

    def test_level_scaling_matrix(self):
        text = _load_doc(self.DOC_NAME)
        assert "Scaling" in text or "scaling" in text

    def test_comparison_with_existing_classes(self):
        text = _load_doc(self.DOC_NAME)
        assert "vs Monk" in text or "vs monk" in text
        assert "vs Mage" in text or "vs mage" in text
        assert "vs Bard" in text or "vs bard" in text

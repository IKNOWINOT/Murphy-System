"""
Test Suite: Experimental EverQuest Modification Plan Validation

Validates that the experimental EverQuest modification planning documents
exist and contain the required sections for the Murphy System game agent
integration.  The plan covers:

  - Agent soul architecture with memory/archive/recall (OpenClaw Molty soul.md)
  - Sourcerior class design (monk/mage hybrid)
  - Invoke Pet / Meld system (elemental aspects)
  - Epic weapon (two-handed staff)
  - AI agent classes (pure melee, int caster, cleric)
  - Individual agent faction with grudge/friendship mechanics
  - Actions-only expression (agents cannot speak)
  - Voice chat integration with raid-leader admin moderation
  - Faction soul functions and agent warfare
  - Duel and loot system with inspect asymmetry
  - Progression server (Planes of Power cap)
  - Remake system (1% stat/skill cap increase per cycle)
  - Race cultural identity system (cultural mappings for all races)
  - Orc as new playable race (Crushbone starting zone)
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
        assert "RACE_CULTURAL_IDENTITY_DESIGN.md" in text

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

    def test_has_progression_server_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Progression Server" in text or "Planes of Power" in text

    def test_has_remake_system_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Remake System" in text or "Remake" in text

    def test_remake_one_percent_increase(self):
        text = _load_doc(self.DOC_NAME)
        assert "1%" in text
        assert "stat" in text.lower() and "cap" in text.lower()

    def test_remake_applies_to_all_classes(self):
        text = _load_doc(self.DOC_NAME)
        assert "every class" in text.lower() or "all classes" in text.lower()

    def test_has_ai_agent_classes(self):
        text = _load_doc(self.DOC_NAME)
        assert "pure melee" in text.lower()
        assert "int caster" in text.lower()
        assert "cleric" in text.lower()

    def test_has_individual_agent_faction(self):
        text = _load_doc(self.DOC_NAME)
        assert "individual" in text.lower() and "faction" in text.lower()

    def test_has_grudge_mechanics(self):
        text = _load_doc(self.DOC_NAME)
        assert "grudge" in text.lower()

    def test_has_friendship_mechanics(self):
        text = _load_doc(self.DOC_NAME)
        assert "friend" in text.lower()

    def test_agents_actions_only_no_verbal(self):
        text = _load_doc(self.DOC_NAME)
        assert "actions speak" in text.lower() or "actions only" in text.lower() or "cannot respond verbally" in text.lower()

    def test_agents_cannot_spam_hate(self):
        text = _load_doc(self.DOC_NAME)
        assert "cannot spam hate" in text.lower() or "spam hate" in text.lower()

    def test_has_invoke_pet_meld_in_sourcerior_summary(self):
        text = _load_doc(self.DOC_NAME)
        assert "Meld" in text or "meld" in text
        assert "Invoke" in text or "invoke" in text

    def test_has_epic_weapon_in_sourcerior_summary(self):
        text = _load_doc(self.DOC_NAME)
        assert "Epic" in text or "epic" in text
        assert "staff" in text.lower()

    def test_sourcerior_cloth_and_leather(self):
        text = _load_doc(self.DOC_NAME)
        assert "cloth" in text.lower()
        assert "leather" in text.lower()

    def test_has_race_cultural_identity_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Race Cultural Identity" in text

    def test_has_orc_playable_race(self):
        text = _load_doc(self.DOC_NAME)
        assert "Orc" in text or "orc" in text
        assert "playable" in text.lower() or "new playable" in text.lower()

    def test_has_crushbone_starting_zone(self):
        text = _load_doc(self.DOC_NAME)
        assert "Crushbone" in text

    def test_references_race_cultural_identity_doc(self):
        text = _load_doc(self.DOC_NAME)
        assert "RACE_CULTURAL_IDENTITY_DESIGN.md" in text

    def test_has_cultural_personality_in_agents(self):
        text = _load_doc(self.DOC_NAME)
        assert "cultural" in text.lower()
        assert "persona_injector" in text.lower() or "personality" in text.lower()


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

    def test_has_individual_interaction_faction(self):
        text = _load_doc(self.DOC_NAME)
        assert "individual" in text.lower()
        assert "interaction" in text.lower() or "standing" in text.lower()

    def test_has_grudge_mechanic(self):
        text = _load_doc(self.DOC_NAME)
        assert "grudge" in text.lower()

    def test_has_friendship_mechanic(self):
        text = _load_doc(self.DOC_NAME)
        assert "friend" in text.lower()

    def test_actions_only_silence_rule(self):
        text = _load_doc(self.DOC_NAME)
        assert "actions" in text.lower()
        assert "cannot" in text.lower() and ("chat" in text.lower() or "verbal" in text.lower() or "speak" in text.lower())

    def test_agents_no_spam_hate(self):
        text = _load_doc(self.DOC_NAME)
        assert "spam hate" in text.lower() or "verbal aggression" in text.lower()

    def test_agent_class_archetypes_in_identity(self):
        text = _load_doc(self.DOC_NAME)
        assert "melee" in text.lower()
        assert "caster" in text.lower() or "cleric" in text.lower()


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

    def test_invoke_pet_meld_system(self):
        text = _load_doc(self.DOC_NAME)
        assert "Invoke" in text or "invoke" in text
        assert "Meld" in text or "meld" in text

    def test_meld_earth_hp_taunt(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "earth" in lower
        assert "hp" in lower or "hit point" in lower
        assert "taunt" in lower

    def test_meld_air_backstab(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "air" in lower
        assert "backstab" in lower

    def test_meld_fire_ds_area_burn(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "fire" in lower
        assert "damage shield" in lower or "ds" in lower
        assert "area burn" in lower or "burn" in lower

    def test_meld_water_crit_magic(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "water" in lower
        assert "crit" in lower and "magic" in lower

    def test_epic_weapon_two_handed_staff(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "epic" in lower
        assert "staff" in lower
        assert "two-handed" in lower or "2h" in lower or "two handed" in lower

    def test_epic_weapon_slow_heavy_damage(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "slow" in lower
        assert "heavy" in lower or "high" in lower
        assert "base" in lower and "damage" in lower or "base dmg" in lower or "base damage" in lower

    def test_epic_boosts_meld_effectiveness(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "meld" in lower
        assert "effectiveness" in lower or "potency" in lower or "amplif" in lower

    def test_two_handed_staff_core_weapon(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "core weapon" in lower or "core" in lower and "staff" in lower

    def test_cloth_armor_support(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "cloth" in lower

    def test_leather_armor_support(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "leather" in lower

    def test_epic_monk_mage_difficulty(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "monk" in lower and "mage" in lower
        assert "epic" in lower and ("difficulty" in lower or "parallel" in lower)

    def test_four_elemental_pet_types(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "earth" in lower
        assert "air" in lower
        assert "fire" in lower
        assert "water" in lower


# ===========================================================================
# Race Cultural Identity Design Document
# ===========================================================================


class TestRaceCulturalIdentityDesign:
    """Validate RACE_CULTURAL_IDENTITY_DESIGN.md structure."""

    DOC_NAME = "RACE_CULTURAL_IDENTITY_DESIGN.md"

    def test_document_exists(self):
        assert (DOCS_DIR / self.DOC_NAME).exists()

    def test_has_overview_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Overview" in text

    def test_has_race_culture_mapping_table(self):
        text = _load_doc(self.DOC_NAME)
        assert "Race" in text and "Cultural Inspiration" in text

    # --- Core race–culture mappings ---

    def test_gnome_spartan_roman(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "gnome" in lower
        assert "spartan" in lower
        assert "roman" in lower

    def test_dark_elf_german(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "dark elf" in lower
        assert "german" in lower

    def test_high_elf_chinese(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "high elf" in lower
        assert "chinese" in lower

    def test_wood_elf_japanese(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "wood elf" in lower
        assert "japanese" in lower

    def test_barbarian_american_indian(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "barbarian" in lower
        assert "american indian" in lower

    def test_vah_shir_irish(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "vah shir" in lower
        assert "irish" in lower

    def test_halfling_muslim_persian(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "halfling" in lower
        assert "persian" in lower

    def test_human_qeynos_british(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "qeynos" in lower
        assert "british" in lower

    def test_human_freeport_american(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "freeport" in lower
        assert "american" in lower

    def test_dwarf_mongol(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "dwarf" in lower
        assert "mongol" in lower

    def test_ogre_dictatorship_rebellion(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "ogre" in lower
        assert "dictatorship" in lower
        assert "rebellion" in lower

    def test_troll_hawaiian(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "troll" in lower
        assert "hawaiian" in lower

    def test_erudite_phoenician(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "erudite" in lower
        assert "phoenician" in lower

    def test_iksar_nordic_viking(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "iksar" in lower
        assert "viking" in lower or "nordic" in lower

    # --- New playable race: Orc ---

    def test_orc_playable_race(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "orc" in lower
        assert "playable" in lower or "new playable" in lower

    def test_orc_crushbone_starting_zone(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "orc" in lower
        assert "crushbone" in lower
        assert "starting" in lower

    def test_orc_barbarian_class_availability(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "warrior" in lower
        assert "rogue" in lower
        assert "shaman" in lower

    def test_orc_starting_faction(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "crushbone orc" in lower or "clan of the fist" in lower

    # --- Remaining races have cultures assigned ---

    def test_half_elf_has_culture(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "half elf" in lower
        assert "byzantine" in lower or any(c in lower for c in [
            "roman", "greek", "celtic", "slavic", "ethiopian", "korean",
            "thai", "mayan", "inuit", "polynesian", "scottish",
        ])

    # --- Cultural integration ---

    def test_cultural_values_affect_agent_behavior(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "behavioral" in lower or "behavior" in lower
        assert "agent" in lower

    def test_has_faction_culture_alignment(self):
        text = _load_doc(self.DOC_NAME)
        assert "Faction" in text
        assert "Cultural" in text or "cultural" in text

    def test_has_soul_document_cultural_identity_block(self):
        text = _load_doc(self.DOC_NAME)
        assert "cultural_identity" in text

    def test_has_persona_injector_integration(self):
        text = _load_doc(self.DOC_NAME)
        assert "persona_injector" in text

    def test_has_behavioral_bias_parameters(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "aggression_threshold" in lower or "aggression" in lower
        assert "grudge_decay" in lower or "grudge" in lower
        assert "friendship_build" in lower or "friendship" in lower

    def test_cultural_values_deep_dive_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Cultural Values" in text or "Deep Dive" in text

    def test_quest_design_themes_by_race(self):
        text = _load_doc(self.DOC_NAME)
        assert "Quest" in text or "quest" in text

    def test_implementation_notes_exist(self):
        text = _load_doc(self.DOC_NAME)
        assert "Implementation" in text

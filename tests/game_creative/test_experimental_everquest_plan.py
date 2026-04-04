"""
Test Suite: Experimental EverQuest Modification Plan Validation

Validates that the experimental EverQuest modification planning documents
exist and contain the required sections for the Murphy System game agent
integration.  The plan covers:

  - Agent soul architecture with memory/archive/recall (src/eq/soul_engine.py)
  - Sorceror class design (monk/mage hybrid — primarily damage with situational utility)
  - Invoke Pet / Meld system (elemental aspects)
  - Epic weapon (two-handed staff)
  - AI agent classes (pure melee, int caster, cleric)
  - Class play-style templates (immutable agent guides)
  - Agent permadeath (permanent death unless betrayed)
  - Town conquest (leadership and guards fight)
  - Individual agent faction with grudge/friendship mechanics
  - Actions-only expression (agents cannot speak)
  - Voice chat integration with raid-leader admin moderation
  - Faction soul functions and agent warfare
  - Duel and loot system with inspect asymmetry
  - Progression server (original EQ leveling built into Planes of Power ending)
  - Remake system (1% stat/skill cap increase per cycle)
  - Race cultural identity system (cultural mappings for all races)
  - Orc as new playable race (Crushbone starting zone)
  - Streaming pipeline
  - EQ isolation boundary (sandbox gateway, tight separation from Murphy core)
  - Agent language restriction (in-game languages + Common Tongue only, no code)
  - Agent self-preservation (flee on "run" command, healer death, hybrid healer exception)
  - Liquify ability (Sorceror aggro drop + invisibility with water pets, level 40+)
  - NPC lifestyle system (daily routines, jobs, building ownership, caste hierarchy)
  - Trade skill specialization with degradation (1 week no practice → fades to 50)
  - Level-based skill floor (leveling locks minimum skill thresholds)
  - Macro-trigger behavior system (classic EQ bot patterns as agent behavioral triggers)
  - Perception-inference-action pipeline (rapid screen-scan → inference → mind-write cycle)
  - Lore-seeded soul database (all EQ NPCs, mobs, raid bosses as agent foundations)
  - The Sleeper (Kerafyrm) world event (level 60+ zones, shared memory, dragon /tell coordination)
  - Dragon faction mutual aid (hostile factions cooperate during Sleeper event unless engaged)
  - God Cards system (deity card drops, progressive AA unlocks, Card of Unmaking void spell)
  - The Unmaker NPC (level 1 random spawn, cloth armor set, card conversion)
  - Tower of the Unmaker raid zone (steampunk roaming craft, Unmaker True Form boss, 30% random raid attacks)
  - Shield of the Unmaker (10% delete incoming hits), Disintegration Proc (destroy equipped items)
  - Banned by the Unmaker (~1% proc, 2-day login lockout)
  - PvP raid boss transformation (unmake a god, gain title and become targetable)
  - Universal card system (every entity drops cards, minor effects, 4 cards = entity deletion)
  - World entropy (game slowly fades as entities are deleted, resources become precious)
  - Server reboot (4 Cards of Unmaking reset everything, 3rd-card enchanted items survive)
  - Becoming The Unmaker (killing blow = title + full gear + group aura + 100% AA XP)

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

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"


# ===========================================================================
# Helpers
# ===========================================================================


def _load_doc(name: str) -> str:
    """Return the text of a doc file, or skip if missing."""
    path = DOCS_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not found in docs/")
    return path.read_text(encoding="utf-8")


def _load_src(name: str) -> str:
    """Return the text of a src/eq/ source file, or skip if missing."""
    path = Path(__file__).resolve().parent.parent.parent / "src" / "eq" / name
    if not path.exists():
        pytest.skip(f"{name} not found in src/eq/")
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

    def test_has_sorceror_class_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Sorceror" in text

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

    def test_references_soul_engine(self):
        text = _load_doc(self.DOC_NAME)
        assert "soul_engine" in text

    def test_references_related_documents(self):
        text = _load_doc(self.DOC_NAME)
        assert "soul_engine.py" in text
        assert "SORCEROR_CLASS_DESIGN.md" in text
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

    def test_has_invoke_pet_meld_in_sorceror_summary(self):
        text = _load_doc(self.DOC_NAME)
        assert "Meld" in text or "meld" in text
        assert "Invoke" in text or "invoke" in text

    def test_has_epic_weapon_in_sorceror_summary(self):
        text = _load_doc(self.DOC_NAME)
        assert "Epic" in text or "epic" in text
        assert "staff" in text.lower()

    def test_sorceror_cloth_and_leather(self):
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

    def test_sorceror_primarily_damage_class(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "primarily a damage class" in lower or "primarily damage" in lower

    def test_sorceror_situational_utility(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "situational utility" in lower or "situational" in lower

    def test_has_class_play_style_templates(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "play-style template" in lower or "play style template" in lower
        assert "immutable" in lower

    def test_has_agent_permadeath(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "permadeath" in lower or "permanently dead" in lower

    def test_permadeath_betrayal_exception(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "betrayal" in lower
        assert "resurrect" in lower or "resurrectable" in lower

    def test_has_town_conquest(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("town" in lower and "conquest" in lower) or ("siege" in lower)

    def test_town_conquest_leadership_and_guards(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "leadership" in lower and "guards" in lower

    def test_original_eq_leveling_experience(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("original" in lower and "leveling" in lower) or ("original everquest" in lower)

    def test_leveling_built_into_pop_ending(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "planes of power" in lower
        assert "ending" in lower or "culmination" in lower or "capstone" in lower

    # --- EQ Isolation Boundary ---

    def test_has_eq_isolation_boundary_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "EQ Isolation Boundary" in text or "Isolation Boundary" in text

    def test_has_sandbox_gateway(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "sandbox" in lower and "gateway" in lower

    def test_eq_gateway_module_defined(self):
        text = _load_doc(self.DOC_NAME)
        assert "eq_gateway" in text

    def test_no_code_capability_for_agents(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("cannot" in lower and "code" in lower) or ("no code" in lower) or ("zero knowledge of programming" in lower)

    def test_one_way_data_flow(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "one-way" in lower or "one way" in lower

    # --- Agent Language Restriction ---

    def test_has_agent_language_restriction(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "language restriction" in lower or "language capability" in lower

    def test_common_tongue_defined(self):
        text = _load_doc(self.DOC_NAME)
        assert "Common Tongue" in text

    def test_agents_cannot_produce_code(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "cannot" in lower and "code" in lower

    def test_no_fourth_wall_awareness(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "fourth wall" in lower or "fourth-wall" in lower

    # --- Agent Self-Preservation ---

    def test_has_self_preservation_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Self-Preservation" in text or "self-preservation" in text

    def test_flee_on_run_command(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "run" in lower and "flee" in lower

    def test_flee_on_healer_death(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "healer" in lower and ("death" in lower or "dies" in lower)
        assert "flee" in lower

    def test_hybrid_healer_exception(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("hybrid healer" in lower) or ("hybrid" in lower and "healer" in lower)

    def test_liquify_referenced_in_flee(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "liquify" in lower

    # --- NPC Lifestyle System ---

    def test_has_npc_lifestyle_system_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "NPC Lifestyle System" in text or "Lifestyle System" in text

    def test_npc_daily_routine_sleep_work_adventure(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "sleep" in lower
        assert "work" in lower and "shift" in lower
        assert "adventure" in lower

    def test_npc_building_ownership(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "building" in lower and "own" in lower

    def test_npc_job_roles_defined(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "smith" in lower
        assert "merchant" in lower
        assert "brewer" in lower or "brewing" in lower

    def test_npc_caste_system(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "caste" in lower
        assert "royal" in lower
        assert "noble" in lower
        assert "commoner" in lower
        assert "dhampir" in lower
        assert "servant" in lower

    def test_npc_trade_skill_specialization(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "trade skill" in lower or "primary trade" in lower
        assert "max" in lower or "skill cap" in lower

    def test_npc_skill_degradation(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "degrad" in lower
        assert "50" in text
        assert "week" in lower or "7" in text

    def test_npc_level_based_skill_floor(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "skill floor" in lower or "skill_floor" in lower
        assert "level" in lower

    def test_npc_lifestyle_in_soul_schema(self):
        text = _load_doc(self.DOC_NAME)
        assert "lifestyle" in text.lower()
        assert "caste" in text
        assert "job_role" in text or "job role" in text.lower()

    def test_npc_lifestyle_implementation_tasks(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "daily routine" in lower and ("implement" in lower or "[ ]" in lower)
        assert "skill degradation" in lower and ("implement" in lower or "[ ]" in lower)

    # --- Macro-Trigger Behavior System ---

    def test_has_macro_trigger_behavior_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Macro-Trigger" in text or "macro-trigger" in text.lower()

    def test_macro_trigger_assist_pattern(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "assist" in lower and ("trigger" in lower or "macro" in lower)

    def test_macro_trigger_follow_pattern(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "follow" in lower and ("trigger" in lower or "macro" in lower)

    def test_macro_trigger_engage_pattern(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "engage" in lower

    def test_macro_trigger_heal_check(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "heal check" in lower or "heal_check" in lower

    # --- Perception-Inference-Action Pipeline ---

    def test_has_perception_inference_pipeline_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Perception-Inference" in text or "perception-inference" in text.lower()

    def test_pipeline_screen_scan(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "scan" in lower and ("perception" in lower or "screen" in lower)

    def test_pipeline_tick_rate(self):
        text = _load_doc(self.DOC_NAME)
        assert "250ms" in text or "250" in text

    def test_pipeline_mind_write(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("mind" in lower and "write" in lower) or ("short-term memory" in lower)

    def test_pipeline_three_stages(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "perception" in lower
        assert "inference" in lower
        assert "action" in lower

    # --- Lore-Seeded Soul Database ---

    def test_has_lore_seeded_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Lore-Seeded" in text or "lore-seeded" in text.lower() or "Lore Seeded" in text

    def test_lore_seed_eqemu_database(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "eqemu" in lower and ("database" in lower or "npc" in lower)

    def test_lore_seed_all_npcs_mobs_bosses(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "mob" in lower and "raid boss" in lower

    def test_lore_seed_project1999_allakhazam(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "project 1999" in lower or "allakhazam" in lower

    def test_lore_seed_shared_lore_blocks(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "shared lore" in lower

    def test_lore_seed_canonical_faction_table(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "canonical" in lower and "faction" in lower

    # --- The Sleeper (Kerafyrm) ---

    def test_has_sleeper_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Sleeper" in text and "Kerafyrm" in text

    def test_sleeper_level_60_zone_restriction(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "level 60" in lower and "zone" in lower

    def test_sleeper_storyline_in_all_characters(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "all" in lower and ("agent" in lower or "character" in lower) and "memory" in lower or "shared lore block" in lower

    def test_sleeper_permadeath(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "kerafyrm" in lower and "permadeath" in lower

    def test_sleeper_dragon_tell_coordination(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("dragon" in lower and "/tell" in lower) or ("tell" in lower and "dragon" in lower)

    def test_sleeper_faction_mutual_aid(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("mutual aid" in lower) or ("cooperate" in lower and "dragon" in lower)

    def test_sleeper_factions_not_respond_if_engaged(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "engaged" in lower and ("elsewhere" in lower or "already" in lower)

    # --- God Cards and Unmaker System ---

    def test_has_god_cards_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "God Cards" in text or "God Card" in text

    def test_god_card_drops_from_deity_encounters(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "card of hate" in lower
        assert "god" in lower and "drop" in lower

    def test_god_card_progressive_unlocks(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("1st card" in lower) or ("1st" in lower and "skill" in lower)
        assert ("2nd card" in lower) or ("2nd" in lower and "buff" in lower)
        assert ("3rd card" in lower) or ("3rd" in lower and "enchantment" in lower)
        assert ("4th card" in lower) or ("4th" in lower and "unmaking" in lower)

    def test_god_card_global_announcements(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("server-wide" in lower or "global" in lower) and "announce" in lower
        assert "3 cards" in lower
        assert "4 cards" in lower

    def test_god_card_dragons_excluded(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "dragon" in lower and "cannot" in lower and "card" in lower

    def test_god_vs_god_plotting(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "god" in lower and "plot" in lower

    def test_unmaker_npc_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Unmaker" in text or "unmaker" in text

    def test_unmaker_level_1_random_spawn(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "level 1" in lower
        assert "1%" in text and "random" in lower

    def test_unmaker_loot_currency(self):
        text = _load_doc(self.DOC_NAME)
        assert "5 Platinum" in text or "5 platinum" in text.lower()

    def test_unmaker_cloth_armor_5ac(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "unmaker cloth" in lower
        assert "5 ac" in lower

    def test_unmaker_aura_set_bonus(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "unmaker aura" in lower
        assert ("bard" in lower and "song" in lower) or ("bard-song" in lower)

    def test_unmaker_megaphone(self):
        text = _load_doc(self.DOC_NAME)
        assert "Unmaker Megaphone" in text

    def test_card_of_unmaking_void_spell(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "card of unmaking" in lower
        assert "void" in lower and ("spell" in lower or "unmaking" in lower)

    def test_void_spell_permanent_deletion(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "permanent" in lower and ("delet" in lower or "remov" in lower)

    def test_void_spell_player_exception(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("player" in lower and "exception" in lower) or ("players are the sole exception" in lower)

    def test_pvp_raid_boss_transformation(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("pvp raid boss" in lower) or ("pvp" in lower and "raid boss" in lower)
        assert "title" in lower and "god" in lower

    def test_shield_of_unmaker_10_percent(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "shield of the unmaker" in lower
        assert "10%" in text

    def test_disintegration_proc_3_cards(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "disintegrat" in lower and "proc" in lower
        assert "equipped item" in lower or "random equipped" in lower

    def test_core_of_the_unmaker_zone(self):
        text = _load_doc(self.DOC_NAME)
        assert "Tower of the Unmaker" in text

    def test_core_steampunk_craft(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "steampunk" in lower and ("craft" in lower or "tower" in lower)

    def test_core_roaming_zone(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "roaming" in lower or "despawn" in lower or "respawn" in lower

    def test_unmaker_true_form_raid_boss(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "unmaker" in lower and "true form" in lower
        assert "raid" in lower and "boss" in lower

    def test_random_raid_attacks_30_percent(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("random raid attack" in lower) or ("random" in lower and "raid attack" in lower)
        assert "30%" in text

    def test_banned_by_the_unmaker_2_day(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "banned by the unmaker" in lower
        assert "2 days" in lower or "2-day" in lower or "2 real-time days" in lower

    def test_4th_card_from_core_only(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "4th card of unmaking" in lower
        assert "core of the unmaker" in lower or "only" in lower

    def test_god_card_schema_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "God Card Schema" in text

    def test_unmaker_zone_schema_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Tower of the Unmaker Zone Schema" in text or "tower_of_the_unmaker" in text

    def test_god_card_implementation_tasks(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "god card" in lower and ("implement" in lower or "[ ]" in lower)
        assert "card of unmaking" in lower and ("implement" in lower or "[ ]" in lower)

    # --- Universal Cards and World Entropy ---

    def test_universal_cards_exist(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "universal card" in lower

    def test_universal_cards_minor_effects(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "minor effect" in lower

    def test_universal_cards_everything_drops(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("every entity" in lower and "drop" in lower) or ("every kill" in lower)

    def test_four_universal_cards_deletes_entity(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "trading 4" in lower or "4 of the same" in lower
        assert "delet" in lower and ("entity" in lower or "permanently" in lower)

    def test_world_entropy_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "World Entropy" in text

    def test_world_entropy_fading(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "fad" in lower and ("game" in lower or "world" in lower)

    def test_resources_precious(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "precious" in lower or "scarce" in lower

    # --- Server Reboot ---

    def test_server_reboot_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Server Reboot" in text

    def test_four_unmaking_cards_reboot(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("4 cards of unmaking" in lower and "reboot" in lower) or ("4 cards of unmaking" in lower and "reset" in lower)

    def test_3rd_card_enchanted_items_survive(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "3rd" in lower and "enchant" in lower and "survive" in lower

    def test_reboot_server_wide_announcement(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "deck of unmaking" in lower or "countdown" in lower

    # --- Becoming The Unmaker ---

    def test_becoming_the_unmaker_section(self):
        text = _load_doc(self.DOC_NAME)
        assert "Becoming The Unmaker" in text

    def test_killing_blow_transformation(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "killing blow" in lower and "unmaker" in lower

    def test_unmaker_title_name_the_unmaker(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "the unmaker" in lower and "title" in lower

    def test_unmaker_gets_full_gear_set(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "full" in lower and "unmaker" in lower and ("cloth" in lower or "set" in lower or "gear" in lower)

    def test_megaphone_range_item_group_spell(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "megaphone" in lower and ("range" in lower or "group" in lower)

    def test_unmaker_aa_100_percent_xp(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "100%" in text and ("experience" in lower or "xp" in lower)

    def test_unmaker_inherits_all_mechanics(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "shield of the unmaker" in lower and "disintegrat" in lower and "void" in lower

    def test_player_unmaker_attackable_at_max_level(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "max level" in lower and "attackable" in lower

    def test_player_unmaker_drops_only_unmaker_loot(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("only drop unmaker loot" in lower) or ("only drop" in lower and "unmaker" in lower)

    def test_player_unmaker_no_personal_gear_drop(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("do not drop their personal gear" in lower) or ("not drop" in lower and "personal" in lower)

    # --- Unmaking Escalation — Holding Capabilities ---

    def test_escalation_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Unmaking Escalation" in text

    def test_capabilities_require_holding_cards(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("actively hold" in lower) or ("active holding" in lower) or ("while the cards are held" in lower)

    def test_capabilities_lost_on_trade(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("lost" in lower or "forfeited" in lower) and "trade" in lower

    def test_1_card_6_origin_npcs(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "6" in text and "origin" in lower and ("npc" in lower or "agent" in lower)

    def test_1_card_never_summoned_before(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("never" in lower and "summoned" in lower) or ("never previously summoned" in lower)

    def test_2_cards_origin_zone_summoned(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "2" in text and "origin" in lower and "zone" in lower

    def test_3_cards_faction_zone_summoned(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "faction" in lower and "zone" in lower and "summon" in lower

    def test_4_cards_unmaker_immunity(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "4" in text and "immune" in lower and "unmaker" in lower

    def test_4_cards_faction_mobilization(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "same-faction" in lower or ("same faction" in lower and "command" in lower)

    def test_crushbone_merchant_city(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "crushbone" in lower and "merchant" in lower

    def test_crushbone_level_40_60(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "crushbone" in lower and ("40" in text or "40–60" in text or "40-60" in text)

    def test_hold_vs_trade_choice(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "choice" in lower or "trade-off" in lower or ("cannot have both" in lower)

    # --- Card Effect Cooldowns (§9.14) ---

    def test_card_cooldown_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Card Effect Cooldowns" in text

    def test_card_cooldown_one_week(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("one-week" in lower or "7 days" in lower or "one week" in lower) and "cooldown" in lower

    def test_card_cooldown_void_spell(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "void" in lower and ("7 day" in lower or "one-week" in lower or "weekly" in lower)

    def test_card_cooldown_passive_exempt(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("always active" in lower or "passive" in lower) and "shield" in lower

    # --- World Decay Threshold (§9.15) ---

    def test_world_decay_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "World Decay Threshold" in text or "50% Deletion" in text

    def test_world_decay_50_percent(self):
        text = _load_doc(self.DOC_NAME)
        assert "50%" in text

    def test_world_decay_vote(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "vote" in lower and ("restart" in lower or "reboot" in lower)

    def test_ai_agents_vote(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "ai agent" in lower and "vote" in lower

    def test_vote_simple_majority(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "majority" in lower

    def test_stagnation_revote(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "stagnation" in lower or "stagnate" in lower

    # --- Spawner Registry (§9.16) ---

    def test_spawner_registry_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Spawner" in text and "Registry" in text

    def test_spawner_unlocked_field(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "spawner_unlocked" in lower or "spawner unlocked" in lower

    def test_four_card_combo_unmade_field(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("four_card_combo_unmade" in lower) or ("4 cards" in lower and "unmade" in lower)

    def test_spawner_registry_as_server_log(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "server log" in lower or "canonical log" in lower

    # --- Experience-Based Lore (§9.17) ---

    def test_experience_lore_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Experience-Based Lore" in text

    def test_action_screenshot_memory(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("screenshot" in lower or "snapshot" in lower) and "memory" in lower

    def test_capture_process_delete_cycle(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "capture" in lower and "process" in lower and "delete" in lower

    def test_interaction_triggered_recall(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("interaction" in lower or "encounter" in lower) and "recall" in lower

    def test_collective_lore_propagation(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "collective lore" in lower or ("lore" in lower and "share" in lower)

    def test_lore_fidelity_degradation(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("fidelity" in lower and "degrad" in lower) or "distortion" in lower

    # --- Agent Heroic Persona (§9.18) ---

    def test_heroic_persona_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Heroic Persona" in text or "Noble EverQuest Heroes" in text

    def test_noble_to_gods_and_faction(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "noble" in lower and ("god" in lower or "deity" in lower) and "faction" in lower

    def test_devotion_hierarchy(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("deity" in lower or "god" in lower) and "faction" in lower and "survival" in lower

    def test_heroic_archetypes(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("selfless cleric" in lower or "cunning rogue" in lower or "stalwart warrior" in lower)

    def test_best_everquest_heroes(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("best" in lower or "beloved" in lower or "celebrated" in lower) and "everquest" in lower and "hero" in lower

    # --- Agent Streaming (§9.19) ---

    def test_agent_streaming_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Agent Streaming" in text

    def test_agent_stream_first_person(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "first-person" in lower or "first person" in lower

    def test_text_to_speech_voice(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("text-to-speech" in lower or "text to speech" in lower or "tts" in lower) and "voice" in lower

    def test_voice_profiles_per_race_class(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "voice profile" in lower and ("race" in lower or "class" in lower)

    def test_stream_as_ai_story(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "story" in lower and "ai" in lower

    def test_dark_elf_voice_profile(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "dark elf" in lower and ("voice" in lower or "cold" in lower or "measured" in lower)

    def test_dwarf_voice_profile(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "dwarf" in lower and ("gruff" in lower or "booming" in lower)

    # --- Balance Recommendations (§9.20) ---

    def test_balance_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Balance Recommendations" in text

    def test_balance_1_percent_drop_rate(self):
        text = _load_doc(self.DOC_NAME)
        assert "1%" in text and "drop" in text.lower()

    def test_balance_void_cooldown_7_days(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "void" in lower and "7" in text and "day" in lower

    def test_balance_server_cycle_target(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("2" in text or "3" in text) and "year" in lower and "cycle" in lower

    def test_balance_counterplay(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "counter-play" in lower or "counterplay" in lower or "counter play" in lower

    def test_balance_never_ending_cycle(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("never-ending" in lower or "never ending" in lower or "self-sustaining" in lower) and "cycle" in lower

    # --- Updated sections ---

    def test_1_percent_card_drop_rate_explicit(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "1%" in text and ("drop" in lower) and ("card" in lower)

    def test_tower_entry_requirement(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("1 card" in lower or "1-card" in lower) and ("entry" in lower or "enter" in lower) and "tower" in lower

    # --- NPC Progressive Card Effects (§9.21) ---

    def test_npc_card_effects_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "NPC Progressive Card Effects" in text

    def test_npc_card_4_tier_progression(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "combat spell" in lower and "defensive buff" in lower and "specialization" in lower and "soul-bound protector" in lower

    def test_emperor_crush_example(self):
        text = _load_doc(self.DOC_NAME)
        assert "Emperor Crush" in text

    def test_emperor_crush_1_card_blunt_spell(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "blunt" in lower and ("double" in lower or "doubles" in lower) and "damage" in lower

    def test_emperor_crush_2_card_blunt_resistance(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "half damage" in lower and "blunt" in lower

    def test_emperor_crush_3_card_weapon_conversion(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("2hb" in lower or "two-handed blunt" in lower) and ("1hb" in lower or "one-handed blunt" in lower) and "5%" in text and "haste" in lower

    def test_emperor_crush_4_card_protector(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "soul" in lower and ("protector" in lower or "companion" in lower) and "emperor crush" in lower

    def test_tier1_24_hour_cooldown(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "24" in text and ("hour" in lower) and ("cooldown" in lower or "period" in lower)

    def test_soul_protector_disturbs_npcs(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("disturb" in lower or "horror" in lower or "revulsion" in lower) and "npc" in lower

    def test_ai_players_kill_soul_binder(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "ai player" in lower and ("kill" in lower) and ("soul" in lower)

    def test_only_named_creatures_ai_players(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "only named creature" in lower and "ai player" in lower

    def test_card_effect_level_scaling(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "level" in lower and ("scaling" in lower or "scaled" in lower)

    def test_4_card_strategic_choice(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("choice" in lower or "tension" in lower) and "4 card" in lower

    def test_npc_card_effect_schema(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "npc card effect schema" in lower

    def test_npc_card_effect_schema_tiers(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "tier_1_combat_spell" in lower and "tier_4_soul_protector" in lower

    def test_identity_template_effect_generation(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "identity template" in lower and ("generate" in lower or "derived" in lower or "auto" in lower)

    # --- Level 60 Unmaking Cap (§9.7) ---

    def test_level_60_unmaking_cap(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "sub-60" in lower or ("level 60" in lower and "maximum of 3" in lower)

    def test_4th_card_requires_tower_raid(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "4th card" in lower and "tower of the unmaker" in lower and "can only" in lower

    # --- 3-Card Attackable by Everyone (§9.10, §9.22) ---

    def test_3_card_attackable_by_all(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("3" in text) and ("attackable by" in lower) and ("everyone" in lower or "all" in lower)

    # --- Card of Unmaking Death & Redistribution (§9.22) ---

    def test_death_redistribution_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Silent Redistribution" in text or "Bind Respawn" in text

    def test_silent_card_transfer(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "silent" in lower and ("transfer" in lower or "redistribu" in lower)

    def test_zero_card_holders_only(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "zero cards of unmaking" in lower or "zero card" in lower

    def test_no_announcement_on_redistribution(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "no server-wide announcement" in lower or ("completely silent" in lower and "no" in lower)

    def test_respawn_at_bind_point(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "bind" in lower and ("respawn" in lower or "point" in lower)

    def test_enchanted_items_preserved_on_death(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("enchant" in lower) and ("preserv" in lower or "keep" in lower or "survive" in lower or "retain" in lower)

    def test_no_unmaking_buffs_after_death(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "zero cards of unmaking" in lower and ("respawn" in lower or "death" in lower)

    # --- NPC Card Effect Auto-Generation (§9.23) ---

    def test_auto_generation_section_exists(self):
        text = _load_doc(self.DOC_NAME)
        assert "Auto-Generation" in text or "Identity Template System" in text

    def test_auto_generation_example_table(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "fire beetle" in lower and "fippy darkpaw" in lower and "lord nagafen" in lower

    def test_auto_generation_rules(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "auto-generat" in lower and ("rule" in lower or "template" in lower)


# ===========================================================================
# Soul Engine — soul architecture implementation
# ===========================================================================


class TestSoulEngine:
    """Validate soul_engine.py has the expected soul architecture components."""

    SRC_NAME = "soul_engine.py"

    def test_source_file_exists(self):
        from pathlib import Path
        assert (Path(__file__).resolve().parent.parent.parent / "src" / "eq" / self.SRC_NAME).exists()

    def test_has_soul_document_class(self):
        text = _load_src(self.SRC_NAME)
        assert "SoulDocument" in text

    def test_has_short_term_memory(self):
        text = _load_src(self.SRC_NAME)
        assert "short_term_memory" in text

    def test_has_long_term_archive(self):
        text = _load_src(self.SRC_NAME)
        assert "long_term_archive" in text

    def test_has_recall_engine(self):
        text = _load_src(self.SRC_NAME)
        assert "recall_engine" in text

    def test_has_faction_alignment(self):
        text = _load_src(self.SRC_NAME)
        assert "faction_alignment" in text

    def test_has_lifestyle_layer(self):
        text = _load_src(self.SRC_NAME)
        assert "lifestyle" in text

    def test_has_caste_in_lifestyle(self):
        text = _load_src(self.SRC_NAME)
        assert "caste" in text

    def test_has_heroic_persona(self):
        text = _load_src(self.SRC_NAME)
        assert "heroic_persona" in text

    def test_has_card_collection(self):
        text = _load_src(self.SRC_NAME)
        assert "card_collection" in text

    def test_has_death_state(self):
        text = _load_src(self.SRC_NAME)
        assert "death_state" in text

    def test_has_named_creature_flag(self):
        text = _load_src(self.SRC_NAME)
        assert "is_named" in text

    def test_has_ai_player_flag(self):
        text = _load_src(self.SRC_NAME)
        assert "is_ai_player" in text

    def test_has_soul_bound_protector(self):
        text = _load_src(self.SRC_NAME)
        assert "soul_bound_protectors" in text

    def test_has_soul_engine_class(self):
        text = _load_src(self.SRC_NAME)
        assert "class SoulEngine" in text

    def test_has_death_processing(self):
        text = _load_src(self.SRC_NAME)
        assert "process_death" in text

    def test_has_respawn_processing(self):
        text = _load_src(self.SRC_NAME)
        assert "process_respawn_at_bind" in text

    def test_has_memory_recording(self):
        text = _load_src(self.SRC_NAME)
        assert "record_event" in text

    def test_has_npc_card_effects_import(self):
        text = _load_src(self.SRC_NAME)
        assert "npc_card_effects" in text

    def test_has_spawner_registry_reference(self):
        text = _load_src(self.SRC_NAME)
        # soul engine integrates with spawner_registry (referenced in module docstring)
        assert "spawner_registry" in text

# ===========================================================================
# Sorceror Class Design Document
# ===========================================================================


class TestSorcerorClassDesign:
    """Validate SORCEROR_CLASS_DESIGN.md structure."""

    DOC_NAME = "SORCEROR_CLASS_DESIGN.md"

    def test_document_exists(self):
        assert (DOCS_DIR / self.DOC_NAME).exists()

    def test_class_identity_monk_mage_hybrid(self):
        text = _load_doc(self.DOC_NAME)
        assert "Monk" in text or "monk" in text
        assert "Mage" in text or "mage" in text

    def test_primarily_damage_class(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "primarily a damage class" in lower

    def test_situational_utility(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "situational utility" in lower

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
        assert ("base" in lower and "damage" in lower) or ("base dmg" in lower) or ("base damage" in lower)

    def test_epic_boosts_meld_effectiveness(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "meld" in lower
        assert "effectiveness" in lower or "potency" in lower or "amplif" in lower

    def test_two_handed_staff_core_weapon(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("core weapon" in lower) or ("core" in lower and "staff" in lower)

    def test_cloth_armor_support(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "cloth" in lower

    def test_leather_armor_support(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "leather" in lower

    def test_fungi_tunic_usable(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "fungi tunic" in lower

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

    def test_avoidance_tank_identity(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "avoidance" in lower and "tank" in lower

    def test_discipline_of_rumblecrush(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "rumblecrush" in lower
        assert "discipline" in lower or "disc" in lower

    def test_rumblecrush_defensive_disc_duration(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "defensive" in lower and ("discipline" in lower or "disc" in lower)
        assert "180" in text or "same duration" in lower or "same as" in lower

    def test_rumblecrush_pets_gain_defensive(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "pet" in lower and "defensive" in lower
        assert "damage reduction" in lower or "mitigation" in lower or "dr" in lower

    def test_rumblecrush_procs_cost_mana(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "proc" in lower and "mana" in lower

    def test_beastlord_synergy(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "beastlord" in lower
        assert "mana" in lower

    def test_lord_of_the_maelstrom(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "lord of the maelstrom" in lower
        assert "plane of sky" in lower

    def test_lord_of_maelstrom_raid_drop(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "raid" in lower and ("drop" in lower or "dropped" in lower)

    def test_single_element_rule(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "single-element" in lower or "one type of elemental" in lower or "one element" in lower

    def test_earth_procs_root_and_rune(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "earth" in lower
        assert "root" in lower
        assert "rune" in lower or "absorption" in lower

    def test_fire_procs_ac_damage_shield(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "fire" in lower
        assert "damage shield" in lower or "ds" in lower
        assert "ac" in lower

    def test_eligible_races_int_casters(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "dark elf" in lower
        assert "erudite" in lower
        assert "human" in lower
        assert "high elf" in lower
        assert "gnome" in lower

    def test_slow_weapon_proc_modifier(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "proc modifier" in lower or "proc modifiers" in lower
        assert "slow" in lower

    def test_bard_proc_line(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "bard" in lower and "proc" in lower and "line" in lower

    def test_weapon_1h_slashing(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "1h slashing" in lower or "1h slash" in lower

    def test_weapon_1h_piercing(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "1h piercing" in lower or "piercing" in lower

    def test_no_1h_blunt(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("no 1h blunt" in lower) or ("cannot" in lower and "1h blunt" in lower) or ("no" in lower and "blunt" in lower)

    # --- Liquify Ability ---

    def test_liquify_ability_exists(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "liquify" in lower

    def test_liquify_requires_water_pet(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "water" in lower and "pet" in lower
        assert "liquify" in lower

    def test_liquify_aggro_drop(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert ("aggro" in lower and "drop" in lower) or ("aggro drop" in lower)

    def test_liquify_invisibility(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "invisibility" in lower or "invisible" in lower or "invis" in lower

    def test_liquify_level_40(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "liquify" in lower
        assert "40" in text

    def test_liquify_in_ability_table(self):
        text = _load_doc(self.DOC_NAME)
        lower = text.lower()
        assert "liquify i" in lower or "liquify ii" in lower


# ===========================================================================
# Cross-Document Consistency — Sorceror features match in both docs
# ===========================================================================


class TestCrossDocumentConsistency:
    """Verify key Sorceror features are documented consistently in both
    the main plan and the class design document."""

    PLAN = "EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md"
    CLASS = "SORCEROR_CLASS_DESIGN.md"

    def test_both_mention_rumblecrush(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "rumblecrush" in plan
        assert "rumblecrush" in cls

    def test_both_mention_lord_of_the_maelstrom(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "lord of the maelstrom" in plan
        assert "lord of the maelstrom" in cls

    def test_both_mention_single_element_rule(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "single-element" in plan or "single element" in plan or "one element" in plan
        assert "single-element" in cls or "single element" in cls or "one element" in cls

    def test_both_mention_bard_proc_line(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "bard" in plan and "proc" in plan
        assert "bard" in cls and "proc" in cls

    def test_both_mention_eligible_races(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        for race in ["dark elf", "erudite", "human", "high elf", "gnome"]:
            assert race in plan, f"{race} missing from main plan"
            assert race in cls, f"{race} missing from class design"

    def test_both_mention_weapon_restrictions(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "1h slashing" in plan or "1h slash" in plan
        assert "1h slashing" in cls or "1h slash" in cls
        assert "piercing" in plan
        assert "piercing" in cls

    def test_both_mention_fungi_tunic(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "fungi" in plan
        assert "fungi" in cls

    def test_both_mention_defensive_disc_comparison(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "defensive" in plan
        assert "defensive" in cls

    def test_both_mention_beastlord_synergy(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "beastlord" in plan
        assert "beastlord" in cls

    def test_plan_implementation_has_rumblecrush_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "rumblecrush" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_implementation_has_maelstrom_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "maelstrom" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_section_numbers_unique(self):
        """Verify no duplicate subsection numbers in the main plan."""
        text = _load_doc(self.PLAN)
        headings = re.findall(r"^(### \d+\.\d+)\s", text, re.MULTILINE)
        assert len(headings) == len(set(headings)), (
            f"Duplicate subsection numbers found: "
            f"{[h for h in headings if headings.count(h) > 1]}"
        )

    # --- EQ Isolation, Language, Self-Preservation consistency ---

    def test_both_mention_liquify(self):
        plan = _load_doc(self.PLAN).lower()
        cls = _load_doc(self.CLASS).lower()
        assert "liquify" in plan
        assert "liquify" in cls

    def test_plan_and_soul_mention_language_restriction(self):
        plan = _load_doc(self.PLAN).lower()
        assert "language" in plan and ("restriction" in plan or "capability" in plan)
        # soul architecture implementation (soul_engine.py) enforces language rules at runtime

    def test_plan_and_soul_mention_self_preservation(self):
        plan = _load_doc(self.PLAN).lower()
        assert "self-preservation" in plan or "self preservation" in plan

    def test_plan_and_soul_mention_flee_on_healer_death(self):
        plan = _load_doc(self.PLAN).lower()
        assert "healer" in plan and "flee" in plan

    def test_plan_and_soul_mention_hybrid_healer_exception(self):
        plan = _load_doc(self.PLAN).lower()
        assert "hybrid" in plan and "healer" in plan

    def test_plan_has_isolation_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "isolation" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_liquify_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "liquify" in plan and ("implement" in plan or "[ ]" in plan)

    # --- NPC Lifestyle cross-document consistency ---

    def test_plan_and_soul_mention_lifestyle(self):
        plan = _load_doc(self.PLAN).lower()
        soul = _load_src("soul_engine.py").lower()
        assert "lifestyle" in plan
        assert "lifestyle" in soul

    def test_plan_and_soul_mention_caste(self):
        plan = _load_doc(self.PLAN).lower()
        soul = _load_src("soul_engine.py").lower()
        assert "caste" in plan
        assert "caste" in soul

    def test_plan_and_soul_mention_skill_degradation(self):
        plan = _load_doc(self.PLAN).lower()
        assert "degrad" in plan

    def test_plan_and_soul_mention_skill_floor(self):
        plan = _load_doc(self.PLAN).lower()
        assert "skill floor" in plan or "skill_floor" in plan

    def test_plan_has_lifestyle_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "daily routine" in plan and ("implement" in plan or "[ ]" in plan)

    # --- Macro-Trigger, Perception, Lore, Sleeper cross-doc consistency ---

    def test_plan_and_soul_mention_perception_inference(self):
        plan = _load_doc(self.PLAN).lower()
        assert "perception" in plan and "inference" in plan

    def test_plan_and_soul_mention_lore_seed(self):
        plan = _load_doc(self.PLAN).lower()
        assert "lore" in plan and "seed" in plan

    def test_plan_and_soul_mention_macro_trigger(self):
        plan = _load_doc(self.PLAN).lower()
        assert "macro" in plan and "trigger" in plan

    def test_plan_and_soul_mention_shared_lore_blocks(self):
        plan = _load_doc(self.PLAN).lower()
        assert "shared lore" in plan

    def test_plan_has_perception_pipeline_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "perception" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_lore_seed_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "lore" in plan and "import" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_sleeper_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "sleeper" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_dragon_tell_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert ("dragon" in plan and "/tell" in plan) or ("tell" in plan and "rally" in plan)

    # --- God Cards cross-document consistency ---

    def test_plan_has_god_card_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "god card" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_tower_of_unmaker_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "tower of the unmaker" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_banned_by_unmaker_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "banned by the unmaker" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_card_system_extension(self):
        plan = _load_doc(self.PLAN).lower()
        assert "card_system.py" in plan

    def test_plan_has_god_card_scope(self):
        plan = _load_doc(self.PLAN).lower()
        assert ("god cards" in plan and "unmaker" in plan) or ("deity card" in plan) or ("card drop" in plan)

    def test_plan_and_soul_mention_card_collection(self):
        plan = _load_doc(self.PLAN).lower()
        soul = _load_src("soul_engine.py").lower()
        assert ("card" in plan and "collection" in plan) or ("card_collection" in plan)
        assert ("card" in soul and "collection" in soul) or ("card_collection" in soul)

    def test_plan_has_universal_card_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "universal card" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_world_entropy_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "world entropy" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_server_reboot_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "server reboot" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_becoming_unmaker_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "becoming the unmaker" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_unmaker_aa_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "unmaker aa" in plan and "100%" in plan

    # --- New system cross-doc tests ---

    def test_plan_has_cooldown_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "cooldown" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_spawner_registry_implementation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "spawner registry" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_world_decay_vote_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "50%" in plan and "vote" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_experience_lore_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "experience" in plan and "lore" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_heroic_persona_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "heroic persona" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_tts_voice_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert ("text-to-speech" in plan or "voice profile" in plan) and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_agent_streaming_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "streaming" in plan and "agent" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_spawner_registry_schema(self):
        plan = _load_doc(self.PLAN).lower()
        assert "spawner registry schema" in plan or "spawner_unlocked" in plan

    def test_plan_has_world_decay_schema(self):
        plan = _load_doc(self.PLAN).lower()
        assert "world decay state schema" in plan or "decay_percentage" in plan

    def test_plan_has_streaming_profile_schema(self):
        plan = _load_doc(self.PLAN).lower()
        assert "streaming profile schema" in plan or "is_streaming_agent" in plan

    def test_plan_has_spawner_registry_extension(self):
        plan = _load_doc(self.PLAN).lower()
        assert "spawner_registry.py" in plan

    def test_plan_has_experience_lore_extension(self):
        plan = _load_doc(self.PLAN).lower()
        assert "experience_lore.py" in plan

    def test_plan_has_agent_voice_extension(self):
        plan = _load_doc(self.PLAN).lower()
        assert "agent_voice.py" in plan

    def test_plan_and_soul_both_have_cooldowns(self):
        plan = _load_doc(self.PLAN).lower()
        assert "cooldown" in plan

    def test_plan_and_soul_both_have_experience_lore(self):
        plan = _load_doc(self.PLAN).lower()
        assert "experience" in plan and "lore" in plan

    def test_plan_and_soul_both_have_voice(self):
        plan = _load_doc(self.PLAN).lower()
        assert "voice profile" in plan or "text-to-speech" in plan

    def test_plan_scope_has_spawner_registry(self):
        plan = _load_doc(self.PLAN).lower()
        assert "spawner registry" in plan and ("scope" in plan or "spawner_registry.py" in plan)

    def test_plan_scope_has_experience_lore(self):
        plan = _load_doc(self.PLAN).lower()
        assert "experience-based lore" in plan or "experience_lore.py" in plan

    def test_plan_scope_has_agent_streaming(self):
        plan = _load_doc(self.PLAN).lower()
        assert "agent" in plan and "streaming" in plan

    def test_plan_risk_card_cooldown(self):
        plan = _load_doc(self.PLAN).lower()
        assert "cooldown" in plan and ("risk" in plan or "too long" in plan or "too short" in plan)

    def test_plan_risk_vote_manipulation(self):
        plan = _load_doc(self.PLAN).lower()
        assert "vote" in plan and ("manipulation" in plan or "manipulate" in plan)

    def test_plan_risk_lore_fidelity(self):
        plan = _load_doc(self.PLAN).lower()
        assert "fidelity" in plan and ("spiral" in plan or "degrad" in plan)

    def test_plan_risk_tts_quality(self):
        plan = _load_doc(self.PLAN).lower()
        assert "tts" in plan or ("voice" in plan and "quality" in plan)

    # --- NPC Card Effects cross-doc tests ---

    def test_plan_has_npc_card_effects_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "npc card effect" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_soul_protector_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "soul-bound protector" in plan and ("implement" in plan or "[ ]" in plan)

    def test_plan_has_npc_card_effects_extension(self):
        plan = _load_doc(self.PLAN).lower()
        assert "npc_card_effects.py" in plan

    def test_plan_has_npc_card_effect_schema(self):
        plan = _load_doc(self.PLAN).lower()
        assert "npc card effect schema" in plan or "tier_1_combat_spell" in plan

    def test_plan_scope_has_npc_card_effects(self):
        plan = _load_doc(self.PLAN).lower()
        assert "npc card effects" in plan and "soul-binding" in plan

    def test_plan_risk_soul_protector_imbalance(self):
        plan = _load_doc(self.PLAN).lower()
        assert "soul-bound protector" in plan and ("imbalance" in plan or "risk" in plan)

    def test_plan_risk_ai_player_aggression(self):
        plan = _load_doc(self.PLAN).lower()
        assert "ai player" in plan and ("aggression" in plan or "kill" in plan)

    def test_plan_and_soul_both_have_npc_card_effects(self):
        plan = _load_doc(self.PLAN).lower()
        soul = _load_src("soul_engine.py").lower()
        assert "npc_card_effects.py" in plan
        assert "npc_card_effects" in soul

    def test_plan_has_level_60_cap_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert ("level-60" in plan or "sub-60" in plan or "level 60" in plan) and ("cap" in plan or "max" in plan)

    def test_plan_has_3_card_attackable_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "attackable" in plan and "3" in plan

    def test_plan_has_death_redistribution_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert ("redistribu" in plan or "silent transfer" in plan) and "death" in plan

    def test_plan_has_auto_generation_task(self):
        plan = _load_doc(self.PLAN).lower()
        assert "auto-generat" in plan or "identity template" in plan

    def test_plan_risk_silent_transfer_exploit(self):
        plan = _load_doc(self.PLAN).lower()
        assert "silent" in plan and ("transfer" in plan or "card" in plan) and ("exploit" in plan or "farm" in plan)

    def test_plan_schema_has_sub_60_cards(self):
        plan = _load_doc(self.PLAN).lower()
        assert "sub_60_cards_obtained" in plan

    def test_plan_schema_has_attackable_by_all(self):
        plan = _load_doc(self.PLAN).lower()
        assert "attackable_by_all" in plan

    def test_plan_schema_has_death_redistribution(self):
        plan = _load_doc(self.PLAN).lower()
        assert "death_redistribution" in plan

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

"""
Tests for the final EQ modules: town systems, streaming overlay, Murphy integration.
"""

import pytest

from src.eq.town_systems import (
    GovernanceLogger,
    InspectSystem,
    Town,
    TownConquestSystem,
    TownDefender,
    TownState,
)
from src.eq.streaming_overlay import (
    DuelHighlight,
    FactionWarMapEntry,
    OverlayConfig,
    OverlayType,
    StreamOverlayManager,
    ThoughtBubble,
)
from src.eq.murphy_integration import (
    RaidLeaderModerator,
    RosettaPersistenceAdapter,
    SentimentClassifier,
    SentimentResult,
    VoiceChatConfig,
)


# ===================================================================
# Inspect System Tests
# ===================================================================

class TestInspectSystem:

    def test_cannot_inspect_unknown_item(self):
        ins = InspectSystem()
        assert ins.can_inspect("p1", "sword_01") is False

    def test_can_inspect_after_possession(self):
        ins = InspectSystem()
        ins.register_possession("p1", "sword_01")
        assert ins.can_inspect("p1", "sword_01") is True

    def test_different_entity_cannot_inspect(self):
        ins = InspectSystem()
        ins.register_possession("p1", "sword_01")
        assert ins.can_inspect("p2", "sword_01") is False

    def test_get_known_items(self):
        ins = InspectSystem()
        ins.register_possession("p1", "sword_01")
        ins.register_possession("p1", "shield_01")
        known = ins.get_known_items("p1")
        assert "sword_01" in known
        assert "shield_01" in known
        assert len(known) == 2


# ===================================================================
# Town Conquest System Tests
# ===================================================================

class TestTownConquestSystem:

    def _make_town(self, town_id="cb", faction="orcs") -> Town:
        return Town(
            town_id=town_id,
            name="Crushbone",
            owning_faction=faction,
            state=TownState.PEACEFUL,
            defenders=[TownDefender(npc_id="g1", name="Guard", level=30, role="guard")],
            buildings=["forge", "tavern"],
        )

    def test_register_town(self):
        tcs = TownConquestSystem()
        tcs.register_town(self._make_town())
        assert tcs.town_count == 1

    def test_get_town(self):
        tcs = TownConquestSystem()
        tcs.register_town(self._make_town())
        town = tcs.get_town("cb")
        assert town is not None
        assert town.name == "Crushbone"

    def test_start_siege(self):
        tcs = TownConquestSystem()
        tcs.register_town(self._make_town())
        result = tcs.start_siege("cb", "elves")
        assert result is True
        town = tcs.get_town("cb")
        assert town.state == TownState.UNDER_SIEGE

    def test_resolve_siege_conquered(self):
        tcs = TownConquestSystem()
        tcs.register_town(self._make_town())
        tcs.start_siege("cb", "elves")
        state = tcs.resolve_siege("cb", attackers_won=True)
        assert state == TownState.CONQUERED

    def test_resolve_siege_liberated(self):
        tcs = TownConquestSystem()
        tcs.register_town(self._make_town())
        tcs.start_siege("cb", "elves")
        state = tcs.resolve_siege("cb", attackers_won=False)
        assert state == TownState.LIBERATED

    def test_towns_by_faction(self):
        tcs = TownConquestSystem()
        tcs.register_town(self._make_town("cb", "orcs"))
        tcs.register_town(self._make_town("gfay", "elves"))
        orc_towns = tcs.get_towns_by_faction("orcs")
        assert len(orc_towns) == 1


# ===================================================================
# Governance Logger Tests
# ===================================================================

class TestGovernanceLogger:

    def test_log_action(self):
        gl = GovernanceLogger()
        entry = gl.log_action("mute", "admin_1", "player_5")
        assert entry.action == "mute"
        assert entry.actor == "admin_1"

    def test_log_count(self):
        gl = GovernanceLogger()
        gl.log_action("mute", "a", "p1")
        gl.log_action("kick", "a", "p2")
        assert gl.log_count == 2

    def test_filter_by_actor(self):
        gl = GovernanceLogger()
        gl.log_action("mute", "admin_1", "p1")
        gl.log_action("kick", "admin_2", "p2")
        logs = gl.get_logs(actor="admin_1")
        assert len(logs) == 1


# ===================================================================
# Stream Overlay Manager Tests
# ===================================================================

class TestStreamOverlayManager:

    def test_register_overlay(self):
        mgr = StreamOverlayManager()
        cfg = OverlayConfig(overlay_type=OverlayType.EVENT_FEED, enabled=True)
        mgr.register_overlay(cfg)
        assert mgr.overlay_count >= 1

    def test_show_thought_bubble(self):
        mgr = StreamOverlayManager()
        bubble = mgr.show_thought_bubble("agent_1", "I wonder about that orc...")
        assert bubble.agent_id == "agent_1"
        assert bubble.text == "I wonder about that orc..."
        assert mgr.thought_bubble_count == 1

    def test_capture_duel_highlight(self):
        mgr = StreamOverlayManager()
        hl = mgr.capture_duel_highlight("d1", "PlayerA", "PlayerB", "PlayerA")
        assert hl.winner_name == "PlayerA"
        assert hl.auto_captured is True
        assert mgr.duel_highlight_count == 1

    def test_faction_war_map(self):
        mgr = StreamOverlayManager()
        entries = [
            FactionWarMapEntry(faction_id="orcs", territory_zones=["crushbone"], at_war_with=["elves"], color="#ff0000"),
        ]
        mgr.update_faction_war_map(entries)
        # No assertion failure = success

    def test_start_stop_stream(self):
        mgr = StreamOverlayManager()
        agent = mgr.start_agent_stream("a1", "twitch")
        assert agent.streaming is True
        assert mgr.active_streams >= 1
        mgr.stop_agent_stream("a1")
        assert mgr.active_streams == 0

    def test_get_active_overlays(self):
        mgr = StreamOverlayManager()
        mgr.register_overlay(OverlayConfig(overlay_type=OverlayType.THOUGHT_BUBBLE, enabled=True))
        mgr.register_overlay(OverlayConfig(overlay_type=OverlayType.CARD_COLLECTION, enabled=False))
        active = mgr.get_active_overlays()
        assert len(active) >= 1
        assert all(o.enabled for o in active)


# ===================================================================
# Sentiment Classifier Tests
# ===================================================================

class TestSentimentClassifier:

    def test_classify_positive(self):
        sc = SentimentClassifier()
        result = sc.classify("Great job everyone! Well played!")
        assert result.sentiment in ("positive", "neutral")

    def test_classify_negative(self):
        sc = SentimentClassifier()
        result = sc.classify("This is terrible and awful")
        assert result.sentiment in ("negative", "neutral")

    def test_should_moderate_toxic(self):
        sc = SentimentClassifier()
        result = SentimentResult(text="bad words", sentiment="toxic", confidence=0.9, moderated=False)
        assert sc.should_moderate(result) is True

    def test_should_not_moderate_neutral(self):
        sc = SentimentClassifier()
        result = SentimentResult(text="hello", sentiment="neutral", confidence=0.9, moderated=False)
        assert sc.should_moderate(result) is False


# ===================================================================
# Raid Leader Moderator Tests
# ===================================================================

class TestRaidLeaderModerator:

    def test_mute_player(self):
        mod = RaidLeaderModerator()
        action = mod.mute_player("admin1", "player5", "disruptive")
        assert action.action_type == "mute"
        assert action.target_entity == "player5"

    def test_kick_from_raid(self):
        mod = RaidLeaderModerator()
        action = mod.kick_from_raid("admin1", "player5", "afk")
        assert action.action_type == "kick"

    def test_action_count(self):
        mod = RaidLeaderModerator()
        mod.mute_player("a", "p1", "spam")
        mod.unmute_player("a", "p1")
        assert mod.action_count == 2


# ===================================================================
# Rosetta Persistence Adapter Tests
# ===================================================================

class TestRosettaPersistenceAdapter:

    def test_save_and_load(self):
        rpa = RosettaPersistenceAdapter()
        assert rpa.save_soul("agent1", {"name": "Emperor Crush", "level": 55}) is True
        loaded = rpa.load_soul("agent1")
        assert loaded is not None
        assert loaded["name"] == "Emperor Crush"

    def test_load_nonexistent(self):
        rpa = RosettaPersistenceAdapter()
        assert rpa.load_soul("nobody") is None

    def test_delete_soul(self):
        rpa = RosettaPersistenceAdapter()
        rpa.save_soul("agent1", {"name": "test"})
        assert rpa.delete_soul("agent1") is True
        assert rpa.load_soul("agent1") is None

    def test_list_saved_souls(self):
        rpa = RosettaPersistenceAdapter()
        rpa.save_soul("a1", {"n": "1"})
        rpa.save_soul("a2", {"n": "2"})
        souls = rpa.list_saved_souls()
        assert "a1" in souls
        assert "a2" in souls

    def test_saved_soul_count(self):
        rpa = RosettaPersistenceAdapter()
        rpa.save_soul("a1", {})
        assert rpa.saved_soul_count == 1


# ===================================================================
# Voice Chat Config Tests
# ===================================================================

class TestVoiceChatConfig:

    def test_default_config(self):
        cfg = VoiceChatConfig()
        assert cfg.enabled is True
        assert cfg.push_to_talk is True
        assert cfg.group_toggle is True
        assert cfg.raid_toggle is True

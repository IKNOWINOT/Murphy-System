"""
Tests for EverQuest Avatar Agent Window and Let's Play Session system.

Validates:
  - AvatarAgentWindow creation and state management
  - EQLetsPlaySession lifecycle (start, narrate, action, zone change, end)
  - LetsPlaySessionManager session tracking
  - StreamOverlayManager avatar window integration
  - CRO-managed session creation via InoniOrgBootstrap
  - Agent routing for avatar/let's-play keywords → CRO
"""

import pytest

from src.eq.streaming_overlay import (
    AvatarAgentWindow,
    EQLetsPlaySession,
    LetsPlaySessionManager,
    OverlayConfig,
    OverlayType,
    StreamOverlayManager,
)


# ---------------------------------------------------------------------------
# AvatarAgentWindow
# ---------------------------------------------------------------------------

class TestAvatarAgentWindow:
    """Tests for the avatar agent window overlay."""

    def test_create_window_defaults(self):
        window = AvatarAgentWindow(
            agent_id="agent-001",
            character_name="Gorefist",
        )
        assert window.agent_id == "agent-001"
        assert window.character_name == "Gorefist"
        assert window.race == "Human"
        assert window.eq_class == "Warrior"
        assert window.position == "bottom_left"
        assert window.visible is True
        assert window.narration_enabled is True
        assert window.current_action == "idle"

    def test_create_window_custom(self):
        window = AvatarAgentWindow(
            agent_id="agent-002",
            character_name="Xylira",
            race="High Elf",
            eq_class="Enchanter",
            level=55,
            current_zone="Plane of Hate",
        )
        assert window.race == "High Elf"
        assert window.eq_class == "Enchanter"
        assert window.level == 55
        assert window.current_zone == "Plane of Hate"

    def test_add_narration(self):
        window = AvatarAgentWindow(agent_id="a1", character_name="Test")
        window.add_narration("I see a gnoll camp ahead.")
        window.add_narration("Time to pull carefully.")
        assert len(window.thought_stream) == 2
        assert "gnoll" in window.thought_stream[0]

    def test_update_game_state(self):
        window = AvatarAgentWindow(agent_id="a1", character_name="Test")
        window.update_game_state(
            zone="Lower Guk",
            action="combat",
            hp=75.0,
            mana=50.0,
            level=30,
        )
        assert window.current_zone == "Lower Guk"
        assert window.current_action == "combat"
        assert window.hp_percent == 75.0
        assert window.mana_percent == 50.0
        assert window.level == 30

    def test_to_overlay_config(self):
        window = AvatarAgentWindow(agent_id="a1", character_name="Test")
        config = window.to_overlay_config()
        assert isinstance(config, OverlayConfig)
        assert config.overlay_type == OverlayType.AVATAR_AGENT_WINDOW
        assert config.position == "bottom_left"

    def test_to_dict(self):
        window = AvatarAgentWindow(
            agent_id="a1",
            character_name="Gorefist",
            race="Ogre",
            eq_class="Shadow Knight",
        )
        d = window.to_dict()
        assert d["agent_id"] == "a1"
        assert d["character_name"] == "Gorefist"
        assert d["race"] == "Ogre"
        assert d["class"] == "Shadow Knight"
        assert d["position"] == "bottom_left"
        assert d["visible"] is True


# ---------------------------------------------------------------------------
# EQLetsPlaySession
# ---------------------------------------------------------------------------

class TestEQLetsPlaySession:
    """Tests for the EQ let's play session lifecycle."""

    def test_session_creation(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael Ashford",
            character_name="Firiona",
            race="Wood Elf",
            eq_class="Ranger",
        )
        assert session.agent_persona_name == "Kael Ashford"
        assert session.character_name == "Firiona"
        assert session.active is False
        assert session.managed_by == "chief_research_officer"

    def test_start_session(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael Ashford",
            character_name="Firiona",
        )
        session.start()
        assert session.active is True
        assert session.started_at is not None
        assert session.avatar_window is not None
        assert session.avatar_window.visible is True
        assert len(session.narration_log) == 1
        assert "begins their adventure" in session.narration_log[0]["text"]

    def test_end_session(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael",
            character_name="Firiona",
        )
        session.start()
        session.end()
        assert session.active is False
        assert session.ended_at is not None
        assert session.avatar_window.visible is False

    def test_narrate(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael",
            character_name="Firiona",
        )
        session.start()
        session.narrate("I smell orcs in the distance.")
        assert len(session.narration_log) == 2  # start + narration
        assert session.avatar_window.thought_stream[-1] == "I smell orcs in the distance."

    def test_perform_action(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael",
            character_name="Firiona",
        )
        session.start()
        result = session.perform_action("attack", {"target": "orc pawn"})
        assert result["action"] == "attack"
        assert result["details"]["target"] == "orc pawn"
        assert session.avatar_window.current_action == "attack"

    def test_update_zone(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael",
            character_name="Firiona",
        )
        session.start()
        session.update_zone("Crushbone")
        assert session.current_zone == "Crushbone"
        assert session.avatar_window.current_zone == "Crushbone"

    def test_to_dict(self):
        session = EQLetsPlaySession(
            agent_id="cro-001",
            agent_persona_name="Kael Ashford",
            character_name="Firiona",
            race="Wood Elf",
            eq_class="Ranger",
        )
        session.start()
        d = session.to_dict()
        assert d["agent_persona_name"] == "Kael Ashford"
        assert d["managed_by"] == "chief_research_officer"
        assert d["avatar_window"] is not None
        assert d["avatar_window"]["position"] == "bottom_left"


# ---------------------------------------------------------------------------
# LetsPlaySessionManager
# ---------------------------------------------------------------------------

class TestLetsPlaySessionManager:
    """Tests for the session manager."""

    def test_create_session(self):
        mgr = LetsPlaySessionManager()
        session = mgr.create_session(
            agent_id="cro-001",
            agent_persona_name="Kael",
            character_name="Gorefist",
            race="Ogre",
            eq_class="Warrior",
        )
        assert session.active is True
        assert mgr.session_count == 1
        assert mgr.active_session_count == 1

    def test_end_session(self):
        mgr = LetsPlaySessionManager()
        session = mgr.create_session(
            agent_id="cro-001",
            agent_persona_name="Kael",
            character_name="Gorefist",
        )
        mgr.end_session(session.session_id)
        assert mgr.active_session_count == 0
        assert mgr.session_count == 1  # still tracked

    def test_multiple_sessions(self):
        mgr = LetsPlaySessionManager()
        s1 = mgr.create_session("a1", "Kael", "Gorefist", "Ogre", "Warrior")
        s2 = mgr.create_session("a2", "Kael", "Xylira", "High Elf", "Enchanter")
        assert mgr.session_count == 2
        assert mgr.active_session_count == 2
        mgr.end_session(s1.session_id)
        assert mgr.active_session_count == 1

    def test_get_sessions_by_agent(self):
        mgr = LetsPlaySessionManager()
        mgr.create_session("a1", "Kael", "Gorefist")
        mgr.create_session("a1", "Kael", "Xylira")
        mgr.create_session("a2", "Other", "Firiona")
        assert len(mgr.get_sessions_by_agent("a1")) == 2
        assert len(mgr.get_sessions_by_agent("a2")) == 1

    def test_overlay_registered(self):
        overlay_mgr = StreamOverlayManager()
        mgr = LetsPlaySessionManager(overlay_manager=overlay_mgr)
        mgr.create_session("a1", "Kael", "Gorefist")
        assert overlay_mgr.overlay_count == 1
        active = overlay_mgr.get_active_overlays()
        assert any(o.overlay_type == OverlayType.AVATAR_AGENT_WINDOW for o in active)


# ---------------------------------------------------------------------------
# StreamOverlayManager avatar window creation
# ---------------------------------------------------------------------------

class TestStreamOverlayManagerAvatarWindow:
    """Tests for avatar window creation via the overlay manager."""

    def test_create_avatar_window(self):
        mgr = StreamOverlayManager()
        window = mgr.create_avatar_window(
            agent_id="cro-001",
            character_name="Gorefist",
            race="Ogre",
            eq_class="Warrior",
        )
        assert isinstance(window, AvatarAgentWindow)
        assert window.position == "bottom_left"
        assert window.character_name == "Gorefist"
        assert mgr.active_streams == 1


# ---------------------------------------------------------------------------
# CRO routing for avatar agent keywords
# ---------------------------------------------------------------------------

class TestCROAvatarRouting:
    """Tests that avatar/let's play keywords route to the CRO."""

    @pytest.fixture()
    def bootstrap(self):
        from src.inoni_org_bootstrap import InoniOrgBootstrap
        b = InoniOrgBootstrap()
        b.bootstrap()
        return b

    def test_route_lets_play(self, bootstrap):
        persona = bootstrap.route_to_agent("Can we start a let's play session?")
        assert persona is not None
        assert persona["role"] == "chief_research_officer"

    def test_route_avatar_agent(self, bootstrap):
        persona = bootstrap.route_to_agent("Show me the avatar agent window")
        assert persona is not None
        assert persona["role"] == "chief_research_officer"

    def test_route_eq_session(self, bootstrap):
        persona = bootstrap.route_to_agent("Create a new EQ session for Gorefist")
        assert persona is not None
        assert persona["role"] == "chief_research_officer"

    def test_create_eq_lets_play(self, bootstrap):
        result = bootstrap.create_eq_lets_play_session(
            character_name="Gorefist",
            race="Ogre",
            eq_class="Warrior",
        )
        assert "session" in result
        assert result["session"]["active"] is True
        assert result["managed_by"]["role"] == "chief_research_officer"
        assert result["avatar_window"]["position"] == "bottom_left"

    def test_get_eq_sessions(self, bootstrap):
        bootstrap.create_eq_lets_play_session("Gorefist", "Ogre", "Warrior")
        sessions = bootstrap.get_eq_sessions()
        assert sessions["active"] == 1
        assert sessions["total"] == 1

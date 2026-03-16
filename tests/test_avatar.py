"""Comprehensive tests for the Avatar Identity Layer."""

import threading
from datetime import datetime, timezone

import pytest

from avatar import (
    AvatarProfile,
    AvatarRegistry,
    AvatarSession,
    AvatarSessionManager,
    AvatarStyle,
    AvatarVoice,
    BehavioralScoringEngine,
    ComplianceGuard,
    ComplianceViolation,
    CostEntry,
    CostLedger,
    PersonaInjector,
    SentimentClassifier,
    SentimentResult,
    UserAdaptation,
    UserAdaptationEngine,
)
from avatar.connectors import (
    ElevenLabsConnector,
    HeyGenConnector,
    TavusConnector,
    VapiConnector,
)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestAvatarModels:
    def test_avatar_profile_defaults(self):
        p = AvatarProfile(avatar_id="a1", name="Murphy")
        assert p.voice == AvatarVoice.PROFESSIONAL
        assert p.style == AvatarStyle.FORMAL
        assert p.enabled is True
        assert isinstance(p.created_at, datetime)
        assert p.personality_traits == {}
        assert p.knowledge_domains == []

    def test_avatar_profile_custom(self):
        p = AvatarProfile(
            avatar_id="a2",
            name="Ada",
            voice=AvatarVoice.EMPATHETIC,
            style=AvatarStyle.SUPPORTIVE,
            personality_traits={"warmth": 0.9},
            knowledge_domains=["python", "ai"],
        )
        assert p.voice == AvatarVoice.EMPATHETIC
        assert p.personality_traits["warmth"] == 0.9

    def test_avatar_profile_serialization(self):
        p = AvatarProfile(avatar_id="a3", name="Test")
        data = p.model_dump()
        assert data["avatar_id"] == "a3"
        rebuilt = AvatarProfile(**data)
        assert rebuilt.avatar_id == p.avatar_id

    def test_user_adaptation_defaults(self):
        a = UserAdaptation(user_id="u1", avatar_id="a1")
        assert a.interaction_count == 0
        assert a.preferred_response_length == "medium"
        assert a.preferred_formality == 0.5
        assert a.behavioral_score == 1.0

    def test_sentiment_result(self):
        r = SentimentResult(text="hello", sentiment="neutral", confidence=0.5)
        assert r.emotions == {}

    def test_cost_entry(self):
        e = CostEntry(
            entry_id="e1",
            avatar_id="a1",
            service="elevenlabs",
            operation="tts",
            cost_usd=0.05,
            timestamp=datetime.now(timezone.utc),
        )
        assert e.cost_usd == 0.05

    def test_compliance_violation(self):
        v = ComplianceViolation(
            violation_id="v1",
            avatar_id="a1",
            rule="no_pii_disclosure",
            description="SSN detected",
            severity="high",
            timestamp=datetime.now(timezone.utc),
        )
        assert v.resolved is False

    def test_avatar_session(self):
        s = AvatarSession(
            session_id="s1",
            avatar_id="a1",
            user_id="u1",
            started_at=datetime.now(timezone.utc),
        )
        assert s.active is True
        assert s.message_count == 0
        assert s.total_cost_usd == 0.0


# ---------------------------------------------------------------------------
# AvatarRegistry tests
# ---------------------------------------------------------------------------


class TestAvatarRegistry:
    def test_register_and_get(self):
        reg = AvatarRegistry()
        p = AvatarProfile(avatar_id="a1", name="Murphy")
        assert reg.register(p) is True
        assert reg.get("a1").name == "Murphy"

    def test_register_duplicate(self):
        reg = AvatarRegistry()
        p = AvatarProfile(avatar_id="a1", name="Murphy")
        reg.register(p)
        assert reg.register(p) is False

    def test_unregister(self):
        reg = AvatarRegistry()
        reg.register(AvatarProfile(avatar_id="a1", name="Murphy"))
        assert reg.unregister("a1") is True
        assert reg.get("a1") is None

    def test_unregister_missing(self):
        reg = AvatarRegistry()
        assert reg.unregister("missing") is False

    def test_list_avatars(self):
        reg = AvatarRegistry()
        reg.register(AvatarProfile(avatar_id="a1", name="A", enabled=True))
        reg.register(AvatarProfile(avatar_id="a2", name="B", enabled=False))
        assert len(reg.list_avatars()) == 2
        assert len(reg.list_avatars(enabled_only=True)) == 1

    def test_update(self):
        reg = AvatarRegistry()
        reg.register(AvatarProfile(avatar_id="a1", name="Old"))
        updated = reg.update("a1", {"name": "New"})
        assert updated.name == "New"

    def test_update_missing(self):
        reg = AvatarRegistry()
        assert reg.update("missing", {"name": "X"}) is None

    def test_get_status(self):
        reg = AvatarRegistry()
        reg.register(AvatarProfile(avatar_id="a1", name="A", enabled=True))
        reg.register(AvatarProfile(avatar_id="a2", name="B", enabled=False))
        status = reg.get_status()
        assert status["total_avatars"] == 2
        assert status["enabled_avatars"] == 1
        assert status["disabled_avatars"] == 1


# ---------------------------------------------------------------------------
# PersonaInjector tests
# ---------------------------------------------------------------------------


class TestPersonaInjector:
    def test_inject_basic(self):
        inj = PersonaInjector()
        avatar = AvatarProfile(avatar_id="a1", name="Murphy")
        result = inj.inject("Tell me about AI.", avatar)
        assert "You are Murphy." in result
        assert "professional" in result
        assert "Tell me about AI." in result

    def test_inject_with_traits(self):
        inj = PersonaInjector()
        avatar = AvatarProfile(
            avatar_id="a1",
            name="Ada",
            personality_traits={"warmth": 0.8},
            knowledge_domains=["python"],
        )
        result = inj.inject("Hello", avatar)
        assert "warmth: 0.8" in result
        assert "python" in result

    def test_inject_with_adaptation_formal(self):
        inj = PersonaInjector()
        avatar = AvatarProfile(avatar_id="a1", name="Murphy")
        adapt = UserAdaptation(
            user_id="u1",
            avatar_id="a1",
            preferred_response_length="long",
            preferred_formality=0.9,
        )
        result = inj.inject("Hi", avatar, adapt)
        assert "long" in result
        assert "formal language" in result

    def test_inject_with_adaptation_casual(self):
        inj = PersonaInjector()
        avatar = AvatarProfile(avatar_id="a1", name="Murphy")
        adapt = UserAdaptation(
            user_id="u1",
            avatar_id="a1",
            preferred_formality=0.1,
        )
        result = inj.inject("Hi", avatar, adapt)
        assert "casual" in result

    def test_generate_greeting(self):
        inj = PersonaInjector()
        avatar = AvatarProfile(avatar_id="a1", name="Murphy")
        greeting = inj.generate_greeting(avatar)
        assert "Murphy" in greeting

    def test_generate_greeting_with_user(self):
        inj = PersonaInjector()
        avatar = AvatarProfile(avatar_id="a1", name="Murphy")
        greeting = inj.generate_greeting(avatar, user_name="Alice")
        assert "Alice" in greeting
        assert "Murphy" in greeting


# ---------------------------------------------------------------------------
# UserAdaptationEngine tests
# ---------------------------------------------------------------------------


class TestUserAdaptationEngine:
    def test_get_creates_default(self):
        engine = UserAdaptationEngine()
        adapt = engine.get_adaptation("u1", "a1")
        assert adapt.user_id == "u1"
        assert adapt.interaction_count == 0

    def test_record_interaction(self):
        engine = UserAdaptationEngine()
        adapt = engine.record_interaction("u1", "a1")
        assert adapt.interaction_count == 1
        assert adapt.last_interaction is not None

    def test_record_interaction_with_feedback(self):
        engine = UserAdaptationEngine()
        adapt = engine.record_interaction("u1", "a1", feedback={"rating": 5})
        assert len(adapt.feedback_history) == 1
        assert adapt.feedback_history[0]["rating"] == 5

    def test_update_preferences(self):
        engine = UserAdaptationEngine()
        adapt = engine.update_preferences(
            "u1", "a1", {"preferred_formality": 0.9, "preferred_response_length": "long"}
        )
        assert adapt.preferred_formality == 0.9
        assert adapt.preferred_response_length == "long"

    def test_get_status(self):
        engine = UserAdaptationEngine()
        engine.record_interaction("u1", "a1")
        engine.record_interaction("u2", "a1")
        status = engine.get_status()
        assert status["total_adaptations"] == 2
        assert status["total_interactions"] == 2


# ---------------------------------------------------------------------------
# SentimentClassifier tests
# ---------------------------------------------------------------------------


class TestSentimentClassifier:
    def test_positive(self):
        c = SentimentClassifier()
        r = c.classify("This is great and amazing!")
        assert r.sentiment == "positive"
        assert r.confidence > 0

    def test_negative(self):
        c = SentimentClassifier()
        r = c.classify("This is terrible and awful")
        assert r.sentiment == "negative"
        assert r.confidence > 0

    def test_neutral(self):
        c = SentimentClassifier()
        r = c.classify("The weather is cloudy today")
        assert r.sentiment == "neutral"

    def test_mixed_positive(self):
        c = SentimentClassifier()
        r = c.classify("great awesome bad")
        assert r.sentiment == "positive"

    def test_mixed_equal(self):
        c = SentimentClassifier()
        r = c.classify("great bad")
        assert r.sentiment == "neutral"

    def test_batch(self):
        c = SentimentClassifier()
        results = c.classify_batch(["great", "terrible", "okay"])
        assert len(results) == 3
        assert results[0].sentiment == "positive"
        assert results[1].sentiment == "negative"
        assert results[2].sentiment == "neutral"


# ---------------------------------------------------------------------------
# BehavioralScoringEngine tests
# ---------------------------------------------------------------------------


class TestBehavioralScoringEngine:
    def test_calculate_no_feedback(self):
        engine = BehavioralScoringEngine()
        adapt = UserAdaptation(
            user_id="u1", avatar_id="a1", interaction_count=5
        )
        score = engine.calculate_score(adapt)
        assert 0.0 <= score <= 1.0

    def test_calculate_with_positive_feedback(self):
        engine = BehavioralScoringEngine()
        adapt = UserAdaptation(
            user_id="u1",
            avatar_id="a1",
            interaction_count=10,
            feedback_history=[{"rating": 5}, {"rating": 4}],
        )
        score = engine.calculate_score(adapt)
        assert score > 0.5

    def test_calculate_with_negative_feedback(self):
        engine = BehavioralScoringEngine()
        adapt = UserAdaptation(
            user_id="u1",
            avatar_id="a1",
            interaction_count=10,
            feedback_history=[{"rating": 1}, {"rating": 2}],
        )
        score = engine.calculate_score(adapt)
        assert score <= 0.5

    def test_update_score(self):
        engine = BehavioralScoringEngine()
        s = engine.update_score("u1", 0.3)
        assert s == 0.8  # default 0.5 + 0.3

    def test_update_score_clamp(self):
        engine = BehavioralScoringEngine()
        s = engine.update_score("u1", 2.0)
        assert s == 1.0

    def test_get_score_default(self):
        engine = BehavioralScoringEngine()
        assert engine.get_score("unknown") == 0.5

    def test_get_status(self):
        engine = BehavioralScoringEngine()
        engine.update_score("u1", 0.1)
        status = engine.get_status()
        assert status["total_users_scored"] == 1


# ---------------------------------------------------------------------------
# AvatarSessionManager tests
# ---------------------------------------------------------------------------


class TestAvatarSessionManager:
    def test_start_session(self):
        mgr = AvatarSessionManager()
        s = mgr.start_session("a1", "u1")
        assert s.active is True
        assert s.avatar_id == "a1"
        assert s.user_id == "u1"

    def test_end_session(self):
        mgr = AvatarSessionManager()
        s = mgr.start_session("a1", "u1")
        ended = mgr.end_session(s.session_id)
        assert ended.active is False
        assert ended.ended_at is not None

    def test_end_session_missing(self):
        mgr = AvatarSessionManager()
        assert mgr.end_session("nonexistent") is None

    def test_get_session(self):
        mgr = AvatarSessionManager()
        s = mgr.start_session("a1", "u1")
        fetched = mgr.get_session(s.session_id)
        assert fetched.session_id == s.session_id

    def test_record_message(self):
        mgr = AvatarSessionManager()
        s = mgr.start_session("a1", "u1")
        updated = mgr.record_message(s.session_id)
        assert updated.message_count == 1
        updated = mgr.record_message(s.session_id)
        assert updated.message_count == 2

    def test_record_message_missing(self):
        mgr = AvatarSessionManager()
        assert mgr.record_message("nonexistent") is None

    def test_add_cost(self):
        mgr = AvatarSessionManager()
        s = mgr.start_session("a1", "u1")
        updated = mgr.add_cost(s.session_id, 0.05)
        assert updated.total_cost_usd == 0.05
        updated = mgr.add_cost(s.session_id, 0.10)
        assert abs(updated.total_cost_usd - 0.15) < 1e-9

    def test_add_cost_missing(self):
        mgr = AvatarSessionManager()
        assert mgr.add_cost("nonexistent", 1.0) is None

    def test_list_active_sessions(self):
        mgr = AvatarSessionManager()
        s1 = mgr.start_session("a1", "u1")
        s2 = mgr.start_session("a2", "u2")
        mgr.end_session(s2.session_id)
        active = mgr.list_active_sessions()
        assert len(active) == 1
        assert active[0].session_id == s1.session_id

    def test_list_active_sessions_by_avatar(self):
        mgr = AvatarSessionManager()
        mgr.start_session("a1", "u1")
        mgr.start_session("a2", "u2")
        active = mgr.list_active_sessions(avatar_id="a1")
        assert len(active) == 1

    def test_get_status(self):
        mgr = AvatarSessionManager()
        mgr.start_session("a1", "u1")
        s2 = mgr.start_session("a1", "u2")
        mgr.end_session(s2.session_id)
        status = mgr.get_status()
        assert status["total_sessions"] == 2
        assert status["active_sessions"] == 1


# ---------------------------------------------------------------------------
# CostLedger tests
# ---------------------------------------------------------------------------


class TestCostLedger:
    def test_record(self):
        ledger = CostLedger()
        entry = ledger.record("a1", "elevenlabs", "tts", 0.05)
        assert entry.cost_usd == 0.05
        assert entry.service == "elevenlabs"

    def test_get_total_cost(self):
        ledger = CostLedger()
        ledger.record("a1", "elevenlabs", "tts", 0.05)
        ledger.record("a1", "heygen", "video", 0.50)
        ledger.record("a2", "elevenlabs", "tts", 0.03)
        assert abs(ledger.get_total_cost() - 0.58) < 1e-9
        assert abs(ledger.get_total_cost(avatar_id="a1") - 0.55) < 1e-9
        assert abs(ledger.get_total_cost(service="elevenlabs") - 0.08) < 1e-9

    def test_get_entries(self):
        ledger = CostLedger()
        ledger.record("a1", "elevenlabs", "tts", 0.05)
        ledger.record("a2", "heygen", "video", 0.50)
        assert len(ledger.get_entries()) == 2
        assert len(ledger.get_entries(avatar_id="a1")) == 1

    def test_get_entries_limit(self):
        ledger = CostLedger()
        for i in range(5):
            ledger.record("a1", "elevenlabs", "tts", 0.01)
        assert len(ledger.get_entries(limit=3)) == 3

    def test_get_cost_summary(self):
        ledger = CostLedger()
        ledger.record("a1", "elevenlabs", "tts", 0.05)
        ledger.record("a1", "heygen", "video", 0.50)
        summary = ledger.get_cost_summary()
        assert summary["entry_count"] == 2
        assert abs(summary["total_cost_usd"] - 0.55) < 1e-9
        assert "elevenlabs" in summary["by_service"]
        assert "heygen" in summary["by_service"]

    def test_get_status(self):
        ledger = CostLedger()
        ledger.record("a1", "elevenlabs", "tts", 0.05)
        status = ledger.get_status()
        assert status["total_entries"] == 1
        assert status["total_cost_usd"] == 0.05


# ---------------------------------------------------------------------------
# ComplianceGuard tests
# ---------------------------------------------------------------------------


class TestComplianceGuard:
    def test_check_content_clean(self):
        guard = ComplianceGuard()
        violations = guard.check_content("a1", "Hello, how are you?")
        assert len(violations) == 0

    def test_check_content_ssn(self):
        guard = ComplianceGuard()
        violations = guard.check_content("a1", "SSN is 123-45-6789")
        assert len(violations) == 1
        assert violations[0].rule == "no_pii_disclosure"

    def test_check_content_credit_card(self):
        guard = ComplianceGuard()
        violations = guard.check_content("a1", "Card: 1234567890123456")
        assert len(violations) == 1
        assert violations[0].severity == "high"

    def test_check_prompt_financial(self):
        guard = ComplianceGuard()
        violations = guard.check_prompt("a1", "Should I invest in crypto?")
        assert any(v.rule == "no_financial_advice" for v in violations)

    def test_check_prompt_medical(self):
        guard = ComplianceGuard()
        violations = guard.check_prompt("a1", "Can you prescribe me medication?")
        assert any(v.rule == "no_medical_advice" for v in violations)

    def test_check_prompt_clean(self):
        guard = ComplianceGuard()
        violations = guard.check_prompt("a1", "What is the weather like?")
        assert len(violations) == 0

    def test_get_violations_filtered(self):
        guard = ComplianceGuard()
        guard.check_content("a1", "SSN is 123-45-6789")
        guard.check_content("a2", "Card: 1234567890123456")
        assert len(guard.get_violations(avatar_id="a1")) == 1
        assert len(guard.get_violations()) == 2

    def test_get_status(self):
        guard = ComplianceGuard()
        guard.check_content("a1", "SSN is 123-45-6789")
        status = guard.get_status()
        assert status["total_violations"] == 1
        assert status["unresolved_violations"] == 1
        assert status["rules_count"] == 5


# ---------------------------------------------------------------------------
# Connector tests
# ---------------------------------------------------------------------------


class TestElevenLabsConnector:
    def test_no_api_key(self):
        c = ElevenLabsConnector()
        assert c.available is False
        result = c.synthesize("hello")
        assert isinstance(result, dict)
        assert result["status"] == "unavailable"

    def test_with_api_key(self):
        c = ElevenLabsConnector(api_key="test-key")
        assert c.available is True

    def test_list_voices(self):
        c = ElevenLabsConnector()
        result = c.list_voices()
        assert isinstance(result, (list, dict))

    def test_get_status(self):
        c = ElevenLabsConnector()
        status = c.get_status()
        assert status["service"] == "elevenlabs"


class TestHeyGenConnector:
    def test_no_api_key(self):
        c = HeyGenConnector()
        assert c.available is False
        result = c.create_video("test script")
        assert result["status"] == "unavailable"

    def test_with_api_key(self):
        c = HeyGenConnector(api_key="test-key")
        assert c.available is True
        result = c.create_video("test script")
        # Real HTTP call will fail without a live server; expect error status
        assert result["status"] in ("processing", "error")

    def test_get_video_status(self):
        c = HeyGenConnector()
        status = c.get_video_status("v1")
        assert status["status"] in ("completed", "unavailable")

    def test_list_avatars(self):
        c = HeyGenConnector()
        result = c.list_avatars()
        assert isinstance(result, (list, dict))

    def test_get_status(self):
        c = HeyGenConnector()
        assert c.get_status()["service"] == "heygen"


class TestTavusConnector:
    def test_no_api_key(self):
        c = TavusConnector()
        assert c.available is False
        assert c.create_replica("test")["status"] == "unavailable"
        assert c.generate_video("r1", "script")["status"] == "unavailable"

    def test_with_api_key(self):
        c = TavusConnector(api_key="test-key")
        assert c.available is True
        # Real HTTP call will fail without a live server; expect error status
        assert c.create_replica("test")["status"] in ("training", "error")
        assert c.generate_video("r1", "script")["status"] in ("processing", "error")

    def test_list_replicas(self):
        c = TavusConnector()
        result = c.list_replicas()
        assert isinstance(result, (list, dict))

    def test_get_status(self):
        c = TavusConnector()
        assert c.get_status()["service"] == "tavus"


class TestVapiConnector:
    def test_no_api_key(self):
        c = VapiConnector()
        assert c.available is False
        assert c.start_call("+1234567890")["status"] == "unavailable"

    def test_with_api_key(self):
        c = VapiConnector(api_key="test-key")
        assert c.available is True
        # Real HTTP call will fail without a live server; expect error status
        assert c.start_call("+1234567890")["status"] in ("ringing", "error")

    def test_end_call(self):
        c = VapiConnector()
        result = c.end_call("c1")
        assert result["status"] in ("ended", "unavailable")

    def test_get_call_status(self):
        c = VapiConnector()
        result = c.get_call_status("c1")
        assert result["status"] in ("active", "unavailable")

    def test_list_assistants(self):
        c = VapiConnector()
        result = c.list_assistants()
        assert isinstance(result, (list, dict))

    def test_get_status(self):
        c = VapiConnector()
        assert c.get_status()["service"] == "vapi"


# ---------------------------------------------------------------------------
# Thread safety tests
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_registry_concurrent_register(self):
        reg = AvatarRegistry()
        results = []

        def register_avatar(i):
            p = AvatarProfile(avatar_id=f"a{i}", name=f"Avatar{i}")
            results.append(reg.register(p))

        threads = [threading.Thread(target=register_avatar, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 20
        assert len(reg.list_avatars()) == 20

    def test_session_manager_concurrent(self):
        mgr = AvatarSessionManager()
        sessions = []

        def create_session(i):
            s = mgr.start_session("a1", f"u{i}")
            sessions.append(s.session_id)

        threads = [threading.Thread(target=create_session, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(mgr.list_active_sessions()) == 20

    def test_cost_ledger_concurrent(self):
        ledger = CostLedger()

        def record_cost(i):
            ledger.record("a1", "elevenlabs", "tts", 0.01)

        threads = [threading.Thread(target=record_cost, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert abs(ledger.get_total_cost() - 0.20) < 1e-9

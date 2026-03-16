"""Tests for the Murphy System Matrix Bridge package.

Covers:
- MatrixClient (no real homeserver needed — nio is optional)
- RoomRegistry
- CommandRouter
- EventBridge
- BotPersonas
- SpaceManager
- HITLMatrixAdapter
- WebhookReceiver
- MODULE_MANIFEST
- startup (import-level only)
"""

from __future__ import annotations

import asyncio

import pytest



# ---------------------------------------------------------------------------
# MatrixClient
# ---------------------------------------------------------------------------

class TestMatrixClient:
    def test_import(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        assert MatrixClient is not None

    def test_init_defaults(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        c = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        assert c.homeserver == "http://localhost:8008"
        assert c.user_id == "@test:localhost"
        assert c.is_connected() is False

    def test_trailing_slash_stripped(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        c = MatrixClient(homeserver="http://localhost:8008/")
        assert c.homeserver == "http://localhost:8008"

    def test_circuit_breaker_initial_state(self):
        from src.matrix_bridge.matrix_client import _CircuitBreaker, _CircuitState
        cb = _CircuitBreaker(threshold=3, timeout=10.0)
        assert cb.is_open is False
        assert cb._state == _CircuitState.CLOSED

    def test_circuit_breaker_opens_after_threshold(self):
        from src.matrix_bridge.matrix_client import _CircuitBreaker, _CircuitState
        cb = _CircuitBreaker(threshold=3, timeout=10.0)
        for _ in range(3):
            cb.record_failure()
        assert cb._state == _CircuitState.OPEN
        assert cb.is_open is True

    def test_circuit_breaker_resets_on_success(self):
        from src.matrix_bridge.matrix_client import _CircuitBreaker, _CircuitState
        cb = _CircuitBreaker(threshold=3, timeout=10.0)
        for _ in range(3):
            cb.record_failure()
        cb.record_success()
        assert cb._state == _CircuitState.CLOSED
        assert cb._failures == 0

    def test_connect_without_nio_returns_false(self):
        """connect() should return False gracefully when matrix-nio is absent."""
        from src.matrix_bridge import matrix_client as mc
        original = mc._NIO_AVAILABLE
        mc._NIO_AVAILABLE = False
        try:
            c = mc.MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
            result = asyncio.get_event_loop().run_until_complete(c.connect())
            assert result is False
        finally:
            mc._NIO_AVAILABLE = original

    def test_connect_without_user_id_returns_false(self):
        from src.matrix_bridge import matrix_client as mc
        original = mc._NIO_AVAILABLE
        mc._NIO_AVAILABLE = False
        try:
            c = mc.MatrixClient(homeserver="http://localhost:8008", user_id="")
            result = asyncio.get_event_loop().run_until_complete(c.connect())
            assert result is False
        finally:
            mc._NIO_AVAILABLE = original

    def test_send_text_returns_false_when_not_connected(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        c = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        result = asyncio.get_event_loop().run_until_complete(
            c.send_text("!roomid:localhost", "hello")
        )
        assert result is False

    def test_add_event_callback(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        c = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")

        async def cb(room, event):
            pass

        c.add_event_callback(cb)
        assert cb in c._event_callbacks


# ---------------------------------------------------------------------------
# RoomRegistry
# ---------------------------------------------------------------------------

class TestRoomRegistry:
    def _make_registry(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        return RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)

    def test_import(self):
        from src.matrix_bridge.room_registry import RoomRegistry, SUBSYSTEM_ROOMS
        assert RoomRegistry is not None
        assert len(SUBSYSTEM_ROOMS) > 200

    def test_all_subsystems_populated(self):
        registry = self._make_registry()
        subsystems = registry.all_subsystems()
        assert len(subsystems) > 200

    def test_get_room_known(self):
        registry = self._make_registry()
        info = registry.get_room("security-plane")
        assert info is not None
        assert info.subsystem == "security-plane"
        assert info.category == "security"
        assert info.encrypted is True

    def test_get_room_unknown(self):
        registry = self._make_registry()
        assert registry.get_room("nonexistent-room") is None

    def test_full_alias_format(self):
        registry = self._make_registry()
        info = registry.get_room("confidence-engine")
        assert info is not None
        assert info.full_alias == "#murphy-confidence-engine:localhost"

    def test_categories_non_empty(self):
        registry = self._make_registry()
        cats = registry.categories()
        assert len(cats) > 10
        assert "security" in cats
        assert "core-engines" in cats

    def test_subsystems_by_category(self):
        registry = self._make_registry()
        security_rooms = registry.subsystems_by_category("security")
        assert "security-plane" in security_rooms
        assert "secure-key-manager" in security_rooms

    def test_set_room_id(self):
        registry = self._make_registry()
        registry.set_room_id("confidence-engine", "!roomid123:localhost")
        assert registry.get_room_id("confidence-engine") == "!roomid123:localhost"

    def test_summary_structure(self):
        registry = self._make_registry()
        summary = registry.summary()
        assert "security-plane" in summary
        assert summary["security-plane"]["encrypted"] is True

    def test_ensure_all_rooms_skipped_when_auto_create_false(self):
        """ensure_all_rooms should not call create_room when auto_create=False."""
        registry = self._make_registry()
        result = asyncio.get_event_loop().run_until_complete(registry.ensure_all_rooms())
        # All room IDs should be None (no creation attempted)
        assert all(v is None for v in result.values())

    def test_well_known_system_rooms(self):
        from src.matrix_bridge.room_registry import SUBSYSTEM_ROOMS
        for key in ("system-status", "security-alerts", "hitl-approvals", "ci-cd", "finance"):
            assert key in SUBSYSTEM_ROOMS, f"Missing well-known room: {key}"


# ---------------------------------------------------------------------------
# CommandRouter
# ---------------------------------------------------------------------------

class TestCommandRouter:
    def _make_router(self):
        from src.matrix_bridge.command_router import CommandRouter
        return CommandRouter(prefix="!murphy")

    def test_import(self):
        from src.matrix_bridge.command_router import (
            CommandRouter, CommandDef, PERM_VIEWER, PERM_OPERATOR, PERM_ADMIN
        )
        assert PERM_VIEWER == 0
        assert PERM_OPERATOR == 50
        assert PERM_ADMIN == 100

    def test_non_command_returns_none(self):
        router = self._make_router()
        result = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "hello world")
        )
        assert result is None

    def test_help_returns_pair(self):
        router = self._make_router()
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy help")
        )
        assert "Command Reference" in html
        assert "!murphy" in plain

    def test_ping_command(self):
        router = self._make_router()
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy ping")
        )
        assert "Pong" in plain

    def test_whoami_command(self):
        router = self._make_router()
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy whoami")
        )
        assert "@user:localhost" in plain
        assert "operator" in plain.lower()

    def test_commands_command(self):
        router = self._make_router()
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy commands")
        )
        assert "!murphy" in plain

    def test_unknown_command_error(self):
        router = self._make_router()
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy zzznonsense")
        )
        assert "Error" in plain or "Unknown" in plain

    def test_subsystem_handler_called(self):
        router = self._make_router()
        calls = []

        async def handler(subsystem, command, args):
            calls.append((subsystem, command, args))
            return ("ok", "<b>ok</b>")

        router.set_subsystem_handler(handler)
        asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy security scan")
        )
        assert calls == [("security", "scan", [])]

    def test_custom_command_registration(self):
        from src.matrix_bridge.command_router import CommandDef, PERM_VIEWER
        router = self._make_router()

        async def my_handler(user_id, args):
            return ("custom result", "<b>custom result</b>")

        router.register_command(CommandDef(
            name="custom",
            handler=my_handler,
            description="A custom command",
            min_permission=PERM_VIEWER,
        ))
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy custom")
        )
        assert plain == "custom result"

    def test_prefix_case_insensitive(self):
        router = self._make_router()
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!MURPHY ping")
        )
        assert "Pong" in plain

    def test_permission_denied_for_admin_command(self):
        from src.matrix_bridge.command_router import CommandDef, PERM_ADMIN, PERM_VIEWER
        router = self._make_router()

        async def admin_only(user_id, args):
            return ("secret", "<b>secret</b>")

        router.register_command(CommandDef(
            name="secret",
            handler=admin_only,
            description="Admin only",
            min_permission=PERM_ADMIN,
        ))

        async def viewer_perm(user_id):
            return PERM_VIEWER

        router._permission_resolver = viewer_perm
        plain, html = asyncio.get_event_loop().run_until_complete(
            router.dispatch("@user:localhost", "!roomid:localhost", "!murphy secret")
        )
        assert "denied" in plain.lower() or "permission" in plain.lower()


# ---------------------------------------------------------------------------
# EventBridge
# ---------------------------------------------------------------------------

class TestEventBridge:
    def _make_bridge(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        from src.matrix_bridge.event_bridge import EventBridge
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        registry = RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)
        return EventBridge(client=client, registry=registry)

    def test_import(self):
        from src.matrix_bridge.event_bridge import EventBridge, BridgedEvent, Severity
        assert EventBridge is not None

    def test_start_without_backbone(self):
        bridge = self._make_bridge()
        bridge.start()  # should not raise
        bridge.stop()

    def test_resolve_rooms_gate_blocked(self):
        from src.matrix_bridge.event_bridge import BridgedEvent
        bridge = self._make_bridge()
        event = BridgedEvent(
            event_type="gate_blocked",
            source="gate_synthesis",
            payload={"reason": "policy violation"},
            severity="error",
        )
        rooms = bridge._resolve_rooms(event)
        assert "gate-synthesis" in rooms
        assert "security-alerts" in rooms

    def test_resolve_rooms_system_health(self):
        from src.matrix_bridge.event_bridge import BridgedEvent
        bridge = self._make_bridge()
        event = BridgedEvent(
            event_type="system_health",
            source="health_monitor",
            payload={"status": "ok"},
        )
        rooms = bridge._resolve_rooms(event)
        assert "health-monitor" in rooms
        assert "system-status" in rooms

    def test_resolve_rooms_unknown_event(self):
        from src.matrix_bridge.event_bridge import BridgedEvent
        bridge = self._make_bridge()
        event = BridgedEvent(
            event_type="some_unknown_event",
            source="unknown",
            payload={},
        )
        rooms = bridge._resolve_rooms(event)
        assert rooms == []

    def test_format_event(self):
        from src.matrix_bridge.event_bridge import BridgedEvent
        bridge = self._make_bridge()
        event = BridgedEvent(
            event_type="alert_fired",
            source="alert_rules_engine",
            payload={"rule": "high_cpu", "value": 95},
            severity="warning",
            timestamp="2026-01-01T00:00:00Z",
        )
        plain, html = bridge._format(event)
        assert "alert_fired" in plain
        assert "⚠️" in plain
        assert "alert_fired" in html
        assert "high_cpu" in plain

    def test_custom_router(self):
        from src.matrix_bridge.event_bridge import BridgedEvent
        bridge = self._make_bridge()

        def my_router(event: BridgedEvent):
            if event.event_type == "custom_event":
                return "monitoring"
            return None

        bridge.add_router(my_router)
        event = BridgedEvent(event_type="custom_event", source="test", payload={})
        rooms = bridge._resolve_rooms(event)
        assert "monitoring" in rooms

    def test_dispatch_no_room_id(self):
        """dispatch() should not raise when room IDs are not populated."""
        from src.matrix_bridge.event_bridge import BridgedEvent
        bridge = self._make_bridge()
        event = BridgedEvent(
            event_type="system_health",
            source="health_monitor",
            payload={"status": "ok"},
        )
        # No room IDs populated → should run silently
        asyncio.get_event_loop().run_until_complete(bridge.dispatch(event))


# ---------------------------------------------------------------------------
# BotPersonas
# ---------------------------------------------------------------------------

class TestBotPersonas:
    def test_import(self):
        from src.matrix_bridge.bot_personas import BotPersonas, Persona
        assert BotPersonas is not None

    def test_default_personas_loaded(self):
        from src.matrix_bridge.bot_personas import BotPersonas
        personas = BotPersonas()
        names = personas.names()
        for expected in [
            "TriageBot", "SecurityBot", "EngineeringBot", "LibrarianBot",
            "CADBot", "KeyManagerBot", "ComplianceBot", "MonitoringBot",
            "ExecutionBot", "FinanceBot", "OnboardingBot",
        ]:
            assert expected in names, f"Missing persona: {expected}"

    def test_get_existing_persona(self):
        from src.matrix_bridge.bot_personas import BotPersonas
        personas = BotPersonas()
        p = personas.get("SecurityBot")
        assert p is not None
        assert "security-plane" in p.subsystems

    def test_get_missing_persona(self):
        from src.matrix_bridge.bot_personas import BotPersonas
        personas = BotPersonas()
        assert personas.get("NonExistent") is None

    def test_register_custom_persona(self):
        from src.matrix_bridge.bot_personas import BotPersonas, Persona
        personas = BotPersonas()
        p = Persona(name="TestBot", description="A test bot", subsystems=["test-room"])
        personas.register(p)
        assert personas.get("TestBot") is p

    def test_persona_for_room(self):
        from src.matrix_bridge.bot_personas import BotPersonas
        personas = BotPersonas()
        p = personas.persona_for_room("security-plane")
        assert p is not None
        assert p.name == "SecurityBot"

    def test_persona_for_subsystem(self):
        from src.matrix_bridge.bot_personas import BotPersonas
        personas = BotPersonas()
        # credential-profile-system is only in KeyManagerBot's subsystems list
        p = personas.persona_for_subsystem("credential-profile-system")
        assert p is not None
        assert p.name == "KeyManagerBot"

    def test_all_personas_have_commands(self):
        from src.matrix_bridge.bot_personas import BotPersonas
        personas = BotPersonas()
        for p in personas.all():
            assert len(p.commands) > 0, f"Persona {p.name} has no commands"


# ---------------------------------------------------------------------------
# SpaceManager
# ---------------------------------------------------------------------------

class TestSpaceManager:
    def _make_space_manager(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        from src.matrix_bridge.space_manager import SpaceManager
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        registry = RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)
        return SpaceManager(client=client, registry=registry, space_name="Test Space")

    def test_import(self):
        from src.matrix_bridge.space_manager import SpaceManager, CATEGORY_DISPLAY
        assert SpaceManager is not None
        assert len(CATEGORY_DISPLAY) > 10

    def test_category_display_covers_all_categories(self):
        from src.matrix_bridge.room_registry import SUBSYSTEM_ROOMS
        from src.matrix_bridge.space_manager import CATEGORY_DISPLAY
        categories = {spec[0] for spec in SUBSYSTEM_ROOMS.values()}
        for cat in categories:
            assert cat in CATEGORY_DISPLAY, f"Category {cat} has no display name"

    def test_summary_structure(self):
        mgr = self._make_space_manager()
        summary = mgr.summary()
        assert "top_level" in summary
        assert "sub_spaces" in summary

    def test_power_level_constants(self):
        from src.matrix_bridge.space_manager import PL_BOT, PL_ADMIN, PL_USER
        assert PL_BOT == 100
        assert PL_ADMIN == 50
        assert PL_USER == 0


# ---------------------------------------------------------------------------
# HITLMatrixAdapter
# ---------------------------------------------------------------------------

class TestHITLMatrixAdapter:
    def _make_adapter(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        from src.matrix_bridge.hitl_matrix_adapter import HITLMatrixAdapter
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        registry = RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)
        return HITLMatrixAdapter(client=client, registry=registry)

    def test_import(self):
        from src.matrix_bridge.hitl_matrix_adapter import HITLMatrixAdapter, HITLItem
        assert HITLMatrixAdapter is not None

    def test_format_intervention_approve_message(self):
        from src.matrix_bridge.hitl_matrix_adapter import HITLMatrixAdapter
        plain, html = HITLMatrixAdapter._format_intervention(
            "hitl-123",
            {"title": "Deploy to production", "severity": "high", "requester": "exec-engine"},
        )
        assert "hitl-123" in plain
        assert "Deploy to production" in plain
        assert "APPROVE" in plain
        assert "hitl-123" in html

    def test_handle_reaction_approve(self):
        adapter = self._make_adapter()
        from src.matrix_bridge.hitl_matrix_adapter import HITLItem

        # Inject a pending item
        adapter._pending["test-id"] = HITLItem(intervention_id="test-id")
        adapter._event_to_id["!evt1:localhost"] = "test-id"

        result = asyncio.get_event_loop().run_until_complete(
            adapter.handle_reaction("@user:localhost", "!evt1:localhost", "✅")
        )
        assert result == "test-id"
        assert adapter._pending["test-id"].resolved is True

    def test_handle_reaction_reject(self):
        adapter = self._make_adapter()
        from src.matrix_bridge.hitl_matrix_adapter import HITLItem
        adapter._pending["test-id2"] = HITLItem(intervention_id="test-id2")
        adapter._event_to_id["!evt2:localhost"] = "test-id2"

        result = asyncio.get_event_loop().run_until_complete(
            adapter.handle_reaction("@user:localhost", "!evt2:localhost", "❌")
        )
        assert result == "test-id2"

    def test_handle_reaction_unknown_event(self):
        adapter = self._make_adapter()
        result = asyncio.get_event_loop().run_until_complete(
            adapter.handle_reaction("@user:localhost", "!unknownevt:localhost", "✅")
        )
        assert result is None

    def test_handle_command_response_invalid_decision(self):
        adapter = self._make_adapter()
        result = asyncio.get_event_loop().run_until_complete(
            adapter.handle_command_response("x", "@user:localhost", "maybe")
        )
        assert result is False

    def test_stop(self):
        adapter = self._make_adapter()
        adapter._running = True
        adapter.stop()
        assert adapter._running is False


# ---------------------------------------------------------------------------
# WebhookReceiver
# ---------------------------------------------------------------------------

class TestWebhookReceiver:
    def test_import(self):
        from src.matrix_bridge.webhook_receiver import WebhookReceiver
        assert WebhookReceiver is not None

    def test_format_webhook_github(self):
        from src.matrix_bridge.webhook_receiver import WebhookReceiver
        plain, html = WebhookReceiver._format_webhook(
            "github", "push", {"repository": "murphy", "pusher": "admin"}
        )
        assert "GITHUB" in plain
        assert "push" in plain
        assert "🐙" in plain

    def test_format_webhook_stripe(self):
        from src.matrix_bridge.webhook_receiver import WebhookReceiver
        plain, html = WebhookReceiver._format_webhook(
            "stripe", "payment_intent.succeeded", {"amount": 1000}
        )
        assert "STRIPE" in plain
        assert "💳" in plain

    def test_add_route(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        from src.matrix_bridge.webhook_receiver import WebhookReceiver
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        registry = RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)
        receiver = WebhookReceiver(client=client, registry=registry)
        receiver.add_route("custom-hook", "monitoring")
        assert receiver._custom_routes["custom-hook"] == "monitoring"

    def test_github_sig_verification_invalid(self):
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        from src.matrix_bridge.webhook_receiver import WebhookReceiver
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        registry = RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)
        receiver = WebhookReceiver(
            client=client, registry=registry, github_secret="secret123"
        )
        assert receiver._verify_github_sig(b"payload", "sha256=wrongsig") is False

    def test_github_sig_verification_valid(self):
        import hashlib
        import hmac as _hmac
        from src.matrix_bridge.matrix_client import MatrixClient
        from src.matrix_bridge.room_registry import RoomRegistry
        from src.matrix_bridge.webhook_receiver import WebhookReceiver
        client = MatrixClient(homeserver="http://localhost:8008", user_id="@test:localhost")
        registry = RoomRegistry(client=client, homeserver_domain="localhost", auto_create=False)
        receiver = WebhookReceiver(
            client=client, registry=registry, github_secret="secret123"
        )
        body = b"payload body"
        expected = _hmac.new(b"secret123", body, hashlib.sha256).hexdigest()
        assert receiver._verify_github_sig(body, f"sha256={expected}") is True


# ---------------------------------------------------------------------------
# MODULE_MANIFEST
# ---------------------------------------------------------------------------

class TestModuleManifest:
    def test_import(self):
        from src.matrix_bridge.module_manifest import MODULE_MANIFEST, ModuleEntry
        assert len(MODULE_MANIFEST) > 150

    def test_all_entries_have_required_fields(self):
        from src.matrix_bridge.module_manifest import MODULE_MANIFEST
        for entry in MODULE_MANIFEST:
            assert entry.module, f"Entry missing module: {entry}"
            assert entry.room, f"Entry missing room: {entry.module}"
            assert entry.persona, f"Entry missing persona: {entry.module}"

    def test_all_rooms_exist_in_registry(self):
        from src.matrix_bridge.module_manifest import MODULE_MANIFEST
        from src.matrix_bridge.room_registry import SUBSYSTEM_ROOMS
        for entry in MODULE_MANIFEST:
            assert entry.room in SUBSYSTEM_ROOMS, (
                f"Module {entry.module} references unknown room: {entry.room}"
            )

    def test_manifest_by_module_index(self):
        from src.matrix_bridge.module_manifest import manifest_by_module, MODULE_MANIFEST
        index = manifest_by_module()
        assert len(index) > 0
        assert "confidence_engine" in index or "system_librarian" in index

    def test_manifest_by_room_index(self):
        from src.matrix_bridge.module_manifest import manifest_by_room
        by_room = manifest_by_room()
        assert "security-plane" in by_room
        assert len(by_room["security-plane"]) > 0

    def test_manifest_by_persona_index(self):
        from src.matrix_bridge.module_manifest import manifest_by_persona
        by_persona = manifest_by_persona()
        assert "SecurityBot" in by_persona
        assert "MonitoringBot" in by_persona
        assert "ComplianceBot" in by_persona

    def test_security_modules_have_security_persona(self):
        from src.matrix_bridge.module_manifest import MODULE_MANIFEST
        security_entries = [e for e in MODULE_MANIFEST if e.room in (
            "security-plane", "security-audit-scanner", "secure-key-manager"
        )]
        assert len(security_entries) > 0
        for e in security_entries:
            assert e.persona in ("SecurityBot", "KeyManagerBot"), (
                f"Expected security persona for {e.module}, got {e.persona}"
            )

    def test_no_duplicate_modules(self):
        from src.matrix_bridge.module_manifest import MODULE_MANIFEST
        modules = [e.module for e in MODULE_MANIFEST]
        seen = set()
        duplicates = []
        for m in modules:
            if m in seen:
                duplicates.append(m)
            seen.add(m)
        assert not duplicates, f"Duplicate module entries: {duplicates}"

    def test_known_modules_present(self):
        from src.matrix_bridge.module_manifest import manifest_by_module
        index = manifest_by_module()
        required = [
            "confidence_engine", "execution_engine", "learning_engine",
            "security_plane", "compliance_engine", "health_monitor",
            "trading_bot_engine", "system_librarian",
        ]
        for mod in required:
            assert mod in index, f"Missing required module in manifest: {mod}"


# ---------------------------------------------------------------------------
# Package-level imports (__init__)
# ---------------------------------------------------------------------------

class TestPackageInit:
    def test_all_exports_importable(self):
        from src.matrix_bridge import (
            MatrixClient,
            RoomRegistry,
            SUBSYSTEM_ROOMS,
            CommandRouter,
            EventBridge,
            BotPersonas,
            Persona,
            SpaceManager,
            HITLMatrixAdapter,
            WebhookReceiver,
            MODULE_MANIFEST,
        )
        assert MatrixClient is not None
        assert RoomRegistry is not None
        assert SUBSYSTEM_ROOMS is not None
        assert CommandRouter is not None
        assert EventBridge is not None
        assert BotPersonas is not None
        assert Persona is not None
        assert SpaceManager is not None
        assert HITLMatrixAdapter is not None
        assert WebhookReceiver is not None
        assert MODULE_MANIFEST is not None


# ---------------------------------------------------------------------------
# Startup (import only)
# ---------------------------------------------------------------------------

class TestStartup:
    def test_import(self):
        from src.matrix_bridge import startup as startup_module
        assert startup_module is not None

    def test_startup_function_importable(self):
        from src.matrix_bridge.startup import startup, run_forever
        assert callable(startup)
        assert callable(run_forever)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

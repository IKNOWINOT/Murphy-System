#!/usr/bin/env python3
"""
murphy_dbus_service.py — Murphy System D-Bus Bridge

Bridges the Murphy REST API (FastAPI on localhost:8000) to the Linux
system D-Bus, exposing five interfaces:

    org.murphy.ControlPlane  — engine lifecycle management
    org.murphy.Confidence    — live confidence metrics
    org.murphy.HITL          — human-in-the-loop approval workflow
    org.murphy.Swarm         — autonomous agent swarm management
    org.murphy.Forge         — natural-language-to-deliverable builds

Uses dbus-next (asyncio-native) and aiohttp for non-blocking HTTP.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1

Installed to: /usr/lib/murphy/murphy-dbus-service

---------------------------------------------------------------------------
Error-code registry
---------------------------------------------------------------------------
MURPHY-DBUS-ERR-001  Failed to write confidence to /murphy/live/confidence
MURPHY-DBUS-ERR-002  Confidence polling cycle encountered an error
MURPHY-DBUS-ERR-003  Main event loop interrupted by KeyboardInterrupt
---------------------------------------------------------------------------
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, dbus_property, method, signal as dbus_signal

import aiohttp

# ── configuration ──────────────────────────────────────────────────
MURPHY_API = os.environ.get("MURPHY_API_URL", "http://127.0.0.1:8000")
BUS_NAME = "org.murphy.System"
OBJECT_PATH = "/org/murphy/System"
CONFIDENCE_POLL_INTERVAL = float(os.environ.get("MURPHY_CONFIDENCE_POLL_INTERVAL", "5"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [murphy-dbus] %(levelname)s %(message)s",
)
logger = logging.getLogger("murphy-dbus")


# ── helpers ────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, path: str) -> dict:
    """GET *path* from the Murphy API and return the parsed JSON body."""
    async with session.get(f"{MURPHY_API}{path}") as resp:
        resp.raise_for_status()
        return await resp.json()


async def _post(session: aiohttp.ClientSession, path: str,
                payload: dict | None = None) -> dict:
    """POST *payload* as JSON to *path* and return the parsed response."""
    async with session.post(f"{MURPHY_API}{path}", json=payload or {}) as resp:
        resp.raise_for_status()
        return await resp.json()


# ── D-Bus interface: ControlPlane ──────────────────────────────────

class ControlPlane(ServiceInterface):
    """Engine lifecycle management."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__("org.murphy.ControlPlane")
        self._session = session

    @method()
    async def StartEngine(self, engine_name: "s"):  # noqa: N802
        logger.info("ControlPlane.StartEngine(%s)", engine_name)
        await _post(self._session, "/api/scheduler/start",
                    {"engine": engine_name})

    @method()
    async def StopEngine(self, engine_name: "s"):  # noqa: N802
        logger.info("ControlPlane.StopEngine(%s)", engine_name)
        await _post(self._session, "/api/scheduler/stop",
                    {"engine": engine_name})

    @method()
    async def ListEngines(self) -> "as":  # noqa: N802
        data = await _get(self._session, "/api/modules")
        modules = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(modules, list):
            return [str(m.get("name", m) if isinstance(m, dict) else m)
                    for m in modules]
        return []

    @method()
    async def ExecuteTask(self, json_payload: "s") -> "s":  # noqa: N802
        payload = json.loads(json_payload)
        result = await _post(self._session, "/api/swarm/execute", payload)
        return json.dumps(result)


# ── D-Bus interface: Confidence ────────────────────────────────────

class Confidence(ServiceInterface):
    """Live confidence metrics with property polling."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__("org.murphy.Confidence")
        self._session = session
        self._score: float = 0.0
        self._murphy_index: float = 0.0
        self._gate_satisfaction: float = 0.0

    # ── properties ──
    @dbus_property()
    def Score(self) -> "d":  # noqa: N802
        return self._score

    @dbus_property()
    def MurphyIndex(self) -> "d":  # noqa: N802
        return self._murphy_index

    @dbus_property()
    def GateSatisfaction(self) -> "d":  # noqa: N802
        return self._gate_satisfaction

    # ── signal ──
    @dbus_signal()
    def ConfidenceChanged(self, new_score: "d") -> None:  # noqa: N802
        pass

    # ── background polling ──
    async def poll_loop(self) -> None:
        """Periodically fetch confidence from the REST API and emit a
        signal when the score changes."""
        while True:
            try:
                data = await _get(self._session,
                                  "/api/compute-plane/statistics")
                payload = data.get("data", data)
                new_score = float(payload.get("confidence", payload.get("score", 0.0)))
                new_index = float(payload.get("murphy_index", 0.0))
                new_gate = float(payload.get("gate_satisfaction", 0.0))

                if new_score != self._score:
                    self._score = new_score
                    self.ConfidenceChanged(new_score)
                    self.emit_properties_changed({
                        "Score": Variant("d", new_score),
                    })
                self._murphy_index = new_index
                self._gate_satisfaction = new_gate

                # Write to well-known path for Polkit rules
                try:
                    os.makedirs("/murphy/live", exist_ok=True)
                    with open("/murphy/live/confidence", "w") as f:
                        f.write(f"{self._score:.4f}\n")
                except OSError as exc:  # MURPHY-DBUS-ERR-001
                    logger.debug("MURPHY-DBUS-ERR-001: cannot write confidence file: %s", exc)
            except Exception as exc:  # MURPHY-DBUS-ERR-002
                logger.debug("MURPHY-DBUS-ERR-002: Confidence poll error: %s", exc)

            await asyncio.sleep(CONFIDENCE_POLL_INTERVAL)


# ── D-Bus interface: HITL ──────────────────────────────────────────

class HITL(ServiceInterface):
    """Human-in-the-loop approval workflow."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__("org.murphy.HITL")
        self._session = session

    @method()
    async def RequestApproval(self, task_json: "s") -> "s":  # noqa: N802
        payload = json.loads(task_json)
        result = await _post(self._session,
                             "/api/hitl/interventions/pending",
                             payload)
        data = result.get("data", result)
        request_id = str(data.get("id", data.get("request_id", "")))
        if request_id:
            desc = str(data.get("description", ""))
            self.ApprovalRequired(request_id, desc)
        return request_id

    @method()
    async def Approve(self, request_id: "s"):  # noqa: N802
        logger.info("HITL.Approve(%s)", request_id)
        await _post(
            self._session,
            f"/api/hitl/interventions/{request_id}/respond",
            {"decision": "approve"},
        )

    @method()
    async def Deny(self, request_id: "s"):  # noqa: N802
        logger.info("HITL.Deny(%s)", request_id)
        await _post(
            self._session,
            f"/api/hitl/interventions/{request_id}/respond",
            {"decision": "deny"},
        )

    @method()
    async def ListPending(self) -> "as":  # noqa: N802
        data = await _get(self._session, "/api/hitl/interventions/pending")
        items = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(items, list):
            return [str(i.get("id", i) if isinstance(i, dict) else i)
                    for i in items]
        return []

    @dbus_signal()
    def ApprovalRequired(self, request_id: "s", description: "s") -> None:  # noqa: N802
        pass


# ── D-Bus interface: Swarm ─────────────────────────────────────────

class Swarm(ServiceInterface):
    """Autonomous agent swarm management."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__("org.murphy.Swarm")
        self._session = session
        self._active_count: int = 0
        self._agent_list: list[str] = []

    @dbus_property()
    def ActiveAgentCount(self) -> "u":  # noqa: N802
        return self._active_count

    @dbus_property()
    def AgentList(self) -> "as":  # noqa: N802
        return list(self._agent_list)

    @method()
    async def SpawnAgent(self, role: "s") -> "s":  # noqa: N802
        logger.info("Swarm.SpawnAgent(%s)", role)
        result = await _post(self._session, "/module-instances/spawn",
                             {"role": role})
        data = result.get("data", result)
        agent_id = str(data.get("id", data.get("agent_id", "")))
        if agent_id:
            self._agent_list.append(agent_id)
            self._active_count = len(self._agent_list)
            self.AgentSpawned(agent_id, role)
            self.emit_properties_changed({
                "ActiveAgentCount": Variant("u", self._active_count),
                "AgentList": Variant("as", list(self._agent_list)),
            })
        return agent_id

    @method()
    async def TerminateAgent(self, agent_id: "s"):  # noqa: N802
        logger.info("Swarm.TerminateAgent(%s)", agent_id)
        await _post(self._session,
                    f"/module-instances/{agent_id}/despawn")
        if agent_id in self._agent_list:
            self._agent_list.remove(agent_id)
            self._active_count = len(self._agent_list)
            self.AgentCompleted(agent_id)
            self.emit_properties_changed({
                "ActiveAgentCount": Variant("u", self._active_count),
                "AgentList": Variant("as", list(self._agent_list)),
            })

    @dbus_signal()
    def AgentSpawned(self, agent_id: "s", role: "s") -> None:  # noqa: N802
        pass

    @dbus_signal()
    def AgentCompleted(self, agent_id: "s") -> None:  # noqa: N802
        pass


# ── D-Bus interface: Forge ─────────────────────────────────────────

class Forge(ServiceInterface):
    """Natural-language-to-deliverable build pipeline."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__("org.murphy.Forge")
        self._session = session

    @method()
    async def Build(self, natural_language_query: "s") -> "s":  # noqa: N802
        logger.info("Forge.Build(%r)", natural_language_query[:80])
        self.BuildProgress("submitted", 0.0)

        result = await _post(self._session,
                             "/api/production/proposals",
                             {"query": natural_language_query})
        self.BuildProgress("compiling", 0.5)

        data = result.get("data", result)
        self.BuildProgress("complete", 1.0)
        return json.dumps(data)

    @dbus_signal()
    def BuildProgress(self, stage: "s", progress: "d") -> None:  # noqa: N802
        pass


# ── main ───────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Starting Murphy D-Bus bridge → %s", MURPHY_API)

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    async with aiohttp.ClientSession() as session:
        ctrl = ControlPlane(session)
        conf = Confidence(session)
        hitl = HITL(session)
        swarm = Swarm(session)
        forge = Forge(session)

        bus.export(OBJECT_PATH, ctrl)
        bus.export(OBJECT_PATH, conf)
        bus.export(OBJECT_PATH, hitl)
        bus.export(OBJECT_PATH, swarm)
        bus.export(OBJECT_PATH, forge)

        await bus.request_name(BUS_NAME)
        logger.info("Acquired bus name %s at %s", BUS_NAME, OBJECT_PATH)

        # Start background confidence polling
        poll_task = asyncio.create_task(conf.poll_loop())

        # Graceful shutdown
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _shutdown(sig: int) -> None:
            logger.info("Received signal %d, shutting down", sig)
            stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _shutdown, sig)

        await stop_event.wait()
        poll_task.cancel()
        bus.disconnect()
        logger.info("Murphy D-Bus bridge stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # MURPHY-DBUS-ERR-003
        logger.debug("MURPHY-DBUS-ERR-003: interrupted by KeyboardInterrupt")
    sys.exit(0)

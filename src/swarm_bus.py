"""
PATCH-170b — src/swarm_bus.py
Murphy System — Redis Pub/Sub Signal Bus

Enables true parallel multi-agent operation:
  - UNISON:   broadcast signal → all agents respond simultaneously
  - TANDEM:   agent A output → triggers agent B input (pipeline)
  - SEPARATE: each agent listens only on its domain channel
  - PLANNING: Rosetta decomposes task → sub-signals → each agent's channel

Architecture:
  Channels:
    murphy:signals:{domain}   — domain-specific (exec_admin, prod_ops, etc.)
    murphy:signals:broadcast  — all agents listen here (unison mode)
    murphy:signals:results    — agents publish outcomes here
    murphy:signals:planning   — planning signals for Rosetta to decompose

  Each message is JSON:
    {
      "signal_id": str,
      "signal_type": str,
      "domain": str,
      "intent_hint": str,
      "mode": "unison"|"tandem"|"separate"|"planning",
      "origin_agent": str|null,
      "payload": dict,
      "timestamp": ISO str
    }

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("murphy.swarm_bus")

# ── Redis connection ──────────────────────────────────────────────────────────

_redis_client = None
_redis_lock = threading.Lock()

def _get_redis():
    """Get (or lazily create) the Redis client."""
    global _redis_client
    with _redis_lock:
        if _redis_client is not None:
            try:
                _redis_client.ping()
                return _redis_client
            except Exception:
                _redis_client = None

        try:
            import redis as _redis
            url = os.environ.get("REDIS_URL", "")
            password = os.environ.get("REDIS_PASSWORD", "")
            if url:
                _redis_client = _redis.from_url(url, decode_responses=True, socket_timeout=5)
            elif password:
                _redis_client = _redis.Redis(
                    host="localhost", port=6379, password=password,
                    decode_responses=True, socket_timeout=5
                )
            else:
                _redis_client = _redis.Redis(host="localhost", port=6379, decode_responses=True, socket_timeout=5)
            _redis_client.ping()
            logger.info("SwarmBus: Redis connected")
            return _redis_client
        except Exception as e:
            logger.warning("SwarmBus: Redis unavailable — %s", e)
            return None


# ── Channel names ─────────────────────────────────────────────────────────────

CHANNEL_BROADCAST = "murphy:signals:broadcast"
CHANNEL_RESULTS   = "murphy:signals:results"
CHANNEL_PLANNING  = "murphy:signals:planning"

def domain_channel(domain: str) -> str:
    return f"murphy:signals:{domain}"


# ── Signal modes ──────────────────────────────────────────────────────────────

class SignalMode:
    UNISON   = "unison"    # all agents receive and respond
    TANDEM   = "tandem"    # pipeline: A → B → C
    SEPARATE = "separate"  # only the target domain agent handles it
    PLANNING = "planning"  # Rosetta decomposes then dispatches sub-signals


# ── Core publish ─────────────────────────────────────────────────────────────

def publish(
    signal_type: str,
    intent_hint: str,
    domain: str = "system",
    mode: str = SignalMode.SEPARATE,
    payload: Dict = None,
    origin_agent: str = None,
    signal_id: str = None,
) -> str:
    """
    Publish a signal to the bus.
    Returns the signal_id.
    """
    sid = signal_id or str(uuid.uuid4())
    message = {
        "signal_id": sid,
        "signal_type": signal_type,
        "domain": domain,
        "intent_hint": intent_hint,
        "mode": mode,
        "origin_agent": origin_agent,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    msg_json = json.dumps(message)
    r = _get_redis()
    if r is None:
        logger.warning("SwarmBus.publish: Redis unavailable, signal %s dropped", sid)
        return sid

    try:
        if mode == SignalMode.UNISON:
            r.publish(CHANNEL_BROADCAST, msg_json)
        elif mode == SignalMode.PLANNING:
            r.publish(CHANNEL_PLANNING, msg_json)
        else:
            r.publish(domain_channel(domain), msg_json)
        logger.debug("SwarmBus: published %s [%s/%s]", sid, domain, mode)
    except Exception as e:
        logger.warning("SwarmBus.publish error: %s", e)

    return sid


def publish_result(
    agent_id: str,
    signal_id: str,
    outcome: str,
    result: Dict = None,
    next_domain: str = None,
) -> None:
    """
    Agent publishes its result to the results channel.
    If next_domain is set, also publishes a tandem signal to that domain.
    """
    r = _get_redis()
    if r is None:
        return

    result_msg = json.dumps({
        "type": "agent_result",
        "agent_id": agent_id,
        "signal_id": signal_id,
        "outcome": outcome,
        "result": result or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r.publish(CHANNEL_RESULTS, result_msg)
        # Tandem: chain to next agent
        if next_domain:
            publish(
                signal_type="tandem_handoff",
                intent_hint=f"Handoff from {agent_id}: {outcome[:80]}",
                domain=next_domain,
                mode=SignalMode.TANDEM,
                payload=result or {},
                origin_agent=agent_id,
                signal_id=str(uuid.uuid4()),
            )
    except Exception as e:
        logger.warning("SwarmBus.publish_result error: %s", e)


# ── Subscriber / listener thread ──────────────────────────────────────────────

class AgentBusListener:
    """
    Per-agent Redis subscriber.
    Listens on: domain channel + broadcast channel (if unison capable).
    Calls coordinator.dispatch() when a message arrives.
    """

    def __init__(self, agent_id: str, domains: List[str], unison: bool = True):
        self.agent_id = agent_id
        self.domains = domains
        self.unison = unison
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self, on_signal: Callable[[Dict], None]) -> bool:
        """Start listening. on_signal called with parsed signal dict."""
        r = _get_redis()
        if r is None:
            logger.warning("AgentBusListener[%s]: Redis unavailable, not starting", self.agent_id)
            return False

        channels = [domain_channel(d) for d in self.domains]
        if self.unison:
            channels.append(CHANNEL_BROADCAST)

        def _listen():
            try:
                pubsub = r.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(*channels)
                logger.info("AgentBusListener[%s]: subscribed to %s", self.agent_id, channels)
                for raw in pubsub.listen():
                    if self._stop.is_set():
                        break
                    if raw and raw.get("type") == "message":
                        try:
                            signal = json.loads(raw["data"])
                            on_signal(signal)
                        except Exception as e:
                            logger.warning("AgentBusListener[%s] parse error: %s", self.agent_id, e)
            except Exception as e:
                logger.warning("AgentBusListener[%s] listen error: %s", self.agent_id, e)

        self._thread = threading.Thread(
            target=_listen,
            daemon=True,
            name=f"swarm-bus-{self.agent_id}"
        )
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()


# ── Live feed — recent signals for UI ────────────────────────────────────────

_FEED_KEY    = "murphy:bus:feed"
_FEED_MAX    = 100   # keep last 100 events

def record_bus_event(event: Dict) -> None:
    """Push an event to the Redis list used by the UI live feed."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.lpush(_FEED_KEY, json.dumps(event))
        r.ltrim(_FEED_KEY, 0, _FEED_MAX - 1)
    except Exception:
        pass

def get_bus_feed(limit: int = 20) -> List[Dict]:
    """Return recent bus events for the UI."""
    r = _get_redis()
    if r is None:
        return []
    try:
        raw = r.lrange(_FEED_KEY, 0, limit - 1)
        return [json.loads(x) for x in raw]
    except Exception:
        return []


# ── Planning mode — Rosetta decomposes a task ─────────────────────────────────

TANDEM_PIPELINES = {
    "research_and_report": ["collector", "translator", "exec_admin"],
    "monitor_and_alert":   ["prod_ops", "hitl"],
    "audit_and_log":       ["auditor", "exec_admin"],
    "collect_and_infer":   ["collector", "translator"],
}

def dispatch_planning(
    task: str,
    pipeline: List[str] = None,
    payload: Dict = None,
) -> List[str]:
    """
    Break a planning task into tandem signals dispatched to a pipeline of agents.
    Returns list of signal_ids.
    """
    if pipeline is None:
        pipeline = ["collector", "translator", "exec_admin"]

    signal_ids = []
    prev_sid = None
    for i, domain in enumerate(pipeline):
        sid = publish(
            signal_type="planning_step",
            intent_hint=f"[Step {i+1}/{len(pipeline)}] {task}",
            domain=domain,
            mode=SignalMode.TANDEM if i > 0 else SignalMode.PLANNING,
            payload={**(payload or {}), "step": i, "total_steps": len(pipeline), "prev_signal": prev_sid},
            signal_id=str(uuid.uuid4()),
        )
        signal_ids.append(sid)
        prev_sid = sid
    return signal_ids


# ── Status ────────────────────────────────────────────────────────────────────

def bus_status() -> Dict:
    r = _get_redis()
    if r is None:
        return {"connected": False, "error": "Redis unavailable"}
    try:
        info = r.info("clients")
        feed_len = r.llen(_FEED_KEY)
        return {
            "connected": True,
            "connected_clients": info.get("connected_clients", 0),
            "feed_events": feed_len,
            "channels": {
                "broadcast": CHANNEL_BROADCAST,
                "results": CHANNEL_RESULTS,
                "planning": CHANNEL_PLANNING,
            },
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ── Singleton ─────────────────────────────────────────────────────────────────
_listeners: Dict[str, AgentBusListener] = {}

def get_listener(agent_id: str, domains: List[str]) -> AgentBusListener:
    if agent_id not in _listeners:
        _listeners[agent_id] = AgentBusListener(agent_id, domains)
    return _listeners[agent_id]

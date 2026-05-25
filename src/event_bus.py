"""
PATCH-OPT-4 — Murphy Event Bus (Redis pub/sub)
================================================

WHAT THIS IS:
  Async pub/sub messaging between the 6 Murphy services. Uses the existing
  Redis container (already running on 127.0.0.1:6379, previously unused).
  Replaces the in-process event spine fanout — events now reach every
  service that subscribes, regardless of which process they run in.

WHY IT EXISTS:
  Before the split, PATCH-400 (Event Spine) was in-process: every audit
  event lived in one Python dict. After the split, edge/core/ops can't
  see each other's events. Redis pub/sub makes the spine span all
  services without any service knowing about the others.

HOW IT FITS:
  - PATCH-400 Event Spine still hash-chains its audit log (single source
    of truth for the chain)
  - publish() writes to the chain AND fans out via Redis
  - subscribe() registers a coroutine handler per topic
  - On boot, each service subscribes to topics it cares about

KEY CONCEPTS:
  - Topic: dotted name like "audit.event", "household.profile.updated",
    "robot.command.sent", "internal_auth.failed"
  - Payload: JSON-serializable dict
  - Wildcards: "audit.*" matches "audit.event", "audit.alert", etc.
  - At-most-once delivery (Redis pub/sub is fire-and-forget; for durable
    delivery use the hash-chained spine + replay)

ENDPOINTS / PUBLIC SURFACE:
  - publish(topic, payload) — fan out
  - subscribe(topic, handler) — register coroutine
  - GET /api/bus/status — connection health + counters
  - GET /api/bus/topics — what this service is listening to

DEPENDENCIES:
  - redis (Python client, already in venv)
  - asyncio for the listener task
  - PATCH-400 event_spine (optional — bus calls into it if available)

REDIS DETAILS:
  - URL: redis://127.0.0.1:6379/1 (db 1 reserved for bus; db 0 for app cache)
  - Container: murphy-redis (already healthy 26h+)
  - No password (loopback only, network-isolated)

KNOWN LIMITS:
  - No durable replay yet (events lost if subscriber down)
  - No exactly-once semantics — use hash-chain for that
  - No back-pressure (publisher never blocks)

LAST UPDATED: 2026-05-24 by Murphy
"""
from __future__ import annotations

import os, json, asyncio, logging, time, fnmatch
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("murphy.event_bus")

REDIS_URL = os.environ.get("MURPHY_BUS_REDIS_URL", "redis://127.0.0.1:6379/1")
CHANNEL_PREFIX = "murphy:bus:"


# ── State ───────────────────────────────────────────────────────────────────
_redis_pub = None        # sync client for publish path
_redis_sub_task = None   # asyncio task running the listener
_handlers: List[Tuple[str, Callable]] = []   # (topic_pattern, handler)
_stats = {
    "connected": False,
    "published": 0,
    "received": 0,
    "errors": 0,
    "last_error": None,
    "subscribers_started_at": None,
}
_SERVICE_NAME: str = "unknown"


# ── Lazy Redis connection ───────────────────────────────────────────────────
def _get_redis():
    """Return a sync Redis client. Lazy-init."""
    global _redis_pub
    if _redis_pub is not None:
        return _redis_pub
    try:
        import redis  # type: ignore
        _redis_pub = redis.Redis.from_url(REDIS_URL, decode_responses=True,
                                          socket_connect_timeout=2,
                                          socket_timeout=2)
        _redis_pub.ping()
        _stats["connected"] = True
        log.info("event_bus connected to %s", REDIS_URL)
    except Exception as e:
        _stats["connected"] = False
        _stats["last_error"] = f"{type(e).__name__}: {e}"
        log.warning("event_bus Redis unreachable (%s) — running in NO-OP mode", e)
        _redis_pub = None
    return _redis_pub


# ── Publish ─────────────────────────────────────────────────────────────────
def publish(topic: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    """
    Publish an event. Returns True if delivered to Redis, False otherwise.
    Never raises — bus failures should never break business logic.
    """
    payload = payload or {}
    payload.setdefault("ts", time.time())
    payload.setdefault("origin_service", _SERVICE_NAME)
    payload.setdefault("topic", topic)

    # Best-effort: also hand to event spine if available (for hash-chain)
    try:
        from event_spine import emit  # type: ignore
        emit(topic, payload)
    except Exception:
        pass

    r = _get_redis()
    if r is None:
        return False
    try:
        channel = CHANNEL_PREFIX + topic
        r.publish(channel, json.dumps(payload, default=str))
        _stats["published"] += 1
        return True
    except Exception as e:
        _stats["errors"] += 1
        _stats["last_error"] = f"{type(e).__name__}: {e}"
        log.warning("event_bus publish failed: %s", e)
        return False


# ── Subscribe ───────────────────────────────────────────────────────────────
def subscribe(topic_pattern: str, handler: Callable) -> None:
    """
    Register an async handler for events matching topic_pattern.

    Pattern can be:
      - "audit.event"     exact match
      - "audit.*"         single-segment wildcard
      - "*"               everything

    Handler signature: async def handler(topic: str, payload: dict): ...
    """
    _handlers.append((topic_pattern, handler))
    log.info("event_bus subscribed: %s -> %s", topic_pattern, handler.__name__)


def _matches(pattern: str, topic: str) -> bool:
    return fnmatch.fnmatchcase(topic, pattern)


# ── Listener loop ──────────────────────────────────────────────────────────
async def _listener_loop():
    """Long-running task: subscribes to murphy:bus:* and dispatches."""
    import redis.asyncio as aioredis  # type: ignore

    while True:
        try:
            r = aioredis.from_url(REDIS_URL, decode_responses=True)
            await r.ping()
            _stats["connected"] = True
            _stats["subscribers_started_at"] = time.time()

            pubsub = r.pubsub()
            await pubsub.psubscribe(CHANNEL_PREFIX + "*")
            log.info("event_bus listener live on %s%s", CHANNEL_PREFIX, "*")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue
                channel = message["channel"]
                topic = channel.removeprefix(CHANNEL_PREFIX) \
                    if hasattr(channel, "removeprefix") \
                    else channel[len(CHANNEL_PREFIX):]
                try:
                    payload = json.loads(message["data"])
                except Exception:
                    payload = {"raw": message["data"]}

                _stats["received"] += 1

                # Dispatch to all matching handlers (concurrent)
                tasks = []
                for pattern, handler in _handlers:
                    if _matches(pattern, topic):
                        tasks.append(_safe_invoke(handler, topic, payload))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

        except asyncio.CancelledError:
            log.info("event_bus listener cancelled")
            raise
        except Exception as e:
            _stats["connected"] = False
            _stats["errors"] += 1
            _stats["last_error"] = f"listener: {type(e).__name__}: {e}"
            log.warning("event_bus listener error (will retry in 5s): %s", e)
            await asyncio.sleep(5)


async def _safe_invoke(handler: Callable, topic: str, payload: Dict[str, Any]):
    try:
        result = handler(topic, payload)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        _stats["errors"] += 1
        log.exception("event_bus handler %s crashed on %s: %s",
                      handler.__name__, topic, e)


async def start_listener(service_name: str):
    """Call this once from your FastAPI startup event."""
    global _redis_sub_task, _SERVICE_NAME
    _SERVICE_NAME = service_name
    if _redis_sub_task and not _redis_sub_task.done():
        return
    _redis_sub_task = asyncio.create_task(_listener_loop())
    log.info("event_bus listener started for service=%s", service_name)


async def stop_listener():
    global _redis_sub_task
    if _redis_sub_task:
        _redis_sub_task.cancel()
        try:
            await _redis_sub_task
        except asyncio.CancelledError:
            pass
        _redis_sub_task = None


# ── Diagnostics ────────────────────────────────────────────────────────────
def status() -> Dict[str, Any]:
    return {
        "service": _SERVICE_NAME,
        "redis_url": REDIS_URL,
        "connected": _stats["connected"],
        "published": _stats["published"],
        "received": _stats["received"],
        "errors": _stats["errors"],
        "last_error": _stats["last_error"],
        "subscribers_count": len(_handlers),
        "subscribers_started_at": _stats["subscribers_started_at"],
        "patterns": [p for p, _ in _handlers],
    }


def init_bus_routes(app, service_name: str):
    """Mount /api/bus/* on the FastAPI app."""
    from fastapi import Depends
    from fastapi.responses import JSONResponse
    from internal_auth import require_internal  # type: ignore

    @app.get("/api/bus/status")
    async def bus_status():
        return JSONResponse(status())

    @app.get("/api/bus/topics")
    async def bus_topics():
        return JSONResponse({
            "service": service_name,
            "patterns": [p for p, _ in _handlers],
        })

    @app.post("/api/bus/publish")
    async def bus_publish_internal(body: dict, _=Depends(require_internal)):
        topic = body.get("topic")
        payload = body.get("payload", {})
        if not topic:
            return JSONResponse({"ok": False, "error": "missing_topic"}, status_code=400)
        ok = publish(topic, payload)
        return JSONResponse({"ok": ok, "topic": topic})

    # Startup hook
    @app.on_event("startup")
    async def _bus_start():
        await start_listener(service_name)

    @app.on_event("shutdown")
    async def _bus_stop():
        await stop_listener()

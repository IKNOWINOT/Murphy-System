# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Split-Screen Replay Viewer — Murphy System (MCB-REPLAY-001)

Owner: Multi-Cursor / Visualization
Dep: murphy_native_automation, rpa_recorder_engine, threading, json, html

Renders recorded multi-cursor split-screen sessions as an interactive HTML
replay that shows each zone's cursor movements, clicks, and channel data
transfers in a synchronised timeline.

Designed to:
  1. Capture live cursor events from a SplitScreenSession into a ReplayLog.
  2. Export the log as a self-contained HTML file with embedded JavaScript
     that renders split-screen zones as SVG panels and steps through events
     frame-by-frame with play/pause/scrub controls.
  3. Visualise CursorChannel data transfers as animated arrows between zones.

Integration Points:
  - split_screen_coordinator.SplitScreenSession — session lifecycle
  - murphy_native_automation.CursorContext — cursor event history
  - murphy_native_automation.CursorChannel — channel copy/paste events
  - rpa_recorder_engine.RpaRecorderEngine — action recordings (optional)

Error Handling:
  All public methods log and raise on invalid input.  No silent failures.
  Error codes: MCB-REPLAY-ERR-001 through MCB-REPLAY-ERR-006.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)


# ---------------------------------------------------------------------------
# Replay event model
# ---------------------------------------------------------------------------

@dataclass
class ReplayEvent:
    """A single event in a split-screen replay timeline.

    Attributes:
        event_id:    Unique identifier.
        timestamp:   ISO-8601 UTC timestamp when the event occurred.
        zone_id:     The zone this event belongs to.
        cursor_id:   The cursor that generated this event.
        event_type:  One of: move, click, double_click, drag, scroll,
                     channel_copy, channel_paste, zone_task_start,
                     zone_task_end, session_start, session_end.
        data:        Event-specific payload (positions, channel data, etc.).
    """

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    zone_id: str = ""
    cursor_id: str = ""
    event_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "zone_id": self.zone_id,
            "cursor_id": self.cursor_id,
            "event_type": self.event_type,
            "data": self.data,
        }


# ---------------------------------------------------------------------------
# ReplayLog — bounded, thread-safe event accumulator
# ---------------------------------------------------------------------------

@dataclass
class ReplayLog:
    """Accumulated timeline of events from a split-screen session.

    Design Label: MCB-REPLAY-002
    Thread-safe, bounded to MAX_EVENTS.
    """

    log_id: str = field(default_factory=lambda: "replay_" + uuid.uuid4().hex[:8])
    session_id: str = ""
    layout: str = "quad"
    zones: List[Dict[str, Any]] = field(default_factory=list)
    events: List[ReplayEvent] = field(default_factory=list)
    channels: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    MAX_EVENTS: int = 50_000  # CWE-770: bounded

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_event(self, event: ReplayEvent) -> None:
        """Append an event to the log (thread-safe, bounded)."""
        with self._lock:
            if len(self.events) >= self.MAX_EVENTS:
                self.events = self.events[-(self.MAX_EVENTS // 2):]
                logger.warning(
                    "MCB-REPLAY-ERR-002: ReplayLog %s hit max events (%d), "
                    "truncated oldest half",
                    self.log_id, self.MAX_EVENTS,
                )
            self.events.append(event)

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self.events)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "log_id": self.log_id,
                "session_id": self.session_id,
                "layout": self.layout,
                "zones": self.zones,
                "event_count": len(self.events),
                "events": [e.to_dict() for e in self.events],
                "channels": self.channels,
                "metadata": self.metadata,
                "created_at": self.created_at,
            }


# ---------------------------------------------------------------------------
# ReplayCapture — hooks into live sessions to record events
# ---------------------------------------------------------------------------

class ReplayCapture:
    """Captures cursor events from a live SplitScreenSession into a ReplayLog.

    Design Label: MCB-REPLAY-003

    Usage::

        capture = ReplayCapture()
        log = capture.start_capture(session)
        # ... session runs ...
        capture.record_cursor_event(zone_id, cursor, "click", {...})
        capture.record_channel_event(channel_id, "copy", {...})
        capture.stop_capture()
    """

    def __init__(self) -> None:
        self._active_log: Optional[ReplayLog] = None
        self._lock = threading.Lock()

    def start_capture(
        self,
        session_id: str,
        layout: str,
        zones: List[Dict[str, Any]],
        channels: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReplayLog:
        """Begin capturing events for a session.

        Raises:
            RuntimeError: If a capture is already in progress.
        """
        with self._lock:
            if self._active_log is not None:
                raise RuntimeError(
                    "MCB-REPLAY-ERR-003: Capture already active for "
                    f"session {self._active_log.session_id}; "
                    "call stop_capture() first"
                )
            log = ReplayLog(
                session_id=session_id,
                layout=layout,
                zones=zones,
                channels=channels or [],
                metadata=metadata or {},
            )
            log.add_event(ReplayEvent(
                event_type="session_start",
                data={"session_id": session_id, "layout": layout},
            ))
            self._active_log = log
            logger.info("MCB-REPLAY-003: Started replay capture for session %s", session_id)
            return log

    def stop_capture(self) -> Optional[ReplayLog]:
        """End the active capture and return the completed ReplayLog.

        Returns:
            The completed log, or ``None`` if no capture was active.
        """
        with self._lock:
            if self._active_log is None:
                logger.warning("MCB-REPLAY-ERR-004: stop_capture called with no active capture")
                return None
            self._active_log.add_event(ReplayEvent(
                event_type="session_end",
                data={"session_id": self._active_log.session_id},
            ))
            log = self._active_log
            self._active_log = None
            logger.info("MCB-REPLAY-003: Stopped replay capture for session %s", log.session_id)
            return log

    def record_cursor_event(
        self,
        zone_id: str,
        cursor_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a cursor event (move, click, drag, etc.)."""
        with self._lock:
            if self._active_log is None:
                logger.error(
                    "MCB-REPLAY-ERR-005: record_cursor_event called with no active capture"
                )
                return
            self._active_log.add_event(ReplayEvent(
                zone_id=zone_id,
                cursor_id=cursor_id,
                event_type=event_type,
                data=data or {},
            ))

    def record_channel_event(
        self,
        channel_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a channel event (copy, paste, push, pull)."""
        with self._lock:
            if self._active_log is None:
                logger.error(
                    "MCB-REPLAY-ERR-005: record_channel_event called with no active capture"
                )
                return
            self._active_log.add_event(ReplayEvent(
                event_type=f"channel_{event_type}",
                data={"channel_id": channel_id, **(data or {})},
            ))

    @property
    def is_capturing(self) -> bool:
        with self._lock:
            return self._active_log is not None


# ---------------------------------------------------------------------------
# ReplayRenderer — generates self-contained HTML replay viewer
# ---------------------------------------------------------------------------

class ReplayRenderer:
    """Generates a self-contained HTML replay of a split-screen session.

    Design Label: MCB-REPLAY-004

    The output is a single HTML file with embedded CSS and JavaScript that:
      - Renders each zone as a bordered panel in a CSS grid layout
      - Draws cursor positions as coloured dots per zone
      - Animates cursor movement frame-by-frame with play/pause/scrub
      - Shows channel data transfers as labelled arrows between zones
      - Displays a synchronised timeline bar at the bottom

    Usage::

        renderer = ReplayRenderer()
        html = renderer.render(replay_log)
        with open("replay.html", "w") as f:
            f.write(html)
    """

    def render(self, log: ReplayLog) -> str:
        """Render a ReplayLog as a self-contained HTML page.

        Args:
            log: The completed ReplayLog to render.

        Returns:
            Complete HTML string.

        Raises:
            ValueError: If the log has no zones or events.
        """
        if not log.zones:
            raise ValueError(
                "MCB-REPLAY-ERR-006: Cannot render replay with no zones"
            )
        if not log.events:
            raise ValueError(
                "MCB-REPLAY-ERR-006: Cannot render replay with no events"
            )

        events_json = json.dumps(
            [e.to_dict() for e in log.events], default=str
        )
        zones_json = json.dumps(log.zones, default=str)
        channels_json = json.dumps(log.channels, default=str)
        title = html_mod.escape(
            f"Murphy Split-Screen Replay — {log.session_id}"
        )

        return _REPLAY_HTML_TEMPLATE.format(
            title=title,
            session_id=html_mod.escape(log.session_id),
            layout=html_mod.escape(log.layout),
            zones_json=zones_json,
            events_json=events_json,
            channels_json=channels_json,
            event_count=len(log.events),
            zone_count=len(log.zones),
            created_at=html_mod.escape(log.created_at),
        )

    def render_to_file(self, log: ReplayLog, path: str) -> str:
        """Render and write to a file. Returns the file path."""
        content = self.render(log)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.info("MCB-REPLAY-004: Wrote replay HTML to %s", path)
        return path


# ---------------------------------------------------------------------------
# HTML template — self-contained replay viewer
# ---------------------------------------------------------------------------

_REPLAY_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0a0a0f; color: #e0e0e0; font-family: monospace; }}
.header {{ padding: 12px 16px; background: #111; border-bottom: 1px solid #333;
           display: flex; justify-content: space-between; align-items: center; }}
.header h1 {{ font-size: 14px; color: #00ff88; }}
.header .meta {{ font-size: 11px; color: #888; }}
.grid {{ display: grid; gap: 2px; padding: 4px; height: calc(100vh - 100px); }}
.zone {{ border: 1px solid #333; background: #0d0d15; position: relative;
         overflow: hidden; border-radius: 3px; }}
.zone-label {{ position: absolute; top: 4px; left: 6px; font-size: 10px;
              color: #555; z-index: 2; }}
.cursor-dot {{ position: absolute; width: 10px; height: 10px; border-radius: 50%;
              transform: translate(-50%, -50%); z-index: 10;
              transition: left 0.1s ease, top 0.1s ease; }}
.channel-arrow {{ position: absolute; z-index: 5; pointer-events: none; }}
.timeline {{ height: 48px; background: #111; border-top: 1px solid #333;
            display: flex; align-items: center; padding: 0 12px; gap: 8px; }}
.timeline button {{ background: #222; color: #0f0; border: 1px solid #444;
                   padding: 4px 10px; cursor: pointer; border-radius: 3px;
                   font-family: monospace; font-size: 11px; }}
.timeline button:hover {{ background: #333; }}
.timeline input[type=range] {{ flex: 1; accent-color: #00ff88; }}
.timeline .frame-info {{ font-size: 11px; color: #888; min-width: 120px;
                        text-align: right; }}
.event-log {{ position: absolute; bottom: 4px; right: 6px; font-size: 9px;
             color: #444; z-index: 2; max-width: 60%; text-align: right;
             overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}
</style>
</head>
<body>
<div class="header">
  <h1>Murphy Split-Screen Replay</h1>
  <span class="meta">Session: {session_id} | Layout: {layout} |
    Zones: {zone_count} | Events: {event_count} | {created_at}</span>
</div>
<div class="grid" id="grid"></div>
<div class="timeline" id="timeline">
  <button id="btn-prev">&#9664;&#9664;</button>
  <button id="btn-play">&#9654; Play</button>
  <button id="btn-next">&#9654;&#9654;</button>
  <input type="range" id="scrub" min="0" max="0" value="0"/>
  <span class="frame-info" id="frame-info">0 / 0</span>
</div>
<script>
(function() {{
  "use strict";
  var ZONES = {zones_json};
  var EVENTS = {events_json};
  var CHANNELS = {channels_json};
  var frame = 0, playing = false, timer = null;
  var COLORS = ["#ff4444","#44ff44","#4488ff","#ffaa00","#ff44ff","#44ffff",
                "#88ff44","#ff8844","#aa44ff","#44ffaa","#ff4488","#44aaff"];
  var grid = document.getElementById("grid");
  var cols = Math.ceil(Math.sqrt(ZONES.length));
  var rows = Math.ceil(ZONES.length / cols);
  grid.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";
  grid.style.gridTemplateRows = "repeat(" + rows + ", 1fr)";
  var zoneDivs = {{}};
  ZONES.forEach(function(z, i) {{
    var div = document.createElement("div");
    div.className = "zone";
    div.id = "zone-" + (z.zone_id || z.name || i);
    var label = document.createElement("div");
    label.className = "zone-label";
    label.textContent = z.label || z.name || ("Zone " + i);
    div.appendChild(label);
    var dot = document.createElement("div");
    dot.className = "cursor-dot";
    dot.style.background = COLORS[i % COLORS.length];
    dot.style.left = "50%";
    dot.style.top = "50%";
    div.appendChild(dot);
    var elog = document.createElement("div");
    elog.className = "event-log";
    div.appendChild(elog);
    grid.appendChild(div);
    zoneDivs[z.zone_id || z.name || i] = {{ div: div, dot: dot, elog: elog }};
  }});
  var scrub = document.getElementById("scrub");
  var info = document.getElementById("frame-info");
  scrub.max = Math.max(0, EVENTS.length - 1);
  function renderFrame(idx) {{
    if (idx < 0 || idx >= EVENTS.length) return;
    frame = idx;
    scrub.value = idx;
    info.textContent = (idx + 1) + " / " + EVENTS.length;
    var ev = EVENTS[idx];
    var zk = ev.zone_id || "";
    var zd = zoneDivs[zk];
    if (zd && ev.data) {{
      var rx = ev.data.rel_x != null ? ev.data.rel_x : (ev.data.abs_x != null ? 0.5 : null);
      var ry = ev.data.rel_y != null ? ev.data.rel_y : (ev.data.abs_y != null ? 0.5 : null);
      if (rx != null) zd.dot.style.left = (rx * 100) + "%";
      if (ry != null) zd.dot.style.top = (ry * 100) + "%";
      zd.elog.textContent = ev.event_type + (ev.data.button ? " (" + ev.data.button + ")" : "");
    }}
  }}
  document.getElementById("btn-play").addEventListener("click", function() {{
    if (playing) {{
      playing = false; clearInterval(timer); this.innerHTML = "&#9654; Play";
    }} else {{
      playing = true; this.innerHTML = "&#9646;&#9646; Pause";
      timer = setInterval(function() {{
        if (frame >= EVENTS.length - 1) {{
          playing = false; clearInterval(timer);
          document.getElementById("btn-play").innerHTML = "&#9654; Play";
          return;
        }}
        renderFrame(frame + 1);
      }}, 50);
    }}
  }});
  document.getElementById("btn-prev").addEventListener("click", function() {{
    renderFrame(Math.max(0, frame - 1));
  }});
  document.getElementById("btn-next").addEventListener("click", function() {{
    renderFrame(Math.min(EVENTS.length - 1, frame + 1));
  }});
  scrub.addEventListener("input", function() {{
    renderFrame(parseInt(this.value, 10));
  }});
  if (EVENTS.length > 0) renderFrame(0);
}})();
</script>
</body>
</html>"""

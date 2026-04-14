# SPDX-License-Identifier: BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post
#
# Murphy Nautilus File-Manager Plugin
# Adds right-click "Process with Murphy" context menu entries.
#
# ---------------------------------------------------------------------------
# Error-code registry
# ---------------------------------------------------------------------------
# MURPHY-NAUTILUS-ERR-001  HTTP request to Murphy API failed (URLError)
# MURPHY-NAUTILUS-ERR-002  D-Bus fallback invocation failed
# ---------------------------------------------------------------------------

"""Nautilus extension — Process files with Murphy System."""

import logging
import os
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from gi.repository import GObject, Nautilus, GLib

logger = logging.getLogger("murphy-nautilus")

MURPHY_API = os.environ.get("MURPHY_API_URL", "http://localhost:8000")
MURPHY_BRAND_ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "brand", "murphy-icon-symbolic.svg",
)

# Map file extensions / MIME prefixes to Murphy API endpoints.
_ROUTE_MAP = {
    ".pdf":  "/api/document/process",
    ".csv":  "/api/data-pipeline/process",
    ".tsv":  "/api/data-pipeline/process",
    ".py":   "/api/code-repair/process",
    ".png":  "/api/vision/process",
    ".jpg":  "/api/vision/process",
    ".jpeg": "/api/vision/process",
    ".webp": "/api/vision/process",
    ".gif":  "/api/vision/process",
    ".bmp":  "/api/vision/process",
}

FALLBACK_ENDPOINT = "/api/forge/process"


def _endpoint_for(filepath: str) -> str:
    """Choose the best Murphy API endpoint for a file."""
    ext = Path(filepath).suffix.lower()
    return _ROUTE_MAP.get(ext, FALLBACK_ENDPOINT)


def _send_to_murphy(filepath: str, endpoint: str) -> dict:
    """POST a file to the Murphy API and return the JSON response."""
    with open(filepath, "rb") as fh:
        data = fh.read()

    boundary = "----MurphyNautilusBoundary"
    filename = os.path.basename(filepath)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

    req = Request(
        f"{MURPHY_API}{endpoint}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except URLError as exc:  # MURPHY-NAUTILUS-ERR-001
        logger.warning("MURPHY-NAUTILUS-ERR-001: API request failed: %s", exc)
        return _send_via_dbus(filepath)


def _send_via_dbus(filepath: str) -> dict:
    """Fallback: invoke org.murphy.Forge.Build over D-Bus."""
    try:
        import subprocess

        result = subprocess.run(
            [
                "gdbus", "call", "--system",
                "--dest", "org.murphy.Forge",
                "--object-path", "/org/murphy/Forge",
                "--method", "org.murphy.Forge.Build",
                f"file://{filepath}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {"status": "dbus", "output": result.stdout.strip()}
    except Exception as exc:  # MURPHY-NAUTILUS-ERR-002
        logger.error("MURPHY-NAUTILUS-ERR-002: D-Bus fallback failed: %s", exc)
        return {"error": str(exc)}


class MurphyMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    """Provides 'Process with Murphy' context-menu entries in Nautilus."""

    def get_file_items(self, files):
        if not files:
            return []

        items = []
        for f in files:
            if f.is_directory():
                continue

            filepath = f.get_location().get_path()
            if filepath is None:
                continue

            item = Nautilus.MenuItem(
                name=f"MurphyProcess::{os.path.basename(filepath)}",
                label="⚙ Process with Murphy System",
                tip=f"Send {os.path.basename(filepath)} to Murphy System for AI processing",
                icon="system-run-symbolic",
            )
            item.connect("activate", self._on_activate, filepath)
            items.append(item)

        if len(files) > 1 and items:
            return items[:1]  # single entry for multi-select

        return items

    def _on_activate(self, _menu_item, filepath):
        """Run the API call in a background thread to avoid blocking."""
        endpoint = _endpoint_for(filepath)
        thread = threading.Thread(
            target=self._process_async,
            args=(filepath, endpoint),
            daemon=True,
        )
        thread.start()

    def _process_async(self, filepath, endpoint):
        logger.info("Processing %s via %s", filepath, endpoint)
        result = _send_to_murphy(filepath, endpoint)
        GLib.idle_add(self._notify_result, filepath, result)

    @staticmethod
    def _notify_result(filepath, result):
        filename = os.path.basename(filepath)
        status = result.get("status", result.get("error", "unknown"))
        logger.info("Murphy result for %s: %s", filename, status)
        return GLib.SOURCE_REMOVE

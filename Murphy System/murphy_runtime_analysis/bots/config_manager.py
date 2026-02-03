"""Configuration caching and reload with checksum validation."""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any, Dict

import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .security_bot import SecurityBot


class ConfigManagerBot:
    """Cache configuration and reload when the file changes."""

    def __init__(self, path: str = "config.yml", secbot: SecurityBot | None = None) -> None:
        self.path = Path(path)
        self.secbot = secbot or SecurityBot()
        self.data: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._observer: Observer | None = None

    def load(self) -> None:
        with self.path.open("r", encoding="utf-8") as fh:
            content = fh.read()
        checksum = hashlib.sha256(content.encode()).hexdigest()
        if self.secbot.config_hash and not self.secbot.validate_config_hash(checksum):
            raise ValueError("Config checksum mismatch")
        self.secbot.store_config_hash(checksum)
        with self._lock:
            self.data = yaml.safe_load(content) or {}

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.data)

    def start_watcher(self) -> None:
        if self._observer:
            return

        class Handler(FileSystemEventHandler):
            def __init__(self, mgr: "ConfigManagerBot") -> None:
                self.mgr = mgr

            def on_modified(self, event):
                if Path(event.src_path) == self.mgr.path:
                    self.mgr.load()

        self._observer = Observer()
        self._observer.schedule(Handler(self), str(self.path.parent), recursive=False)
        self._observer.start()

    def stop_watcher(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

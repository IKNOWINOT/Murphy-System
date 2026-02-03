"""Health-check utilities using watchdog timers."""
from __future__ import annotations

import asyncio
from typing import Callable, Dict

class HealthChecker:
    """Periodically run health checks for bots."""

    def __init__(self, checks: Dict[str, Callable[[], bool]], interval: float = 60.0) -> None:
        self.checks = checks
        self.interval = interval
        self.status = {name: True for name in checks}

    async def run(self) -> None:
        while True:
            tasks = [asyncio.to_thread(check) for check in self.checks.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (name, _), res in zip(self.checks.items(), results):
                self.status[name] = bool(res) if not isinstance(res, Exception) else False
            await asyncio.sleep(self.interval)

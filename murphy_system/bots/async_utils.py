"""Async utilities for network operations."""
from __future__ import annotations

import aiohttp
import asyncio

async def fetch_with_timeout(url: str, timeout: int = 5) -> dict:
    """Fetch JSON from URL with timeout handling."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as resp:
                return await resp.json()
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": None}
